import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { ASSUMPTION_NOTE, ProposalError, UNQUANTIFIED_NOTE, defaultEffectClaim, makeProposal } from './proposal';
import type { InterventionProposal, InvestigationResult } from './types';

interface Props {
  investigation: InvestigationResult;
  /** Called with a validated hypothetical proposal. Forward to Person 1 only when proposal.rerank_eligible !== false. */
  onSubmit?: (proposal: InterventionProposal) => void;
}

interface Option {
  id: string;
  label: string;
  group: 'Candidate methods' | 'Cause-matched actions';
}

export function InterventionForm({ investigation, onSubmit }: Props) {
  const inv = investigation;
  const options = useMemo<Option[]>(
    () => [
      ...inv.candidate_methods.map((m) => ({ id: m.method_id, label: m.name, group: 'Candidate methods' as const })),
      ...(inv.cause_assessment?.cause_matched_actions ?? [])
        .filter((a) => a.kind !== 'investigation')
        .map((a) => ({ id: a.action_id, label: `${a.name} (${a.kind})`, group: 'Cause-matched actions' as const })),
    ],
    [inv],
  );
  const [methodId, setMethodId] = useState(options[0]?.id ?? '');
  const [scenarios, setScenarios] = useState<string[]>([]);
  // No roads pre-selected: the planner must choose which roads the assumption covers.
  const [roads, setRoads] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<InterventionProposal | null>(null);

  useEffect(() => {
    setMethodId(options[0]?.id ?? '');
    setScenarios([]);
    setRoads([]);
    setSaved(null);
    setError(null);
  }, [inv, options]);

  const effect = methodId ? defaultEffectClaim(inv, methodId) : 'access_only';
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!roads.length) {
      setError('Select the roads this proposal covers.');
      return;
    }
    try {
      const p = makeProposal(inv, methodId, scenarios, { roadIds: roads, reviewNotes: notes });
      setSaved(p);
      setError(null);
      onSubmit?.(p);
    } catch (err) {
      setError(err instanceof ProposalError ? err.message : 'Could not create proposal.');
    }
  }

  const groups = ['Candidate methods', 'Cause-matched actions'] as const;

  return (
    <form className="fr-inv-form" onSubmit={submit} aria-labelledby="fr-inv-form-title" noValidate>
      <h3 id="fr-inv-form-title">Test an assumed protection</h3>
      <p className="fr-inv-muted">{effect === 'access_only' ? ASSUMPTION_NOTE : UNQUANTIFIED_NOTE}</p>

      {groups.map((g) => {
        const opts = options.filter((o) => o.group === g);
        if (!opts.length) return null;
        return (
          <fieldset key={g}>
            <legend>{g}</legend>
            {opts.map((o) => (
              <label key={o.id} className="fr-inv-option">
                <input
                  type="radio"
                  name="fr-inv-method"
                  value={o.id}
                  checked={methodId === o.id}
                  onChange={() => setMethodId(o.id)}
                />
                {o.label}
              </label>
            ))}
          </fieldset>
        );
      })}

      <p className="fr-inv-small">
        Effect claim: <strong>{effect === 'access_only' ? 'access only' : 'hydraulic / drainage (unquantified)'}</strong>
        {effect !== 'access_only' && (
          <span className="fr-inv-muted"> — road passability and ranking stay unchanged until a before/after flood analysis exists.</span>
        )}
      </p>

      <fieldset>
        <legend>{effect === 'access_only' ? 'Scenarios it is assumed to withstand' : 'Scenarios of interest (recorded, not applied)'}</legend>
        {inv.flood_evidence.map((f) => (
          <label key={f.scenario_id} className="fr-inv-option">
            <input
              type="checkbox"
              checked={scenarios.includes(f.scenario_id)}
              onChange={() => setScenarios((s) => toggle(s, f.scenario_id))}
            />
            {f.label}{' '}
            <span className="fr-inv-muted">
              ({f.kind === 'future_model' ? 'projected' : f.kind === 'historical_observed' ? 'observed' : f.kind})
            </span>
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Roads covered (none selected by default)</legend>
        {inv.road_ids.map((r) => (
          <label key={r} className="fr-inv-option">
            <input type="checkbox" checked={roads.includes(r)} onChange={() => setRoads((s) => toggle(s, r))} />
            {r}
          </label>
        ))}
      </fieldset>

      <label htmlFor="fr-inv-notes">Review notes (optional)</label>
      <textarea id="fr-inv-notes" rows={2} maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)} />

      <p>
        Status: <strong>hypothetical</strong>{' '}
        <span className="fr-inv-muted">(implemented / verified need documented evidence and are not set here)</span>
      </p>

      {error && (
        <p className="fr-inv-error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={!methodId}>
        {effect === 'access_only' ? 'Record proposal and rerank' : 'Record unquantified proposal'}
      </button>

      {saved && (
        <p className="fr-inv-success" role="status">
          Recorded <code>{saved.intervention_id}</code>: {saved.proposed_method.name}.{' '}
          {saved.rerank_eligible
            ? `Assumed open in ${Object.entries(saved.assumed_passability_by_scenario)
              .filter(([, v]) => v === 'assumed_open')
              .map(([k]) => k)
              .join(', ')}.`
            : 'Not sent for reranking; no flood or ranking change is applied.'}
        </p>
      )}
    </form>
  );
}
