"""Download real open data for the Woodlands GLS reference-site case study.

Sources (all open):
  - HDB Property Information (data.gov.sg, d_17f5382f26140b1fdae0ba2ef6239d2f)
  - OneMap Search API (SLA) for SVY21 coordinates of HDB blocks
  - Eldercare Services GeoJSON (MOH via data.gov.sg, d_f0fd1b3643ed8bd34bd403dedd7c1533)
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

RAW = Path(sys.argv[1])
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}

def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# 1. HDB property information (all blocks)
hdb_path = RAW / "hdb_property_info.json"
if not hdb_path.exists():
    rid = "d_17f5382f26140b1fdae0ba2ef6239d2f"
    recs, off = [], 0
    while True:
        d = json.loads(get(f"https://data.gov.sg/api/action/datastore_search?resource_id={rid}&limit=5000&offset={off}"))
        batch = d["result"]["records"]
        recs += batch
        off += len(batch)
        if not batch or off >= d["result"]["total"]:
            break
        time.sleep(1.5)
    hdb_path.write_text(json.dumps(recs))
recs = json.loads(hdb_path.read_text())
print("HDB blocks:", len(recs))

# 2. Geocode Woodlands (WL) residential blocks via OneMap
wl = [r for r in recs if r["bldg_contract_town"] == "WL"]
print("Woodlands blocks:", len(wl))
geo_path = RAW / "wl_geocoded.json"
geo = json.loads(geo_path.read_text()) if geo_path.exists() else {}
for i, r in enumerate(wl):
    key = f'{r["blk_no"]}|{r["street"]}'
    if geo.get(key) is not None:
        continue
    q = urllib.parse.quote(f'{r["blk_no"]} {r["street"]}')
    try:
        d = json.loads(get(f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={q}&returnGeom=Y&getAddrDetails=Y&pageNum=1"))
        hit = next((h for h in d.get("results", []) if h["BLK_NO"].upper() == r["blk_no"].upper()), None)
        geo[key] = {"X": float(hit["X"]), "Y": float(hit["Y"]), "lat": float(hit["LATITUDE"]), "lon": float(hit["LONGITUDE"]), "postal": hit["POSTAL"]} if hit else None
    except Exception as e:
        print("fail", key, e)
        geo[key] = None
        if "429" in str(e):
            time.sleep(20)
    if i % 50 == 0:
        geo_path.write_text(json.dumps(geo)); print(i, key, geo[key])
    time.sleep(0.9)
geo_path.write_text(json.dumps(geo))
print("geocoded:", sum(v is not None for v in geo.values()))

# 3. Eldercare services (GeoJSON)
ec_path = RAW / "eldercare.geojson"
if not ec_path.exists():
    meta = json.loads(get("https://api-open.data.gov.sg/v1/public/api/datasets/d_f0fd1b3643ed8bd34bd403dedd7c1533/poll-download"))
    ec_path.write_bytes(get(meta["data"]["url"]))
print("eldercare bytes:", ec_path.stat().st_size)
