#!/usr/bin/env python3
"""Build a browser-ready 3D street scene from the official Boston 3D city model.

Source: Boston Planning Department (BPDA) 3D Smart Model, published per 5,000 ft
tile under the Open Data Commons PDDL licence:
https://www.bostonplans.org/3d-data-maps/3d-smart-model/3d-data-download

Inputs per tile (downloaded and cached):
  * Terrain mesh (2011 TIN, OBJ) with the 2011 planimetric groundplan texture.
  * Building model collection (OBJ per structure, CyberCity3D / pbcGIS LOD 1-3).
  * Vector groundplan (DXF): road polygons, sidewalks, pavement markings, parking,
    hydrography.

Coordinates: BPDA "Metro Boston 3D" local feet, i.e. NAD83 / Massachusetts
Mainland (ftUS, EPSG:2249) minus the documented origin (731,100 ; 2,902,900).
Heights are NAVD88 feet. Output uses a local right-handed metre frame for
three.js: x = east, y = up (metres NAVD88), z = -north, around ``SCENE_ORIGIN``.

What this script does NOT do: it does not invent buildings, terrain, roads or
water. Street props (trees, lights, parked cars) are written to a separate,
explicitly ``illustrative`` file because no location-specific inventory was
loaded.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import struct
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import ezdxf
    import shapely
    import shapely.prepared
    from PIL import Image
    from pyproj import Transformer
    from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
    from shapely.ops import unary_union
except ImportError as error:  # pragma: no cover - environment guidance
    sys.exit(f'Missing dependency ({error}). pip install -r analysis/scene/requirements.txt')

BPDA_BASE = 'https://maps.bostonplans.org/3d'
BPDA_PAGE = 'https://www.bostonplans.org/3d-data-maps/3d-smart-model/3d-data-download'
BPDA_DOC = 'https://maps.bostonplans.org/3d/3D_Data_Documentation.pdf'
ORIGIN_SP_FT = (731_100.0, 2_902_900.0)  # documented Metro Boston 3D origin
US_FT = 1200.0 / 3937.0
TILE_FT = 5000.0
Image.MAX_IMAGE_PIXELS = None


@dataclass(frozen=True)
class Tile:
    tile_id: str
    x0: float  # local ft, south-west corner
    y0: float

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x0 + TILE_FT, self.y0 + TILE_FT)


TILES = {
    # From the BPDA tile-grid FeatureServer (Bos3D_TileGrid_PopUps_20260624).
    'BOS_I_7': Tile('BOS_I_7', 45_000.0, 35_000.0),
    'BOS_I_8': Tile('BOS_I_8', 45_000.0, 30_000.0),
}

DOWNLOADS = {
    'terrain': 'Bos3d_Terrain_2011_OBJ/{tile}_TerrainMesh_2011_OBJ.zip',
    'buildings': 'Bos3d_BldgModels_20251204_OBJ/{tile}_BldgModels_OBJ.zip',
    'groundplan': 'Bos3d_Groundplan_DXF/{tile}_Groundplan_DXF.zip',
}

# Display offsets above the 2011 terrain surface (metres). Visual layering only.
OFFSETS = {
    'road': 0.05,
    'parking': 0.045,
    'driveway': 0.05,
    'sidewalk': 0.17,
    'marking': 0.065,
}
SAMPLE_RES_M = 1.0
HEIGHTFIELD_RES_M = 2.0


# --------------------------------------------------------------------------- io

def fetch(url: str, target: Path) -> Path:
    if target.exists() and target.stat().st_size > 0:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f'  downloading {url}')
    request = urllib.request.Request(url, headers={'User-Agent': 'FloodRoute planning prototype'})
    with urllib.request.urlopen(request, timeout=600) as response:
        target.write_bytes(response.read())
    return target


def write_glb(path: Path, meshes: dict[str, dict[str, np.ndarray]], extras: dict | None = None) -> int:
    """Minimal glTF 2.0 binary writer: one node per mesh, no materials."""
    buffer = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    gltf_meshes: list[dict] = []
    nodes: list[dict] = []

    def add(array: np.ndarray, target: int | None, kind: str) -> int:
        nonlocal buffer
        while len(buffer) % 4:
            buffer.append(0)
        data = np.ascontiguousarray(array)
        view = {'buffer': 0, 'byteOffset': len(buffer), 'byteLength': data.nbytes}
        if target is not None:
            view['target'] = target
        buffer_views.append(view)
        buffer.extend(data.tobytes())
        component = {np.dtype('float32'): 5126, np.dtype('uint32'): 5125, np.dtype('uint16'): 5123}[data.dtype]
        accessor = {
            'bufferView': len(buffer_views) - 1,
            'componentType': component,
            'count': int(data.shape[0]),
            'type': kind,
        }
        if kind == 'VEC3' and data.dtype == np.float32:
            accessor['min'] = data.min(axis=0).astype(float).tolist()
            accessor['max'] = data.max(axis=0).astype(float).tolist()
        accessors.append(accessor)
        return len(accessors) - 1

    for name, mesh in meshes.items():
        attributes = {}
        for attr, values in mesh.items():
            if attr == 'index':
                continue
            kind = {1: 'SCALAR', 2: 'VEC2', 3: 'VEC3', 4: 'VEC4'}[1 if values.ndim == 1 else values.shape[1]]
            attributes[attr] = add(values.astype(np.float32), 34962, kind)
        primitive: dict = {'attributes': attributes, 'mode': 4}
        if 'index' in mesh:
            primitive['indices'] = add(mesh['index'].astype(np.uint32).reshape(-1), 34963, 'SCALAR')
        gltf_meshes.append({'name': name, 'primitives': [primitive]})
        nodes.append({'name': name, 'mesh': len(gltf_meshes) - 1})

    while len(buffer) % 4:
        buffer.append(0)
    document = {
        'asset': {'version': '2.0', 'generator': 'FloodRoute build_bpda_scene.py'},
        'scene': 0,
        'scenes': [{'nodes': list(range(len(nodes)))}],
        'nodes': nodes,
        'meshes': gltf_meshes,
        'accessors': accessors,
        'bufferViews': buffer_views,
        'buffers': [{'byteLength': len(buffer)}],
    }
    if extras:
        document['asset']['extras'] = extras
    json_bytes = json.dumps(document, separators=(',', ':')).encode('utf-8')
    json_bytes += b' ' * ((4 - len(json_bytes) % 4) % 4)
    total = 12 + 8 + len(json_bytes) + 8 + len(buffer)
    with path.open('wb') as handle:
        handle.write(struct.pack('<4sII', b'glTF', 2, total))
        handle.write(struct.pack('<I4s', len(json_bytes), b'JSON'))
        handle.write(json_bytes)
        handle.write(struct.pack('<I4s', len(buffer), b'BIN\x00'))
        handle.write(bytes(buffer))
    return total


# ------------------------------------------------------------------ geometry

class Frame:
    """Boston-3D local feet  <->  scene metres (x east, y up, z = -north)."""

    def __init__(self, origin_ft: tuple[float, float]):
        self.ox, self.oy = origin_ft

    def xy(self, x_ft: np.ndarray, y_ft: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return (x_ft - self.ox) * US_FT, -(y_ft - self.oy) * US_FT

    def point3(self, xyz_ft: np.ndarray) -> np.ndarray:
        x, z = self.xy(xyz_ft[:, 0], xyz_ft[:, 1])
        return np.column_stack([x, xyz_ft[:, 2] * US_FT, z]).astype(np.float32)


def parse_obj(text: str) -> tuple[np.ndarray, np.ndarray | None, list[list[tuple[int, int | None]]]]:
    vertices: list[list[float]] = []
    uvs: list[list[float]] = []
    faces: list[list[tuple[int, int | None]]] = []
    for line in text.splitlines():
        if line.startswith('v '):
            vertices.append([float(value) for value in line.split()[1:4]])
        elif line.startswith('vt '):
            uvs.append([float(value) for value in line.split()[1:3]])
        elif line.startswith('f '):
            face = []
            for token in line.split()[1:]:
                parts = token.split('/')
                vertex = int(parts[0]) - 1
                uv = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else None
                face.append((vertex, uv))
            faces.append(face)
    return np.array(vertices, dtype=np.float64), (np.array(uvs, dtype=np.float64) if uvs else None), faces


class HeightSampler:
    """Exact linear interpolation of the official terrain TIN (via a dense raster)."""

    def __init__(self, xs: np.ndarray, zs: np.ndarray, heights: np.ndarray, bounds: tuple[float, float, float, float]):
        self.x0, self.z0, x1, z1 = bounds
        self.res = SAMPLE_RES_M
        self.nx = int(math.ceil((x1 - self.x0) / self.res)) + 1
        self.nz = int(math.ceil((z1 - self.z0) / self.res)) + 1
        self.grid = heights
        self.xs, self.zs = xs, zs

    def sample(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        fx = np.clip((x - self.x0) / self.res, 0, self.nx - 1.001)
        fz = np.clip((z - self.z0) / self.res, 0, self.nz - 1.001)
        ix, iz = np.floor(fx).astype(int), np.floor(fz).astype(int)
        tx, tz = fx - ix, fz - iz
        g = self.grid
        a = g[iz, ix] * (1 - tx) + g[iz, ix + 1] * tx
        b = g[iz + 1, ix] * (1 - tx) + g[iz + 1, ix + 1] * tx
        return a * (1 - tz) + b * tz


def build_height_raster(points: np.ndarray, triangles: np.ndarray, bounds: tuple[float, float, float, float]) -> np.ndarray:
    x0, z0, x1, z1 = bounds
    nx = int(math.ceil((x1 - x0) / SAMPLE_RES_M)) + 1
    nz = int(math.ceil((z1 - z0) / SAMPLE_RES_M)) + 1
    grid = np.full((nz, nx), np.nan, dtype=np.float32)
    # Rasterise each TIN triangle with exact barycentric interpolation.
    tri = points[triangles]
    fx = (tri[:, :, 0] - x0) / SAMPLE_RES_M
    fz = (tri[:, :, 2] - z0) / SAMPLE_RES_M
    heights = tri[:, :, 1]
    for k in range(len(triangles)):
        ax, bx, cx = fx[k]
        az, bz, cz = fz[k]
        ix0, ix1 = max(0, int(math.ceil(min(ax, bx, cx)))), min(nx - 1, int(math.floor(max(ax, bx, cx))))
        iz0, iz1 = max(0, int(math.ceil(min(az, bz, cz)))), min(nz - 1, int(math.floor(max(az, bz, cz))))
        if ix1 < ix0 or iz1 < iz0:
            continue
        det = (bz - cz) * (ax - cx) + (cx - bx) * (az - cz)
        if abs(det) < 1e-9:
            continue
        gx, gz = np.meshgrid(np.arange(ix0, ix1 + 1), np.arange(iz0, iz1 + 1))
        l1 = ((bz - cz) * (gx - cx) + (cx - bx) * (gz - cz)) / det
        l2 = ((cz - az) * (gx - cx) + (ax - cx) * (gz - cz)) / det
        l3 = 1 - l1 - l2
        inside = (l1 >= -1e-6) & (l2 >= -1e-6) & (l3 >= -1e-6)
        if inside.any():
            ha, hb, hc = heights[k]
            grid[gz[inside], gx[inside]] = l1[inside] * ha + l2[inside] * hb + l3[inside] * hc
    # Fill gaps (tile seams / outside TIN) with nearest valid neighbours along rows/cols.
    for _ in range(4):
        mask = np.isnan(grid)
        if not mask.any():
            break
        shifted = [np.roll(grid, shift, axis) for shift in (1, -1) for axis in (0, 1)]
        stack = np.nanmean(np.stack(shifted), axis=0)
        grid[mask] = stack[mask]
    grid[np.isnan(grid)] = 0.0
    return grid


def iter_polygons(geometry) -> list[Polygon]:
    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if hasattr(geometry, 'geoms'):
        return [part for child in geometry.geoms for part in iter_polygons(child)]
    return []


def drape_polygons(geometry, sampler: HeightSampler, offset: float, cell: float = 10.0) -> tuple[np.ndarray, np.ndarray]:
    """Tessellate polygons on a grid and drape each vertex onto the terrain."""
    positions: list[np.ndarray] = []
    for polygon in iter_polygons(geometry):
        minx, miny, maxx, maxy = polygon.bounds
        xs = np.arange(math.floor(minx / cell) * cell, maxx + cell, cell)
        ys = np.arange(math.floor(miny / cell) * cell, maxy + cell, cell)
        cells = [box(x, y, x + cell, y + cell) for x in xs[:-1] for y in ys[:-1]]
        if not cells:
            continue
        pieces = shapely.intersection(np.array(cells, dtype=object), polygon)
        for piece in pieces:
            for part in iter_polygons(piece):
                if part.area < 0.05:
                    continue
                triangles = shapely.constrained_delaunay_triangles(part)
                for triangle in getattr(triangles, 'geoms', []):
                    coords = np.asarray(triangle.exterior.coords)[:3]
                    # Orient counter-clockwise when viewed from +y (x east, z south).
                    a, b, c = coords
                    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
                    if cross > 0:
                        coords = coords[[0, 2, 1]]
                    positions.append(coords)
    if not positions:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    flat = np.concatenate(positions)
    heights = sampler.sample(flat[:, 0], flat[:, 1]) + offset
    xyz = np.column_stack([flat[:, 0], heights, flat[:, 1]]).astype(np.float32)
    normals = face_normals(xyz)
    return xyz, normals


def face_normals(xyz: np.ndarray) -> np.ndarray:
    tri = xyz.reshape(-1, 3, 3)
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(normal, axis=1, keepdims=True)
    normal = normal / np.where(length == 0, 1, length)
    return np.repeat(normal, 3, axis=0).astype(np.float32)


def index_mesh(xyz: np.ndarray, feature: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """Weld identical vertices (mm precision) into an indexed mesh; normals are left to the client."""
    key = np.round(xyz.astype(np.float64) * 1000).astype(np.int64)
    if feature is not None:
        key = np.column_stack([key, feature.astype(np.int64)])
    unique, first, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    mesh = {'POSITION': xyz[first].astype(np.float32), 'index': inverse.reshape(-1).astype(np.uint32)}
    if feature is not None:
        mesh['_FEATURE_ID'] = feature[first].astype(np.float32)
    return mesh


def densify(coords: np.ndarray, step: float) -> np.ndarray:
    out = [coords[0]]
    for start, end in zip(coords[:-1], coords[1:]):
        length = float(np.hypot(*(end - start)))
        count = max(1, int(math.ceil(length / step)))
        for i in range(1, count + 1):
            out.append(start + (end - start) * (i / count))
    return np.array(out)


def ribbons(lines: list[np.ndarray], width: float, sampler: HeightSampler, offset: float) -> tuple[np.ndarray, np.ndarray]:
    quads: list[np.ndarray] = []
    half = width / 2
    for line in lines:
        if len(line) < 2:
            continue
        dense = densify(line, 3.0)
        for a, b in zip(dense[:-1], dense[1:]):
            direction = b - a
            length = float(np.hypot(*direction))
            if length < 1e-3:
                continue
            nx, nz = -direction[1] / length * half, direction[0] / length * half
            p = np.array([[a[0] + nx, a[1] + nz], [a[0] - nx, a[1] - nz], [b[0] - nx, b[1] - nz], [b[0] + nx, b[1] + nz]])
            quads.append(p[[0, 1, 2, 0, 2, 3]])
    if not quads:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    flat = np.concatenate(quads)
    heights = sampler.sample(flat[:, 0], flat[:, 1]) + offset
    xyz = np.column_stack([flat[:, 0], heights, flat[:, 1]]).astype(np.float32)
    tri = xyz.reshape(-1, 3, 3)
    flip = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])[:, 1] < 0
    tri[flip] = tri[flip][:, [0, 2, 1]]
    xyz = tri.reshape(-1, 3)
    return xyz, face_normals(xyz)


def curb_walls(geometry, sampler: HeightSampler, bottom: float, top: float) -> tuple[np.ndarray, np.ndarray]:
    quads: list[np.ndarray] = []
    for polygon in iter_polygons(geometry):
        for ring in [polygon.exterior, *polygon.interiors]:
            coords = densify(np.asarray(ring.coords)[:, :2], 3.0)
            ground = sampler.sample(coords[:, 0], coords[:, 1])
            for i in range(len(coords) - 1):
                a, b = coords[i], coords[i + 1]
                ga, gb = ground[i], ground[i + 1]
                quad = np.array([
                    [a[0], ga + bottom, a[1]], [b[0], gb + bottom, b[1]], [b[0], gb + top, b[1]],
                    [a[0], ga + bottom, a[1]], [b[0], gb + top, b[1]], [a[0], ga + top, a[1]],
                ])
                quads.append(quad)
    if not quads:
        return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32)
    xyz = np.concatenate(quads).astype(np.float32)
    return xyz, face_normals(xyz)


# ------------------------------------------------------------------- stages

def load_terrain(tiles: list[Tile], cache: Path, frame: Frame, out: Path, texture_px: int):
    all_points, all_tris, meshes, textures = [], [], {}, {}
    vertex_offset = 0
    for tile in tiles:
        archive = fetch(f"{BPDA_BASE}/{DOWNLOADS['terrain'].format(tile=tile.tile_id)}", cache / f'{tile.tile_id}_terrain.zip')
        with zipfile.ZipFile(archive) as zipped:
            obj_name = next(name for name in zipped.namelist() if name.lower().endswith('.obj'))
            jpg_name = next(name for name in zipped.namelist() if name.lower().endswith('.jpg'))
            vertices, uvs, faces = parse_obj(zipped.read(obj_name).decode('utf-8', 'ignore'))
            image = Image.open(io.BytesIO(zipped.read(jpg_name))).convert('RGB')
        triangles = []
        uv_index: dict[int, int] = {}
        for face in faces:
            for k in range(1, len(face) - 1):
                tri = (face[0], face[k], face[k + 1])
                triangles.append([vertex for vertex, _ in tri])
                for vertex, uv in tri:
                    if uv is not None:
                        uv_index[vertex] = uv
        triangles = np.array(triangles, dtype=np.int64)
        points = frame.point3(vertices)
        if uvs is not None and len(uv_index) == len(vertices):
            uv = uvs[[uv_index[i] for i in range(len(vertices))]]
        else:  # Groundplan texture spans exactly the tile extent.
            x0, y0, x1, y1 = tile.bounds
            uv = np.column_stack([(vertices[:, 0] - x0) / (x1 - x0), (vertices[:, 1] - y0) / (y1 - y0)])
        # three.js/GLTF flip V; keep texture upright by flipping here.
        uv = np.column_stack([uv[:, 0], 1.0 - uv[:, 1]])
        # Wind triangles counter-clockwise seen from +y.
        tri_xyz = points[triangles]
        up = np.cross(tri_xyz[:, 1] - tri_xyz[:, 0], tri_xyz[:, 2] - tri_xyz[:, 0])[:, 1]
        triangles[up < 0] = triangles[up < 0][:, [0, 2, 1]]
        meshes[f'terrain_{tile.tile_id}'] = {
            'POSITION': points, 'TEXCOORD_0': uv.astype(np.float32), 'index': triangles.astype(np.uint32),
        }
        texture_name = f'groundplan_{tile.tile_id}.jpg'
        image.resize((texture_px, texture_px), Image.LANCZOS).save(out / texture_name, quality=82, optimize=True)
        textures[tile.tile_id] = texture_name
        all_points.append(points)
        all_tris.append(triangles + vertex_offset)
        vertex_offset += len(points)
        print(f'  terrain {tile.tile_id}: {len(points)} vertices, {len(triangles)} triangles')
    return np.concatenate(all_points), np.concatenate(all_tris), meshes, textures


def vertex_normals(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(points, dtype=np.float64)
    tri = points[triangles]
    face = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for k in range(3):
        np.add.at(normals, triangles[:, k], face)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    return (normals / np.where(length == 0, 1, length)).astype(np.float32)


def load_buildings(tiles: list[Tile], cache: Path, frame: Frame):
    positions, normals, feature_ids, records = [], [], [], []
    for tile in tiles:
        archive = fetch(f"{BPDA_BASE}/{DOWNLOADS['buildings'].format(tile=tile.tile_id)}", cache / f'{tile.tile_id}_buildings.zip')
        with zipfile.ZipFile(archive) as outer:
            catalog_name = next(name for name in outer.namelist() if name.endswith('catalog.csv'))
            catalog = {row['Model_ID']: row for row in csv.DictReader(io.StringIO(outer.read(catalog_name).decode('utf-8-sig')))}
            for name in outer.namelist():
                if not name.endswith('_OBJ.zip'):
                    continue
                model_id = Path(name).name.replace('_OBJ.zip', '')
                row = catalog.get(model_id)
                if not row or row['Status'] == 'History':
                    continue  # superseded / demolished models are not current context
                with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                    obj_name = next(n for n in inner.namelist() if n.endswith('.obj'))
                    vertices, _, faces = parse_obj(inner.read(obj_name).decode('utf-8', 'ignore'))
                if not len(vertices):
                    continue
                points = frame.point3(vertices)
                tris = np.array([[face[0][0], face[k][0], face[k + 1][0]] for face in faces for k in range(1, len(face) - 1)])
                if not len(tris):
                    continue
                xyz = points[tris.reshape(-1)]
                feature = len(records)
                positions.append(xyz)
                normals.append(face_normals(xyz))
                feature_ids.append(np.full(len(xyz), feature, dtype=np.float32))
                def num(key: str) -> float | None:
                    try:
                        return round(float(row[key]), 2)
                    except (TypeError, ValueError):
                        return None
                records.append({
                    'feature_id': feature,
                    'model_id': model_id,
                    'name': row.get('Name') or None,
                    'struct_type': row.get('StructType') or 'Unknown',
                    'status': row.get('Status'),
                    'lod': row.get('Model_LOD'),
                    'model_credit': row.get('Model_Cred') or None,
                    'survey_source': row.get('Survey_Src') or None,
                    'survey_date': row.get('Survey_Dt') or None,
                    'ground_elevation_ft_navd88': num('Gnd_El_Ft'),
                    'height_ft': num('Height_Ft'),
                    'tile_id': tile.tile_id,
                    'parcel_id': row.get('Parcel_ID') or None,
                    'centroid': [round(float(xyz[:, 0].mean()), 2), round(float(xyz[:, 2].mean()), 2)],
                    'base_m': round(float(xyz[:, 1].min()), 2),
                    'top_m': round(float(xyz[:, 1].max()), 2),
                })
        print(f'  buildings through {tile.tile_id}: {len(records)} current models')
    return {'buildings': index_mesh(np.concatenate(positions), np.concatenate(feature_ids))}, records


def dxf_rings(msp, layer: str) -> list[np.ndarray]:
    rings = []
    for entity in msp.query(f'*[layer=="{layer}"]'):
        kind = entity.dxftype()
        if kind == 'LWPOLYLINE':
            coords = np.array([point[:2] for point in entity.get_points('xy')], dtype=np.float64)
            closed = entity.closed
        elif kind == 'POLYLINE':
            coords = np.array([[v.dxf.location.x, v.dxf.location.y] for v in entity.vertices], dtype=np.float64)
            closed = entity.is_closed
        elif kind == 'LINE':
            coords = np.array([[entity.dxf.start.x, entity.dxf.start.y], [entity.dxf.end.x, entity.dxf.end.y]])
            closed = False
        else:
            continue
        if len(coords) >= 2:
            rings.append((coords, closed))
    return rings


def to_local_2d(coords: np.ndarray, frame: Frame) -> np.ndarray:
    x, z = frame.xy(coords[:, 0], coords[:, 1])
    return np.column_stack([x, z])


def polygon_layer(rings, frame: Frame, even_odd: bool):
    polygons = []
    for coords, _closed in rings:
        if len(coords) < 3:
            continue
        polygon = Polygon(to_local_2d(coords, frame))
        if not polygon.is_valid:
            polygon = shapely.make_valid(polygon)
        polygons.extend(part for part in iter_polygons(polygon) if part.area > 0.2)
    if not polygons:
        return None
    if not even_odd:
        return unary_union(polygons)
    # Islands are digitised as separate closed rings: XOR them (even-odd fill).
    polygons.sort(key=lambda p: -p.area)
    result = polygons[0]
    for polygon in polygons[1:]:
        result = result.symmetric_difference(polygon)
    return shapely.make_valid(result)


def load_groundplan(tiles: list[Tile], cache: Path, frame: Frame, sampler: HeightSampler):
    layers: dict[str, list] = {key: [] for key in ('road', 'sidewalk', 'parking', 'driveway', 'hydro', 'open_space', 'docks')}
    marking_lines: list[np.ndarray] = []
    marking_polys: list = []
    for tile in tiles:
        archive = fetch(f"{BPDA_BASE}/{DOWNLOADS['groundplan'].format(tile=tile.tile_id)}", cache / f'{tile.tile_id}_groundplan.zip')
        dxf_path = cache / f'{tile.tile_id}_groundplan.dxf'
        if not dxf_path.exists():
            with zipfile.ZipFile(archive) as zipped:
                dxf_path.write_bytes(zipped.read(next(n for n in zipped.namelist() if n.lower().endswith('.dxf'))))
        print(f'  reading {dxf_path.name}')
        msp = ezdxf.readfile(dxf_path).modelspace()
        tx, tz = frame.xy(np.array([tile.bounds[0], tile.bounds[2]]), np.array([tile.bounds[1], tile.bounds[3]]))
        tile_box = box(tx.min(), tz.min(), tx.max(), tz.max())
        for key, layer, even_odd in [
            ('road', 'road_poly', True), ('sidewalk', 'Sidewalk', False), ('parking', 'Parking', False),
            ('driveway', 'Driveway', False), ('hydro', 'hydro', True), ('open_space', 'OpenSpace', False), ('docks', 'docks', False),
        ]:
            geometry = polygon_layer(dxf_rings(msp, layer), frame, even_odd)
            if geometry is not None:
                layers[key].append(shapely.make_valid(geometry).intersection(tile_box))
        for coords, _closed in dxf_rings(msp, 'Pave_Mrk_Line'):
            marking_lines.append(to_local_2d(coords, frame))
        poly = polygon_layer(dxf_rings(msp, 'Pave_Mrk_Poly'), frame, False)
        if poly is not None:
            marking_polys.append(poly)
    merged = {key: shapely.make_valid(unary_union(value)) if value else None for key, value in layers.items()}
    # Sidewalks sit on top; remove their footprint from the pavement so surfaces never overlap.
    if merged['road'] is not None and merged['sidewalk'] is not None:
        merged['road'] = merged['road'].difference(merged['sidewalk'])
    markings = unary_union(marking_polys) if marking_polys else None
    return merged, marking_lines, markings


def build_streets(merged, marking_lines, marking_polys, sampler: HeightSampler):
    meshes = {}
    for key, offset, cell in [('road', OFFSETS['road'], 12.0), ('parking', OFFSETS['parking'], 12.0), ('driveway', OFFSETS['driveway'], 12.0), ('sidewalk', OFFSETS['sidewalk'], 8.0)]:
        geometry = merged.get(key)
        if geometry is None:
            continue
        xyz, normal = drape_polygons(geometry, sampler, offset, cell)
        meshes[key] = index_mesh(xyz)
        print(f'  {key}: {len(xyz) // 3} triangles')
    if merged.get('sidewalk') is not None:
        xyz, normal = curb_walls(merged['sidewalk'], sampler, 0.0, OFFSETS['sidewalk'])
        meshes['curb'] = index_mesh(xyz)
    line_xyz, line_n = ribbons(marking_lines, 0.15, sampler, OFFSETS['marking'])
    parts_xyz, parts_n = [line_xyz], [line_n]
    if marking_polys is not None:
        xyz, normal = drape_polygons(marking_polys, sampler, OFFSETS['marking'], 12.0)
        parts_xyz.append(xyz)
        parts_n.append(normal)
    meshes['marking'] = index_mesh(np.concatenate(parts_xyz))
    print(f"  markings: {len(meshes['marking']['POSITION']) // 3} triangles")
    if merged.get('hydro') is not None:
        flat, _ = drape_polygons(merged['hydro'], sampler, 0.0, 120.0)
        flat[:, 1] = 0.0  # Placed at a runtime water level by the client.
        meshes['harbor_mask'] = index_mesh(flat)
    return meshes


def place_props(merged, building_records, sampler: HeightSampler, rng: np.random.Generator):
    """Deterministic, explicitly illustrative street furniture anchors."""
    road, sidewalk = merged.get('road'), merged.get('sidewalk')
    parking, hydro = merged.get('parking'), merged.get('hydro')
    open_space = merged.get('open_space')
    blocked = unary_union([g for g in (road, parking, hydro) if g is not None])
    blocked_prepared = shapely.prepared.prep(blocked) if blocked is not None else None
    lights, street_trees, park_trees, cars = [], [], [], []

    def ground(x: float, z: float) -> float:
        return float(sampler.sample(np.array([x]), np.array([z]))[0])

    if road is not None and sidewalk is not None:
        side_prepared = shapely.prepared.prep(sidewalk)
        for polygon in iter_polygons(road):
            if polygon.area < 400:
                continue
            for ring in [polygon.exterior]:
                line = LineString(ring.coords)
                length = line.length
                orientation = 1.0 if Polygon(ring.coords).exterior.is_ccw else -1.0
                for distance, spacing_kind in [(d, 'light') for d in np.arange(10, length, 34.0)] + [(d, 'tree') for d in np.arange(27, length, 17.0)]:
                    p0 = line.interpolate(distance)
                    p1 = line.interpolate(min(length, distance + 0.5))
                    dx, dz = p1.x - p0.x, p1.y - p0.y
                    norm = math.hypot(dx, dz) or 1
                    outward = 1.0 if spacing_kind == 'light' else 1.0
                    inset = 0.9 if spacing_kind == 'light' else 2.2
                    # Try both sides; keep the one that lands on a sidewalk.
                    for sign in (orientation, -orientation):
                        x = p0.x + sign * (dz / norm) * inset * outward
                        z = p0.y - sign * (dx / norm) * inset * outward
                        if side_prepared.contains(Point(x, z)):
                            heading = math.atan2(sign * dz, -sign * dx)
                            y = ground(x, z) + OFFSETS['sidewalk']
                            if spacing_kind == 'light':
                                lights.append([round(x, 2), round(y, 2), round(z, 2), round(heading, 3)])
                            elif rng.random() < 0.55:
                                street_trees.append([round(x, 2), round(y, 2), round(z, 2), round(float(rng.uniform(0.8, 1.25)), 2)])
                            break
    footprints = [Point(record['centroid']).buffer(1) for record in building_records]
    building_hint = shapely.prepared.prep(unary_union(footprints)) if footprints else None
    if open_space is not None:
        for polygon in iter_polygons(open_space):
            minx, miny, maxx, maxy = polygon.bounds
            prepared = shapely.prepared.prep(polygon)
            count = int(polygon.area / 260)
            for _ in range(count * 3):
                if count <= 0:
                    break
                x, z = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
                point = Point(x, z)
                if not prepared.contains(point):
                    continue
                if blocked_prepared and blocked_prepared.contains(point):
                    continue
                if building_hint and building_hint.contains(point):
                    continue
                y = ground(x, z)
                if y < 1.2:  # keep trees out of tidal flats / beaches near datum
                    continue
                park_trees.append([round(x, 2), round(y, 2), round(z, 2), round(float(rng.uniform(0.75, 1.35)), 2)])
                count -= 1
    if parking is not None:
        for polygon in iter_polygons(parking):
            if polygon.area < 120:
                continue
            rect = polygon.minimum_rotated_rectangle
            coords = np.asarray(rect.exterior.coords)[:4]
            edges = [coords[1] - coords[0], coords[2] - coords[1]]
            long_axis = edges[0] if np.linalg.norm(edges[0]) >= np.linalg.norm(edges[1]) else edges[1]
            angle = math.atan2(long_axis[1], long_axis[0])
            ux = np.array([math.cos(angle), math.sin(angle)])
            uz = np.array([-ux[1], ux[0]])
            centre = np.asarray(polygon.centroid.coords)[0]
            prepared = shapely.prepared.prep(polygon.buffer(-1.6))
            extent = math.sqrt(polygon.area) * 1.5 + 30
            for i in np.arange(-extent, extent, 2.7):
                for j in np.arange(-extent, extent, 6.2):
                    x, z = centre + ux * i + uz * j
                    if not prepared.contains(Point(x, z)) or rng.random() > 0.14:
                        continue
                    y = ground(x, z) + OFFSETS['parking']
                    cars.append([round(float(x), 2), round(y, 2), round(float(z), 2), round(-angle + math.pi / 2, 3), int(rng.integers(0, 6))])
    print(f'  props: {len(lights)} lights, {len(street_trees)} street trees, {len(park_trees)} park trees, {len(cars)} parked cars')
    return {'streetlights': lights, 'street_trees': street_trees, 'park_trees': park_trees, 'parked_cars': cars}


def fit_geo_affine(frame: Frame, bounds_local: tuple[float, float, float, float]) -> dict:
    """Least-squares affine lon/lat <-> scene metres, with measured residuals."""
    to_geo = Transformer.from_crs('EPSG:2249', 'EPSG:4326', always_xy=True)
    x0, z0, x1, z1 = bounds_local
    gx, gz = np.meshgrid(np.linspace(x0, x1, 25), np.linspace(z0, z1, 25))
    x, z = gx.ravel(), gz.ravel()
    x_sp = x / US_FT + frame.ox + ORIGIN_SP_FT[0]
    y_sp = -z / US_FT + frame.oy + ORIGIN_SP_FT[1]
    lon, lat = to_geo.transform(x_sp, y_sp)
    A = np.column_stack([lon, lat, np.ones_like(lon)])
    coef_x, *_ = np.linalg.lstsq(A, x, rcond=None)
    coef_z, *_ = np.linalg.lstsq(A, z, rcond=None)
    residual = np.hypot(A @ coef_x - x, A @ coef_z - z)
    B = np.column_stack([x, z, np.ones_like(x)])
    coef_lon, *_ = np.linalg.lstsq(B, lon, rcond=None)
    coef_lat, *_ = np.linalg.lstsq(B, lat, rcond=None)
    print(f'  geo affine residual: max {residual.max():.3f} m, mean {residual.mean():.3f} m')
    return {
        'lonlat_to_xz': {'x': coef_x.tolist(), 'z': coef_z.tolist()},
        'xz_to_lonlat': {'lon': coef_lon.tolist(), 'lat': coef_lat.tolist()},
        'max_residual_m': round(float(residual.max()), 4),
        'note': 'Affine fit to pyproj EPSG:2249->EPSG:4326 over the scene extent.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--tiles', default='BOS_I_7,BOS_I_8')
    parser.add_argument('--cache', type=Path, default=Path('analysis/scene/.cache'))
    parser.add_argument('--out', type=Path, default=Path('frontend/public/scene/morrissey'))
    parser.add_argument('--texture-px', type=int, default=4096)
    parser.add_argument('--skip-streets', action='store_true')
    args = parser.parse_args()

    tiles = [TILES[tile_id] for tile_id in args.tiles.split(',')]
    xs = [tile.x0 for tile in tiles] + [tile.x0 + TILE_FT for tile in tiles]
    ys = [tile.y0 for tile in tiles] + [tile.y0 + TILE_FT for tile in tiles]
    origin = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    frame = Frame(origin)
    args.out.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)

    bx0, bz1 = frame.xy(np.array(min(xs)), np.array(min(ys)))
    bx1, bz0 = frame.xy(np.array(max(xs)), np.array(max(ys)))
    bounds_local = (float(bx0), float(bz0), float(bx1), float(bz1))

    print('terrain')
    points, triangles, terrain_meshes, textures = load_terrain(tiles, args.cache, frame, args.out, args.texture_px)
    write_glb(args.out / 'terrain.glb', terrain_meshes)

    print('height raster')
    grid = build_height_raster(points, triangles, bounds_local)
    sampler = HeightSampler(points[:, 0], points[:, 2], grid, bounds_local)
    step = int(round(HEIGHTFIELD_RES_M / SAMPLE_RES_M))
    coarse = grid[::step, ::step]
    encoded = np.clip(np.round((coarse + 20.0) * 100.0), 0, 65535).astype('<u2')
    (args.out / 'heightfield.bin').write_bytes(encoded.tobytes())

    print('buildings')
    building_meshes, records = load_buildings(tiles, args.cache, frame)
    write_glb(args.out / 'buildings.glb', building_meshes)
    (args.out / 'buildings.json').write_text(json.dumps(records, separators=(',', ':')))

    props = None
    if not args.skip_streets:
        print('streets')
        merged, marking_lines, marking_polys = load_groundplan(tiles, args.cache, frame, sampler)
        street_meshes = build_streets(merged, marking_lines, marking_polys, sampler)
        write_glb(args.out / 'streets.glb', street_meshes)
        props = place_props(merged, records, sampler, np.random.default_rng(20180104))
        (args.out / 'props.json').write_text(json.dumps({
            'provenance': 'illustrative',
            'note': 'Generated placements for visual context only. Positions follow official sidewalk, road and parking polygons, but no tree, streetlight or vehicle inventory was loaded.',
            **props,
        }, separators=(',', ':')))

    manifest = {
        'scene_id': 'bpda-morrissey-' + '-'.join(tile.tile_id.lower() for tile in tiles),
        'title': 'Morrissey Boulevard / Columbia Point',
        'frame': {
            'description': 'Local metres: x east, y up (NAVD88), z = -north. Origin is the centre of the loaded tiles.',
            'origin_boston3d_ft': list(origin),
            'origin_epsg2249_ft': [origin[0] + ORIGIN_SP_FT[0], origin[1] + ORIGIN_SP_FT[1]],
            'source_crs': 'EPSG:2249 (NAD83 / Massachusetts Mainland, US survey feet) minus Metro Boston 3D origin (731100, 2902900)',
            'vertical_datum': 'NAVD88',
            'units': 'metres',
            'bounds_xz': bounds_local,
            'geo': fit_geo_affine(frame, bounds_local),
        },
        'heightfield': {
            'file': 'heightfield.bin',
            'encoding': 'uint16 little-endian, metres = value / 100 - 20',
            'width': int(coarse.shape[1]),
            'height': int(coarse.shape[0]),
            'resolution_m': HEIGHTFIELD_RES_M,
            'origin_xz': [bounds_local[0], bounds_local[1]],
            'source': 'Resampled from the BPDA 2011 terrain TIN.',
        },
        'layers': {
            'terrain': {'file': 'terrain.glb', 'textures': textures, 'status': 'official'},
            'buildings': {'file': 'buildings.glb', 'records': 'buildings.json', 'count': len(records), 'status': 'official'},
            'streets': None if args.skip_streets else {'file': 'streets.glb', 'status': 'official', 'display_offsets_m': OFFSETS},
            'props': None if args.skip_streets else {'file': 'props.json', 'status': 'illustrative'},
        },
        'tiles': [tile.tile_id for tile in tiles],
        'sources': [
            {'id': 'bpda-3d-smart-model', 'name': 'Boston Planning Department 3D Smart Model', 'url': BPDA_PAGE, 'license': 'ODC Public Domain Dedication and License (PDDL)'},
            {'id': 'bpda-3d-documentation', 'name': 'BPDA 3D Data Documentation', 'url': BPDA_DOC},
        ],
        'limitations': [
            'Terrain is the 2011 survey surface; post-2011 grading, seawalls or road changes may be missing.',
            'Groundplan linework is 2011 photogrammetry (~6 in precision); building models are 2014-2025 vintages.',
            'Road, sidewalk and marking surfaces are draped onto terrain with small display offsets; curb heights are stylised (0.17 m).',
            'Facade windows and materials are stylised, not surveyed.',
        ],
    }
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    sizes = {path.name: round(path.stat().st_size / 1e6, 2) for path in sorted(args.out.iterdir())}
    print('written (MB):', sizes)


if __name__ == '__main__':
    main()
