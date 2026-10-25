"""Assemble an ``InvestigationResult`` for one corridor.

Inputs are normalized records only (contract shapes), never NetworkX graphs or
raw rasters:

* corridor context: ``{corridor, roads, scenarios, flood_exposure, ranking}``
  (the fixture shape; produced from Person 1/2 results in integration)
* MassDOT Road Inventory snapshot (S10) for road facts
* the cited evidence library

Candidate methods are *screened*, not recommended: each screening check reports
``supports`` / ``against`` / ``unknown`` with the fact or source that drove it.
"""

from __future__ import annotations

import datetime
from typing import Any

from .library import EvidenceLibrary
from .road_facts import spatial_join, summarize_corridor_facts

SCHEMA_VERSION = "investigation-v0.1"
NOT_AVAILABLE = "not available / requires site survey"

# Order in which methods are offered; first MAX_CANDIDATES that pass go into candidate_methods.
METHOD_ORDER = ["raised_roadway", "vegetated_berm", "alternate_access",
                "deployable_barrier", "drainage_backflow", "seawall_extension"]
MAX_CANDIDATES = 4

REQUIREMENT_LABELS = {
    "adjacent_setbacks": "Building setbacks from back of sidewalk",
    "road_surface_elevation": "Surveyed road elevation with vertical datum",
    "drainage_capacity": "Drainage capacity, outfalls, tide gates",
    "subsurface_utilities": "Underground utilities",
    "geotechnical": "Geotechnical / groundwater conditions",
    "open_space_flood_side": "Open space between road and water for a berm footprint",
    "existing_seawall": "Existing seawall at the flood edge",
    "forecast_lead_time": "Forecast lead time for deployment",
    "operations_owner": "Agency that would store and deploy the barrier",
    "detour_flood_exposure": "Flood exposure of the detour route",
}


class _Citations:
    """Collects citations used in the result, deduplicated by citation_id."""

    def __init__(self, lib: EvidenceLibrary):
        self.lib = lib
        self.items: dict[str, dict] = {}

    def add(self, source_id: str, pdf_page: int | None = None,
            printed_page: int | None = None, url_override: str | None = None) -> str:
        c = self.lib.citation(source_id, pdf_page, printed_page, url_override)
        self.items.setdefault(c["citation_id"], c)
        return c["citation_id"]


def _corridor_matches(claim_or_precedent: dict, corridor_name: str) -> bool:
    key = claim_or_precedent.get("applies_to_corridor_match") or claim_or_precedent.get("corridor_match")
    return key is None or key.upper() in corridor_name.upper()


# ------------------------------------------------------------------ sections


def _flood_evidence(ctx: dict, road_ids: list[str], cites: _Citations) -> list[dict]:
    scen_meta = {s["scenario_id"]: s for s in ctx.get("scenarios", [])}
    out = []
    for fe in ctx.get("flood_exposure", []):
        sid = fe["scenario_id"]
        meta = scen_meta.get(sid, {})
        rows = [r for r in fe.get("affected_roads", []) if r["road_id"] in road_ids]
        listed = {r["road_id"] for r in rows}
        depths = [r["depth_m"] for r in rows if r.get("depth_m") is not None]
        source_id = meta.get("source_id") or (rows[0]["source_id"] if rows else None)
        citation_id = cites.add(source_id) if source_id in cites.lib.sources else None
        data_status = meta.get("data_status") or fe.get("provenance", {}).get("data_status", "unknown")
        kind = meta.get("kind", "unknown")
        out.append({
            "scenario_id": sid,
            "label": meta.get("label", sid),
            "kind": kind,
            "data_status": data_status,
            "roads_exposed": sorted(r["road_id"] for r in rows if r["exposure"] == "exposed"),
            "roads_not_exposed": sorted(r["road_id"] for r in rows if r["exposure"] == "not_exposed"),
            "roads_unknown": sorted([r["road_id"] for r in rows if r["exposure"] == "unknown"]
                                    + [rid for rid in road_ids if rid not in listed]),
            "passability": {p: sum(1 for r in rows if r["passability"] == p)
                            for p in ("potentially_closed", "unknown", "assumed_open")},
            "depth_m": ({"min": min(depths), "max": max(depths), "status": "reported"} if depths
                        else {"min": None, "max": None, "status": NOT_AVAILABLE}),
            "basis": sorted({r["basis"] for r in rows}),
            "citation_ids": [citation_id] if citation_id else [],
            "caveat": ("Projected annual-exceedance scenario; not a prediction of a dated storm."
                       if kind == "future_model" else
                       "Observed footprint; does not show street-level depth, velocity, or timing."
                       if kind == "historical_observed" else
                       "Scenario type not specified.")
                      + " Extent overlap does not prove the road was impassable.",
        })
    return out


def _network_impact(ctx: dict, corridor_id: str) -> dict:
    entry = next((r for r in ctx.get("ranking", {}).get("ranking", [])
                  if r["corridor_id"] == corridor_id), None)
    if entry is None:
        return {"status": "not_available", "note": "No ranking record for this corridor."}
    journeys = entry.get("affected_journeys", [])
    ev = entry.get("detour_or_disconnection_evidence")
    return {
        "status": "available",
        "data_status": entry.get("provenance", {}).get("data_status", "unknown"),
        "priority_rank": entry.get("priority_rank"),
        "candidates_total": len(ctx.get("ranking", {}).get("ranking", [])),
        "evidence_text": ev if isinstance(ev, list) else [],
        "standalone_loss": entry.get("standalone_loss"),
        "impact_metric": entry.get("impact_metric"),
        "metric_units": entry.get("metric_units"),
        "journeys_total": len(journeys),
        "journeys_unreachable": [j["journey_id"] for j in journeys if not j.get("reachable", True)],
        "affected_journeys": journeys,
        "detour_or_disconnect_evidence": entry.get("detour_or_disconnect_evidence", {}),
        "assumptions": entry.get("assumptions", []),
        "scenario_set_id": ctx.get("ranking", {}).get("scenario_set_id"),
    }


def _known_facts(road_summary: dict, network: dict, site_facts: dict) -> dict[str, Any]:
    """Facts usable for screening. ``None`` means unknown."""
    facts: dict[str, Any] = {k: None for k in REQUIREMENT_LABELS}
    for k in REQUIREMENT_LABELS:
        entry = road_summary.get(k)
        if entry and entry.get("status") == "observed":
            facts[k] = entry.get("value")
    detour = network.get("detour_or_disconnect_evidence", {})
    if detour.get("detour_flood_exposure") not in (None, "unknown"):
        facts["detour_flood_exposure"] = detour["detour_flood_exposure"]
    for k, v in (site_facts or {}).items():  # planner/engineer-supplied, already provenance-tagged
        facts[k] = v.get("value") if isinstance(v, dict) else v
    return facts


def _screen_method(m: dict, facts: dict, corridor_name: str, network: dict, cites: _Citations) -> dict:
    checks = []
    excluded_reason = None
    for req in m["screening"]["requires"]:
        val = facts.get(req)
        checks.append({"check": REQUIREMENT_LABELS.get(req, req),
                       "fact": req,
                       "status": "unknown" if val is None else "supports",
                       "value": val,
                       "note": NOT_AVAILABLE if val is None else "Provided"})
    for rule in m["screening"]["exclude_if"]:
        val = facts.get(rule["fact"])
        if val is not None and rule["condition"] == "lt" and float(val) < rule["value_ft"]:
            excluded_reason = rule["reason"]
            for c in checks:
                if c["fact"] == rule["fact"]:
                    c["status"], c["note"] = "against", rule["reason"]

    sourced, hypotheses = [], []
    for claim in m["claims"]:
        if not _corridor_matches(claim, corridor_name):
            continue
        if claim["basis"] == "sourced":
            cid = cites.add(claim["source_id"], claim.get("pdf_page"), claim.get("printed_page"),
                            claim.get("source_url_override"))
            sourced.append({"text": claim["text"], "citation_ids": [cid]})
        else:
            hypotheses.append(claim["text"])

    relevance = "screened_out" if excluded_reason else "candidate"
    if m["method_id"] == "alternate_access":
        detour = network.get("detour_or_disconnect_evidence", {})
        if not detour.get("detour_available_for"):
            relevance, excluded_reason = "screened_out", "Network results show no detour for affected journeys."
        else:
            sourced.append({"text": "Network results report a detour for journeys "
                                    + ", ".join(detour["detour_available_for"])
                                    + (f"; disconnected: {', '.join(detour.get('disconnected', []))}"
                                       if detour.get("disconnected") else "") + ".",
                            "citation_ids": [cites.add("network_impact")]})
    if m["method_id"] == "seawall_extension" and not facts.get("existing_seawall"):
        relevance = "screened_out"
        excluded_reason = excluded_reason or "No evidence of an existing seawall at this corridor's flood edge."

    return {
        "method_id": m["method_id"],
        "name": m["name"],
        "category": m["category"],
        "summary": m["summary"],
        "relevance": relevance,
        "screened_out_reason": excluded_reason,
        "screening": checks,
        "sourced_points": sourced,
        "hypotheses": hypotheses,
        "failure_modes": m["failure_modes"],
        "required_data": m["required_data"],
        "cost_precedent_ids": m["cost_precedent_ids"],
        "status": "to_investigate",
    }


def _cost_examples(lib: EvidenceLibrary, method_ids: list[str], cites: _Citations) -> dict:
    examples = []
    for mid in method_ids:
        for pid in lib.measures[mid]["cost_precedent_ids"]:
            p = lib.cost_precedents[pid]
            cid = cites.add(p["source_id"], p.get("pdf_page"), p.get("printed_page"))
            examples.append({**p, "citation_ids": [cid], "transferable": False,
                             "label": "Published 2018 sample cost (not an estimate for this corridor)"})
    no_precedent = [mid for mid in method_ids if not lib.measures[mid]["cost_precedent_ids"]]
    return {
        "examples": examples,
        "methods_without_cost_precedent": no_precedent,
        "caveats": lib.cost_caveats,
        "estimating_method_guidance": lib.estimating_guidance,
        "site_specific_estimate": {"value": None, "status": "not_estimated",
                                   "note": "Site cost estimation is a separate engineering task."},
    }


def _missing_info(road_summary: dict, flood: list[dict], methods: list[dict]) -> list[dict]:
    items: dict[str, dict] = {}
    for key, entry in road_summary.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        if entry.get("status") == "not_available":
            items[key] = {"item": entry["label"], "status": NOT_AVAILABLE,
                          "why_needed": "Road fact not present in the Road Inventory for this corridor."}
        elif entry.get("segments_missing"):
            items[key] = {"item": entry["label"],
                          "status": f"partially available ({entry['segments_missing']} of "
                                    f"{entry['segments_total']} segments missing)",
                          "why_needed": "Inventory field blank on some matched segments."}
    if any(f["depth_m"]["status"] != "reported" for f in flood):
        items["flood_depth_at_road"] = {"item": "Flood depth at the road surface (with datum)",
                                        "status": NOT_AVAILABLE,
                                        "why_needed": "Passability depends on depth vs road elevation, not extent overlap."}
    for m in methods:
        for c in m["screening"]:
            if c["status"] == "unknown" and c["fact"] not in items:
                items[c["fact"]] = {"item": c["check"], "status": NOT_AVAILABLE,
                                    "why_needed": f"Needed to screen: {m['name']}."}
    return list(items.values())


# ------------------------------------------------------------------ entry point


def build_investigation(ctx: dict, inventory_fc: dict, lib: EvidenceLibrary,
                        corridor_id: str | None = None, site_facts: dict | None = None,
                        max_distance_m: float = 25.0, drainage: dict | None = None,
                        with_diagnosis: bool = True) -> dict:
    """Build the InvestigationResult. ``cause_assessment`` (Causal Diagnosis Addendum) is an
    optional additive field; pass ``with_diagnosis=False`` to get the v0.1 shape only."""
    inv = _build_core(ctx, inventory_fc, lib, corridor_id, site_facts, max_distance_m)
    if not with_diagnosis:
        return inv
    from .diagnosis import build_diagnosis, method_mechanism_index  # local import keeps core independent

    diag = build_diagnosis(inv, lib, drainage=drainage, hotspot_id=ctx.get("hotspot_id"))
    inv["cause_assessment"] = diag
    status = {c["mechanism"]: c["status"] for c in diag["possible_causes"]}
    index = method_mechanism_index()
    for m in inv["candidate_methods"] + [o["details"] for o in inv["other_methods_considered"] if o.get("details")]:
        mechs = index.get(m["method_id"], [])
        m["addresses_mechanisms"] = mechs
        live = [k for k in mechs if status.get(k) in ("possible", "evidence_supported")]
        confirmed = [k for k in mechs if status.get(k) == "evidence_supported"]
        m["cause_gate"] = (
            "Network/access measure; does not address a flooding cause." if m["category"] == "network_measure" else
            f"Matches an evidence-supported cause ({', '.join(confirmed)})." if confirmed else
            f"Only relevant if {' or '.join(mechs)} is confirmed; currently {', '.join(status.get(k, 'unresolved') for k in mechs)}."
            if mechs else "No mechanism mapping.")
        m["cause_relevance"] = ("access_only" if m["category"] == "network_measure" else
                                "cause_supported" if confirmed else "cause_possible" if live else "cause_unresolved")
    inv["limitations"].append("Candidate construction methods are gated on the cause assessment; the flooded road may be "
                              "an impacted location rather than the asset that needs work.")
    seen = {m["item"] for m in inv["missing_site_information"]}
    for item, why in [("Outfall(s) serving the corridor and their owner", "Needed to test tide-constrained drainage."),
                      ("Storm drain pipe sizes and connectivity", "Needed to test drainage capacity; not public."),
                      ("Catch basin condition and cleaning history from the owner", "Needed to test inlet blockage.")]:
        if item not in seen:
            inv["missing_site_information"].append({"item": item, "status": NOT_AVAILABLE, "why_needed": why})
    # Register diagnosis sources as citations so UI links resolve.
    cited = {c["citation_id"] for c in inv["citations"]}
    for e in diag["evidence"]:
        sid = e["source_id"]
        if sid in lib.sources and sid not in cited:
            inv["citations"].append(lib.citation(sid))
            cited.add(sid)
    for a in diag["cause_matched_actions"]:
        for sid in a["source_ids"]:
            if sid not in cited:
                inv["citations"].append(lib.citation(sid))
                cited.add(sid)
    inv["citations"].sort(key=lambda c: c["citation_id"])
    return inv


def _build_core(ctx: dict, inventory_fc: dict, lib: EvidenceLibrary, corridor_id: str | None,
                site_facts: dict | None, max_distance_m: float) -> dict:
    corridor = ctx["corridor"]
    corridor_id = corridor_id or corridor["corridor_id"]
    if corridor_id != corridor["corridor_id"]:
        raise ValueError(f"Context is for {corridor['corridor_id']}, not {corridor_id}")
    road_ids = list(corridor["road_ids"])
    corridor_name = corridor.get("name", "")
    cites = _Citations(lib)

    roads = [f for f in ctx["roads"]["features"] if f["properties"]["road_id"] in road_ids]
    join = spatial_join(roads, inventory_fc["features"], max_distance_m=max_distance_m)
    all_records = [rec for j in join.values() for rec in j["records"]]
    summary = summarize_corridor_facts(all_records)
    inv_cite = cites.add("S10")
    road_facts = {
        "summary": {k: v for k, v in summary.items() if not k.startswith("_")},
        "matched_inventory_segment_ids": summary["_segment_ids"],
        "per_road_match": {rid: j["match"] for rid, j in join.items()},
        "unmatched_road_ids": [rid for rid, j in join.items() if not j["records"]],
        "citation_ids": [inv_cite],
        "snapshot": {k: inventory_fc.get("metadata", {}).get(k)
                     for k in ("source_url", "query_where", "retrieved_at", "record_count")},
    }

    flood = _flood_evidence(ctx, road_ids, cites)
    network = _network_impact(ctx, corridor_id)
    facts = _known_facts(summary, network, site_facts or {})

    screened = [_screen_method(lib.measures[mid], facts, corridor_name, network, cites)
                for mid in METHOD_ORDER if mid in lib.measures]
    passing = [m for m in screened if m["relevance"] == "candidate"]
    candidates = passing[:MAX_CANDIDATES]
    others = []
    for m in screened:
        if m in candidates:
            continue
        entry = {"method_id": m["method_id"], "name": m["name"], "relevance": m["relevance"],
                 "reason": m["screened_out_reason"] or f"Passed screening but outside the top {MAX_CANDIDATES} offered."}
        if m["relevance"] == "candidate":
            entry["details"] = m  # still answerable on request
        others.append(entry)

    local = []
    for p in lib.local_precedents:
        if _corridor_matches(p, corridor_name):
            cid = cites.add(p["source_id"], p.get("pdf_page"))
            local.append({"precedent_id": p["precedent_id"], "status": p["status"],
                          "text": p["text"], "citation_ids": [cid]})

    costs = _cost_examples(lib, [m["method_id"] for m in candidates], cites)

    input_status = {
        "road_facts": "observed",
        "flood_exposure": sorted({f["data_status"] for f in flood}) or ["not_available"],
        "network_impact": network.get("data_status", "not_available"),
        "road_ids": "mock" if str(ctx.get("graph_version", "")).startswith("fixture") else "canonical",
    }
    limitations = [
        "Candidate methods are options to investigate, not recommendations or designs. A licensed engineer must review.",
        "No hydraulic modelling was performed; nothing here shows that a measure would keep the road passable.",
        "Published costs are 2018 sample figures for different sites and are not estimates for this corridor.",
        "Road Inventory code values are passed through undecoded; widths assumed to be in feet.",
    ]
    mock_inputs = [label for key, label in (("road_ids", "corridor road IDs"), ("flood_exposure", "flood exposure"),
                                            ("network_impact", "network ranking")) if "mock" in str(input_status[key])]
    if mock_inputs:
        limitations.insert(0, f"MOCK inputs: {', '.join(mock_inputs)} (see provenance.input_data_status). "
                              "Do not present those numbers as results.")
    if ctx.get("fixture_notice"):
        limitations.insert(0, ctx["fixture_notice"])

    return {
        "schema_version": SCHEMA_VERSION,
        "corridor_id": corridor_id,
        "corridor_name": corridor_name,
        "road_ids": road_ids,
        "graph_version": ctx.get("graph_version"),
        "road_facts": road_facts,
        "flood_evidence": flood,
        "network_impact": network,
        "candidate_methods": candidates,
        "other_methods_considered": others,
        "published_cost_examples": costs,
        "local_precedents": local,
        "missing_site_information": _missing_info(summary, flood, candidates),
        "citations": sorted(cites.items.values(), key=lambda c: c["citation_id"]),
        "limitations": limitations,
        "provenance": {
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "evidence_library_version": lib.version,
            "input_data_status": input_status,
            "generator": "engineering/floodroute_eng/investigation.py",
        },
    }
