"""Fetch a MassDOT Road Inventory snapshot (S10) for one street and save as GeoJSON.

Usage (from engineering/):
    python scripts/fetch_road_inventory.py --street MORRISSEY --out data/road_inventory_morrissey.geojson
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from floodroute_eng.road_facts import fetch_inventory  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--street", required=True, help="Street-name fragment, e.g. MORRISSEY")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # Only letters, digits and spaces are allowed so the fragment cannot alter the SQL clause.
    if not re.fullmatch(r"[A-Za-z0-9 ]+", args.street):
        ap.error("--street may only contain letters, digits and spaces")
    where = f"St_Name LIKE '%{args.street.upper()}%'"

    fc = fetch_inventory(where)
    fc["metadata"]["retrieved_at"] = datetime.date.today().isoformat()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(fc, indent=1), encoding="utf-8")
    print(f"saved {fc['metadata']['record_count']} records -> {out}")


if __name__ == "__main__":
    main()
