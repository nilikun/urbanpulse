"""Neighbourhood layer: real HDB blocks around the reference site, vulnerability weights,
candidate public green-pocket locations, and eldercare centres."""
import json, math, re
from pathlib import Path
import numpy as np
from params import SITE, PEOPLE

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def _svy21(lat, lon):
    """WGS84 -> SVY21 (SLA formulae)."""
    a, f = 6378137.0, 1 / 298.257223563
    oLat, oLon, oN, oE, k = 1.366666, 103.833333, 38744.572, 28001.642, 1.0
    b = a * (1 - f); e2 = (2 * f) - f * f; e4, e6 = e2 * e2, e2 ** 3
    A0 = 1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256
    A2 = 3 / 8 * (e2 + e4 / 4 + 15 * e6 / 128); A4 = 15 / 256 * (e4 + 3 * e6 / 4); A6 = 35 * e6 / 3072
    def M(la):
        r = math.radians(la)
        return a * (A0 * r - A2 * math.sin(2 * r) + A4 * math.sin(4 * r) - A6 * math.sin(6 * r))
    r = math.radians(lat); s = math.sin(r); c = math.cos(r)
    rho = a * (1 - e2) / (1 - e2 * s * s) ** 1.5; v = a / math.sqrt(1 - e2 * s * s); psi = v / rho; t = math.tan(r)
    w = math.radians(lon - oLon)
    N = oN + k * (M(lat) - M(oLat) + v * s * w * w / 2 * c + v * s * c ** 3 * w ** 4 / 24 * (4 * psi ** 2 + psi - t * t))
    E = oE + k * v * w * c * (1 + w * w / 6 * c * c * (psi - t * t))
    return E, N


def load_blocks(use_index=True):
    """HDB blocks within PEOPLE['radius'] of the site.

    use_index=True (default, upgraded): need weights come from the island-wide Urban Resilience Index
    (Census 2020 subzone senior share + public-rental households, older-block factor) and are scaled
    by each block's resilience shortfall, so cool-refuge pockets go where the index sees most need:
        V_b = need_b * (100 - score_b) / 50          (a median block, score 50, keeps factor 1)
    use_index=False reproduces the original hackathon version (one town-level senior share)."""
    if use_index:
        import geopandas as gpd
        b = gpd.read_file(RAW.parent / "processed" / "blocks_scored.gpkg")
        b["dist"] = np.hypot(b.geometry.x - SITE["X"], b.geometry.y - SITE["Y"])
        b = b[b.dist <= PEOPLE["radius"]]
        return [dict(blk=r.blk, street=r.street, X=r.geometry.x, Y=r.geometry.y, units=int(r.units), rental=int(r.rental),
                     year=int(r.year), seniors=float(r.seniors), V=float(r.need * (100 - r.score) / 50), dist=float(r.dist),
                     score=float(r.score), residential=True) for r in b.itertuples()]
    recs = json.loads((RAW / "hdb_property_info.json").read_text())
    geo = json.loads((RAW / "wl_geocoded.json").read_text())
    out = []
    for r in recs:
        if r["bldg_contract_town"] != "WL":
            continue
        g = geo.get(f'{r["blk_no"]}|{r["street"]}')
        if not g:
            continue
        d = math.hypot(g["X"] - SITE["X"], g["Y"] - SITE["Y"])
        if d > PEOPLE["radius"]:
            continue
        units = int(r["total_dwelling_units"] or 0)
        rental = sum(int(r[k] or 0) for k in ("1room_rental", "2room_rental", "3room_rental", "other_room_rental"))
        yr = int(r["year_completed"] or 2000)
        seniors = (units - rental) * PEOPLE["hh_size"] * PEOPLE["share65"]
        V = seniors + PEOPLE["rental_w"] * rental
        if yr < PEOPLE["old_block_year"]:
            V *= PEOPLE["old_block_w"]
        out.append(dict(blk=r["blk_no"], street=r["street"], X=g["X"], Y=g["Y"], units=units, rental=rental,
                        year=yr, seniors=seniors, V=V, dist=d, residential=r["residential"] == "Y"))
    return out


def load_eldercare():
    d = json.loads((RAW / "eldercare.geojson").read_text(encoding="utf-8"))
    out = []
    for f in d["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        X, Y = _svy21(lat, lon)
        dist = math.hypot(X - SITE["X"], Y - SITE["Y"])
        if dist <= PEOPLE["radius"] + 200:
            m = re.search(r"<th>NAME</th> <td>(.*?)</td>", f["properties"]["Description"])
            out.append(dict(name=m.group(1) if m else "Eldercare", X=X, Y=Y, dist=dist))
    return out


def candidates(blocks):
    """Public green-pocket candidates: 8 points on the site edge (on-site) + HDB estate greens
    next to blocks within 600 m (off-site community pockets, delivered with the Town Council)."""
    half = math.sqrt(SITE["area"]) / 2           # site approximated as a square (~120 m side)
    cands = []
    for i, (dx, dy, nm) in enumerate([(0, 1, "N"), (1, 1, "NE"), (1, 0, "E"), (1, -1, "SE"),
                                      (0, -1, "S"), (-1, -1, "SW"), (-1, 0, "W"), (-1, 1, "NW")]):
        cands.append(dict(id=f"edge-{nm}", onsite=True, X=SITE["X"] + dx * half, Y=SITE["Y"] + dy * half))
    seen = set()
    for b in sorted(blocks, key=lambda b: b["dist"]):
        if 90 <= b["dist"] <= 600:
            key = (round(b["X"] / 90), round(b["Y"] / 90))     # one candidate per ~90 m cell (estate green / void deck)
            if key in seen:
                continue
            seen.add(key)
            cands.append(dict(id=f"blk-{b['blk']}", onsite=False, X=b["X"] + 15, Y=b["Y"] + 15))
    return cands


def exposure(cands, blocks, lam=None):
    """S_p = sum_b V_b * exp(-d_bp / lambda): vulnerable residents reached by cooling at p."""
    lam = lam or PEOPLE["lam"]
    B = np.array([[b["X"], b["Y"]] for b in blocks]); V = np.array([b["V"] for b in blocks])
    S, D = [], []
    for c in cands:
        d = np.hypot(B[:, 0] - c["X"], B[:, 1] - c["Y"])
        D.append(d); S.append(float((V * np.exp(-d / lam)).sum()))
    return np.array(S), np.array(D), V
