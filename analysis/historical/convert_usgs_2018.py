#!/usr/bin/env python3
"""Clip an official USGS 2018 inundation-map shapefile for browser display.

This preserves an event's estimated peak footprint. It does not construct time
steps, local water depth, flow direction, velocity, or a hydraulic replay.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from shapely.validation import make_valid

DEFAULT_BBOX = (-71.065, 42.29, -71.035, 42.335)


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = tuple(float(part) for part in value.split(','))
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise argparse.ArgumentTypeError('bbox must be xmin,ymin,xmax,ymax')
    return parts  # type: ignore[return-value]


def convert_archive(
    archive: Path,
    output: Path,
    event_id: str,
    event_label: str,
    event_date: str,
    source_url: str,
    bbox: tuple[float, float, float, float],
) -> dict:
    with tempfile.TemporaryDirectory(prefix='floodroute-usgs-') as directory:
        extracted = Path(directory)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(extracted)
        shapefile_path = next(extracted.glob('*.shp'))
        projection_path = next(extracted.glob('*.prj'))
        source_crs = CRS.from_wkt(projection_path.read_text(encoding='utf-8'))
        transformer = Transformer.from_crs(source_crs, 'EPSG:4326', always_xy=True)
        clip = box(*bbox)
        reader = shapefile.Reader(str(shapefile_path))
        field_names = [field[0] for field in reader.fields[1:]]
        features = []

        for shape_record in reader.iterShapeRecords():
            properties = dict(zip(field_names, shape_record.record))
            geometry = make_valid(shape(shape_record.shape.__geo_interface__))
            geographic = transform(transformer.transform, geometry)
            if not geographic.intersects(clip):
                continue
            clipped = make_valid(geographic.intersection(clip)).simplify(0.000006, preserve_topology=True)
            if clipped.is_empty:
                continue
            features.append({
                'type': 'Feature',
                'properties': {
                    'event_id': event_id,
                    'event_label': event_label,
                    'event_date': event_date,
                    'peak_wse_ft_navd88': properties.get('WSE_FT'),
                    'data_status': 'observed_event_estimated_peak_extent',
                    'source_url': source_url,
                    'limitations': (
                        'Estimated peak footprint derived from high-water marks and sensors; '
                        'not time-resolved and not a road-depth or velocity field.'
                    ),
                },
                'geometry': mapping(clipped),
            })

    result = {
        'type': 'FeatureCollection',
        'name': event_label,
        'bbox': list(bbox),
        'features': features,
        'metadata': {
            'event_id': event_id,
            'event_date': event_date,
            'source_url': source_url,
            'source_crs': source_crs.to_string(),
            'output_crs': 'EPSG:4326',
            'status': 'observed_event_estimated_peak_extent',
            'limitations': [
                'The footprint represents an estimated event peak, not time-varying water.',
                'Water-surface elevation attributes use NAVD88 and are not treated as Cesium ellipsoid heights.',
                'Road depth, velocity, direction, and passability remain unknown.',
            ],
        },
    }
    if not features:
        raise RuntimeError(f'No {event_id} footprint intersects {bbox}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(',', ':')) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--event-id', required=True)
    parser.add_argument('--event-label', required=True)
    parser.add_argument('--event-date', required=True)
    parser.add_argument('--source-url', required=True)
    parser.add_argument('--bbox', type=parse_bbox, default=DEFAULT_BBOX)
    args = parser.parse_args()
    result = convert_archive(
        args.archive, args.output, args.event_id, args.event_label,
        args.event_date, args.source_url, args.bbox,
    )
    print(f"Wrote {len(result['features'])} clipped feature(s) to {args.output}")


if __name__ == '__main__':
    main()
