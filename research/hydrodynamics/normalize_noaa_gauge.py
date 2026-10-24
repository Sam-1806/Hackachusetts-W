#!/usr/bin/env python3
"""Normalize an official NOAA CO-OPS verified water-level response."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SOURCE_URL = (
    "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?"
    "product=water_level&application=FloodRoute&begin_date=20240113%2012:00&"
    "end_date=20240113%2020:00&datum=NAVD&station=8443970&time_zone=gmt&"
    "units=metric&format=json"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Raw NOAA CO-OPS JSON response")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    if "error" in source:
        raise ValueError(source["error"])
    metadata = source["metadata"]
    if metadata["id"] != "8443970":
        raise ValueError(f"Expected station 8443970, received {metadata['id']}")

    observations = []
    for item in source["data"]:
        timestamp = datetime.strptime(item["t"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        observations.append(
            {
                "time_utc": timestamp.isoformat().replace("+00:00", "Z"),
                "water_level_m_navd88": float(item["v"]),
                "sigma_m": float(item["s"]),
                "quality": "verified" if item["q"] == "v" else item["q"],
            }
        )

    peak = max(observations, key=lambda item: item["water_level_m_navd88"])
    payload = {
        "schema_version": "noaa-coops-water-level/v1",
        "event_id": "boston-2024-01-13-coastal-flood",
        "evidence_status": "observed_point_gauge",
        "station": {
            "station_id": metadata["id"],
            "name": metadata["name"],
            "longitude": float(metadata["lon"]),
            "latitude": float(metadata["lat"]),
        },
        "product": "verified_water_level",
        "interval": "6 minutes",
        "units": "meters",
        "vertical_datum": "NAVD88",
        "source_url": SOURCE_URL,
        "peak_in_window": peak,
        "observations": observations,
        "limitations": [
            "This is an observed water level at a single Boston Harbor tide gauge, not a road-depth measurement.",
            "Do not spatially extrapolate the gauge values to buildings, roads, or flood extents.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(observations)} observations; peak {peak['water_level_m_navd88']:.3f} m "
        f"at {peak['time_utc']} to {args.output}"
    )


if __name__ == "__main__":
    main()
