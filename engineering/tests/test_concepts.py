"""Acceptance checks for Addendum 2 (concept geometry + separate network assumption).
Run: python -m unittest discover -s tests -v"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ENG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENG))

from floodroute_eng.brief import render_brief  # noqa: E402
from floodroute_eng.concepts import build_concepts, to_feature_collection  # noqa: E402
from floodroute_eng.investigation import build_investigation  # noqa: E402
from floodroute_eng.library import load_library  # noqa: E402
from floodroute_eng.network_assumption import (AssumptionError, make_network_assumption,  # noqa: E402
                                                validate_network_assumption)

ROOT = ENG.parent
FIXTURE = json.loads((ROOT / "fixtures" / "sample_corridor_context.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((ENG / "data" / "road_inventory_morrissey.geojson").read_text(encoding="utf-8"))
DRAINAGE = json.loads((ENG / "data" / "drainage_evidence_corr-fx-morrissey-01.json").read_text(encoding="utf-8"))
LIB = load_library()
ROADS = [f["properties"]["road_id"] for f in FIXTURE["roads"]["features"]]
SCEN = ["mcfrm-2050-1pct", "usgs-2018-jan-event"]
EFFECT_KEYS = {"assumed_passability_by_scenario", "passability", "hypothetical_preserved_road_ids",
               "protected_road_ids", "flood_extent", "extent_geojson", "ranking", "rerank_requested"}


def build():
    inv = build_investigation(copy.deepcopy(FIXTURE), INVENTORY, LIB, drainage=copy.deepcopy(DRAINAGE))
    return inv, build_concepts(inv, FIXTURE, LIB, DRAINAGE)


class ConceptTests(unittest.TestCase):
    def setUp(self):
        self.inv, self.cs = build()
        self.by = {c["intervention_type"]: c for c in self.cs["concepts"]}

    def test_two_to_four_cause_matched_candidates(self):
        self.assertTrue(2 <= len(self.cs["concepts"]) <= 4)
        for c in self.cs["concepts"]:
            self.assertTrue(c["addressed_mechanism_ids"], c["intervention_id"])
            self.assertTrue(c["confirm_with"] and c["refute_if"])
            self.assertEqual(set(c["unresolved_checks"]),
                             {"physical_survey", "ownership_check", "drainage_assessment", "permitting"})
            self.assertEqual(c["status"], "conceptual")

    def test_geometry_provenance(self):
        statuses = {c["geometry_status"] for c in self.cs["concepts"]}
        self.assertIn("sourced_asset_location", statuses)
        self.assertNotIn("sourced_design_alignment", statuses)  # none extracted in this build
        for c in self.cs["concepts"]:
            if c["geometry_status"] == "sourced_asset_location":
                self.assertTrue(c["geometry"] and c["geometry_source_ids"])
            if c["geometry_status"] == "schematic":
                self.assertIn("SCHEMATIC", c["display_badge"])
                self.assertEqual(c["provenance"], "illustrative")
            if c["geometry_status"] == "none":
                self.assertIsNone(c["geometry"])
            for lon, lat in (pt for g in [c["geometry"]] if g for pt in _coords(g)):
                self.assertTrue(-71.2 < lon < -70.9 and 42.2 < lat < 42.45, (lon, lat))

    def test_preview_has_no_effect_fields_and_does_not_mutate_flood(self):
        before = copy.deepcopy(self.inv["flood_evidence"])
        build_concepts(self.inv, FIXTURE, LIB, DRAINAGE)
        self.assertEqual(before, self.inv["flood_evidence"])
        for c in self.cs["concepts"]:
            self.assertFalse(EFFECT_KEYS & set(c), c["intervention_id"])
            self.assertEqual(c["implied_benefit"], "none")
            self.assertIn("NOT roads assumed protected", c["related_road_ids_note"])

    def test_costs_are_dated_samples_and_not_on_drainage(self):
        self.assertEqual(self.by["drainage_upgrade"]["published_cost_precedents"], [])
        self.assertEqual(self.by["drainage_upgrade"]["cost_status"], "cost_estimate_unavailable")
        for c in self.cs["concepts"]:
            for p in c["published_cost_precedents"]:
                self.assertEqual(p["price_year"], 2018)
                self.assertTrue(p["limitations"] and p["example_scope"])

    def test_visual_parameters_cautious(self):
        for c in self.cs["concepts"]:
            vp = c.get("visual_parameters") or {}
            self.assertNotIn("absolute_crest_elevation_m", vp)
            if "conceptual_height_m" in vp:
                self.assertIn("SAMPLE", vp["basis"])
                self.assertIn(vp["source_id"], LIB.sources)

    def test_published_vs_concept_vs_existing_distinguished(self):
        kinds = {d["kind"] for c in self.cs["concepts"] for d in c["evidence_distinction"]}
        self.assertTrue({"published_option", "illustrative_concept", "existing_asset"} <= kinds)

    def test_feature_collection_for_person2(self):
        fc = to_feature_collection(self.cs)
        json.dumps(fc)
        self.assertEqual(len(fc["features"]), sum(1 for c in self.cs["concepts"] if c["geometry"]))
        self.assertTrue(all(f["properties"]["implied_benefit"] == "none" for f in fc["features"]))

    def test_fixture_matches_result_shape(self):
        fx = json.loads((ROOT / "fixtures" / "sample_concept_interventions.json").read_text(encoding="utf-8"))
        self.assertEqual(set(fx), set(self.cs))
        self.assertEqual(set(fx["concepts"][0]), set(self.cs["concepts"][0]))

    def test_brief_includes_concepts(self):
        md = render_brief(self.inv, concepts=self.cs)
        self.assertIn("Concept interventions for preview", md)
        self.assertIn("Unresolved permitting", md)


class NetworkAssumptionTests(unittest.TestCase):
    def setUp(self):
        self.inv, self.cs = build()
        self.road = next(c for c in self.cs["concepts"] if c["intervention_type"] == "raised_roadway")
        self.drain = next(c for c in self.cs["concepts"] if c["intervention_type"] == "drainage_upgrade")

    def mk(self, cid, scen=(), roads=(), select=False, **kw):
        return make_network_assumption(self.cs, cid, scen, roads, ROADS, SCEN, explicitly_select=select, **kw)

    def test_draft_by_default_and_no_rerank(self):
        rec = self.mk(self.road["intervention_id"])
        self.assertEqual(rec["selection_status"], "draft")
        self.assertFalse(rec["rerank_requested"])
        self.assertEqual(rec["hypothetical_preserved_road_ids"], [])  # never auto-filled from related_road_ids

    def test_explicit_selection_requires_roads_and_scenarios(self):
        with self.assertRaises(AssumptionError):
            self.mk(self.road["intervention_id"], scen=["mcfrm-2050-1pct"], select=True)
        with self.assertRaises(AssumptionError):
            self.mk(self.road["intervention_id"], roads=["fx-r-001"], select=True)
        rec = self.mk(self.road["intervention_id"], ["mcfrm-2050-1pct"], ["fx-r-001"], select=True)
        self.assertTrue(rec["rerank_requested"])
        self.assertIn("Does not imply hydraulic validation, physical protection, or changed flood extents.",
                      rec["assumption_notes"])

    def test_unknown_roads_rejected(self):
        with self.assertRaises(AssumptionError):
            self.mk(self.road["intervention_id"], ["mcfrm-2050-1pct"], ["not-a-road"], select=True)

    def test_drainage_needs_hazard_evidence(self):
        with self.assertRaises(AssumptionError):
            self.mk(self.drain["intervention_id"], ["mcfrm-2050-1pct"], ["fx-r-001"], select=True)
        rec = self.mk(self.drain["intervention_id"], ["mcfrm-2050-1pct"], ["fx-r-001"], select=True,
                      hazard_update_evidence={"source_ids": ["test"], "description": "before/after model"})
        self.assertTrue(rec["rerank_requested"])

    def test_tampering_detected(self):
        rec = self.mk(self.road["intervention_id"], ["mcfrm-2050-1pct"], ["fx-r-001"], select=True)
        rec["assumption_notes"] = []
        with self.assertRaises(AssumptionError):
            validate_network_assumption(rec, ROADS, SCEN)
        rec2 = self.mk(self.road["intervention_id"])
        rec2["rerank_requested"] = True
        with self.assertRaises(AssumptionError):
            validate_network_assumption(rec2, ROADS, SCEN)

    def test_separate_from_concept(self):
        rec = self.mk(self.road["intervention_id"], ["mcfrm-2050-1pct"], ["fx-r-001"], select=True)
        self.assertNotIn("geometry", rec)
        self.assertFalse({"hypothetical_preserved_road_ids", "selection_status"} & set(self.road))


def _coords(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point":
        return [c]
    if t in ("MultiPoint", "LineString"):
        return c
    if t == "MultiLineString":
        return [p for line in c for p in line]
    return []


if __name__ == "__main__":
    unittest.main()
