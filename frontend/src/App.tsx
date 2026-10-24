import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { SceneObject } from './map';
import { StreetScene3D, type CameraPreset, type StreetWater } from './street3d';
import { loadHistoricalExperience } from './data/loadHistoricalExperience';
import type { HistoricalExperienceDataset, HistoricalRoadEvent, RankingRow } from './domain/contracts';
import type { ExplainedRanking } from './data/personOneRanking';
import type { Geometry, Position } from 'geojson';

// Cesium is large; load it only when the city overview is first opened.
const CesiumScene = lazy(() => import('./map/CesiumScene'));

type ViewMode = 'overview' | 'replay' | 'engineering';
type Stage = 'street' | 'city';

const STREET_SCENE_MANIFEST = '/scene/morrissey/manifest.json';
const FEET_TO_M = 0.3048;
/** Nominal harbour surface when no event is selected (display only). */
const NOMINAL_HARBOUR_M = 0;
/** Replay speeds: real seconds per observed gauge hour. */
const REPLAY_SPEEDS = [4, 1, 0.25] as const;
const REPLAY_TICK_MS = 50;

// The 3D concept preview focuses on the central shoreline stretch investigated in the original demo
// (where the 2018 footprints cross the boulevard). Display clip only; the concept data is unchanged.
const CONCEPT_FOCUS_LAT: [number, number] = [42.3068, 42.315];

function clipLineToLat(line: Position[], [lo, hi]: [number, number]): Position[][] {
  const out: Position[][] = [];
  let current: Position[] = [];
  const inside = (p: Position) => p[1] >= lo && p[1] <= hi;
  const cross = (a: Position, b: Position, lat: number): Position => {
    const t = (lat - a[1]) / (b[1] - a[1]);
    return [a[0] + (b[0] - a[0]) * t, lat];
  };
  line.forEach((point, i) => {
    const prev = line[i - 1];
    if (prev && inside(prev) !== inside(point)) {
      current.push(cross(prev, point, inside(prev) ? (point[1] > hi ? hi : lo) : (prev[1] > hi ? hi : lo)));
      if (inside(prev)) { out.push(current); current = []; }
    } else if (prev && !inside(prev) && !inside(point) && (prev[1] - lo) * (point[1] - lo) < 0 && (prev[1] - hi) * (point[1] - hi) < 0) {
      out.push([cross(prev, point, lo), cross(prev, point, hi)]);
    }
    if (inside(point)) current.push(point);
  });
  if (current.length) out.push(current);
  return out.filter((part) => part.length > 1);
}

function focusConceptGeometry<T extends { geometry?: Geometry }>(concept: T): T {
  if (!concept.geometry) return concept;
  const lines = concept.geometry.type === 'LineString' ? [concept.geometry.coordinates]
    : concept.geometry.type === 'MultiLineString' ? concept.geometry.coordinates : null;
  if (!lines) return concept;
  const clipped = lines.flatMap((line) => clipLineToLat(line, CONCEPT_FOCUS_LAT));
  return clipped.length ? { ...concept, geometry: { type: 'MultiLineString', coordinates: clipped } } : concept;
}

const sceneObjects: SceneObject[] = [
  {
    id: 'bfd-engine-17',
    label: 'Boston Fire Engine 17 / Ladder 7',
    position: [-71.0616017, 42.3077286, 12],
    kind: 'fire_station',
    provenance: 'official',
    sourceUrl: 'https://gisportal.boston.gov/arcgis/rest/services/PublicSafety/OpenData/MapServer/2',
  },
  {
    id: 'illustrative-response-vehicle',
    label: 'Response vehicle',
    position: [-71.045392, 42.309184, 4],
    kind: 'vehicle',
    provenance: 'illustrative',
  },
  {
    id: 'investigation-site',
    label: 'Road investigation point',
    position: [-71.047246, 42.305291, 6],
    kind: 'site_marker',
    provenance: 'illustrative',
  },
];

function Badge({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'observed' | 'mock' | 'illustrative' }) {
  return <span className={`simple-badge badge-${tone}`}>{children}</span>;
}


function RoadRanking({
  rows,
  selectedId,
  onSelect,
}: {
  rows: ExplainedRanking[];
  selectedId?: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="simple-list">
      {rows.map((row) => (
        <button
          key={row.corridor_id}
          className={`simple-road ${row.corridor_id === selectedId ? 'is-active' : ''
            }`}
          onClick={() => onSelect(row.corridor_id)}
        >
          <span className="simple-rank">
            #{row.priority_rank}
          </span>

          <span>
            <strong>{row.label}</strong>
            <small>
              {row.impact_value}/100 · Priority score
            </small>
          </span>

          <Badge tone="mock">Estimated</Badge>
        </button>
      ))}
    </div>
  );
}


function RankingReasoning({
  road,
}: {
  road: ExplainedRanking;
}) {
  return (
    <section className="event-detail">
      <Badge tone="mock">Illustrative ranking</Badge>

      <h2>Why is this road ranked #{road.priority_rank}?</h2>
      <h3>{road.label}</h3>

      <div className="replay-time">
        <span>Priority score</span>
        <strong>{road.impact_value}/100</strong>
      </div>

      <h3>Ranking breakdown</h3>

      <dl>
        <div>
          <dt>Flood history</dt>
          <dd>{road.score_breakdown.flood}/30</dd>
        </div>
        <div>
          <dt>Critical access</dt>
          <dd>{road.score_breakdown.access}/45</dd>
        </div>
        <div>
          <dt>Property exposure</dt>
          <dd>{road.score_breakdown.property}/25</dd>
        </div>
      </dl>

      <h3>Why this priority?</h3>

      <ul>
        <li>
          <strong>Historical flooding: </strong>
          {road.explanation.flood}
        </li>

        <li>
          <strong>Community and public-service access: </strong>
          {road.explanation.access}
        </li>

        <li>
          <strong>Property and infrastructure exposure: </strong>
          {road.explanation.property}
        </li>
      </ul>

      <small className="plain-warning">
        Historical flood overlaps use USGS evidence.
        Critical-access and property-exposure scores
        are hardcoded planning assumptions, not
        verified damage or travel-time estimates.
      </small>
    </section>
  );
}


function FloodEventList({ events, selectedId, onSelect }: { events: HistoricalRoadEvent[]; selectedId?: string; onSelect: (id: string) => void }) {
  if (!events.length) return <div className="empty-evidence"><strong>No documented footprint overlap</strong><span>No loaded historical event footprint intersects this fixture road.</span></div>;
  return (
    <div className="event-list">
      {events.map((event) => (
        <button key={event.event_id} className={event.event_id === selectedId ? 'is-active' : ''} onClick={() => onSelect(event.event_id)}>
          <span className="event-date">{event.date_label}</span>
          <strong>{event.label}</strong>
          <small>USGS estimated peak footprint · NOAA gauge record</small>
        </button>
      ))}
    </div>
  );
}

function GaugeSparkline({ event, index }: { event: HistoricalRoadEvent; index: number }) {
  const values = event.gauge.observations.map((item) => item.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 290;
  const height = 72;
  const points = values.map((value, pointIndex) => {
    const x = values.length < 2 ? 0 : pointIndex / (values.length - 1) * width;
    const y = height - ((value - min) / Math.max(max - min, 0.001)) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(' ');
  const markerX = values.length < 2 ? 0 : index / (values.length - 1) * width;
  return (
    <div className="gauge-chart">
      <div><span>NOAA Boston 8443970</span><strong>{event.gauge.datum} · {event.gauge.unit}</strong></div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Observed Boston Harbor water level series">
        <polyline points={points} />
        <line x1={markerX} x2={markerX} y1="0" y2={height} />
      </svg>
      <small>Observed harbor gauge level—not water depth on Morrissey Boulevard.</small>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<HistoricalExperienceDataset>();
  const [error, setError] = useState<string>();
  const [selectedCorridorId, setSelectedCorridorId] = useState<string>();
  const [selectedEventId, setSelectedEventId] = useState<string>();
  const [viewMode, setViewMode] = useState<ViewMode>('overview');
  const [playing, setPlaying] = useState(false);
  const [secondsPerHour, setSecondsPerHour] = useState<(typeof REPLAY_SPEEDS)[number]>(REPLAY_SPEEDS[0]);
  const hoursInSeries = useRef(84);
  const [timelineProgress, setTimelineProgress] = useState(0);
  const [showConcept, setShowConcept] = useState(false);
  const [stage, setStage] = useState<Stage>('street');
  // Each stage mounts on first use and then stays mounted (hidden), so WebGL contexts are not torn down on every switch.
  const [visited, setVisited] = useState<Record<Stage, boolean>>({ street: true, city: false });
  useEffect(() => { setVisited((current) => (current[stage] ? current : { ...current, [stage]: true })); }, [stage]);
  const [cameraRequest, setCameraRequest] = useState<{ preset: CameraPreset; nonce: number }>({ preset: 'corridor', nonce: 0 });
  const requestCamera = (preset: CameraPreset) => setCameraRequest({ preset, nonce: Date.now() });

  useEffect(() => {
    void loadHistoricalExperience()
      .then((loaded) => {
        setData(loaded);
        setSelectedCorridorId(loaded.ranking.ranking[0]?.corridor_id);
        const replayEvent = new URLSearchParams(window.location.search).get('replay');
        const matchingEvent = loaded.events.find((event) => event.event_id === replayEvent);
        if (matchingEvent) {
          setSelectedEventId(matchingEvent.event_id);
          setViewMode('replay');
          setTimelineProgress(0.62);
        }
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setTimelineProgress((progress) => {
        // One observed hour takes `secondsPerHour` of real time.
        const step = REPLAY_TICK_MS / 1000 / secondsPerHour / Math.max(hoursInSeries.current - 1, 1);
        const next = Math.min(progress + step, 1);
        if (next >= 1) setPlaying(false);
        return next;
      });
    }, REPLAY_TICK_MS);
    return () => window.clearInterval(timer);
  }, [playing, secondsPerHour]);

  const selectedRoad = data?.ranking.ranking.find((road) => road.corridor_id === selectedCorridorId) ?? data?.ranking.ranking[0];
  const relevantEvents = useMemo(() => {
    if (!data || !selectedRoad) return [];
    return data.events.filter((event) => selectedRoad.road_ids.some((roadId) => event.affected_road_ids.includes(roadId)));
  }, [data, selectedRoad]);
  const selectedEvent = relevantEvents.find((event) => event.event_id === selectedEventId);
  const observationCount = selectedEvent?.gauge.observations.length ?? 0;
  if (observationCount) hoursInSeries.current = observationCount;
  // Timeline position in observed hours; the readout shows the nearest hourly observation.
  const hourPosition = timelineProgress * Math.max(observationCount - 1, 0);
  const observationIndex = selectedEvent ? Math.min(Math.round(hourPosition), observationCount - 1) : 0;
  const observation = selectedEvent?.gauge.observations[observationIndex];
  // Display only: linear interpolation between adjacent hourly observations so the water glides.
  const interpolatedGaugeM = (() => {
    if (!selectedEvent || !observationCount) return null;
    const i = Math.min(Math.floor(hourPosition), observationCount - 1);
    const j = Math.min(i + 1, observationCount - 1);
    const t = hourPosition - i;
    const list = selectedEvent.gauge.observations;
    return list[i].value * (1 - t) + list[j].value * t;
  })();
  const gaugeValues = selectedEvent?.gauge.observations.map((item) => item.value) ?? [];
  const normalizedGauge = observation && gaugeValues.length
    ? (observation.value - Math.min(...gaugeValues)) / Math.max(Math.max(...gaugeValues) - Math.min(...gaugeValues), 0.001)
    : 1;

  const peakSurfaceM = useMemo(() => {
    const values = (selectedEvent?.footprint.features ?? [])
      .map((feature) => Number((feature.properties as Record<string, unknown> | null)?.peak_wse_ft_navd88))
      .filter((value) => Number.isFinite(value));
    return values.length ? Math.max(...values) * FEET_TO_M : null;
  }, [selectedEvent]);

  const inReplay = viewMode !== 'overview' && Boolean(selectedEvent);

  // Stable object identities: the replay timer re-renders every 100 ms, and the 3D scene
  // must not rebuild geometry, water masks or traffic state on each tick.
  const roadFeatures = useMemo(() => (data ? {
    ...data.roads,
    features: data.roads.features.map((road) => ({
      ...road,
      properties: {
        ...road.properties,
        exposure: selectedEvent?.affected_road_ids.includes(road.properties.road_id) ? 'exposed' as const : 'not_exposed' as const,
      },
    })),
  } : null), [data, selectedEvent]);
  const streetRoads = useMemo(() => (data && roadFeatures && selectedRoad ? {
    graphVersion: data.graph_version,
    data: roadFeatures,
    roadIdProperty: 'road_id',
    exposedRoadIds: selectedEvent?.affected_road_ids ?? [],
    selectedRoadIds: selectedRoad.road_ids,
  } : null), [data, roadFeatures, selectedEvent, selectedRoad]);
  const streetFlood = useMemo(() => (selectedEvent ? {
    scenarioId: selectedEvent.event_id,
    label: selectedEvent.label,
    data: selectedEvent.footprint,
    status: 'observed' as const,
    sourceUrl: selectedEvent.source_url,
    sourceLabel: 'USGS estimated peak',
    limitations: selectedEvent.limitations,
  } : null), [selectedEvent]);
  const focusedConcept = useMemo(() => (data ? focusConceptGeometry(data.concept) : null), [data]);
  const conceptList = useMemo(() => (focusedConcept && showConcept ? [focusedConcept] : []), [focusedConcept, showConcept]);

  // The 3D water surface: sourced footprint; level is the USGS reported peak WSE,
  // or during replay the observed NOAA harbour level capped at that peak (illustrative).
  const displayedLevelM = inReplay && interpolatedGaugeM != null
    ? Math.min(interpolatedGaugeM, peakSurfaceM ?? interpolatedGaugeM)
    : peakSurfaceM;
  const streetWater = useMemo<StreetWater>(() => (!streetFlood
    ? { flood: null, peakSurfaceM: null, displayedLevelM: null, harbourLevelM: NOMINAL_HARBOUR_M, mode: 'none' }
    : {
      flood: streetFlood,
      peakSurfaceM,
      displayedLevelM,
      harbourLevelM: NOMINAL_HARBOUR_M,
      mode: inReplay ? 'gauge_replay' : 'peak',
    }), [streetFlood, peakSurfaceM, displayedLevelM, inReplay]);

  if (error) return <main className="simple-loading"><strong>Historical scene could not load</strong><span>{error}</span></main>;
  if (!data || !selectedRoad || !roadFeatures || !streetRoads) return <main className="simple-loading"><strong>Loading historical flood evidence…</strong></main>;

  const chooseRoad = (corridorId: string) => {
    setSelectedCorridorId(corridorId);
    setSelectedEventId(undefined);
    setViewMode('overview');
    setPlaying(false);
    setTimelineProgress(0);
    setShowConcept(false);
    requestCamera('corridor');
  };

  const startReplay = () => {
    setViewMode('replay');
    setTimelineProgress(0);
    setPlaying(true);
    setShowConcept(false);
    setStage('street');
    requestCamera('corridor');
  };

  const jumpToPeak = () => {
    if (!selectedEvent) return;
    const values = selectedEvent.gauge.observations.map((item) => item.value);
    const peakIndex = values.indexOf(Math.max(...values));
    setPlaying(false);
    setTimelineProgress(peakIndex / Math.max(values.length - 1, 1));
  };

  return (
    <div className="historical-app">
      <header className="simple-header">
        <a href="#top" className="simple-brand"><span>FR</span><div><strong>FloodRoute</strong><small>Historical road investigation</small></div></a>
        <div className="stage-toggle" role="tablist" aria-label="View">
          <button role="tab" aria-selected={stage === 'street'} className={stage === 'street' ? 'is-active' : ''} onClick={() => setStage('street')}><i />3D street scene</button>
          <button role="tab" aria-selected={stage === 'city'} className={stage === 'city' ? 'is-active' : ''} onClick={() => setStage('city')}>City overview</button>
          <span>{viewMode === 'overview' ? (selectedEvent ? 'Event peak extent' : 'Baseline') : viewMode === 'replay' ? 'Evidence replay' : 'Road investigation'}</span>
        </div>
        <p>Planning prototype · not emergency navigation</p>
      </header>

      <main className="simple-workspace" id="top">
        <aside className="simple-sidebar">
          <section>
            <header><div><span>1</span><h2>Ranked roads</h2></div><Badge tone="mock">Person 1 fixture</Badge></header>
            <p>Select a road to inspect documented past flood evidence.</p>
            <RoadRanking
              rows={data.ranking.ranking as ExplainedRanking[]}
              selectedId={selectedRoad.corridor_id}
              onSelect={chooseRoad}
            />
          </section>
          <section>
            <header><div><span>2</span><h2>Past floods</h2></div><Badge tone="observed">USGS + NOAA</Badge></header>
            <p>Events whose estimated peak footprint intersects the selected fixture road.</p>
            <FloodEventList events={relevantEvents} selectedId={selectedEventId} onSelect={(eventId) => {
              setSelectedEventId(eventId);
              setViewMode('overview');
              setTimelineProgress(0);
              setPlaying(false);
              setShowConcept(false);
              requestCamera('corridor');
            }} />
          </section>
        </aside>

        <section className={`simple-map-stage stage-${stage}`}>
          <div className="simple-map-title">
            <Badge tone={inReplay ? 'observed' : 'muted'}>{inReplay ? 'Observed event evidence' : 'Boston overview'}</Badge>
            <h1>{inReplay && selectedEvent ? selectedEvent.label : selectedRoad.label}</h1>
            <p>{inReplay ? 'Street investigation · peak footprint with observed harbor gauge context' : selectedEvent ? 'USGS estimated peak extent at its reported water-surface elevation' : 'Choose a past flood, then replay it in 3D.'}</p>
          </div>
          {visited.street ? (
            <div className="stage-pane" hidden={stage !== 'street'}>
              <StreetScene3D
                active={stage === 'street'}
                className="historical-street"
                manifestUrl={STREET_SCENE_MANIFEST}
                roads={streetRoads}
                selectedRoadIds={selectedRoad.road_ids}
                corridorLabel={`#${selectedRoad.priority_rank} ${selectedRoad.label}`}
                water={streetWater}
                interventions={conceptList}
                selectedInterventionId={showConcept ? data.concept.intervention_id : null}
                sceneObjects={sceneObjects}
                cameraRequest={cameraRequest}
                onOutsideCoverage={() => setStage('city')}
              />
            </div>
          ) : null}
          {visited.city ? (
            <div className="stage-pane" hidden={stage !== 'city'}>
              <Suspense fallback={<div className="street3d-loading"><strong>Loading city overview…</strong></div>}>
                <CesiumScene
                  className="historical-map"
                  viewMode={inReplay ? 'investigation' : 'overview'}
                  replayProgress={inReplay ? normalizedGauge : 0}
                  flood={selectedEvent ? {
                    scenarioId: selectedEvent.event_id,
                    label: selectedEvent.label,
                    data: selectedEvent.footprint,
                    status: 'observed',
                    sourceUrl: selectedEvent.source_url,
                    sourceLabel: 'U.S. Geological Survey',
                    limitations: selectedEvent.limitations,
                  } : null}
                  roads={{
                    graphVersion: data.graph_version,
                    data: roadFeatures,
                    roadIdProperty: 'road_id',
                    exposedRoadIds: selectedEvent?.affected_road_ids ?? [],
                    selectedRoadIds: selectedRoad.road_ids,
                    selectedRoadId: null,
                    focusSelected: true,
                  }}
                  buildings={{
                    data: data.buildings,
                    status: 'official',
                    heightProperty: 'BUILDING_HEIGHT_2010',
                    heightUnits: 'feet',
                    sourceUrl: 'https://gisportal.boston.gov/arcgis/rest/services/Assessing/DOIT_buildings/MapServer/2',
                  }}
                  sceneObjects={inReplay ? sceneObjects : []}
                  interventions={conceptList}
                  selectedInterventionId={showConcept ? data.concept.intervention_id : null}
                  cesiumToken={import.meta.env.VITE_CESIUM_ION_TOKEN}
                />
              </Suspense>
            </div>
          ) : null}
          {inReplay ? <div className="simulation-label"><Badge tone="illustrative">Illustrative timeline</Badge><span>Water level follows the observed NOAA harbor gauge, capped at the USGS peak water-surface elevation. Inside the USGS peak footprint it spreads from the harbour only through ground below that level (connected fill); cut-off pockets appear at the reported peak. Not a hydrodynamic simulation.</span></div> : null}
        </section>

        <aside className="simple-detail">
          {!selectedEvent ? (
            <>
              <RankingReasoning
                road={selectedRoad as ExplainedRanking}
              />

              <div className="detail-empty">
                <span>←</span>
                <h2>Choose a past flood</h2>
                <p>Select January or March 2018 to view its flood evidence.</p>
              </div>
            </>

          ) : viewMode === 'overview' ? (
            <section className="event-detail">
              <Badge tone="observed">Observed-event evidence</Badge>
              <h2>{selectedEvent.date_label}</h2>
              <h3>{selectedEvent.label}</h3>
              <p>{selectedEvent.summary}</p>

              <dl>
                <div>
                  <dt>Road overlap</dt>
                  <dd>
                    {selectedEvent.affected_road_ids.length} fixture segments
                  </dd>
                </div>
                <div>
                  <dt>Footprint</dt>
                  <dd>Estimated peak</dd>
                </div>
                <div>
                  <dt>Road depth</dt>
                  <dd>Unknown</dd>
                </div>
              </dl>

              <a
                href={selectedEvent.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Open USGS source ↗
              </a>

              <button className="replay-button" onClick={startReplay}>
                <span>▶</span> Replay flood evidence
              </button>

              <small className="plain-warning">
                Replay means a camera transition plus observed gauge timeline
                and peak-footprint reveal. It is not measured street-level flow.
              </small>
            </section>
          ) : (
            <section className="replay-console">
              <header>
                <Badge tone="observed">
                  {selectedEvent.date_label}
                </Badge>

                <button
                  onClick={() => {
                    setViewMode('overview');
                    setPlaying(false);
                  }}
                >
                  Exit replay
                </button>
              </header>

              <div className="replay-time">
                <span>
                  {observation
                    ? new Date(observation.timestamp).toLocaleString([], {
                      month: 'short',
                      day: 'numeric',
                      hour: 'numeric',
                      minute: '2-digit',
                      timeZone: 'UTC',
                    })
                    : '—'}{' '}
                  UTC
                </span>

                <strong>
                  {observation?.value.toFixed(2) ?? '—'} m{' '}
                  <small>NAVD88</small>
                </strong>
              </div>

              <GaugeSparkline
                event={selectedEvent}
                index={observationIndex}
              />

              <input
                aria-label="Replay timeline"
                type="range"
                min="0"
                max="1"
                step="0.001"
                value={timelineProgress}
                onChange={(event) => {
                  setTimelineProgress(Number(event.target.value));
                  setPlaying(false);
                }}
              />

              <div className="replay-controls">
                <button onClick={() => setTimelineProgress(0)}>
                  ↺
                </button>

                <button
                  className="play-toggle"
                  onClick={() => setPlaying((value) => !value)}
                >
                  {playing
                    ? 'Pause'
                    : timelineProgress >= 1
                      ? 'Replay'
                      : 'Play'}
                </button>

                <button
                  onClick={jumpToPeak}
                  title="Jump to the highest observed gauge reading"
                >
                  Peak
                </button>

                <button
                  className="speed-toggle"
                  title="Replay speed (real seconds per observed hour)"
                  onClick={() =>
                    setSecondsPerHour(
                      (current) =>
                        REPLAY_SPEEDS[
                        (REPLAY_SPEEDS.indexOf(current) + 1) %
                        REPLAY_SPEEDS.length
                        ]
                    )
                  }
                >
                  1 h = {secondsPerHour} s
                </button>
              </div>

              <small className="replay-hours">
                Hour {Math.round(hourPosition) + 1} of {observationCount}
                {' '}· water level interpolated between hourly gauge
                readings (display only)
              </small>

              <div className="evidence-key">
                <div>
                  <i className="key-building" />
                  <span>
                    <strong>Buildings</strong> Official Boston footprints
                  </span>
                </div>

                <div>
                  <i className="key-water" />
                  <span>
                    <strong>Water</strong> USGS estimated peak extent
                  </span>
                </div>

                <div>
                  <i className="key-object" />
                  <span>
                    <strong>Objects</strong> Official facility or labeled prop
                  </span>
                </div>
              </div>

              <div className="replay-limit">
                <strong>What this supports</strong>
                <p>
                  Where the estimated event peak reached and how Boston
                  Harbor's gauge changed. It does not support local velocity,
                  direction, or road-depth claims.
                </p>
              </div>

              <div className="replay-camera">
                <button
                  onClick={() => {
                    setStage('street');
                    requestCamera('street');
                  }}
                >
                  Street-level view
                </button>

                <button
                  onClick={() => {
                    setStage('street');
                    requestCamera('corridor');
                  }}
                >
                  Corridor view
                </button>
              </div>

              <button
                className="engineering-button"
                onClick={() => setViewMode('engineering')}
              >
                Continue to road investigation →
              </button>

              {viewMode === 'engineering' ? (
                <div className="engineering-card">
                  <Badge tone={data.concept.geometry_status === 'schematic' ? 'illustrative' : 'observed'}>
                    {data.concept.geometry_status === 'schematic'
                      ? 'SCHEMATIC concept'
                      : data.concept.geometry_status === 'sourced_asset_location'
                        ? 'Existing road location · not a design'
                        : 'Concept'}
                  </Badge>

                  <h3>{data.concept.label}</h3>
                  <p>{data.investigation.summary}</p>

                  <button
                    onClick={() => {
                      const next = !showConcept;
                      setShowConcept(next);

                      if (next) {
                        setStage('street');
                        requestCamera('concept');
                      }
                    }}
                  >
                    {showConcept
                      ? 'Hide 3D concept'
                      : 'Preview 3D concept'}
                  </button>

                  <small>
                    The schematic asset does not change the historical
                    footprint or claim protection effectiveness.
                  </small>
                </div>
              ) : null}
            </section>
          )}
          {selectedEvent && (
            <details className="ranking-reasoning-details">
              <summary>
                Why is {selectedRoad.label} ranked #{selectedRoad.priority_rank}?
              </summary>

              <RankingReasoning
                road={selectedRoad as ExplainedRanking}
              />
            </details>
          )}

        </aside>
      </main>
    </div>
  );
}
