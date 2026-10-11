"""Geocode the 36 locations on PUB's 'List of Flood Prone Areas in Singapore (as of Nov 2025)'.

Each entry is a road, junction or small area; we geocode one representative search term per entry
with OneMap and keep the first hit. Output: data/raw/pub_flood_prone_nov2025.geojson
"""
import json, time, urllib.parse, urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
ENTRIES = [  # (S/N, PUB wording (shortened), OneMap search term)
    (1, "Prince Philip Avenue / Jervois Road", "PRINCE PHILIP AVENUE"),
    (2, "Admiralty Road West", "ADMIRALTY ROAD WEST"),
    (3, "St John's HQ, Beach Road / Java Road", "JAVA ROAD"),
    (4, "Bedok South Rd slip road to Bedok South Ave 1", "BEDOK SOUTH ROAD"),
    (5, "Service road off Changi Road near Chin Cheng Ave", "CHIN CHENG AVENUE"),
    (6, "Commonwealth Drive / Commonwealth Ave", "COMMONWEALTH DRIVE"),
    (7, "CTE slip road to Moulmein Road", "MOULMEIN ROAD"),
    (8, "Derbyshire Rd / Cambridge Rd / Farrer Park Field", "DERBYSHIRE ROAD"),
    (9, "Hong Kah Area", "HONG KAH"),
    (10, "Indus Road", "INDUS ROAD"),
    (11, "Jalan Benaan Kapal", "JALAN BENAAN KAPAL"),
    (12, "Jalan Besar Area", "JALAN BESAR"),
    (13, "Jalan Mashor", "JALAN MASHOR"),
    (14, "Jalan Mat Jambol", "JALAN MAT JAMBOL"),
    (15, "Jalan Taman", "JALAN TAMAN"),
    (16, "People's Association HQ, King George's Ave", "KING GEORGE'S AVENUE"),
    (17, "Langsat Road Area", "LANGSAT ROAD"),
    (18, "Lorong Buangkok Area", "LORONG BUANGKOK"),
    (19, "Lorong H Telok Kurau", "LORONG H TELOK KURAU"),
    (20, "Alexandra Road / Lower Delta Road", "LOWER DELTA ROAD"),
    (21, "Margaret Drive / Tanglin Road", "MARGARET DRIVE"),
    (22, "Meyer Road Area", "MEYER ROAD"),
    (23, "Mimosa Walk", "MIMOSA WALK"),
    (24, "Mindef Changi Camp", "CHANGI VILLAGE ROAD"),
    (25, "Service Road off Mountbatten Rd near Jalan Seaview", "JALAN SEAVIEW"),
    (26, "Neo Pee Teck Lane / Pasir Panjang Road", "NEO PEE TECK LANE"),
    (27, "New Upper Changi Road / Tanah Merah Kechil Ave", "TANAH MERAH KECHIL AVENUE"),
    (28, "Rose Lane", "ROSE LANE"),
    (29, "Second Chin Bee Road", "SECOND CHIN BEE ROAD"),
    (30, "Sennett Estate", "SIANG KUANG AVENUE"),
    (31, "Service road off Tampines Road near Jalan Teliti", "JALAN TELITI"),
    (32, "Stevens Road / Balmoral Road", "BALMORAL ROAD"),
    (33, "South Bridge Rd / Upper Hokien St / Upper Pickering St", "UPPER HOKIEN STREET"),
    (34, "Upper East Coast Road near Parbury Avenue", "PARBURY AVENUE"),
    (35, "Waterloo St / Bencoolen St / Prinsep St", "WATERLOO STREET"),
    (36, "Former Boys' Brigade HQ, Zion Road", "ZION ROAD"),
]
feats = []
for sn, name, q in ENTRIES:
    url = ("https://www.onemap.gov.sg/api/common/elastic/search?searchVal=" + urllib.parse.quote(q)
           + "&returnGeom=Y&getAddrDetails=Y&pageNum=1")
    d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
    h = d["results"][0] if d.get("results") else None
    print(sn, q, "->", h and h["SEARCHVAL"], h and (h["LATITUDE"], h["LONGITUDE"]))
    if h:
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(h["LONGITUDE"]), float(h["LATITUDE"])]},
                      "properties": {"sn": sn, "location": name, "matched": h["SEARCHVAL"]}})
    time.sleep(1.0)
(RAW / "pub_flood_prone_nov2025.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, indent=1))
print(len(feats), "of", len(ENTRIES))
