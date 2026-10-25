import { useEffect, useRef, useState, type FormEvent } from 'react';
import { CitationLinks } from './Citations';
import { SUGGESTED_QUESTIONS, answerDeterministic, isGroundedAnswer } from './groundedAssistant';
import type { AssistantAnswer, InvestigationResult, RemoteAsk } from './types';

const KIND_LABEL: Record<string, string> = {
  sourced: 'Sourced',
  hypothesis: 'Hypothesis',
  unknown: 'Unknown',
  caveat: 'Caveat',
};

interface Props {
  investigation: InvestigationResult;
  /** Optional live model. Its answers are validated against the citation list; on failure the scripted answer is shown. */
  askRemote?: RemoteAsk;
}

export function AssistantChat({ investigation, askRemote }: Props) {
  const [history, setHistory] = useState<AssistantAnswer[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => setHistory([]), [investigation.corridor_id]);
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [history]);

  async function ask(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    let ans = answerDeterministic(investigation, text);
    if (askRemote) {
      try {
        const remote = await askRemote(text, investigation);
        if (isGroundedAnswer(remote, investigation)) ans = remote;
        else ans = { ...ans, mode: 'deterministic (remote answer rejected: uncited or unknown sources)' };
      } catch {
        ans = { ...ans, mode: 'deterministic (remote assistant unavailable)' };
      }
    }
    setHistory((h) => [...h, ans]);
    setQuestion('');
    setBusy(false);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(question);
  }

  const followups = history.length ? history[history.length - 1].suggested_followups : SUGGESTED_QUESTIONS.slice(0, 3);

  return (
    <section className="fr-inv-chat" aria-labelledby="fr-inv-chat-title">
      <h3 id="fr-inv-chat-title">Ask about this corridor</h3>
      <p className="fr-inv-muted">
        Answers use only this corridor's evidence. Each line is labelled sourced, hypothesis, unknown, or caveat.
      </p>
      <div className="fr-inv-chat-log" ref={logRef} role="log" aria-live="polite" aria-busy={busy} tabIndex={0}>
        {history.length === 0 && <p className="fr-inv-muted">No questions yet.</p>}
        {history.map((a, i) => (
          <div key={i} className="fr-inv-chat-turn">
            <p className="fr-inv-chat-q">
              <span className="fr-inv-visually-hidden">Question: </span>
              {a.question}
            </p>
            <ul className="fr-inv-blocks">
              {a.blocks.map((blk, j) => (
                <li key={j} className={`fr-inv-block fr-inv-block--${blk.kind}`}>
                  <span className="fr-inv-tag">{KIND_LABEL[blk.kind]}</span> {blk.text}{' '}
                  <CitationLinks ids={blk.citation_ids} citations={investigation.citations} />
                </li>
              ))}
            </ul>
            <p className="fr-inv-muted fr-inv-small">Mode: {a.mode}</p>
          </div>
        ))}
      </div>
      <div className="fr-inv-suggestions" aria-label="Suggested questions">
        {followups.map((f) => (
          <button key={f} type="button" className="fr-inv-chip" onClick={() => void ask(f)} disabled={busy}>
            {f}
          </button>
        ))}
      </div>
      <form className="fr-inv-chat-form" onSubmit={onSubmit}>
        <label htmlFor="fr-inv-question" className="fr-inv-visually-hidden">
          Question about this corridor
        </label>
        <input
          id="fr-inv-question"
          type="text"
          value={question}
          maxLength={500}
          placeholder="e.g. What is the road made of?"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !question.trim()}>
          {busy ? 'Thinking…' : 'Ask'}
        </button>
      </form>
    </section>
  );
}
