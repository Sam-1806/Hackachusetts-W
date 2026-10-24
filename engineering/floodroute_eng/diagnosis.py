"""Cause diagnosis (Causal Diagnosis Addendum): flooded road -> competing cause hypotheses
-> evidence and missing checks -> cause-matched actions -> engineer review.

Produces a ``DiagnosticAddendum`` attached to the InvestigationResult as the optional
``cause_assessment`` field. Rules enforced here:

* A road is treated as the *impacted location*; possible cause assets (inlets, pipes,
  outfalls, shoreline) are listed separately.
* Mechanism status is ``possible`` / ``evidence_supported`` / ``unresolved``. No numeric
  likelihoods. A modelled flood polygon or published study alone can never make a
  mechanism ``evidence_supported``; that requires a non-mock engineering record or
  observed measurement located at the corridor.
* Asset owners are reported only as mapped/recorded by a source, flagged unverified.
* Costs: maintenance and drainage actions get ``cost_estimate_unavailable`` plus quote
  inputs. 2018 barrier/raised-road samples are attached only to coastal capital options.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .library import EVIDENCE_DIR, EvidenceLibrary

MECHANISMS_PATH = EVIDENCE_DIR / "mechanisms.json"
AT_CORRIDOR_M = 50.0          # evidence closer than this counts as "at the corridor"
MAX_LISTED_BASINS = 10

DEBRIS_RE = re.compile(r"debris|cleaned|freed|unclog|relieved flood|removed .*from cb|removed snow|clear(ed)? (cb|basin|grate)", re.I)
WORKING_RE = re.compile(r"all are taking water|no flood on arrival|no flood(ing)? (found|observed)|no flood customer", re.I)
REFERRAL_RE = re.compile(r"\b(DCR|Mass ?DOT|MassDOT|state)\b", re.I)


def load_mechanisms(path: Path | str = MECHANISMS_PATH) -> dict[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {m["mechanism"]: m for m in data["mechanisms"]}


def validate_mechanisms(mechs: dict[str, dict], lib: EvidenceLibrary) -> None:
    known = set(lib.sources)
    bad = [f"{m['mechanism']}/{a['action_id']}: {s}" for m in mechs.values() for a in m["actions"]
           for s in a["source_ids"] if s not in known]
    bad += [f"{m['mechanism']}: method {mid}" for m in mechs.values() for mid in m["addressed_by_methods"]
            if mid not in lib.measures]
    if bad:
        raise ValueError("mechanisms.json references unknown ids: " + "; ".join(bad))


class _Evidence:
    def __init__(self, lib: EvidenceLibrary):
        self.lib = lib
        self.items: list[dict] = []

    def add(self, eid: str, source_id: str, evidence_type: str, summary: str, limitations: list[str],
            **extra) -> str:
        src = self.lib.sources.get(source_id, {})
        item = {"evidence_id": eid, "source_id": source_id, "url": extra.pop("url", None) or src.get("url"),
                "evidence_type": evidence_type, "summary": summary, "limitations": limitations}
        item.update({k: v for k, v in extra.items() if v is not None})
        self.items.append(item)
        return eid

    def get(self, eid: str) -> dict:
        return next(i for i in self.items if i["evidence_id"] == eid)


def _flood_items(inv: dict, ev: _Evidence) -> list[str]:
    ids = []
    for f in inv["flood_evidence"]:
        etype = "published_model" if f["kind"] == "future_model" else "observed_measurement" \
            if f["kind"] == "historical_observed" else "unknown"
        lim = [f["caveat"], "Extent overlap does not identify where water enters or which asset fails."]
        if f["data_status"] == "mock":
            lim.insert(0, "MOCK fixture value; cannot support any cause.")
        ids.append(ev.add(f"ev-flood-{f['scenario_id']}", f["citation_ids"][0].split("#")[0] if f["citation_ids"] else "unknown",
                          etype, f"{f['label']}: {len(f['roads_exposed'])} of {len(inv['road_ids'])} corridor roads "
                                 f"exposed; depth {f['depth_m']['status']}.", lim,
                          data_status=f["data_status"], scenario_id=f["scenario_id"],
                          exposed=bool(f["roads_exposed"])))
    return ids


def _precedent_items(inv: dict, ev: _Evidence) -> dict[str, str]:
    """Map S12 local precedents to evidence ids (only those relevant to causes)."""
    relevant = {"morrissey-flood-pathways-present": "coastal", "morrissey-central-section-gap": "coastal",
                "morrissey-stormwater-high-tide": "tidal", "morrissey-multi-jurisdiction": "owner"}
    out = {}
    for p in inv.get("local_precedents", []):
        if p["precedent_id"] in relevant:
            page = p["citation_ids"][0].split("#p")[-1] if "#p" in p["citation_ids"][0] else None
            out[p["precedent_id"]] = ev.add(
                f"ev-{p['precedent_id']}", "S12", "published_model", p["text"],
                ["Corridor-study finding at study-area scale; not a site inspection of this road segment."],
                pdf_page=int(page) if page else None, role=relevant[p["precedent_id"]])
    return out


def _drainage_items(drainage: dict | None, ev: _Evidence) -> dict:
    res = {"report_groups": [], "debris_notes": [], "working_notes": [], "referral_notes": [],
           "basins": [], "basin_summary": None, "reports_total": 0}
    if not drainage:
        return res
    reports = drainage.get("reports_311", {}).get("records", [])
    res["reports_total"] = len(reports)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        groups[r["location"]].append(r)
    for i, (loc, rs) in enumerate(sorted(groups.items(), key=lambda kv: min(r["distance_to_corridor_m"] for r in kv[1]))):
        dates = sorted(str(r["open_dt"])[:10] for r in rs)
        dist = min(r["distance_to_corridor_m"] for r in rs)
        types = Counter(r["type"] for r in rs)
        eid = ev.add(f"ev-311-loc{i + 1:02d}", "BOS311", "observed_report",
                     f"{len(rs)} 311 report(s) at {loc} ({', '.join(f'{t}: {n}' for t, n in types.items())}), "
                     f"{dates[0]} to {dates[-1]}, {dist:.0f} m from corridor.",
                     ["Resident report; an allegation, not a confirmed blockage or cause.",
                      "Case open time is not necessarily the flood time."],
                     observed_at=dates[-1], distance_to_corridor_m=dist, report_count=len(rs),
                     case_ids=[r["case_enquiry_id"] for r in rs])
        res["report_groups"].append(eid)
        for r in rs:
            note = r.get("closure_reason") or ""
            body = note.split("Case Resolved", 1)[-1].split("Case Noted", 1)[-1].strip() if note else ""
            base = dict(observed_at=str(r["closed_dt"] or r["open_dt"])[:10], distance_to_corridor_m=r["distance_to_corridor_m"],
                        case_ids=[r["case_enquiry_id"]])
            lim = ["Free-text 311 closure note, not a formal inspection record.",
                   "Shows a maintenance visit at that location, not that it caused flooding on the corridor."]
            if DEBRIS_RE.search(body):
                res["debris_notes"].append(ev.add(f"ev-311note-{r['case_enquiry_id']}", "BOS311", "engineering_record",
                                                  f"Closure note at {loc}: \"{body[:140]}\"", lim, **base))
            elif WORKING_RE.search(body):
                res["working_notes"].append(ev.add(f"ev-311note-{r['case_enquiry_id']}", "BOS311", "engineering_record",
                                                   f"Closure note at {loc}: \"{body[:140]}\"", lim, **base))
            if REFERRAL_RE.search(note):
                m = REFERRAL_RE.search(note)
                snippet = note[max(0, m.start() - 80): m.end() + 60].strip()
                res["referral_notes"].append(ev.add(f"ev-311ref-{r['case_enquiry_id']}", "BOS311", "engineering_record",
                                                    f"Closure note at {loc} mentions another agency: \"...{snippet}...\"",
                                                    ["Referral text only; does not establish legal ownership."], **base))
    cb = drainage.get("catch_basins", {}).get("records", [])
    if cb:
        owners = Counter(b.get("owner_code") or "unknown" for b in cb)
        res["basin_summary"] = ev.add(
            "ev-cb-mapped", "BWSC.cb", "gis_derived",
            f"{len(cb)} catch basins mapped within {drainage['catch_basins']['buffer_m']:.0f} m of the corridor; "
            f"owner codes as mapped: {', '.join(f'{k} {v}' for k, v in owners.most_common())}.",
            ["Mapped location and owner code only; not condition, cleaning history, or verified ownership."],
            observed_at=drainage.get("retrieved_at"), owner_counts=dict(owners))
        res["basins"] = cb
    return res


def _status(support: list[str], ev: _Evidence, mechanism: str) -> str:
    """Only non-mock engineering records / observed measurements at the corridor can upgrade status."""
    if not support:
        return "unresolved"
    for eid in support:
        it = ev.get(eid)
        if (it["evidence_type"] in ("engineering_record", "observed_measurement")
                and it.get("data_status") != "mock"
                and (it.get("distance_to_corridor_m") is not None and it["distance_to_corridor_m"] <= AT_CORRIDOR_M)):
            return "evidence_supported"
    return "possible"


def build_diagnosis(inv: dict, lib: EvidenceLibrary, drainage: dict | None = None,
                    hotspot_id: str | None = None, mechanisms: dict | None = None) -> dict:
    mechs = mechanisms or load_mechanisms()
    validate_mechanisms(mechs, lib)
    ev = _Evidence(lib)

    flood_ids = _flood_items(inv, ev)
    prec = _precedent_items(inv, ev)
    dr = _drainage_items(drainage, ev)
    disc = ev.add("ev-bwsc-model-scope", "BWSC.disc", "published_model",
                  "BWSC Inundation Model focuses on coastal flooding (overland flow and outfalls unable to discharge at "
                  "high water); it does not characterise intense-rainfall or clogged-catch-basin flooding and includes "
                  "only Commission-owned outfalls.",
                  ["Absence of modelled flooding is not proof of no flooding."])
    adapt = ev.add("ev-bwsc-adaptation", "BWSC.adapt", "published_model",
                   "BWSC compares No Action, Shoreline Protection Only, and Shoreline Protection + Outfall Adaptation "
                   "for a 2070 100-year tropical storm, separating barrier effects from outfall/tide-gate effects.",
                   ["Regional scenario set; non-Commission outfalls and MassDOT pump stations excluded; "
                    "no corridor-specific benefit is claimed."])

    exposed_flood = [i for i in flood_ids if ev.get(i).get("exposed")]
    hyp_support: dict[str, tuple[list[str], list[str]]] = {
        "coastal_overland": (exposed_flood + [prec[k] for k in ("morrissey-flood-pathways-present",
                                                                 "morrissey-central-section-gap") if k in prec], []),
        # Regional model context (BWSC adaptation scenarios) is not support for a specific corridor.
        "tidal_outfall_backwater": ([prec[k] for k in ("morrissey-stormwater-high-tide",) if k in prec], []),
        "inlet_blockage": (dr["report_groups"][:5] + dr["debris_notes"], dr["working_notes"]),
        "storm_drain_capacity": ([], []),
        "surface_grading": ([], []),
    }

    causes = []
    for mid in ("coastal_overland", "tidal_outfall_backwater", "inlet_blockage", "storm_drain_capacity", "surface_grading"):
        m = mechs[mid]
        support, counter = hyp_support[mid]
        unknowns = list(m["unknowns"])
        if mid in ("inlet_blockage", "storm_drain_capacity"):
            unknowns.append("Not represented in the BWSC Inundation Model (see ev-bwsc-model-scope).")
            if not drainage:
                unknowns.append("Catch basin and 311 evidence not loaded (drainage evidence file missing).")
        st = _status(support, ev, mid)
        mock_only = support and all(ev.get(s).get("data_status") == "mock" for s in support)
        causes.append({
            "mechanism": mid, "label": m["label"], "description": m["description"],
            "supporting_evidence_ids": support, "counter_evidence_ids": counter,
            "unknowns": unknowns, "status": st, "does_not_prove": m["does_not_prove"],
            "status_basis": ("Supporting evidence is mock only." if mock_only else
                             "No discriminating evidence yet." if st == "unresolved" else
                             "Site record or measurement at the corridor." if st == "evidence_supported" else
                             "Evidence is consistent with this cause but does not establish it."),
            "context_evidence_ids": ([disc] if mid in ("inlet_blockage", "storm_drain_capacity") else
                                     [adapt, disc] if mid in ("tidal_outfall_backwater", "coastal_overland") else []),
        })
    n_possible = sum(c["status"] != "unresolved" for c in causes)
    causes.append({
        "mechanism": "multiple_or_unknown", "label": mechs["multiple_or_unknown"]["label"],
        "description": mechs["multiple_or_unknown"]["description"],
        "supporting_evidence_ids": [], "counter_evidence_ids": [],
        "unknowns": mechs["multiple_or_unknown"]["unknowns"],
        "status": "possible" if n_possible >= 2 else "unresolved",
        "does_not_prove": mechs["multiple_or_unknown"]["does_not_prove"],
        "status_basis": f"{n_possible} mechanisms have some supporting evidence; the evidence does not discriminate between them.",
        "context_evidence_ids": [],
    })

    # Assets: the road is the impacted location; other assets are where causes might sit.
    assets = [{"asset_type": "road", "asset_id": rid, "role": "impacted_location", "owner": None,
               "owner_status": "unknown", "location_ref": inv["corridor_name"],
               "evidence_ids": flood_ids} for rid in inv["road_ids"]]
    for b in dr["basins"][:MAX_LISTED_BASINS]:
        assets.append({"asset_type": "catch_basin", "asset_id": b.get("facility_id"), "role": "possible_cause_asset",
                       "owner": b.get("owner_code"), "owner_status": "as_mapped_unverified" if b.get("owner_code") else "unknown",
                       "location_ref": f"{b['lat']:.6f},{b['lon']:.6f} ({b['distance_to_corridor_m']:.0f} m from corridor)",
                       "evidence_ids": [dr["basin_summary"]]})

    assets.append({"asset_type": "pipe", "asset_id": None, "role": "possible_cause_asset", "owner": None,
                   "owner_status": "unknown", "location_ref": "Pipes connecting corridor inlets to their outfall (not public)",
                   "evidence_ids": ["ev-bwsc-model-scope"]})
    assets.append({"asset_type": "outfall", "asset_id": None, "role": "possible_cause_asset", "owner": None,
                   "owner_status": "unknown", "location_ref": "Outfall(s) serving the corridor inlets: not identified",
                   "evidence_ids": [disc] + ([prec["morrissey-stormwater-high-tide"]] if "morrissey-stormwater-high-tide" in prec else [])})
    if "morrissey-central-section-gap" in prec:
        assets.append({"asset_type": "shoreline", "asset_id": None, "role": "possible_cause_asset", "owner": None,
                       "owner_status": "unknown", "location_ref": "Central section shoreline pathway, Bianculli Blvd to Freeport St (per S12)",
                       "evidence_ids": [prec["morrissey-central-section-gap"]]})

    # Cause-matched actions; investigations before maintenance before capital.
    active = {c["mechanism"] for c in causes if c["status"] != "unresolved"} | {"multiple_or_unknown"}
    actions = []
    for c in causes:
        for a in mechs[c["mechanism"]]["actions"]:
            if c["mechanism"] not in active and a["kind"] == "capital":
                continue
            actions.append({**a, "mechanism": c["mechanism"], "mechanism_status": c["status"],
                            "gate": ("Only after checks confirm this mechanism." if a["kind"] == "capital" else
                                     "If inspection confirms blockage." if a["kind"] == "maintenance" else
                                     "First-line investigation.")})
    # Checks and maintenance first (keeping each mechanism's own sequence, e.g. clean before CCTV), capital last.
    idx = {id(a): i for i, a in enumerate(actions)}
    actions.sort(key=lambda a: (a["kind"] == "capital", a["mechanism_status"] == "unresolved", idx[id(a)]))
    next_checks = [a["name"] for a in actions if a["kind"] != "capital"]

    owner_counts = (ev.get(dr["basin_summary"])["owner_counts"] if dr["basin_summary"] else {})
    owner_note = ("Owner codes for nearby mapped catch basins: " + ", ".join(f"{k} {v}" for k, v in owner_counts.items())
                  + ". Send maintenance requests to the confirmed owner; do not assume BWSC." if owner_counts else
                  "Asset owners not established; confirm before naming an agency.")

    finding = ("Flooding on this corridor is documented or modelled, and drainage complaints are reported nearby. "
               "The cause is not established. " if dr["reports_total"] else
               "Flooding on this corridor is documented or modelled. The cause is not established. ") + \
              "Possible explanations: " + ", ".join(c["label"].lower() for c in causes
                                                    if c["status"] != "unresolved" and c["mechanism"] != "multiple_or_unknown") + "."

    return {
        "schema_version": "diagnosis-v0.1",
        "road_ids": inv["road_ids"],
        "hotspot_id": hotspot_id,
        "scenario_ids": [f["scenario_id"] for f in inv["flood_evidence"]],
        "finding": finding,
        "impacted_location_note": ("The road is where flooding is seen. The asset that needs work may be an inlet, "
                                   "pipe, outfall, or shoreline opening elsewhere in the system."),
        "evidence": ev.items,
        "possible_causes": causes,
        "assets_to_investigate": assets,
        "assets_note": (f"{min(len(dr['basins']), MAX_LISTED_BASINS)} nearest of {len(dr['basins'])} mapped catch basins listed."
                        if dr["basins"] else "No catch basin data loaded."),
        "owner_note": owner_note,
        "cause_matched_actions": actions,
        "recommended_next_checks": next_checks,
        "intervention_caveats": [
            "Do not choose road elevation from flood exposure or network priority alone; it addresses coastal overland inflow only.",
            "Drainage or maintenance actions have no published cost example here: cost_estimate_unavailable until quoted.",
            "2018 barrier/raised-road sample costs apply only to coastal capital options, never to catch-basin cleaning or drainage retrofits.",
            "A drainage fix does not change road exposure, property-loss projections, or network ranking without validated before/after flood analysis.",
            "No avoided property damage is claimed.",
        ],
        "limitations": [
            "Hypotheses to investigate, not a hydraulic diagnosis.",
            "Statuses are evidence categories, not probabilities.",
            "311 data are resident reports with closure notes; catch basin data are mapped attributes, not condition.",
            "Pipe network, outfall locations, inverts and maintenance logs were not publicly available as data.",
        ],
        "engineer_review_required": True,
        "data_access": {
            "catch_basins": "obtained (BWSC FeatureServer)" if dr["basins"] else "not_available",
            "reports_311": "obtained (data.boston.gov CKAN)" if drainage else "not_available",
            "pipes_outfalls": "not_available", "maintenance_logs": "not_available",
            "bwsc_model_layers": "not_available (viewer only)",
            "retrieved_at": (drainage or {}).get("retrieved_at"),
        },
    }


def method_mechanism_index(mechs: dict | None = None) -> dict[str, list[str]]:
    """method_id -> mechanisms it could address (for annotating candidate methods)."""
    out: dict[str, list[str]] = defaultdict(list)
    for m in (mechs or load_mechanisms()).values():
        for mid in m["addressed_by_methods"]:
            out[mid].append(m["mechanism"])
    return dict(out)
