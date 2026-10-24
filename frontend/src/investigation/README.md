# frontend/src/investigation — Person 3 investigation drawer

Self-contained React 18 + TypeScript module. It has no dependencies beyond `react`, and all CSS classes are prefixed `.fr-inv-`. Person 2 owns the app shell and composes this module. Nothing here edits `App.tsx` or shared config.

## Usage (Person 2)

```tsx
import { InvestigationDrawer, loadInvestigation, type InterventionProposal } from './investigation';
import investigation from '../../results/engineering/investigation_corr-fx-morrissey-01.json';

<InvestigationDrawer
  investigation={investigation /* or await loadInvestigation(url) */}
  onProposeIntervention={(p: InterventionProposal) => runCounterfactual(p) /* Person 1 */}
  onClose={() => setSelectedCorridor(null)}
/>
```

If you import the JSON directly, set `resolveJsonModule` in tsconfig, or serve the file and use `loadInvestigation`.

## Contents

- `InvestigationDrawer.tsx` shows why the corridor ranks high, flood evidence (projected vs observed), road facts, candidate methods, local precedent, 2018 cost context, missing site info, sources, and an "Export brief" button.
- `AssistantChat.tsx` is grounded Q&A. It uses `groundedAssistant.ts` (a deterministic port of `engineering/floodroute_eng/assistant.py`) by default. The optional `askRemote` prop can call a backend LLM. Remote answers are rejected if they cite unknown sources or make uncited "sourced" claims.
- `CauseAssessment.tsx` is shown when `investigation.cause_assessment` exists. It covers possible causes with supporting and counter evidence, assets to inspect with mapped owner, next checks, and gated options. It renders nothing extra for v0.1 results.
- `InterventionForm.tsx` emits a typed `InterventionProposal` with status `hypothetical` only. It offers candidate methods and cause-matched maintenance/capital actions. Drainage actions produce `effect_claim: 'hydraulic_or_drainage'` with `rerank_eligible: false`. Only forward proposals to reranking when `rerank_eligible !== false`.
- `proposal.ts` and `brief.ts` handle proposal validation and Markdown brief export.

## Concept preview and network what-if (Addendum 2)

```tsx
import { loadConcepts } from './investigation';
const concepts = await loadConcepts('/results/engineering/concepts_corr-fx-morrissey-01.json'); // or fixtures/sample_concept_interventions.json

<InvestigationDrawer
  investigation={investigation}
  concepts={concepts}
  onPreviewConcept={(c) => cesiumLayer.show(c.geometry, c.geometry_status)}  // display only
  onSubmitNetworkAssumption={(r) => { if (r.rerank_requested) runCounterfactual(r); }}  // Person 1
/>
```

- `ConceptInterventions.tsx` shows concept cards with a geometry provenance badge. Schematic concepts get a red "SCHEMATIC" badge, which the map layer should repeat. Cards also show addressed mechanisms, confirm/refute records, unresolved checks and cost status. "Preview on map" only calls `onPreviewConcept`.
- `NetworkAssumptionForm.tsx` is separate from the concept cards and from `InterventionForm`. It starts with nothing selected. Sending a what-if requires ticking roads, scenarios and an explicit-selection checkbox. Drainage concepts can only be saved as drafts.
- `results/engineering/concepts_<id>.geojson` is a flat FeatureCollection for map layers (`geometry_status`, `display_badge`, `conceptual_height_m`, `height_basis`, `featured`).
- `InterventionForm` no longer pre-selects all corridor roads.

## Accessibility

Native `<details>`, `<fieldset>`/`<legend>`, labelled inputs, a table with `scope` headers, an `aria-live` chat log, `role="alert"` errors, and visible focus outlines. Text and border colours aim for WCAG AA contrast on white. Full conformance needs manual testing with assistive technology.
