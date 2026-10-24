"""Road facts: fetch, normalize, and join MassDOT Road Inventory attributes.

Source S10: City of Boston GIS portal, Infrastructure/OpenData MapServer layer 14
("MassDOT Road Inventory"). Attributes are coded strings; blank values (" ")
are treated as *missing*, never as zero.

Code meanings (e.g. Surface_Tp = "6", Jurisdictn = "3") are deliberately NOT
decoded here: the MassDOT data dictionary could not be retrieved during the
build (HTTP 403), so the raw code is passed through with a pointer to the
dictionary. Width units are recorded as ``ft (assumed)`` for the same reason.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

LAYER_URL = (
    "https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/"
    "OpenData/MapServer/14"
)
DATA_DICTIONARY_URL = "https://www.mass.gov/doc/road-inventory-data-dictionary/download"
SOURCE_ID = "S10"

# field -> (fact key, label, unit, value kind)
# kind: "number" -> parsed to float; "code" -> raw code string, meaning not decoded;
#       "text" -> as-is.
FIELD_MAP: dict[str, tuple[str, str, str | None, str]] = {
    "St_Name": ("street_name", "Street name", None, "text"),
    "Fm_St_Name": ("from_street", "From street", None, "text"),
    "To_St_Name": ("to_street", "To street", None, "text"),
    "Rd_Seg_ID": ("inventory_segment_id", "Road Inventory segment ID", None, "text"),
    "Num_Lanes": ("num_lanes", "Number of lanes", "lanes", "number"),
    "Surface_Wd": ("surface_width", "Surface width", "ft (assumed)", "number"),
    "ROW_Width": ("right_of_way_width", "Right-of-way width", "ft (assumed)", "number"),
    "Med_Width": ("median_width", "Median width", "ft (assumed)", "number"),
    "AADT": ("aadt", "Annual average daily traffic", "vehicles/day", "number"),
    "AADT_Year": ("aadt_year", "AADT year", None, "text"),
    "Surface_Tp": ("surface_type_code", "Surface type (code)", None, "code"),
    "F_Class": ("functional_class_code", "State functional class (code)", None, "code"),
    "Jurisdictn": ("jurisdiction_code", "Jurisdiction (code)", None, "code"),
    "Struct_Cnd": ("structural_condition_code", "Structural condition (code)", None, "code"),
    "Curb": ("curb_code", "Curb (code)", None, "code"),
    "Med_Type": ("median_type_code", "Median type (code)", None, "code"),
    "Operation": ("operation_code", "Street operation (code)", None, "code"),
}

# Facts an engineer needs that the Road Inventory does not provide. These are
# always reported as unavailable rather than guessed.
NOT_IN_INVENTORY = [
    ("pavement_structure", "Pavement structure / layer thicknesses and materials"),
    ("road_surface_elevation", "Surveyed road crown / edge-of-pavement elevation (with vertical datum)"),
    ("drainage_capacity", "Storm drain inlet and pipe capacity, outfall locations and tide-gate status"),
    ("subsurface_utilities", "Underground utilities (water, sewer, gas, electric, telecom) and depths"),
    ("geotechnical", "Soil / groundwater conditions and foundation suitability"),
    ("adjacent_setbacks", "Building setbacks and first-floor elevations adjacent to the right-of-way"),
]


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _to_number(v: Any) -> float | None:
    if _blank(v):
        return None
    try:
        return float(str(v).strip())
    except ValueError:
        return None


# --------------------------------------------------------------------------- fetch


def build_query_url(where: str, out_fields: Iterable[str] | None = None, offset: int = 0) -> str:
    fields = ",".join(out_fields) if out_fields else ",".join(FIELD_MAP) + ",Length"
    params = {
        "where": where,
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "resultOffset": str(offset),
        "f": "json",
    }
    return f"{LAYER_URL}/query?{urllib.parse.urlencode(params)}"


def fetch_inventory(where: str, timeout: int = 60, max_pages: int = 20) -> dict:
    """Fetch Road Inventory records as a GeoJSON FeatureCollection (EPSG:4326).

    ``where`` is an ArcGIS SQL clause passed as a URL-encoded parameter.
    """
    features: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        url = build_query_url(where, offset=offset)
        req = urllib.request.Request(url, headers={"User-Agent": "FloodRoute-engineering/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https host)
            payload = json.loads(resp.read().decode("utf-8"))
        if "error" in payload:
            raise RuntimeError(f"ArcGIS error: {payload['error']}")
        batch = payload.get("features", [])
        for f in batch:
            paths = (f.get("geometry") or {}).get("paths") or []
            geom = (
                {"type": "MultiLineString", "coordinates": paths}
                if len(paths) != 1
                else {"type": "LineString", "coordinates": paths[0]}
            )
            features.append({"type": "Feature", "properties": f.get("attributes", {}), "geometry": geom})
        if not payload.get("exceededTransferLimit"):
            break
        offset += len(batch)
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source_id": SOURCE_ID,
            "source_url": LAYER_URL,
            "query_where": where,
            "crs": "EPSG:4326 (reprojected by server from EPSG:2249)",
            "data_status": "observed",
            "record_count": len(features),
        },
    }


# ------------------------------------------------------------------- normalization


def normalize_record(props: dict) -> dict:
    """Turn one raw inventory attribute dict into provenance-tagged facts.

    Missing values are emitted with ``value: None`` and ``status: "not_available"``.
    """
    facts: dict[str, dict] = {}
    for field, (key, label, unit, kind) in FIELD_MAP.items():
        raw = props.get(field)
        if _blank(raw):
            value, status = None, "not_available"
        elif kind == "number":
            value = _to_number(raw)
            status = "observed" if value is not None else "not_available"
        else:
            value, status = str(raw).strip(), "observed"
        fact = {"label": label, "value": value, "unit": unit, "status": status,
                "source_id": SOURCE_ID, "source_field": field}
        if kind == "code" and status == "observed":
            fact["note"] = f"Raw MassDOT code; decode with the Road Inventory data dictionary ({DATA_DICTIONARY_URL})."
        if unit and "assumed" in unit:
            fact["unit_note"] = "Unit assumed from MassDOT Road Inventory convention; confirm in data dictionary."
        facts[key] = fact
    return facts


def summarize_corridor_facts(records: list[dict]) -> dict:
    """Aggregate per-segment facts into a corridor-level summary.

    Numeric fields report min/max over observed values; code/text fields report
    the distinct observed values. Each summary keeps the count of segments with
    missing values so gaps stay visible.
    """
    normalized = [normalize_record(r) for r in records]
    summary: dict[str, dict] = {}
    for field, (key, label, unit, kind) in FIELD_MAP.items():
        if key == "inventory_segment_id":
            continue
        vals = [n[key]["value"] for n in normalized if n[key]["value"] is not None]
        missing = len(normalized) - len(vals)
        entry: dict[str, Any] = {"label": label, "unit": unit, "source_id": SOURCE_ID,
                                 "source_field": field, "segments_total": len(normalized),
                                 "segments_missing": missing}
        if not vals:
            entry.update(status="not_available", value=None)
        elif kind == "number":
            lo, hi = min(vals), max(vals)
            entry.update(status="observed", value=lo if lo == hi else None, range=[lo, hi])
        else:
            distinct = sorted(set(vals))
            entry.update(status="observed", value=distinct[0] if len(distinct) == 1 else None,
                         distinct_values=distinct)
        if kind == "code" and entry["status"] == "observed":
            entry["note"] = "Raw MassDOT code(s); meaning not decoded in this build."
        if unit and "assumed" in unit:
            entry["unit_note"] = "Unit assumed; confirm in MassDOT data dictionary."
        summary[key] = entry

    for key, label in NOT_IN_INVENTORY:
        summary[key] = {"label": label, "value": None, "status": "not_available",
                        "note": "Not in Road Inventory; requires site survey / owner records."}
    summary["_segment_ids"] = sorted({n["inventory_segment_id"]["value"] for n in normalized
                                      if n["inventory_segment_id"]["value"]})
    return summary


# ------------------------------------------------------------------- spatial join


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


def _vertices(geom: dict | None) -> list[tuple[float, float]]:
    if not geom:
        return []
    if geom["type"] == "LineString":
        return [tuple(c[:2]) for c in geom["coordinates"]]
    if geom["type"] == "MultiLineString":
        return [tuple(c[:2]) for line in geom["coordinates"] for c in line]
    return []


def _name_tokens(s: str | None) -> set[str]:
    stop = {"ST", "STREET", "AVE", "AVENUE", "BLVD", "BOULEVARD", "RD", "ROAD", "WILLIAM", "T", "DR", "DRIVE"}
    return {t for t in (s or "").upper().replace(".", " ").split() if t not in stop}


def spatial_join(manifest_roads: list[dict], inventory: list[dict], max_distance_m: float = 25.0) -> dict:
    """Match canonical road features (Person 1 manifest) to inventory records.

    Match rule: mean distance from road vertices to the nearest inventory vertex
    must be <= ``max_distance_m``; street-name token overlap is required when
    both sides carry a name. Returns ``{road_id: {"records": [...], "match": {...}}}``.
    Unmatched roads get an empty record list, so the gap is explicit.
    """
    inv_vertices = [(_vertices(f.get("geometry")), f) for f in inventory]
    out: dict[str, dict] = {}
    for road in manifest_roads:
        props = road.get("properties", {})
        road_id = props["road_id"]
        verts = _vertices(road.get("geometry"))
        name = _name_tokens(props.get("name") or props.get("street"))
        matches = []
        for iverts, feat in inv_vertices:
            if not verts or not iverts:
                continue
            inv_name = _name_tokens(feat["properties"].get("St_Name"))
            if name and inv_name and not (name & inv_name):
                continue
            mean_d = sum(min(_haversine_m(v, w) for w in iverts) for v in verts) / len(verts)
            if mean_d <= max_distance_m:
                matches.append((mean_d, feat))
        matches.sort(key=lambda m: m[0])
        out[road_id] = {
            "records": [m[1]["properties"] for m in matches],
            "match": {
                "method": "vertex-distance + street-name tokens",
                "max_distance_m": max_distance_m,
                "best_mean_distance_m": round(matches[0][0], 2) if matches else None,
                "matched_count": len(matches),
                "data_status": "derived",
            },
        }
    return out


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
