"""The Urban Resilience Index: six pillars, block level, 0-100 (higher = more resilient).

Follows the concept brief:
  indicators -> 0-100 percentile across all HDB blocks (flipped where lower is better)
  pillar     =  mean of its indicators
  block      =  sum(weight x pillar) over the six pillars
  town       =  need-weighted mean of block scores (vulnerability weights, it is not a pillar)
  inclusion  =  gap between the median block and the worst-served 20% of blocks
Every indicator carries a confidence flag. Usage: python -m uri.index
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import signal
from scipy.spatial import cKDTree

from .network import Network

ROOT = Path(__file__).resolve().parents[1]
RAW, SAT, PROC = ROOT / "data" / "raw", ROOT / "data" / "satellite", ROOT / "data" / "processed"
CRS = "EPSG:3414"
X0, Y1 = 2_000, 52_000

WEIGHTS = {"heat": 25, "shade": 20, "green": 15, "community": 15, "access": 15, "flood": 10}   # brief defaults
PILLAR_NAMES = {"heat": "Heat exposure", "shade": "Shade & cooling", "green": "Green-blue space",
                "community": "Community & green use", "access": "Access & mobility", "flood": "Flood resilience"}


@dataclass
class Indicator:
    key: str
    pillar: str
    label: str
    unit: str
    higher_is_better: bool
    source: str
    confidence: str   # high: measured and current | medium: modelled or approximated | low: proxy


INDICATORS = [
    Indicator("lst_anom", "heat", "Surface heat within 100 m (Landsat 8/9, 2021-25)", "degC vs island median", False,
              "USGS Landsat C2 L2 via Planetary Computer", "high"),
    Indicator("canopy200", "shade", "Tree canopy within 200 m (NDVI > 0.6)", "% of land", True,
              "Copernicus Sentinel-2 L2A 2024-25", "medium"),
    Indicator("route_shade400", "shade", "Shaded share of walkways within 400 m", "% of length", True,
              "OSM covered ways + Sentinel-2 canopy", "medium"),
    Indicator("park_walk", "green", "Walk to nearest park", "m (network)", False,
              "NParks parks and nature reserves + OSM", "high"),
    Indicator("park_area800", "green", "Park area within 800 m (10-min walk)", "ha", True,
              "NParks parks and nature reserves", "high"),
    Indicator("blue_dist", "green", "Distance to park connector or waterbody", "m", False,
              "NParks Park Connector Loop, URA Master Plan waterbodies", "high"),
    Indicator("gardens400", "community", "Community in Bloom gardens within 400 m", "count", True,
              "NParks Community in Bloom (proxy until resident reports exist)", "low"),
    Indicator("walk_aac", "access", "Shaded walk to eldercare / AAC", "m (heat-adjusted)", False, "MOH eldercare services + OSM", "high"),
    Indicator("walk_clinic", "access", "Shaded walk to CHAS clinic", "m (heat-adjusted)", False, "MOH CHAS clinics + OSM", "high"),
    Indicator("walk_hawker", "access", "Shaded walk to hawker centre", "m (heat-adjusted)", False, "NEA hawker centres + OSM", "high"),
    Indicator("walk_mrt", "access", "Shaded walk to MRT exit", "m (heat-adjusted)", False, "LTA MRT station exits + OSM", "high"),
    Indicator("walk_bus", "access", "Shaded walk to bus stop", "m (heat-adjusted)", False, "LTA bus stops + OSM", "high"),
    Indicator("flood_dist", "flood", "Distance to a PUB flood-prone location", "m", True,
              "PUB list of flood-prone areas, Nov 2025 (geocoded)", "medium"),
]
IND = {i.key: i for i in INDICATORS}

# Computed and shown, but not scored. NEA WBGT is the right heat-stress measure, yet 27 stations cannot
# resolve blocks: it fails the brief's test 3 ("data ... at block or precinct level") and its values
# track station siting (forest and waterfront stations are the most humid). It stays a live context
# layer until a denser sensor network or resident readings exist (phase 2).
CONTEXT = {"wbgt_hours": "Hours at WBGT >= 31 degC, Mar-May 2026 (27 NEA stations, interpolated)",
           "lst_anom_1990s": "Surface heat within 100 m, Landsat 5 1988-97",
           "lst_abs": "Median surface temperature 2021-25, ~10:30 local time (degC)"}


# ----------------------------------------------------------------------------- raster helpers
def disk(r_px):
    y, x = np.ogrid[-r_px:r_px + 1, -r_px:r_px + 1]
    return (x * x + y * y <= r_px * r_px).astype("float32")


def focal_mean(arr, r_m, res):
    """Mean of finite pixels within r_m metres (NaN-aware disk filter)."""
    k = disk(int(round(r_m / res)))
    ok = np.isfinite(arr)
    num = signal.fftconvolve(np.where(ok, arr, 0).astype("float64"), k, mode="same")
    den = signal.fftconvolve(ok.astype("float64"), k, mode="same")
    return np.where(den > 0.5, num / np.maximum(den, 1e-6), np.nan)


def sample(arr, x, y, res):
    c = ((np.asarray(x) - X0) / res).astype(int); r = ((Y1 - np.asarray(y)) / res).astype(int)
    r = np.clip(r, 0, arr.shape[0] - 1); c = np.clip(c, 0, arr.shape[1] - 1)
    return arr[r, c]


def load_points(name, x_field=None):
    g = gpd.read_file(RAW / name)
    if g.crs is None:
        g = g.set_crs(4326)
    g = g.to_crs(CRS)
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    pts = g.geometry.representative_point() if not (g.geom_type == "Point").all() else g.geometry
    return np.c_[pts.x, pts.y]


def boundary_points(gdf, step=25.0):
    """Points every `step` metres along polygon/line boundaries (park entrances are unknown, so every edge counts)."""
    out = []
    for geom in gdf.geometry:
        line = geom.boundary if geom.geom_type in ("Polygon", "MultiPolygon") else geom
        L = line.length
        for d in np.arange(0, max(L, step), step):
            p = line.interpolate(d); out.append((p.x, p.y))
    return np.array(out)


# ----------------------------------------------------------------------------- indicators
def wbgt_hours(bx, by, thr=31.0):
    d = json.loads((RAW / "wbgt_2026_MarMay.json").read_text())
    st = d.pop("_stations")
    rows = pd.DataFrame([r for v in d.values() for r in v], columns=["t", "sid", "wbgt"])
    hrs = (rows[rows.wbgt >= thr].groupby("sid").size() * 0.25)   # 15-min readings -> hours
    days = rows.groupby("sid").t.apply(lambda s: s.str[:10].nunique())
    hrs = (hrs.reindex(days.index).fillna(0) / days * days.max())  # rescale stations with gaps to full period
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 3414, always_xy=True)
    sx, sy = tf.transform([st[s]["lon"] for s in hrs.index], [st[s]["lat"] for s in hrs.index])
    S = np.c_[sx, sy]; v = hrs.values
    dist, idx = cKDTree(S).query(np.c_[bx, by], k=3)
    w = 1 / np.maximum(dist, 200) ** 2
    meta = dict(stations=len(hrs), days=int(days.max()), threshold=thr,
                station_hours={st[s]["name"]: round(float(h), 1) for s, h in hrs.items()})
    return (w * v[idx]).sum(1) / w.sum(1), meta


def compute_indicators(b, net=None):
    bx, by = b.geometry.x.values, b.geometry.y.values
    out, meta = pd.DataFrame(index=b.index), {}
    land30 = np.load(SAT / "landmask_30m.npy")
    now = np.load(SAT / "lst_now.npz"); then = np.load(SAT / "lst_then.npz")
    a_now = np.where(land30, now["anom"], np.nan); a_then = np.where(land30, then["anom"], np.nan)
    out["lst_anom"] = sample(focal_mean(a_now, 100, 30), bx, by, 30)
    out["lst_anom_1990s"] = sample(focal_mean(a_then, 100, 30), bx, by, 30)      # heat history, reported not scored
    out["lst_abs"] = sample(focal_mean(np.where(land30, now["abs"], np.nan), 100, 30), bx, by, 30)
    out["wbgt_hours"], meta["wbgt"] = wbgt_hours(bx, by)

    ndvi = np.load(SAT / "s2_2024_2025.npz")["ndvi"]
    land10 = np.load(SAT / "landmask_10m.npy")
    can = np.where(land10, (np.nan_to_num(ndvi) > 0.6).astype("float32"), np.nan)
    out["canopy200"] = 100 * sample(focal_mean(can, 200, 10), bx, by, 10)

    net = net or Network()
    meta["network"] = net.summary()
    out["route_shade400"] = 100 * net.shade_share_within(bx, by, 400)

    parks = gpd.read_file(RAW / "nparks_parks_reserves.geojson").to_crs(CRS)
    parks = parks[parks.geom_type.isin(["Polygon", "MultiPolygon"])]
    parks = parks[parks.geometry.area >= 2_000]                                   # pocket parks and larger
    pp = boundary_points(parks)
    G0 = net.set_alpha(0.0)                                                        # plain walking distance
    out["park_walk"] = net.dist_to_nearest(pp[:, 0], pp[:, 1], bx, by, G=G0)
    sidx = parks.sindex
    area = []
    for x, y in zip(bx, by):
        circ = gpd.points_from_xy([x], [y], crs=CRS).buffer(800)[0]
        cand = parks.iloc[list(sidx.query(circ))]
        area.append(cand.geometry.intersection(circ).area.sum() / 1e4)
    out["park_area800"] = area
    pcn = gpd.read_file(RAW / "park_connector.geojson").to_crs(CRS)
    wat = gpd.read_file(RAW / "waterbody.geojson").to_crs(CRS)
    wat = wat[wat.geometry.area >= 5_000] if wat.geom_type.isin(["Polygon", "MultiPolygon"]).all() else wat
    blue = np.vstack([boundary_points(pcn, 50), boundary_points(wat, 50)])
    out["blue_dist"] = cKDTree(blue).query(np.c_[bx, by])[0]

    cib = load_points("community_in_bloom.geojson")
    out["gardens400"] = [len(i) for i in cKDTree(cib).query_ball_point(np.c_[bx, by], 400)]

    G = net.set_alpha(net_alpha := 0.5)
    meta["heat_penalty_alpha"] = net_alpha
    for key, f in [("walk_aac", "eldercare.geojson"), ("walk_clinic", "chas_clinics.geojson"),
                   ("walk_hawker", "hawker_centres.geojson"), ("walk_mrt", "mrt_exits.geojson"),
                   ("walk_bus", "bus_stops.geojson")]:
        p = load_points(f)
        out[key] = net.dist_to_nearest(p[:, 0], p[:, 1], bx, by, G=G)
    fl = load_points("pub_flood_prone_nov2025.geojson")
    out["flood_dist"] = cKDTree(fl).query(np.c_[bx, by])[0]
    return out, meta, net


# ----------------------------------------------------------------------------- scoring
class Scorer:
    """Percentile scoring against a fixed reference (today's HDB blocks), so a scenario can be
    scored on the same scale without re-ranking everyone else."""

    def __init__(self, ref: pd.DataFrame, weights=None):
        self.ref = {k: np.sort(ref[k].dropna().values) for k in IND}
        self.w = dict(weights or WEIGHTS)

    def pct(self, key, v):
        r = self.ref[key]
        p = 100 * (np.searchsorted(r, v, side="left") + np.searchsorted(r, v, side="right")) / (2 * len(r))
        return p if IND[key].higher_is_better else 100 - p

    def score(self, df, weights=None):
        w = weights or self.w
        s = pd.DataFrame(index=df.index)
        for k in IND:
            s["s_" + k] = self.pct(k, df[k].values)
        for p in WEIGHTS:
            ks = [i.key for i in INDICATORS if i.pillar == p]
            s[p] = s[["s_" + k for k in ks]].mean(1)
        tot = sum(w.values())
        s["score"] = sum(w[p] * s[p] for p in WEIGHTS) / tot
        return s


def inclusion_gap(scores, q=0.2):
    s = np.sort(np.asarray(scores))
    return float(np.median(s) - s[: max(1, int(len(s) * q))].mean())


def town_table(b):
    rows = []
    for t, g in b.groupby("town"):
        w = g.need.values
        r = dict(town=t, blocks=len(g), units=int(g.units.sum()), rental=int(g.rental.sum()),
                 seniors=int(g.seniors.sum()), score=float(np.average(g.score, weights=w)),
                 score_plain=float(g.score.mean()), inclusion_gap=inclusion_gap(g.score),
                 lst_anom=float(g.lst_anom.mean()), wbgt_hours=float(g.wbgt_hours.mean()), lst_change=float((g.lst_anom - g.lst_anom_1990s).mean()),
                 median_year=int(g.year.median()))
        for p in WEIGHTS:
            r[p] = float(np.average(g[p], weights=w))
        rows.append(r)
    return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


def redundancy(df, thr=0.8):
    """Brief test 4: flag indicator pairs with |Spearman rho| above thr."""
    keys = [i.key for i in INDICATORS]
    rho = df[keys].rank().corr()
    pairs = [(a, c, round(float(rho.loc[a, c]), 3)) for i, a in enumerate(keys) for c in keys[i + 1:]
             if abs(rho.loc[a, c]) > thr]
    return rho, pairs


def run():
    b = gpd.read_file(PROC / "blocks_base.gpkg")
    ind, meta, net = compute_indicators(b)
    rho, pairs = redundancy(ind)
    meta["redundant_pairs_rho_gt_0.8"] = pairs
    b = pd.concat([b, ind], axis=1)
    sc = Scorer(ind)
    b = gpd.GeoDataFrame(pd.concat([b, sc.score(ind)], axis=1), crs=CRS)
    towns = town_table(b)
    b.to_file(PROC / "blocks_scored.gpkg", driver="GPKG")
    towns.to_csv(PROC / "towns.csv", index=False)
    rho.round(3).to_csv(PROC / "indicator_spearman.csv")
    meta["indicators"] = [asdict(i) for i in INDICATORS]
    meta["context_layers"] = CONTEXT
    meta["wbgt_vs_lst_spearman"] = float(b[["wbgt_hours", "lst_anom"]].rank().corr().iloc[0, 1])
    meta["weights"] = WEIGHTS
    meta["island_inclusion_gap"] = inclusion_gap(b.score)
    (PROC / "index_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(meta["network"]); print("redundant pairs:", pairs)
    print(towns[["town", "blocks", "score", "inclusion_gap", "lst_anom", "lst_change"] + list(WEIGHTS)].round(1).to_string())
    return b, towns, net


if __name__ == "__main__":
    run()
