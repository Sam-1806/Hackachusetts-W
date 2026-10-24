import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { StreetSceneAssets } from '../useStreetSceneAssets';

/** Official BPDA 2011 terrain TIN skinned with the official 2011 planimetric groundplan. */
export function Terrain({ assets, registerMesh }: { assets: StreetSceneAssets; registerMesh: (mesh: THREE.Mesh | null, key: string) => void }) {
  const materials = useMemo(
    () => assets.terrain.map(({ texture }) => {
      const material = new THREE.MeshStandardMaterial({ map: texture, roughness: 0.96, metalness: 0 });
      // Gentle grade so the pastel groundplan reads as a stylised, sunlit ground.
      material.color = new THREE.Color('#cdc6b4');
      return material;
    }),
    [assets],
  );
  return (
    <group>
      {assets.terrain.map((tile, index) => (
        <mesh
          key={tile.tileId}
          ref={(mesh) => registerMesh(mesh, `terrain:${tile.tileId}`)}
          geometry={tile.geometry}
          material={materials[index]}
          receiveShadow
        />
      ))}
    </group>
  );
}

const STREET_STYLE: Record<string, { color: string; roughness: number; offset: number }> = {
  road: { color: '#4a4f57', roughness: 0.82, offset: -2 },
  parking: { color: '#5b6067', roughness: 0.86, offset: -2 },
  driveway: { color: '#6d7075', roughness: 0.9, offset: -2 },
  sidewalk: { color: '#d4cdbf', roughness: 0.93, offset: -3 },
  curb: { color: '#b8b1a4', roughness: 0.9, offset: -3 },
  marking: { color: '#f6f3e8', roughness: 0.6, offset: -6 },
};

/** Official BPDA groundplan roads, sidewalks (with curbs), parking and pavement markings. */
export function Streets({ assets }: { assets: StreetSceneAssets }) {
  const materials = useMemo(() => Object.fromEntries(
    Object.entries(STREET_STYLE).map(([key, style]) => [key, new THREE.MeshStandardMaterial({
      color: style.color,
      roughness: style.roughness,
      metalness: 0,
      polygonOffset: true,
      polygonOffsetFactor: style.offset,
      polygonOffsetUnits: style.offset,
      emissive: key === 'marking' ? new THREE.Color('#2b2b26') : new THREE.Color('#000000'),
      side: key === 'curb' ? THREE.DoubleSide : THREE.FrontSide,
      flatShading: key === 'curb',
    })]),
  ), []);
  return (
    <group>
      {Object.entries(assets.streets)
        .filter(([key]) => key in STREET_STYLE)
        .map(([key, geometry]) => (
          <mesh key={key} geometry={geometry} material={materials[key]} receiveShadow castShadow={key === 'curb'} />
        ))}
    </group>
  );
}

const PALETTE = ['#e8dccb', '#d9c2a7', '#c98f6f', '#b9b4aa', '#e3e0d6', '#a9785f', '#cfd3d1', '#d8b98f', '#9fa8ab', '#efe7d8'];
const KIND_INDEX: Record<string, number> = { Building: 0, Wall: 1, Dock: 2, Bridge: 3 };

/**
 * Official BPDA building models (LOD 1–3). Facade windows are a stylised shader effect
 * derived from world position — they are not surveyed openings.
 */
export function Buildings({
  assets,
  heightTexture,
  selectedFeature,
  registerMesh,
}: {
  assets: StreetSceneAssets;
  heightTexture: THREE.DataTexture;
  selectedFeature: number | null;
  registerMesh: (mesh: THREE.Mesh | null, key: string) => void;
}) {
  const geometry = assets.buildings;

  useMemo(() => {
    const ids = geometry.getAttribute('_feature_id') as THREE.BufferAttribute;
    const colors = new Float32Array(ids.count * 3);
    const kinds = new Float32Array(ids.count);
    const color = new THREE.Color();
    for (let i = 0; i < ids.count; i += 1) {
      const record = assets.buildingRecords[ids.getX(i)];
      const kind = KIND_INDEX[record?.struct_type ?? 'Building'] ?? 0;
      kinds[i] = kind;
      if (kind === 1) color.set('#9a958c');
      else if (kind === 2) color.set('#8a6a4e');
      else if (kind === 3) color.set('#a7a49c');
      else color.set(PALETTE[(record?.feature_id ?? 0) * 7 % PALETTE.length]);
      colors.set([color.r, color.g, color.b], i * 3);
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('aKind', new THREE.BufferAttribute(kinds, 1));
  }, [assets, geometry]);

  const material = useMemo(() => {
    const mat = new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.78, metalness: 0.02 });
    const uniforms = {
      uHeight: { value: heightTexture },
      uHeightXform: { value: assets.heightfield.uvTransform },
      uSelected: { value: -1 },
    };
    mat.userData.uniforms = uniforms;
    mat.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, uniforms);
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', `#include <common>
attribute float aKind;
attribute float _feature_id;
varying vec3 vWorldPos;
varying float vKind;
varying float vFeature;`)
        .replace('#include <worldpos_vertex>', `#include <worldpos_vertex>
vWorldPos = (modelMatrix * vec4(transformed, 1.0)).xyz;
vKind = aKind;
vFeature = _feature_id;`);
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', `#include <common>
uniform sampler2D uHeight;
uniform vec4 uHeightXform;
uniform float uSelected;
varying vec3 vWorldPos;
varying float vKind;
varying float vFeature;`)
        .replace('#include <color_fragment>', `#include <color_fragment>
vec3 wn = normalize(cross(dFdx(vWorldPos), dFdy(vWorldPos)));
float ground = texture2D(uHeight, (vWorldPos.xz - uHeightXform.xy) / uHeightXform.zw).r;
float above = vWorldPos.y - ground;
bool isWall = abs(wn.y) < 0.3;
bool isRoof = wn.y > 0.6 || wn.y < -0.6;
if (vKind < 0.5 && isWall && above > 3.2) {
  vec2 tangent = normalize(vec2(-wn.z, wn.x));
  float along = dot(vWorldPos.xz, tangent);
  float bay = fract(along / 3.1);
  float storey = fract((above - 0.4) / 3.35);
  float win = step(0.22, bay) * step(bay, 0.78) * step(0.28, storey) * step(storey, 0.82);
  vec3 glass = mix(vec3(0.20, 0.27, 0.33), vec3(0.42, 0.52, 0.60), smoothstep(0.28, 0.82, storey));
  diffuseColor.rgb = mix(diffuseColor.rgb, glass, win * 0.88);
  // Subtle floor-line bands.
  diffuseColor.rgb *= 1.0 - 0.08 * (1.0 - step(0.06, storey));
}
if (isRoof) diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.62, 0.63, 0.62), 0.45);
// Ground contact darkening (cheap ambient occlusion at the street).
diffuseColor.rgb *= mix(0.62, 1.0, smoothstep(0.0, 4.0, above));
if (abs(vFeature - uSelected) < 0.5) diffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.0, 0.78, 0.3), 0.7);`);
    };
    return mat;
  }, [assets, heightTexture]);

  useEffect(() => {
    (material.userData.uniforms as { uSelected: { value: number } }).uSelected.value = selectedFeature ?? -1;
  }, [material, selectedFeature]);

  return (
    <mesh
      ref={(mesh) => registerMesh(mesh, 'buildings')}
      geometry={geometry}
      material={material}
      castShadow
      receiveShadow
    />
  );
}
