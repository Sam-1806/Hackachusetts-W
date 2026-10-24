# engineering/ — Person 3: road facts, engineering evidence, assistant

Answers "what could a civil engineer reasonably investigate at this corridor, why, and what evidence is missing?" It produces `InvestigationResult` and `InterventionProposal` JSON. It does not design, certify, or price anything.

Python 3.12, standard library only (no installs needed).

## Run (from `engineering/`)

```powershell
python -m floodroute_eng.cli investigate          # -> results/engineering/investigation_<corridor_id>.json
python -m floodroute_eng.cli ask "What options could we investigate?"
python -m floodroute_eng.cli propose --method raised_roadway --scenario mcfrm-2050-1pct --id iv-fx-001
python -m floodroute_eng.cli brief                # -> results/engineering/brief_<corridor_id>.md
python -m unittest discover -s tests -v
```

Options: `--context <corridor context json>` (default `fixtures/sample_corridor_context.json`), `--inventory <geojson>`, `--corridor <id>`, `--site-facts <json>` (engineer-supplied facts, e.g. `{"adjacent_setbacks": {"value": 20, "source": "site visit 2026-10-25"}}`).

## What is real and what is mock

| Piece | Status |
|:--|:--|
| Road facts for Morrissey Blvd (`data/road_inventory_morrissey.geojson`, 76 records) | Real. Fetched from S10 on 2026-10-24 via `scripts/fetch_road_inventory.py` |
| Engineering methods, claims, page refs (`evidence/measures.json`) | Real. Read from the 2018 Boston guideline PDFs (S11 sections 4–7) and the June 2025 Morrissey study (S12) |
| Cost examples (`evidence/cost_precedents.json`) | Real 2018 sample figures with dimensions, contingency, and exclusions. Not transferable to this corridor |
| Corridor road IDs, flood exposure, ranking, journeys (`fixtures/sample_corridor_context.json`) | **Mock**. Geometry is copied from S10 so the spatial join works; replace with Person 1/2 outputs |
| Drainage evidence (`data/drainage_evidence_<corridor>.json`) | Real. BWSC catch basins and Boston 311 reports near the corridor, fetched 2026-10-24 |

Road Inventory codes (surface type, jurisdiction, condition) are passed through raw. The MassDOT data dictionary returned HTTP 403 during the build, so codes are not decoded and widths are labelled `ft (assumed)`.

## Layout

```text
floodroute_eng/
  road_facts.py     S10 fetch, normalization (blank -> missing, never 0), spatial join to manifest roads
  library.py        loads + validates evidence/*.json (unknown source ids fail fast)
  investigation.py  builds InvestigationResult; screens methods (supports / against / unknown)
  assistant.py      grounded Q&A; deterministic by default, optional Anthropic LLM with citation validation
  intervention.py   InterventionProposal create/validate (UI can only create 'hypothetical')
  brief.py          Markdown engineer review brief
  cli.py
evidence/           sources.json, measures.json, cost_precedents.json, local_precedents.json
prompts/            assistant_system.md (LLM system prompt)
scripts/            fetch_road_inventory.py, make_fixture.py
tests/              unittest suite
```

## Cause diagnosis (Causal Diagnosis Addendum)

The flow is flooded road → competing cause hypotheses → evidence and missing checks → cause-matched actions → engineer review. The result is an optional `cause_assessment` field (`DiagnosticAddendum`) on the InvestigationResult. Use `--no-diagnosis` to get the v0.1 shape.

```powershell
python scripts/fetch_drainage_evidence.py            # BWSC catch basins + Boston 311 near the corridor
python -m floodroute_eng.cli ask "What might be causing the flooding?"
python -m floodroute_eng.cli ask "What should be inspected, and who owns it?"
python -m floodroute_eng.cli propose --method inspect_clean_inlets --scenario mcfrm-2050-1pct
```

- Mechanisms: `coastal_overland`, `tidal_outfall_backwater`, `inlet_blockage`, `storm_drain_capacity`, `surface_grading`, `multiple_or_unknown` (`evidence/mechanisms.json`). Status is `possible` / `evidence_supported` / `unresolved`, with no numeric likelihoods.
- A mechanism becomes `evidence_supported` only from a non-mock engineering record or measurement within 50 m of the corridor. Flood polygons, studies, regional models and 311 complaints alone stay `possible` at most.
- Evidence types are kept separate: `observed_report`, `observed_measurement`, `published_model`, `gis_derived`, `engineering_record`, `hypothesis`, `unknown`.
- The road is listed as the `impacted_location`. Catch basins, pipes, outfalls and shoreline are `possible_cause_asset`. Owners appear only as mapped (`as_mapped_unverified`), otherwise `unknown`.
- Candidate methods gain `addresses_mechanisms`, `cause_gate` and `cause_relevance`. Construction is offered only "if the mechanism is confirmed".
- Drainage and maintenance actions carry `cost_estimate_unavailable` plus quote inputs. The 2018 samples are attached only to coastal capital options.
- Proposals gain `effect_claim`. `access_only` is the idealized passability used for reranking. `hydraulic_or_drainage` keeps every scenario `unchanged` and sets `rerank_eligible: false` unless `hazard_update_evidence` is supplied.

Data access, tested 2026-10-24:

| Source | Status |
|:--|:--|
| BWSC catch basins (FeatureServer behind the public locator map) | Obtained. 59 basins within 40 m; mapped owners DCR 47, PRIV 10, BWSC 2. No licence text found, so use for research display only |
| Boston 311 (data.boston.gov CKAN, 2018–2026) | Obtained. 35 `Catchbasin` / `Roadway Flooding` cases within 400 m, with closure notes |
| Open311 API | Not used; needs an API key |
| BWSC Inundation Model, disclaimers, adaptation scenarios | Pages read. No model layers obtained |
| Pipes, outfalls, inverts, maintenance logs | `not_available` |
| MassDOT PDDG Ch. 8, MA Climate Resilience Design Standards | mass.gov returned 403 to scripts; content not read |
| NOAA Atlas 14 | Reachable; no point estimate retrieved |

## Concept geometry and network what-if (Addendum 2): two separate outputs

```powershell
python -m floodroute_eng.cli concepts --fixture      # results/engineering/concepts_<id>.json + .geojson (+ fixture copy)
python -m floodroute_eng.cli assume --intervention ci-corr-fx-morrissey-01-raised_roadway `
  --scenario mcfrm-2050-1pct --preserve fx-r-001 --preserve fx-r-002 --select
```

**1. `ConceptSet` / `ConceptIntervention`, for Person 2 (map preview).** `concepts.py` holds 2–4 cause-matched concepts. Each records the mechanism it addresses, records that would confirm or refute that mechanism (`evidence/mechanism_checks.json`), and unresolved survey, ownership, drainage and permitting checks. It also labels each piece of evidence as published option, our concept, or existing asset, and attaches dated 2018 cost samples, or `cost_estimate_unavailable` for drainage. Concepts carry **no** passability, flood, or ranking fields (`implied_benefit: "none"`).

| Concept | Geometry | `geometry_status` |
|:--|:--|:--|
| Inspect/clean inlets (featured) | 10 nearest BWSC catch basins (MultiPoint) | `sourced_asset_location` |
| Raised roadway | Corridor centerlines from S10 (MultiLineString); display height = guideline sample 4 ft | `sourced_asset_location` (road, not a design) |
| Vegetated berm | Line drawn 40 m bay-side of the corridor; display height = sample 2 ft | `schematic` (no alignment extractable from S12 figures) |
| Deployable barrier | None (opening not identified) | `none` |

Alternate access and outfall adaptation are kept as cards in `alternatives_not_rendered`. No `sourced_design_alignment` exists yet, and no absolute elevations are given.

**2. `NetworkAssumptionForReview`, for Person 1 (`network_assumption.py`).** This is a separate sidecar, `network_assumption_<id>.json`, and is not `InterventionProposal`. It defaults to `draft` with no preserved roads. Preserved roads are never copied from the concept's `related_road_ids`. `explicitly_selected_for_counterfactual` (`--select`) requires scenarios, at least one preserved road from the graph, and for drainage concepts `hazard_update_evidence`. **Person 1 reruns only when `rerank_requested` is true.**

`InterventionProposal` (`propose`) is unchanged.

## Integration

- Input: a corridor context with `{corridor, roads, scenarios, flood_exposure, ranking}`. `roads` are Person 1 manifest features (EPSG:4326, `properties.road_id`); `flood_exposure` is a list of Person 2 `FloodExposureResult`; `ranking` is Person 1's `RoadRankingResult`. When real outputs land, assemble that object and pass `--context`; nothing else changes.
- Output to Person 2: `results/engineering/investigation_<corridor_id>.json`, rendered by `frontend/src/investigation/`.
- Output to Person 1: `InterventionProposal`. `assumed_passability_by_scenario` maps every scenario to `assumed_open` or `unchanged`. Apply it in a sandbox graph only, and only when `rerank_eligible` is not `false`. `implemented` / `verified` status requires `status_evidence.source_ids` and `reviewer`.

## Optional live LLM

Set `FLOODROUTE_LLM=anthropic`, `ANTHROPIC_API_KEY`, and optionally `FLOODROUTE_LLM_MODEL`. The assistant then sends the InvestigationResult (public-source facts plus fixture values) to the Anthropic API. Answers that cite unknown IDs or make uncited "sourced" claims are rejected, and the deterministic answer is used instead. Off by default.

## Rules this module enforces

- Missing facts are reported as "not available / requires site survey", never guessed.
- Every `sourced` statement carries a citation that resolves to `citations[]`.
- Future scenarios (`future_model`) and observed events (`historical_observed`) stay separate.
- Costs are labelled as 2018 samples for other sites, and no site-specific estimate is produced.
- A proposal changes only an *assumed* passability. It never edits flood data or marks a road fixed.
