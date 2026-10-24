#!/usr/bin/env python3
"""Audit native STOFS mesh spacing around the Morrissey study bbox."""

from __future__ import annotations

import argparse
import json
import math
from array import array
from pathlib import Path


DEFAULT_BBOX = (-71.065, 42.29, -71.035, 42.335)
EARTH_RADIUS_M = 6_371_008.8


def edge_distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(value))


def percentile(values: list[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path, help="STOFS hgrid.ll file")
    parser.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX)
    args = parser.parse_args()
    xmin, ymin, xmax, ymax = args.bbox

    with args.mesh.open(encoding="utf-8") as source:
        source.readline()
        element_count, node_count = map(int, source.readline().split())
        longitudes = array("d", [math.nan])
        latitudes = array("d", [math.nan])
        inside = bytearray(node_count + 1)
        study_nodes = 0
        for expected_id in range(1, node_count + 1):
            fields = source.readline().split()
            node_id = int(fields[0])
            if node_id != expected_id:
                raise ValueError(f"Expected node {expected_id}, received {node_id}")
            longitude, latitude = float(fields[1]), float(fields[2])
            longitudes.append(longitude)
            latitudes.append(latitude)
            if xmin <= longitude <= xmax and ymin <= latitude <= ymax:
                inside[node_id] = 1
                study_nodes += 1

        edges: set[tuple[int, int]] = set()
        touching_elements = 0
        for expected_id in range(1, element_count + 1):
            fields = source.readline().split()
            element_id, vertex_count = int(fields[0]), int(fields[1])
            if element_id != expected_id:
                raise ValueError(f"Expected element {expected_id}, received {element_id}")
            vertices = [int(value) for value in fields[2 : 2 + vertex_count]]
            if any(inside[node_id] for node_id in vertices):
                touching_elements += 1
                for index, first in enumerate(vertices):
                    second = vertices[(index + 1) % len(vertices)]
                    edges.add((first, second) if first < second else (second, first))

    lengths = sorted(
        edge_distance_m(
            (longitudes[first], latitudes[first]),
            (longitudes[second], latitudes[second]),
        )
        for first, second in edges
    )
    result = {
        "bbox_epsg4326": list(args.bbox),
        "mesh_nodes": node_count,
        "mesh_elements": element_count,
        "study_nodes": study_nodes,
        "elements_with_a_study_node": touching_elements,
        "unique_edges": len(lengths),
        "edge_length_m": {
            "min": round(lengths[0], 1),
            "p10": round(percentile(lengths, 0.10), 1),
            "median": round(percentile(lengths, 0.50), 1),
            "p90": round(percentile(lengths, 0.90), 1),
            "max": round(lengths[-1], 1),
        },
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
