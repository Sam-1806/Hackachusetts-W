import {
  BoundingSphere,
  Cartesian2,
  Cartesian3,
  Color,
  ColorMaterialProperty,
  ConstantProperty,
  createOsmBuildingsAsync,
  createWorldTerrainAsync,
  EllipsoidTerrainProvider,
  GeoJsonDataSource as CesiumGeoJsonDataSource,
  GridImageryProvider,
  HeightReference,
  HeadingPitchRange,
  Ion,
  JulianDate,
  OpenStreetMapImageryProvider,
  PolylineDashMaterialProperty,
  PolylineOutlineMaterialProperty,
  ScreenSpaceEventType,
  type Entity as CesiumEntity,
  type Cesium3DTileset,
} from 'cesium';
import {
  BoxGraphics,
  CameraFlyTo,
  CylinderGraphics,
  CorridorGraphics,
  Entity,
  GeoJsonDataSource,
  ImageryLayer,
  LabelGraphics,
  PointGraphics,
  PolygonGraphics,
  PolylineGraphics,
  ScreenSpaceEvent,
  ScreenSpaceEventHandler,
  Viewer,
  useCesium,
} from 'resium';
import React, { Component, useEffect, useMemo, useState } from 'react';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import './map.css';

import type {
  BuildingMapLayer,
  ConceptIntervention,
  FloodMapLayer,
  MapGeometry,
  MapLayerVisibility,
  MapSelection,
  Position,
  RoadMapLayer,
  RouteMapLine,
  SceneObject,
} from './types';

const BOSTON_CAMERA = {
  destination: Cartesian3.fromDegrees(-71.048, 42.306, 7_800),
  orientation: { heading: 0.08, pitch: -0.72, roll: 0 },
};

const FLOOD_FILL = Color.fromCssColorString('#16b8cf').withAlpha(0.42);
const FLOOD_OUTLINE = Color.fromCssColorString('#67e8f9').withAlpha(0.9);
const ROAD_COLOR = Color.fromCssColorString('#a4b2c3').withAlpha(0.7);
const EXPOSED_COLOR = Color.fromCssColorString('#ff7a59').withAlpha(0.96);
const SELECTED_COLOR = Color.fromCssColorString('#ffd166');
const CONCEPT_COLOR = Color.fromCssColorString('#d87cff').withAlpha(0.9);
const VERIFIED_COLOR = Color.fromCssColorString('#69dfac').withAlpha(0.94);

type SceneStatus = 'local' | 'streaming' | 'ready' | 'degraded';

export interface CesiumSceneProps {
  flood?: FloodMapLayer | null;
  roads?: RoadMapLayer | null;
  buildings?: BuildingMapLayer | null;
  sceneObjects?: SceneObject[];
  routes?: RouteMapLine[];
  interventions?: ConceptIntervention[];
  selectedInterventionId?: string | null;
  cesiumToken?: string;
  className?: string;
  viewMode?: 'overview' | 'investigation';
  replayProgress?: number;
  initialVisibility?: Partial<MapLayerVisibility>;
  onSelection?: (selection: MapSelection) => void;
  onLayerVisibilityChange?: (visibility: MapLayerVisibility) => void;
  onSceneStatusChange?: (status: SceneStatus, detail: string) => void;
}

const DEFAULT_VISIBILITY: MapLayerVisibility = {
  flood: true,
  roads: true,
  routes: true,
  interventions: true,
  buildings: true,
};

function positionToCartesian(position: Position): Cartesian3 {
  return Cartesian3.fromDegrees(position[0], position[1], position[2] ?? 0);
}

function positionsToCartesian(positions: Position[]): Cartesian3[] {
  return positions.map(positionToCartesian);
}

function lineStrings(geometry?: MapGeometry): Position[][] {
  if (!geometry) return [];
  if (geometry.type === 'LineString') return [geometry.coordinates];
  if (geometry.type === 'MultiLineString') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') {
    return geometry.geometries.flatMap((child) => lineStrings(child));
  }
  return [];
}

function points(geometry?: MapGeometry): Position[] {
  if (!geometry) return [];
  if (geometry.type === 'Point') return [geometry.coordinates];
  if (geometry.type === 'MultiPoint') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') {
    return geometry.geometries.flatMap((child) => points(child));
  }
  return [];
}

function polygons(geometry?: MapGeometry): Position[][][] {
  if (!geometry) return [];
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') {
    return geometry.geometries.flatMap((child) => polygons(child));
  }
  return [];
}

function entityProperties(entity: CesiumEntity): Record<string, unknown> {
  return entity.properties?.getValue(JulianDate.now()) ?? {};
}

function SelectionBridge({ onSelection }: Pick<CesiumSceneProps, 'onSelection'>) {
  const { viewer } = useCesium();

  if (!onSelection) return null;

  return (
    <ScreenSpaceEventHandler>
      <ScreenSpaceEvent
        action={(movement) => {
          if (!viewer || !('position' in movement) || !movement.position) return;
          const picked = viewer.scene.pick(movement.position) as
            | { id?: CesiumEntity }
            | undefined;
          const entity = picked?.id;
          if (!entity) return;

          const values = entityProperties(entity);
          const interventionId = values.intervention_id;
          const roadId = values.road_id;
          if (typeof interventionId === 'string') {
            onSelection({ kind: 'intervention', id: interventionId });
          } else if (typeof roadId === 'string') {
            onSelection({ kind: 'road', id: roadId });
          }
        }}
        type={ScreenSpaceEventType.LEFT_CLICK}
      />
    </ScreenSpaceEventHandler>
  );
}

function TokenBackedSceneAssets({
  enabled,
  token,
  hasLocalBuildings,
  onStatus,
}: {
  enabled: boolean;
  token?: string;
  hasLocalBuildings: boolean;
  onStatus: (status: SceneStatus, detail: string) => void;
}) {
  const { viewer } = useCesium();

  useEffect(() => {
    if (!viewer) return;
    let cancelled = false;
    let buildings: Cesium3DTileset | undefined;

    if (!token) {
      viewer.terrainProvider = new EllipsoidTerrainProvider();
      onStatus('local', hasLocalBuildings
        ? 'Official Boston footprints extruded locally; streamed terrain is off.'
        : 'Token-free basemap active; Cesium terrain and 3D buildings are off.');
      return;
    }

    Ion.defaultAccessToken = token;
    onStatus('streaming', 'Connecting to Cesium terrain and OSM Buildings…');

    void Promise.allSettled([createWorldTerrainAsync(), enabled ? createOsmBuildingsAsync() : null]).then(
      ([terrainResult, buildingsResult]) => {
        if (cancelled) return;
        if (terrainResult.status === 'fulfilled') {
          viewer.terrainProvider = terrainResult.value;
        }
        if (buildingsResult.status === 'fulfilled' && buildingsResult.value) {
          buildings = buildingsResult.value;
          viewer.scene.primitives.add(buildings);
        }
        const terrainReady = terrainResult.status === 'fulfilled';
        const buildingsReady = !enabled || buildingsResult.status === 'fulfilled';
        const complete = terrainReady && buildingsReady;
        onStatus(
          complete ? 'ready' : 'degraded',
          complete
            ? enabled
              ? 'Cesium terrain and OSM Buildings loaded.'
              : 'Cesium terrain loaded; buildings are hidden.'
            : 'Some streamed 3D context failed; evidence overlays remain available.',
        );
      },
    );

    return () => {
      cancelled = true;
      if (buildings && !buildings.isDestroyed()) viewer.scene.primitives.remove(buildings);
    };
  }, [enabled, hasLocalBuildings, onStatus, token, viewer]);

  return null;
}

function CameraSelection({ intervention, viewMode, roadFocus }: {
  intervention?: ConceptIntervention;
  viewMode: 'overview' | 'investigation';
  roadFocus: boolean;
}) {
  const { viewer } = useCesium();

  useEffect(() => {
    if (!viewer) return;
    if (!intervention?.geometry) {
      if (roadFocus) return; // RoadLayerController frames the selected corridor.
      if (viewMode === 'overview') {
        viewer.camera.flyTo({ destination: BOSTON_CAMERA.destination, orientation: BOSTON_CAMERA.orientation, duration: 1.8 });
      } else {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(-71.0478, 42.309, 2_400),
          orientation: { heading: 0.28, pitch: -1.12, roll: 0 },
          duration: 1.8,
        });
      }
      return;
    }
    const candidate = points(intervention.geometry)[0]
      ?? lineStrings(intervention.geometry)[0]?.[0]
      ?? polygons(intervention.geometry)[0]?.[0]?.[0];
    if (!candidate) return;
    viewer.camera.flyToBoundingSphere(
      new BoundingSphere(Cartesian3.fromDegrees(candidate[0], candidate[1], 0), 50),
      { offset: new HeadingPitchRange(0.55, -0.45, 360), duration: 1.4 },
    );
  }, [intervention, viewMode, viewer, roadFocus]);

  return null;
}

function RoadLayerController({
  dataSource,
  layer,
}: {
  dataSource?: CesiumGeoJsonDataSource;
  layer?: RoadMapLayer | null;
}) {
  const { viewer } = useCesium();
  const selectedSignature = (layer?.selectedRoadIds ?? (layer?.selectedRoadId ? [layer.selectedRoadId] : [])).join('|');
  const layerSignature = layer
    ? [
        layer.graphVersion,
        layer.roadIdProperty ?? 'road_id',
        selectedSignature,
        ...(layer.exposedRoadIds ?? []),
      ].join('|')
    : '';

  useEffect(() => {
    if (!dataSource || !layer) return;
    styleRoadDataSource(dataSource, layer);
    viewer?.scene.requestRender();
  }, [dataSource, layerSignature, viewer]);

  // Fly to the selected corridor whenever the selection changes.
  useEffect(() => {
    if (!viewer || !dataSource || !layer?.focusSelected || !selectedSignature) return;
    const selected = new Set(selectedSignature.split('|'));
    const idProperty = layer.roadIdProperty ?? 'road_id';
    const now = JulianDate.now();
    const positions: Cartesian3[] = [];
    for (const entity of dataSource.entities.values) {
      const roadId = String(entityProperties(entity)[idProperty] ?? entity.id);
      if (!selected.has(roadId) || !entity.polyline?.positions) continue;
      positions.push(...(entity.polyline.positions.getValue(now) as Cartesian3[]));
    }
    if (!positions.length) return;
    const sphere = BoundingSphere.fromPoints(positions);
    viewer.camera.flyToBoundingSphere(sphere, {
      offset: new HeadingPitchRange(0.35, -0.62, sphere.radius * 3.2 + 500),
      duration: 1.6,
    });
  }, [dataSource, selectedSignature, viewer, layer?.focusSelected]);

  return null;
}

function styleFloodDataSource(dataSource: CesiumGeoJsonDataSource, replayProgress = 1) {
  const alpha = 0.08 + Math.max(0, Math.min(1, replayProgress)) * 0.42;
  for (const entity of dataSource.entities.values) {
    if (entity.polygon) {
      entity.polygon.material = new ColorMaterialProperty(FLOOD_FILL.withAlpha(alpha));
      entity.polygon.outline = new ConstantProperty(true);
      entity.polygon.outlineColor = new ConstantProperty(FLOOD_OUTLINE);
      entity.polygon.height = new ConstantProperty(1);
      entity.polygon.heightReference = new ConstantProperty(HeightReference.NONE);
    }
    if (entity.polyline) {
      entity.polyline.material = new ColorMaterialProperty(FLOOD_OUTLINE);
      entity.polyline.width = new ConstantProperty(2);
      entity.polyline.clampToGround = new ConstantProperty(true);
    }
  }
}

function FloodLayerController({ dataSource, replayProgress }: { dataSource?: CesiumGeoJsonDataSource; replayProgress: number }) {
  const { viewer } = useCesium();
  useEffect(() => {
    if (!dataSource) return;
    styleFloodDataSource(dataSource, replayProgress);
    viewer?.scene.requestRender();
  }, [dataSource, replayProgress, viewer]);
  return null;
}

function styleBuildingDataSource(dataSource: CesiumGeoJsonDataSource, layer: BuildingMapLayer) {
  const property = layer.heightProperty ?? 'BUILDING_HEIGHT_2010';
  const unitScale = layer.heightUnits === 'meters' ? 1 : 0.3048;
  for (const entity of dataSource.entities.values) {
    if (!entity.polygon) continue;
    const values = entityProperties(entity);
    const sourceHeight = Number(values[property]);
    const height = Number.isFinite(sourceHeight) && sourceHeight > 0 ? Math.min(sourceHeight * unitScale, 90) : 8;
    entity.polygon.material = new ColorMaterialProperty(Color.fromCssColorString('#6f8d96').withAlpha(0.96));
    entity.polygon.outline = new ConstantProperty(true);
    entity.polygon.outlineColor = new ConstantProperty(Color.fromCssColorString('#d2f5f1').withAlpha(0.75));
    entity.polygon.height = new ConstantProperty(0);
    entity.polygon.heightReference = new ConstantProperty(HeightReference.NONE);
    entity.polygon.extrudedHeight = new ConstantProperty(height);
    entity.polygon.extrudedHeightReference = new ConstantProperty(HeightReference.NONE);
  }
}

function BuildingLayerController({ dataSource, layer }: { dataSource?: CesiumGeoJsonDataSource; layer?: BuildingMapLayer | null }) {
  const { viewer } = useCesium();
  useEffect(() => {
    if (!dataSource || !layer) return;
    styleBuildingDataSource(dataSource, layer);
    viewer?.scene.requestRender();
  }, [dataSource, layer, viewer]);
  return null;
}

function styleRoadDataSource(dataSource: CesiumGeoJsonDataSource, layer: RoadMapLayer) {
  const exposed = new Set(layer.exposedRoadIds ?? []);
  const selectedIds = new Set(layer.selectedRoadIds ?? (layer.selectedRoadId ? [layer.selectedRoadId] : []));
  const idProperty = layer.roadIdProperty ?? 'road_id';
  for (const entity of dataSource.entities.values) {
    const values = entityProperties(entity);
    const roadId = String(values[idProperty] ?? entity.id);
    if (entity.properties && !entity.properties.hasProperty('road_id')) {
      entity.properties.addProperty('road_id', roadId);
    }
    if (!entity.polyline) continue;
    const selected = selectedIds.has(roadId);
    const isExposed = exposed.has(roadId);
    if (selected) {
      entity.polyline.material = new PolylineOutlineMaterialProperty({
        color: isExposed ? EXPOSED_COLOR : SELECTED_COLOR,
        outlineColor: Color.fromCssColorString('#2a1d05'),
        outlineWidth: 3,
      });
      entity.polyline.width = new ConstantProperty(13);
    } else {
      entity.polyline.material = new ColorMaterialProperty(isExposed ? EXPOSED_COLOR : ROAD_COLOR);
      entity.polyline.width = new ConstantProperty(isExposed ? 6 : 3);
    }
    entity.polyline.clampToGround = new ConstantProperty(true);
    entity.polyline.zIndex = new ConstantProperty(selected ? 10 : 1);
  }
}

function RouteEntities({ routes }: { routes: RouteMapLine[] }) {
  const styles: Record<RouteMapLine['kind'], { color: Color; width: number }> = {
    baseline: { color: Color.fromCssColorString('#71e5c1'), width: 4 },
    disrupted: { color: Color.fromCssColorString('#ff5c77'), width: 6 },
    counterfactual: { color: Color.fromCssColorString('#ffd166'), width: 5 },
  };

  return routes.map((route) => (
    <Entity key={route.routeId} name={route.label} properties={{ route_id: route.routeId }}>
      <PolylineGraphics
        positions={positionsToCartesian(route.coordinates)}
        width={styles[route.kind].width}
        material={styles[route.kind].color}
        clampToGround
      />
    </Entity>
  ));
}

function InterventionEntities({ interventions }: { interventions: ConceptIntervention[] }) {
  return interventions.flatMap((intervention) => {
    const color = intervention.status === 'verified' ? VERIFIED_COLOR : CONCEPT_COLOR;
    const schematic = intervention.geometry_status === 'schematic';
    const common = {
      intervention_id: intervention.intervention_id,
      geometry_status: intervention.geometry_status,
    };
    const label = intervention.label ?? intervention.intervention_type.replaceAll('_', ' ');
    const result: React.ReactElement[] = [];

    points(intervention.geometry).forEach((position, index) => {
      result.push(
        <Entity
          key={`${intervention.intervention_id}-point-${index}`}
          position={positionToCartesian(position)}
          name={label}
          properties={common}
        >
          <PointGraphics color={color} pixelSize={schematic ? 13 : 10} outlineColor={Color.WHITE} outlineWidth={2} />
          <LabelGraphics
            text={`${schematic ? 'SCHEMATIC · ' : ''}${label}`}
            font="12px Inter, system-ui, sans-serif"
            fillColor={Color.WHITE}
            outlineColor={Color.BLACK.withAlpha(0.75)}
            outlineWidth={3}
            pixelOffset={new Cartesian2(0, -24)}
          />
        </Entity>,
      );
    });

    lineStrings(intervention.geometry).forEach((coordinates, index) => {
      const hasSourcedVolume =
        intervention.geometry_status !== 'schematic' &&
        intervention.visual_parameters?.footprint_width_m != null &&
        intervention.visual_parameters?.conceptual_height_m != null;
      result.push(
        <Entity
          key={`${intervention.intervention_id}-line-${index}`}
          name={`${schematic ? 'Schematic ' : ''}${label}`}
          description="Concept preview only. Protection outcome is not hydraulically modeled."
          properties={common}
        >
          {hasSourcedVolume ? (
            <CorridorGraphics
              positions={positionsToCartesian(coordinates)}
              width={intervention.visual_parameters?.footprint_width_m}
              height={intervention.visual_parameters?.conceptual_height_m}
              heightReference={HeightReference.RELATIVE_TO_GROUND}
              extrudedHeight={0}
              extrudedHeightReference={HeightReference.RELATIVE_TO_GROUND}
              material={color.withAlpha(0.68)}
              outline
              outlineColor={color}
            />
          ) : null}
          <PolylineGraphics
            positions={positionsToCartesian(coordinates)}
            width={schematic ? 8 : 6}
            material={
              schematic
                ? new PolylineDashMaterialProperty({ color, dashLength: 14 })
                : color
            }
            clampToGround={!hasSourcedVolume}
          />
        </Entity>,
      );
    });

    polygons(intervention.geometry).forEach((rings, index) => {
      const exterior = rings[0];
      if (!exterior) return;
      const explicitHeight = intervention.visual_parameters?.conceptual_height_m;
      result.push(
        <Entity
          key={`${intervention.intervention_id}-polygon-${index}`}
          name={`${schematic ? 'Schematic ' : ''}${label}`}
          properties={common}
        >
          <PolygonGraphics
            hierarchy={positionsToCartesian(exterior)}
            material={color.withAlpha(0.46)}
            outline
            outlineColor={color}
            height={explicitHeight}
            heightReference={HeightReference.NONE}
            extrudedHeight={explicitHeight == null ? undefined : 0}
            extrudedHeightReference={HeightReference.RELATIVE_TO_GROUND}
          />
        </Entity>,
      );
    });

    return result;
  });
}

function SceneObjectEntities({ objects }: { objects: SceneObject[] }) {
  return objects.map((object) => {
    const official = object.provenance === 'official';
    const color = official ? Color.fromCssColorString('#57dccb') : Color.fromCssColorString('#ffb45e');
    const position = Cartesian3.fromDegrees(object.position[0], object.position[1], object.position[2]);
    return (
      <Entity
        key={object.id}
        name={object.label}
        position={position}
        description={`${official ? 'Official geographic feature' : 'Illustrative scene prop'}${object.sourceUrl ? ` · ${object.sourceUrl}` : ''}`}
      >
        {object.kind === 'vehicle' ? (
          <BoxGraphics
            dimensions={new Cartesian3(5.2, 2.2, 1.8)}
            material={color.withAlpha(0.92)}
            outline
            outlineColor={Color.WHITE.withAlpha(0.7)}
            heightReference={HeightReference.NONE}
          />
        ) : (
          <CylinderGraphics
            length={object.kind === 'fire_station' ? 14 : 5}
            topRadius={object.kind === 'fire_station' ? 4 : 1.2}
            bottomRadius={object.kind === 'fire_station' ? 4 : 1.2}
            material={color.withAlpha(0.86)}
            outline
            outlineColor={Color.WHITE.withAlpha(0.7)}
            heightReference={HeightReference.RELATIVE_TO_GROUND}
          />
        )}
        <LabelGraphics
          text={`${official ? '' : 'ILLUSTRATIVE · '}${object.label}`}
          font="11px Inter, system-ui, sans-serif"
          fillColor={Color.WHITE}
          outlineColor={Color.BLACK.withAlpha(0.9)}
          outlineWidth={3}
          pixelOffset={new Cartesian2(0, -28)}
        />
      </Entity>
    );
  });
}

class SceneErrorBoundary extends Component<
  { children: React.ReactNode },
  { error?: Error }
> {
  state: { error?: Error } = {};

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="map-fallback" role="alert">
          <strong>3D scene unavailable</strong>
          <span>The evidence panels can still be used. Check WebGL support and reload the page.</span>
          <code>{this.state.error.message}</code>
        </div>
      );
    }
    return this.props.children;
  }
}

export function CesiumScene({
  flood,
  roads,
  buildings,
  sceneObjects = [],
  routes = [],
  interventions = [],
  selectedInterventionId,
  cesiumToken,
  className,
  viewMode = 'overview',
  replayProgress = 1,
  initialVisibility,
  onSelection,
  onLayerVisibilityChange,
  onSceneStatusChange,
}: CesiumSceneProps) {
  const [visibility, setVisibility] = useState<MapLayerVisibility>({
    ...DEFAULT_VISIBILITY,
    buildings: Boolean(cesiumToken || buildings),
    ...initialVisibility,
  });
  const [sceneStatus, setSceneStatus] = useState<{ state: SceneStatus; detail: string }>({
    state: cesiumToken ? 'streaming' : 'local',
    detail: cesiumToken
      ? 'Preparing streamed 3D context…'
      : buildings
        ? 'Local Boston building footprints active; streamed terrain is optional.'
        : 'Token-free basemap active; terrain and buildings are optional.',
  });
  const [roadDataSource, setRoadDataSource] = useState<CesiumGeoJsonDataSource>();
  const [floodDataSource, setFloodDataSource] = useState<CesiumGeoJsonDataSource>();
  const [buildingDataSource, setBuildingDataSource] = useState<CesiumGeoJsonDataSource>();
  const imageryProvider = useMemo(
    () =>
      new OpenStreetMapImageryProvider({
        url: 'https://tile.openstreetmap.org/',
        credit: '© OpenStreetMap contributors',
      }),
    [],
  );
  const fallbackImageryProvider = useMemo(
    () => new GridImageryProvider({
      color: Color.fromCssColorString('#21404a').withAlpha(0.45),
      glowColor: Color.fromCssColorString('#071820'),
      backgroundColor: Color.fromCssColorString('#0a1c24'),
      cells: 8,
    }),
    [],
  );
  const selectedIntervention = interventions.find(
    (item) => item.intervention_id === selectedInterventionId,
  );
  const availableControls = (Object.keys(visibility) as Array<keyof MapLayerVisibility>).filter((key) => {
    if (key === 'routes') return routes.length > 0;
    if (key === 'interventions') return interventions.length > 0;
    if (key === 'flood') return Boolean(flood);
    if (key === 'roads') return Boolean(roads);
    if (key === 'buildings') return Boolean(cesiumToken || buildings);
    return true;
  });

  const updateStatus = React.useCallback(
    (state: SceneStatus, detail: string) => {
      setSceneStatus({ state, detail });
      onSceneStatusChange?.(state, detail);
    },
    [onSceneStatusChange],
  );

  const toggle = (key: keyof MapLayerVisibility) => {
    setVisibility((current) => {
      const next = { ...current, [key]: !current[key] };
      onLayerVisibilityChange?.(next);
      return next;
    });
  };

  return (
    <SceneErrorBoundary>
      <section className={`cesium-scene ${className ?? ''}`} aria-label="3D Boston flood evidence map">
        <Viewer
          full
          baseLayer={false}
          animation={false}
          timeline={false}
          geocoder={false}
          homeButton={false}
          sceneModePicker={false}
          baseLayerPicker={false}
          navigationHelpButton={false}
          fullscreenButton={false}
          selectionIndicator
          infoBox={false}
          requestRenderMode
          maximumRenderTimeChange={Number.POSITIVE_INFINITY}
        >
          <ImageryLayer imageryProvider={fallbackImageryProvider} />
          <ImageryLayer imageryProvider={imageryProvider} />
          {viewMode === 'overview' ? <CameraFlyTo {...BOSTON_CAMERA} duration={0} once /> : null}
          <TokenBackedSceneAssets
            enabled={visibility.buildings && !buildings}
            token={cesiumToken}
            hasLocalBuildings={Boolean(buildings)}
            onStatus={updateStatus}
          />
          <CameraSelection intervention={selectedIntervention} viewMode={viewMode} roadFocus={Boolean(roads?.focusSelected)} />
          <FloodLayerController dataSource={floodDataSource} replayProgress={replayProgress} />
          <BuildingLayerController dataSource={buildingDataSource} layer={buildings} />
          <RoadLayerController dataSource={roadDataSource} layer={roads} />
          <SelectionBridge onSelection={onSelection} />

          {visibility.flood && flood ? (
            <GeoJsonDataSource
              name={`${flood.label} · ${flood.status}`}
              data={flood.data}
              clampToGround={false}
              onLoad={setFloodDataSource}
            />
          ) : null}

          {visibility.buildings && buildings && !cesiumToken ? (
            <GeoJsonDataSource
              name={`Boston buildings · ${buildings.status}`}
              data={buildings.data}
              clampToGround={false}
              onLoad={setBuildingDataSource}
            />
          ) : null}

          {visibility.roads && roads ? (
            <GeoJsonDataSource
              name={`Road evidence · ${roads.graphVersion}`}
              data={roads.data}
              clampToGround
              onLoad={setRoadDataSource}
            />
          ) : null}

          {visibility.routes ? <RouteEntities routes={routes} /> : null}
          {visibility.interventions ? (
            <InterventionEntities interventions={interventions} />
          ) : null}
          <SceneObjectEntities objects={sceneObjects} />
        </Viewer>

        <div className="map-layer-controls" aria-label="Map layers">
          {availableControls.map((key) => (
            <button
              key={key}
              type="button"
              className={visibility[key] ? 'is-active' : ''}
              aria-pressed={visibility[key]}
              onClick={() => toggle(key)}
              disabled={key === 'buildings' && !cesiumToken && !buildings}
              title={key === 'buildings' && !cesiumToken && !buildings ? 'Add a Cesium ion token to stream buildings' : undefined}
            >
              <span aria-hidden="true" />
              {key}
            </button>
          ))}
        </div>

        <div className={`map-stream-status status-${sceneStatus.state}`} role="status">
          <span aria-hidden="true" />
          <div>
            <strong>{sceneStatus.state === 'ready' ? '3D context ready' : 'Map evidence ready'}</strong>
            <small>{sceneStatus.detail}</small>
          </div>
        </div>

        <div className="map-legend" aria-label="Map legend">
          {flood ? <span><i className="legend-flood" /> Observed-event peak footprint</span> : null}
          {roads ? <span><i className="legend-road" /> Selected corridor (bold) / footprint-overlap road</span> : null}
          {interventions.length ? <span><i className="legend-concept" /> Schematic concept</span> : null}
          <small>{viewMode === 'investigation' ? 'Gauge-driven reveal is illustrative; the mapped footprint is a sourced event peak.' : 'Select a documented event to begin the 3D investigation.'}</small>
        </div>
      </section>
    </SceneErrorBoundary>
  );
}

export default CesiumScene;
