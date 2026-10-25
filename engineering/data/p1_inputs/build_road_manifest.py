#!/usr/bin/env python3
"""Person 1: build the REAL canonical road manifest + audit from boston-streets/data.csv (stdlib only).
Usage:
  python build_road_manifest.py --csv data.csv --out data/normalized/roads \
      --trip "-71.0500,42.3480:-71.0725,42.3358"
Outputs: road_manifest.json (RoadManifest contract), audit_report.json, and a printed audit."""
import argparse, csv, hashlib, heapq, json, math, re, sys, statistics, pathlib
from collections import Counter, defaultdict

def hav(a, b):
    R = 6371000.0; p1, p2 = math.radians(a[1]), math.radians(b[1])
    h = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(b[0]-a[0])/2)**2
    return 2*R*math.asin(math.sqrt(h))
def parse_wkt(w):
    parts = re.findall(r"\(([^()]+)\)", w[w.index("("):])
    return [[tuple(float(v) for v in p.split()[:2]) for p in part.split(",")] for part in parts]
def key(pt): return (round(pt[0], 6), round(pt[1], 6))
def nid(pt): return "nd_" + hashlib.sha1(f"{pt[0]:.6f},{pt[1]:.6f}".encode()).hexdigest()[:10]
def num(s):
    try: return float(s)
    except (TypeError, ValueError): return None

def load(csv_path):
    raw = open(csv_path, "rb").read()
    file_hash = hashlib.sha256(raw).hexdigest()
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    return rows, file_hash

def build(rows, file_hash):
    A = Counter(); roads = []; seen = Counter(); mism = []; ratios = []; fails = []; matrix = Counter()
    ow_map = {"": "no", "FT": "forward", "TF": "reverse"}
    for i, r in enumerate(rows):
        try: parts = parse_wkt(r["geometry"])
        except Exception:
            g = (r.get("geometry") or "").strip()
            kind = "empty_string" if not g else ("wkt_EMPTY" if "EMPTY" in g.upper() else "other")
            A["geometry_parse_failures"] += 1; fails.append((i + 2, kind, g[:90], r.get("street"), r.get("neighborhood"), r.get("oneway"), r)); continue
        ow = (r.get("oneway") or "").strip().upper()
        if ow not in ow_map: A["unrecognized_oneway_values"] += 1
        if len(parts) > 1: A["multipart_rows"] += 1
        merged = [list(parts[0])]
        for p in parts[1:]:
            if key(merged[-1][-1]) == key(p[0]): merged[-1].extend(p[1:])
            else: merged.append(list(p))
        if len(merged) > 1: A["multipart_rows_noncontiguous_split"] += 1
        speed, cf, cb = num(r.get("speed_mph")), num(r.get("cost_forward")), num(r.get("cost_back"))
        _f = cf is not None and cf >= 0; _b = cb is not None and cb >= 0
        matrix[f"oneway={ow or '(blank)'} | fwd_ok={_f} | back_ok={_b}"] += 1
        if speed is None or speed <= 0: A["missing_or_zero_speed"] += 1
        for k, coords in enumerate(merged):
            if len(coords) < 2: A["degenerate_part"] += 1; continue
            L = sum(hav(coords[j], coords[j+1]) for j in range(len(coords)-1))
            if L <= 0: A["zero_length"] += 1; continue
            a, b = key(coords[0]), key(coords[-1]); mid = key(coords[len(coords)//2])
            base = f"{r['street']}|{r['type']}|{a}|{b}|{mid}"
            seen[base] += 1
            if seen[base] > 1: A["duplicate_geometry_name"] += 1
            rid = "rd_" + hashlib.sha1((base + f"|dup{seen[base]-1}").encode()).hexdigest()[:10]
            fwd = cf is not None and cf >= 0; back = cb is not None and cb >= 0
            if ow == "FT" and back: mism.append(i)
            if ow == "" and not (fwd and back): mism.append(i)
            if fwd and speed and speed > 0:
                ratios.append(cf / ((L/1609.344)/speed*60))
            roads.append({"rid": rid, "row": i + 2, "part": k, "name": r["street"], "type": r["type"], "speed": speed,
                          "ow": ("no" if fwd and back else "forward" if fwd else "reverse" if back else "closed"), "ow_raw": ow, "nb": r.get("neighborhood", ""), "L": L, "coords": coords,
                          "a": a, "b": b, "cf": cf*60 if fwd else None, "cb": cb*60 if back else None, "key": base})
    A["oneway_vs_cost_sign_mismatch"] = len(set(mism))
    return roads, A, ratios, fails, matrix

def manifest(roads, file_hash, gv):
    prov = {"source_id": "S01", "source_ref": "robotics.zip/boston-streets/data.csv", "data_status": "derived",
            "limitations": ["Derived from city street centerlines; no stable source IDs; topology inferred from shared endpoints.",
                            "Rows with empty geometry in the source are absent. oneway label is derived from cost signs; oneway_flag_raw keeps the source flag.",
                            "cost_forward/back assumed to be minutes at posted speed (checked in audit); -1 = not traversable.",
                            f"Input sha256: {file_hash}"]}
    feats, idmap = [], []
    for r in roads:
        feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": [list(c) for c in r["coords"]]},
            "properties": {"road_id": r["rid"], "name": r["name"], "speed_mph": r["speed"], "oneway": r["ow"], "oneway_flag_raw": r["ow_raw"],
                "length_m": round(r["L"], 1), "cost_forward_s": None if r["cf"] is None else round(r["cf"], 1),
                "cost_back_s": None if r["cb"] is None else round(r["cb"], 1),
                "from_node": nid(r["a"]), "to_node": nid(r["b"]), "data_status": "derived",
                "road_type": r["type"], "neighborhood": r["nb"]}})
        idmap.append({"road_id": r["rid"], "source_id": "S01", "source_ref": f"data.csv line {r['row']} part {r['part']}", "source_key": r["key"]})
    return {"graph_version": gv, "roads": {"type": "FeatureCollection", "features": feats}, "id_mapping": idmap,
            "metadata": {"crs": "EPSG:4326", "units": {"distance": "m", "time": "s", "speed": "mph"}, "provenance": prov}}

def graph(roads):
    adj = defaultdict(list); pos = {}
    for r in roads:
        a, b = nid(r["a"]), nid(r["b"]); pos[a], pos[b] = r["a"], r["b"]
        adj[a]; adj[b]
        if r["cf"] is not None: adj[a].append((b, r["cf"], r["rid"]))
        if r["cb"] is not None: adj[b].append((a, r["cb"], r["rid"]))
    return adj, pos

def components(adj):
    nodes = list(adj); radj = defaultdict(list)
    for u in adj:
        for v, _, _ in adj[u]: radj[v].append(u)
    seen, order = set(), []
    for s in nodes:                      # Kosaraju pass 1 (iterative)
        if s in seen: continue
        seen.add(s); st = [(s, iter(adj[s]))]
        while st:
            u, it = st[-1]
            for v, _, _ in it:
                if v not in seen: seen.add(v); st.append((v, iter(adj[v]))); break
            else: order.append(u); st.pop()
    comp, sizes = {}, []
    for s in reversed(order):            # pass 2 on reverse graph
        if s in comp: continue
        c = len(sizes); comp[s] = c; st = [s]; n = 0
        while st:
            u = st.pop(); n += 1
            for v in radj[u]:
                if v not in comp: comp[v] = c; st.append(v)
        sizes.append(n)
    # weakly connected via union-find
    par = {n: n for n in nodes}
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for u in adj:
        for v, _, _ in adj[u]: par[f(u)] = f(v)
    wroot = {n: f(n) for n in nodes}
    wc = Counter(wroot.values())
    return comp, sorted(sizes, reverse=True), sorted(wc.values(), reverse=True), sizes.index(max(sizes)), wroot

def route(adj, s, t, name_of):
    d, pq, prev = {s: 0}, [(0, s)], {}
    while pq:
        c, u = heapq.heappop(pq)
        if u == t: break
        if c > d.get(u, 1e18): continue
        for v, w, r in adj[u]:
            if c + w < d.get(v, 1e18): d[v] = c + w; prev[v] = (u, r); heapq.heappush(pq, (c + w, v))
    if t not in d: return None
    path, u = [], t
    while u != s: u, r = prev[u][0], prev[u][1]; path.append(r)
    return d[t], path[::-1]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", required=True); ap.add_argument("--out", default="data/normalized/roads")
    ap.add_argument("--street", action="append", metavar="NAME", help="report on a street by name (repeatable)")
    ap.add_argument("--trip", action="append", metavar="LON,LAT:LON,LAT", help="origin:dest, snapped to nearest nodes; repeatable")
    a = ap.parse_args()
    rows, fh = load(a.csv); gv = f"streets-{fh[:8]}-v0.1"
    roads, A, ratios, fails, matrix = build(rows, fh); adj, pos = graph(roads)
    comp, scc, wcc, main_id, wroot = components(adj)
    rep = {"graph_version": gv, "input_rows": len(rows), "roads_emitted": len(roads), "nodes": len(adj),
           "directed_edges": sum(len(v) for v in adj.values()), "anomalies": dict(A),
           "oneway_values": dict(Counter((r.get("oneway") or "").strip() or "(blank)" for r in rows)),
           "road_types": dict(Counter(r["type"] for r in roads).most_common(12)),
           "neighborhoods": len({r["nb"] for r in roads}),
           "strongly_connected": {"components": len(scc), "largest": scc[0], "largest_share": round(scc[0]/len(adj), 4), "next_5": scc[1:6]},
           "weakly_connected": {"components": len(wcc), "largest": wcc[0], "next_5": wcc[1:6]}}
    if ratios:
        q = statistics.quantiles(ratios, n=20)
        rep["cost_vs_length_check"] = {"n": len(ratios), "median_ratio": round(statistics.median(ratios), 3), "p05": round(q[0], 3), "p95": round(q[-1], 3),
                                       "note": "ratio ~1.0 means cost_forward is minutes at posted speed over geometric length"}
    rep["geometry_failure_kinds"] = dict(Counter(f[1] for f in fails))
    rep["geometry_failure_samples"] = [{"csv_line": f[0], "kind": f[1], "geometry": f[2], "street": f[3], "neighborhood": f[4], "oneway": f[5]} for f in fails[:6]]
    rep["geometry_failures_by_neighborhood"] = dict(Counter(f[4] for f in fails).most_common(8))
    rep["oneway_cost_matrix"] = dict(sorted(matrix.items(), key=lambda kv: -kv[1]))
    rep["roads_with_start_node_off_main_scc_by_neighborhood"] = dict(Counter(r["nb"] for r in roads if comp[nid(r["a"])] != main_id).most_common(8))
    # small weak components: where are the islands?
    acc = defaultdict(lambda: {"roads": 0, "nb": Counter(), "streets": Counter(), "x": 0.0, "y": 0.0})
    for r in roads:
        w = acc[wroot[nid(r["a"])]]; w["roads"] += 1; w["nb"][r["nb"]] += 1; w["streets"][r["name"]] += 1; w["x"] += r["a"][0]; w["y"] += r["a"][1]
    top = sorted(acc.values(), key=lambda w: -w["roads"])[1:7]
    rep["next_weak_components"] = [{"roads": w["roads"], "centroid_lon_lat": [round(w["x"]/w["roads"], 4), round(w["y"]/w["roads"], 4)],
        "neighborhoods": dict(w["nb"].most_common(3)), "top_streets": [k for k, _ in w["streets"].most_common(4)]} for w in top]
    # snap-tolerance audit: dead-end nodes sitting close to a different node (possible near-miss joins)
    deg = Counter()
    for r in roads: deg[nid(r["a"])] += 1; deg[nid(r["b"])] += 1
    grid = defaultdict(list)
    for n, p in pos.items(): grid[(int(p[0]*1e4), int(p[1]*1e4))].append(n)
    near = Counter()
    for n in [n for n, d in deg.items() if d == 1]:
        gx, gy = int(pos[n][0]*1e4), int(pos[n][1]*1e4)
        dmin = min((hav(pos[n], pos[m]) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for m in grid[(gx+dx, gy+dy)] if m != n), default=None)
        near["no_node_within_~15m" if dmin is None else ("<=1m" if dmin <= 1 else "<=3m" if dmin <= 3 else "<=8m" if dmin <= 8 else "<=15m")] += 1
    rep["dead_end_nodes"] = {"total": sum(1 for d in deg.values() if d == 1), "nearest_other_node": dict(near)}
    KW = ["tunnel", "bridge", "ramp", "sumner", "callahan", "tobin", "williams", "prison", "meridian", "chelsea", "storrow", "interstate", "expressway", "turnpike", "route"]
    dn = Counter(f[3] for f in fails)
    rep["dropped_rows_top_streets"] = dict(dn.most_common(25))
    rep["dropped_rows_keyword_streets"] = dict([(k, v) for k, v in dn.most_common() if any(w in (k or "").lower() for w in KW)][:25])
    sc = {}
    for nm in (a.street or []):
        rs = [r for r in roads if r["name"].lower() == nm.lower()]; hd = Counter()
        for r in rs:
            if r["ow"] in ("forward", "reverse"):
                p, q = (r["coords"][0], r["coords"][-1]) if r["ow"] == "forward" else (r["coords"][-1], r["coords"][0])
                dx = (q[0] - p[0]) * math.cos(math.radians(p[1])); dy = q[1] - p[1]
                hd[("eastbound" if dx > 0 else "westbound") if abs(dx) > abs(dy) else ("northbound" if dy > 0 else "southbound")] += 1
        sc[nm] = {"segments_in_manifest": len(rs), "start_node_in_main_scc": sum(comp[nid(r["a"])] == main_id for r in rs),
                  "by_traversability": dict(Counter(r["ow"] for r in rs)), "one_way_headings": dict(hd),
                  "neighborhoods": dict(Counter(r["nb"] for r in rs).most_common(4)),
                  "dropped_rows_with_this_name": sum(v for k, v in dn.items() if (k or "").lower() == nm.lower())}
    if sc: rep["street_checks"] = sc
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with open(out / "dropped_rows.csv", "w", newline="") as fh2:
        w = csv.writer(fh2); w.writerow(["csv_line", "street", "type", "neighborhood", "oneway", "speed_mph", "cost_forward", "cost_back"])
        for f in fails: w.writerow([f[0], f[3], f[6].get("type"), f[4], f[5], f[6].get("speed_mph"), f[6].get("cost_forward"), f[6].get("cost_back")])
    (out / "road_manifest.json").write_text(json.dumps(manifest(roads, fh, gv)))
    (out / "audit_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    byid = {r["rid"]: r for r in roads}
    for tr in (a.trip or []):
        o, d = tr.strip().split(":")
        pt = lambda s: tuple(float(x) for x in s.split(","))
        snap = lambda p: min(pos, key=lambda n: hav(pos[n], p))
        po, pd = pt(o), pt(d); so, sd = snap(po), snap(pd)
        res = route(adj, so, sd, None)
        print(f"\nTRIP {o} -> {d}  (snap {hav(pos[so], po):.0f} m / {hav(pos[sd], pd):.0f} m; origin in main SCC: {comp[so]==main_id}, dest in main SCC: {comp[sd]==main_id})")
        if not res: print("  NO DIRECTED PATH"); continue
        t, path = res; names = []
        for rid in path:
            n = byid[rid]["name"]
            if not names or names[-1] != n: names.append(n)
        print(f"  {t/60:.1f} min, {sum(byid[r]['L'] for r in path)/1000:.2f} km, {len(path)} segments")
        print("  via:", " > ".join(names[:25]) + (" ..." if len(names) > 25 else ""))
    print(f"\nWrote {out}/road_manifest.json, audit_report.json, dropped_rows.csv")
if __name__ == "__main__": main()