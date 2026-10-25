"""Concept interventions for map preview (Addendum 2: Intervention Geometry & Simulation Handoff).

Output 1 of 2. A ``ConceptSet`` holds 2-4 ``ConceptIntervention`` records that Person 2 can render.
They are deliberately separate from the network what-if (``network_assumption.py``):

* Geometry implies no benefit. Concepts have no passability, flood, or ranking fields.
* ``geometry_status`` says how far to trust a location:
    sourced_design_alignment  only with a cited design drawing/map (none extracted in this build)
    sourced_asset_location    location of an EXISTING asset from a cited dataset (road, catch basin)
    schematic                 drawn by us for UI exploration; must be badged
    none                      no spatial claim possible
* ``related_road_ids`` are roads near the concept. They are NOT roads assumed protected.
* Display heights come only from guideline sample values and are labelled as such. Absolute
  elevations are never provided (no surveyed elevations or datum available).
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

from .diagnosis import load_mechanisms
from .library import EVIDENCE_DIR, EvidenceLibrary
from .road_facts import _haversine_m, _vertices

SCHEMA_VERSION = "concept-intervention-v0.1"
CHECKS_PATH = EVIDENCE_DIR / "mechanism_checks.json"
RELATED_ROAD_M = 60.0
MAX_BASIN_POINTS = 10
FT_TO_M = 0.3048

BADGES = {
    "sourced_design_alignment": "Published design alignment (cited)",
    "sourced_asset_location": "Existing asset location (cited). Not a design.",
    "schematic": "SCHEMATIC - illustrative only, not an engineered or published alignment",
    "none": "No location claimed",
}

# candidate key -> (intervention_type, target_asset_type)
TYPE_MAP = {
    "raised_roadway": ("raised_roadway", "road"),
    "vegetated_berm": ("berm", "shoreline"),
    "seawall_extension": ("floodwall", "shoreline"),
    "deployable_barrier": ("deployable_barrier", "opening"),
    "alternate_access": ("alternate_access", "other"),
    "drainage_backflow": ("drainage_upgrade", "outfall"),
    "inspect_clean_inlets": ("drainage_upgrade", "catch_basin"),
    "outfall_adaptation_review": ("drainage_upgrade", "outfall"),
}

UNRESOLVED = {
    "raised_roadway": {
        "physical_survey": "Road, sidewalk and adjacent grade elevations with vertical datum; building setbacks (>=14 ft rule).",
        "ownership_check": "Roadway jurisdiction is a raw Road Inventory code (not decoded); adjacent property ownership unknown.",
        "drainage_assessment": "Pumped drainage behind a raised road; outfall and tide conditions.",
        "permitting": "Coastal/environmental permitting expected to be complex per S12.",
    },
    "berm": {
        "physical_survey": "Shoreline position, open-space width and topography; tie-in to high ground at both ends.",
        "ownership_check": "Owner of the flood-side land strip not established.",
        "drainage_assessment": "Drainage of water trapped landward of the berm.",
        "permitting": "Wetland / resource-area permitting; nature-based design review.",
    },
    "floodwall": {
        "physical_survey": "Existing wall condition and foundation; alignment survey.",
        "ownership_check": "Wall/edge owner not established.",
        "drainage_assessment": "Behind-wall drainage and outfalls.",
        "permitting": "Coastal permitting.",
    },
    "deployable_barrier": {
        "physical_survey": "Which opening admits water; anchoring surface.",
        "ownership_check": "Agency that stores and deploys it not identified.",
        "drainage_assessment": "Seepage and ponding behind the barrier.",
        "permitting": "Emergency access and right-of-way use while deployed.",
    },
    "drainage_upgrade": {
        "physical_survey": "Basin condition inspection; connecting pipe CCTV if needed.",
        "ownership_check": "Mapped owner codes are unverified; confirm before sending a maintenance request.",
        "drainage_assessment": "Outfall location, invert and tide-gate status; pipe sizes (not public).",
        "permitting": "Usually none for cleaning; capital drainage work needs owner approval and street-opening permits.",
    },
    "alternate_access": {
        "physical_survey": "Detour geometry and capacity.",
        "ownership_check": "Owners of the detour roads.",
        "drainage_assessment": "Flood exposure of the detour roads.",
        "permitting": "Traffic management.",
    },
}


def load_checks(path: Path | str = CHECKS_PATH) -> dict[str, dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["checks"]


# ------------------------------------------------------------------ geometry helpers


def _corridor_lines(ctx: dict, road_ids: list[str]) -> list[list[list[float]]]:
    lines = []
    for f in ctx["roads"]["features"]:
        if f["properties"]["road_id"] not in road_ids:
            continue
        g = f["geometry"]
        lines += [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
    return lines


def _offset_east(line: list[list[float]], meters: float) -> list[list[float]]:
    out = []
    for lon, lat, *_ in line:
        dlon = meters / (111_320 * math.cos(math.radians(lat)))
        out.append([round(lon + dlon, 7), round(lat, 7)])
    return out


def _bayside_line(lines: list[list[list[float]]], offset_m: float, bin_m: float = 25.0) -> list[list[float]]:
    """Schematic line following the east (bay) edge of the whole corridor, offset east.

    Bins every corridor vertex by latitude (~bin_m), keeps the easternmost vertex per bin, then shifts
    it east by offset_m. Works for a roughly north-south corridor with the water to the east.
    """
    pts = [p[:2] for line in lines for p in line]
    if len(pts) < 2:
        return []
    step = bin_m / 111_320
    bins: dict[int, list[float]] = {}
    for lon, lat in pts:
        k = int(lat // step)
        if k not in bins or lon > bins[k][0]:
            bins[k] = [lon, lat]
    edge = [bins[k] for k in sorted(bins)]
    # Smooth longitude with a centred moving window so the line doesn't zigzag between carriageways/ramps,
    # then thin to ~every other bin. Purely cosmetic: this is a schematic line.
    half = 3
    smooth = []
    for i, (_, lat) in enumerate(edge):
        win = edge[max(0, i - half): i + half + 1]
        smooth.append([max(p[0] for p in win) * 0.5 + sum(p[0] for p in win) / len(win) * 0.5, lat])
    thinned = smooth[::2] + ([smooth[-1]] if (len(smooth) - 1) % 2 else [])
    return _offset_east(thinned, offset_m)


def _related_roads(geom: dict | None, ctx: dict, road_ids: list[str]) -> list[str]:
    if not geom:
        return list(road_ids)
    if geom["type"] == "MultiPoint":
        pts = [tuple(c[:2]) for c in geom["coordinates"]]
    else:
        pts = _vertices(geom)
    out = []
    for f in ctx["roads"]["features"]:
        rid = f["properties"]["road_id"]
        verts = _vertices(f["geometry"])
        if verts and pts and min(_haversine_m(p, v) for p in pts for v in verts) <= RELATED_ROAD_M:
            out.append(rid)
    return sorted(out)


# ------------------------------------------------------------------ builders


def _cost_precedents(lib: EvidenceLibrary, precedent_ids: list[str]) -> list[dict]:
    out = []
    for pid in precedent_ids:
        p = lib.cost_precedents[pid]
        out.append({
            "precedent_id": pid,
            "source_id": p["source_id"],
            "example_scope": f"{p['title']}; sample length {p['sample_dimensions']['length_ft']:,} ft",
            "price_year": 2018,
            "price_year_note": p["price_basis"],
            "amount_usd": p["total_usd"],
            "limitations": ["Sample site in the 2018 Boston guidelines, not this corridor; not a quote.",
                            f"Excludes: {', '.join(p['excluded'][:4])}."],
        })
    return out


def _mechanism_context(diag: dict | None, mechanisms: list[str]) -> dict:
    if not diag:
        return {"status": {m: "unresolved" for m in mechanisms}, "support": [], "counter": []}
    by = {c["mechanism"]: c for c in diag["possible_causes"]}
    return {
        "status": {m: by[m]["status"] if m in by else "unresolved" for m in mechanisms},
        "support": sorted({e for m in mechanisms if m in by for e in by[m]["supporting_evidence_ids"]}),
        "counter": sorted({e for m in mechanisms if m in by for e in by[m]["counter_evidence_ids"]}),
    }


def _base(inv: dict, key: str, name: str, mechanisms: list[str], checks: dict, diag: dict | None) -> dict:
    itype, target = TYPE_MAP[key]
    ctx = _mechanism_context(diag, mechanisms)
    return {
        "intervention_id": f"ci-{inv['corridor_id']}-{key}",
        "name": name,
        "linked_investigation_id": f"inv:{inv['corridor_id']}:{inv['provenance']['generated_at']}",
        "corridor_id": inv["corridor_id"],
        "graph_version": inv.get("graph_version"),
        "intervention_type": itype,
        "target_asset_type": target,
        "candidate_ref": key,
        "addressed_mechanism_ids": mechanisms,
        "mechanism_status": ctx["status"],
        "supporting_evidence_ids": ctx["support"],
        "conflicting_evidence_ids": ctx["counter"],
        "confirm_with": [c for m in mechanisms for c in checks.get(m, {}).get("confirm_with", [])],
        "refute_if": [c for m in mechanisms for c in checks.get(m, {}).get("refute_if", [])],
        "unresolved_checks": UNRESOLVED[itype],
        "status": "conceptual",
        "implied_benefit": "none",
        "display_caveats": ["Preview only. Does not mark any road as protected and does not change flood layers or travel results."],
    }


def _with_geometry(c: dict, geom: dict | None, status: str, source_ids: list[str], note: str,
                   ctx: dict, road_ids: list[str]) -> dict:
    c.update({
        "geometry": geom,
        "geometry_status": status,
        "geometry_source_ids": source_ids,
        "geometry_note": note,
        "display_badge": BADGES[status],
        "related_road_ids": _related_roads(geom, ctx, road_ids),
        "related_road_ids_note": "Roads near this concept. NOT roads assumed protected.",
    })
    return c


def _raised_road_visuals(inv: dict) -> dict:
    """Display height = guideline sample; display width = MassDOT surface width when it is observed."""
    vp = {"conceptual_height_m": round(4 * FT_TO_M, 2),
          "basis": "Guideline SAMPLE grade change of 4 ft (S11.sec6 p.51), not a design height for this site.",
          "source_id": "S11.sec6"}
    sw = inv["road_facts"]["summary"].get("surface_width", {})
    if sw.get("status") == "observed" and sw.get("range"):
        w_ft = max(sw["range"])
        vp["footprint_width_m"] = round(w_ft * FT_TO_M, 1)
        vp["width_basis"] = (f"MassDOT Road Inventory surface width {w_ft:g} ft (units assumed feet; S10). "
                             "Existing pavement width, not a design footprint.")
        vp["width_source_id"] = "S10"
    return vp


# Short descriptions for Person 2's ConceptIntervention.description (display text).
DESCRIPTIONS = {
    "drainage_upgrade": "Mapped catch basins near the corridor to inspect and, if blocked, clean. Existing asset "
                        "locations, not new works; no flood or ranking change is implied.",
    "raised_roadway": "Existing corridor road segments shown with a guideline-sample 4 ft raise for spatial discussion. "
                      "Not a design; only relevant if coastal overland inflow is confirmed.",
    "berm": "Schematic bay-side berm line drawn by us for spatial discussion. Not surveyed and not a published "
            "alignment; only relevant if coastal overland inflow is confirmed.",
    "floodwall": "Schematic floodwall concept for spatial discussion. Not surveyed or designed.",
    "deployable_barrier": "Deployable barrier concept. The opening it would close is not identified, so no geometry.",
    "alternate_access": "Alternate access concept. Detour geometry not established.",
}


# Preferred human-facing source per type (stable public pages, not staging mirrors or raw services).
SOURCE_PREF = {
    "drainage_upgrade": ["BWSC.cb", "BWSC.maint"],
    "raised_roadway": ["S11"],
    "berm": ["S11"],
    "floodwall": ["S11"],
    "deployable_barrier": ["S11"],
    "alternate_access": ["S12"],
}


def _person2_fields(c: dict, lib: EvidenceLibrary) -> None:
    """Fields Person 2's ConceptIntervention type requires (label, description, source_url)."""
    src = next((s for s in SOURCE_PREF.get(c["intervention_type"], []) + c["evidence_source_ids"]
                if lib.sources.get(s, {}).get("url")), None)
    c["label"] = c["name"]
    c["description"] = DESCRIPTIONS.get(c["intervention_type"], c["geometry_note"])
    c["source_url"] = (lib.sources[src].get("viewer_url") or lib.sources[src]["url"]) if src else ""


def build_concepts(inv: dict, ctx: dict, lib: EvidenceLibrary, drainage: dict | None = None) -> dict:
    mechs = load_mechanisms()
    checks = load_checks()
    diag = inv.get("cause_assessment")
    road_ids = inv["road_ids"]
    methods = {m["method_id"]: m for m in inv["candidate_methods"]}
    actions = {a["action_id"]: a for a in (diag or {}).get("cause_matched_actions", [])}
    concepts: list[dict] = []

    # 1. Drainage: inspect/clean inlets at mapped catch basins (existing asset locations).
    basins = (drainage or {}).get("catch_basins", {}).get("records", [])[:MAX_BASIN_POINTS]
    if "inspect_clean_inlets" in actions:
        a = actions["inspect_clean_inlets"]
        c = _base(inv, "inspect_clean_inlets", a["name"], [a["mechanism"]], checks, diag)
        geom = {"type": "MultiPoint", "coordinates": [[b["lon"], b["lat"]] for b in basins]} if basins else None
        _with_geometry(c, geom, "sourced_asset_location" if basins else "none",
                       ["BWSC.cb"] if basins else [],
                       f"{len(basins)} nearest mapped catch basins (BWSC layer). Locations of existing assets, not new works."
                       if basins else "Catch basin data not loaded.", ctx, road_ids)
        c.update({
            "target_asset_id": None,
            "target_asset_refs": [{"facility_id": b.get("facility_id"), "owner_as_mapped": b.get("owner_code"),
                                   "owner_status": "as_mapped_unverified" if b.get("owner_code") else "unknown"}
                                  for b in basins],
            "visual_parameters": None,
            "provenance": "derived_concept",
            "evidence_distinction": [
                {"kind": "existing_asset", "text": "Catch basin locations and owner codes as mapped by BWSC.", "source_id": "BWSC.cb"},
                {"kind": "published_option", "text": "Catch basin cleaning and CCTV are routine BWSC maintenance programs.", "source_id": "BWSC.maint"},
                {"kind": "illustrative_concept", "text": "Inspecting these specific basins is our suggestion, not an owner work order.", "source_id": None},
            ],
            "evidence_source_ids": sorted(set(a["source_ids"])),
            "suitability": a["gate"] + " " + a["applicable_if"],
            "trade_offs": [a["could_fail"]] + a["downstream_checks"],
            "missing_engineering_inputs": mechs[a["mechanism"]]["unknowns"] + [f"For a quote: {', '.join(a['quote_inputs'])}"],
            "published_cost_precedents": [],
            "cost_status": "cost_estimate_unavailable",
        })
        concepts.append(c)

    # 2. Raised roadway on the corridor road segments (existing road location).
    if "raised_roadway" in methods:
        m = methods["raised_roadway"]
        lines = _corridor_lines(ctx, road_ids)
        c = _base(inv, "raised_roadway", m["name"], m.get("addresses_mechanisms", ["coastal_overland"]), checks, diag)
        _with_geometry(c, {"type": "MultiLineString", "coordinates": lines} if lines else None,
                       "sourced_asset_location" if lines else "none", ["S10"] if lines else [],
                       "Centerlines of the existing corridor road segments (MassDOT Road Inventory). The extent of any raised "
                       "section is not designed.", ctx, road_ids)
        c.update({
            "target_asset_id": None,
            "visual_parameters": _raised_road_visuals(inv),
            "provenance": "derived_concept",
            "evidence_distinction": [
                {"kind": "existing_asset", "text": "Road segment location from the MassDOT Road Inventory.", "source_id": "S10"},
                {"kind": "published_option", "text": "Raised roadway is a sample barrier type in the 2018 Boston guidelines; DCR's 2017 redesign planned to elevate Morrissey Blvd (recorded in S12).", "source_id": "S11.sec6"},
                {"kind": "illustrative_concept", "text": "Raising these specific segments is our concept for preview, not a published or approved design.", "source_id": None},
            ],
            "evidence_source_ids": sorted({cid.split("#")[0] for p in m["sourced_points"] for cid in p["citation_ids"]} | {"S12"}),
            "suitability": m.get("cause_gate", ""),
            "trade_offs": m["failure_modes"],
            "missing_engineering_inputs": m["required_data"],
            "published_cost_precedents": _cost_precedents(lib, m["cost_precedent_ids"]),
            "cost_status": "published_example_available",
        })
        concepts.append(c)

    # 3. Berm on the flood side: no extractable alignment -> schematic.
    if "vegetated_berm" in methods:
        m = methods["vegetated_berm"]
        line = _bayside_line(_corridor_lines(ctx, road_ids), 40.0)
        c = _base(inv, "vegetated_berm", m["name"], m.get("addresses_mechanisms", ["coastal_overland"]), checks, diag)
        _with_geometry(c, {"type": "LineString", "coordinates": line} if len(line) >= 2 else None,
                       "schematic" if len(line) >= 2 else "none", [],
                       "Drawn 40 m east (bay side) of the corridor's eastern edge along its full length, for display "
                       "only. Not a surveyed shoreline, not the Morrissey study's alignment (figures in S12 are images; "
                       "no vector alignment extracted). May cross buildings, paths or water.",
                       ctx, road_ids)
        c.update({
            "target_asset_id": None,
            "visual_parameters": {"conceptual_height_m": round(2 * FT_TO_M, 2),
                                  "basis": "Guideline SAMPLE grade change of ~2 ft (S11.sec4 p.27), not a design height for this site.",
                                  "source_id": "S11.sec4"},
            "provenance": "illustrative",
            "evidence_distinction": [
                {"kind": "published_option", "text": "Vegetated berm is a sample barrier type in the 2018 Boston guidelines; the Morrissey study favours nature-based coastal measures.", "source_id": "S11.sec4"},
                {"kind": "illustrative_concept", "text": "This alignment is drawn by us; no published alignment was extracted.", "source_id": None},
            ],
            "evidence_source_ids": sorted({cid.split("#")[0] for p in m["sourced_points"] for cid in p["citation_ids"]}),
            "suitability": m.get("cause_gate", ""),
            "trade_offs": m["failure_modes"],
            "missing_engineering_inputs": m["required_data"] + ["Published or surveyed alignment"],
            "published_cost_precedents": _cost_precedents(lib, m["cost_precedent_ids"]),
            "cost_status": "published_example_available",
        })
        concepts.append(c)

    # 4. Deployable barrier: the opening is not identified -> no geometry.
    if "deployable_barrier" in methods and len(concepts) < 4:
        m = methods["deployable_barrier"]
        c = _base(inv, "deployable_barrier", m["name"], m.get("addresses_mechanisms", ["coastal_overland"]), checks, diag)
        _with_geometry(c, None, "none", [], "The opening that would need a gate has not been identified.", ctx, road_ids)
        c.update({
            "target_asset_id": None, "visual_parameters": None, "provenance": "derived_concept",
            "evidence_distinction": [
                {"kind": "published_option", "text": "Deployable barriers are covered by Section 7.0 of the 2018 Boston guidelines.", "source_id": "S11.sec7"},
            ],
            "evidence_source_ids": sorted({cid.split("#")[0] for p in m["sourced_points"] for cid in p["citation_ids"]}),
            "suitability": m.get("cause_gate", ""),
            "trade_offs": m["failure_modes"],
            "missing_engineering_inputs": m["required_data"],
            "published_cost_precedents": [],
            "cost_status": "cost_estimate_unavailable",
        })
        concepts.append(c)

    concepts = concepts[:4]
    for c in concepts:
        _person2_fields(c, lib)
    rendered = {c["candidate_ref"] for c in concepts}
    alternatives = [{"candidate_ref": k, "name": (methods.get(k) or actions.get(k))["name"],
                     "intervention_type": TYPE_MAP[k][0], "reason": "Card only; no custom geometry in this build."}
                    for k in ("alternate_access", "outfall_adaptation_review", "drainage_backflow")
                    if k not in rendered and (k in methods or k in actions)]

    def score(c: dict) -> tuple:
        live = any(s in ("possible", "evidence_supported") for s in c["mechanism_status"].values())
        return (c["geometry_status"] != "sourced_asset_location", not live, -len(c["supporting_evidence_ids"]))

    featured = min(concepts, key=score)["intervention_id"] if concepts else None
    for c in concepts:
        cited = set(lib.sources)
        bad = [s for s in c["evidence_source_ids"] + c["geometry_source_ids"] if s not in cited]
        if bad:
            raise ValueError(f"{c['intervention_id']}: unknown source ids {bad}")

    return {
        "schema_version": SCHEMA_VERSION,
        "corridor_id": inv["corridor_id"],
        "graph_version": inv.get("graph_version"),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "featured_intervention_id": featured,
        "featured_reason": "Best-grounded preview: existing-asset geometry and the most supporting evidence for its mechanism.",
        "concepts": concepts,
        "alternatives_not_rendered": alternatives,
        "notes": [n for n in [
            "Concepts carry no passability, flood, or ranking effect. To test access, create a separate NetworkAssumptionForReview.",
            "Statuses: conceptual only. Nothing here is engineer-reviewed, implemented, or verified.",
            "Inputs marked mock in the investigation remain mock." if "mock" in json.dumps(inv["provenance"]["input_data_status"]) else "",
        ] if n],
    }


def to_feature_collection(concept_set: dict) -> dict:
    """Flat GeoJSON for map layers. Properties are display-only; geometry-less concepts are omitted."""
    feats = []
    for c in concept_set["concepts"]:
        if not c.get("geometry"):
            continue
        vp = c.get("visual_parameters") or {}
        feats.append({"type": "Feature", "geometry": c["geometry"], "properties": {
            "intervention_id": c["intervention_id"], "name": c["name"], "intervention_type": c["intervention_type"],
            "geometry_status": c["geometry_status"], "display_badge": c["display_badge"], "provenance": c["provenance"],
            "featured": c["intervention_id"] == concept_set["featured_intervention_id"],
            "conceptual_height_m": vp.get("conceptual_height_m"), "height_basis": vp.get("basis"),
            "implied_benefit": "none"}})
    return {"type": "FeatureCollection", "features": feats,
            "metadata": {"crs": "EPSG:4326", "schema_version": SCHEMA_VERSION, "corridor_id": concept_set["corridor_id"]}}
