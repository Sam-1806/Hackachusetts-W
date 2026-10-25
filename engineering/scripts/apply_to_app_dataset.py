"""Put Person 3's drop-in concept + investigation into a sim+ranks checkout's app-dataset.json.

Usage (from engineering/): python scripts/apply_to_app_dataset.py <sim+ranks checkout>
Only the `concept` and `investigation` keys are replaced; everything else is left as-is.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    target = Path(sys.argv[1]) / "frontend" / "public" / "data" / "app-dataset.json"
    ds = json.loads(target.read_text(encoding="utf-8"))
    b = json.loads((ROOT / "handoff" / "person3_demo" / "demo_data.json").read_text(encoding="utf-8"))
    concept = next(c for c in b["person2_concepts"] if c["intervention_id"] == b["person2_recommended_concept_id"])
    inv = dict(b["person2_investigation"])
    inv.pop("_citations_used", None)
    old = ds["concept"]["intervention_id"], ds["investigation"]["investigation_id"]
    ds["concept"], ds["investigation"] = concept, inv
    target.write_text(json.dumps(ds, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"concept {old[0]} -> {concept['intervention_id']} ({concept['geometry_status']}); "
          f"investigation {old[1]} -> {inv['investigation_id']}")


if __name__ == "__main__":
    main()
