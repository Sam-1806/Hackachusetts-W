import { useFrame } from '@react-three/fiber';
import { useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { densifyXZ, pointAlong, polylineLength, roadProfile } from '../frame';
import type { StreetSceneAssets } from '../useStreetSceneAssets';
import type { WaterMask } from './Water';

const CAR_COLORS = ['#d9dde2', '#2d3540', '#b23a3a', '#3d6fa8', '#e6e2d6', '#6b747d', '#1f4f46', '#d6a443'];

const flat = (geometry: THREE.BufferGeometry) => (geometry.index ? geometry.toNonIndexed() : geometry);

function box(w: number, h: number, d: number, x = 0, y = 0, z = 0) {
  const geometry = new THREE.BoxGeometry(w, h, d);
  geometry.translate(x, y, z);
  return geometry;
}

/** Stylised low-poly car, forward along +z, origin at road level. */
export function carGeometries() {
  const body = mergeGeometries([
    box(1.78, 0.62, 4.3, 0, 0.55, 0),
    box(1.7, 0.18, 1.0, 0, 0.92, 1.55),
    box(1.7, 0.18, 0.8, 0, 0.92, -1.7),
  ].map(flat))!;
  const cabin = new THREE.BoxGeometry(1.56, 0.58, 2.2, 1, 1, 1);
  const p = cabin.getAttribute('position') as THREE.BufferAttribute;
  for (let i = 0; i < p.count; i += 1) {
    if (p.getY(i) > 0) { p.setX(i, p.getX(i) * 0.9); p.setZ(i, p.getZ(i) * 0.78 - 0.1); }
  }
  cabin.translate(0, 1.15, -0.2);
  cabin.computeVertexNormals();
  const wheels = mergeGeometries([-1, 1].flatMap((side) => [-1.35, 1.35].map((z) => {
    const wheel = new THREE.CylinderGeometry(0.34, 0.34, 0.26, 10);
    wheel.rotateZ(Math.PI / 2);
    wheel.translate(side * 0.82, 0.34, z);
    return flat(wheel);
  })))!;
  const glassAndTyres = mergeGeometries([flat(cabin), flat(wheels)])!;
  return { body: flat(body), detail: glassAndTyres };
}

function useInstances(
  ref: React.RefObject<THREE.InstancedMesh | null>,
  items: Array<{ x: number; y: number; z: number; heading?: number; scale?: number; color?: string }>,
) {
  useLayoutEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    const dummy = new THREE.Object3D();
    const color = new THREE.Color();
    items.forEach((item, index) => {
      dummy.position.set(item.x, item.y, item.z);
      dummy.rotation.set(0, item.heading ?? 0, 0);
      dummy.scale.setScalar(item.scale ?? 1);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);
      if (item.color) mesh.setColorAt(index, color.set(item.color));
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    mesh.computeBoundingSphere();
  }, [ref, items]);
}

/** Generated street furniture (provenance: illustrative). */
export function StreetProps({ assets }: { assets: StreetSceneAssets }) {
  const props = assets.props;
  const trees = useMemo(() => {
    if (!props) return [];
    const palette = ['#5f8f4e', '#6e9b52', '#4f7f45', '#7aa25a', '#86a964'];
    return [...props.street_trees, ...props.park_trees].map(([x, y, z, scale], index) => ({
      x, y, z, scale, heading: index * 1.7, color: palette[index % palette.length],
    }));
  }, [props]);
  const lights = useMemo(() => (props?.streetlights ?? []).map(([x, y, z, heading]) => ({ x, y, z, heading })), [props]);
  const cars = useMemo(() => (props?.parked_cars ?? []).map(([x, y, z, heading, colour]) => ({
    x, y, z, heading, color: CAR_COLORS[colour % CAR_COLORS.length],
  })), [props]);

  const geometries = useMemo(() => {
    const foliage = mergeGeometries([
      new THREE.IcosahedronGeometry(2.5, 1).translate(0, 5.2, 0),
      new THREE.IcosahedronGeometry(1.9, 1).translate(0.5, 6.9, 0.3),
      new THREE.IcosahedronGeometry(1.6, 1).translate(-0.9, 6.0, -0.6),
    ].map(flat))!;
    const trunk = new THREE.CylinderGeometry(0.16, 0.24, 4.4, 6).translate(0, 2.2, 0);
    const pole = mergeGeometries([
      flat(new THREE.CylinderGeometry(0.07, 0.11, 7.5, 6).translate(0, 3.75, 0)),
      flat(box(0.08, 0.08, 1.6, 0, 7.4, 0.75)),
    ])!;
    const lamp = box(0.32, 0.12, 0.6, 0, 7.32, 1.5);
    return { foliage, trunk, pole, lamp, car: carGeometries() };
  }, []);

  const foliageRef = useRef<THREE.InstancedMesh>(null);
  const trunkRef = useRef<THREE.InstancedMesh>(null);
  const poleRef = useRef<THREE.InstancedMesh>(null);
  const lampRef = useRef<THREE.InstancedMesh>(null);
  const carRef = useRef<THREE.InstancedMesh>(null);
  const carDetailRef = useRef<THREE.InstancedMesh>(null);
  useInstances(foliageRef, trees);
  useInstances(trunkRef, trees);
  useInstances(poleRef, lights);
  useInstances(lampRef, lights);
  useInstances(carRef, cars);
  useInstances(carDetailRef, cars);

  if (!props) return null;
  return (
    <group>
      <instancedMesh ref={foliageRef} args={[geometries.foliage, undefined, trees.length]} castShadow receiveShadow>
        <meshStandardMaterial flatShading roughness={0.9} color="#ffffff" />
      </instancedMesh>
      <instancedMesh ref={trunkRef} args={[geometries.trunk, undefined, trees.length]} castShadow>
        <meshStandardMaterial color="#6b5040" roughness={1} />
      </instancedMesh>
      <instancedMesh ref={poleRef} args={[geometries.pole, undefined, lights.length]} castShadow>
        <meshStandardMaterial color="#3b434b" roughness={0.6} metalness={0.4} />
      </instancedMesh>
      <instancedMesh ref={lampRef} args={[geometries.lamp, undefined, lights.length]}>
        <meshStandardMaterial color="#fff3d1" emissive="#ffd892" emissiveIntensity={1.4} />
      </instancedMesh>
      <instancedMesh ref={carRef} args={[geometries.car.body, undefined, cars.length]} castShadow receiveShadow>
        <meshStandardMaterial flatShading roughness={0.35} metalness={0.35} color="#ffffff" />
      </instancedMesh>
      <instancedMesh ref={carDetailRef} args={[geometries.car.detail, undefined, cars.length]} castShadow>
        <meshStandardMaterial color="#1c2630" roughness={0.25} metalness={0.5} />
      </instancedMesh>
    </group>
  );
}

/**
 * Illustrative traffic on the selected corridor centreline. Cars queue (with spacing) before
 * displayed floodwater instead of driving into it; this is NOT a passability or routing claim.
 */
export function CorridorTraffic({
  assets,
  lines,
  mask,
  levelRef,
}: {
  assets: StreetSceneAssets;
  lines: Array<Array<[number, number]>>;
  mask: WaterMask;
  levelRef: React.RefObject<number>;
}) {
  const paths = useMemo(() => {
    const result: Array<{ points: Array<[number, number]>; heights: number[]; length: number; step: number }> = [];
    for (const line of lines) {
      const dense = densifyXZ(line, 4);
      for (const [offset, reverse] of [[-3.4, false], [-7.0, false], [3.4, true], [7.0, true]] as const) {
        const shifted = dense.map(([x, z], i) => {
          const a = dense[Math.max(0, i - 1)];
          const b = dense[Math.min(dense.length - 1, i + 1)];
          const length = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
          return [x + ((b[1] - a[1]) / length) * offset, z - ((b[0] - a[0]) / length) * offset] as [number, number];
        });
        const points = reverse ? shifted.reverse() : shifted;
        const heights = roadProfile(points, assets.heightfield, (x, z) => mask.hydro(x, z));
        const length = polylineLength(points);
        result.push({ points, heights, length, step: length / Math.max(points.length - 1, 1) });
      }
    }
    return result;
  }, [assets, lines, mask]);

  const cars = useMemo(() => {
    const out: Array<{ path: number; s: number; speed: number; color: string }> = [];
    paths.forEach((path, index) => {
      const count = Math.max(1, Math.floor(path.length / 70));
      for (let k = 0; k < count; k += 1) {
        out.push({ path: index, s: (k / count) * path.length + index * 9, speed: 10 + ((index * 7 + k * 3) % 5), color: CAR_COLORS[(index + k * 3) % CAR_COLORS.length] });
      }
    });
    return out;
  }, [paths]);

  const geometry = useMemo(() => carGeometries(), []);
  const bodyRef = useRef<THREE.InstancedMesh>(null);
  const detailRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  useLayoutEffect(() => {
    const color = new THREE.Color();
    cars.forEach((car, index) => bodyRef.current?.setColorAt(index, color.set(car.color)));
    if (bodyRef.current?.instanceColor) bodyRef.current.instanceColor.needsUpdate = true;
  }, [cars]);

  useFrame((_, rawDelta) => {
    const delta = Math.min(rawDelta, 0.1);
    const level = levelRef.current ?? -99;
    const flooded = (x: number, z: number) => mask.flooded(x, z, level);
    const heightAt = (path: (typeof paths)[number], s: number) => {
      const f = Math.min(Math.max(s / path.step, 0), path.heights.length - 1);
      const i = Math.floor(f);
      const t = f - i;
      return path.heights[i] * (1 - t) + (path.heights[Math.min(i + 1, path.heights.length - 1)] ?? path.heights[i]) * t;
    };
    // Order cars on each path so followers keep a gap behind the car ahead.
    const byPath = new Map<number, typeof cars>();
    for (const car of cars) byPath.set(car.path, [...(byPath.get(car.path) ?? []), car]);
    for (const [pathIndex, list] of byPath) {
      const path = paths[pathIndex];
      list.sort((a, b) => a.s - b.s);
      for (let k = list.length - 1; k >= 0; k -= 1) {
        const car = list[k];
        let limit = Infinity;
        if (k < list.length - 1) limit = list[k + 1].s - 9;
        else if (list.length > 1) limit = list[0].s + path.length - 9;
        let next = Math.min(car.s + car.speed * delta, limit);
        const ahead = pointAlong(path.points, (next + 7) % path.length);
        if (flooded(ahead.x, ahead.z)) next = car.s; // hold before displayed water
        car.s = Math.max(car.s, next);
      }
      for (const car of list) if (car.s >= path.length) car.s -= path.length;
    }
    cars.forEach((car, index) => {
      const path = paths[car.path];
      const p = pointAlong(path.points, car.s);
      // A car already standing in water when the level rises is hidden, never drawn driving through it.
      const hidden = flooded(p.x, p.z);
      dummy.position.set(p.x, heightAt(path, car.s) + 0.06, p.z);
      dummy.rotation.set(0, p.heading, 0);
      dummy.scale.setScalar(hidden ? 0.0001 : 1);
      dummy.updateMatrix();
      bodyRef.current?.setMatrixAt(index, dummy.matrix);
      detailRef.current?.setMatrixAt(index, dummy.matrix);
    });
    if (bodyRef.current) bodyRef.current.instanceMatrix.needsUpdate = true;
    if (detailRef.current) detailRef.current.instanceMatrix.needsUpdate = true;
  });

  if (!cars.length) return null;
  return (
    <group>
      <instancedMesh ref={bodyRef} args={[geometry.body, undefined, cars.length]} castShadow frustumCulled={false}>
        <meshStandardMaterial flatShading roughness={0.3} metalness={0.4} color="#ffffff" />
      </instancedMesh>
      <instancedMesh ref={detailRef} args={[geometry.detail, undefined, cars.length]} frustumCulled={false}>
        <meshStandardMaterial color="#1c2630" roughness={0.25} metalness={0.5} />
      </instancedMesh>
    </group>
  );
}
