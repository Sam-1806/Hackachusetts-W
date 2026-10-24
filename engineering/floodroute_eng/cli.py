"""Command line entry point.

Run from engineering/:

    python -m floodroute_eng.cli investigate            # fixture -> results/engineering/investigation_<id>.json
    python -m floodroute_eng.cli ask "What options could we investigate?"
    python -m floodroute_eng.cli propose --method raised_roadway --scenario mcfrm-2050-1pct
    python -m floodroute_eng.cli brief
    python -m floodroute_eng.cli concepts [--fixture]   # ConceptIntervention set (+ GeoJSON) for Person 2
    python -m floodroute_eng.cli assume --intervention <id> --scenario <sid> --preserve <road_id> [--select]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .assistant import answer
from .brief import render_brief
from .concepts import build_concepts, to_feature_collection
from .network_assumption import AssumptionError, make_network_assumption
from .intervention import ProposalError, make_proposal
from .investigation import build_investigation
from .library import load_library
from .road_facts import load_json

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTEXT = ROOT / "fixtures" / "sample_corridor_context.json"
DEFAULT_INVENTORY = ROOT / "engineering" / "data" / "road_inventory_morrissey.geojson"
RESULTS = ROOT / "results" / "engineering"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def _investigation(args) -> dict:
    ctx = load_json(args.context)
    site = load_json(args.site_facts) if args.site_facts else None
    drainage_path = Path(args.drainage) if args.drainage else \
        ROOT / "engineering" / "data" / f"drainage_evidence_{args.corridor or ctx['corridor']['corridor_id']}.json"
    drainage = load_json(drainage_path) if drainage_path.exists() else None
    inv = build_investigation(ctx, load_json(args.inventory), load_library(),
                              corridor_id=args.corridor, site_facts=site, drainage=drainage,
                              with_diagnosis=not args.no_diagnosis)
    return inv, ctx, drainage


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="floodroute_eng")
    ap.add_argument("--context", default=str(DEFAULT_CONTEXT), help="Corridor context JSON (fixture shape)")
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY), help="Road Inventory GeoJSON snapshot")
    ap.add_argument("--corridor", default=None, help="corridor_id (defaults to the context's corridor)")
    ap.add_argument("--site-facts", default=None, help="Optional JSON of engineer-supplied site facts")
    ap.add_argument("--drainage", default=None,
                    help="Drainage evidence JSON (default: engineering/data/drainage_evidence_<corridor>.json if present)")
    ap.add_argument("--no-diagnosis", action="store_true", help="Omit the optional cause_assessment field")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("investigate")
    a = sub.add_parser("ask")
    a.add_argument("question")
    p = sub.add_parser("propose")
    p.add_argument("--method", required=True)
    p.add_argument("--scenario", action="append", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--id", default=None)
    p.add_argument("--effect-claim", choices=["access_only", "hydraulic_or_drainage"], default=None,
                   help="Default inferred: drainage/maintenance actions -> hydraulic_or_drainage")
    sub.add_parser("brief")
    c = sub.add_parser("concepts", help="ConceptIntervention set for map preview (Person 2)")
    c.add_argument("--fixture", action="store_true", help="Also write fixtures/sample_concept_interventions.json")
    na = sub.add_parser("assume", help="NetworkAssumptionForReview for Person 1 (separate from concepts)")
    na.add_argument("--intervention", required=True, help="Concept intervention_id")
    na.add_argument("--scenario", action="append", default=[])
    na.add_argument("--preserve", action="append", default=[], help="Road id explicitly assumed passable")
    na.add_argument("--note", action="append", default=[])
    na.add_argument("--select", action="store_true", help="Explicitly select for the counterfactual (requests rerank)")
    args = ap.parse_args(argv)

    inv, ctx, drainage = _investigation(args)
    cid = inv["corridor_id"]
    if args.cmd in ("concepts", "assume"):
        concept_set = build_concepts(inv, ctx, load_library(), drainage)
        if args.cmd == "concepts":
            _write(RESULTS / f"concepts_{cid}.json", json.dumps(concept_set, indent=2))
            _write(RESULTS / f"concepts_{cid}.geojson", json.dumps(to_feature_collection(concept_set), indent=1))
            if args.fixture:
                _write(ROOT / "fixtures" / "sample_concept_interventions.json", json.dumps(concept_set, indent=2))
            return 0
        try:
            rec = make_network_assumption(
                concept_set, args.intervention, args.scenario, args.preserve,
                known_road_ids=[f["properties"]["road_id"] for f in ctx["roads"]["features"]],
                known_scenario_ids=[f["scenario_id"] for f in inv["flood_evidence"]],
                notes=args.note, explicitly_select=args.select)
        except AssumptionError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        _write(RESULTS / f"network_assumption_{rec['intervention_id']}.json", json.dumps(rec, indent=2))
        return 0
    if args.cmd == "investigate":
        _write(RESULTS / f"investigation_{cid}.json", json.dumps(inv, indent=2))
    elif args.cmd == "ask":
        res = answer(inv, args.question)
        for b in res["blocks"]:
            cites = f" [{', '.join(b['citation_ids'])}]" if b["citation_ids"] else ""
            print(f"[{b['kind']}] {b['text']}{cites}")
        print(f"(mode: {res['mode']}, intent: {res['intent']})")
    elif args.cmd == "propose":
        try:
            prop = make_proposal(inv, args.method, args.scenario, review_notes=args.notes, intervention_id=args.id,
                                 effect_claim=args.effect_claim)
        except ProposalError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        _write(RESULTS / f"intervention_{prop['intervention_id']}.json", json.dumps(prop, indent=2))
    elif args.cmd == "brief":
        _write(RESULTS / f"brief_{cid}.md", render_brief(inv, concepts=build_concepts(inv, ctx, load_library(), drainage)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
