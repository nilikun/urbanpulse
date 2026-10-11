"""Geocode every residential HDB block (data.gov.sg HDB Property Information) with the OneMap Search API.

OneMap is rate limited (~250 calls/min); three workers with a 0.8 s pause each stay under it.
Resumable: results are cached in data/raw/hdb_geocoded.json.
"""
import json, sys, time, threading, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT = RAW / "hdb_geocoded.json"
recs = [r for r in json.loads((RAW / "hdb_property_info.json").read_text()) if r["residential"] == "Y"]
geo = json.loads(OUT.read_text()) if OUT.exists() else {}
seed = Path(sys.argv[1]) if len(sys.argv) > 1 else None          # optional earlier cache (same key format)
if seed and seed.exists():
    for k, v in json.loads(seed.read_text()).items():
        geo.setdefault(k, v)
lock = threading.Lock()
todo = [r for r in recs if f'{r["blk_no"]}|{r["street"]}' not in geo]
print("residential blocks", len(recs), "to geocode", len(todo), flush=True)


def one(r):
    key = f'{r["blk_no"]}|{r["street"]}'
    q = urllib.parse.quote(f'{r["blk_no"]} {r["street"]}')
    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={q}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read())
            hit = next((h for h in d.get("results", []) if h["BLK_NO"].upper() == r["blk_no"].upper()), None)
            val = {"X": float(hit["X"]), "Y": float(hit["Y"]), "lat": float(hit["LATITUDE"]),
                   "lon": float(hit["LONGITUDE"]), "postal": hit["POSTAL"]} if hit else None
            break
        except Exception as e:
            val = None
            time.sleep(20 if "429" in str(e) else 3)
    with lock:
        geo[key] = val
    time.sleep(0.8)


with ThreadPoolExecutor(3) as ex:
    for i, _ in enumerate(ex.map(one, todo)):
        if i % 200 == 0:
            with lock:
                OUT.write_text(json.dumps(geo))
            print(i, flush=True)
OUT.write_text(json.dumps(geo))
print("done; geocoded", sum(v is not None for v in geo.values()), "of", len(geo), flush=True)
