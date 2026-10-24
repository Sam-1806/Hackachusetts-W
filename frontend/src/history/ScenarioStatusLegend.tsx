import type { EvidenceStatus, ScenarioStatusItem } from "./types";

const defaultLabels: Record<EvidenceStatus, string> = {
  observed: "Observed evidence",
  published_model: "Published future model",
  computed: "Computed result",
  assumed: "Explicit assumption",
  illustrative: "Illustrative display",
  mock: "Fixture / mock",
};

const defaultDescriptions: Record<EvidenceStatus, string> = {
  observed: "Measured or documented historical evidence.",
  published_model: "An official modeled scenario, not a historical date or live forecast.",
  computed: "Derived by the prototype from identified inputs.",
  assumed: "A what-if condition selected for analysis.",
  illustrative: "Visual explanation without an observed physical time series.",
  mock: "Fallback demonstration data, not a real-world result.",
};

export interface ScenarioStatusLegendProps {
  items?: ScenarioStatusItem[];
  compact?: boolean;
}

const defaultItems: ScenarioStatusItem[] = [
  { status: "observed" },
  { status: "published_model" },
  { status: "computed" },
  { status: "assumed" },
  { status: "illustrative" },
  { status: "mock" },
];

export function ScenarioStatusLegend({
  items = defaultItems,
  compact = false,
}: ScenarioStatusLegendProps) {
  return (
    <section className={`history-legend${compact ? " history-legend--compact" : ""}`} aria-label="Evidence status legend">
      {items.map((item) => (
        <div className="history-legend__item" key={`${item.status}-${item.label ?? ""}`}>
          <span className={`history-legend__swatch history-legend__swatch--${item.status}`} />
          <span>
            <strong>{item.label ?? defaultLabels[item.status]}</strong>
            {!compact ? <small>{item.description ?? defaultDescriptions[item.status]}</small> : null}
          </span>
        </div>
      ))}
    </section>
  );
}

