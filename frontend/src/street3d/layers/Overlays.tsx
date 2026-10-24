import { Html } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { ConceptIntervention, SceneObject } from '../../map/types';
import { densifyXZ, lineStrings, pointAlong, pointPositions, polygonRings, polylineLength, roadProfile } from '../frame';
import type { StreetSceneAssets } from '../useStreetSceneAssets';
import type { WaterMask } from './Water';

// ----------------------------------------------------------------- road ribbons

const ribbonVertex = /* glsl */ `
attribute vec2 aRibbon; // x: across 0..1, y: metres along
varying vec2 vRibbon;
#include <common>
#include <fog_pars_vertex>
void main() {
  vRibbon = aRibbon;
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

const ribbonFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uTime;
uniform float uOpacity;
uniform float uChevrons;
varying vec2 vRibbon;
#include <common>
#include <fog_pars_fragment>
void main() {
  float across = abs(vRibbon.x - 0.5) * 2.0;
  float edge = smoothstep(0.78, 0.95, across) * (1.0 - smoothstep(0.95, 1.0, across));
  float chevron = fract((vRibbon.y - abs(vRibbon.x - 0.5) * 6.0 - uTime * 9.0) / 9.0);
  float band = smoothstep(0.0, 0.08, chevron) * (1.0 - smoothstep(0.2, 0.3, chevron)) * uChevrons;
  float fill = 0.22 + band * 0.55 + edge * 0.9;
  gl_FragColor = vec4(uColor * (0.85 + edge * 0.9 + band * 0.5), fill * uOpacity);
  #include <fog_fragment>
}`;

function ribbonGeometry(lines: Array<Array<[number, number]>>, width: number, lift: number, assets: StreetSceneAssets, mask: WaterMask) {
  const positions: number[] = [];
  const ribbon: number[] = [];
  const index: number[] = [];
  for (const line of lines) {
    const dense = densifyXZ(line, 3);
    if (dense.length < 2) continue;
    const profile = roadProfile(dense, assets.heightfield, (x, z) => mask.hydro(x, z));
    const start = positions.length / 3;
    let along = 0;
    dense.forEach(([x, z], i) => {
      const a = dense[Math.max(0, i - 1)];
      const b = dense[Math.min(dense.length - 1, i + 1)];
      const length = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const nx = ((b[1] - a[1]) / length) * (width / 2);
      const nz = (-(b[0] - a[0]) / length) * (width / 2);
      if (i > 0) along += Math.hypot(x - dense[i - 1][0], z - dense[i - 1][1]);
      for (const side of [-1, 1]) {
        const px = x + nx * side;
        const pz = z + nz * side;
        positions.push(px, profile[i] + lift, pz);
        ribbon.push(side < 0 ? 0 : 1, along);
      }
      if (i > 0) {
        const k = start + (i - 1) * 2;
        index.push(k, k + 1, k + 2, k + 1, k + 3, k + 2);
      }
    });
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('aRibbon', new THREE.Float32BufferAttribute(ribbon, 2));
  geometry.setIndex(index);
  return geometry;
}

function ribbonMaterial(color: string, opacity: number, chevrons: boolean) {
  return new THREE.ShaderMaterial({
    vertexShader: ribbonVertex,
    fragmentShader: ribbonFragment,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    fog: true,
    polygonOffset: true,
    polygonOffsetFactor: -8,
    polygonOffsetUnits: -8,
    uniforms: THREE.UniformsUtils.merge([THREE.UniformsLib.fog, {
      uColor: { value: new THREE.Color(color) },
      uTime: { value: 0 },
      uOpacity: { value: opacity },
      uChevrons: { value: chevrons ? 1 : 0 },
    }]),
  });
}

export interface RoadOverlayLine {
  roadId: string;
  name: string;
  points: Array<[number, number]>;
  selected: boolean;
  exposed: boolean;
}

export function RoadOverlay({ assets, mask, roads, label, sublabel }: {
  assets: StreetSceneAssets;
  mask: WaterMask;
  roads: RoadOverlayLine[];
  label: string;
  sublabel: string;
}) {
  const groups = useMemo(() => {
    const build = (filter: (road: RoadOverlayLine) => boolean, width: number, lift: number, color: string, opacity: number, chevrons: boolean) => {
      const lines = roads.filter(filter).map((road) => road.points);
      if (!lines.length) return null;
      return { geometry: ribbonGeometry(lines, width, lift, assets, mask), material: ribbonMaterial(color, opacity, chevrons) };
    };
    // Kept just above the pavement so displayed floodwater visibly covers inundated stretches.
    return [
      build((road) => !road.selected && !road.exposed, 3.2, 0.1, '#9fd8e6', 0.55, false),
      build((road) => !road.selected && road.exposed, 4.5, 0.11, '#ff7a59', 0.8, false),
      build((road) => road.selected && !road.exposed, 11, 0.12, '#ffd166', 1, true),
      build((road) => road.selected && road.exposed, 11, 0.12, '#ff9a4d', 1, true),
    ].filter(Boolean) as Array<{ geometry: THREE.BufferGeometry; material: THREE.ShaderMaterial }>;
  }, [assets, mask, roads]);

  useFrame((_, delta) => {
    for (const group of groups) group.material.uniforms.uTime.value += delta;
  });

  const anchor = useMemo(() => {
    const selected = roads.filter((road) => road.selected);
    if (!selected.length) return null;
    const all = selected.flatMap((road) => road.points);
    const mid = pointAlong(all, polylineLength(all) * 0.5);
    return [mid.x, assets.heightfield.sample(mid.x, mid.z) + 26, mid.z] as [number, number, number];
  }, [assets, roads]);

  return (
    <group>
      {groups.map((group, index) => (
        <mesh key={index} geometry={group.geometry} material={group.material} renderOrder={4} />
      ))}
      {anchor ? (
        <Html position={anchor} center zIndexRange={[20, 0]} className="street-label-anchor">
          <div className="street-road-label"><strong>{label}</strong><span>{sublabel}</span></div>
        </Html>
      ) : null}
    </group>
  );
}

// ---------------------------------------------------------------- scene objects

function EmergencyVehicle({ position, heading }: { position: [number, number, number]; heading: number }) {
  const red = useRef<THREE.MeshStandardMaterial>(null);
  const blue = useRef<THREE.MeshStandardMaterial>(null);
  useFrame(({ clock }) => {
    const on = Math.sin(clock.elapsedTime * 9) > 0;
    if (red.current) red.current.emissiveIntensity = on ? 6 : 0.3;
    if (blue.current) blue.current.emissiveIntensity = on ? 0.3 : 6;
  });
  return (
    <group position={position} rotation={[0, heading, 0]}>
      <mesh position={[0, 1.35, -0.6]} castShadow><boxGeometry args={[2.3, 2.1, 5.4]} /><meshStandardMaterial color="#c8202b" roughness={0.4} metalness={0.3} /></mesh>
      <mesh position={[0, 1.15, 2.75]} castShadow><boxGeometry args={[2.25, 1.7, 1.9]} /><meshStandardMaterial color="#d22a33" roughness={0.4} metalness={0.3} /></mesh>
      <mesh position={[0, 1.55, 3.55]}><boxGeometry args={[2.0, 0.75, 0.2]} /><meshStandardMaterial color="#1b2733" roughness={0.2} metalness={0.6} /></mesh>
      <mesh position={[0, 1.05, -0.6]}><boxGeometry args={[2.32, 0.18, 5.42]} /><meshStandardMaterial color="#f4f1e8" /></mesh>
      <mesh position={[-0.55, 2.12, 2.5]}><boxGeometry args={[0.9, 0.16, 0.35]} /><meshStandardMaterial ref={red} color="#ff3045" emissive="#ff1030" /></mesh>
      <mesh position={[0.55, 2.12, 2.5]}><boxGeometry args={[0.9, 0.16, 0.35]} /><meshStandardMaterial ref={blue} color="#3d7bff" emissive="#2050ff" /></mesh>
      {[-1, 1].flatMap((side) => [-2.3, 0.9, 2.7].map((z) => (
        <mesh key={`${side}${z}`} position={[side * 1.05, 0.45, z]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[0.45, 0.45, 0.32, 12]} /><meshStandardMaterial color="#15191d" /></mesh>
      )))}
    </group>
  );
}

function SiteBeacon({ position }: { position: [number, number, number] }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.y = clock.elapsedTime * 1.2;
    ref.current.position.y = position[1] + 14 + Math.sin(clock.elapsedTime * 2) * 0.8;
  });
  return (
    <group>
      <mesh ref={ref} position={[position[0], position[1] + 14, position[2]]}>
        <octahedronGeometry args={[2.2, 0]} />
        <meshStandardMaterial color="#ffd166" emissive="#ffb020" emissiveIntensity={1.6} />
      </mesh>
      <mesh position={[position[0], position[1] + 6, position[2]]}>
        <cylinderGeometry args={[0.12, 0.12, 12, 8]} />
        <meshBasicMaterial color="#ffd166" transparent opacity={0.6} />
      </mesh>
    </group>
  );
}

export function SceneObjects({ assets, objects, corridor }: {
  assets: StreetSceneAssets;
  objects: SceneObject[];
  corridor: Array<[number, number]>;
}) {
  return (
    <group>
      {objects.map((object) => {
        const [x, z] = assets.frame.toXZ(object.position[0], object.position[1]);
        if (!assets.frame.contains(x, z, 5)) return null;
        const y = assets.heightfield.sample(x, z);
        let heading = 0;
        if (corridor.length > 1) {
          let best = Infinity;
          for (let i = 1; i < corridor.length; i += 1) {
            const [ax, az] = corridor[i - 1];
            const [bx, bz] = corridor[i];
            const d = Math.hypot((ax + bx) / 2 - x, (az + bz) / 2 - z);
            if (d < best) { best = d; heading = Math.atan2(bx - ax, bz - az); }
          }
        }
        const illustrative = object.provenance === 'illustrative';
        return (
          <group key={object.id}>
            {object.kind === 'vehicle' ? <EmergencyVehicle position={[x, y + 0.06, z]} heading={heading} /> : <SiteBeacon position={[x, y, z]} />}
            <Html position={[x, y + (object.kind === 'vehicle' ? 6 : 20), z]} center zIndexRange={[19, 0]}>
              <div className={`street-object-label ${illustrative ? 'is-illustrative' : ''}`}>{illustrative ? 'Illustrative · ' : ''}{object.label}</div>
            </Html>
          </group>
        );
      })}
    </group>
  );
}

// ----------------------------------------------------------------- interventions

/** Display-only heights for schematic concepts that carry no sourced height. */
const SCHEMATIC_HEIGHT_M: Record<ConceptIntervention['intervention_type'], number> = {
  berm: 1.8,
  floodwall: 2.2,
  raised_roadway: 1.2,
  deployable_barrier: 1.2,
  drainage_upgrade: 0,
  alternate_access: 0,
};

const hologramVertex = /* glsl */ `
varying vec3 vWorld;
varying vec3 vNormalW;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  vNormalW = normalize(mat3(modelMatrix) * normal);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const hologramFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uTime;
varying vec3 vWorld;
varying vec3 vNormalW;
void main() {
  vec3 viewDir = normalize(cameraPosition - vWorld);
  float rim = pow(1.0 - abs(dot(normalize(vNormalW), viewDir)), 2.0);
  float scan = smoothstep(0.0, 0.15, fract(vWorld.y * 1.4 - uTime * 0.8)) * (1.0 - smoothstep(0.15, 0.3, fract(vWorld.y * 1.4 - uTime * 0.8)));
  float hatch = step(0.82, fract((vWorld.x + vWorld.z) * 0.35));
  float alpha = (0.16 + rim * 0.55 + scan * 0.3 + hatch * 0.12) * (gl_FrontFacing ? 1.0 : 0.6);
  gl_FragColor = vec4(uColor * (1.2 + rim * 1.5 + scan), alpha);
}`;

function sweepProfile(
  path: Array<[number, number]>,
  profile: Array<[number, number]>,
  assets: StreetSceneAssets,
  crestFrom: 'max' | 'local',
  height: number,
): THREE.BufferGeometry {
  // profile: [offsetAcross, heightAboveGround]; heights equal to `height` are crest points.
  const dense = densifyXZ(path, 2);
  const ground = dense.map(([x, z]) => assets.heightfield.sample(x, z));
  const crestBase = crestFrom === 'max' ? Math.max(...ground) : null;
  const positions: number[] = [];
  const index: number[] = [];
  const ring = profile.length;
  dense.forEach(([x, z], i) => {
    const a = dense[Math.max(0, i - 1)];
    const b = dense[Math.min(dense.length - 1, i + 1)];
    const length = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const nx = (b[1] - a[1]) / length;
    const nz = -(b[0] - a[0]) / length;
    for (const [across, up] of profile) {
      const px = x + nx * across;
      const pz = z + nz * across;
      const isCrest = Math.abs(up - height) < 1e-6 && height > 0;
      const base = isCrest && crestBase != null ? crestBase : up <= 0 ? assets.heightfield.sample(px, pz) : ground[i];
      positions.push(px, base + (isCrest && crestBase != null ? height : up), pz);
    }
    if (i > 0) {
      const p = (i - 1) * ring;
      const c = i * ring;
      for (let k = 0; k < ring - 1; k += 1) index.push(p + k, c + k, p + k + 1, c + k, c + k + 1, p + k + 1);
    }
  });
  const last = (dense.length - 1) * ring;
  for (let k = 1; k < ring - 1; k += 1) {
    index.push(0, k + 1, k);
    index.push(last, last + k, last + k + 1);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(index);
  const flat = geometry.toNonIndexed();
  flat.computeVertexNormals();
  return flat;
}

interface BuiltIntervention {
  id: string;
  solid: THREE.BufferGeometry[];
  solidColor: string;
  top?: THREE.BufferGeometry;
  topColor?: string;
  posts?: Array<[number, number, number]>;
  labelAt: [number, number, number];
  centre: [number, number, number];
}

export function buildIntervention(intervention: ConceptIntervention, assets: StreetSceneAssets): BuiltIntervention | null {
  const type = intervention.intervention_type;
  const sourcedHeight = intervention.visual_parameters?.conceptual_height_m;
  const height = sourcedHeight ?? SCHEMATIC_HEIGHT_M[type];
  const width = intervention.visual_parameters?.footprint_width_m;
  const lines = lineStrings(intervention.geometry).map((line) => assets.frame.lineToXZ(line));
  const points = pointPositions(intervention.geometry).map((p) => assets.frame.toXZ(p[0], p[1]));
  const polygons = polygonRings(intervention.geometry).map((rings) => assets.frame.lineToXZ(rings[0] ?? []));
  const solid: THREE.BufferGeometry[] = [];
  let top: THREE.BufferGeometry | undefined;
  let posts: Array<[number, number, number]> | undefined;
  const allXZ = [...lines.flat(), ...points, ...polygons.flat()];
  if (!allXZ.length) return null;

  for (const line of [...lines, ...polygons]) {
    if (line.length < 2) continue;
    if (type === 'berm') {
      const w = width ?? 9;
      const crest = Math.max(1.2, w * 0.22);
      solid.push(sweepProfile(line, [[-w / 2, -0.4], [-w / 2, 0], [-crest / 2, height], [crest / 2, height], [w / 2, 0], [w / 2, -0.4]], assets, 'local', height));
      top = sweepProfile(line, [[-crest / 2 + 0.2, height + 0.04], [crest / 2 - 0.2, height + 0.04]], assets, 'local', 0);
    } else if (type === 'floodwall') {
      const t = width ?? 0.5;
      solid.push(sweepProfile(line, [[-t / 2, -0.6], [-t / 2, height], [t / 2, height], [t / 2, -0.6], [-t / 2, -0.6]], assets, 'local', 0));
    } else if (type === 'raised_roadway') {
      const w = width ?? 14;
      solid.push(sweepProfile(line, [[-w / 2, -0.5], [-w / 2, height], [w / 2, height], [w / 2, -0.5]], assets, 'local', 0));
      top = sweepProfile(line, [[-w / 2 + 0.6, height + 0.03], [w / 2 - 0.6, height + 0.03]], assets, 'local', 0);
    } else if (type === 'deployable_barrier') {
      const t = width ?? 0.25;
      solid.push(sweepProfile(line, [[-t / 2, 0], [-t / 2, height], [t / 2, height], [t / 2, 0], [-t / 2, 0]], assets, 'local', 0));
      posts = densifyXZ(line, 3).map(([x, z]) => [x, assets.heightfield.sample(x, z), z]);
    } else if (type === 'alternate_access') {
      solid.push(sweepProfile(line, [[-3.5, 0.02], [-3.5, 0.25], [3.5, 0.25], [3.5, 0.02]], assets, 'local', 0));
    }
  }
  for (const [x, z] of points) {
    const y = assets.heightfield.sample(x, z);
    const shaft = new THREE.CylinderGeometry(1.4, 1.6, 1.4, 20).translate(x, y + 0.5, z);
    solid.push(shaft.index ? shaft.toNonIndexed() : shaft);
  }

  const cx = allXZ.reduce((sum, p) => sum + p[0], 0) / allXZ.length;
  const cz = allXZ.reduce((sum, p) => sum + p[1], 0) / allXZ.length;
  const cy = assets.heightfield.sample(cx, cz);
  const colors: Record<string, [string, string]> = {
    berm: ['#5f8a45', '#c9b98d'],
    floodwall: ['#bdb8ae', '#bdb8ae'],
    raised_roadway: ['#a9a59c', '#3f444b'],
    deployable_barrier: ['#d9d4c7', '#d9d4c7'],
    drainage_upgrade: ['#7d8b94', '#7d8b94'],
    alternate_access: ['#565b63', '#565b63'],
  };
  return {
    id: intervention.intervention_id,
    solid,
    solidColor: colors[type][0],
    top,
    topColor: colors[type][1],
    posts,
    labelAt: [cx, cy + Math.max(height, 1) + 12, cz],
    centre: [cx, cy, cz],
  };
}

export function Interventions({ assets, interventions, selectedId, registerMesh }: {
  assets: StreetSceneAssets;
  interventions: ConceptIntervention[];
  selectedId?: string | null;
  registerMesh: (mesh: THREE.Mesh | null, key: string) => void;
}) {
  const built = useMemo(
    () => interventions.map((item) => ({ item, geometry: buildIntervention(item, assets) })).filter((entry) => entry.geometry),
    [assets, interventions],
  );
  const hologram = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: hologramVertex,
    fragmentShader: hologramFragment,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    uniforms: { uColor: { value: new THREE.Color('#c58bff') }, uTime: { value: 0 } },
  }), []);
  // X-ray pass: keeps the concept footprint legible even where it sits below displayed water.
  const xray = useMemo(() => {
    const material = hologram.clone();
    material.depthTest = false;
    material.uniforms = { uColor: { value: new THREE.Color('#b77bff') }, uTime: hologram.uniforms.uTime };
    material.opacity = 0.5;
    return material;
  }, [hologram]);
  useFrame((_, delta) => { hologram.uniforms.uTime.value += delta; });

  return (
    <group>
      {built.map(({ item, geometry }) => {
        const g = geometry!;
        const conceptual = item.status !== 'implemented' && item.status !== 'verified';
        const schematic = item.geometry_status === 'schematic';
        const heightSourced = item.visual_parameters?.conceptual_height_m != null;
        return (
          <group key={item.intervention_id}>
            {g.solid.map((solid, index) => (
              <group key={index}>
                <mesh
                  ref={(mesh) => registerMesh(mesh, `intervention:${item.intervention_id}:${index}`)}
                  geometry={solid}
                  castShadow
                  receiveShadow
                  userData={{ interventionId: item.intervention_id }}
                >
                  <meshStandardMaterial color={g.solidColor} roughness={0.92} flatShading transparent={conceptual} opacity={conceptual ? 0.88 : 1} />
                </mesh>
                {conceptual ? <mesh geometry={solid} material={hologram} renderOrder={9} /> : null}
                {conceptual ? <mesh geometry={solid} material={xray} renderOrder={12} /> : null}
              </group>
            ))}
            {g.top ? (
              <mesh geometry={g.top} receiveShadow>
                <meshStandardMaterial color={g.topColor} roughness={0.95} polygonOffset polygonOffsetFactor={-2} />
              </mesh>
            ) : null}
            {g.posts?.map(([x, y, z], index) => (
              <mesh key={index} position={[x, y + 0.7, z]} castShadow>
                <boxGeometry args={[0.2, 1.5, 0.2]} />
                <meshStandardMaterial color="#e8b33a" />
              </mesh>
            ))}
            <Html position={g.labelAt} center zIndexRange={[21, 0]}>
              <div className={`street-concept-label ${item.intervention_id === selectedId ? 'is-selected' : ''}`}>
                <span>{schematic ? 'Schematic concept' : item.status}</span>
                <strong>{item.label ?? item.intervention_type.replaceAll('_', ' ')}</strong>
                <small>{heightSourced ? 'Sourced display height' : `Schematic: ${SCHEMATIC_HEIGHT_M[item.intervention_type]} m above local grade, not a design crest`} · not hydraulically modeled</small>
              </div>
            </Html>
          </group>
        );
      })}
    </group>
  );
}
