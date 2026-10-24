import type { GaugeSeries, TideObservation } from "./types";

export interface TideLevelChartProps {
  series?: GaugeSeries;
  locale?: string;
  height?: number;
}

const WIDTH = 620;
const PADDING = { top: 18, right: 18, bottom: 46, left: 54 };

function isUsableObservation(observation: TideObservation): boolean {
  return (
    Number.isFinite(observation.value) &&
    Number.isFinite(Date.parse(observation.timestamp))
  );
}

function formatTime(timestamp: number, locale?: string): string {
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function TideLevelChart({
  series,
  locale,
  height = 250,
}: TideLevelChartProps) {
  const observations = (series?.observations ?? [])
    .filter(isUsableObservation)
    .map((observation) => ({
      ...observation,
      epoch: Date.parse(observation.timestamp),
    }))
    .sort((left, right) => left.epoch - right.epoch);

  if (!series) {
    return (
      <section className="history-chart history-empty" aria-label="Tide observations">
        <strong>No gauge series selected</strong>
        <span>A chart appears only when sourced observations are supplied.</span>
      </section>
    );
  }

  if (observations.length === 0) {
    return (
      <section className="history-chart history-empty" aria-label="Tide observations">
        <strong>No valid observations available</strong>
        <span>Missing readings are not inferred or replaced with zero.</span>
      </section>
    );
  }

  const chartWidth = WIDTH - PADDING.left - PADDING.right;
  const chartHeight = height - PADDING.top - PADDING.bottom;
  const minTime = observations[0].epoch;
  const maxTime = observations[observations.length - 1].epoch;
  const values = observations.map((observation) => observation.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const valuePadding = Math.max((rawMax - rawMin) * 0.12, 0.05);
  const minValue = rawMin - valuePadding;
  const maxValue = rawMax + valuePadding;

  const x = (epoch: number) =>
    PADDING.left +
    (maxTime === minTime ? chartWidth / 2 : ((epoch - minTime) / (maxTime - minTime)) * chartWidth);
  const y = (value: number) =>
    PADDING.top + ((maxValue - value) / (maxValue - minValue)) * chartHeight;

  const path = observations
    .map((observation, index) =>
      `${index === 0 ? "M" : "L"}${x(observation.epoch).toFixed(1)},${y(
        observation.value,
      ).toFixed(1)}`,
    )
    .join(" ");
  const ticks = [maxValue, (maxValue + minValue) / 2, minValue];

  return (
    <section className="history-chart" aria-labelledby="history-chart-title">
      <div className="history-chart__heading">
        <div>
          <span className="history-kicker">Observed gauge context</span>
          <h3 id="history-chart-title">{series.parameterLabel}</h3>
        </div>
        <span className="history-status history-status--observed">Observed</span>
      </div>

      <p className="history-chart__metadata">
        {series.stationName} ({series.stationId}) · {series.unit} relative to {series.datum}
      </p>

      <div className="history-chart__scroll">
        <svg
          className="history-chart__svg"
          viewBox={`0 0 ${WIDTH} ${height}`}
          role="img"
          aria-label={`${series.parameterLabel} at ${series.stationName}, ${observations.length} timestamped observations`}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={PADDING.left}
                x2={WIDTH - PADDING.right}
                y1={y(tick)}
                y2={y(tick)}
                className="history-chart__grid"
              />
              <text x={PADDING.left - 9} y={y(tick) + 4} textAnchor="end">
                {tick.toFixed(2)}
              </text>
            </g>
          ))}
          <path d={path} className="history-chart__line" />
          {observations.map((observation) => (
            <circle
              key={`${observation.timestamp}-${observation.value}`}
              cx={x(observation.epoch)}
              cy={y(observation.value)}
              r="3.2"
              className="history-chart__point"
            >
              <title>
                {formatTime(observation.epoch, locale)}: {observation.value.toFixed(3)} {series.unit} ({observation.quality ?? "quality unknown"})
              </title>
            </circle>
          ))}
          <text x={PADDING.left} y={height - 13} textAnchor="start">
            {formatTime(minTime, locale)}
          </text>
          <text x={WIDTH - PADDING.right} y={height - 13} textAnchor="end">
            {formatTime(maxTime, locale)}
          </text>
        </svg>
      </div>

      <p className="history-chart__caveat">
        Station water level provides regional timing context. It is not street-level depth,
        direction, velocity, or a physical flood replay.
      </p>
    </section>
  );
}

