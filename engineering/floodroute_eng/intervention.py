"""Create and validate ``InterventionProposal`` records.

A proposal tells Person 1's counterfactual engine: "assume these roads are
passable in these scenarios". It never edits flood extents and never marks a
road fixed. ``implemented`` / ``verified`` statuses require cited evidence and
a named reviewer note; the planner form can only create ``hypothetical``.

Causal Diagnosis Addendum (additive fields):
* ``effect_claim = "access_only"``: idealized passability assumption for the graph
  counterfactual. No claimed reduction in flooding or property losses.
* ``effect_claim = "hydraulic_or_drainage"``: drainage/maintenance/outfall work. Without
  ``hazard_update_evidence`` (validated before/after flood surfaces or engineered
  calculations) it is an *unquantified proposal*: every scenario stays ``unchanged`` and
  Person 1 must not rerank on it.
"""

from __future__ import annotations

import datetime
import re
import uuid
from typing import Iterable

STATUSES = ("hypothetical", "implemented", "verified")
PASSABILITY_VALUES = ("assumed_open", "unchanged")
EFFECT_CLAIMS = ("access_only", "hydraulic_or_drainage")
DEFAULT_ASSUMPTION_NOTE = ("Idealized assumption for network counterfactual only. "
                           "Physical effectiveness has not been modelled or verified.")
UNQUANTIFIED_NOTE = ("Unquantified drainage/hydraulic proposal. Road exposure, property-loss projections and "
                     "network ranking stay unchanged until validated before/after flood analysis is supplied.")
HYDRAULIC_METHODS = {"drainage_backflow"}


class ProposalError(ValueError):
    pass


def _lookup(investigation: dict, method_id: str) -> tuple[dict, str]:
    """Return (record, kind) for a candidate method or a cause-matched action."""
    for m in investigation["candidate_methods"]:
        if m["method_id"] == method_id:
            return m, "method"
    for o in investigation.get("other_methods_considered", []):
        if o["method_id"] == method_id and o.get("details"):
            return o["details"], "method"
    for a in (investigation.get("cause_assessment") or {}).get("cause_matched_actions", []):
        if a["action_id"] == method_id:
            return a, "action"
    raise ProposalError(f"{method_id!r} is not a candidate method or cause-matched action for "
                        f"{investigation['corridor_id']}")


def make_proposal(investigation: dict, method_id: str, scenario_ids: Iterable[str],
                  road_ids: Iterable[str] | None = None, review_notes: str = "",
                  intervention_id: str | None = None, effect_claim: str | None = None,
                  hazard_update_evidence: dict | None = None) -> dict:
    """Build a hypothetical proposal from an InvestigationResult."""
    rec, kind = _lookup(investigation, method_id)
    if effect_claim is None:
        is_drainage = (kind == "action" and rec["mechanism"] != "coastal_overland") or method_id in HYDRAULIC_METHODS
        effect_claim = "hydraulic_or_drainage" if is_drainage else "access_only"
    if effect_claim not in EFFECT_CLAIMS:
        raise ProposalError(f"effect_claim must be one of {EFFECT_CLAIMS}")

    all_scenarios = [f["scenario_id"] for f in investigation["flood_evidence"]]
    chosen = list(scenario_ids)
    unknown = set(chosen) - set(all_scenarios)
    if unknown:
        raise ProposalError(f"Unknown scenario ids: {sorted(unknown)}")
    quantified = effect_claim == "access_only" or bool(hazard_update_evidence)
    if quantified and not chosen:
        raise ProposalError("Select at least one scenario the measure is assumed to withstand")

    roads = list(road_ids) if road_ids is not None else list(investigation["road_ids"])
    if kind == "method":
        name, category = rec["name"], rec["category"]
        source_ids = sorted({cid.split("#")[0] for p in rec["sourced_points"] for cid in p["citation_ids"]})
        mechanism = None
    else:
        name, category = rec["name"], rec["kind"]
        source_ids = sorted(set(rec["source_ids"]))
        mechanism = rec["mechanism"]

    note = DEFAULT_ASSUMPTION_NOTE if quantified and effect_claim == "access_only" else \
        UNQUANTIFIED_NOTE if not quantified else "Hydraulic effect per supplied hazard update evidence; engineer review required."
    proposal = {
        "intervention_id": intervention_id or f"iv-{uuid.uuid4().hex[:8]}",
        "corridor_id": investigation["corridor_id"],
        "road_ids": roads,
        "graph_version": investigation.get("graph_version"),
        "proposed_method": {"method_id": method_id, "name": name, "category": category},
        "status": "hypothetical",
        "assumed_passability_by_scenario": {
            sid: ("assumed_open" if quantified and sid in chosen else "unchanged") for sid in all_scenarios
        },
        "review_notes": (review_notes.strip() + " " if review_notes.strip() else "") + note,
        "source_ids": source_ids,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "effect_claim": effect_claim,
        "mechanism": mechanism,
        "effect_status": "idealized_access_assumption" if effect_claim == "access_only" else
                         "hazard_update_supplied" if quantified else "unquantified_proposal",
        "rerank_eligible": quantified,
        "requested_scenarios": chosen,
    }
    if hazard_update_evidence:
        proposal["hazard_update_evidence"] = hazard_update_evidence
    validate_proposal(proposal, investigation)
    return proposal


def validate_proposal(p: dict, investigation: dict | None = None) -> None:
    """Raise ProposalError if the record breaks the contract or overclaims."""
    required = ["intervention_id", "corridor_id", "road_ids", "proposed_method", "status",
                "assumed_passability_by_scenario", "review_notes", "source_ids"]
    missing = [k for k in required if k not in p]
    if missing:
        raise ProposalError(f"Missing fields: {missing}")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", p["intervention_id"]):
        raise ProposalError("intervention_id must be 1-64 chars of [A-Za-z0-9_.:-]")
    if p["status"] not in STATUSES:
        raise ProposalError(f"status must be one of {STATUSES}")
    if not p["road_ids"]:
        raise ProposalError("road_ids must not be empty")
    bad = {k: v for k, v in p["assumed_passability_by_scenario"].items() if v not in PASSABILITY_VALUES}
    if bad:
        raise ProposalError(f"Invalid passability values: {bad}")
    effect = p.get("effect_claim", "access_only")  # v0.1 records have no effect_claim
    if effect not in EFFECT_CLAIMS:
        raise ProposalError(f"effect_claim must be one of {EFFECT_CLAIMS}")
    opens = "assumed_open" in p["assumed_passability_by_scenario"].values()
    if effect == "access_only" and not opens:
        raise ProposalError("Proposal does not assume passability in any scenario")
    if effect == "hydraulic_or_drainage" and opens:
        ev = p.get("hazard_update_evidence") or {}
        if not ev.get("source_ids") or not ev.get("description"):
            raise ProposalError("hydraulic_or_drainage proposals cannot change passability without "
                                "hazard_update_evidence (source_ids + description)")
    if p["status"] in ("implemented", "verified"):
        evidence = p.get("status_evidence") or {}
        if not evidence.get("source_ids") or not evidence.get("reviewer"):
            raise ProposalError(f"status '{p['status']}' requires status_evidence with source_ids and reviewer")
    if investigation is not None:
        if p["corridor_id"] != investigation["corridor_id"]:
            raise ProposalError("corridor_id does not match investigation")
        extra = set(p["road_ids"]) - set(investigation["road_ids"])
        if extra:
            raise ProposalError(f"road_ids outside corridor: {sorted(extra)}")
