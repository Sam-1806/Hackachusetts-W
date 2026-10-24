#!/usr/bin/env python3
"""Fetch and clip one official MC-FRM flood extent, then join road geometry.

The ArcGIS layer contains a statewide multipart polygon in a single feature.  A
spatial filter therefore selects the feature but does not clip its geometry.
This module deliberately performs the final rectangular clip locally and emits
small EPSG:4326 artifacts suitable for the browser.

Only polygon/line overlap is computed.  The result does not establish depth,
road-deck inundation, passability, or safety.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


SERVICE_URL = (
    "https://services1.arcgis.com/7iJyYTjCtKsZS1LR/ArcGIS/rest/services/"
    "MA_2050_1Perc_v11/FeatureServer"
)
LAYER_URL = f"{SERVICE_URL}/1"
QUERY_URL = f"{LAYER_URL}/query"
SCENARIO_ID = "mcfrm-2050-1pct"
DEFAULT_BBOX = (-71.065, 42.290, -71.035, 42.335)
FIXTURE_PATH = Path(__file__).with_name("fixtures") / "morrissey_roads.geojson"

Point = list[float]
Ring = list[Point]
Bbox = tuple[float, float, float, float]


def request_json(url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    """Read JSON with a bounded retry for transient service failures."""
    target = url
    if params:
        target = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        target,
        headers={"User-Agent": "FloodRoute-hazard-ingest/1.0"},
    )
    # The python.org macOS interpreter can lack a populated OpenSSL certificate
    # bundle even though the operating system exposes one at /etc/ssl/cert.pem.
    # Keep verification enabled and use that system bundle as a safe fallback.
    default_paths = ssl.get_default_verify_paths()
    certificate_file = default_paths.cafile
    if not certificate_file or not os.path.exists(certificate_file):
        certificate_file = "/etc/ssl/cert.pem" if os.path.exists("/etc/ssl/cert.pem") else None
    ssl_context = ssl.create_default_context(cafile=certificate_file)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90, context=ssl_context) as response:
                payload = json.load(response)
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            return payload
        except Exception as error:  # pragma: no cover - network behavior
            last_error = error
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Unable to read {url}: {last_error}")


def signed_area(ring: Sequence[Sequence[float]]) -> float:
    return sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(ring, ring[1:])
    ) / 2.0


def _clip_edge(
    ring: Ring,
    inside: Callable[[Point], bool],
    intersection: Callable[[Point, Point], Point],
) -> Ring:
    if not ring:
        return []
    output: Ring = []
    previous = ring[-1]
    previous_inside = inside(previous)
    for current in ring:
        current_inside = inside(current)
        if current_inside != previous_inside:
            output.append(intersection(previous, current))
        if current_inside:
            output.append(current)
        previous = current
        previous_inside = current_inside
    return output


def clip_ring_to_bbox(ring: Sequence[Sequence[float]], bbox: Bbox) -> Ring:
    """Sutherland-Hodgman clip for a closed geographic ring."""
    xmin, ymin, xmax, ymax = bbox
    result: Ring = [[float(point[0]), float(point[1])] for point in ring]

    def vertical(value: float) -> Callable[[Point, Point], Point]:
        def intersect(first: Point, second: Point) -> Point:
            fraction = (value - first[0]) / (second[0] - first[0])
            return [value, first[1] + fraction * (second[1] - first[1])]

        return intersect

    def horizontal(value: float) -> Callable[[Point, Point], Point]:
        def intersect(first: Point, second: Point) -> Point:
            fraction = (value - first[1]) / (second[1] - first[1])
            return [first[0] + fraction * (second[0] - first[0]), value]

        return intersect

    result = _clip_edge(result, lambda point: point[0] >= xmin, vertical(xmin))
    result = _clip_edge(result, lambda point: point[0] <= xmax, vertical(xmax))
    result = _clip_edge(result, lambda point: point[1] >= ymin, horizontal(ymin))
    result = _clip_edge(result, lambda point: point[1] <= ymax, horizontal(ymax))
    if result and result[0] != result[-1]:
        result.append(result[0])
    if len(result) < 4 or math.isclose(signed_area(result), 0.0, abs_tol=1e-13):
        return []
    return result


def point_in_ring(point: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    """Return whether a point is inside a ring (boundary counts as inside)."""
    x, y = point[:2]
    inside = False
    for first, second in zip(ring, ring[1:]):
        x1, y1 = first[:2]
        x2, y2 = second[:2]
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if math.isclose(cross, 0.0, abs_tol=1e-12) and (
            min(x1, x2) - 1e-12 <= x <= max(x1, x2) + 1e-12
            and min(y1, y2) - 1e-12 <= y <= max(y1, y2) + 1e-12
        ):
            return True
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def point_in_polygon(point: Sequence[float], rings: Sequence[Ring]) -> bool:
    """Use even/odd fill so the function is independent of ring winding."""
    return sum(1 for ring in rings if point_in_ring(point, ring)) % 2 == 1


def _orientation(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> int:
    value = (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return 0
    return 1 if value > 0 else 2


def _on_segment(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> bool:
    return (
        min(a[0], c[0]) - 1e-12 <= b[0] <= max(a[0], c[0]) + 1e-12
        and min(a[1], c[1]) - 1e-12 <= b[1] <= max(a[1], c[1]) + 1e-12
    )


def segments_intersect(
    first: Sequence[float],
    second: Sequence[float],
    third: Sequence[float],
    fourth: Sequence[float],
) -> bool:
    o1 = _orientation(first, second, third)
    o2 = _orientation(first, second, fourth)
    o3 = _orientation(third, fourth, first)
    o4 = _orientation(third, fourth, second)
    if o1 != o2 and o3 != o4:
        return True
    return any(
        (
            orientation == 0 and _on_segment(a, b, c)
            for orientation, a, b, c in (
                (o1, first, third, second),
                (o2, first, fourth, second),
                (o3, third, first, fourth),
                (o4, third, second, fourth),
            )
        )
    )


def line_intersects_polygon(line: Sequence[Sequence[float]], rings: Sequence[Ring]) -> bool:
    if any(point_in_polygon(point, rings) for point in line):
        return True
    polygon_segments = [segment for ring in rings for segment in zip(ring, ring[1:])]
    return any(
        segments_intersect(start, end, boundary_start, boundary_end)
        for start, end in zip(line, line[1:])
        for boundary_start, boundary_end in polygon_segments
    )


def clip_official_feature(feature_collection: dict[str, Any], bbox: Bbox) -> dict[str, Any]:
    features = feature_collection.get("features", [])
    if not features:
        raise ValueError("The ArcGIS response contained no intersecting feature")
    geometry = features[0].get("geometry") or {}
    if geometry.get("type") != "Polygon":
        raise ValueError(f"Expected Polygon geometry, received {geometry.get('type')}")
    clipped_rings = [
        clipped
        for ring in geometry.get("coordinates", [])
        if (clipped := clip_ring_to_bbox(ring, bbox))
    ]
    if not clipped_rings:
        raise ValueError("The official feature had no geometry inside the requested bounds")
    return {
        "type": "FeatureCollection",
        "name": "MC-FRM 2050 1% AEP — Morrissey study clip",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "bbox": list(bbox),
        "features": [
            {
                "type": "Feature",
                "id": features[0].get("id"),
                "properties": {
                    **features[0].get("properties", {}),
                    "scenario_id": SCENARIO_ID,
                    "scenario_type": "published_future_model",
                    "horizon_year": 2050,
                    "annual_exceedance_probability": 0.01,
                    "depth_m": None,
                    "data_status": "published_model",
                    "source_url": LAYER_URL,
                    "processing_note": "Statewide feature clipped to study bbox; geometry simplified by ArcGIS query.",
                },
                "geometry": {"type": "Polygon", "coordinates": clipped_rings},
            }
        ],
    }


def iter_lines(geometry: dict[str, Any]) -> Iterable[Sequence[Sequence[float]]]:
    if geometry.get("type") == "LineString":
        yield geometry.get("coordinates", [])
    elif geometry.get("type") == "MultiLineString":
        yield from geometry.get("coordinates", [])


def build_exposure(
    extent: dict[str, Any],
    roads: dict[str, Any],
    road_source: str,
) -> dict[str, Any]:
    rings = extent["features"][0]["geometry"]["coordinates"]
    # Accept either a bare GeoJSON FeatureCollection or the provisional
    # RoadManifest wrapper: {graph_version, roads: FeatureCollection, ...}.
    road_features = roads.get("roads", roads)
    affected_roads: list[dict[str, Any]] = []
    for feature in road_features.get("features", []):
        properties = feature.get("properties", {})
        road_id = properties.get("road_id") or properties.get("id")
        if not road_id:
            raise ValueError("Every road feature must have properties.road_id")
        exposed = any(line_intersects_polygon(line, rings) for line in iter_lines(feature["geometry"]))
        affected_roads.append(
            {
                "road_id": road_id,
                "corridor_id": properties.get("corridor_id"),
                "exposure": "exposed" if exposed else "not_exposed",
                "depth_m": None,
                "passability": "unknown",
                "passability_basis": (
                    "Official extent geometry overlap only; road-deck elevation, local water depth, "
                    "and drivability were not established."
                ),
                "basis": "official_extent",
                "source_id": "mcfrm-2050-1pct-extent",
                "provenance": "computed",
            }
        )
    graph_version = (
        roads.get("graph_version")
        or road_features.get("graph_version")
        or roads.get("metadata", {}).get("graph_version")
    )
    if not graph_version:
        graph_version = "unknown-road-manifest"
    return {
        "schema_version": "flood-exposure-result/v1",
        "scenario_id": SCENARIO_ID,
        "graph_version": graph_version,
        "scenario_type": "published_future_model",
        "scenario": {
            "horizon_year": 2050,
            "annual_exceedance_probability": 0.01,
            "annual_exceedance_label": "1% annual exceedance probability",
            "is_historical_event": False,
            "is_live_forecast": False,
            "depth_available": False,
        },
        "affected_roads": affected_roads,
        "extent_geojson_ref": "mcfrm_2050_1pct_morrissey.geojson",
        "provenance": {
            "origin": "published_model",
            "source_id": "mcfrm-2050-1pct-extent",
            "source_url": LAYER_URL,
            "publisher_attribution": "Woods Hole Group; published through the Massachusetts ArcGIS service",
            "source_crs": "EPSG:26986 (NAD83 / Massachusetts Mainland)",
            "output_crs": "EPSG:4326",
            "road_source": road_source,
            "processing": "ArcGIS envelope query, server transform to EPSG:4326, local bbox clip, line/polygon overlap",
            "limitations": [
                "Polygon overlap is exposure evidence, not confirmed road inundation or impassability.",
                "This extent layer does not provide authoritative road-level depth; depth_m is null.",
                "The 2050 horizon is a modeled future condition, not a historical date or live forecast.",
                "The bounded browser artifact is simplified for visualization and is not a replacement for source data.",
            ],
        },
    }


def fetch_feature(bbox: Bbox) -> dict[str, Any]:
    return request_json(
        QUERY_URL,
        {
            "where": "1=1",
            "geometry": ",".join(str(value) for value in bbox),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "FID,Id,gridcode",
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "6",
            "maxAllowableOffset": "0.00002",
            "f": "geojson",
        },
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_bbox(value: str) -> Bbox:
    parts = tuple(float(part) for part in value.split(","))
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise argparse.ArgumentTypeError("bbox must be xmin,ymin,xmax,ymax")
    return parts  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", type=parse_bbox, default=DEFAULT_BBOX)
    parser.add_argument("--road-manifest", type=Path)
    parser.add_argument("--offline-feature", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/hazard"))
    args = parser.parse_args()

    service_metadata = request_json(SERVICE_URL, {"f": "json"}) if not args.offline_feature else None
    layer_metadata = request_json(LAYER_URL, {"f": "json"}) if not args.offline_feature else None
    source_feature = (
        json.loads(args.offline_feature.read_text(encoding="utf-8"))
        if args.offline_feature
        else fetch_feature(args.bbox)
    )
    extent = clip_official_feature(source_feature, args.bbox)

    road_path = args.road_manifest or FIXTURE_PATH
    roads = json.loads(road_path.read_text(encoding="utf-8"))
    road_source = str(args.road_manifest) if args.road_manifest else (
        "analysis/hazard/fixtures/morrissey_roads.geojson "
        "(labeled fixture; replace with Person 1 canonical manifest)"
    )
    exposure = build_exposure(extent, roads, road_source)

    source_record = {
        "source_id": "mcfrm-2050-1pct-extent",
        "service_url": SERVICE_URL,
        "layer_url": LAYER_URL,
        "service_item_id": (service_metadata or {}).get("serviceItemId", "101f62d8bb8445a59c12a6a4eb118c59"),
        "layer_id": 1,
        "layer_name": (layer_metadata or {}).get("name", "MCFRM_1pct_2050"),
        "description": (
            "Projected coastal flooding in Massachusetts driven by sea level rise and storm surge "
            "for the 2050 1% annual exceedance probability scenario."
        ),
        "copyright_text": (service_metadata or {}).get("copyrightText", "Woods Hole Group"),
        "source_spatial_reference": "EPSG:26986",
        "source_units": "meters",
        "output_spatial_reference": "EPSG:4326",
        "geometry_type": (layer_metadata or {}).get("geometryType", "esriGeometryPolygon"),
        "native_extent": (layer_metadata or {}).get(
            "extent",
            {
                "xmin": 213004,
                "ymin": 776516,
                "xmax": 331848,
                "ymax": 959746,
                "spatialReference": {"wkid": 26986},
            },
        ),
        "source_data_last_edit_utc": (
            datetime.fromtimestamp(
                (layer_metadata or {}).get("editingInfo", {}).get("dataLastEditDate", 1727369875344)
                / 1000,
                tz=timezone.utc,
            ).isoformat()
        ),
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "fields": [
            {"name": field.get("name"), "type": field.get("type")}
            for field in (layer_metadata or {}).get("fields", [])
        ]
        or [
            {"name": "FID", "type": "esriFieldTypeOID"},
            {"name": "Id", "type": "esriFieldTypeInteger"},
            {"name": "gridcode", "type": "esriFieldTypeInteger"},
            {"name": "Shape__Area", "type": "esriFieldTypeDouble"},
            {"name": "Shape__Length", "type": "esriFieldTypeDouble"},
        ],
        "study_bbox_epsg4326": list(args.bbox),
        "feature_count_in_query": len(source_feature.get("features", [])),
        "status": "official_published_model_extent_loaded",
        "limitations": [
            "The layer represents a future 2050 1% AEP scenario, not an observed event.",
            "No depth attribute is present in this vector extent layer.",
            "ArcGIS returns the statewide feature; this pipeline clips it locally to the study bbox.",
        ],
    }
    write_json(args.output_dir / "mcfrm_2050_1pct_morrissey.geojson", extent)
    write_json(args.output_dir / "flood_exposure_mcfrm_2050_1pct.json", exposure)
    write_json(args.output_dir / "mcfrm_2050_1pct_source_metadata.json", source_record)

    exposed_count = sum(road["exposure"] == "exposed" for road in exposure["affected_roads"])
    print(
        f"Wrote official extent and exposure result to {args.output_dir}; "
        f"{exposed_count}/{len(exposure['affected_roads'])} road features overlap."
    )


if __name__ == "__main__":
    main()
