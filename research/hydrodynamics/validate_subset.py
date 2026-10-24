#!/usr/bin/env python3
"""Validate the normalized STOFS browser sidecar without third-party packages."""

import json
from pathlib import Path


PATH = Path("results/hydrodynamics/stofs_20240113_boston_disturbance.json")
GAUGE_PATH = Path("results/hydrodynamics/noaa_8443970_20240113_water_level.json")
BBOX = (-71.065, 42.29, -71.035, 42.335)


def positions(value):
    if isinstance(value, list) and len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from positions(item)


data = json.loads(PATH.read_text(encoding="utf-8"))
assert data["evidence_status"] == "archived_operational_forecast_guidance"
assert data["scenario_id"] == "stofs-3d-atl-20240113t12z-boston-guidance"
assert data["bbox_epsg4326"] == list(BBOX)
assert data["historical_observation_context"]["station_id"] == "8443970"
assert [frame["forecast_hour"] for frame in data["frames"]] == [1, 4, 7]
assert data["local_mesh_audit"]["edge_length_m"]["median"] == 280.3
assert all(frame["features"] for frame in data["frames"])
for frame in data["frames"]:
    for feature in frame["features"]:
        assert feature["geometry"]["type"] == "MultiPolygon"
        assert feature["properties"]["vertical_datum"] == "NAVD88"
        for longitude, latitude, *_ in positions(feature["geometry"]["coordinates"]):
            assert BBOX[0] - 1e-9 <= longitude <= BBOX[2] + 1e-9
            assert BBOX[1] - 1e-9 <= latitude <= BBOX[3] + 1e-9
print(f"Validated {len(data['frames'])} STOFS frames in {PATH}.")

gauge = json.loads(GAUGE_PATH.read_text(encoding="utf-8"))
assert gauge["evidence_status"] == "observed_point_gauge"
assert gauge["station"]["station_id"] == "8443970"
assert gauge["vertical_datum"] == "NAVD88"
assert len(gauge["observations"]) == 81
assert gauge["peak_in_window"]["time_utc"] == "2024-01-13T16:48:00Z"
assert gauge["peak_in_window"]["water_level_m_navd88"] == 2.713
assert all(item["quality"] == "verified" for item in gauge["observations"])
print(f"Validated {len(gauge['observations'])} NOAA gauge observations in {GAUGE_PATH}.")
