"""NEA Wet-Bulb Globe Temperature (WBGT) history from the data.gov.sg real-time API.

Pulls every 15-minute reading at all NEA WBGT stations for the hot inter-monsoon months
(1 Mar - 31 May 2026) and counts, per station, the hours at or above 31 degC (NEA 'moderate'
heat stress or higher) and 33 degC ('high').  Usage: python -m uri.wbgt
"""
import datetime as dt
import json
import time
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
START, END = dt.date(2026, 3, 1), dt.date(2026, 5, 31)


def get(url):
    for a in range(8):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            time.sleep(10 * (a + 1) if "429" in str(e) else 3)
    raise RuntimeError(url)


def day(d):
    base = f"https://api-open.data.gov.sg/v2/real-time/api/weather?api=wbgt&date={d.isoformat()}"
    recs, tok = [], None
    while True:
        r = get(base + (f"&paginationToken={tok}" if tok else ""))
        recs += r["data"]["records"]
        tok = r["data"].get("paginationToken")
        time.sleep(1.1)
        if not tok:
            return recs


if __name__ == "__main__":
    out = RAW / "wbgt_2026_MarMay.json"
    store = json.loads(out.read_text()) if out.exists() else {}
    d = START
    while d <= END:
        if d.isoformat() not in store:
            rows = []
            for rec in day(d):
                for x in rec["item"]["readings"]:
                    try:
                        float(x["wbgt"])
                    except (TypeError, ValueError):
                        continue
                    rows.append([rec["datetime"], x["station"]["id"], float(x["wbgt"])])
                    store.setdefault("_stations", {})[x["station"]["id"]] = dict(
                        name=x["station"]["name"], lat=float(x["location"]["latitude"]), lon=float(x["location"]["longitude"]))
            store[d.isoformat()] = rows
            out.write_text(json.dumps(store))
            print(d, len(rows), flush=True)
        d += dt.timedelta(days=1)
