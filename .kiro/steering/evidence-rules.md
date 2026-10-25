---
inclusion: fileMatch
fileMatchPattern: "{engineering/**,frontend/src/investigation/**,handoff/**}"
---

# Evidence and honesty rules (engineering workstream)

These rules come from the team work split and the Causal Diagnosis and Intervention Geometry addenda. Apply them to any code, data, UI text, or assistant answer in the engineering workstream.

## Facts and sources
- Every factual claim cites a `source_id` registered in `engineering/evidence/sources.json`. Unknown source IDs must fail validation.
- Missing data is `null` and shown as "not available / requires site survey". Never zero, never guessed.
- Test a data source for machine-readable access before relying on it. If blocked (e.g. HTTP 403) or key-gated, record it as `not_available`.
- Label every input `observed`, `published_model`, `derived`/`computed`, `assumed`, or `mock`. Mock values must stay visibly labelled.

## Causes
- The flooded road is the impacted location; the asset needing work may be an inlet, pipe, outfall, or shoreline.
- Cause status is only `possible`, `evidence_supported`, or `unresolved`. No numeric likelihoods.
- A flood polygon, study, regional model, or 311 complaint alone can never make a cause `evidence_supported`; that needs a non-mock site record within 50 m.
- Never conclude "raise the road" from exposure or network priority alone.

## Costs
- Only quote the 2018 Boston guideline sample costs, with sample length, contingency, exclusions, and "not transferable".
- Drainage, maintenance and outfall work is `cost_estimate_unavailable` with quote inputs. Never apply barrier/raised-road samples to it.

## Concepts and what-ifs
- `ConceptIntervention` geometry implies no benefit: no passability, flood, or ranking fields.
- `geometry_status` must be honest: `sourced_asset_location`, `schematic` (badged), or `none`. No absolute elevations without a datum.
- `NetworkAssumptionForReview` starts as `draft` with no preserved roads; reranking needs explicit selection. Drainage concepts need `hazard_update_evidence` first.
- Previews never change flood layers, road colours, or rankings.
