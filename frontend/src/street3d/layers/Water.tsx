import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { polygonRings } from '../frame';
import type { StreetSceneAssets } from '../useStreetSceneAssets';
import type { StreetWater } from '../types';

const MASK_PX_PER_M = 0.5;
const NEVER = 1000; // spill level for footprint cells with no connection to the harbour

/** Minimal binary min-heap keyed by float, storing integer cell indices. */
class CellHeap {
  private keys: Float32Array;
  private cells: Int32Array;
  size = 0;
  constructor(capacity: number) {
    this.keys = new Float32Array(capacity);
    this.cells = new Int32Array(capacity);
  }
  push(key: number, cell: number) {
    if (this.size === this.keys.length) {
      const keys = new Float32Array(this.keys.length * 2); keys.set(this.keys); this.keys = keys;
      const cells = new Int32Array(this.cells.length * 2); cells.set(this.cells); this.cells = cells;
    }
    let i = this.size++;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (this.keys[parent] <= key) break;
      this.keys[i] = this.keys[parent]; this.cells[i] = this.cells[parent]; i = parent;
    }
    this.keys[i] = key; this.cells[i] = cell;
  }
  pop(): [number, number] {
    const topKey = this.keys[0];
    const topCell = this.cells[0];
    const key = this.keys[--this.size];
    const cell = this.cells[this.size];
    let i = 0;
    for (;;) {
      let child = 2 * i + 1;
      if (child >= this.size) break;
      if (child + 1 < this.size && this.keys[child + 1] < this.keys[child]) child += 1;
      if (this.keys[child] >= key) break;
      this.keys[i] = this.keys[child]; this.cells[i] = this.cells[child]; i = child;
    }
    this.keys[i] = key; this.cells[i] = cell;
    return [topKey, topCell];
  }
}

/**
 * CPU + GPU mask of where water may be drawn:
 *  R = official BPDA hydrography (harbour, coves),  G = sourced flood footprint.
 * Water is never drawn outside these polygons, so the scene never invents inland flooding.
 */
export class WaterMask {
  readonly canvas: HTMLCanvasElement;
  readonly texture: THREE.CanvasTexture;
  private pixels: Uint8ClampedArray | null = null;
  /**
   * Connected-fill "spill level" per heightfield cell (metres NAVD88): the lowest water level at
   * which the cell joins the harbour through footprint cells that are already under water.
   */
  spill: Float32Array | null = null;
  readonly spillTexture: THREE.DataTexture;
  /** True when the displayed level is at the reported peak: show the whole sourced footprint. */
  fullFootprint = false;
  private readonly x0: number;
  private readonly z0: number;
  private readonly w: number;
  private readonly h: number;

  constructor(private readonly assets: StreetSceneAssets) {
    const [x0, z0, x1, z1] = assets.manifest.frame.bounds_xz;
    this.x0 = x0;
    this.z0 = z0;
    this.w = Math.ceil((x1 - x0) * MASK_PX_PER_M);
    this.h = Math.ceil((z1 - z0) * MASK_PX_PER_M);
    this.canvas = document.createElement('canvas');
    this.canvas.width = this.w;
    this.canvas.height = this.h;
    this.texture = new THREE.CanvasTexture(this.canvas);
    this.texture.flipY = false;
    this.texture.minFilter = THREE.LinearFilter;
    this.texture.magFilter = THREE.LinearFilter;
    this.texture.generateMipmaps = false;
    const hf = assets.heightfield;
    this.spillTexture = new THREE.DataTexture(new Uint16Array(hf.width * hf.height), hf.width, hf.height, THREE.RedFormat, THREE.HalfFloatType);
    this.spillTexture.magFilter = THREE.NearestFilter;
    this.spillTexture.minFilter = THREE.NearestFilter;
    this.draw(null); // hydrography is static; available immediately for road profiles
  }

  get transform(): THREE.Vector4 {
    return new THREE.Vector4(this.x0, this.z0, this.w / MASK_PX_PER_M, this.h / MASK_PX_PER_M);
  }

  draw(flood: StreetWater['flood']) {
    const context = this.canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return;
    context.globalCompositeOperation = 'source-over';
    context.fillStyle = '#000';
    context.fillRect(0, 0, this.w, this.h);
    context.globalCompositeOperation = 'lighter';
    const harbour = this.assets.streets.harbor_mask;
    if (harbour) {
      const position = harbour.getAttribute('position');
      const index = harbour.getIndex();
      context.fillStyle = '#ff0000';
      context.strokeStyle = '#ff0000';
      context.lineWidth = 1;
      context.beginPath();
      const count = index ? index.count : position.count;
      for (let i = 0; i < count; i += 3) {
        for (let k = 0; k < 3; k += 1) {
          const v = index ? index.getX(i + k) : i + k;
          const px = (position.getX(v) - this.x0) * MASK_PX_PER_M;
          const pz = (position.getZ(v) - this.z0) * MASK_PX_PER_M;
          if (k === 0) context.moveTo(px, pz); else context.lineTo(px, pz);
        }
        context.closePath();
      }
      context.fill();
      context.stroke();
    }
    if (flood) {
      context.fillStyle = '#00ff00';
      context.beginPath();
      for (const feature of flood.data.features) {
        for (const polygon of polygonRings(feature.geometry)) {
          for (const ring of polygon) {
            ring.forEach((position, i) => {
              const [x, z] = this.assets.frame.toXZ(position[0], position[1]);
              const px = (x - this.x0) * MASK_PX_PER_M;
              const pz = (z - this.z0) * MASK_PX_PER_M;
              if (i === 0) context.moveTo(px, pz); else context.lineTo(px, pz);
            });
            context.closePath();
          }
        }
      }
      context.fill('evenodd');
    }
    this.pixels = context.getImageData(0, 0, this.w, this.h).data;
    this.texture.needsUpdate = true;
    this.computeSpill(Boolean(flood));
  }

  /**
   * Priority-flood from the harbour across footprint cells (4-connected). A cell's spill level is
   * max(its terrain, the lowest spill level among the paths reaching it). Water drawn at level L
   * therefore spreads from the shoreline and only reaches cells with spill < L. Display method
   * only ("connected bathtub"): no velocities, timing or drainage pathways are modelled.
   */
  private computeSpill(hasFlood: boolean) {
    const hf = this.assets.heightfield;
    const n = hf.width * hf.height;
    const spill = new Float32Array(n).fill(NEVER);
    if (hasFlood && this.pixels) {
      const kind = new Uint8Array(n); // 0 = outside, 1 = harbour, 2 = footprint on land
      for (let iz = 0; iz < hf.height; iz += 1) {
        for (let ix = 0; ix < hf.width; ix += 1) {
          const offset = this.offset(hf.x0 + ix * hf.res, hf.z0 + iz * hf.res);
          if (offset < 0) continue;
          if (this.pixels[offset] > 127) kind[iz * hf.width + ix] = 1;
          else if (this.pixels[offset + 1] > 127) kind[iz * hf.width + ix] = 2;
        }
      }
      const heap = new CellHeap(1 << 16);
      const neighbours = [1, -1, hf.width, -hf.width];
      for (let i = 0; i < n; i += 1) {
        if (kind[i] !== 1) continue;
        spill[i] = -100;
        const x = i % hf.width;
        for (const d of neighbours) {
          const j = i + d;
          if (j < 0 || j >= n || (d === 1 && x === hf.width - 1) || (d === -1 && x === 0)) continue;
          if (kind[j] === 2) { heap.push(-100, i); break; }
        }
      }
      while (heap.size) {
        const [level, i] = heap.pop();
        const x = i % hf.width;
        for (const d of neighbours) {
          const j = i + d;
          if (j < 0 || j >= n || (d === 1 && x === hf.width - 1) || (d === -1 && x === 0)) continue;
          if (kind[j] !== 2 || spill[j] !== NEVER) continue;
          spill[j] = Math.max(hf.data[j], level);
          heap.push(spill[j], j);
        }
      }
    }
    this.spill = hasFlood ? spill : null;
    const data = this.spillTexture.image.data as Uint16Array;
    for (let i = 0; i < n; i += 1) data[i] = THREE.DataUtils.toHalfFloat(spill[i]);
    this.spillTexture.needsUpdate = true;
  }

  /** Whether displayed floodwater (connected fill, or full footprint at peak) covers this land point. */
  flooded(x: number, z: number, level: number): boolean {
    if (!this.floodLand(x, z)) return false;
    const hf = this.assets.heightfield;
    if (hf.sample(x, z) >= level) return false;
    if (this.fullFootprint) return true;
    if (!this.spill) return false;
    const ix = Math.round((x - hf.x0) / hf.res);
    const iz = Math.round((z - hf.z0) / hf.res);
    if (ix < 0 || iz < 0 || ix >= hf.width || iz >= hf.height) return false;
    return this.spill[iz * hf.width + ix] < level;
  }

  /**
   * Height of the 2011 terrain's flat water fill inside official hydrography. The TIN carries
   * no bathymetry there, so the harbour surface is never drawn below this (plus a few cm).
   */
  hydroFill(heightfield: { width: number; height: number; res: number; x0: number; z0: number; data: Float32Array }): number {
    if (!this.pixels) return 0;
    const values: number[] = [];
    for (let iz = 0; iz < heightfield.height; iz += 3) {
      for (let ix = 0; ix < heightfield.width; ix += 3) {
        const x = heightfield.x0 + ix * heightfield.res;
        const z = heightfield.z0 + iz * heightfield.res;
        const px = Math.floor((x - this.x0) * MASK_PX_PER_M);
        const pz = Math.floor((z - this.z0) * MASK_PX_PER_M);
        if (px < 1 || pz < 1 || px >= this.w - 1 || pz >= this.h - 1) continue;
        // Interior only: all four neighbours inside the hydrography mask.
        const at = (dx: number, dz: number) => this.pixels![((pz + dz) * this.w + px + dx) * 4];
        if (at(0, 0) > 250 && at(1, 0) > 250 && at(-1, 0) > 250 && at(0, 1) > 250 && at(0, -1) > 250) {
          values.push(heightfield.data[iz * heightfield.width + ix]);
        }
      }
    }
    if (!values.length) return 0;
    values.sort((a, b) => a - b);
    return values[Math.floor(values.length * 0.97)];
  }

  /** Inside official hydrography (harbour, coves) — e.g. under a bridge. */
  hydro(x: number, z: number): boolean {
    const offset = this.offset(x, z);
    return offset >= 0 && this.pixels![offset] > 127;
  }

  /** Inside the sourced flood footprint on land (outside hydrography). */
  floodLand(x: number, z: number): boolean {
    const offset = this.offset(x, z);
    return offset >= 0 && this.pixels![offset + 1] > 127 && this.pixels![offset] <= 127;
  }

  private offset(x: number, z: number): number {
    if (!this.pixels) return -1;
    const px = Math.floor((x - this.x0) * MASK_PX_PER_M);
    const pz = Math.floor((z - this.z0) * MASK_PX_PER_M);
    if (px < 0 || pz < 0 || px >= this.w || pz >= this.h) return -1;
    return (pz * this.w + px) * 4;
  }

  /** True if water may be drawn here (harbour or footprint). */
  wet(x: number, z: number): boolean {
    if (!this.pixels) return false;
    const px = Math.floor((x - this.x0) * MASK_PX_PER_M);
    const pz = Math.floor((z - this.z0) * MASK_PX_PER_M);
    if (px < 0 || pz < 0 || px >= this.w || pz >= this.h) return false;
    const offset = (pz * this.w + px) * 4;
    return this.pixels[offset] > 127 || this.pixels[offset + 1] > 127;
  }
}

const vertexShader = /* glsl */ `
#include <common>
#include <fog_pars_vertex>
varying vec3 vWorld;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  vec4 mvPosition = viewMatrix * world;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

const fragmentShader = /* glsl */ `
#include <common>
#include <fog_pars_fragment>
uniform sampler2D uHeight;
uniform vec4 uHeightXform;
uniform sampler2D uMask;
uniform vec4 uMaskXform;
uniform float uLevel;
uniform float uTime;
uniform float uFloodOn;
uniform float uMode; // 0 = harbour (official hydrography), 1 = flood footprint on land
uniform sampler2D uSpill;
uniform float uFullFootprint;
uniform vec3 uSunDir;
uniform vec3 uSky;
uniform vec3 uHorizon;
varying vec3 vWorld;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float waves(vec2 p) {
  float t = uTime;
  float h = 0.0;
  h += noise(p * 0.08 + vec2(t * 0.05, t * 0.03)) * 0.55;
  h += noise(p * 0.21 - vec2(t * 0.09, -t * 0.06)) * 0.28;
  h += noise(p * 0.55 + vec2(-t * 0.16, t * 0.11)) * 0.12;
  h += noise(p * 1.4 + vec2(t * 0.3, t * 0.25)) * 0.05;
  return h;
}

void main() {
  vec2 hUv = (vWorld.xz - uHeightXform.xy) / uHeightXform.zw;
  vec2 mUv = (vWorld.xz - uMaskXform.xy) / uMaskXform.zw;
  vec4 mask = texture2D(uMask, mUv);
  float hydro = mask.r;
  float ground = texture2D(uHeight, hUv).r;
  float depth;
  float shoreFoam;
  if (uMode < 0.5) {
    // Harbour: no bathymetry was loaded, so draw a nominal-depth surface everywhere inside hydrography.
    if (hydro < 0.5) discard;
    depth = 1.6 + max(uLevel - ground, 0.0);
    shoreFoam = 1.0 - smoothstep(0.5, 0.72, hydro);
  } else {
    // Flood: only inside the sourced footprint, outside hydrography, where terrain is below the level.
    if (uFloodOn < 0.5 || mask.g < 0.5 || hydro >= 0.5) discard;
    depth = uLevel - ground;
    if (depth <= 0.0) discard;
    float spill = texture2D(uSpill, hUv).r;
    if (uFullFootprint < 0.5 && spill >= uLevel) discard; // not yet connected to the harbour
    // Foam at the terrain edge and along the advancing front of the connected fill.
    float front = uFullFootprint > 0.5 ? 0.0 : 1.0 - smoothstep(0.0, 0.06, uLevel - spill);
    shoreFoam = max(1.0 - smoothstep(0.0, 0.10, depth), front);
  }
  float inland = uMode;

  // Analytic normal from layered value noise (visual ripples only).
  float e = 0.35;
  float hC = waves(vWorld.xz);
  float hX = waves(vWorld.xz + vec2(e, 0.0));
  float hZ = waves(vWorld.xz + vec2(0.0, e));
  float calm = mix(0.55, 1.0, smoothstep(0.0, 1.2, depth));
  vec3 n = normalize(vec3((hC - hX) * 2.2 * calm, 1.0, (hC - hZ) * 2.2 * calm));

  vec3 viewDir = normalize(cameraPosition - vWorld);
  float fresnel = 0.04 + 0.96 * pow(1.0 - clamp(dot(n, viewDir), 0.0, 1.0), 5.0);
  vec3 reflected = reflect(-viewDir, n);
  vec3 skyCol = mix(uHorizon, uSky, clamp(reflected.y * 1.6, 0.0, 1.0));

  // Depth cues: shallow sheet over pavement is clear/murky, deep harbour is blue-green.
  vec3 deep = vec3(0.02, 0.19, 0.30);
  vec3 mid = vec3(0.05, 0.40, 0.50);
  vec3 shallowSea = vec3(0.28, 0.64, 0.66);
  vec3 shallowFlood = vec3(0.16, 0.44, 0.50);
  vec3 shallow = mix(shallowSea, shallowFlood, inland);
  vec3 body = mix(shallow, mid, smoothstep(0.0, 1.0, depth));
  body = mix(body, deep, smoothstep(1.0, 5.0, depth));

  float sunSpec = pow(max(dot(reflected, normalize(uSunDir)), 0.0), 220.0) * 2.4;
  vec3 color = mix(body, skyCol, fresnel * mix(0.55, 0.3, inland)) + vec3(1.0, 0.95, 0.85) * sunSpec;

  // Shoreline foam where the water surface meets official terrain.
  float foamBand = shoreFoam;
  float foamNoise = noise(vWorld.xz * 1.8 + uTime * 0.6);
  color = mix(color, vec3(0.93, 0.95, 0.94), foamBand * smoothstep(0.35, 0.75, foamNoise) * 0.85);

  float alpha = mix(mix(0.6, 0.8, inland), 0.93, smoothstep(0.0, 1.0, depth));
  alpha = max(alpha, fresnel * 0.9);
  gl_FragColor = vec4(color, alpha);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  #include <fog_fragment>
}`;

function makeWaterMaterial() {
  return new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    fog: true,
    uniforms: THREE.UniformsUtils.merge([
      THREE.UniformsLib.fog,
      {
        uHeight: { value: null },
        uHeightXform: { value: new THREE.Vector4() },
        uMask: { value: null },
        uMaskXform: { value: new THREE.Vector4() },
        uLevel: { value: 0 },
        uTime: { value: 0 },
        uFloodOn: { value: 0 },
        uMode: { value: 0 },
        uSpill: { value: null },
        uFullFootprint: { value: 0 },
        uSunDir: { value: new THREE.Vector3(0.5, 0.8, 0.3) },
        uSky: { value: new THREE.Color('#7fa8d1') },
        uHorizon: { value: new THREE.Color('#d9e6ee') },
      },
    ]),
  });
}

export function Water({ assets, mask, water, sunDirection, hydroFillM }: {
  assets: StreetSceneAssets;
  mask: WaterMask;
  water: StreetWater;
  sunDirection: THREE.Vector3;
  hydroFillM: number;
}) {
  const [x0, z0, x1, z1] = assets.manifest.frame.bounds_xz;
  const geometry = useMemo(() => {
    const plane = new THREE.PlaneGeometry(x1 - x0, z1 - z0, 1, 1);
    plane.rotateX(-Math.PI / 2);
    plane.translate((x0 + x1) / 2, 0, (z0 + z1) / 2);
    return plane;
  }, [x0, x1, z0, z1]);

  const harbour = useMemo(makeWaterMaterial, []);
  const flood = useMemo(() => {
    const material = makeWaterMaterial();
    material.uniforms.uMode.value = 1;
    return material;
  }, []);
  const materials = useMemo(() => [harbour, flood], [harbour, flood]);

  useEffect(() => {
    for (const material of materials) {
      material.uniforms.uHeight.value = assets.heightTexture;
      material.uniforms.uHeightXform.value = assets.heightfield.uvTransform;
      material.uniforms.uMask.value = mask.texture;
      material.uniforms.uMaskXform.value = mask.transform;
      material.uniforms.uSpill.value = mask.spillTexture;
    }
  }, [assets, mask, materials]);

  const floodLevel = water.mode === 'none' || water.displayedLevelM == null ? water.harbourLevelM : water.displayedLevelM;
  // The harbour surface never drops below the terrain's flat water fill (no bathymetry loaded).
  const harbourFloor = hydroFillM + 0.06;
  useEffect(() => {
    const storm = water.mode !== 'none';
    for (const material of materials) {
      material.uniforms.uFloodOn.value = storm ? 1 : 0;
      material.uniforms.uSunDir.value.copy(sunDirection);
      (material.uniforms.uSky.value as THREE.Color).set(storm ? '#7f8c96' : '#7fa8d1');
      (material.uniforms.uHorizon.value as THREE.Color).set(storm ? '#a3afb7' : '#d9e6ee');
    }
  }, [materials, water.mode, sunDirection]);

  const harbourRef = useRef<THREE.Mesh>(null);
  const floodRef = useRef<THREE.Mesh>(null);
  const eased = useRef<number | null>(null);
  useFrame((_, rawDelta) => {
    const delta = Math.min(rawDelta, 0.1);
    // Ease toward the requested level so hourly gauge steps read as a smooth rise/fall.
    const current = eased.current ?? floodLevel;
    const next = current + (floodLevel - current) * Math.min(1, delta * 2.5);
    eased.current = next;
    const harbourLevel = Math.max(next, harbourFloor);
    // At the reported peak, show the whole sourced footprint (including pockets not connected at lower levels).
    const full = water.mode === 'peak' || (water.peakSurfaceM != null && next >= water.peakSurfaceM - 0.01);
    mask.fullFootprint = full;
    flood.uniforms.uFullFootprint.value = full ? 1 : 0;
    harbour.uniforms.uTime.value += delta;
    flood.uniforms.uTime.value = harbour.uniforms.uTime.value;
    harbour.uniforms.uLevel.value = harbourLevel;
    flood.uniforms.uLevel.value = next;
    if (harbourRef.current) harbourRef.current.position.y = harbourLevel;
    if (floodRef.current) floodRef.current.position.y = next;
  });

  return (
    <>
      <mesh ref={harbourRef} geometry={geometry} material={harbour} renderOrder={5} frustumCulled={false} />
      <mesh ref={floodRef} geometry={geometry} material={flood} renderOrder={6} frustumCulled={false} />
    </>
  );
}
