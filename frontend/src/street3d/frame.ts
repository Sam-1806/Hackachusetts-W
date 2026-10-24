import * as THREE from 'three';
import type { Geometry, Position } from 'geojson';
import type { StreetSceneManifest } from './types';

/** Converts EPSG:4326 lon/lat to the scene's local metre frame (x east, z = -north). */
export class SceneFrame {
  constructor(readonly manifest: StreetSceneManifest) {}

  toXZ(lon: number, lat: number): [number, number] {
    const { x, z } = this.manifest.frame.geo.lonlat_to_xz;
    return [x[0] * lon + x[1] * lat + x[2], z[0] * lon + z[1] * lat + z[2]];
  }

  toLonLat(x: number, z: number): [number, number] {
    const { lon, lat } = this.manifest.frame.geo.xz_to_lonlat;
    return [lon[0] * x + lon[1] * z + lon[2], lat[0] * x + lat[1] * z + lat[2]];
  }

  contains(x: number, z: number, margin = 0): boolean {
    const [x0, z0, x1, z1] = this.manifest.frame.bounds_xz;
    return x >= x0 + margin && x <= x1 - margin && z >= z0 + margin && z <= z1 - margin;
  }

  lineToXZ(coords: Position[]): Array<[number, number]> {
    return coords.map((position) => this.toXZ(position[0], position[1]));
  }
}

/** Official BPDA 2011 terrain, resampled to a regular grid. Heights are metres NAVD88. */
export class Heightfield {
  readonly data: Float32Array;
  readonly width: number;
  readonly height: number;
  readonly res: number;
  readonly x0: number;
  readonly z0: number;

  constructor(buffer: ArrayBuffer, manifest: StreetSceneManifest) {
    const raw = new Uint16Array(buffer);
    this.width = manifest.heightfield.width;
    this.height = manifest.heightfield.height;
    this.res = manifest.heightfield.resolution_m;
    [this.x0, this.z0] = manifest.heightfield.origin_xz;
    this.data = new Float32Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) this.data[i] = raw[i] / 100 - 20;
  }

  sample(x: number, z: number): number {
    const fx = Math.min(Math.max((x - this.x0) / this.res, 0), this.width - 1.001);
    const fz = Math.min(Math.max((z - this.z0) / this.res, 0), this.height - 1.001);
    const ix = Math.floor(fx);
    const iz = Math.floor(fz);
    const tx = fx - ix;
    const tz = fz - iz;
    const row = iz * this.width;
    const a = this.data[row + ix] * (1 - tx) + this.data[row + ix + 1] * tx;
    const b = this.data[row + this.width + ix] * (1 - tx) + this.data[row + this.width + ix + 1] * tx;
    return a * (1 - tz) + b * tz;
  }

  /** Half-float texture (linear filtering works everywhere in WebGL2). */
  toTexture(): THREE.DataTexture {
    const half = new Uint16Array(this.data.length);
    for (let i = 0; i < this.data.length; i += 1) half[i] = THREE.DataUtils.toHalfFloat(this.data[i]);
    const texture = new THREE.DataTexture(half, this.width, this.height, THREE.RedFormat, THREE.HalfFloatType);
    texture.magFilter = THREE.LinearFilter;
    texture.minFilter = THREE.LinearFilter;
    texture.wrapS = THREE.ClampToEdgeWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.needsUpdate = true;
    return texture;
  }

  /** UV transform used by shaders: uv = (xz - origin) / extent. */
  get uvTransform(): THREE.Vector4 {
    return new THREE.Vector4(this.x0, this.z0, (this.width - 1) * this.res, (this.height - 1) * this.res);
  }
}

export function lineStrings(geometry?: Geometry | null): Position[][] {
  if (!geometry) return [];
  if (geometry.type === 'LineString') return [geometry.coordinates];
  if (geometry.type === 'MultiLineString') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') return geometry.geometries.flatMap(lineStrings);
  return [];
}

export function polygonRings(geometry?: Geometry | null): Position[][][] {
  if (!geometry) return [];
  if (geometry.type === 'Polygon') return [geometry.coordinates];
  if (geometry.type === 'MultiPolygon') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') return geometry.geometries.flatMap(polygonRings);
  return [];
}

export function pointPositions(geometry?: Geometry | null): Position[] {
  if (!geometry) return [];
  if (geometry.type === 'Point') return [geometry.coordinates];
  if (geometry.type === 'MultiPoint') return geometry.coordinates;
  if (geometry.type === 'GeometryCollection') return geometry.geometries.flatMap(pointPositions);
  return [];
}

/** Resample a polyline at a fixed spacing (metres) so it can follow terrain. */
export function densifyXZ(points: Array<[number, number]>, step: number): Array<[number, number]> {
  if (points.length < 2) return points;
  const out: Array<[number, number]> = [points[0]];
  for (let i = 1; i < points.length; i += 1) {
    const [ax, az] = points[i - 1];
    const [bx, bz] = points[i];
    const count = Math.max(1, Math.ceil(Math.hypot(bx - ax, bz - az) / step));
    for (let k = 1; k <= count; k += 1) out.push([ax + ((bx - ax) * k) / count, az + ((bz - az) * k) / count]);
  }
  return out;
}

export function polylineLength(points: Array<[number, number]>): number {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) total += Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
  return total;
}

/** Position and heading at a distance along a polyline. */
export function pointAlong(points: Array<[number, number]>, distance: number): { x: number; z: number; heading: number } {
  let remaining = distance;
  for (let i = 1; i < points.length; i += 1) {
    const [ax, az] = points[i - 1];
    const [bx, bz] = points[i];
    const length = Math.hypot(bx - ax, bz - az);
    if (remaining <= length || i === points.length - 1) {
      const t = length === 0 ? 0 : Math.min(remaining / length, 1);
      return { x: ax + (bx - ax) * t, z: az + (bz - az) * t, heading: Math.atan2(bx - ax, bz - az) };
    }
    remaining -= length;
  }
  const [x, z] = points[points.length - 1] ?? [0, 0];
  return { x, z, heading: 0 };
}

/**
 * Terrain heights along a road polyline. Where the line crosses official hydrography (a bridge),
 * the 2011 TIN only has the water fill, so short runs are bridged by linear interpolation between
 * the abutments. Display only: not a surveyed deck profile.
 */
export function roadProfile(
  points: Array<[number, number]>,
  heightfield: Heightfield,
  overWater: (x: number, z: number) => boolean,
  maxBridgeM = 300,
): number[] {
  const heights = points.map(([x, z]) => heightfield.sample(x, z));
  const wet = points.map(([x, z]) => overWater(x, z));
  let i = 0;
  while (i < points.length) {
    if (!wet[i]) { i += 1; continue; }
    let j = i;
    while (j < points.length && wet[j]) j += 1;
    const before = i - 1;
    const after = j < points.length ? j : -1;
    let span = 0;
    for (let k = Math.max(i, 1); k < Math.min(j + 1, points.length); k += 1) span += Math.hypot(points[k][0] - points[k - 1][0], points[k][1] - points[k - 1][1]);
    if (span <= maxBridgeM && (before >= 0 || after >= 0)) {
      const h0 = before >= 0 ? heights[before] : heights[after];
      const h1 = after >= 0 ? heights[after] : heights[before];
      for (let k = i; k < j; k += 1) {
        const t = (k - i + 1) / (j - i + 1);
        heights[k] = h0 + (h1 - h0) * t;
      }
    }
    i = j;
  }
  return heights;
}
