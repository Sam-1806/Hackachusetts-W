"""Grounded Q&A over one InvestigationResult.

Default mode is deterministic: answers are assembled only from fields of the
InvestigationResult, each block labelled ``sourced`` / ``hypothesis`` /
``unknown`` / ``caveat``. An optional live LLM mode (Anthropic Messages API) is
used only when ``FLOODROUTE_LLM=anthropic`` and ``ANTHROPIC_API_KEY`` are set;
its output is validated against the citation list and falls back to the
deterministic answer on any problem.

The frontend ships a TypeScript port of the deterministic responder
(frontend/src/investigation/groundedAssistant.ts); keep the intents in sync.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "assistant_system.md"
NA = "not available / requires site survey"

INTENTS: list[tuple[str, str]] = [
    ("guarantee", r"\b(guarantee|will (it|this) work|fix(ed)? (it|the)|solve|prevent|keep .* open|effective)\b"),
    ("cost", r"(\b(costs?|prices?|budget|dollars?|expensive|cheap|estimates?|how much)\b|\$)"),
    ("inspect", r"\b(inspect\w*|who owns|owner\w*|which assets?|what should (we|i) check|next (steps?|checks?))\b"),
    ("cause", r"\b(caus\w*|why does it flood|root|clog\w*|blocked|catch ?basins?|outfalls?|diagnos\w*|source of (the )?water|where does the water)\b"),
    ("missing", r"\b(missing|unknown|survey|data (do we )?need|gaps?|what else)\b"),
    ("method", r"\b(rais(e|ed|ing)|elevat\w*|berm|deployable|temporary barrier|drain\w*|backflow|tide gate|detour|alternate|seawall)\b"),
    ("candidates", r"\b(options?|measures?|recommend\w*|what (can|could|should)|solutions?|interventions?|investigate)\b"),
    ("network", r"\b(why|priorit\w*|rank\w*|important|journeys?|access|hospital|fire|reachable)\b"),
    ("flood", r"\b(flood\w*|water|depth|scenario|surge|storm|2018|2050|historic\w*|inundat\w*)\b"),
    ("road", r"\b(road facts?|width|lanes?|surface|material|pavement|traffic|aadt|jurisdiction|made of)\b"),
    ("precedent", r"\b(precedent|study|plan(ned)?|morrissey|massdot|dcr|proposal)\b"),
    ("sources", r"\b(sources?|references?|citations?|documents?|links?)\b"),
]

METHOD_KEYWORDS = {
    "raised_roadway": r"rais|elevat",
    "vegetated_berm": r"berm|embankment",
    "deployable_barrier": r"deployable|temporary",
    "drainage_backflow": r"drain|backflow|tide gate|pump",
    "alternate_access": r"detour|alternate",
    "seawall_extension": r"seawall",
}


def _b(kind: str, text: str, cites: list[str] | None = None) -> dict:
    return {"kind": kind, "text": text, "citation_ids": cites or []}


def classify(question: str) -> str:
    q = question.lower()
    for intent, pat in INTENTS:
        if re.search(pat, q):
            return intent
    return "overview"


def _mock_caveat(inv: dict) -> list[dict]:
    if "mock" in json.dumps(inv["provenance"]["input_data_status"]):
        return [_b("caveat", "Network and flood inputs for this corridor are mock fixture values; treat numbers as placeholders.")]
    return []


def _fmt_usd(v: float) -> str:
    return f"${v / 1e6:.1f}M" if v >= 1e6 else f"${v:,.0f}"


def _answer_network(inv: dict) -> list[dict]:
    n = inv["network_impact"]
    if n.get("status") != "available":
        return [_b("unknown", "No network ranking record is available for this corridor yet.")]
    out = [_b("sourced", f"Priority rank {n['priority_rank']} with impact {n['impact_metric']:g} "
                         f"{n['metric_units']} across {n['journeys_total']} representative journeys.",
              ["network_impact"])]
    for j in n["affected_journeys"]:
        if not j.get("reachable", True):
            out.append(_b("sourced", f"{j['label']}: unreachable in the flood scenario (baseline {j['baseline_s']} s).",
                          ["network_impact"]))
        else:
            out.append(_b("sourced", f"{j['label']}: {j['baseline_s']} s normal vs {j['flooded_s']} s flooded.",
                          ["network_impact"]))
    d = n.get("detour_or_disconnect_evidence", {})
    if d.get("detour_flood_exposure") in (None, "unknown"):
        out.append(_b("unknown", "Whether the detour route itself floods in this scenario: not available "
                                 "(needs flood exposure for the detour roads)."))
    return out


def _answer_flood(inv: dict) -> list[dict]:
    out = []
    for f in inv["flood_evidence"]:
        kind = {"future_model": "Projected scenario", "historical_observed": "Observed historical event"}.get(f["kind"], "Scenario")
        out.append(_b("sourced", f"{kind} '{f['label']}': {len(f['roads_exposed'])} corridor roads exposed, "
                                 f"{len(f['roads_unknown'])} unknown (data status: {f['data_status']}).",
                      f["citation_ids"]))
        if f["depth_m"]["status"] != "reported":
            out.append(_b("unknown", f"Flood depth at the road for {f['scenario_id']}: {NA}."))
        out.append(_b("caveat", f["caveat"]))
    return out or [_b("unknown", "No flood evidence is attached to this corridor.")]


def _answer_road(inv: dict) -> list[dict]:
    rf = inv["road_facts"]
    out = []
    for key, e in rf["summary"].items():
        if e["status"] == "not_available":
            out.append(_b("unknown", f"{e['label']}: {NA}."))
            continue
        if "range" in e:
            lo, hi = e["range"]
            val = f"{lo:g}" if lo == hi else f"{lo:g}-{hi:g}"
            val += f" {e['unit']}" if e.get("unit") else ""
        else:
            val = ", ".join(e.get("distinct_values", [])) or str(e.get("value"))
        note = f" ({e['note']})" if e.get("note") else ""
        out.append(_b("sourced", f"{e['label']}: {val}{note}.", rf["citation_ids"]))
    if rf["unmatched_road_ids"]:
        out.append(_b("unknown", f"No inventory match for roads {', '.join(rf['unmatched_road_ids'])}."))
    return out


def _cite_for(inv: dict, ev: dict) -> list[str]:
    ids = {c["citation_id"] for c in inv["citations"]}
    paged = f"{ev['source_id']}#p{ev['pdf_page']}" if ev.get("pdf_page") else None
    if paged and paged in ids:
        return [paged]
    return [ev["source_id"]] if ev["source_id"] in ids else []


def _ev_block(inv: dict, ev: dict, prefix: str = "") -> dict:
    cites = _cite_for(inv, ev)
    label = ev["evidence_type"].replace("_", " ")
    text = f"{prefix}[{label}] {ev['summary']}"
    if ev.get("data_status") == "mock":
        return _b("caveat", text + " (mock fixture value)")
    return _b("sourced", text, cites) if cites else _b("unknown", text + " (source not resolvable)")


def _answer_cause(inv: dict) -> list[dict]:
    d = inv.get("cause_assessment")
    if not d:
        return [_b("unknown", "No cause assessment is attached to this corridor; the cause of flooding is not established.")]
    evs = {e["evidence_id"]: e for e in d["evidence"]}
    out = [_b("caveat", d["finding"]), _b("caveat", d["impacted_location_note"])]
    for c in d["possible_causes"]:
        if c["mechanism"] == "multiple_or_unknown":
            out.append(_b("hypothesis", f"{c['label']}: {c['status']}. {c['status_basis']}"))
            continue
        if c["status"] == "unresolved":
            out.append(_b("unknown", f"{c['label']}: unresolved. Needs: {'; '.join(c['unknowns'][:2])}."))
            continue
        out.append(_b("hypothesis", f"Possibly {c['label'].lower()} ({c['status'].replace('_', ' ')}). {c['status_basis']}"))
        for eid in c["supporting_evidence_ids"][:2]:
            out.append(_ev_block(inv, evs[eid], "Supports: "))
        for eid in c["counter_evidence_ids"][:1]:
            out.append(_ev_block(inv, evs[eid], "Against: "))
        out.append(_b("caveat", f"Does not prove it: {c['does_not_prove']}"))
        out.append(_b("unknown", "Missing: " + "; ".join(c["unknowns"][:2]) + "."))
    return out


def _answer_inspect(inv: dict) -> list[dict]:
    d = inv.get("cause_assessment")
    if not d:
        return [_b("unknown", "No cause assessment is attached; assets to inspect are not identified.")]
    evs = {e["evidence_id"]: e for e in d["evidence"]}
    out = [_b("caveat", d["impacted_location_note"])]
    by_type: dict[str, list[dict]] = {}
    for a in d["assets_to_investigate"]:
        if a["role"] == "possible_cause_asset":
            by_type.setdefault(a["asset_type"], []).append(a)
    for t, items in by_type.items():
        known_owner = sorted({a["owner"] for a in items if a.get("owner")})
        owner = (f"owner as mapped (unverified): {', '.join(known_owner)}" if known_owner else "owner: unknown")
        locs = [(f"{a['asset_id']} at " if a.get("asset_id") else "") + a["location_ref"] for a in items][:2]
        ev_ids = sorted({e for a in items for e in a["evidence_ids"]})
        cites = sorted({c for e in ev_ids if e in evs for c in _cite_for(inv, evs[e])})
        kind = "sourced" if known_owner and cites else "unknown"
        count = d.get("assets_note", "").rstrip(".") if t == "catch_basin" else f"{len(items)} listed"
        out.append(_b(kind, f"{t.replace('_', ' ').title()} ({count}; {owner}): {'; '.join(locs)}.",
                      cites if kind == "sourced" else []))
    if d.get("owner_note"):
        cb = [e for e in d["evidence"] if e["source_id"] == "BWSC.cb"]
        out.append(_b("sourced" if cb else "caveat", d["owner_note"], _cite_for(inv, cb[0]) if cb else []))
    for e in d["evidence"]:
        if e["evidence_id"].startswith("ev-311ref-"):
            out.append(_ev_block(inv, e))
            break
    out.append(_b("hypothesis", "Next checks: " + "; ".join(d["recommended_next_checks"]) + "."))
    return out


def _method_blocks(m: dict) -> list[dict]:
    out = [_b("hypothesis", f"Candidate to investigate: {m['name']}. {m['summary']}")]
    if m.get("cause_gate"):
        out.append(_b("caveat", f"Cause check: {m['cause_gate']}"))
    out += [_b("sourced", p["text"], p["citation_ids"]) for p in m["sourced_points"]]
    out += [_b("hypothesis", h) for h in m["hypotheses"]]
    unknown = [c["check"] for c in m["screening"] if c["status"] == "unknown"]
    if unknown:
        out.append(_b("unknown", "Needed before screening further: " + "; ".join(unknown) + "."))
    out.append(_b("hypothesis", "Ways it could fail: " + "; ".join(m["failure_modes"]) + "."))
    return out


def _answer_candidates(inv: dict) -> list[dict]:
    out = [_b("caveat", f"{len(inv['candidate_methods'])} methods to evaluate, not a recommended fix. "
                        "A licensed engineer must review.")]
    if inv.get("cause_assessment"):
        out.append(_b("caveat", "Cause not established. Start with: "
                                + "; ".join(inv["cause_assessment"]["recommended_next_checks"][:3]) + "."))
    for m in inv["candidate_methods"]:
        first = m["sourced_points"][0] if m["sourced_points"] else None
        txt = f"{m['name']}: {m['summary']}"
        out.append(_b("hypothesis", txt))
        if m.get("cause_gate"):
            out.append(_b("caveat", f"Cause check: {m['cause_gate']}"))
        if first:
            out.append(_b("sourced", first["text"], first["citation_ids"]))
        out.append(_b("hypothesis", f"Could fail by: {m['failure_modes'][0].lower()}."))
    for o in inv.get("other_methods_considered", []):
        out.append(_b("caveat", f"Not offered: {o['name']} ({o['reason']})"))
    return out


def _mentioned_method(question: str) -> str | None:
    q = question.lower()
    return next((mid for mid, pat in METHOD_KEYWORDS.items() if re.search(pat, q)), None)


def _answer_method(inv: dict, question: str) -> list[dict]:
    mid = _mentioned_method(question)
    if mid:
        m = next((c for c in inv["candidate_methods"] if c["method_id"] == mid), None)
        if m:
            return _method_blocks(m)
        other = next((o for o in inv.get("other_methods_considered", []) if o["method_id"] == mid), None)
        if other and other.get("details"):
            return [_b("caveat", f"Not in the top candidates ({other['reason']}), but it passed screening.")] \
                + _method_blocks(other["details"])
        if other:
            return [_b("caveat", f"{other['name']} is not among the current candidates: {other['reason']}")]
    return _answer_candidates(inv)


def _answer_cost(inv: dict, question: str = "") -> list[dict]:
    c = inv["published_cost_examples"]
    d = inv.get("cause_assessment")
    if d and re.search(r"drain|clean|catch ?basin|inlet|pipe|outfall|tide gate|cctv|maint", question.lower()):
        out = [_b("unknown", "cost_estimate_unavailable: no published cost example in the evidence set for drainage, "
                             "maintenance or outfall work. The 2018 barrier/raised-road samples do not apply.")]
        for a in d["cause_matched_actions"]:
            if a["cost_status"] == "cost_estimate_unavailable" and a["mechanism"] != "coastal_overland":
                out.append(_b("hypothesis", f"{a['name']}: inputs needed for a quote: {', '.join(a['quote_inputs'])}."))
        return out
    mid = _mentioned_method(question)
    examples = [e for e in c["examples"] if e["method_id"] == mid] if mid else c["examples"]
    if mid and not examples:
        return [_b("unknown", f"No published cost example in the evidence set for {mid.replace('_', ' ')}."),
                _b("hypothesis", c["estimating_method_guidance"][1])]
    out = [_b("caveat", cav) for cav in c["caveats"][:2]]
    for e in examples:
        dims = e["sample_dimensions"]
        out.append(_b("sourced", f"{e['title']}: {_fmt_usd(e['total_usd'])} for a {dims['length_ft']:,}-ft sample "
                                 f"({_fmt_usd(e['unit_cost']['usd'])} per {e['unit_cost']['per']}, {e['contingency']}). "
                                 f"Excludes: {', '.join(e['excluded'][:4])}.", e["citation_ids"]))
    for other in ([] if mid else c["methods_without_cost_precedent"]):
        out.append(_b("unknown", f"No published cost example in the evidence set for {other.replace('_', ' ')}."))
    out.append(_b("unknown", "Site-specific cost for this corridor: not estimated (separate engineering task)."))
    out.append(_b("hypothesis", c["estimating_method_guidance"][1]))
    return out


def _answer_missing(inv: dict) -> list[dict]:
    return [_b("unknown", f"{m['item']}: {m['status']}. {m['why_needed']}") for m in inv["missing_site_information"]]


def _answer_precedent(inv: dict) -> list[dict]:
    if not inv["local_precedents"]:
        return [_b("unknown", "No local study precedent in the evidence set for this corridor.")]
    out = [_b("sourced", f"[{p['status'].replace('_', ' ')}] {p['text']}", p["citation_ids"]) for p in inv["local_precedents"]]
    out.append(_b("caveat", "Study findings are not evidence that a measure is approved, funded, or built."))
    return out


def _answer_sources(inv: dict) -> list[dict]:
    out = []
    for c in inv["citations"]:
        page = c.get("page") or {}
        p = f", PDF p.{page['pdf_page']}" if page.get("pdf_page") else ""
        out.append(_b("sourced", f"{c['title']}{p}: {c['url'] or 'internal record'}", [c["citation_id"]]))
    return out


def _answer_guarantee(inv: dict, question: str = "") -> list[dict]:
    head = _b("caveat", "This tool cannot say whether a measure would keep the road open. No hydraulic or structural analysis was run.")
    tail = _b("unknown", "Physical effectiveness: requires engineering design and modelling.")
    if re.search(r"drain|catch ?basin|inlet|outfall|pipe|clog|tide gate", question.lower()):
        return [head,
                _b("caveat", "Fixing a drain is recorded as an unquantified hydraulic_or_drainage proposal. It does not "
                             "mark this road or nearby properties safe, and does not change exposure or ranking, until "
                             "validated before/after flood analysis is supplied."),
                _b("hypothesis", "Confirm the cause first (inspect inlets, trace the outfall and owner), then record the "
                                 "proposal; attach hazard_update_evidence once a before/after analysis exists."),
                tail]
    return [head,
            _b("hypothesis", "You can record a hypothetical access_only proposal; the network model then assumes the corridor "
                             "is passable in the scenarios you pick and reranks other corridors. That shows the value IF it worked."),
            tail]


def _answer_overview(inv: dict) -> list[dict]:
    cause = [_b("caveat", inv["cause_assessment"]["finding"])] if inv.get("cause_assessment") else []
    return (_answer_network(inv)[:1] + _answer_flood(inv)[:1] + cause
            + [_b("hypothesis", "Candidate methods: " + ", ".join(m["name"] for m in inv["candidate_methods"]) + ".")]
            + [_b("unknown", f"{len(inv['missing_site_information'])} site facts are missing; ask 'what is missing?'.")])


HANDLERS = {
    "network": _answer_network, "flood": _answer_flood, "road": _answer_road,
    "candidates": _answer_candidates, "cost": _answer_cost, "missing": _answer_missing,
    "precedent": _answer_precedent, "sources": _answer_sources,
    "cause": _answer_cause, "inspect": _answer_inspect, "overview": _answer_overview,
}

FOLLOWUPS = ["Why is this corridor a priority?", "What might be causing the flooding?",
             "What should be inspected, and who owns it?", "What flood evidence do we have?",
             "What options could we investigate?", "What do published costs look like?",
             "What site information is missing?"]


def answer_deterministic(inv: dict, question: str) -> dict:
    intent = classify(question)
    if intent == "method":
        blocks = _answer_method(inv, question)
    elif intent == "cost":
        blocks = _answer_cost(inv, question)
    elif intent == "guarantee":
        blocks = _answer_guarantee(inv, question)
    else:
        blocks = HANDLERS[intent](inv)
    return {"question": question, "intent": intent, "mode": "deterministic",
            "blocks": _mock_caveat(inv) + blocks,
            "suggested_followups": [f for f in FOLLOWUPS if classify(f) != intent][:3]}


# ------------------------------------------------------------------ optional LLM


def _valid_llm_blocks(blocks: object, allowed: set[str]) -> bool:
    if not isinstance(blocks, list) or not blocks:
        return False
    for b in blocks:
        if not isinstance(b, dict) or b.get("kind") not in {"sourced", "hypothesis", "unknown", "caveat"}:
            return False
        cites = b.get("citation_ids", [])
        if not isinstance(cites, list) or any(c not in allowed for c in cites):
            return False
        if b["kind"] == "sourced" and not cites:
            return False
    return True


def answer_llm(inv: dict, question: str, timeout: int = 45) -> dict:
    """Ask a live model. Sends the InvestigationResult (public-source facts and
    fixture values, no credentials) to the Anthropic API. Falls back on error."""
    fallback = answer_deterministic(inv, question)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if os.environ.get("FLOODROUTE_LLM") != "anthropic" or not key:
        return fallback
    model = os.environ.get("FLOODROUTE_LLM_MODEL", "claude-sonnet-4-5")
    body = {
        "model": model, "max_tokens": 1200,
        "system": PROMPT_PATH.read_text(encoding="utf-8"),
        "messages": [{"role": "user", "content":
                      f"<investigation>{json.dumps(inv)}</investigation>\n\nQuestion: {question}"}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https host)
            data = json.loads(resp.read().decode("utf-8"))
        text = "".join(c.get("text", "") for c in data.get("content", []))
        parsed = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception as exc:  # network, JSON, or schema problems -> deterministic answer
        fallback["llm_error"] = type(exc).__name__
        return fallback
    allowed = {c["citation_id"] for c in inv["citations"]} | {"network_impact"}
    if not _valid_llm_blocks(parsed.get("blocks"), allowed):
        fallback["llm_error"] = "invalid_or_uncited_output"
        return fallback
    return {"question": question, "intent": classify(question), "mode": f"llm:{model}",
            "blocks": _mock_caveat(inv) + parsed["blocks"],
            "suggested_followups": parsed.get("suggested_followups", [])[:3]}


def answer(inv: dict, question: str) -> dict:
    return answer_llm(inv, question)
