"""Export a self-contained, hardcode-friendly demo bundle for Person 2.

Writes handoff/person3_demo/:
  demo_data.json     curated panel content (causes, assets, options, costs, chat Q&A, what-if examples, citations)
  map_layers.geojson every map layer in one EPSG:4326 FeatureCollection, distinguished by properties.layer

Values are copied from the generated results (no new analysis). Run from engineering/ after
`investigate` and `concepts`:
    python scripts/export_demo_bundle.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floodroute_eng.assistant import answer_deterministic, mock_parts  # noqa: E402
from floodroute_eng.network_assumption import make_network_assumption  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "engineering"
CID = "corr-fx-morrissey-01"
OUT = ROOT / "handoff" / "person3_demo"

QUESTIONS = [
    "What might be causing the flooding?",
    "What should be inspected, and who owns it?",
    "Does the road need elevation?",
    "How much to clean the catch basins?",
    "If we fix the drain will the road be safe?",
]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


P2_VISUAL_KEYS = ("conceptual_height_m", "absolute_crest_elevation_m", "vertical_datum", "footprint_width_m")


RANK_DIR = ROOT / "engineering" / "data" / "ranking"
P2_ROW_KEYS = ("corridor_id", "road_ids", "label", "priority_rank", "impact_value", "impact_units",
               "affected_journey_ids", "detour_or_disconnection_evidence", "assumptions")
P2_PROV_KEYS = ("origin", "source_id", "source_name", "source_url", "retrieved_at", "period", "limitations")


def _p2_row(r: dict) -> dict:
    row = {k: r[k] for k in P2_ROW_KEYS if k in r}
    row["provenance"] = {k: r["provenance"][k] for k in P2_PROV_KEYS if k in r["provenance"]}
    return row


def person2_ranking(ranking: dict, k: int = 10) -> dict:
    """Person 2's RoadRankingResult (top-k rows) for their ranking table."""
    return {"scenario_set_id": ranking.get("scenario_set_id"), "graph_version": ranking.get("graph_version"),
            "ranking": [_p2_row(r) for r in ranking.get("ranking", [])[:k]]}


def person2_counterfactual(cf: dict, k: int = 10) -> dict:
    """Person 2's CounterfactualResult; keeps our journey_changes / preserved_road_ids as extras."""
    out = {kk: cf[kk] for kk in ("graph_version", "intervention_id", "scenario_set_id", "accessibility_change",
                                 "assumptions", "preserved_road_ids", "journey_changes")}
    out["before_ranking"] = person2_ranking(cf["before_ranking"], k)
    out["after_ranking"] = person2_ranking(cf["after_ranking"], k)
    out["provenance"] = {kk: cf["provenance"][kk] for kk in P2_PROV_KEYS if kk in cf["provenance"]}
    return out


def top_ranked(ctx: dict, k: int = 5) -> list[dict]:
    """Top-k rows of the scenario ranking, for context next to this corridor's own rank."""
    rows = (ctx.get("ranking") or {}).get("ranking", [])[:k]
    return [{"rank": r["priority_rank"], "corridor_id": r["corridor_id"], "label": r["label"],
             "impact_value": r.get("impact_value", r.get("impact_metric")),
             "standalone_loss": r.get("standalone_loss"),
             "evidence": (r.get("detour_or_disconnection_evidence") or [])[:1],
             "candidate_source": r.get("candidate_source")} for r in rows]


def person2_investigation(inv: dict, cs: dict) -> dict:
    """Person 2's simplified InvestigationResult; its UI shows `summary` in the engineering card."""
    d = inv["cause_assessment"]
    cites = {c["citation_id"]: c for c in inv["citations"]}
    live = [c for c in d["possible_causes"] if c["status"] != "unresolved" and c["mechanism"] != "multiple_or_unknown"]
    methods = []
    for c in cs["concepts"]:
        methods.append({"method": c["name"],
                        "evidence": f"{c['suitability']} Geometry: {c['display_badge']}",
                        "source_url": c.get("source_url", "")})
    first_check = d["recommended_next_checks"][0].lower() if d["recommended_next_checks"] else "site checks"
    summary = (f"{d['finding']} {d['impacted_location_note']} "
               f"Start with inspection ({first_check}) before choosing a construction option.")
    return {
        "investigation_id": f"inv:{inv['corridor_id']}",
        "corridor_id": inv["corridor_id"],
        "road_ids": inv["road_ids"],
        "summary": summary,
        "possible_mechanisms": [f"{c['label']} ({c['status'].replace('_', ' ')})" for c in live],
        "candidate_methods": methods,
        "unknown_site_constraints": [m["item"] for m in inv["missing_site_information"]],
        "caveats": [l for l in inv["limitations"] if l][:6],
        # Built from observed/published sources by deterministic rules; ranking inputs flagged separately.
        "provenance": "computed",
        "_citations_used": sorted(cites)[:20],
    }


def person2_concept(c: dict) -> dict:
    """Exactly the fields of Person 2's ConceptIntervention; omit geometry when we claim none."""
    vp = {k: v for k, v in (c.get("visual_parameters") or {}).items() if k in P2_VISUAL_KEYS}
    out = {
        "intervention_id": c["intervention_id"],
        "linked_investigation_id": c.get("linked_investigation_id"),
        "corridor_id": c.get("corridor_id"),
        "graph_version": c["graph_version"],
        "intervention_type": c["intervention_type"],
        "target_asset_type": c["target_asset_type"],
        "geometry_status": c["geometry_status"],
        "geometry_source_ids": c["geometry_source_ids"],
        "related_road_ids": c["related_road_ids"],
        "evidence_source_ids": c["evidence_source_ids"],
        "missing_engineering_inputs": c["missing_engineering_inputs"],
        "status": c["status"],
        "provenance": c["provenance"],
        "label": c["label"],
        "description": c["description"],
        "source_url": c["source_url"],
    }
    if c.get("geometry"):
        out["geometry"] = c["geometry"]
    if vp:
        out["visual_parameters"] = vp
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corridor", default=CID)
    ap.add_argument("--context", default=str(ROOT / "fixtures" / "sample_corridor_context.json"))
    args = ap.parse_args()
    cid = args.corridor
    inv = load(RES / f"investigation_{cid}.json")
    cs = load(RES / f"concepts_{cid}.json")
    ctx = load(Path(args.context))
    dr = load(ROOT / "engineering" / "data" / f"drainage_evidence_{cid}.json")
    parts = mock_parts(inv)
    xs = [c for f in ctx["roads"]["features"] for c in f["geometry"]["coordinates"]]
    center = [round(sum(c[0] for c in xs) / len(xs), 5), round(sum(c[1] for c in xs) / len(xs), 5)]
    d = inv["cause_assessment"]
    evs = {e["evidence_id"]: e for e in d["evidence"]}

    def ev_line(eid: str) -> dict:
        e = evs[eid]
        return {"type": e["evidence_type"], "text": e["summary"], "source_id": e["source_id"],
                "mock": e.get("data_status") == "mock"}

    causes = []
    for c in d["possible_causes"]:
        causes.append({
            "mechanism": c["mechanism"], "label": c["label"], "status": c["status"],
            "status_basis": c["status_basis"],
            "supporting": [ev_line(e) for e in c["supporting_evidence_ids"][:3]],
            "against": [ev_line(e) for e in c["counter_evidence_ids"][:2]],
            "does_not_prove": c["does_not_prove"], "unknowns": c["unknowns"][:3],
        })

    options = []
    for c in cs["concepts"]:
        costs = [f"{p['example_scope']}: ${p['amount_usd']:,} ({p['price_year']} sample, not a quote)"
                 for p in c["published_cost_precedents"]]
        options.append({
            "intervention_id": c["intervention_id"], "name": c["name"], "type": c["intervention_type"],
            "featured": c["intervention_id"] == cs["featured_intervention_id"],
            "geometry_status": c["geometry_status"], "badge": c["display_badge"],
            "has_geometry": c["geometry"] is not None,
            "display_height_m": (c.get("visual_parameters") or {}).get("conceptual_height_m"),
            "height_basis": (c.get("visual_parameters") or {}).get("basis"),
            "addresses": c["mechanism_status"], "gate": c["suitability"],
            "confirm_with": c["confirm_with"], "refute_if": c["refute_if"],
            "unresolved": c["unresolved_checks"],
            "cost": costs or ["Estimate unavailable: no published example for this work type"],
        })

    chat = []
    for q in QUESTIONS:
        a = answer_deterministic(inv, q)
        chat.append({"question": q, "blocks": [{"kind": b["kind"], "text": b["text"], "cites": b["citation_ids"]}
                                               for b in a["blocks"]]})

    roads = [f["properties"]["road_id"] for f in ctx["roads"]["features"]]
    scen = [f["scenario_id"] for f in inv["flood_evidence"]]
    road_ci = f"ci-{cid}-raised_roadway"
    exposed_first = [rid for f in inv["flood_evidence"] for rid in f["roads_exposed"]][:2] or roads[:2]
    whatif = {
        "draft_default": make_network_assumption(cs, road_ci, [], [], roads, scen),
        "explicitly_selected": make_network_assumption(cs, road_ci, scen[:1], exposed_first,
                                                       roads, scen, notes=["Demo what-if"], explicitly_select=True),
        "drainage_selected_rejected_message": "Drainage concepts need hazard_update_evidence (validated before/after "
                                              "flood analysis) before a network counterfactual can be requested",
    }

    n = inv["network_impact"]
    rf = inv["road_facts"]["summary"]
    facts = []
    for k in ("num_lanes", "surface_width", "right_of_way_width", "median_width", "aadt", "aadt_year"):
        e = rf[k]
        v = e.get("range") or e.get("distinct_values")
        facts.append({"label": e["label"], "value": (f"{v[0]:g}" if v[0] == v[-1] else f"{v[0]:g}-{v[-1]:g}")
                      if isinstance(v[0], float) else ", ".join(v), "unit": e.get("unit"), "source_id": "S10"})
    facts += [{"label": e["label"], "value": "not available / requires site survey", "unit": None, "source_id": None}
              for k, e in rf.items() if e["status"] == "not_available"]

    data = {
        "bundle_version": "person3-demo-v1",
        "generated_from": [f"results/engineering/investigation_{cid}.json", f"results/engineering/concepts_{cid}.json",
                           Path(args.context).name],
        "corridor": {"corridor_id": cid, "name": inv["corridor_name"], "road_ids": inv["road_ids"],
                     "graph_version": inv["graph_version"],
                     "inventory_segments": inv["road_facts"]["matched_inventory_segment_ids"],
                     "center_lonlat": center, "suggested_zoom": 16},
        "input_status": inv["provenance"]["input_data_status"],
        "mock_parts": parts,
        "mock_banner": (f"Mock inputs: {', '.join(parts)}. Those numbers are placeholders, not results." if parts else None),
        "why_priority": {"mock": "network ranking" in parts, "rank": n.get("priority_rank"),
                         "rank_of": n.get("candidates_total"),
                         "impact": f"{n['impact_metric']:g} {n['metric_units']}" if n.get("status") == "available" else None,
                         "standalone_loss": n.get("standalone_loss"),
                         "evidence": n.get("evidence_text", []),
                         "assumptions": n.get("assumptions", []),
                         "journeys": n.get("affected_journeys", []),
                         "scenario_set_id": n.get("scenario_set_id"),
                         "top_of_ranking": top_ranked(ctx)},
        "flood_evidence": [{"label": f["label"], "kind": f["kind"], "mock": f["data_status"] == "mock",
                            "data_status": f["data_status"], "exposed": len(f["roads_exposed"]),
                            "not_exposed": len(f["roads_not_exposed"]), "unknown": len(f["roads_unknown"]),
                            "depth": f["depth_m"]["status"], "caveat": f["caveat"]} for f in inv["flood_evidence"]],
        "road_facts": facts,
        "cause_assessment": {"finding": d["finding"], "impacted_location_note": d["impacted_location_note"],
                             "causes": causes, "owner_note": d["owner_note"], "assets_note": d.get("assets_note"),
                             "next_checks": d["recommended_next_checks"], "cannot_claim": d["intervention_caveats"]},
        "local_precedent": [{"status": p["status"], "text": p["text"], "cite": p["citation_ids"][0]}
                            for p in inv["local_precedents"]],
        "options": options,
        "alternatives_cards_only": [a["name"] for a in cs["alternatives_not_rendered"]],
        # Drop-in objects matching Person 2's ConceptIntervention / InvestigationResult
        # (frontend/src/domain/contracts.ts on `simulations`).
        "person2_concepts": [person2_concept(c) for c in cs["concepts"]],
        "person2_investigation": person2_investigation(inv, cs),
        "person2_ranking": person2_ranking(ctx.get("ranking") or {}),
        "person2_counterfactuals": [person2_counterfactual(load(p)) for p in sorted(RANK_DIR.glob(
            f"counterfactual_{(ctx.get('ranking') or {}).get('scenario_set_id')}_*.json"))],
        "person2_recommended_concept_id": next((c["intervention_id"] for c in cs["concepts"]
                                                if c["intervention_type"] == "raised_roadway" and c["geometry"]),
                                               cs["featured_intervention_id"]),
        "published_costs_caveats": inv["published_cost_examples"]["caveats"],
        "chat_script": chat,
        "whatif_examples": whatif,
        "citations": [{"id": c["citation_id"], "title": c["title"], "url": c["url"],
                       "pdf_page": (c.get("page") or {}).get("pdf_page")} for c in inv["citations"]],
        "limitations": inv["limitations"],
    }

    feats = []
    # Flood footprints first so they draw underneath. Exposure per road comes from the same FloodExposureResult.
    exposure = {}
    for fe in ctx.get("flood_exposure", []):
        meta = next((s for s in ctx.get("scenarios", []) if s["scenario_id"] == fe["scenario_id"]), {})
        for r in fe["affected_roads"]:
            exposure.setdefault(r["road_id"], {})[fe["scenario_id"]] = r["exposure"]
        ext = fe.get("extent_geojson")
        if ext and fe["provenance"].get("data_status") != "mock":
            feats.append({"type": "Feature", "geometry": ext["geometry"],
                          "properties": {"layer": "flood_extent", "scenario_id": fe["scenario_id"],
                                         "label": f"{meta.get('label', fe['scenario_id'])} - footprint only, no depth",
                                         "data_status": fe["provenance"]["data_status"],
                                         "source_id": fe["provenance"].get("source_id"),
                                         "style_hint": "translucent blue fill"}})
    fixture_ids = str(ctx.get("graph_version", "")).startswith("fixture")
    for f in ctx["roads"]["features"]:
        rid = f["properties"]["road_id"]
        ex = exposure.get(rid, {})
        feats.append({"type": "Feature", "geometry": f["geometry"],
                      "properties": {"layer": "corridor", "road_id": rid, "exposure_by_scenario": ex,
                                     "label": (f"Corridor road {rid} ({'fixture id' if fixture_ids else ctx.get('graph_version')})"
                                               + (f"; {', '.join(f'{k}: {v}' for k, v in ex.items())}" if ex else "")),
                                     "style_hint": "dark blue if any scenario exposed, else light blue, 6px"}})
    for b in dr["catch_basins"]["records"]:
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [b["lon"], b["lat"]]},
                      "properties": {"layer": "catch_basin", "facility_id": b.get("facility_id"),
                                     "owner_as_mapped": b.get("owner_code"), "distance_m": b["distance_to_corridor_m"],
                                     "label": f"Catch basin {b.get('facility_id')} - owner {b.get('owner_code') or 'unknown'} (mapped, unverified)",
                                     "style_hint": {"DCR": "purple", "PRIV": "gold", "BWSC": "blue"}.get(b.get("owner_code"), "grey")}})
    for r in dr["reports_311"]["records"]:
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                      "properties": {"layer": "report_311", "type": r["type"], "opened": str(r["open_dt"])[:10],
                                     "status": r["case_status"], "location": r["location"],
                                     "closure_note": (r.get("closure_reason") or "")[:240] or None,
                                     "label": f"311 {r['type']} {str(r['open_dt'])[:10]} - report, not a confirmed cause",
                                     "style_hint": "red ring"}})
    for c in cs["concepts"]:
        if c["geometry"]:
            vp = c.get("visual_parameters") or {}
            feats.append({"type": "Feature", "geometry": c["geometry"],
                          "properties": {"layer": "concept", "intervention_id": c["intervention_id"], "name": c["name"],
                                         "geometry_status": c["geometry_status"], "badge": c["display_badge"],
                                         "featured": c["intervention_id"] == cs["featured_intervention_id"],
                                         "display_height_m": vp.get("conceptual_height_m"), "height_basis": vp.get("basis"),
                                         "style_hint": "red dashed + SCHEMATIC label" if c["geometry_status"] == "schematic"
                                         else "green solid"}})
    layers = {"type": "FeatureCollection", "features": feats,
              "metadata": {"crs": "EPSG:4326 [lon, lat]", "retrieved_at": dr["retrieved_at"],
                           "layers": ["flood_extent", "corridor", "catch_basin", "report_311", "concept"],
                           "note": "Concept layer is display only: no flood or ranking change."}}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "demo_data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "map_layers.geojson").write_text(json.dumps(layers, indent=1, ensure_ascii=False), encoding="utf-8")
    counts = {k: sum(1 for f in feats if f["properties"]["layer"] == k) for k in layers["metadata"]["layers"]}
    print(f"wrote {OUT.relative_to(ROOT)}/demo_data.json and map_layers.geojson; features: {counts}")


if __name__ == "__main__":
    main()
