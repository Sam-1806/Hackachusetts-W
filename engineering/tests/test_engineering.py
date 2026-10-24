"""Run from engineering/:  python -m unittest discover -s tests -v"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ENG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENG))

from floodroute_eng.assistant import answer_deterministic, classify  # noqa: E402
from floodroute_eng.brief import render_brief  # noqa: E402
from floodroute_eng.intervention import ProposalError, make_proposal, validate_proposal  # noqa: E402
from floodroute_eng.investigation import NOT_AVAILABLE, build_investigation  # noqa: E402
from floodroute_eng.library import EvidenceLibrary, load_library, validate_library  # noqa: E402
from floodroute_eng.road_facts import normalize_record, spatial_join  # noqa: E402

FIXTURE = json.loads((ENG.parent / "fixtures" / "sample_corridor_context.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((ENG / "data" / "road_inventory_morrissey.geojson").read_text(encoding="utf-8"))
LIB = load_library()


def build(site_facts=None):
    return build_investigation(copy.deepcopy(FIXTURE), INVENTORY, LIB, site_facts=site_facts)


class LibraryTests(unittest.TestCase):
    def test_unknown_source_rejected(self):
        measures = copy.deepcopy(LIB.measures)
        measures["raised_roadway"]["claims"].append({"text": "x", "basis": "sourced", "source_id": "S99"})
        bad = EvidenceLibrary(LIB.sources, measures, LIB.cost_precedents, LIB.cost_caveats,
                              LIB.estimating_guidance, LIB.local_precedents, LIB.version)
        with self.assertRaises(ValueError):
            validate_library(bad)

    def test_cost_precedents_are_2018_samples(self):
        for p in LIB.cost_precedents.values():
            self.assertIn("2018", p["price_basis"])
            self.assertIn("length_ft", p["sample_dimensions"])
            self.assertTrue(p["excluded"])


class RoadFactsTests(unittest.TestCase):
    def test_blank_is_missing_not_zero(self):
        facts = normalize_record({"AADT": " ", "Surface_Wd": "34", "Surface_Tp": "6"})
        self.assertIsNone(facts["aadt"]["value"])
        self.assertEqual(facts["aadt"]["status"], "not_available")
        self.assertEqual(facts["surface_width"]["value"], 34.0)
        self.assertIn("decode", facts["surface_type_code"]["note"])

    def test_spatial_join_matches_and_rejects(self):
        roads = copy.deepcopy(FIXTURE["roads"]["features"][:1])
        far = copy.deepcopy(roads[0])
        far["properties"]["road_id"] = "far"
        far["geometry"]["coordinates"] = [[c[0] + 0.01, c[1]] for c in far["geometry"]["coordinates"]]
        res = spatial_join(roads + [far], INVENTORY["features"])
        self.assertGreater(res[roads[0]["properties"]["road_id"]]["match"]["matched_count"], 0)
        self.assertEqual(res["far"]["records"], [])


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.inv = build()

    def test_contract_fields_present(self):
        for k in ["corridor_id", "road_ids", "road_facts", "flood_evidence", "network_impact",
                  "candidate_methods", "published_cost_examples", "missing_site_information",
                  "citations", "limitations"]:
            self.assertIn(k, self.inv)

    def test_two_to_four_candidates(self):
        self.assertTrue(2 <= len(self.inv["candidate_methods"]) <= 4)

    def test_every_citation_resolves(self):
        ids = {c["citation_id"] for c in self.inv["citations"]}
        for m in self.inv["candidate_methods"]:
            for p in m["sourced_points"]:
                self.assertTrue(p["citation_ids"])
                self.assertTrue(set(p["citation_ids"]) <= ids, p)
        for e in self.inv["published_cost_examples"]["examples"]:
            self.assertTrue(set(e["citation_ids"]) <= ids)
            self.assertFalse(e["transferable"])

    def test_unknowns_are_explicit(self):
        items = {m["item"]: m["status"] for m in self.inv["missing_site_information"]}
        self.assertEqual(items["Pavement structure / layer thicknesses and materials"], NOT_AVAILABLE)
        self.assertIn("Flood depth at the road surface (with datum)", items)
        self.assertIsNone(self.inv["published_cost_examples"]["site_specific_estimate"]["value"])

    def test_mock_inputs_flagged(self):
        self.assertTrue(any("MOCK" in l or "ILLUSTRATIVE" in l for l in self.inv["limitations"]))

    def test_historical_and_future_kept_distinct(self):
        kinds = {f["scenario_id"]: f["kind"] for f in self.inv["flood_evidence"]}
        self.assertEqual(kinds["mcfrm-2050-1pct"], "future_model")
        self.assertEqual(kinds["usgs-2018-jan-event"], "historical_observed")

    def test_setback_rule_screens_out_raised_roadway(self):
        inv = build(site_facts={"adjacent_setbacks": {"value": 5, "source": "test"}})
        self.assertNotIn("raised_roadway", [m["method_id"] for m in inv["candidate_methods"]])
        other = next(o for o in inv["other_methods_considered"] if o["method_id"] == "raised_roadway")
        self.assertIn("14 ft", other["reason"])

    def test_brief_renders(self):
        md = render_brief(self.inv)
        self.assertIn("2018", md)
        self.assertIn("not available / requires site survey", md)


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.inv = build()
        self.ids = {c["citation_id"] for c in self.inv["citations"]} | {"network_impact"}

    def _check_grounded(self, res):
        for b in res["blocks"]:
            if b["kind"] == "sourced":
                self.assertTrue(b["citation_ids"], b)
                self.assertTrue(set(b["citation_ids"]) <= self.ids, b)

    def test_material_question_reports_unknown(self):
        res = answer_deterministic(self.inv, "What is the road made of?")
        self._check_grounded(res)
        self.assertTrue(any(b["kind"] == "unknown" and "Pavement" in b["text"] for b in res["blocks"]))

    def test_cost_filtered_by_method(self):
        res = answer_deterministic(self.inv, "How much would raising it cost?")
        sourced = [b["text"] for b in res["blocks"] if b["kind"] == "sourced"]
        self.assertTrue(sourced)
        self.assertTrue(all("raised roadway" in t.lower() for t in sourced))

    def test_guarantee_question_does_not_overclaim(self):
        res = answer_deterministic(self.inv, "Will raising the road guarantee it stays open?")
        self.assertEqual(res["intent"], "guarantee")
        self.assertTrue(any("cannot say" in b["text"] for b in res["blocks"]))

    def test_all_intents_grounded(self):
        for q in ["Why is this a priority?", "What flood evidence?", "What options?", "Tell me about the berm",
                  "What is missing?", "Any local study?", "List sources", "hello", "drainage?"]:
            res = answer_deterministic(self.inv, q)
            self.assertTrue(res["blocks"], q)
            self._check_grounded(res)

    def test_classify(self):
        self.assertEqual(classify("what options could we investigate"), "candidates")
        self.assertEqual(classify("what does it cost"), "cost")


class ProposalTests(unittest.TestCase):
    def setUp(self):
        self.inv = build()

    def test_hypothetical_proposal(self):
        p = make_proposal(self.inv, "raised_roadway", ["mcfrm-2050-1pct"], intervention_id="iv-t1")
        self.assertEqual(p["status"], "hypothetical")
        self.assertEqual(p["assumed_passability_by_scenario"],
                         {"mcfrm-2050-1pct": "assumed_open", "usgs-2018-jan-event": "unchanged"})
        self.assertIn("not been modelled", p["review_notes"])

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ProposalError):
            make_proposal(self.inv, "seawall_extension", ["mcfrm-2050-1pct"])
        with self.assertRaises(ProposalError):
            make_proposal(self.inv, "raised_roadway", ["no-such-scenario"])
        with self.assertRaises(ProposalError):
            make_proposal(self.inv, "raised_roadway", ["mcfrm-2050-1pct"], road_ids=["not-in-corridor"])

    def test_verified_requires_evidence(self):
        p = make_proposal(self.inv, "raised_roadway", ["mcfrm-2050-1pct"])
        p["status"] = "verified"
        with self.assertRaises(ProposalError):
            validate_proposal(p)
        p["status_evidence"] = {"source_ids": ["S13"], "reviewer": "PE review 2026-10"}
        validate_proposal(p)


if __name__ == "__main__":
    unittest.main()
