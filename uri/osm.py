"""Pedestrian network for Singapore from OpenStreetMap (Overpass API).

Keeps every way a person can walk on (footways, paths, covered linkways, service and local roads)
and drops motorways/trunks. Tags kept: highway, covered, tunnel, indoor, layer, footway.
OSM data (c) OpenStreetMap contributors, ODbL 1.0.

Usage: python -m uri.osm
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
BBOX = "1.2,103.6,1.48,104.1"   # S,W,N,E
WALK = "footway|path|pedestrian|steps|corridor|living_street|residential|service|unclassified|tertiary|tertiary_link|secondary|secondary_link|primary|primary_link|cycleway|track"
QUERY = f"""[out:json][timeout:300];
way["highway"~"^({WALK})$"]["access"!~"private|no"]["foot"!~"no"]({BBOX});
out tags geom qt;"""
KEEP = ("highway", "covered", "tunnel", "indoor", "layer", "footway", "bridge")


MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def query(bbox):
    q = QUERY.replace(BBOX, bbox)
    for attempt in range(12):
        url = MIRRORS[attempt % len(MIRRORS)]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                         headers={"User-Agent": "urban-resilience-index/0.1 (research)", "Accept": "*/*"})
            return json.loads(urllib.request.urlopen(req, timeout=900).read())
        except Exception as e:
            print("  retry", bbox, url.split("/")[2], e, flush=True)
            time.sleep(45)
    raise RuntimeError(bbox)


def fetch(nx=6, ny=4):
    """Query the island in nx * ny tiles (one big query times out), merge and de-duplicate ways."""
    out = RAW / "osm_walk.json"
    if out.exists():
        return out
    s, w, n, e = map(float, BBOX.split(","))
    ways, stamp = {}, None
    for i in range(nx):
        for j in range(ny):
            bb = f"{s + (n - s) * j / ny:.4f},{w + (e - w) * i / nx:.4f},{s + (n - s) * (j + 1) / ny:.4f},{w + (e - w) * (i + 1) / nx:.4f}"
            tile = RAW / "osm_tiles" / f"{i}_{j}.json"
            tile.parent.mkdir(exist_ok=True)
            if tile.exists():
                d = json.loads(tile.read_text())
            else:
                d = query(bb)
                tile.write_text(json.dumps(d))
                time.sleep(20)
            stamp = d.get("osm3s", {}).get("timestamp_osm_base", stamp)
            for el in d["elements"]:
                if el["type"] == "way" and "geometry" in el:
                    ways[el["id"]] = dict(id=el["id"], tags={k: el["tags"][k] for k in KEEP if k in el.get("tags", {})},
                                          geom=[(round(p["lon"], 7), round(p["lat"], 7)) for p in el["geometry"]])
            print(bb, "->", len(ways), "ways so far", flush=True)
    out.write_text(json.dumps(dict(timestamp=stamp, ways=list(ways.values()))))
    return out


def from_pbf(pbf=RAW / "osm_pbf" / "Singapore.osm.pbf"):
    """Same output as fetch(), built from a local extract (BBBike Singapore .osm.pbf) when Overpass is overloaded."""
    import re
    import osmium
    walk = re.compile(f"^({WALK})$")
    s, w, n, e = map(float, BBOX.split(","))
    ways = []
    for o in osmium.FileProcessor(str(pbf)).with_locations().with_filter(osmium.filter.KeyFilter("highway")):
        if not o.is_way():
            continue
        t = dict(o.tags)
        if not walk.match(t.get("highway", "")) or t.get("access") in ("private", "no") or t.get("foot") == "no":
            continue
        try:
            g = [(round(nd.lon, 7), round(nd.lat, 7)) for nd in o.nodes]
        except osmium.InvalidLocationError:
            continue
        if any(s <= la <= n and w <= lo <= e for lo, la in g):
            ways.append(dict(id=o.id, tags={k: t[k] for k in KEEP if k in t}, geom=g))
    hdr = osmium.io.Reader(str(pbf), osmium.osm.osm_entity_bits.NOTHING).header()
    stamp = hdr.get("osmosis_replication_timestamp") or "BBBike extract " + str(pbf.stat().st_mtime)
    out = RAW / "osm_walk.json"
    out.write_text(json.dumps(dict(timestamp=stamp, source="BBBike Singapore extract", ways=ways)))
    return out


if __name__ == "__main__":
    import sys
    p = from_pbf() if "--pbf" in sys.argv else fetch()
    d = json.loads(p.read_text())
    print(len(d["ways"]), "ways; OSM base", d["timestamp"])
