#!/usr/bin/env python3
"""Person 1 (fallback): build the canonical road manifest from OpenStreetMap via OSMnx, same RoadManifest contract.
Needs: pip install osmnx   (internet required for --place; use --xml for an offline .osm file)
Keep build_road_manifest.py in the same folder (helpers are reused).
Works with OSMnx 1.x and 2.x (buffer is applied to the place polygon, not via buffer_dist).
Usage:
  python build_osm_manifest.py --place "Boston, Massachusetts, USA" --buffer 3000 --out data/normalized/roads_osm \
      --street "William T Morrissey" --trip="-71.0500,42.3480:-71.0725,42.3358"
"""
import argparse, json, hashlib, datetime, pathlib, math
from collections import Counter, defaultdict
import osmnx as ox
import build_road_manifest as B

def nm(v):
    if isinstance(v, list): v = "/".join(sorted({str(x) for x in v}))
    return v or ""

def load_graph(a):
    """Download (or read) the drive network. The place polygon is buffered in a projected CRS (meters)."""
    if a.xml:
        return ox.graph_from_xml(a.xml, simplify=True, retain_all=True)
    import geopandas as gpd
    gdf = ox.geocode_to_gdf(a.place)
    utm = gdf.estimate_utm_crs()
    g = gdf.to_crs(utm).geometry
    geom = g.union_all() if hasattr(g, "union_all") else g.unary_union
    poly = gpd.GeoSeries([geom.buffer(a.buffer)], crs=utm).to_crs(4326).iloc[0]
    return ox.graph_from_polygon(poly, network_type="drive", simplify=True, retain_all=True)

def edges_to_roads(G):
    groups = defaultdict(list)
    for u, v, k, d in G.edges(keys=True, data=True):
        oid = d.get("osmid"); oid = tuple(sorted(oid)) if isinstance(oid, list) else (oid,)
        groups[(min(u, v), max(u, v), oid, round(d["length"], 1))].append((u, v, k, d))
    pos = {n: (d["x"], d["y"]) for n, d in G.nodes(data=True)}
    def coords(u, v, d):
        if "geometry" in d: return [(round(x, 7), round(y, 7)) for x, y in d["geometry"].coords]
        return [pos[u], pos[v]]
    roads, seen = [], Counter()
    for (lo, hi, oid, L), es in groups.items():
        fw = [e for e in es if e[0] == lo]; bw = [e for e in es if e[0] != lo and e[1] == lo]
        if lo == hi: fw, bw = es, []
        pairs = [(fw[i] if i < len(fw) else None, bw[i] if i < len(bw) else None) for i in range(max(len(fw), len(bw)))]
        for f, b in pairs:
            u, v, k, d = f if f else (b[0], b[1], b[2], b[3])
            c = coords(u, v, d) if f else list(reversed(coords(*b[:2], b[3])))
            a_, b_ = (u, v) if f else (b[1], b[0])
            cf = f[3]["travel_time"] if f else None; cb = b[3]["travel_time"] if b else None
            base = f"osm:{oid}:{a_}:{b_}:{k}"; seen[base] += 1
            rid = "rd_" + hashlib.sha1((base + f"|{seen[base]-1}").encode()).hexdigest()[:10]
            sp = d.get("speed_kph")
            roads.append({"rid": rid, "row": 0, "part": 0, "name": nm(d.get("name")), "type": nm(d.get("highway")),
                "speed": round(sp / 1.609344, 1) if sp else None,
                "ow": "no" if (cf is not None and cb is not None) else ("forward" if cf is not None else "reverse"),
                "ow_raw": str(d.get("oneway")), "nb": "", "L": float(d["length"]), "coords": c,
                "a": B.key(c[0]), "b": B.key(c[-1]), "cf": cf, "cb": cb, "key": base})
    return roads

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", default="Boston, Massachusetts, USA"); ap.add_argument("--buffer", type=int, default=3000)
    ap.add_argument("--xml", help="offline .osm file instead of downloading"); ap.add_argument("--out", default="data/normalized/roads_osm")
    ap.add_argument("--street", action="append"); ap.add_argument("--trip", action="append", metavar="LON,LAT:LON,LAT")
    a = ap.parse_args()
    G = load_graph(a)
    G = ox.add_edge_speeds(G); G = ox.add_edge_travel_times(G)
    roads = edges_to_roads(G); adj, pos = B.graph(roads)
    comp, scc, wcc, main_id, wroot = B.components(adj)
    today = datetime.date.today().isoformat(); gv = f"osm-{today}-v0.1"
    mf = B.manifest(roads, hashlib.sha256(json.dumps(sorted(r["key"] for r in roads)).encode()).hexdigest(), gv)
    mf["metadata"]["provenance"] = {"source_id": "OSM", "source_ref": f"OpenStreetMap via OSMnx {ox.__version__}; place={a.place if not a.xml else a.xml}; buffer_m={a.buffer}; fetched {today}",
        "data_status": "derived", "limitations": ["(c) OpenStreetMap contributors, ODbL. Snapshot date is part of graph_version; IDs are only stable within one snapshot.",
        "Speeds/times from maxspeed tags or OSMnx highway-type defaults, not observed traffic.", "No neighborhood attribute; join to polygons later."]}
    for m in mf["id_mapping"]: m["source_id"] = "OSM"; m["source_ref"] = m["source_key"]
    for f in mf["roads"]["features"]: f["properties"]["data_status"] = "derived"
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "road_manifest.json").write_text(json.dumps(mf))
    main_nodes = sorted(B.nid(pos[n]) for n in adj if comp[n] == main_id)
    (out / "main_scc_node_ids.json").write_text(json.dumps(main_nodes))
    # network.json = what analysis/network/engine.py reads (same road ids as the manifest; cf/cb = seconds a->b / b->a, None = not traversable)
    net = [{"id": r["rid"], "name": r["name"], "type": r["type"], "ow": r["ow"], "a": B.nid(r["a"]), "b": B.nid(r["b"]),
            "cf": r["cf"], "cb": r["cb"], "L": r["L"], "coords": [list(p) for p in r["coords"]]} for r in roads]
    (out / "network.json").write_text(json.dumps({"graph_version": gv, "roads": net}, default=str))
    acc = defaultdict(lambda: {"roads": 0, "streets": Counter(), "x": 0.0, "y": 0.0})
    for r in roads:
        w = acc[wroot[B.nid(r["a"])]]; w["roads"] += 1; w["streets"][r["name"]] += 1; w["x"] += r["a"][0]; w["y"] += r["a"][1]
    top = sorted(acc.values(), key=lambda w: -w["roads"])[1:6]
    rep = {"graph_version": gv, "roads": len(roads), "nodes": len(adj), "directed_edges": sum(len(v) for v in adj.values()),
           "road_types": dict(Counter(r["type"] for r in roads).most_common(8)),
           "strongly_connected": {"components": len(scc), "largest": scc[0], "largest_share": round(scc[0] / len(adj), 4), "next_5": scc[1:6]},
           "weakly_connected": {"components": len(wcc), "largest": wcc[0], "next_5": wcc[1:6]},
           "next_weak_components": [{"roads": w["roads"], "centroid_lon_lat": [round(w["x"]/w["roads"], 4), round(w["y"]/w["roads"], 4)], "top_streets": [k for k, _ in w["streets"].most_common(4)]} for w in top]}
    sc = {}
    for q in (a.street or []):
        rs = [r for r in roads if q.lower() in r["name"].lower()]
        sc[q] = {"segments_in_manifest": len(rs), "start_node_in_main_scc": sum(comp[B.nid(r["a"])] == main_id for r in rs), "by_traversability": dict(Counter(r["ow"] for r in rs))}
    if sc: rep["street_checks"] = sc
    (out / "audit_report.json").write_text(json.dumps(rep, indent=2)); print(json.dumps(rep, indent=2))
    byid = {r["rid"]: r for r in roads}
    for tr in (a.trip or []):
        o, d = tr.strip().split(":"); pt = lambda s: tuple(float(x) for x in s.split(","))
        snap = lambda p: min(pos, key=lambda n: B.hav(pos[n], p)); po, pd = pt(o), pt(d); so, sd = snap(po), snap(pd)
        res = B.route(adj, so, sd, None)
        print(f"\nTRIP {o} -> {d} (snap {B.hav(pos[so], po):.0f} m / {B.hav(pos[sd], pd):.0f} m; in main SCC: {comp[so]==main_id}/{comp[sd]==main_id})")
        if not res: print("  NO DIRECTED PATH"); continue
        t, path = res; names = []
        for rid in path:
            n = byid[rid]["name"] or "(unnamed)"
            if not names or names[-1] != n: names.append(n)
        print(f"  {t/60:.1f} min, {sum(byid[r]['L'] for r in path)/1000:.2f} km, {len(path)} segments\n  via:", " > ".join(names[:25]))
    print(f"\nWrote {out}/road_manifest.json, main_scc_node_ids.json, network.json, audit_report.json")
if __name__ == "__main__": main()