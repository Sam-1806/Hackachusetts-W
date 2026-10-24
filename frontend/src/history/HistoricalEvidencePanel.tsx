import { EvidenceSourceDrawer } from "./EvidenceSourceDrawer";
import { TideLevelChart } from "./TideLevelChart";
import type { HistoricalEventEvidence } from "./types";
import "./history.css";

export interface HistoricalEvidencePanelProps {
  events: HistoricalEventEvidence[];
  selectedEventId?: string;
  onSelectEvent?: (eventId: string) => void;
  className?: string;
}

export function HistoricalEvidencePanel({
  events,
  selectedEventId,
  onSelectEvent,
  className = "",
}: HistoricalEvidencePanelProps) {
  const selectedEvent =
    events.find((event) => event.eventId === selectedEventId) ?? events[0];

  if (!selectedEvent) {
    return (
      <section className={`history-panel history-empty ${className}`}>
        <strong>No historical evidence configured</strong>
        <span>Add a sourced event record to enable this panel.</span>
      </section>
    );
  }

  const limitations = [
    ...selectedEvent.limitations,
    ...(selectedEvent.gaugeSeries?.limitations ?? []),
  ];

  return (
    <section className={`history-panel ${className}`} aria-labelledby="historical-evidence-title">
      <header className="history-panel__header">
        <div>
          <span className="history-kicker">Historical evidence</span>
          <h2 id="historical-evidence-title">Event record</h2>
        </div>
        <span className={`history-status history-status--${selectedEvent.footprintStatus}`}>
          {selectedEvent.footprintStatus === "observed"
            ? "Observed"
            : selectedEvent.footprintStatus === "illustrative"
              ? "Illustrative"
              : "Mock"}
        </span>
      </header>

      <label className="history-select">
        <span>Evidence event</span>
        <select
          value={selectedEvent.eventId}
          onChange={(event) => onSelectEvent?.(event.target.value)}
          disabled={events.length < 2 || !onSelectEvent}
        >
          {events.map((event) => (
            <option key={event.eventId} value={event.eventId}>
              {event.title} · {event.dateLabel}
            </option>
          ))}
        </select>
      </label>

      <article className="history-event-card">
        <div>
          <h3>{selectedEvent.title}</h3>
          <time>{selectedEvent.dateLabel}</time>
        </div>
        <p>{selectedEvent.summary}</p>
        <div className="history-footprint-row">
          <span>Peak footprint</span>
          <strong>{selectedEvent.footprintLabel}</strong>
        </div>
      </article>

      <TideLevelChart series={selectedEvent.gaugeSeries} />

      <div className="history-warning" role="note">
        <strong>No physical street-level replay</strong>
        <span>
          A peak footprint and a tide gauge do not provide local water direction, velocity,
          or time-dependent road depth.
        </span>
      </div>

      <EvidenceSourceDrawer sources={selectedEvent.sources} limitations={limitations} />
    </section>
  );
}

