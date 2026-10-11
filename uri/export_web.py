"""Export compact data and raster overlays for the website (web/data, web/assets/img/maps).

Rasters are drawn on the SVY21 grid and placed on the web map with their four corner coordinates.
Usage: python -m uri.export_web
"""
import json
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from pyproj import Transformer

from .index import INDICATORS, WEIGHTS, PILLAR_NAMES, CONTEXT

ROOT = Path(__file__).resolve().parents[1]
SAT, PROC = ROOT / "data" / "satellite", ROOT / "data" / "processed"
WEB = ROOT / "web"
DATA, MAPS = WEB / "data", WEB / "assets" / "img" / "maps"
X0, X1, Y0, Y1 = 2_000, 56_000, 20_000, 52_000
TO_LL = Transformer.from_crs(3414, 4326, always_xy=True)

# red <-> blue diverging, neutral grey midpoint (red = hotter / less resilient)
DIV = LinearSegmentedColormap.from_list("div", ["#0d366b", "#256abf", "#86b6ef", "#f0efec", "#f6b1a8", "#e34948", "#9a1d22"])
GRN = LinearSegmentedColormap.from_list("grn", ["#f0efec", "#bfe0c4", "#6fbf7c", "#2e9443", "#0b5d1e"])


def corners():
    xs, ys = [X0, X1, X1, X0], [Y1, Y1, Y0, Y0]                      # TL, TR, BR, BL
    lon, lat = TO_LL.transform(xs, ys)
    return [[round(a, 6), round(b, 6)] for a, b in zip(lon, lat)]


def rgba(arr, cmap, vmin, vmax, mask):
    v = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
    img = (cmap(np.nan_to_num(v, nan=0.5)) * 255).astype("uint8")
    img[..., 3] = np.where(mask & np.isfinite(arr), 235, 0)
    return Image.fromarray(img, "RGBA")


def rasters():
    MAPS.mkdir(parents=True, exist_ok=True)
    land30, land10 = np.load(SAT / "landmask_30m.npy"), np.load(SAT / "landmask_10m.npy")
    now, then = np.load(SAT / "lst_now.npz"), np.load(SAT / "lst_then.npz")
    rgba(now["anom"], DIV, -6, 6, land30).save(MAPS / "lst_2021_2025.png", optimize=True)
    rgba(then["anom"], DIV, -6, 6, land30).save(MAPS / "lst_1988_1997.png", optimize=True)
    rgba(now["anom"] - then["anom"], DIV, -6, 6, land30).save(MAPS / "lst_change.png", optimize=True)
    s2 = np.load(SAT / "s2_2024_2025.npz")
    ndvi = s2["ndvi"][::2, ::2]
    rgba(ndvi, GRN, 0.1, 0.85, land10[::2, ::2]).save(MAPS / "ndvi_2024_2025.png", optimize=True)
    rgb = np.moveaxis(s2["rgb"][:, ::2, ::2], 0, -1)
    rgb = np.clip(np.nan_to_num(rgb) / 0.20, 0, 1) ** (1 / 1.7)
    Image.fromarray((rgb * 255).astype("uint8")).save(MAPS / "s2_truecolor.jpg", quality=84, optimize=True)
    return dict(corners=corners(), lst_range=[-6, 6], ndvi_range=[0.1, 0.85])


def blocks():
    b = gpd.read_file(PROC / "blocks_scored.gpkg")
    lon, lat = TO_LL.transform(b.geometry.x.values, b.geometry.y.values)
    keys = [i.key for i in INDICATORS]
    rows = []
    for k, r in enumerate(b.itertuples()):
        p = [round(float(getattr(r, q)), 1) for q in WEIGHTS]
        rows.append([round(lon[k], 5), round(lat[k], 5), r.blk, r.street.title(), r.town, int(r.year), int(r.units),
                     int(r.rental), round(float(r.seniors)), round(float(r.need), 1), round(float(r.score), 1), *p,
                     *[round(float(getattr(r, q)), 1) for q in keys], round(float(r.wbgt_hours), 1),
                     round(float(r.lst_anom - r.lst_anom_1990s), 2) if np.isfinite(r.lst_anom_1990s) else None])
    cols = ["lon", "lat", "blk", "street", "town", "year", "units", "rental", "seniors", "need", "score", *WEIGHTS,
            *keys, "wbgt_hours", "lst_change"]
    (DATA / "blocks.json").write_text(json.dumps(dict(cols=cols, rows=rows), separators=(",", ":")))
    return len(rows)


def run():
    DATA.mkdir(parents=True, exist_ok=True)
    meta = json.loads((PROC / "index_meta.json").read_text())
    out = dict(rasters=rasters(), weights=WEIGHTS, pillars=PILLAR_NAMES,
               indicators=[dict(key=i.key, pillar=i.pillar, label=i.label, unit=i.unit, higher_is_better=i.higher_is_better,
                                source=i.source, confidence=i.confidence) for i in INDICATORS],
               context=CONTEXT, network=meta["network"], wbgt=meta["wbgt"],
               wbgt_vs_lst_spearman=meta["wbgt_vs_lst_spearman"], island_gap=meta["island_inclusion_gap"])
    for tag in ("now", "then"):
        out[f"lst_{tag}_validation"] = json.loads((SAT / f"lst_{tag}_validation.json").read_text())
        out[f"lst_{tag}_scenes"] = len(json.loads((SAT / f"lst_{tag}_scenes.json").read_text()))
    out["s2_scenes"] = json.loads((SAT / "s2_scenes.json").read_text())
    out["n_blocks"] = blocks()
    (DATA / "meta.json").write_text(json.dumps(out, indent=1, default=float))
    pd.read_csv(PROC / "towns.csv").round(3).to_json(DATA / "towns.json", orient="records")
    for f in ["analysis.json", "tweaks_woodlands.json", "tweaks_woodlands_blocks.csv"]:
        if (PROC / f).exists():
            shutil.copy(PROC / f, DATA / f)
    case = ROOT / "case_gls_site" / "results"
    opt = json.loads((case / "optimization.json").read_text())
    an = json.loads((case / "analysis.json").read_text())
    keep = ["npv", "premium", "sll", "lcc", "capex", "fee_unit_month", "gnpr", "lra_pct", "r200", "x", "z"]
    cdata = dict(designs={k: {q: v[q] for q in keep if q in v} for k, v in opt["designs"].items()},
                 frontier=[{q: f[q] for q in ("eq", "npv", "r200")} for f in opt["frontier"]],
                 cands=[dict(id=c["id"], onsite=c["onsite"], lonlat=TO_LL.transform(c["X"], c["Y"])) for c in opt["cands"]],
                 blocks=[dict(lonlat=TO_LL.transform(b["X"], b["Y"]), V=b["V"], units=b["units"]) for b in opt["blocks"]],
                 site=dict(lonlat=TO_LL.transform(opt["site"]["X"], opt["site"]["Y"]), area=opt["site"]["area"]),
                 mc=an["mc"], flywheel=an["flywheel"], sensitivity=an["sensitivity"], business=an["business"], fee_pv=an["fee_pv"])
    (DATA / "case.json").write_text(json.dumps(cdata, default=float))
    hero_and_compare()
    (WEB / "assets" / "img" / "figures").mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "figures").glob("fig*.png"):
        shutil.copy(f, WEB / "assets" / "img" / "figures" / f.name)
    print("exported", out["n_blocks"], "blocks; files:", sorted(p.name for p in DATA.iterdir()))



def hero_and_compare():
    """Dark hero map (surface heat + HDB blocks) and flattened 1990s / 2020s images for the compare slider."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm
    land30 = np.load(SAT / "landmask_30m.npy")
    now, then = np.load(SAT / "lst_now.npz"), np.load(SAT / "lst_then.npz")
    b = gpd.read_file(PROC / "blocks_scored.gpkg")
    norm = TwoSlopeNorm(0, -6, 6)
    # hero: 21:9, dark
    fig = plt.figure(figsize=(24, 11), facecolor="#07111f")
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#07111f")
    ax.imshow(np.where(land30, now["anom"], np.nan), extent=(X0, X1, Y0, Y1), cmap=DIV, norm=norm, alpha=0.92, interpolation="bilinear")
    ax.scatter(b.geometry.x, b.geometry.y, s=1.2, c="white", alpha=0.75, lw=0)
    ax.set_xlim(-9000, 62000); ax.set_ylim(20500, 53000); ax.set_aspect("equal"); ax.axis("off")
    fig.savefig(MAPS / "hero_heat.jpg", dpi=100, facecolor="#07111f", pil_kwargs=dict(quality=82, optimize=True))
    plt.close(fig)
    for tag, arr in (("1990s", then["anom"]), ("2020s", now["anom"])):
        fig = plt.figure(figsize=(18, 10.67), facecolor="#f4f3ef")
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_facecolor("#f4f3ef")
        ax.imshow(np.where(land30, arr, np.nan), extent=(X0, X1, Y0, Y1), cmap=DIV, norm=norm, interpolation="nearest")
        ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.axis("off")
        fig.savefig(MAPS / f"compare_{tag}.jpg", dpi=100, facecolor="#f4f3ef", pil_kwargs=dict(quality=84, optimize=True))
        plt.close(fig)
    im = Image.open(MAPS / "ndvi_2024_2025.png")
    im.quantize(colors=64, method=Image.Quantize.FASTOCTREE).save(MAPS / "ndvi_2024_2025.png", optimize=True)
    for f in ("lst_2021_2025.png", "lst_1988_1997.png", "lst_change.png"):
        Image.open(MAPS / f).quantize(colors=96, method=Image.Quantize.FASTOCTREE).save(MAPS / f, optimize=True)


if __name__ == "__main__":
    run()
