#!/usr/bin/env python3
"""Check that the generated BPDA scene aligns with the app's other geographic layers.

1. Official City of Boston building footprints (EPSG:4326 GeoJSON used by the app)
   should land on BPDA building models after the manifest's lon/lat transform.
2. Inside the USGS 2018 estimated peak-inundation footprint, BPDA 2011 terrain
   should mostly lie below the footprint's reported peak water-surface elevation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SCENE = Path('frontend/public/scene/morrissey')
DATA = Path('frontend/public/data')
FT = 0.3048


def main() -> int:
    manifest = json.loads((SCENE / 'manifest.json').read_text())
    geo = manifest['frame']['geo']['lonlat_to_xz']
    hf = manifest['heightfield']
    raw = np.frombuffer((SCENE / 'heightfield.bin').read_bytes(), dtype='<u2').astype(np.float32)
    heights = raw.reshape(hf['height'], hf['width']) / 100 - 20
    ox, oz = hf['origin_xz']
    res = hf['resolution_m']

    def to_xz(lon, lat):
        lon, lat = np.asarray(lon), np.asarray(lat)
        return geo['x'][0] * lon + geo['x'][1] * lat + geo['x'][2], geo['z'][0] * lon + geo['z'][1] * lat + geo['z'][2]

    def ground(x, z):
        ix = np.clip(((x - ox) / res).round().astype(int), 0, hf['width'] - 1)
        iz = np.clip(((z - oz) / res).round().astype(int), 0, hf['height'] - 1)
        return heights[iz, ix]

    failures = 0
    records = json.loads((SCENE / 'buildings.json').read_text())
    centroids = np.array([record['centroid'] for record in records])
    city = json.loads((DATA / 'boston_buildings_morrissey.geojson').read_text())
    distances = []
    for feature in city['features']:
        ring = np.array(feature['geometry']['coordinates'][0])
        x, z = to_xz(ring[:, 0].mean(), ring[:, 1].mean())
        distances.append(float(np.min(np.hypot(centroids[:, 0] - x, centroids[:, 1] - z))))
    distances = np.array(distances)
    print(f'City footprint -> nearest BPDA model centroid: median {np.median(distances):.2f} m, p90 {np.percentile(distances, 90):.2f} m (n={len(distances)})')
    if np.median(distances) > 5:
        print('  FAIL: building layers are not aligned')
        failures += 1

    try:
        from shapely.geometry import shape
        from shapely import contains_xy
    except ImportError:
        print('shapely missing; skipping footprint/terrain check')
        return failures
    bx0, bz0, bx1, bz1 = manifest['frame']['bounds_xz']
    xv = manifest['frame']['geo']['xz_to_lonlat']
    gx, gz = np.meshgrid(np.arange(bx0, bx1, 6.0), np.arange(bz0, bz1, 6.0))
    gx, gz = gx.ravel(), gz.ravel()
    lon = xv['lon'][0] * gx + xv['lon'][1] * gz + xv['lon'][2]
    lat = xv['lat'][0] * gx + xv['lat'][1] * gz + xv['lat'][2]
    for name in ('usgs_2018_01_04_morrissey.geojson', 'usgs_2018_03_02_morrissey.geojson'):
        collection = json.loads((DATA / name).read_text())
        for feature in collection['features']:
            wse_ft = feature['properties'].get('peak_wse_ft_navd88')
            if wse_ft is None:
                continue
            inside = contains_xy(shape(feature['geometry']), lon, lat)
            if not inside.any():
                continue
            g = ground(gx[inside], gz[inside])
            land = g > -0.3  # ignore open water / mudflat cells
            share = float(np.mean(g[land] <= wse_ft * FT + 0.3)) if land.any() else float('nan')
            print(f'{name}: WSE {wse_ft} ft NAVD88; {inside.sum()} samples inside; land cells at/below WSE+0.3 m: {share:.1%}')
            if share < 0.8:
                print('  WARN: footprint and terrain disagree more than expected')
    return failures


if __name__ == '__main__':
    sys.exit(main())
