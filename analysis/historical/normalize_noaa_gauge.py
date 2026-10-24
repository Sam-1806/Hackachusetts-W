#!/usr/bin/env python3
"""Normalize NOAA CO-OPS hourly heights into the historical UI contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def normalize(path: Path, event_id: str) -> dict:
    source = json.loads(path.read_text(encoding='utf-8'))
    if source.get('error'):
        raise RuntimeError(source['error'])
    metadata = source['metadata']
    return {
        'event_id': event_id,
        'station_id': metadata['id'],
        'station_name': metadata['name'],
        'longitude': float(metadata['lon']),
        'latitude': float(metadata['lat']),
        'parameter': 'verified hourly water level',
        'unit': 'm',
        'datum': 'NAVD88',
        'time_zone': 'GMT',
        'source_url': 'https://api.tidesandcurrents.noaa.gov/api/prod/',
        'observations': [
            {
                'timestamp': item['t'].replace(' ', 'T') + ':00Z',
                'value': float(item['v']),
                'quality': 'verified' if item.get('f', '').split(',')[-1:] == ['0'] else 'unknown',
            }
            for item in source['data']
            if item.get('v') not in (None, '')
        ],
        'limitations': [
            'A harbor tide gauge is not a street-level water-depth sensor.',
            'Gauge levels do not establish local flow direction or velocity.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--january', type=Path, required=True)
    parser.add_argument('--march', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = {
        'schema_version': 'historical-gauge-series/v1',
        'series': [
            normalize(args.january, 'usgs-2018-01-04'),
            normalize(args.march, 'usgs-2018-03-02'),
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(f"Wrote {sum(len(item['observations']) for item in output['series'])} hourly observations")


if __name__ == '__main__':
    main()
