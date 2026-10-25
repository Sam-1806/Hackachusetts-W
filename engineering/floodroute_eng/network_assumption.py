"""Network what-if for Person 1 (Addendum 2). Output 2 of 2, separate from concept geometry.

A ``NetworkAssumptionForReview`` is a QUESTION to the network simulator ("if these roads stayed
passable in these scenarios, what changes?"), not a forecast that the intervention works.

Rules:
* Preserved roads are chosen explicitly. They are never copied from a concept's geometry or
  ``related_road_ids``.
* ``draft`` records may be incomplete. ``explicitly_selected_for_counterfactual`` requires the
  caller to opt in, at least one scenario, and at least one preserved road from the graph.
* Drainage concepts cannot be selected without ``hazard_update_evidence`` (Addendum 1: a
  drainage change needs validated before/after flood analysis before it changes ranking).
* Person 1 should rerank only when ``rerank_requested`` is true.

This module does not touch ``InterventionProposal`` (intervention.py), which stays as before.
"""

from __future__ import annotations

import datetime
from typing import Iterable

SCHEMA_VERSION = "network-assumption-v0.1"
SELECTION_STATUSES = ("draft", "explicitly_selected_for_counterfactual")
FIXED_NOTES = [
    "Hypothetical access assumption for network analysis only.",
    "Does not imply hydraulic validation, physical protection, or changed flood extents.",
]


class AssumptionError(ValueError):
    pass


def make_network_assumption(concept_set: dict, intervention_id: str, scenario_ids: Iterable[str],
                            preserved_road_ids: Iterable[str], known_road_ids: Iterable[str],
                            known_scenario_ids: Iterable[str], notes: Iterable[str] = (),
                            explicitly_select: bool = False,
                            hazard_update_evidence: dict | None = None) -> dict:
    concept = next((c for c in concept_set["concepts"] if c["intervention_id"] == intervention_id), None)
    if concept is None:
        raise AssumptionError(f"Unknown concept intervention_id {intervention_id!r}")
    rec = {
        "schema_version": SCHEMA_VERSION,
        "intervention_id": intervention_id,
        "intervention_type": concept["intervention_type"],
        "graph_version": concept_set.get("graph_version"),
        "scenario_ids": list(dict.fromkeys(scenario_ids)),
        "hypothetical_preserved_road_ids": list(dict.fromkeys(preserved_road_ids)),
        "selection_status": "explicitly_selected_for_counterfactual" if explicitly_select else "draft",
        "assumption_notes": FIXED_NOTES + [n.strip() for n in notes if n and n.strip()],
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    if hazard_update_evidence:
        rec["hazard_update_evidence"] = hazard_update_evidence
    rec["rerank_requested"] = rec["selection_status"] == "explicitly_selected_for_counterfactual"
    validate_network_assumption(rec, known_road_ids, known_scenario_ids)
    return rec


def validate_network_assumption(rec: dict, known_road_ids: Iterable[str], known_scenario_ids: Iterable[str]) -> None:
    for k in ("intervention_id", "graph_version", "scenario_ids", "hypothetical_preserved_road_ids",
              "selection_status", "assumption_notes"):
        if k not in rec:
            raise AssumptionError(f"Missing field {k}")
    if rec["selection_status"] not in SELECTION_STATUSES:
        raise AssumptionError(f"selection_status must be one of {SELECTION_STATUSES}")
    roads, scen = set(known_road_ids), set(known_scenario_ids)
    bad_r = [r for r in rec["hypothetical_preserved_road_ids"] if r not in roads]
    bad_s = [s for s in rec["scenario_ids"] if s not in scen]
    if bad_r:
        raise AssumptionError(f"Preserved roads not in graph {rec['graph_version']}: {bad_r}")
    if bad_s:
        raise AssumptionError(f"Unknown scenario ids: {bad_s}")
    if not all(n in rec["assumption_notes"] for n in FIXED_NOTES):
        raise AssumptionError("Required assumption notes removed")
    if rec["selection_status"] == "explicitly_selected_for_counterfactual":
        if not rec["scenario_ids"]:
            raise AssumptionError("Select at least one scenario before requesting a counterfactual")
        if not rec["hypothetical_preserved_road_ids"]:
            raise AssumptionError("Select at least one preserved road explicitly before requesting a counterfactual")
        if rec.get("intervention_type") == "drainage_upgrade":
            ev = rec.get("hazard_update_evidence") or {}
            if not ev.get("source_ids") or not ev.get("description"):
                raise AssumptionError("Drainage concepts need hazard_update_evidence (validated before/after flood "
                                      "analysis) before a network counterfactual can be requested")
    if rec.get("rerank_requested") and rec["selection_status"] != "explicitly_selected_for_counterfactual":
        raise AssumptionError("rerank_requested is only allowed for explicitly selected assumptions")
