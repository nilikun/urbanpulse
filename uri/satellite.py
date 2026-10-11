"""Satellite layers on a common SVY21 (EPSG:3414) grid.

1. Land surface temperature (LST), Landsat Collection 2 Level-2 surface temperature
   - "now":  Landsat 8/9, 2021-2025      - "then": Landsat 5, 1988-1997
   Every scene is cloud-masked with QA_PIXEL, then expressed as an anomaly against that scene's
   island-wide land median, so scenes from different days and seasons can be combined. The
   composite is the per-pixel median anomaly ("degC hotter than a typical Singapore surface at
   ~10:30 local time"), plus the per-pixel median absolute LST for reference.
2. Sentinel-2 L2A (2024-2025): cloud-masked median of B02/B03/B04/B08 -> true colour + NDVI.

Data: USGS Landsat and Copernicus Sentinel-2, read from the Microsoft Planetary Computer.
Usage: python -m uri.satellite
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

ROOT = Path(__file__).resolve().parents[1]
SAT = ROOT / "data" / "satellite"
CACHE = SAT / "scenes"
CRS = "EPSG:3414"
X0, X1, Y0, Y1 = 2_000, 56_000, 20_000, 52_000          # Singapore main island + Ubin/Tekong
BBOX_LL = [103.6, 1.2, 104.1, 1.49]
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def grid(res):
    w, h = int((X1 - X0) / res), int((Y1 - Y0) / res)
    return from_origin(X0, Y1, res, res), w, h


def read(href, res, resampling=Resampling.bilinear):
    tr, w, h = grid(res)
    with rasterio.open(href) as src, WarpedVRT(src, crs=CRS, transform=tr, width=w, height=h,
                                               resampling=resampling, src_nodata=0, nodata=0) as v:
        return v.read(1)


def catalog():
    return pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)


# ----------------------------------------------------------------------------- Landsat LST
QA_BAD = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 7)   # dilated cloud, cirrus, cloud, shadow, snow, water
# Thermal band calibration constants (USGS MTL files): K1 [W m-2 sr-1 um-1], K2 [K]
K = {"landsat-8": (774.8853, 1321.0789), "landsat-9": (799.0284, 1329.2405), "landsat-5": (607.76, 1260.56)}
EPS_SOIL, EPS_VEG = 0.97, 0.99          # NDVI-threshold emissivity (Sobrino et al. 2004)


def lst_scene(item, res=30):
    """Single-channel LST from the L2 thermal radiance and atmospheric layers.

    The official ST band is empty wherever ASTER GED emissivity is missing (in Singapore: large
    parts of Sengkang, Punggol and Yishun, in every scene). We therefore invert the radiative
    transfer equation ourselves for every pixel, with NDVI-threshold emissivity:
        TRAD = ATRAN * eps * B(Ts) + ATRAN * (1 - eps) * DRAD + URAD
        Ts   = K2 / ln(K1 / B + 1)
    The official ST value is kept alongside for validation where it exists."""
    out = CACHE / f"{item.id}_sc.npz"
    if out.exists():
        return out
    A = item.assets
    rd = lambda k, rs=Resampling.bilinear: read(A[k].href, res, rs).astype("float32")
    qa = read(A["qa_pixel"].href, res, Resampling.nearest)
    trad, atran, urad, drad = rd("trad") * 1e-3, rd("atran") * 1e-4, rd("urad") * 1e-3, rd("drad") * 1e-3
    red, nir = rd("red") * 2.75e-5 - 0.2, rd("nir08") * 2.75e-5 - 0.2
    st_off = rd("lwir11" if "lwir11" in A else "lwir")
    ndvi = (nir - red) / (nir + red + 1e-6)
    pv = np.clip((ndvi - 0.2) / 0.3, 0, 1) ** 2
    eps = EPS_VEG * pv + EPS_SOIL * (1 - pv)
    B = (trad - urad - atran * (1 - eps) * drad) / np.maximum(atran * eps, 1e-3)
    k1, k2 = K[item.properties["platform"]]
    with np.errstate(invalid="ignore", divide="ignore"):
        ts = k2 / np.log(k1 / B + 1) - 273.15
    valid = (trad > 0) & (atran > 0) & ((qa & QA_BAD) == 0) & (qa > 1) & np.isfinite(ts)
    lst = np.where(valid, ts, np.nan).astype("float32")
    lst[(lst < 15) | (lst > 65)] = np.nan
    off = np.where(valid & (st_off > 0), st_off * 0.00341802 + 149.0 - 273.15, np.nan).astype("float32")
    np.savez_compressed(out, lst=lst, official=off)
    return out


def lst_composite(tag, datetime, platforms, max_cloud=40, min_valid=0.25):
    items = list(catalog().search(collections=["landsat-c2-l2"], bbox=BBOX_LL, datetime=datetime,
                                  query={"platform": {"in": platforms}, "eo:cloud_cover": {"lt": max_cloud}}).items())
    print(tag, "scenes found:", len(items), flush=True)
    with ThreadPoolExecutor(6) as ex:
        paths = list(ex.map(lst_scene, items))
    land = np.load(SAT / "landmask_30m.npy")
    anoms, absol, used, diffs = [], [], [], []
    for it, p in zip(items, paths):
        z = np.load(p)
        lst, off = z["lst"], z["official"]
        both = land & np.isfinite(lst) & np.isfinite(off)
        if both.sum() > 1000:
            diffs.append((lst - off)[both][::50])
        lst[~land] = np.nan
        frac = np.isfinite(lst).sum() / land.sum()
        if frac < min_valid:
            continue
        med = np.nanmedian(lst)
        anoms.append(lst - med); absol.append(lst)
        used.append(dict(id=it.id, date=it.properties["datetime"][:10], valid_frac=round(float(frac), 3),
                         scene_median_c=round(float(med), 2)))
    A = np.stack(anoms)
    comp = dict(anom=np.nanmedian(A, 0).astype("float32"), abs=np.nanmedian(np.stack(absol), 0).astype("float32"),
                n=np.isfinite(A).sum(0).astype("int16"))
    np.savez_compressed(SAT / f"lst_{tag}.npz", **comp)
    (SAT / f"lst_{tag}_scenes.json").write_text(json.dumps(used, indent=1))
    dd = np.concatenate(diffs)
    val = dict(n_pixels=int(dd.size), bias_c=round(float(dd.mean()), 3), rmse_c=round(float(np.sqrt((dd ** 2).mean())), 3),
               mae_c=round(float(np.abs(dd).mean()), 3))
    (SAT / f"lst_{tag}_validation.json").write_text(json.dumps(val, indent=1))
    print(tag, "single-channel vs official ST:", val, flush=True)
    print(tag, "scenes used:", len(used), "median obs/pixel:", int(np.median(comp["n"][land])), flush=True)
    return comp


# ----------------------------------------------------------------------------- Sentinel-2
S2_BANDS = ["B02", "B03", "B04", "B08"]
SCL_OK = {4, 5, 6, 7, 11}        # vegetation, bare, water, unclassified, snow (no snow in SG); drops cloud/shadow/cirrus


def s2_scene(item, res=10):
    out = CACHE / f"{item.id}.npz"
    if out.exists():
        return out
    scl = read(item.assets["SCL"].href, res, Resampling.nearest)
    ok = np.isin(scl, list(SCL_OK))
    arr = {}
    for b in S2_BANDS:
        v = read(item.assets[b].href, res).astype("float32")
        arr[b] = np.where(ok & (v > 0), (v - 1000) / 10000.0, np.nan).astype("float32")   # L2A BOA offset since baseline 04.00
    np.savez_compressed(out, **arr)
    return out


def s2_composite():
    items = list(catalog().search(collections=["sentinel-2-l2a"], bbox=BBOX_LL, datetime="2024-01-01/2025-12-31",
                                  query={"eo:cloud_cover": {"lt": 20}, "s2:mgrs_tile": {"eq": "48NUG"}}).items())
    print("S2 scenes:", len(items), flush=True)
    with ThreadPoolExecutor(3) as ex:
        paths = list(ex.map(s2_scene, items))
    comp = {}
    for b in S2_BANDS:
        comp[b] = np.nanmedian(np.stack([np.load(p)[b] for p in paths]), 0).astype("float32")
    ndvi = (comp["B08"] - comp["B04"]) / (comp["B08"] + comp["B04"] + 1e-6)
    np.savez_compressed(SAT / "s2_2024_2025.npz", ndvi=ndvi.astype("float32"),
                        rgb=np.stack([comp["B04"], comp["B03"], comp["B02"]]).astype("float32"))
    (SAT / "s2_scenes.json").write_text(json.dumps([dict(id=i.id, date=i.properties["datetime"][:10],
                                                         cloud=i.properties["eo:cloud_cover"]) for i in items], indent=1))
    return ndvi


def landmask():
    """Land = inside the URA subzone polygons (no sea), rasterised to the 30 m and 10 m grids."""
    import geopandas as gpd
    from rasterio.features import rasterize
    sz = gpd.read_file(ROOT / "data" / "raw" / "subzones.geojson").to_crs(CRS)
    for res in (30, 10):
        tr, w, h = grid(res)
        m = rasterize(((g, 1) for g in sz.geometry), out_shape=(h, w), transform=tr).astype(bool)
        np.save(SAT / f"landmask_{res}m.npy", m)


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    if not (SAT / "landmask_30m.npy").exists():
        landmask()
    s2_composite()
    lst_composite("now", "2021-01-01/2025-12-31", ["landsat-8", "landsat-9"])
    lst_composite("then", "1988-01-01/1997-12-31", ["landsat-5"])
    tr, w, h = grid(30)
    (SAT / "grid.json").write_text(json.dumps(dict(crs=CRS, x0=X0, x1=X1, y0=Y0, y1=Y1,
                                                   lst_res=30, s2_res=10)))
