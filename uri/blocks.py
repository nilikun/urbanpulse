"""Block table: every residential HDB block with location, households and a vulnerability (need) weight.

Join path (no geocoding needed):
  HDB Property Information (blk_no + street name)  --street-name <-> street-code match-->
  HDB Existing Building footprints (BLK_NO + ST_COD, polygons) -> centroid in SVY21.
The street-name <-> street-code table is recovered by matching the set of block numbers on each
street (Jaccard similarity, Hungarian assignment). Checked against 929 OneMap-geocoded Woodlands
blocks: 899 correct, 2 wrong, 28 without a footprint.

Need weight (brief: "vulnerability weights the result rather than adding to it"):
  seniors_b  = (units_b - rental_b) * HH_SIZE * share65(subzone)   [Census 2020, by subzone]
  need_b     = seniors_b + RENTAL_W * rental_b, x OLD_W if completed before OLD_YEAR
"""
import collections
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
CRS = "EPSG:3414"

HH_SIZE = 3.0          # persons per resident household (SingStat GHS 2025: 3.07)
RENTAL_W = 1.5         # extra weight per public-rental household (low income, >90% without air-con; Chew et al. 2026)
OLD_YEAR, OLD_W = 1990, 1.3   # older blocks: thinner insulation, more ageing-in-place (assumption, tested in sensitivity)

TOWNS = {"AMK": "Ang Mo Kio", "BB": "Bukit Batok", "BD": "Bedok", "BH": "Bishan", "BM": "Bukit Merah",
         "BP": "Bukit Panjang", "BT": "Bukit Timah", "CCK": "Choa Chu Kang", "CL": "Clementi", "CT": "Central Area",
         "GL": "Geylang", "HG": "Hougang", "JE": "Jurong East", "JW": "Jurong West", "KWN": "Kallang/Whampoa",
         "MP": "Marine Parade", "PG": "Punggol", "PRC": "Pasir Ris", "QT": "Queenstown", "SB": "Sembawang",
         "SGN": "Serangoon", "SK": "Sengkang", "TAP": "Tampines", "TG": "Tengah", "TP": "Toa Payoh",
         "WL": "Woodlands", "YS": "Yishun"}


def street_code_table(fp, pi):
    code_blks, st_blks = collections.defaultdict(set), collections.defaultdict(set)
    for _, f in fp.iterrows():
        code_blks[f.ST_COD].add(str(f.BLK_NO).upper())
    for r in pi:
        st_blks[r["street"]].add(r["blk_no"].upper())
    C, S = list(code_blks), list(st_blks)
    J = np.zeros((len(S), len(C)))
    for i, s in enumerate(S):
        a = st_blks[s]
        for j, c in enumerate(C):
            n = len(a & code_blks[c])
            if n:
                J[i, j] = n / len(a | code_blks[c])
    r, c = linear_sum_assignment(-J)
    return {S[i]: (C[j], J[i, j]) for i, j in zip(r, c) if J[i, j] >= 0.5}


def senior_share():
    df = pd.read_csv(RAW / "pop_age_subzone_2020.csv")
    df = df[~df["Number"].str.contains("Total")].copy()
    old = ["Total_65_69", "Total_70_74", "Total_75_79", "Total_80_84", "Total_85_89", "Total_90andOver"]
    for c in old + ["Total_Total"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "").replace("-", "0"), errors="coerce").fillna(0)
    df["share65"] = df[old].sum(1) / df["Total_Total"].replace(0, np.nan)
    df["SUBZONE_N"] = df["Number"].str.strip().str.upper()
    return df.set_index("SUBZONE_N")[["share65", "Total_Total"]]


def build():
    pi = json.loads((RAW / "hdb_property_info.json").read_text())
    fp = gpd.read_file(RAW / "hdb_buildings.geojson").set_crs(4326, allow_override=True).to_crs(CRS)
    fp["BLK_NO"] = fp["BLK_NO"].astype(str).str.upper()
    table = street_code_table(fp, pi)
    fp = fp.dissolve(by=["ST_COD", "BLK_NO"], as_index=False, aggfunc={"POSTAL_COD": "first"})
    fp["area_m2"] = fp.geometry.area
    idx = {(r.ST_COD, r.BLK_NO): i for i, r in fp.iterrows()}

    rows, missing = [], 0
    for r in pi:
        if r["residential"] != "Y":
            continue
        code = table.get(r["street"], (None,))[0]
        i = idx.get((code, r["blk_no"].upper()))
        if i is None:
            missing += 1
            continue
        g = fp.geometry.iloc[i]
        units = int(r["total_dwelling_units"] or 0)
        rental = sum(int(r[k] or 0) for k in ("1room_rental", "2room_rental", "3room_rental", "other_room_rental"))
        rows.append(dict(blk=r["blk_no"], street=r["street"], town_code=r["bldg_contract_town"],
                         town=TOWNS.get(r["bldg_contract_town"], r["bldg_contract_town"]),
                         postal=fp.POSTAL_COD.iloc[i], year=int(r["year_completed"] or 0),
                         floors=int(r["max_floor_lvl"] or 0), units=units, rental=rental,
                         footprint_m2=round(fp.area_m2.iloc[i], 1),
                         x=g.centroid.x, y=g.centroid.y))
    b = gpd.GeoDataFrame(rows, geometry=gpd.points_from_xy([r["x"] for r in rows], [r["y"] for r in rows]), crs=CRS)
    b = b[b.units > 0].reset_index(drop=True)

    sz = gpd.read_file(RAW / "subzones.geojson").to_crs(CRS)[["SUBZONE_N", "PLN_AREA_N", "geometry"]]
    b = gpd.sjoin(b, sz, how="left", predicate="within").drop(columns="index_right")
    share = senior_share()
    b = b.join(share, on="SUBZONE_N")
    b["share65_imputed"] = b["share65"].isna()
    # towns with no residents in Census 2020 (e.g. Tengah): fall back to the town, then island median
    b["share65"] = b["share65"].fillna(b.groupby("town")["share65"].transform("median")).fillna(b["share65"].median())
    b["seniors"] = (b.units - b.rental) * HH_SIZE * b.share65
    b["need"] = (b.seniors + RENTAL_W * b.rental) * np.where(b.year < OLD_YEAR, OLD_W, 1.0)
    b["block_id"] = b.blk + "|" + b.street
    print(f"residential blocks matched: {len(b)} (unmatched: {missing}); towns: {b.town.nunique()}; "
          f"units: {b.units.sum():,}; rental units: {b.rental.sum():,}")
    PROC.mkdir(parents=True, exist_ok=True)
    b.to_file(PROC / "blocks_base.gpkg", driver="GPKG")
    return b


if __name__ == "__main__":
    build()
