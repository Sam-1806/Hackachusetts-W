"""Fetch drainage-related evidence near a corridor and save it with retrieval metadata.

Sources (both tested for machine-readable access on 2026-10-24):
  * BWSC catch basins: public ArcGIS FeatureServer behind BWSC's Catch Basin Locator map.
    No licence/terms text was found on the item; treat as public reference data and do not bulk-redistribute.
  * Boston 311 service requests (data.boston.gov CKAN datastore, yearly resources), case types
    'Catchbasin' and 'Roadway Flooding' plus any case whose location names the corridor street.

Usage (from engineering/):
    python scripts/fetch_drainage_evidence.py            # uses fixtures/sample_corridor_context.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from floodroute_eng.road_facts import _haversine_m, _vertices  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CATCH_BASIN_LAYER = ("https://services5.arcgis.com/ji3WHeqN0AysEK5g/arcgis/rest/services/"
                     "Hydrant_Search_Map1/FeatureServer/0")
CKAN_SQL = "https://data.boston.gov/api/3/action/datastore_search_sql"
# Yearly 311 resources (data.boston.gov dataset '311-service-requests'), checked 2026-10-24.
RESOURCES_311 = {
    "2026": "1a0b420d-99f1-4887-9851-990b2a5a6e17", "2025": "9d7c2214-4709-478a-a2e8-fb2020a5bb94",
    "2024": "dff4d804-5031-443a-8409-8344efd0e5c8", "2023": "e6013a93-1321-4f2a-bf91-8d8a02f1e62f",
    "2022": "81a7b022-f8fc-4da5-80e4-b160058ca207", "2021": "f53ebccd-bc61-49f9-83db-625f209c95f5",
    "2020": "6ff6a6fd-3141-4440-a880-6f60a37fe789", "2019": "ea2e4696-4a2d-429c-9807-d02eb92e0222",
    "2018": "2be28d90-3a90-4af1-a3f6-f28c1e25880a",
}
TYPES_311 = ("Catchbasin", "Roadway Flooding")
# BWSC layer sentinel values meaning "unknown / not recorded"
SENTINELS = {-999, -777, "U", "", None}


def _get_json(url: str, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "FloodRoute-engineering/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https hosts)
        return json.loads(resp.read().decode("utf-8"))


def _corridor_vertices(ctx: dict) -> list[tuple[float, float]]:
    road_ids = set(ctx["corridor"]["road_ids"])
    return [v for f in ctx["roads"]["features"] if f["properties"]["road_id"] in road_ids
            for v in _vertices(f["geometry"])]


def _bbox(verts, pad_deg: float) -> tuple[float, float, float, float]:
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    return min(xs) - pad_deg, min(ys) - pad_deg, max(xs) + pad_deg, max(ys) + pad_deg


def _dist_to_corridor(pt, verts) -> float:
    return min(_haversine_m(pt, v) for v in verts)


def fetch_catch_basins(verts, buffer_m: float) -> list[dict]:
    pad = buffer_m / 80_000  # generous degrees pad at Boston latitude; exact filter below
    x0, y0, x1, y1 = _bbox(verts, pad)
    params = {"where": "1=1", "geometry": f"{x0},{y0},{x1},{y1}", "geometryType": "esriGeometryEnvelope",
              "inSR": "4326", "spatialRel": "esriSpatialRelIntersects", "outFields": "*",
              "outSR": "4326", "returnGeometry": "true", "f": "json"}
    data = _get_json(f"{CATCH_BASIN_LAYER}/query?{urllib.parse.urlencode(params)}")
    if "error" in data:
        raise RuntimeError(data["error"])
    out = []
    for f in data.get("features", []):
        pt = (f["geometry"]["x"], f["geometry"]["y"])
        d = _dist_to_corridor(pt, verts)
        if d > buffer_m:
            continue
        a = f["attributes"]
        clean = {k: (None if v in SENTINELS else v) for k, v in a.items()
                 if k in ("facility_id", "owner_code", "basin_type_code", "material_code", "hood_trap_code",
                          "basin_diam_value_ft", "outlet1_diameter_value_in", "depth_to_outlet_value_in",
                          "sewer_system_code", "asset_status", "update_date_time")}
        if clean.get("update_date_time"):
            clean["update_date"] = datetime.datetime.fromtimestamp(
                clean.pop("update_date_time") / 1000, datetime.timezone.utc).date().isoformat()
        out.append({**clean, "lon": pt[0], "lat": pt[1], "distance_to_corridor_m": round(d, 1)})
    return sorted(out, key=lambda r: r["distance_to_corridor_m"])


def fetch_311(verts, buffer_m: float, street_fragment: str) -> tuple[list[dict], dict]:
    pad = buffer_m / 80_000
    x0, y0, x1, y1 = _bbox(verts, pad)
    types = ",".join(f"'{t}'" for t in TYPES_311)
    frag = "".join(ch for ch in street_fragment if ch.isalnum() or ch == " ")  # keep SQL literal safe
    rows, status = [], {}
    for year, rid in RESOURCES_311.items():
        sql = (f'SELECT case_enquiry_id, open_dt, closed_dt, case_status, closure_reason, "type", location, '
               f'latitude, longitude, queue FROM "{rid}" WHERE ("type" IN ({types}) AND '
               f"CAST(latitude AS float) BETWEEN {y0} AND {y1} AND CAST(longitude AS float) BETWEEN {x0} AND {x1})"
               f" OR (location ILIKE '%{frag}%' AND \"type\" IN ({types})) LIMIT 500")
        try:
            recs = _get_json(f"{CKAN_SQL}?{urllib.parse.urlencode({'sql': sql})}")["result"]["records"]
            status[year] = {"resource_id": rid, "records": len(recs), "ok": True}
        except Exception as exc:  # schema differs in some years; record and continue
            status[year] = {"resource_id": rid, "ok": False, "error": type(exc).__name__}
            continue
        for r in recs:
            try:
                pt = (float(r["longitude"]), float(r["latitude"]))
            except (TypeError, ValueError):
                continue
            d = _dist_to_corridor(pt, verts)
            if d > buffer_m:
                continue
            rows.append({
                "case_enquiry_id": str(r["case_enquiry_id"]), "open_dt": r["open_dt"], "closed_dt": r["closed_dt"],
                "case_status": r["case_status"], "type": r["type"],
                "location": (r["location"] or "").replace("&amp;", "&").strip(),
                "closure_reason": (r.get("closure_reason") or "").strip() or None,
                "queue": r.get("queue"), "lon": pt[0], "lat": pt[1], "distance_to_corridor_m": round(d, 1),
            })
    dedup = {r["case_enquiry_id"]: r for r in rows}
    return sorted(dedup.values(), key=lambda r: str(r["open_dt"])), status


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--context", default=str(ROOT / "fixtures" / "sample_corridor_context.json"))
    ap.add_argument("--street", default="Morrissey")
    ap.add_argument("--basin-buffer-m", type=float, default=40.0)
    ap.add_argument("--report-buffer-m", type=float, default=400.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ctx = json.loads(Path(args.context).read_text(encoding="utf-8"))
    verts = _corridor_vertices(ctx)
    today = datetime.date.today().isoformat()
    basins = fetch_catch_basins(verts, args.basin_buffer_m)
    reports, status = fetch_311(verts, args.report_buffer_m, args.street)
    out = {
        "corridor_id": ctx["corridor"]["corridor_id"],
        "retrieved_at": today,
        "catch_basins": {
            "source_id": "BWSC.cb", "url": CATCH_BASIN_LAYER, "crs": "EPSG:4326 (server reprojection)",
            "buffer_m": args.basin_buffer_m, "machine_readable_obtained": True,
            "evidence_type": "gis_derived", "records": basins,
            "limitations": ["Mapped location and owner code only; not functional condition or cleaning history.",
                            "Sentinel values (-999, -777, 'U') converted to null (unknown)."],
        },
        "reports_311": {
            "source_id": "BOS311", "url": "https://data.boston.gov/dataset/311-service-requests",
            "types": list(TYPES_311), "buffer_m": args.report_buffer_m, "years": status,
            "machine_readable_obtained": True, "evidence_type": "observed_report", "records": reports,
            "limitations": ["Complaints are allegations, not confirmed causes; reporting bias and duplicates.",
                            "Closure notes are free text written at case closure, not formal inspection records."],
        },
    }
    dest = Path(args.out) if args.out else ROOT / "engineering" / "data" / f"drainage_evidence_{out['corridor_id']}.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"catch basins within {args.basin_buffer_m} m: {len(basins)}; 311 reports within {args.report_buffer_m} m: "
          f"{len(reports)}; years: {', '.join(f'{y}:{s.get('records', 'ERR')}' for y, s in status.items())}")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
