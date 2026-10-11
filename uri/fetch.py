"""Download the open datasets behind the index (data.gov.sg, Singapore Open Data Licence v1.0).

Usage:  python -m uri.fetch            (skips files that already exist)

Every file lands in data/raw/ under the name given in DATASETS. Sources are credited in
docs/DATA.md as the licence requires.
"""
import json
import time
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (urban-resilience-index research)"}

# name -> (data.gov.sg dataset id, publisher, what it feeds)
DATASETS = {
    "hdb_buildings.geojson":      ("d_16b157c52ed637edd6ba1232e026258d", "HDB", "block footprints"),
    "subzones.geojson":           ("d_8594ae9ff96d0c708bc2af633048edfb", "URA", "Master Plan 2019 subzone boundary"),
    "pop_age_subzone_2020.csv":   ("d_d95ae740c0f8961a0b10435836660ce0", "SingStat", "Census 2020 residents by subzone and age"),
    "hawker_centres.geojson":     ("d_4a086da0a5553be1d89383cd90d07ecd", "NEA", "access: hawker centre"),
    "chas_clinics.geojson":       ("d_548c33ea2d99e29ec63a7cc9edcccedc", "MOH", "access: clinic"),
    "mrt_exits.geojson":          ("d_b39d3a0871985372d7e1637193335da5", "LTA", "access: MRT exit"),
    "bus_stops.geojson":          ("d_3f172c6feb3f4f92a2f47d93eed2908a", "LTA", "access: bus stop"),
    "eldercare.geojson":          ("d_f0fd1b3643ed8bd34bd403dedd7c1533", "MOH", "access: eldercare / AAC"),
    "nparks_parks_reserves.geojson": ("d_77d7ec97be83d44f61b85454f844382f", "NParks", "green-blue: parks and nature reserves"),
    "park_connector.geojson":     ("d_a69ef89737379f231d2ae93fd1c5707f", "NParks", "green-blue: Park Connector Loop"),
    "waterbody.geojson":          ("d_0b0792ae30cd6cce62e5ea55fc37860e", "URA", "green-blue: waterbodies"),
    "community_in_bloom.geojson": ("d_f91a8b057cfb2bebf2e531ad8061e1c1", "NParks", "community: Community in Bloom gardens"),
    "landuse_mp2025.geojson":     ("d_a8c3546b26712e35021f3a681d0353ae", "URA", "Master Plan 2025 land use"),
    "resale_2017on.csv":          ("d_8b84c4ee58e3cfc0ece0d773c8ca6abc", "HDB", "value lens: resale transactions"),
}


def get(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def hdb_property_info():
    """HDB Property Information (d_17f5382f26140b1fdae0ba2ef6239d2f) through the datastore API, as JSON records."""
    out = RAW / "hdb_property_info.json"
    if out.exists():
        return out
    rid, recs, off = "d_17f5382f26140b1fdae0ba2ef6239d2f", [], 0
    while True:
        d = json.loads(get(f"https://data.gov.sg/api/action/datastore_search?resource_id={rid}&limit=5000&offset={off}"))
        batch = d["result"]["records"]
        recs += batch; off += len(batch)
        if not batch or off >= d["result"]["total"]:
            break
        time.sleep(2)
    out.write_text(json.dumps(recs))
    return out


def download(name, dsid):
    out = RAW / name
    if out.exists():
        return out
    for attempt in range(5):
        try:
            meta = json.loads(get(f"https://api-open.data.gov.sg/v1/public/api/datasets/{dsid}/poll-download"))
            url = meta["data"].get("url")
            if url:
                out.write_bytes(get(url, timeout=600))
                return out
            get(f"https://api-open.data.gov.sg/v1/public/api/datasets/{dsid}/initiate-download")
        except Exception as e:
            print("  retry", name, e)
        time.sleep(8 * (attempt + 1))
    raise RuntimeError(f"could not download {name} ({dsid})")


if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    p = hdb_property_info()
    print(f"{p.name:32s} {p.stat().st_size/1e6:7.2f} MB  HDB      block attributes (units, rental, year)")
    for name, (dsid, pub, use) in DATASETS.items():
        p = download(name, dsid)
        print(f"{name:32s} {p.stat().st_size/1e6:7.2f} MB  {pub:8s} {use}")
        time.sleep(2)
