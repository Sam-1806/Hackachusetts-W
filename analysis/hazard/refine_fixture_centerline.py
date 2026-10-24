#!/usr/bin/env python3
"""Snap the Morrissey road fixture to the real road alignment.

The original fixture used hand-placed centreline samples ~75 m west of the actual
boulevard, which is visible in the 3D street scene. This script keeps every
``road_id`` / ``corridor_id`` and the segment break latitudes, but replaces the
geometry with the median line of OpenStreetMap's ``highway=primary`` carriageways
named "William T. Morrissey Boulevard" (both directions of the divided road).

It is still a labelled fixture, not Person 1's canonical road manifest.

Input:  analysis/hazard/fixtures/osm_morrissey_ways.json  (Overpass `out geom`, © OpenStreetMap contributors, ODbL)
Output: analysis/hazard/fixtures/morrissey_roads.geojson (+ copy in frontend/public/data/)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).parent
OSM = HERE / 'fixtures' / 'osm_morrissey_ways.json'
FIXTURE = HERE / 'fixtures' / 'morrissey_roads.geojson'
FRONTEND = Path('frontend/public/data/morrissey_roads.geojson')
GRAPH_VERSION = 'hazard-fixture-morrissey-v2'
STEP_DEG = 0.00025  # ~28 m of latitude
BAND_DEG = 0.00022


def main() -> None:
    osm = json.loads(OSM.read_text())
    points = [
        (node['lon'], node['lat'])
        for way in osm['elements']
        if way.get('tags', {}).get('highway') == 'primary'
        for node in way['geometry']
    ]
    # Densify each way so carriageways contribute evenly to every latitude band.
    dense: list[tuple[float, float]] = []
    for way in osm['elements']:
        if way.get('tags', {}).get('highway') != 'primary':
            continue
        nodes = [(n['lon'], n['lat']) for n in way['geometry']]
        for (ax, ay), (bx, by) in zip(nodes[:-1], nodes[1:]):
            count = max(1, int(math.hypot(bx - ax, (by - ay)) / 0.00005))
            dense.extend((ax + (bx - ax) * k / count, ay + (by - ay) * k / count) for k in range(count))
    if not dense:
        raise SystemExit('No primary Morrissey ways in the OSM extract.')

    def centre_at(lat: float) -> tuple[float, float] | None:
        lons = sorted(lon for lon, y in dense if abs(y - lat) <= BAND_DEG)
        if len(lons) < 2:
            return None
        # Median of the two carriageways: mid-point of the outer extremes is robust to ramps.
        return ((lons[0] + lons[-1]) / 2, lat)

    fixture = json.loads(FIXTURE.read_text())
    lat_min = min(lat for _, lat in points)
    lat_max = max(lat for _, lat in points)
    for feature in fixture['features']:
        if feature['properties']['corridor_id'] != 'fixture:morrissey-boulevard':
            continue
        coords = feature['geometry']['coordinates']
        north = min(max(coords[0][1], coords[-1][1]), lat_max)
        south = max(min(coords[0][1], coords[-1][1]), lat_min)
        lats = [north - i * STEP_DEG for i in range(int((north - south) / STEP_DEG) + 1)] + [south]
        line = [p for p in (centre_at(lat) for lat in lats) if p]
        # Keep the first coordinate's ordering (north -> south) and round for diffs.
        feature['geometry']['coordinates'] = [[round(lon, 6), round(lat, 6)] for lon, lat in line]
        feature['properties']['geometry_source'] = 'OpenStreetMap primary carriageway median (ODbL)'

    fixture['graph_version'] = GRAPH_VERSION
    fixture['metadata']['geometry_note'] = (
        'Morrissey centreline = median of OpenStreetMap highway=primary carriageways (© OpenStreetMap contributors, ODbL), '
        'sampled every ~28 m between the original fixture break latitudes. The inland control segment is unchanged. '
        'Still a labelled fixture: not a routable graph, surveyed alignment, or Person 1 canonical manifest.'
    )
    text = json.dumps(fixture, indent=2) + '\n'
    FIXTURE.write_text(text)
    FRONTEND.write_text(text)
    for feature in fixture['features']:
        print(feature['properties']['road_id'], len(feature['geometry']['coordinates']), 'points')


if __name__ == '__main__':
    main()
