"""Interim corridor ranking on Person 1's OSM graph, using REAL flood exposure as closures.

Person 1 owns the network engine (analysis/network/engine.py, not in this repo). This script
re-implements the method documented in their outputs (ranking_detail.json / road_ranking.json) so
the demo can use real-flood rankings until Person 1 reruns their engine. `--validate` reproduces
Person 1's own mock run first; if it does not match, nothing should be trusted.

Method (from Person 1's assumptions text):
  * travel time = shortest path (seconds, posted speed) from journey origin to the NEAREST of the
    listed emergency departments; origins/destinations snapped to the nearest graph node
  * scenario loss = sum_j weight_j * (t_scenario_j - t_baseline_j); unreachable = +penalty_s (3600)
  * corridor impact = loss(all closures) - loss(all closures except this corridor's roads)
    ("seconds recovered by keeping this corridor passable, conditional on all other closures")
Closure rule for real flood files: roads with exposure "exposed" are closed; others stay open.

Usage (from engineering/, any Python 3.10+, stdlib only):
  python scripts/rank_corridors.py --network <network.json> --p1-results "<...>/results" \
     --exposure data/hazard/osm_net/flood_exposure_mcfrm-2050-1pct.json --out-dir data/ranking --validate
"""

from __future__ import annotations

import argparse
import datetime
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

INF = float("inf")


def hav(a, b) -> float:
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[0] - a[0]) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


class Graph:
    def __init__(self, net: dict, snap_nodes: set[str] | None = None):
        self.version = net["graph_version"]
        self.adj: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
        self.pos: dict[str, tuple[float, float]] = {}
        self.road = {}
        for r in net["roads"]:
            a, b, c = r["a"], r["b"], r["coords"]
            self.pos.setdefault(a, tuple(c[0][:2]))
            self.pos.setdefault(b, tuple(c[-1][:2]))
            self.road[r["id"]] = r
            if r["cf"] is not None:
                self.adj[a].append((b, float(r["cf"]), r["id"]))
            if r["cb"] is not None:
                self.adj[b].append((a, float(r["cb"]), r["id"]))
        # coarse grid for snapping; restricted to the main strongly connected component when given
        self.grid = defaultdict(list)
        for n, p in self.pos.items():
            if snap_nodes is None or n in snap_nodes:
                self.grid[(int(p[0] * 200), int(p[1] * 200))].append(n)

    def snap(self, lon: float, lat: float) -> tuple[str, float]:
        gx, gy = int(lon * 200), int(lat * 200)
        best, bd = None, INF
        for r in range(0, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for n in self.grid.get((gx + dx, gy + dy), []):
                        d = hav(self.pos[n], (lon, lat))
                        if d < bd:
                            best, bd = n, d
            if best is not None and r >= 1:
                break
        return best, bd

    def nearest_target(self, src: str, targets: set[str], closed: set[str]):
        """Dijkstra until the first target is settled. Returns (time_s, [road ids]) or (inf, None)."""
        dist, prev, pq = {src: 0.0}, {}, [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, INF):
                continue
            if u in targets:
                path = []
                while u != src:
                    u, rid = prev[u]
                    path.append(rid)
                return d, path[::-1]
            for v, w, rid in self.adj[u]:
                if rid in closed:
                    continue
                nd = d + w
                if nd < dist.get(v, INF):
                    dist[v], prev[v] = nd, (u, rid)
                    heapq.heappush(pq, (nd, v))
        return INF, None


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load_p1(results: Path):
    """Journeys/weights/penalty from ranking_detail; hospital nodes from journey end points; corridors."""
    runs = sorted(d for d in results.iterdir() if d.is_dir() and (d / "ranking_detail.json").exists())
    detail = load(runs[0] / "ranking_detail.json")
    ends = set()
    corridors = {}
    for run in runs:
        for f in load(run / "journeys.geojson")["features"]:
            ends.add(tuple(round(x, 7) for x in f["geometry"]["coordinates"][-1][:2]))
        for row in load(run / "road_ranking.json")["ranking"]:
            corridors.setdefault(row["corridor_id"], {"corridor_id": row["corridor_id"], "label": row["label"],
                                                      "road_ids": row["road_ids"]})
    return detail, sorted(ends), corridors, runs


class Engine:
    def __init__(self, g: Graph, detail: dict, hospital_points: list):
        self.g, self.penalty = g, float(detail["penalty_s"])
        self.journeys = detail["journeys"]
        self.targets = {g.snap(*p)[0] for p in hospital_points}
        # Reproduce Person 1's origin snaps: they record the snap distance, so pick the main-component node
        # whose distance matches it (falls back to nearest node when no record is given).
        self.origin = {}
        for j in self.journeys:
            o = (j["origin"]["lon"], j["origin"]["lat"])
            want = j.get("origin_snap_m")
            node, d = g.snap(*o)
            if want is not None and abs(d - want) > 0.5:
                cand = [(abs(hav(g.pos[n], o) - want), n) for cells in g.grid.values() for n in cells
                        if abs(g.pos[n][1] - o[1]) < 0.01 and abs(g.pos[n][0] - o[0]) < 0.013]
                if cand:
                    node = min(cand)[1]
            self.origin[j["journey_id"]] = node
        self.cache: dict[tuple, tuple] = {}

    def time(self, jid: str, closed: frozenset):
        key = (jid, closed)
        if key not in self.cache:
            self.cache[key] = self.g.nearest_target(self.origin[jid], self.targets, set(closed))
        return self.cache[key]

    def run(self, closed: frozenset, base: dict) -> dict:
        out = {}
        for j in self.journeys:
            t, path = self.time(j["journey_id"], closed)
            out[j["journey_id"]] = (t, path)
        return out

    def loss(self, times: dict, base: dict) -> float:
        total = 0.0
        for j in self.journeys:
            t = times[j["journey_id"]][0]
            b = base[j["journey_id"]][0]
            total += j["weight"] * ((self.penalty if t == INF else t - b))
        return total


def road_names(g: Graph, ids) -> list[str]:
    out = []
    for rid in ids or []:
        n = g.road[rid]["name"] or "(unnamed)"
        if not out or out[-1] != n:
            out.append(n)
    return out


def closure_candidates(g: Graph, closed: set, base: dict, disrupted: list) -> dict:
    """Extra candidate corridors built from the scenario's closed roads (Person 1's set is predefined).

    * one bundle per street name among closed roads (corridor_id "p3c_<slug>")
    * each closed UNNAMED road on a disrupted journey's baseline path, individually
    * per disrupted journey, the bundle of all closed roads on its baseline path ("restore baseline route")
    """
    import re as _re
    by_name: dict[str, list[str]] = defaultdict(list)
    for rid in closed:
        n = g.road[rid]["name"]
        if n:
            by_name[n].append(rid)
    out = {}
    for n, ids in by_name.items():
        slug = _re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")[:40]
        out[f"p3c_{slug}"] = {"corridor_id": f"p3c_{slug}", "label": f"{n} (closed segments: {len(ids)})",
                              "road_ids": sorted(ids), "candidate_source": "closed roads grouped by street name"}
    for jid in disrupted:
        path = base[jid][1] or []
        on = [r for r in path if r in closed]
        for r in on:
            if not g.road[r]["name"]:
                out[f"p3c_unnamed-{r}"] = {"corridor_id": f"p3c_unnamed-{r}", "label": f"Unnamed link {r}",
                                          "road_ids": [r], "candidate_source": "closed unnamed link on a baseline route"}
        if on:
            names = ", ".join(dict.fromkeys(g.road[r]["name"] or "unnamed link" for r in on))
            out[f"p3b_{jid}"] = {"corridor_id": f"p3b_{jid}", "road_ids": sorted(set(on)),
                                 "label": f"Bundle: closed roads on the baseline route of {jid} ({len(set(on))}: {names})",
                                 "candidate_source": "bundle of closed roads on one baseline route"}
    return out


def rank(engine: Engine, g: Graph, closed: set, corridors: dict, scenario_id: str, status: str,
         closure_note: str, extra_candidates: bool = False) -> tuple[dict, dict]:
    base = engine.run(frozenset(), {})
    full = frozenset(closed)
    flooded = engine.run(full, base)
    total = engine.loss(flooded, base)
    disrupted = [j["journey_id"] for j in engine.journeys
                 if flooded[j["journey_id"]][0] != base[j["journey_id"]][0]]
    if extra_candidates:
        corridors = {**corridors, **closure_candidates(g, set(full), base, disrupted)}
    rows, detail = [], {}
    for cid, c in corridors.items():
        in_closed = [r for r in c["road_ids"] if r in full]
        if in_closed and disrupted:
            reopened = frozenset(full - set(c["road_ids"]))
            t_open = {jid: engine.time(jid, reopened) for jid in disrupted}
            with_open = {**flooded, **t_open}
            marginal = total - engine.loss(with_open, base)
        else:
            t_open, marginal = {}, 0.0
        # Standalone: loss if ONLY this corridor's flooded roads were closed (its own criticality).
        if in_closed:
            only = frozenset(in_closed)
            standalone = engine.loss({j["journey_id"]: engine.time(j["journey_id"], only) for j in engine.journeys},
                                     base)
        else:
            standalone = 0.0
        improved = [jid for jid in disrupted if t_open.get(jid, flooded[jid])[0] < flooded[jid][0] - 1e-6]
        jmeta = {j["journey_id"]: j for j in engine.journeys}
        journeys, evidence, detour_for, disconnected, detour_names = [], [], [], [], []
        for jid in improved:
            b, f, o = base[jid][0], flooded[jid][0], t_open[jid][0]
            reach = f != INF
            journeys.append({"journey_id": jid, "label": jmeta[jid]["label"], "baseline_s": round(b, 1),
                             "flooded_s": round(f, 1) if reach else None, "reachable": reach,
                             "with_corridor_open_s": round(o, 1) if o != INF else None,
                             "weight": jmeta[jid]["weight"]})
            if reach:
                detour_for.append(jid)
                extra = [n for n in road_names(g, flooded[jid][1]) if n not in set(road_names(g, base[jid][1]))]
                detour_names += [n for n in extra if n not in detour_names]
                evidence.append(f"{jmeta[jid]['label']}: {b:.0f} s baseline -> {f:.0f} s with {scenario_id} closures "
                                f"(+{(f - b) / b * 100:.0f}%); {o:.0f} s if this corridor stays passable "
                                f"(recovers {f - o:.0f} s).")
            else:
                disconnected.append(jid)
                evidence.append(f"{jmeta[jid]['label']}: unreachable with {scenario_id} closures; "
                                f"{o:.0f} s if this corridor stays passable.")
        if not evidence:
            evidence = ["No modeled journey changes: either alternatives exist or no representative journey uses "
                        "this corridor." if in_closed else "No road in this corridor is closed in this scenario."]
        assumptions = [
            "Impact = demand-weighted seconds recovered by keeping this corridor passable, conditional on all other "
            "closures in the scenario; unreachable journeys count as 3600 extra seconds.",
            "Journeys are Person 1's assumed planning proxies (neighborhood to emergency department), not ambulance "
            "dispatch or clinical appropriateness; equal-per-neighborhood demand weights.",
            closure_note,
            "Travel times are posted-speed estimates, no traffic.",
            "Interim re-implementation of Person 1's method by Person 3 (validated against Person 1's mock run).",
        ]
        rows.append({
            "corridor_id": cid, "road_ids": c["road_ids"], "label": c["label"],
            "candidate_source": c.get("candidate_source", "Person 1 corridor"),
            "impact_value": round(marginal, 1), "impact_metric": round(marginal, 1),
            "impact_units": "demand-weighted seconds recovered (unreachable = +3600 s)",
            "metric_units": "demand-weighted seconds recovered (unreachable = +3600 s)",
            "standalone_loss": round(standalone, 1),
            "standalone_note": "Loss if ONLY this corridor's flooded roads were closed (not used for rank order).",
            "closed_roads_in_corridor": len(in_closed),
            "affected_journey_ids": improved,
            "affected_journeys": journeys,
            "detour_or_disconnection_evidence": evidence,
            "detour_or_disconnect_evidence": {
                "detour_available_for": detour_for, "disconnected": disconnected,
                "detour_road_names": detour_names[:6],
                "detour_flood_exposure": ("not_exposed: router avoided all closed (exposed) roads; roads outside the "
                                          "flood-extent window are assumed open") if detour_for else "unknown"},
            "assumptions": assumptions,
            "provenance": {"origin": "computed", "data_status": status, "source_id": "P3-INTERIM-RANKING",
                           "source_name": "Interim re-implementation of Person 1's accessibility method (Person 3)",
                           "source_url": "engineering/scripts/rank_corridors.py",
                           "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                           "period": scenario_id,
                           "limitations": ["Relative criticality for investigation, not a construction priority.",
                                           "Overlap-based closures; no depth or verified impassability.",
                                           "Replace with Person 1's engine output when available."]},
        })
        detail[cid] = {"marginal_loss_recovered": marginal, "standalone_loss": standalone,
                       "closed_roads_in_corridor": len(in_closed), "improved_journeys": improved}
    # Rank by marginal recovery; ties broken by standalone criticality, then fewer roads (smaller bundle first).
    rows.sort(key=lambda r: (-r["impact_value"], -r["standalone_loss"], len(r["road_ids"]), r["corridor_id"]))
    for i, r in enumerate(rows, 1):
        r["priority_rank"] = i
    ranking = {"scenario_set_id": scenario_id, "graph_version": g.version, "ranking": rows}
    summary = {"scenario_id": scenario_id, "closed_roads": len(full), "loss": total,
               "journeys_disrupted": disrupted,
               "unreachable": [jid for jid in disrupted if flooded[jid][0] == INF],
               "baseline_times_s": {k: v[0] for k, v in base.items()},
               "times_s": {k: (None if v[0] == INF else v[0]) for k, v in flooded.items()},
               "corridors": detail}
    return ranking, summary


def counterfactual(engine: Engine, g: Graph, closed: set, corridors: dict, scenario_id: str, note: str,
                   preserved: list[str], intervention_id: str) -> dict:
    """CounterfactualResult (Person 2's contract): rerank with `preserved` roads assumed passable."""
    before, sb = rank(engine, g, closed, corridors, scenario_id, "derived", note, extra_candidates=True)
    after_closed = set(closed) - set(preserved)
    after, sa = rank(engine, g, after_closed, corridors, f"{scenario_id}+assume:{intervention_id}", "derived",
                     note + f" Counterfactual: {len(set(preserved) & set(closed))} roads assumed passable.",
                     extra_candidates=True)
    jmeta = {j["journey_id"]: j for j in engine.journeys}
    changes = []
    for jid, t0 in sb["times_s"].items():
        t1 = sa["times_s"][jid]
        if t0 != t1:
            changes.append({"journey_id": jid, "label": jmeta[jid]["label"], "baseline_s": round(sb["baseline_times_s"][jid], 1),
                            "flooded_s": None if t0 is None else round(t0, 1),
                            "with_assumption_s": None if t1 is None else round(t1, 1)})
    return {
        "graph_version": g.version,
        "intervention_id": intervention_id,
        "scenario_set_id": scenario_id,
        "preserved_road_ids": sorted(set(preserved)),
        "before_ranking": before,
        "after_ranking": after,
        "accessibility_change": {"value": round(sb["loss"] - sa["loss"], 1),
                                 "units": "demand-weighted seconds of accessibility loss avoided (unreachable = +3600 s)"},
        "journey_changes": changes,
        "assumptions": [f"Assume {len(set(preserved))} listed roads remain passable in {scenario_id} only.",
                        "Idealized access assumption; no physical protection, hydraulic effect, or changed flood extent "
                        "is inferred.", note],
        "provenance": {"origin": "computed", "source_id": "P3-INTERIM-RANKING",
                       "source_name": "Interim re-implementation of Person 1's accessibility method (Person 3)",
                       "source_url": "engineering/scripts/rank_corridors.py",
                       "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "limitations": ["Replace with Person 1's engine output when available.",
                                       "Journeys and demand weights are Person 1's assumed planning proxies."]},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--counterfactual", action="append", default=[], metavar="ID:ROAD,ROAD,...",
                    help="With exactly one --exposure: also write CounterfactualResult for these preserved roads")
    ap.add_argument("--network", required=True)
    ap.add_argument("--p1-results", required=True, help="Folder with Person 1's run subfolders")
    ap.add_argument("--exposure", action="append", default=[])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()

    scc_path = Path(a.network).with_name("main_scc_node_ids.json")
    scc = set(load(scc_path)) if scc_path.exists() else None
    g = Graph(load(a.network), scc)
    detail, ends, corridors, runs = load_p1(Path(a.p1_results))
    if detail["graph_version"] != g.version:
        raise SystemExit(f"graph mismatch: P1 {detail['graph_version']} vs network {g.version}")
    eng = Engine(g, detail, ends)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"graph {g.version}: {len(g.road)} roads; {len(eng.journeys)} journeys; {len(eng.targets)} ED nodes; "
          f"{len(corridors)} corridors")

    if a.validate:
        worst = 0.0
        for run in runs:
            mock = next(run.glob("mock_flood_exposure_*.json"))
            fe = load(mock)
            closed = {r["road_id"] for r in fe["affected_roads"] if r["passability"] == "potentially_closed"}
            mine, summ = rank(eng, g, closed, corridors, fe["scenario_id"], "mock", "validation")
            p1 = load(run / "ranking_detail.json")
            p1rows = load(run / "road_ranking.json")["ranking"]
            p1rank = {r["corridor_id"]: r["impact_value"] for r in p1rows}
            rel = max(abs(summ["baseline_times_s"][k] - v) / v for k, v in p1["baseline_times_s"].items())
            p1loss = next(iter(p1["scenarios"].values()))["loss"]
            mine_imp = {r["corridor_id"]: r["impact_value"] for r in mine["ranking"]}
            dimp = max(abs(mine_imp[c] - v) for c, v in p1rank.items())
            # Same order among the corridors Person 1 ranked in this run (ties ignored).
            order_ok = all((mine_imp[x["corridor_id"]] >= mine_imp[y["corridor_id"]] - 1e-6)
                           for x, y in zip(p1rows, p1rows[1:]) if x["impact_value"] > y["impact_value"])
            same_disrupted = set(summ["journeys_disrupted"]) == set(next(iter(p1["scenarios"].values()))["journeys_disrupted"])
            ok = rel <= 0.02 and order_ok and same_disrupted and dimp <= max(5.0, 0.1 * max(p1rank.values()))
            worst = max(worst, 0.0 if ok else 1.0)
            print(f"  validate {run.name}: max baseline diff {rel * 100:.1f}%, loss {summ['loss']:.1f} vs P1 {p1loss:.1f}, "
                  f"max corridor impact diff {dimp:.1f}, same order {order_ok}, same disrupted journeys "
                  f"{same_disrupted} -> {'OK' if ok else 'FAIL'}")
        if worst:
            raise SystemExit("VALIDATION FAILED; not writing real rankings")
        print("  validation OK (within tolerance: <=2% baseline, same corridor order and disrupted journeys)")

    for path in a.exposure:
        fe = load(path)
        if fe["graph_version"] != g.version:
            raise SystemExit(f"{path}: graph {fe['graph_version']} != {g.version}")
        closed = {r["road_id"] for r in fe["affected_roads"] if r["exposure"] == "exposed"}
        status = "derived"
        note = (f"Closures: the {len(closed)} roads whose centerline overlaps the {fe['scenario_id']} extent are "
                "treated as closed (ASSUMED; overlap is not verified impassability). Roads outside the extent's "
                "study window are treated as open.")
        ranking, summ = rank(eng, g, closed, corridors, fe["scenario_id"], status, note, extra_candidates=True)
        (out / f"road_ranking_{fe['scenario_id']}.json").write_text(json.dumps(ranking, indent=1), encoding="utf-8")
        (out / f"ranking_summary_{fe['scenario_id']}.json").write_text(json.dumps(summ, indent=1, default=str),
                                                                      encoding="utf-8")
        print(f"{fe['scenario_id']}: {len(closed)} closed, loss {summ['loss']:.1f}, disrupted {summ['journeys_disrupted']}, "
              f"unreachable {summ['unreachable']}; {len(ranking['ranking'])} candidates")
        for r in ranking["ranking"][:6]:
            print(f"   #{r['priority_rank']:<3} {r['impact_value']:7.1f} recovered | standalone {r['standalone_loss']:7.1f} | "
                  f"{r['label'][:80]}")
        for cid in ("cor_87278ad9ba", "cor_dceb13cd52", "cor_6dece7a926"):
            r = next(x for x in ranking["ranking"] if x["corridor_id"] == cid)
            print(f"   Morrissey {cid}: rank {r['priority_rank']}, recovered {r['impact_value']}, standalone {r['standalone_loss']}")
        for spec in a.counterfactual:
            iid, roads = spec.split(":", 1)
            if roads.startswith("@"):  # @<corridor_id>: all roads of that ranked candidate
                roads_list = next(x for x in ranking["ranking"] if x["corridor_id"] == roads[1:])["road_ids"]
            else:
                roads_list = [r for r in roads.split(",") if r]
            cf = counterfactual(eng, g, closed, corridors, fe["scenario_id"], note, roads_list, iid)
            p = out / f"counterfactual_{fe['scenario_id']}_{iid}.json"
            p.write_text(json.dumps(cf, indent=1), encoding="utf-8")
            print(f"   counterfactual {iid}: {len(cf['preserved_road_ids'])} roads kept passable -> "
                  f"loss avoided {cf['accessibility_change']['value']}; journeys {cf['journey_changes']}")


if __name__ == "__main__":
    main()
