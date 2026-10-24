"""Render an InvestigationResult as a short engineer review brief (Markdown)."""

from __future__ import annotations


def _cite(ids: list[str]) -> str:
    return " " + " ".join(f"[{i}]" for i in ids) if ids else ""


def _cause_section(d: dict) -> list[str]:
    evs = {e["evidence_id"]: e for e in d["evidence"]}

    def ev_line(eid: str, tag: str) -> str:
        e = evs[eid]
        mock = " (mock)" if e.get("data_status") == "mock" else ""
        return f"  - {tag} [{e['evidence_type']}] {e['summary']}{mock} [{e['source_id']}]"

    L = ["## Cause assessment (hypotheses, not a diagnosis)", "", f"**Finding:** {d['finding']}", "",
         f"**Why the road may not be the asset to fix:** {d['impacted_location_note']}", ""]
    for c in d["possible_causes"]:
        L.append(f"- **{c['label']}**: {c['status']}. {c['status_basis']}")
        L += [ev_line(e, "Supports:") for e in c["supporting_evidence_ids"][:3]]
        L += [ev_line(e, "Against:") for e in c["counter_evidence_ids"][:2]]
        if c["mechanism"] != "multiple_or_unknown":
            L.append(f"  - Does not prove it: {c['does_not_prove']}")
            L.append(f"  - Unknown: {'; '.join(c['unknowns'])}")
    L += ["", "### Assets to inspect", f"{d['owner_note']} {d.get('assets_note', '')}", ""]
    L.append("| Type | Role | ID | Owner | Location |")
    L.append("|:--|:--|:--|:--|:--|")
    for a in d["assets_to_investigate"]:
        owner = f"{a['owner']} ({a['owner_status']})" if a.get("owner") else a["owner_status"]
        L.append(f"| {a['asset_type']} | {a['role']} | {a.get('asset_id') or '-'} | {owner} | {a.get('location_ref') or '-'} |")
    L += ["", "### Next investigation steps"]
    L += [f"{i}. {s}" for i, s in enumerate(d["recommended_next_checks"], 1)]
    L += ["", "### Cause-matched options (only after checks)"]
    for a in d["cause_matched_actions"]:
        if a["kind"] == "investigation":
            continue
        cost = a["cost_status"] + (f" (inputs for a quote: {', '.join(a['quote_inputs'])})" if a.get("quote_inputs") else "")
        L.append(f"- **{a['name']}** [{a['kind']}, {a['mechanism']}: {a['mechanism_status']}]. Gate: {a['gate']} "
                 f"Applicable if: {a['applicable_if']} Could fail: {a['could_fail']} Downstream checks: "
                 f"{'; '.join(a['downstream_checks'])}. Cost: {cost}.")
    L += ["", "### Cannot presently be claimed"]
    L += [f"- {c}" for c in d["intervention_caveats"]]
    L += [f"- {c}" for c in d["limitations"]]
    L.append("- Engineer review required.")
    L.append("")
    return L


def _concept_section(cs: dict) -> list[str]:
    L = ["## Concept interventions for preview (not designs)", "",
         "Previews show where a measure might sit. They do not mark roads protected or change flood layers.", ""]
    for c in cs["concepts"]:
        star = " (featured preview)" if c["intervention_id"] == cs["featured_intervention_id"] else ""
        L.append(f"### {c['name']}{star}")
        L.append(f"- Type / target: {c['intervention_type']} / {c['target_asset_type']}; geometry: "
                 f"**{c['geometry_status']}** ({c['display_badge']}). {c['geometry_note']}")
        L.append(f"- Addresses: {', '.join(f'{k} ({v})' for k, v in c['mechanism_status'].items())}")
        L.append(f"- Would confirm: {'; '.join(c['confirm_with'])}")
        L.append(f"- Would refute: {'; '.join(c['refute_if'])}")
        for k, v in c["unresolved_checks"].items():
            L.append(f"- Unresolved {k.replace('_', ' ')}: {v}")
        if c["published_cost_precedents"]:
            L.append("- Cost context (2018 samples, not quotes): " + "; ".join(
                f"{p['example_scope']}: ${p['amount_usd']:,}" for p in c["published_cost_precedents"]))
        else:
            L.append(f"- Cost: {c['cost_status']}")
    if cs["alternatives_not_rendered"]:
        L.append("\nAlternatives (cards only): " + "; ".join(a["name"] for a in cs["alternatives_not_rendered"]))
    L.append("")
    return L


def render_brief(inv: dict, proposal: dict | None = None, concepts: dict | None = None) -> str:
    L: list[str] = []
    L.append(f"# Engineer review brief: {inv['corridor_name'] or inv['corridor_id']}")
    L.append("")
    L.append(f"Corridor `{inv['corridor_id']}` · roads {', '.join(inv['road_ids'])} · graph `{inv['graph_version']}` · "
             f"generated {inv['provenance']['generated_at']}")
    L.append("")
    L.append("> Preliminary investigation aid. Not a design, certification, or cost estimate.")
    for lim in inv["limitations"]:
        L.append(f"> - {lim}")
    L.append("")

    n = inv["network_impact"]
    L.append("## Why this corridor is a priority")
    if n.get("status") == "available":
        L.append(f"Rank {n['priority_rank']}, impact {n['impact_metric']} {n['metric_units']} "
                 f"(data status: {n['data_status']}) [network_impact].")
        for j in n["affected_journeys"]:
            res = "unreachable" if not j.get("reachable", True) else f"{j['flooded_s']} s flooded"
            L.append(f"- {j['label']}: {j['baseline_s']} s normal, {res}")
    else:
        L.append("Network ranking not available.")
    L.append("")

    d = inv.get("cause_assessment")
    if d:
        L.extend(_cause_section(d))
    L.append("## Documented flood exposure")
    for f in inv["flood_evidence"]:
        depth = f["depth_m"]["status"] if f["depth_m"]["status"] != "reported" else f"{f['depth_m']['min']}-{f['depth_m']['max']} m"
        L.append(f"- **{f['label']}** ({f['kind']}, {f['data_status']}): exposed {len(f['roads_exposed'])}, "
                 f"unknown {len(f['roads_unknown'])}; depth: {depth}.{_cite(f['citation_ids'])} {f['caveat']}")
    L.append("")

    L.append("## Road facts (MassDOT Road Inventory)")
    for e in inv["road_facts"]["summary"].values():
        if e["status"] == "not_available":
            val = "not available / requires site survey"
        elif "range" in e:
            lo, hi = e["range"]
            val = (f"{lo:g}" if lo == hi else f"{lo:g}-{hi:g}") + (f" {e['unit']}" if e.get("unit") else "")
        else:
            val = ", ".join(e.get("distinct_values", []))
        L.append(f"- {e['label']}: {val}")
    L.append(f"\nMatched inventory segments: {', '.join(inv['road_facts']['matched_inventory_segment_ids']) or 'none'}"
             f"{_cite(inv['road_facts']['citation_ids'])}")
    L.append("")

    L.append("## Candidate measures to investigate")
    for m in inv["candidate_methods"]:
        L.append(f"### {m['name']}")
        L.append(m["summary"])
        for p in m["sourced_points"]:
            L.append(f"- {p['text']}{_cite(p['citation_ids'])}")
        for h in m["hypotheses"]:
            L.append(f"- *Hypothesis:* {h}")
        L.append(f"- Failure modes: {'; '.join(m['failure_modes'])}")
        L.append(f"- Data needed: {'; '.join(m['required_data'])}")
    if inv.get("other_methods_considered"):
        L.append("\nNot offered: " + "; ".join(f"{o['name']} ({o['reason']})" for o in inv["other_methods_considered"]))
    L.append("")

    if inv["local_precedents"]:
        L.append("## Local precedent")
        for p in inv["local_precedents"]:
            L.append(f"- [{p['status']}] {p['text']}{_cite(p['citation_ids'])}")
        L.append("")

    c = inv["published_cost_examples"]
    L.append("## Published cost context (2018 samples, not transferable)")
    for cav in c["caveats"]:
        L.append(f"- {cav}")
    L.append("")
    L.append("| Sample | Length | Total | Unit | Key exclusions |")
    L.append("|:--|--:|--:|--:|:--|")
    for e in c["examples"]:
        L.append(f"| {e['title']}{_cite(e['citation_ids'])} | {e['sample_dimensions']['length_ft']:,} ft | "
                 f"${e['total_usd']:,} | ${e['unit_cost']['usd']:,}/{e['unit_cost']['per']} | {', '.join(e['excluded'][:3])} |")
    L.append(f"\nSite-specific estimate: {c['site_specific_estimate']['note']}")
    L.append("")

    if concepts:
        L.extend(_concept_section(concepts))

    L.append("## Site investigations needed")
    for m in inv["missing_site_information"]:
        L.append(f"- {m['item']}: {m['status']}")
    L.append("")

    if proposal:
        L.append("## Recorded hypothetical intervention")
        L.append(f"- `{proposal['intervention_id']}`: {proposal['proposed_method']['name']} ({proposal['status']})")
        L.append(f"- Assumed passability: {proposal['assumed_passability_by_scenario']}")
        if proposal.get("effect_claim"):
            L.append(f"- Effect claim: {proposal['effect_claim']} ({proposal.get('effect_status')}); "
                     f"rerank eligible: {proposal.get('rerank_eligible')}")
        L.append(f"- Notes: {proposal['review_notes']}")
        L.append("")

    L.append("## References")
    for ref in inv["citations"]:
        page = ref.get("page") or {}
        pg = f", PDF p.{page['pdf_page']}" if page.get("pdf_page") else ""
        L.append(f"- [{ref['citation_id']}] {ref['title']}{pg}. {ref['url'] or ''}")
    return "\n".join(L) + "\n"
