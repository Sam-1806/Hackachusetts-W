---
inclusion: manual
---

# Data contracts between streams

The TypeScript source of truth is `frontend/src/domain/contracts.ts`. Person 3's extended types are in `frontend/src/investigation/types.ts`. New fields must be optional and additive; agree contract changes with Person 1 before freezing a version.

| Record | Producer → consumer | Key rules |
|:--|:--|:--|
| `RoadManifest` / `network.json` | Person 1 → all | Canonical `road_id`, `graph_version` |
| `FloodExposureResult` | Person 2 (Person 3 joins extents to roads) → 1, 3 | `exposure` exposed / not_exposed / unknown; `depth_m: null` if unknown; `passability: unknown` from overlap only |
| `RoadRankingResult` | Person 1 → 2, 3 | Unreachable journeys kept (`reachable: false`, penalty 3600 s); `assumptions` state the closure rule |
| `InvestigationResult` (+ optional `cause_assessment`) | Person 3 → 2 | Cited fields only; mock inputs listed in `provenance.input_data_status` |
| `ConceptIntervention` | Person 3 → 2 | Map preview only; `implied_benefit: "none"` |
| `NetworkAssumptionForReview` | Person 3 → 1 | Rerank only when `rerank_requested` is true |
| `InterventionProposal` | Person 3 → 1 | Rerank only when `rerank_eligible !== false` |
| `CounterfactualResult` | Person 1 (interim: Person 3) → 2 | Access assumption only; no hydraulic effect implied |

Interim ranking in `engineering/scripts/rank_corridors.py` must pass `--validate` against Person 1's runs in `engineering/data/p1_inputs/results/` before its output is used.
