#!/usr/bin/env python3
"""Extract a small EPSG:4326 subset from NOAA STOFS disturbance GeoPackages.

The source GeoPackages contain 18 domain-wide multipolygon water-level bands.
This script uses only Python's standard library, parses the GeoPackage/WKB
geometry, clips it to a supplied bounding box, and writes a compact animation
sidecar. The result remains archived *forecast guidance*, not an observation or
historical hindcast.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence


BBOX = (-71.065, 42.29, -71.035, 42.335)
SOURCE_PREFIX = (
    "https://noaa-nos-stofs3d-pds.s3.amazonaws.com/STOFS-3D-Atl/"
    "stofs_3d_atl.20240113/"
)


class WkbReader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = memoryview(data)
        self.offset = offset

    def unpack(self, fmt: str, endian: str) -> tuple[Any, ...]:
        size = struct.calcsize(endian + fmt)
        result = struct.unpack_from(endian + fmt, self.data, self.offset)
        self.offset += size
        return result

    def geometry(self) -> dict[str, Any]:
        byte_order = self.data[self.offset]
        self.offset += 1
        endian = "<" if byte_order == 1 else ">"
        raw_type = self.unpack("I", endian)[0]
        geometry_type = raw_type % 1000
        dimensions = 3 if 1000 <= raw_type < 2000 else 2
        if raw_type & 0x80000000:
            dimensions = 3
            geometry_type = raw_type & 0xFF
        if geometry_type == 3:
            rings = []
            for _ in range(self.unpack("I", endian)[0]):
                ring = [list(self.unpack("d" * dimensions, endian)[:2]) for _ in range(self.unpack("I", endian)[0])]
                rings.append(ring)
            return {"type": "Polygon", "coordinates": rings}
        if geometry_type == 6:
            polygons = []
            for _ in range(self.unpack("I", endian)[0]):
                child = self.geometry()
                if child["type"] != "Polygon":
                    raise ValueError("MultiPolygon contained a non-polygon child")
                polygons.append(child["coordinates"])
            return {"type": "MultiPolygon", "coordinates": polygons}
        raise ValueError(f"Unsupported WKB geometry type {raw_type}")


def decode_gpkg_geometry(blob: bytes) -> dict[str, Any]:
    if blob[:2] != b"GP":
        raise ValueError("Not a GeoPackage geometry")
    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    envelope_sizes = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
    if envelope_code not in envelope_sizes:
        raise ValueError(f"Unsupported GeoPackage envelope code {envelope_code}")
    return WkbReader(blob, 8 + envelope_sizes[envelope_code]).geometry()


def _clip_edge(ring, inside, intersection):
    if not ring:
        return []
    output = []
    previous = ring[-1]
    previous_inside = inside(previous)
    for current in ring:
        current_inside = inside(current)
        if current_inside != previous_inside:
            output.append(intersection(previous, current))
        if current_inside:
            output.append(current)
        previous, previous_inside = current, current_inside
    return output


def clip_ring(ring: Sequence[Sequence[float]], bbox=BBOX) -> list[list[float]]:
    xmin, ymin, xmax, ymax = bbox
    result = [[float(point[0]), float(point[1])] for point in ring]

    def vertical(x):
        return lambda a, b: [x, a[1] + (x - a[0]) * (b[1] - a[1]) / (b[0] - a[0])]

    def horizontal(y):
        return lambda a, b: [a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]), y]

    result = _clip_edge(result, lambda point: point[0] >= xmin, vertical(xmin))
    result = _clip_edge(result, lambda point: point[0] <= xmax, vertical(xmax))
    result = _clip_edge(result, lambda point: point[1] >= ymin, horizontal(ymin))
    result = _clip_edge(result, lambda point: point[1] <= ymax, horizontal(ymax))
    if result and result[0] != result[-1]:
        result.append(result[0])
    return result if len(result) >= 4 else []


def clip_geometry(geometry: dict[str, Any], bbox=BBOX) -> dict[str, Any] | None:
    source_polygons = (
        [geometry["coordinates"]]
        if geometry["type"] == "Polygon"
        else geometry["coordinates"]
    )
    polygons = []
    for rings in source_polygons:
        exterior = clip_ring(rings[0], bbox)
        if not exterior:
            continue
        clipped = [exterior]
        clipped.extend(hole for ring in rings[1:] if (hole := clip_ring(ring, bbox)))
        polygons.append(clipped)
    return {"type": "MultiPolygon", "coordinates": polygons} if polygons else None


def frame(path: Path, run_time: datetime, bbox=BBOX) -> dict[str, Any]:
    forecast_hour = int(path.stem.split(".f")[-1])
    valid_time = run_time + timedelta(hours=forecast_hour)
    features = []
    with sqlite3.connect(path) as database:
        rows = database.execute(
            "SELECT id,minWaterLevel,maxWaterLevel,verticalDatum,units,geom "
            "FROM disturbance ORDER BY id"
        )
        for band_id, minimum, maximum, datum, units, blob in rows:
            clipped = clip_geometry(decode_gpkg_geometry(blob), bbox)
            if clipped:
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "band_id": band_id,
                            "min_water_level_m": None if minimum < -1000 else minimum,
                            "max_water_level_m": maximum,
                            "vertical_datum": datum,
                            "units": units,
                            "field": "water_level_disturbance",
                        },
                        "geometry": clipped,
                    }
                )
    key = f"stofs_3d_atl.t12z.disturbance.f{forecast_hour:03d}.gpkg"
    return {
        "forecast_hour": forecast_hour,
        "valid_time_utc": valid_time.isoformat().replace("+00:00", "Z"),
        "source_object_key": f"STOFS-3D-Atl/stofs_3d_atl.20240113/{key}",
        "source_url": SOURCE_PREFIX + key,
        "features": features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("geopackages", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_time = datetime(2024, 1, 13, 12, tzinfo=timezone.utc)
    frames = sorted((frame(path, run_time) for path in args.geopackages), key=lambda item: item["forecast_hour"])
    payload = {
        "schema_version": "stofs-disturbance-animation/v1",
        "scenario_id": "stofs-3d-atl-20240113t12z-boston-guidance",
        "event_id": "boston-2024-01-13-coastal-flood",
        "model": "NOAA STOFS-3D-Atlantic v1.1",
        "model_run_initialization_utc": "2024-01-13T12:00:00Z",
        "evidence_status": "archived_operational_forecast_guidance",
        "bbox_epsg4326": list(BBOX),
        "historical_observation_context": {
            "station_id": "8443970",
            "station_name": "Boston, MA",
            "product": "verified_water_level",
            "interval": "6 minutes",
            "units": "meters",
            "vertical_datum": "NAVD88",
            "source_url": (
                "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
                "product=water_level&application=FloodRoute&begin_date=20240113%2012:00&"
                "end_date=20240113%2020:00&datum=NAVD&station=8443970&time_zone=gmt&"
                "units=metric&format=json"
            ),
            "scope_note": "Point gauge context only; it is not a road-depth observation or spatial flood footprint.",
        },
        "field": {
            "name": "water_level_disturbance",
            "units": "meters",
            "vertical_datum": "NAVD88",
            "meaning": "Water above ground on model land cells, or elevation above xGEOID20B over water, distributed here as 0.1 m bands.",
        },
        "local_mesh_audit": {
            "mesh_version": "v1.1",
            "study_nodes": 138,
            "elements_with_a_study_node": 301,
            "edge_length_m": {"min": 138.7, "p10": 220.2, "median": 280.3, "p90": 394.5, "max": 603.3},
            "interpretation": "The Boston study-area mesh is neighborhood/coastal scale, not building- or lane-resolving.",
        },
        "frames": frames,
        "limitations": [
            "These frames are archived operational forecast guidance initialized during the event, not observations or a calibrated hindcast.",
            "The local mesh is too coarse to support building-scale flow, road-lane depth, or object-level collision claims.",
            "The disturbance GeoPackages contain binned polygons, not velocity vectors.",
            "Do not treat a band touching a road or building as proof of measured inundation there.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(frames)} frames and {sum(len(item['features']) for item in frames)} clipped bands to {args.output}")


if __name__ == "__main__":
    main()
