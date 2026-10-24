import { useEffect, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Heightfield, SceneFrame } from './frame';
import type { BuildingRecord, StreetPropsFile, StreetSceneManifest } from './types';

export interface StreetSceneAssets {
  manifest: StreetSceneManifest;
  frame: SceneFrame;
  heightfield: Heightfield;
  heightTexture: THREE.DataTexture;
  terrain: Array<{ tileId: string; geometry: THREE.BufferGeometry; texture: THREE.Texture }>;
  buildings: THREE.BufferGeometry;
  buildingRecords: BuildingRecord[];
  streets: Record<string, THREE.BufferGeometry>;
  props: StreetPropsFile | null;
}

type LoadState =
  | { status: 'loading'; progress: number; detail: string }
  | { status: 'ready'; assets: StreetSceneAssets }
  | { status: 'error'; message: string };

const cache = new Map<string, Promise<StreetSceneAssets>>();

function meshesByName(gltf: { scene: THREE.Object3D }): Record<string, THREE.BufferGeometry> {
  const out: Record<string, THREE.BufferGeometry> = {};
  gltf.scene.traverse((object) => {
    if ((object as THREE.Mesh).isMesh) out[object.name] = (object as THREE.Mesh).geometry;
  });
  return out;
}

async function load(manifestUrl: string, onProgress: (progress: number, detail: string) => void): Promise<StreetSceneAssets> {
  const base = manifestUrl.slice(0, manifestUrl.lastIndexOf('/') + 1);
  const manifestResponse = await fetch(manifestUrl);
  if (!manifestResponse.ok) throw new Error(`Scene manifest missing (${manifestResponse.status}). Run analysis/scene/build_bpda_scene.py.`);
  const manifest = (await manifestResponse.json()) as StreetSceneManifest;
  const frame = new SceneFrame(manifest);
  const loader = new GLTFLoader();
  const textureLoader = new THREE.TextureLoader();
  const steps = 6;
  let done = 0;
  const tick = (detail: string) => onProgress(++done / steps, detail);

  const [heightBuffer, terrainGltf, buildingsGltf, buildingRecords, streetsGltf, props, textures] = await Promise.all([
    fetch(base + manifest.heightfield.file).then((r) => r.arrayBuffer()).then((b) => { tick('Terrain heights'); return b; }),
    loader.loadAsync(base + manifest.layers.terrain.file).then((g) => { tick('Terrain mesh'); return g; }),
    loader.loadAsync(base + manifest.layers.buildings.file).then((g) => { tick('Building models'); return g; }),
    fetch(base + manifest.layers.buildings.records).then((r) => r.json() as Promise<BuildingRecord[]>),
    manifest.layers.streets ? loader.loadAsync(base + manifest.layers.streets.file).then((g) => { tick('Streets'); return g; }) : Promise.resolve(null),
    manifest.layers.props ? fetch(base + manifest.layers.props.file).then((r) => r.json() as Promise<StreetPropsFile>) : Promise.resolve(null),
    Promise.all(Object.entries(manifest.layers.terrain.textures).map(async ([tileId, file]) => {
      const texture = await textureLoader.loadAsync(base + file);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.flipY = false; // UVs are written in glTF (top-left) convention.
      texture.anisotropy = 8;
      return [tileId, texture] as const;
    })).then((t) => { tick('Groundplan imagery'); return t; }),
  ]);

  const heightfield = new Heightfield(heightBuffer, manifest);
  const terrainMeshes = meshesByName(terrainGltf);
  const textureMap = Object.fromEntries(textures);
  const terrain = Object.keys(manifest.layers.terrain.textures).map((tileId) => {
    const geometry = terrainMeshes[`terrain_${tileId}`];
    geometry.computeVertexNormals();
    return { tileId, geometry, texture: textureMap[tileId] };
  });
  const buildings = meshesByName(buildingsGltf).buildings;
  // Flat-shaded material derives normals in the fragment shader; no normal attribute needed.
  buildings.computeBoundingSphere();
  const streets = streetsGltf ? meshesByName(streetsGltf) : {};
  for (const geometry of Object.values(streets)) geometry.computeVertexNormals();
  tick('Ready');

  return {
    manifest,
    frame,
    heightfield,
    heightTexture: heightfield.toTexture(),
    terrain,
    buildings,
    buildingRecords,
    streets,
    props,
  };
}

export function useStreetSceneAssets(manifestUrl: string): LoadState {
  const [state, setState] = useState<LoadState>({ status: 'loading', progress: 0, detail: 'Loading official Boston 3D model…' });

  useEffect(() => {
    let cancelled = false;
    let promise = cache.get(manifestUrl);
    if (!promise) {
      promise = load(manifestUrl, (progress, detail) => {
        if (!cancelled) setState({ status: 'loading', progress, detail });
      });
      cache.set(manifestUrl, promise);
      promise.catch(() => cache.delete(manifestUrl));
    }
    promise
      .then((assets) => { if (!cancelled) setState({ status: 'ready', assets }); })
      .catch((error: unknown) => { if (!cancelled) setState({ status: 'error', message: error instanceof Error ? error.message : String(error) }); });
    return () => { cancelled = true; };
  }, [manifestUrl]);

  return state;
}
