import { CameraControls, Sky } from '@react-three/drei';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Bloom, EffectComposer, N8AO, SMAA, ToneMapping, Vignette } from '@react-three/postprocessing';
import { ToneMappingMode } from 'postprocessing';
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import * as THREE from 'three';
import { acceleratedRaycast, computeBoundsTree, disposeBoundsTree } from 'three-mesh-bvh';
import { densifyXZ, lineStrings, pointAlong, polylineLength } from './frame';
import { Buildings, Streets, Terrain } from './layers/CityLayers';
import { Interventions, RoadOverlay, SceneObjects, buildIntervention, type RoadOverlayLine } from './layers/Overlays';
import { CorridorTraffic, StreetProps } from './layers/Props';
import { Water, WaterMask } from './layers/Water';
import type { BuildingRecord, CameraPreset, StreetSceneProps } from './types';
import { useStreetSceneAssets, type StreetSceneAssets } from './useStreetSceneAssets';
import './street3d.css';

THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

declare module 'three' {
  interface BufferGeometry {
    computeBoundsTree: typeof computeBoundsTree;
    disposeBoundsTree: typeof disposeBoundsTree;
  }
}

type Quality = 'high' | 'balanced';
interface LayerToggles { buildings: boolean; streets: boolean; props: boolean; traffic: boolean; water: boolean; concept: boolean }

const SUN_CLEAR = new THREE.Vector3(-0.52, 0.62, 0.58).normalize();
const SUN_STORM = new THREE.Vector3(-0.3, 0.42, 0.85).normalize();

// --------------------------------------------------------------------- camera

interface View { position: THREE.Vector3; target: THREE.Vector3 }

function corridorFrame(assets: StreetSceneAssets, lines: Array<Array<[number, number]>>) {
  const all = lines.flat();
  if (!all.length) {
    const [x0, z0, x1, z1] = assets.manifest.frame.bounds_xz;
    return { centre: new THREE.Vector3((x0 + x1) / 2, 5, (z0 + z1) / 2), axis: new THREE.Vector2(0, 1), length: 800, seaSide: new THREE.Vector2(1, 0), points: [] as Array<[number, number]> };
  }
  const xs = all.map((p) => p[0]);
  const zs = all.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cz = (Math.min(...zs) + Math.max(...zs)) / 2;
  const first = all[0];
  const last = all[all.length - 1];
  const axis = new THREE.Vector2(last[0] - first[0], last[1] - first[1]);
  const length = Math.max(axis.length(), 60);
  axis.normalize();
  const normal = new THREE.Vector2(-axis.y, axis.x);
  // Look from whichever side is lower (usually the harbour), toward the city.
  const probe = (sign: number) => {
    let total = 0;
    for (const d of [80, 160, 260]) total += assets.heightfield.sample(cx + normal.x * d * sign, cz + normal.y * d * sign);
    return total;
  };
  const seaSide = probe(1) < probe(-1) ? normal : normal.clone().multiplyScalar(-1);
  return { centre: new THREE.Vector3(cx, assets.heightfield.sample(cx, cz), cz), axis, length, seaSide, points: all };
}

interface WetContext { mask: WaterMask; level: number }

function presetView(
  preset: CameraPreset,
  assets: StreetSceneAssets,
  lines: Array<Array<[number, number]>>,
  conceptCentre: THREE.Vector3 | null,
  wet?: WetContext,
): View {
  const frame = corridorFrame(assets, lines);
  const { centre, axis, length, seaSide } = frame;
  if (preset === 'aerial') {
    const d = THREE.MathUtils.clamp(length * 0.75, 650, 1250);
    return {
      position: new THREE.Vector3(centre.x + seaSide.x * d * 0.7 - axis.x * d * 0.45, centre.y + d * 0.75, centre.z + seaSide.y * d * 0.7 - axis.y * d * 0.45),
      target: centre.clone(),
    };
  }
  if (preset === 'concept' && conceptCentre) {
    const d = 95;
    return {
      position: new THREE.Vector3(conceptCentre.x + seaSide.x * d - axis.x * 30, conceptCentre.y + 34, conceptCentre.z + seaSide.y * d - axis.y * 30),
      target: conceptCentre.clone().add(new THREE.Vector3(0, 2, 0)),
    };
  }
  if (preset === 'street' && frame.points.length > 1) {
    const dense = densifyXZ(frame.points, 4);
    const total = polylineLength(dense);
    const trees = [...(assets.props?.street_trees ?? []), ...(assets.props?.park_trees ?? [])];
    let s0 = total * 0.42;
    let lookAhead = 80;
    if (wet && wet.level > -50) {
      // Stand just before the most inundated displayed stretch of the corridor and look into it.
      let best = 0;
      let bestS = -1;
      let along = 0;
      dense.forEach(([x, z], i) => {
        if (i > 0) along += Math.hypot(x - dense[i - 1][0], z - dense[i - 1][1]);
        if (!wet.mask.flooded(x, z, wet.level)) return;
        const depth = wet.level - assets.heightfield.sample(x, z);
        if (depth > best) { best = depth; bestS = along; }
      });
      if (bestS >= 0) { s0 = Math.max(0, bestS - 45); lookAhead = 75; }
    }
    let here = pointAlong(dense, s0);
    let px = here.x;
    let pz = here.z;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      here = pointAlong(dense, s0);
      // Right-hand carriageway, ~5 m off the median line.
      px = here.x - Math.cos(here.heading) * 5;
      pz = here.z + Math.sin(here.heading) * 5;
      const blocked = trees.some(([tx, , tz]) => Math.hypot(tx - px, tz - pz) < 7);
      if (!blocked) break;
      s0 = (s0 + 9) % total;
    }
    const ahead = pointAlong(dense, Math.min(total, s0 + lookAhead));
    const groundHere = assets.heightfield.sample(px, pz);
    return {
      position: new THREE.Vector3(px, groundHere + 1.8, pz),
      target: new THREE.Vector3(ahead.x, assets.heightfield.sample(ahead.x, ahead.z) + 1.4, ahead.z),
    };
  }
  const d = THREE.MathUtils.clamp(length * 0.42, 220, 620);
  return {
    position: new THREE.Vector3(centre.x + seaSide.x * d - axis.x * d * 0.25, centre.y + d * 0.42, centre.z + seaSide.y * d - axis.y * d * 0.25),
    target: centre.clone().add(new THREE.Vector3(0, 2, 0)),
  };
}

function CameraRig({ assets, lines, conceptCentre, request, levelRef, mask }: {
  mask: WaterMask;
  assets: StreetSceneAssets;
  lines: Array<Array<[number, number]>>;
  conceptCentre: THREE.Vector3 | null;
  request?: { preset: CameraPreset; nonce: number };
  levelRef: React.RefObject<number>;
}) {
  const controls = useRef<CameraControls>(null);
  const { camera } = useThree();
  const keys = useRef(new Set<string>());
  const introDone = useRef(false);

  useEffect(() => {
    const down = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      keys.current.add(event.key.toLowerCase());
    };
    const up = (event: KeyboardEvent) => keys.current.delete(event.key.toLowerCase());
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', () => keys.current.clear());
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);

  // Cinematic intro: start high over the harbour, then descend to the corridor.
  const latest = useRef({ assets, lines, conceptCentre, preset: request?.preset });
  latest.current = { assets, lines, conceptCentre, preset: request?.preset };
  useEffect(() => {
    const c = controls.current;
    if (!c || introDone.current) return;
    introDone.current = true;
    const { assets: a, lines: l, conceptCentre: cc, preset } = latest.current;
    const from = presetView('aerial', a, l, cc);
    from.position.y += 900;
    void c.setLookAt(from.position.x, from.position.y, from.position.z, from.target.x, from.target.y, from.target.z, false);
    const to = presetView(preset ?? 'corridor', a, l, cc);
    window.setTimeout(() => {
      c.smoothTime = 1.4;
      void c.setLookAt(to.position.x, to.position.y, to.position.z, to.target.x, to.target.y, to.target.z, true).then(() => { c.smoothTime = 0.55; });
    }, 250);
  }, []);

  useEffect(() => {
    const c = controls.current;
    if (!c || !request || !introDone.current) return;
    const view = presetView(request.preset, assets, lines, conceptCentre, { mask, level: levelRef.current ?? -99 });
    c.smoothTime = request.preset === 'street' ? 0.9 : 0.75;
    void c.setLookAt(view.position.x, view.position.y, view.position.z, view.target.x, view.target.y, view.target.z, true);
    // Only respond to explicit requests (nonce) — not to every data change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request?.nonce]);

  const target = useMemo(() => new THREE.Vector3(), []);
  const endPosition = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, rawDelta) => {
    const c = controls.current;
    if (!c) return;
    const delta = Math.min(rawDelta, 0.1);
    const ground = assets.heightfield.sample(camera.position.x, camera.position.z);
    const altitude = Math.max(camera.position.y - ground, 0.5);
    const pressed = keys.current;
    if (pressed.size) {
      const speed = THREE.MathUtils.clamp(altitude * 1.2, 8, 260) * (pressed.has('shift') ? 2.5 : 1) * delta;
      if (pressed.has('w') || pressed.has('arrowup')) void c.forward(speed, false);
      if (pressed.has('s') || pressed.has('arrowdown')) void c.forward(-speed, false);
      if (pressed.has('a') || pressed.has('arrowleft')) void c.truck(-speed, 0, false);
      if (pressed.has('d') || pressed.has('arrowright')) void c.truck(speed, 0, false);
      if (pressed.has('e')) void c.elevate(speed * 0.6, false);
      if (pressed.has('q')) void c.elevate(-speed * 0.6, false);
    }
    // Keep the camera above the official terrain surface and above displayed water.
    // Judge the transition's end point so fly-tos are never frozen half-way.
    c.getPosition(endPosition, true);
    const endFloor = Math.max(assets.heightfield.sample(endPosition.x, endPosition.z) + 1.2, (levelRef.current ?? -99) + 0.9);
    if (endPosition.y < endFloor - 0.01) {
      c.getTarget(target, true);
      void c.setLookAt(endPosition.x, endFloor, endPosition.z, target.x, Math.max(target.y, endFloor - 0.6), target.z, false);
    }
    const near = THREE.MathUtils.clamp(altitude * 0.04, 0.25, 6);
    if (Math.abs((camera as THREE.PerspectiveCamera).near - near) > 0.05) {
      (camera as THREE.PerspectiveCamera).near = near;
      camera.updateProjectionMatrix();
    }
  });

  return (
    <CameraControls
      ref={controls}
      makeDefault
      minDistance={2}
      maxDistance={4200}
      maxPolarAngle={Math.PI * 0.5 + 0.12}
      dollyToCursor
      smoothTime={0.55}
      draggingSmoothTime={0.12}
    />
  );
}

// ------------------------------------------------------------------- lighting

function SunAndShadow({ storm }: { storm: boolean }) {
  const light = useRef<THREE.DirectionalLight>(null);
  const { camera, controls } = useThree();
  const target = useMemo(() => new THREE.Vector3(), []);
  const lastSize = useRef(0);
  useFrame(() => {
    const sun = light.current;
    if (!sun) return;
    const c = controls as unknown as CameraControls | null;
    if (c?.getTarget) c.getTarget(target); else target.set(0, 0, 0);
    const distance = camera.position.distanceTo(target);
    const size = THREE.MathUtils.clamp(distance * 0.75, 70, 650);
    const dir = storm ? SUN_STORM : SUN_CLEAR;
    sun.position.copy(target).addScaledVector(dir, 900);
    sun.target.position.copy(target);
    sun.target.updateMatrixWorld();
    if (Math.abs(size - lastSize.current) > lastSize.current * 0.12) {
      lastSize.current = size;
      const shadow = sun.shadow.camera as THREE.OrthographicCamera;
      shadow.left = -size; shadow.right = size; shadow.top = size; shadow.bottom = -size;
      shadow.near = 100; shadow.far = 1900;
      shadow.updateProjectionMatrix();
      sun.shadow.bias = -0.00025 * (size / 150);
      sun.shadow.normalBias = 0.04 * (size / 150);
    }
  });
  return (
    <>
      <directionalLight
        ref={light}
        castShadow
        intensity={storm ? 1.1 : 2.1}
        color={storm ? '#dfe6ee' : '#fff1de'}
        shadow-mapSize={[4096, 4096]}
      />
      <hemisphereLight args={[storm ? '#b9c6d2' : '#cfe3ff', storm ? '#4d5552' : '#5d5242', storm ? 0.95 : 0.65]} />
      <ambientLight intensity={storm ? 0.25 : 0.12} />
    </>
  );
}

// ------------------------------------------------------------------- picking

function Picker({ meshes, onPick }: { meshes: React.RefObject<Map<string, THREE.Mesh>>; onPick: (hit: THREE.Intersection | null) => void }) {
  const { gl, camera } = useThree();
  useEffect(() => {
    const element = gl.domElement;
    let start: [number, number] | null = null;
    const raycaster = new THREE.Raycaster();
    (raycaster as THREE.Raycaster & { firstHitOnly?: boolean }).firstHitOnly = true;
    const down = (event: PointerEvent) => { start = [event.clientX, event.clientY]; };
    const up = (event: PointerEvent) => {
      if (!start || Math.hypot(event.clientX - start[0], event.clientY - start[1]) > 5) return;
      const rect = element.getBoundingClientRect();
      const ndc = new THREE.Vector2(((event.clientX - rect.left) / rect.width) * 2 - 1, -((event.clientY - rect.top) / rect.height) * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      const targets = [...(meshes.current?.values() ?? [])].filter((mesh) => mesh.visible);
      const hits = raycaster.intersectObjects(targets, false).sort((a, b) => a.distance - b.distance);
      onPick(hits[0] ?? null);
    };
    element.addEventListener('pointerdown', down);
    element.addEventListener('pointerup', up);
    return () => { element.removeEventListener('pointerdown', down); element.removeEventListener('pointerup', up); };
  }, [gl, camera, meshes, onPick]);
  return null;
}

// --------------------------------------------------------------------- scene

/** Fog starts beyond the area being looked at, so aerial views stay crisp and only the horizon fades. */
function FogController({ storm }: { storm: boolean }) {
  const { scene, camera, controls } = useThree();
  const target = useMemo(() => new THREE.Vector3(), []);
  useFrame(() => {
    const fog = scene.fog as THREE.Fog | null;
    if (!fog) return;
    const c = controls as unknown as CameraControls | null;
    if (c?.getTarget) c.getTarget(target); else target.set(0, 0, 0);
    const distance = camera.position.distanceTo(target);
    fog.near = Math.max(storm ? 700 : 1200, distance * 1.25);
    fog.far = fog.near + (storm ? 4200 : 7000);
  });
  return null;
}

/** Neutral ground beyond the loaded BPDA tiles so the model edge never shows a void. */
function OutsideCoverage({ assets }: { assets: StreetSceneAssets }) {
  const [x0, z0, x1, z1] = assets.manifest.frame.bounds_xz;
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[(x0 + x1) / 2, -1.6, (z0 + z1) / 2]} receiveShadow>
      <planeGeometry args={[30000, 30000]} />
      <meshStandardMaterial color="#7f8d89" roughness={1} />
    </mesh>
  );
}

/** Dev-only handle for automated visual checks (stripped from production builds). */
function DevHandle() {
  const { scene, camera, gl, controls } = useThree();
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    (window as unknown as Record<string, unknown>).__floodroute3d = { scene, camera, gl, controls, THREE };
  }, [scene, camera, gl, controls]);
  return null;
}

function SceneContents({ assets, props, toggles, quality, selectedBuilding, setSelectedBuilding }: {
  assets: StreetSceneAssets;
  props: StreetSceneProps;
  toggles: LayerToggles;
  quality: Quality;
  selectedBuilding: BuildingRecord | null;
  setSelectedBuilding: (record: BuildingRecord | null) => void;
}) {
  const { roads, selectedRoadIds, water } = props;
  const pickables = useRef(new Map<string, THREE.Mesh>());

  const registerMesh = useCallback((mesh: THREE.Mesh | null, key: string) => {
    if (mesh) {
      if (!mesh.geometry.boundsTree) mesh.geometry.computeBoundsTree();
      // Terrain is not pickable. The camera floor is enforced per frame from the heightfield (no
      // camera-controls colliders: their near-plane rays trap the camera on low targets near slopes).
      if (key.startsWith('terrain:')) return;
      pickables.current.set(key, mesh);
    } else {
      pickables.current.delete(key);
    }
  }, []);

  const mask = useMemo(() => new WaterMask(assets), [assets]);
  const hydroFillM = useMemo(() => mask.hydroFill(assets.heightfield), [assets, mask]);
  useEffect(() => { mask.draw(water.mode === 'none' ? null : water.flood); }, [mask, water.flood, water.mode]);
  useEffect(() => {
    if (import.meta.env.DEV) Object.assign(window, { __floodroute3dDebug: { mask, assets } });
  }, [mask, assets]);

  const overlay = useMemo<RoadOverlayLine[]>(() => {
    const idProperty = roads.roadIdProperty ?? 'road_id';
    const selected = new Set(selectedRoadIds);
    const exposed = new Set(roads.exposedRoadIds ?? []);
    return roads.data.features.flatMap((feature) => {
      const roadId = String(feature.properties?.[idProperty] ?? feature.id ?? '');
      return lineStrings(feature.geometry).map((line) => ({
        roadId,
        name: String(feature.properties?.name ?? roadId),
        points: assets.frame.lineToXZ(line).filter(([x, z]) => assets.frame.contains(x, z, 2)),
        selected: selected.has(roadId),
        exposed: water.mode !== 'none' && exposed.has(roadId),
      }));
    }).filter((line) => line.points.length > 1);
  }, [assets, roads, selectedRoadIds, water.mode]);

  const selectedLines = useMemo(() => overlay.filter((line) => line.selected).map((line) => line.points), [overlay]);
  const corridorPoints = useMemo(() => selectedLines.flat(), [selectedLines]);
  const conceptCentre = useMemo(() => {
    const concept = props.interventions.find((item) => item.intervention_id === props.selectedInterventionId) ?? props.interventions[0];
    const built = concept ? buildIntervention(concept, assets) : null;
    return built ? new THREE.Vector3(...built.centre) : null;
  }, [assets, props.interventions, props.selectedInterventionId]);

  const levelRef = useRef<number>(-99);
  levelRef.current = water.mode === 'none' || water.displayedLevelM == null ? -99 : water.displayedLevelM;
  const storm = water.mode !== 'none';

  const onPick = useCallback((hit: THREE.Intersection | null) => {
    const interventionId = hit?.object.userData?.interventionId as string | undefined;
    if (interventionId) {
      props.onSelection?.({ kind: 'intervention', id: interventionId });
      return;
    }
    if (hit && hit.object === pickables.current.get('buildings') && hit.face) {
      const ids = (hit.object as THREE.Mesh).geometry.getAttribute('_feature_id');
      const record = assets.buildingRecords[ids.getX(hit.face.a)];
      setSelectedBuilding(record ?? null);
      return;
    }
    setSelectedBuilding(null);
  }, [assets, props, setSelectedBuilding]);

  return (
    <>
      <color attach="background" args={[storm ? '#8f9ca6' : '#cfe0ec']} />
      <fog attach="fog" args={[storm ? '#8f9ca6' : '#c4d6e3', 1400, 7500]} />
      <FogController storm={storm} />
      {storm ? null : (
        <Sky
          distance={20000}
          sunPosition={SUN_CLEAR.clone().multiplyScalar(1000).toArray()}
          turbidity={5.5}
          rayleigh={1.1}
          mieCoefficient={0.004}
          mieDirectionalG={0.82}
        />
      )}
      <SunAndShadow storm={storm} />
      <OutsideCoverage assets={assets} />
      <Terrain assets={assets} registerMesh={registerMesh} />
      {toggles.streets ? <Streets assets={assets} /> : null}
      {toggles.buildings ? (
        <Buildings assets={assets} heightTexture={assets.heightTexture} selectedFeature={selectedBuilding?.feature_id ?? null} registerMesh={registerMesh} />
      ) : null}
      {toggles.props ? <StreetProps assets={assets} /> : null}
      {toggles.traffic ? <CorridorTraffic assets={assets} lines={selectedLines} mask={mask} levelRef={levelRef} /> : null}
      <SceneObjects assets={assets} objects={props.sceneObjects ?? []} corridor={corridorPoints} />
      {toggles.water ? <Water assets={assets} mask={mask} water={water} hydroFillM={hydroFillM} sunDirection={storm ? SUN_STORM : SUN_CLEAR} /> : null}
      <RoadOverlay
        assets={assets}
        mask={mask}
        roads={overlay}
        label={props.corridorLabel}
        sublabel={water.mode === 'none' ? 'Selected corridor · fixture centreline' : 'Footprint overlap · passability unknown'}
      />
      {toggles.concept ? (
        <Interventions assets={assets} interventions={props.interventions} selectedId={props.selectedInterventionId} registerMesh={registerMesh} />
      ) : null}
      <CameraRig assets={assets} lines={selectedLines} conceptCentre={conceptCentre} request={props.cameraRequest} levelRef={levelRef} mask={mask} />
      <Picker meshes={pickables} onPick={onPick} />
      <DevHandle />
      <EffectComposer multisampling={0} enableNormalPass={false}>
        {quality === 'high' ? <N8AO aoRadius={5} distanceFalloff={1.2} intensity={2.4} halfRes quality="performance" /> : <></>}
        <Bloom intensity={0.4} luminanceThreshold={1.15} luminanceSmoothing={0.15} mipmapBlur />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <SMAA />
        <Vignette offset={0.25} darkness={0.42} />
      </EffectComposer>
    </>
  );
}

class CanvasBoundary extends Component<{ children: ReactNode }, { error?: Error }> {
  state: { error?: Error } = {};
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    if (this.state.error) {
      return <div className="street3d-fallback" role="alert"><strong>3D street scene unavailable</strong><span>{this.state.error.message}</span><small>Check WebGL2 support. The city overview remains available.</small></div>;
    }
    return this.props.children;
  }
}

function BuildingCard({ record, onClose }: { record: BuildingRecord; onClose: () => void }) {
  const ft = (value: number | null) => (value == null ? 'Unknown' : `${value.toFixed(1)} ft`);
  return (
    <aside className="street3d-card">
      <header><span className="street3d-chip is-official">BPDA 3D model · official</span><button onClick={onClose} aria-label="Close">×</button></header>
      <h3>{record.name ?? `${record.struct_type} model`}</h3>
      <dl>
        <div><dt>Structure</dt><dd>{record.struct_type} · LOD {record.lod}</dd></div>
        <div><dt>Model height</dt><dd>{ft(record.height_ft)}</dd></div>
        <div><dt>Ground elevation</dt><dd>{ft(record.ground_elevation_ft_navd88)} NAVD88</dd></div>
        <div><dt>Survey</dt><dd>{record.survey_source ?? 'Unknown'}{record.survey_date ? ` · ${record.survey_date}` : ''}</dd></div>
      </dl>
      <small>{record.model_credit ?? 'Model credit not recorded.'} Model ID {record.model_id}. Facade windows in this view are stylised, not surveyed. No flood damage is inferred.</small>
      {record.parcel_id ? <a href={`https://app01.cityofboston.gov/AssessingMap/?find=${record.parcel_id}`} target="_blank" rel="noreferrer">Boston Assessing parcel {record.parcel_id} ↗</a> : null}
    </aside>
  );
}

export function StreetScene3D(props: StreetSceneProps) {
  const state = useStreetSceneAssets(props.manifestUrl);
  const [toggles, setToggles] = useState<LayerToggles>({ buildings: true, streets: true, props: true, traffic: true, water: true, concept: true });
  const [quality, setQuality] = useState<Quality>('high');
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingRecord | null>(null);
  const [localRequest, setLocalRequest] = useState<{ preset: CameraPreset; nonce: number } | undefined>();
  const [activePreset, setActivePreset] = useState<CameraPreset>(props.cameraRequest?.preset ?? 'corridor');

  const request = useMemo(() => {
    if (!localRequest) return props.cameraRequest;
    if (!props.cameraRequest) return localRequest;
    return localRequest.nonce > props.cameraRequest.nonce ? localRequest : props.cameraRequest;
  }, [localRequest, props.cameraRequest]);
  useEffect(() => { if (props.cameraRequest) setActivePreset(props.cameraRequest.preset); }, [props.cameraRequest]);

  const go = (preset: CameraPreset) => {
    setActivePreset(preset);
    setLocalRequest({ preset, nonce: Date.now() });
  };
  const toggle = (key: keyof LayerToggles) => setToggles((current) => ({ ...current, [key]: !current[key] }));
  const { water } = props;
  const assets = state.status === 'ready' ? state.assets : null;
  const covered = useMemo(() => {
    if (!assets) return true;
    const idProperty = props.roads.roadIdProperty ?? 'road_id';
    const selected = new Set(props.selectedRoadIds);
    return props.roads.data.features.some((feature) => selected.has(String(feature.properties?.[idProperty] ?? ''))
      && lineStrings(feature.geometry).some((line) => line.some(([lon, lat]) => assets.frame.contains(...assets.frame.toXZ(lon, lat)))));
  }, [assets, props.roads, props.selectedRoadIds]);

  return (
    <section className={`street3d ${props.className ?? ''}`} aria-label="3D street scene">
      {assets ? (
        <CanvasBoundary>
          <Canvas
            frameloop={props.active === false ? 'never' : 'always'}
            shadows={{ type: THREE.PCFShadowMap }}
            dpr={[1, quality === 'high' ? 1.75 : 1.25]}
            camera={{ fov: 50, near: 0.5, far: 14000, position: [0, 1500, 1500] }}
            gl={{ antialias: false, powerPreference: 'high-performance', stencil: false }}
          >
            <SceneContents
              assets={assets}
              props={{ ...props, cameraRequest: request }}
              toggles={toggles}
              quality={quality}
              selectedBuilding={selectedBuilding}
              setSelectedBuilding={setSelectedBuilding}
            />
          </Canvas>
        </CanvasBoundary>
      ) : (
        <div className="street3d-loading">
          {state.status === 'error' ? (
            <><strong>3D street model could not load</strong><span>{state.message}</span></>
          ) : state.status === 'loading' && (
            <><strong>Building Boston in 3D…</strong><span>{state.detail}</span><div className="street3d-progress"><i style={{ width: `${Math.round(state.progress * 100)}%` }} /></div></>
          )}
        </div>
      )}

      <div className="street3d-layers" aria-label="3D layers">
        {(Object.keys(toggles) as Array<keyof LayerToggles>).filter((key) => key !== 'concept' || props.interventions.length > 0).map((key) => (
          <button key={key} className={toggles[key] ? 'is-active' : ''} aria-pressed={toggles[key]} onClick={() => toggle(key)}>
            <span aria-hidden="true" />{key}
          </button>
        ))}
        <button className="quality" onClick={() => setQuality((q) => (q === 'high' ? 'balanced' : 'high'))} title="Ambient occlusion and resolution">
          {quality === 'high' ? 'High quality' : 'Balanced'}
        </button>
      </div>

      {!covered ? (
        <div className="street3d-coverage" role="status">
          <strong>{props.corridorLabel} is outside the loaded 3D tiles</strong>
          <span>Detailed BPDA geometry is built for {assets?.manifest.tiles.join(', ')}. Add tiles with analysis/scene/build_bpda_scene.py --tiles.</span>
          {props.onOutsideCoverage ? <button onClick={props.onOutsideCoverage}>Open city overview</button> : null}
        </div>
      ) : null}

      {selectedBuilding ? <BuildingCard record={selectedBuilding} onClose={() => setSelectedBuilding(null)} /> : null}

      <nav className="street3d-camera" aria-label="Camera">
        {(['aerial', 'corridor', 'street', ...(props.interventions.length ? ['concept'] as const : [])] as CameraPreset[]).map((preset) => (
          <button key={preset} className={activePreset === preset ? 'is-active' : ''} onClick={() => go(preset)}>
            {preset === 'aerial' ? 'Aerial' : preset === 'corridor' ? 'Corridor' : preset === 'street' ? 'Street level' : 'Concept'}
          </button>
        ))}
        <span className="street3d-keys"><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> move · <kbd>Q</kbd>/<kbd>E</kbd> height · drag to orbit · right-drag to pan</span>
      </nav>

      <div className="street3d-legend">
        <div><i className="lg-official" /><span><strong>Terrain, buildings, streets</strong> BPDA 3D Smart Model (official, PDDL)</span></div>
        {water.mode !== 'none' && water.flood ? (
          <div><i className="lg-water" /><span><strong>Water</strong> {water.flood.sourceLabel ?? 'Sourced'} footprint · surface {water.displayedLevelM?.toFixed(2)} m NAVD88{water.mode === 'gauge_replay' ? ' (gauge-driven, illustrative)' : water.peakSurfaceM != null ? ' (reported peak WSE)' : ''}</span></div>
        ) : (
          <div><i className="lg-water" /><span><strong>Harbour</strong> official hydrography at nominal {water.harbourLevelM.toFixed(1)} m NAVD88</span></div>
        )}
        <div><i className="lg-illustrative" /><span><strong>Trees, lights, cars</strong> illustrative placement</span></div>
        {props.interventions.length ? <div><i className="lg-concept" /><span><strong>Concept</strong> schematic · not hydraulically modeled</span></div> : null}
        <small>Water colour = displayed level minus 2011 terrain (visual cue, not measured depth). No bathymetry is loaded, so the harbour is never drawn below the terrain's flat water fill (~0.4 m NAVD88). Floodwater spreads from the harbour through ground below the displayed level (connected fill, not flow modelling). Planning prototype — not for operational emergency routing or construction decisions.</small>
      </div>
    </section>
  );
}

export default StreetScene3D;
