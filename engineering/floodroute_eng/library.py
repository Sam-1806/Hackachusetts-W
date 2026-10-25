"""Load the cited engineering evidence library (engineering/evidence/*.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "evidence"


@dataclass(frozen=True)
class EvidenceLibrary:
    sources: dict[str, dict]
    measures: dict[str, dict]
    cost_precedents: dict[str, dict]
    cost_caveats: list[str]
    estimating_guidance: list[str]
    local_precedents: list[dict]
    version: str

    def source(self, source_id: str) -> dict | None:
        return self.sources.get(source_id)

    def citation(self, source_id: str, pdf_page: int | None = None,
                 printed_page: int | None = None, url_override: str | None = None) -> dict:
        """Build a citation record. Raises KeyError for unknown sources so a
        typo in the library can never produce an unsourced 'citation'."""
        if source_id == "network_impact":
            return {"citation_id": "network_impact", "source_id": "network_impact",
                    "title": "Network impact record for this corridor (ranking input)",
                    "url": None, "page": None}
        src = self.sources[source_id]
        cid = source_id + (f"#p{pdf_page}" if pdf_page else "")
        page = None
        if printed_page or pdf_page:
            page = {"printed_page": printed_page, "pdf_page": pdf_page}
        return {"citation_id": cid, "source_id": source_id, "title": src["title"],
                "url": url_override or src["url"], "page": page,
                "published": src.get("published")}


def _read(name: str, base: Path) -> dict:
    return json.loads((base / name).read_text(encoding="utf-8"))


def load_library(base: Path | str = EVIDENCE_DIR) -> EvidenceLibrary:
    base = Path(base)
    src = _read("sources.json", base)
    meas = _read("measures.json", base)
    cost = _read("cost_precedents.json", base)
    local = _read("local_precedents.json", base)
    lib = EvidenceLibrary(
        sources={s["source_id"]: s for s in src["sources"]},
        measures={m["method_id"]: m for m in meas["measures"]},
        cost_precedents={p["precedent_id"]: p for p in cost["precedents"]},
        cost_caveats=cost["global_caveats"],
        estimating_guidance=cost["estimating_method_guidance"],
        local_precedents=local["precedents"],
        version=src["library_version"],
    )
    validate_library(lib)
    return lib


def validate_library(lib: EvidenceLibrary) -> None:
    """Fail fast if any claim or precedent points at a source that is not registered."""
    known = set(lib.sources) | {"network_impact"}
    problems = []
    for m in lib.measures.values():
        for c in m["claims"]:
            if c["basis"] == "sourced" and c.get("source_id") not in known:
                problems.append(f"{m['method_id']}: unknown source {c.get('source_id')}")
        for pid in m.get("cost_precedent_ids", []):
            if pid not in lib.cost_precedents:
                problems.append(f"{m['method_id']}: unknown cost precedent {pid}")
    for p in list(lib.cost_precedents.values()) + lib.local_precedents:
        if p["source_id"] not in known:
            problems.append(f"{p['precedent_id']}: unknown source {p['source_id']}")
    if problems:
        raise ValueError("Evidence library inconsistent: " + "; ".join(problems))
