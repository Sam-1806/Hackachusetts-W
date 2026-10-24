"""Acceptance checks for the Causal Diagnosis Addendum.  Run: python -m unittest discover -s tests -v"""

from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ENG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENG))

from floodroute_eng.assistant import answer_deterministic  # noqa: E402
from floodroute_eng.brief import render_brief  # noqa: E402
from floodroute_eng.intervention import ProposalError, make_proposal, validate_proposal  # noqa: E402
from floodroute_eng.investigation import build_investigation  # noqa: E402
from floodroute_eng.library import load_library  # noqa: E402

FIXTURE = json.loads((ENG.parent / "fixtures" / "sample_corridor_context.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((ENG / "data" / "road_inventory_morrissey.geojson").read_text(encoding="utf-8"))
DRAINAGE_PATH = ENG / "data" / "drainage_evidence_corr-fx-morrissey-01.json"
DRAINAGE = json.loads(DRAINAGE_PATH.read_text(encoding="utf-8"))
LIB = load_library()
USD = re.compile(r"\$\s?\d")


def build(ctx=None, drainage=DRAINAGE, **kw):
    return build_investigation(copy.deepcopy(ctx or FIXTURE), INVENTORY, LIB, drainage=copy.deepcopy(drainage), **kw)


def polygon_only_context():
    """Non-mock official-looking flood exposure, no local study match, no drainage evidence."""
    ctx = copy.deepcopy(FIXTURE)
    ctx["corridor"]["name"] = "Example Street (test)"
    ctx["scenarios"] = [dict(s, data_status="published_model") for s in ctx["scenarios"]]
    for fe in ctx["flood_exposure"]:
        fe["provenance"]["data_status"] = "published_model"
    return ctx


def statuses(inv):
    return {c["mechanism"]: c["status"] for c in inv["cause_assessment"]["possible_causes"]}


class PolygonAloneTests(unittest.TestCase):
    def setUp(self):
        self.inv = build(polygon_only_context(), drainage=None)

    def test_no_definite_diagnosis_from_polygon(self):
        st = statuses(self.inv)
        self.assertNotIn("evidence_supported", st.values())
        for m in ("tidal_outfall_backwater", "inlet_blockage", "storm_drain_capacity", "surface_grading"):
            self.assertEqual(st[m], "unresolved", m)

    def test_no_exact_cost_for_drainage(self):
        d = self.inv["cause_assessment"]
        for a in d["cause_matched_actions"]:
            if a["mechanism"] != "coastal_overland":
                self.assertEqual(a["cost_status"], "cost_estimate_unavailable")
        res = answer_deterministic(self.inv, "How much would it cost to clean the catch basins?")
        self.assertFalse(any(USD.search(b["text"]) for b in res["blocks"]), res["blocks"])
        self.assertTrue(any("cost_estimate_unavailable" in b["text"] for b in res["blocks"]))

    def test_elevation_not_concluded_from_exposure(self):
        res = answer_deterministic(self.inv, "Does the road need elevation?")
        text = " ".join(b["text"] for b in res["blocks"]).lower()
        self.assertIn("only relevant if coastal_overland is confirmed", text)
        self.assertNotRegex(text, r"road needs (to be )?elevat")


class FixtureDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.inv = build()
        self.d = self.inv["cause_assessment"]

    def test_additive_and_optional(self):
        plain = build(with_diagnosis=False)
        self.assertNotIn("cause_assessment", plain)
        self.assertNotIn("cause_gate", plain["candidate_methods"][0])
        self.assertEqual([m["method_id"] for m in plain["candidate_methods"]],
                         [m["method_id"] for m in self.inv["candidate_methods"]])

    def test_three_mechanisms_distinguished_with_sources(self):
        live = [c for c in self.d["possible_causes"] if c["status"] != "unresolved"
                and c["mechanism"] != "multiple_or_unknown"]
        self.assertGreaterEqual(len({c["mechanism"] for c in live}), 3)
        evs = {e["evidence_id"]: e for e in self.d["evidence"]}
        for c in live:
            self.assertTrue(c["supporting_evidence_ids"])
            self.assertTrue(c["unknowns"])
            for eid in c["supporting_evidence_ids"]:
                self.assertIn(evs[eid]["source_id"], LIB.sources)

    def test_evidence_types_separated(self):
        types = {e["evidence_type"] for e in self.d["evidence"]}
        self.assertTrue({"observed_report", "published_model", "gis_derived"} <= types)
        allowed = {"observed_report", "observed_measurement", "published_model", "gis_derived",
                   "engineering_record", "hypothesis", "unknown"}
        self.assertTrue(types <= allowed)

    def test_no_numeric_likelihoods(self):
        for c in self.d["possible_causes"]:
            self.assertIn(c["status"], ("possible", "evidence_supported", "unresolved"))
            self.assertFalse(any(k in c for k in ("probability", "likelihood", "confidence", "score")))

    def test_assets_and_owners(self):
        assets = self.d["assets_to_investigate"]
        roles = {a["asset_type"]: a["role"] for a in assets}
        self.assertEqual(roles["road"], "impacted_location")
        self.assertEqual(roles["outfall"], "possible_cause_asset")
        for a in assets:
            if a.get("owner"):
                self.assertEqual(a["owner_status"], "as_mapped_unverified")
            else:
                self.assertIn(a["owner_status"], ("unknown",))
        outfall = next(a for a in assets if a["asset_type"] == "outfall")
        self.assertIsNone(outfall["owner"])

    def test_brief_explains_impacted_location(self):
        md = render_brief(self.inv)
        self.assertIn("Why the road may not be the asset to fix", md)
        self.assertIn("Next investigation steps", md)

    def test_2018_costs_never_on_drainage(self):
        for a in self.d["cause_matched_actions"]:
            if a.get("precedent_ids"):
                self.assertEqual(a["mechanism"], "coastal_overland")

    def test_311_reports_never_upgrade_status_alone(self):
        only_reports = copy.deepcopy(DRAINAGE)
        for r in only_reports["reports_311"]["records"]:
            r["closure_reason"] = None
        st = statuses(build(drainage=only_reports))
        self.assertEqual(st["inlet_blockage"], "possible")

    def test_engineering_record_at_corridor_can_support(self):
        dr = copy.deepcopy(DRAINAGE)
        dr["reports_311"]["records"].append({
            "case_enquiry_id": "TEST-1", "open_dt": "2026-01-01", "closed_dt": "2026-01-02", "case_status": "Closed",
            "type": "Catchbasin", "location": "Test location", "queue": "test",
            "closure_reason": "Case Resolved Cleaned and removed debris from cb.",
            "lon": -71.049, "lat": 42.300, "distance_to_corridor_m": 10.0})
        self.assertEqual(statuses(build(drainage=dr))["inlet_blockage"], "evidence_supported")


class ProposalEffectTests(unittest.TestCase):
    def setUp(self):
        self.inv = build()

    def test_fix_the_drain_is_unquantified(self):
        p = make_proposal(self.inv, "inspect_clean_inlets", ["mcfrm-2050-1pct"])
        self.assertEqual(p["effect_claim"], "hydraulic_or_drainage")
        self.assertEqual(p["effect_status"], "unquantified_proposal")
        self.assertFalse(p["rerank_eligible"])
        self.assertEqual(set(p["assumed_passability_by_scenario"].values()), {"unchanged"})

    def test_hydraulic_cannot_open_without_hazard_evidence(self):
        p = make_proposal(self.inv, "inspect_clean_inlets", ["mcfrm-2050-1pct"])
        p["assumed_passability_by_scenario"]["mcfrm-2050-1pct"] = "assumed_open"
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        ok = make_proposal(self.inv, "inspect_clean_inlets", ["mcfrm-2050-1pct"],
                           hazard_update_evidence={"source_ids": ["test"], "description": "before/after model run"})
        self.assertTrue(ok["rerank_eligible"])

    def test_access_only_default_for_road_methods(self):
        p = make_proposal(self.inv, "raised_roadway", ["mcfrm-2050-1pct"])
        self.assertEqual(p["effect_claim"], "access_only")
        self.assertIn("assumed_open", p["assumed_passability_by_scenario"].values())

    def test_drain_fix_question_does_not_mark_safe(self):
        res = answer_deterministic(self.inv, "If we fix the drain will the road be safe?")
        text = " ".join(b["text"] for b in res["blocks"])
        self.assertIn("does not mark this road or nearby properties safe", text)


if __name__ == "__main__":
    unittest.main()
