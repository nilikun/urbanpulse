"""Analyses on top of the scored blocks.

1. Benchmark   town ranking, inclusion gaps, and design targets taken from the best performers
2. Heat drivers which plannable features go with cooler surfaces (OLS with town fixed effects,
                town-clustered errors; gradient boosting with leave-one-town-out validation)
3. Heat history 1988-97 vs 2021-25 surface heat anomaly, by town and by block age
4. Value lens  hedonic model of HDB resale prices (2024 onwards) on greening/cooling indicators;
                kept outside the score so seniors' homes are never marked down
5. Robustness  stakeholder weight lenses (AHP), Dirichlet weight Monte Carlo, heat-penalty alpha
Usage: python -m uri.analysis
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold

from .index import INDICATORS, WEIGHTS, Scorer, inclusion_gap, focal_mean, sample, SAT

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
PILLARS = list(WEIGHTS)
rng = np.random.default_rng(20261011)

# Saaty pairwise judgements (row vs column) per stakeholder lens; order = PILLARS
AHP_LENS = {
    "Balanced (brief default)": None,
    "Senior / resident": [[1, 1, 3, 2, 1, 4], [1, 1, 3, 2, 1, 4], [1/3, 1/3, 1, 1/2, 1/3, 2],
                          [1/2, 1/2, 2, 1, 1/2, 3], [1, 1, 3, 2, 1, 4], [1/4, 1/4, 1/2, 1/3, 1/4, 1]],
    "Planner": [[1, 2, 1, 3, 2, 1], [1/2, 1, 1/2, 2, 1, 1/2], [1, 2, 1, 3, 2, 1],
                [1/3, 1/2, 1/3, 1, 1/2, 1/3], [1/2, 1, 1/2, 2, 1, 1/2], [1, 2, 1, 3, 2, 1]],
    "Developer / lender": [[1, 1/2, 2, 1/2, 2, 1], [2, 1, 3, 1, 3, 2], [1/2, 1/3, 1, 1/3, 1, 1/2],
                           [2, 1, 3, 1, 3, 2], [1/2, 1/3, 1, 1/3, 1, 1/2], [1, 1/2, 2, 1/2, 2, 1]],
}


def ahp(M):
    M = np.asarray(M, float)
    w, v = np.linalg.eig(M)
    i = np.argmax(w.real)
    wt = np.abs(v[:, i].real); wt /= wt.sum()
    cr = ((w[i].real - len(M)) / (len(M) - 1)) / 1.24
    return wt, float(cr)


def town_scores(b, scored, w):
    tot = sum(w.values())
    s = sum(w[p] * scored[p] for p in PILLARS) / tot
    return pd.Series(np.bincount(b.town_id, weights=s * b.need) / np.bincount(b.town_id, weights=b.need),
                     index=b.town_cat.cat.categories)


# ----------------------------------------------------------------------------- 1. benchmark
PLANNABLE = ["canopy200", "route_shade400", "park_walk", "park_area800", "gardens400", "walk_aac", "walk_clinic",
             "walk_hawker", "walk_mrt", "walk_bus"]


def benchmark(b, towns):
    out = {"towns": towns.round(3).to_dict("records")}
    targets = []
    for k in PLANNABLE:
        ind = next(i for i in INDICATORS if i.key == k)
        by_town = b.groupby("town")[k].median()
        best = by_town.sort_values(ascending=not ind.higher_is_better).head(5)
        targets.append(dict(key=k, label=ind.label, unit=ind.unit, higher_is_better=ind.higher_is_better,
                            island_median=float(b[k].median()), target=float(best.median()),
                            best_towns=list(best.index)))
    out["design_targets"] = targets
    out["island_gap"] = inclusion_gap(b.score)
    return out


# ----------------------------------------------------------------------------- 2. heat drivers
def heat_features(b):
    land10 = np.load(SAT / "landmask_10m.npy")
    ndvi = np.nan_to_num(np.load(SAT / "s2_2024_2025.npz")["ndvi"])
    imperv = np.where(land10, (ndvi < 0.2).astype("float32"), np.nan)
    X = pd.DataFrame(index=b.index)
    X["canopy200"] = b.canopy200
    X["impervious100"] = 100 * sample(focal_mean(imperv, 100, 10), b.geometry.x, b.geometry.y, 10)
    X["park_area800"] = b.park_area800
    X["blue_dist"] = b.blue_dist / 100
    X["floors"] = b.floors
    X["year_built"] = b.year
    xy = np.c_[b.geometry.x, b.geometry.y]
    nb = cKDTree(xy).query_ball_point(xy, 200)
    X["hdb_footprint200"] = [100 * b.footprint_m2.values[i].sum() / (np.pi * 200 ** 2) for i in nb]   # % of the 200 m disk
    return X


def heat_drivers(b):
    X = heat_features(b)
    df = pd.concat([X, b[["lst_anom", "town"]]], axis=1).dropna()
    z = df.copy()
    feats = list(X.columns)
    for c in feats:
        z[c] = (df[c] - df[c].mean()) / df[c].std()
    ols = smf.ols("lst_anom ~ " + " + ".join(feats) + " + C(town)", data=z).fit(cov_type="cluster", cov_kwds={"groups": z.town})
    raw = smf.ols("lst_anom ~ " + " + ".join(feats) + " + C(town)", data=df).fit(cov_type="cluster", cov_kwds={"groups": df.town})
    coef = [dict(feature=f, beta_std=float(ols.params[f]), ci_lo=float(ols.conf_int().loc[f, 0]),
                 ci_hi=float(ols.conf_int().loc[f, 1]), p=float(ols.pvalues[f]), per_unit=float(raw.params[f])) for f in feats]
    # gradient boosting with leave-one-town-out validation (spatial generalisation to an unseen town)
    groups = df.town.astype("category").cat.codes.values
    preds = np.full(len(df), np.nan)
    gkf = GroupKFold(n_splits=df.town.nunique())
    grid = np.linspace(df.canopy200.quantile(0.02), df.canopy200.quantile(0.98), 25)
    pdp_folds = []
    for tr, te in gkf.split(df[feats], df.lst_anom, groups):
        m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, random_state=0)
        m.fit(df[feats].iloc[tr], df.lst_anom.iloc[tr])
        preds[te] = m.predict(df[feats].iloc[te])
        sub = df[feats].sample(min(3000, len(df)), random_state=0)
        curve = []
        for g in grid:
            d2 = sub.copy(); d2["canopy200"] = g
            curve.append(float(m.predict(d2).mean()))
        pdp_folds.append(np.array(curve) - curve[0])      # change relative to the lowest canopy level
    r2_loto = 1 - np.sum((df.lst_anom - preds) ** 2) / np.sum((df.lst_anom - df.lst_anom.mean()) ** 2)
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, random_state=0).fit(df[feats], df.lst_anom)
    pi = permutation_importance(m, df[feats], df.lst_anom, n_repeats=10, random_state=0)
    imp = [dict(feature=f, importance=float(pi.importances_mean[i]), sd=float(pi.importances_std[i])) for i, f in enumerate(feats)]
    P = np.array(pdp_folds)
    pdp = dict(x=grid.tolist(), y=np.median(P, 0).tolist(), lo=np.percentile(P, 5, 0).tolist(), hi=np.percentile(P, 95, 0).tolist(),
               q25=np.percentile(P, 25, 0).tolist(), q75=np.percentile(P, 75, 0).tolist(), n_models=len(P))
    ci50 = ols.conf_int(alpha=0.5)
    for c in coef:
        c["ci50_lo"], c["ci50_hi"] = float(ci50.loc[c["feature"], 0]), float(ci50.loc[c["feature"], 1])
    return dict(n=len(df), ols_r2=float(ols.rsquared), coef=coef, gbm_r2_leave_one_town_out=float(r2_loto),
                importance=imp, pdp_canopy=pdp,
                canopy_10pp_effect_c=float(raw.params["canopy200"] * 10))


# ----------------------------------------------------------------------------- 3. heat history
def heat_history(b):
    d = b.assign(change=b.lst_anom - b.lst_anom_1990s).dropna(subset=["change"])
    d["era"] = pd.cut(d.year, [0, 1979, 1989, 1997, 2009, 2100], labels=["<1980", "1980s", "1990-97", "1998-2009", "2010+"])
    by_era = d.groupby("era", observed=True).change.agg(["mean", "median", "count"]).reset_index()
    by_town = d.groupby("town").agg(then=("lst_anom_1990s", "mean"), now=("lst_anom", "mean"), change=("change", "mean"),
                                    median_year=("year", "median"), blocks=("change", "size")).reset_index()
    rho, p = stats.spearmanr(d.year, d.change)
    return dict(by_era=by_era.round(3).to_dict("records"), by_town=by_town.round(3).to_dict("records"),
                spearman_year_change=float(rho), p=float(p),
                note="Anomalies are relative to each scene's island median, so they show where heat moved, not absolute warming.")


# ----------------------------------------------------------------------------- 4. value lens
def value_lens(b):
    r = pd.read_csv(RAW / "resale_2017on.csv")
    r = r[r.month >= "2024-01"].copy()
    r["block_id"] = r.block.str.upper() + "|" + r.street_name
    keep = ["block_id", "canopy200", "lst_anom", "park_walk", "walk_mrt", "walk_hawker", "blue_dist", "town"]
    r = r.merge(b[keep], on="block_id", how="inner", suffixes=("", "_b"))
    lo = r.storey_range.str[:2].astype(int); hi = r.storey_range.str[-2:].astype(int)
    r["storey"] = (lo + hi) / 2
    yrs = r.remaining_lease.str.extract(r"(\d+) years")[0].astype(float)
    mos = r.remaining_lease.str.extract(r"(\d+) month")[0].astype(float).fillna(0)
    r["lease"] = yrs + mos / 12
    r["lp"] = np.log(r.resale_price)
    r["canopy10"] = r.canopy200 / 10
    r["mrt100"] = r.walk_mrt / 100; r["hawker100"] = r.walk_hawker / 100; r["park100"] = r.park_walk / 100
    f = ("lp ~ np.log(floor_area_sqm) + storey + lease + I(lease**2) + C(flat_type) + C(flat_model) + C(month) + C(town)"
         " + canopy10 + lst_anom + park100 + mrt100 + hawker100")
    m = smf.ols(f, data=r).fit(cov_type="cluster", cov_kwds={"groups": r.block_id})
    ci95, ci50 = m.conf_int(), m.conf_int(alpha=0.5)
    tr = lambda v: float(100 * (np.exp(v) - 1))
    pct = lambda c: dict(pct=tr(m.params[c]), lo=tr(ci95.loc[c, 0]), hi=tr(ci95.loc[c, 1]),
                         lo50=tr(ci50.loc[c, 0]), hi50=tr(ci50.loc[c, 1]), p=float(m.pvalues[c]))
    return dict(n=int(m.nobs), blocks=int(r.block_id.nunique()), r2=float(m.rsquared), period=f"{r.month.min()} to {r.month.max()}",
                median_price=float(r.resale_price.median()),
                effects={"+10 pp canopy within 200 m": pct("canopy10"), "+1 degC surface heat": pct("lst_anom"),
                         "+100 m walk to park": pct("park100"), "+100 m walk to MRT": pct("mrt100"),
                         "+100 m walk to hawker centre": pct("hawker100")},
                caveat="Associations within town and month, controlling for flat attributes; not causal estimates.")


# ----------------------------------------------------------------------------- 5. robustness
def robustness(b, n_mc=2000):
    sc = Scorer(b[[i.key for i in INDICATORS]])
    scored = sc.score(b)
    b = b.copy()
    b["town_cat"] = b.town.astype("category"); b["town_id"] = b.town_cat.cat.codes
    lenses, ranks = {}, {}
    for name, M in AHP_LENS.items():
        if M is None:
            w, cr = np.array([WEIGHTS[p] for p in PILLARS], float) / 100, 0.0
        else:
            w, cr = ahp(M)
        ts = town_scores(b, scored, dict(zip(PILLARS, w)))
        lenses[name] = dict(weights=dict(zip(PILLARS, w.round(3).tolist())), cr=round(cr, 4))
        ranks[name] = ts.rank(ascending=False)
    base = ranks["Balanced (brief default)"]
    for name in lenses:
        lenses[name]["spearman_vs_default"] = float(stats.spearmanr(base, ranks[name])[0])
        lenses[name]["top5"] = list(ranks[name].sort_values().index[:5])
    w0 = np.array([WEIGHTS[p] for p in PILLARS], float) / 100
    draws = rng.dirichlet(w0 * 40, n_mc)
    S = np.array([town_scores(b, scored, dict(zip(PILLARS, w))).values for w in draws])
    R = np.array([pd.Series(row).rank(ascending=False).values for row in S])
    names = b.town_cat.cat.categories
    mc = {t: dict(p5=float(np.percentile(R[:, i], 5)), p50=float(np.median(R[:, i])), p95=float(np.percentile(R[:, i], 95)),
                  s5=float(np.percentile(S[:, i], 5)), s25=float(np.percentile(S[:, i], 25)), s50=float(np.median(S[:, i])),
                  s75=float(np.percentile(S[:, i], 75)), s95=float(np.percentile(S[:, i], 95)))
          for i, t in enumerate(names)}
    return dict(lenses=lenses, weight_mc=mc, mc_draws=n_mc, dirichlet_concentration=40)


def alpha_sensitivity(b, alphas=(0.0, 1.0)):
    """Recompute the five access walks with a different heat penalty and re-score."""
    from .network import Network
    from .index import load_points
    net = Network()
    bx, by = b.geometry.x.values, b.geometry.y.values
    ref = b[[i.key for i in INDICATORS]]
    base = Scorer(ref).score(ref)
    out = {}
    for a in alphas:
        G = net.set_alpha(a)
        alt = ref.copy()
        for key, f in [("walk_aac", "eldercare.geojson"), ("walk_clinic", "chas_clinics.geojson"),
                       ("walk_hawker", "hawker_centres.geojson"), ("walk_mrt", "mrt_exits.geojson"), ("walk_bus", "bus_stops.geojson")]:
            p = load_points(f)
            alt[key] = net.dist_to_nearest(p[:, 0], p[:, 1], bx, by, G=G)
        s = Scorer(alt).score(alt)
        tb = pd.DataFrame(dict(town=b.town, need=b.need, s0=base.score, s1=s.score))
        t = tb.groupby("town").apply(lambda g: pd.Series(dict(s0=np.average(g.s0, weights=g.need), s1=np.average(g.s1, weights=g.need))))
        out[str(a)] = dict(block_spearman=float(stats.spearmanr(base.score, s.score)[0]),
                           town_spearman=float(stats.spearmanr(t.s0, t.s1)[0]),
                           max_town_shift=float((t.s1 - t.s0).abs().max()))
    return out


def run():
    b = gpd.read_file(PROC / "blocks_scored.gpkg")
    towns = pd.read_csv(PROC / "towns.csv")
    res = dict(benchmark=benchmark(b, towns))
    res["heat_drivers"] = heat_drivers(b); print("heat drivers:", {k: v for k, v in res["heat_drivers"].items() if k in ("n", "ols_r2", "gbm_r2_leave_one_town_out", "canopy_10pp_effect_c")})
    res["heat_history"] = heat_history(b); print("heat history by era:", res["heat_history"]["by_era"])
    res["value_lens"] = value_lens(b); print("value lens:", json.dumps(res["value_lens"]["effects"], indent=0))
    res["robustness"] = robustness(b); print("lenses:", {k: (v["spearman_vs_default"], v["top5"]) for k, v in res["robustness"]["lenses"].items()})
    res["alpha_sensitivity"] = alpha_sensitivity(b); print("alpha:", res["alpha_sensitivity"])
    (PROC / "analysis.json").write_text(json.dumps(res, indent=1, default=float))
    return res


if __name__ == "__main__":
    run()
