"""Paper figures for UrbanPulse (Nature-style: Arial, hairlines, lowercase bold panel letters).

Colour roles
  green  #1f7a52   the element this study adds (our design, our package, the lever we recommend)
  greys            context and baselines
  BrBG diverging   resilience scores (brown = less resilient, teal = more), colour-blind safe
  blue <-> red     surface heat (cooler <-> hotter), the remote-sensing convention
Uncertainty is drawn as interval bars: a wide light bar for the 95% interval and a narrow dark bar for
the 50% interval, with the point estimate on top. Output: figures/*.png|pdf.  Usage: python -m uri.figures
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
SAT, PROC, RAW, FIG = ROOT / "data" / "satellite", ROOT / "data" / "processed", ROOT / "data" / "raw", ROOT / "figures"
CASE = ROOT / "case_gls_site" / "results"
X0, X1, Y0, Y1 = 2_000, 56_000, 20_000, 52_000

HEAT = LinearSegmentedColormap.from_list("heat", ["#0d366b", "#256abf", "#86b6ef", "#f2f1ec", "#f6b1a8", "#e34948", "#9a1d22"])
SCORE = LinearSegmentedColormap.from_list("score", ["#8c510a", "#d8b365", "#f2f1ec", "#7fc8b8", "#01665e"])
INK, INK2, MUTED, GRID, BASE = "#111a15", "#4a524d", "#8a918c", "#e3e8e4", "#c4ccc6"
GREEN, GREEN_L, GREEN_XL = "#1f7a52", "#8cc9a8", "#dcefe4"
GREY, GREY_L, GREY_XL = "#7d8580", "#c4cbc6", "#e9ece9"
PILLAR_N = {"heat": "Heat", "shade": "Shade", "green": "Green-blue", "community": "Community", "access": "Access", "flood": "Flood"}
TYPE_C = {"green_pocket": GREEN, "rooftop_farm": "#b5527f", "shade_walkway": "#2a78d6"}

plt.rcParams.update({
    "font.family": "Arial", "font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5, "axes.edgecolor": BASE, "axes.linewidth": 0.5, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2, "ytick.major.size": 0, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "legend.frameon": False, "legend.fontsize": 6.3, "savefig.dpi": 300, "pdf.fonttype": 42,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlecolor": INK,
})
MM = 1 / 25.4


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", name)


def letter(ax, s, title=""):
    ax.set_title(f"{s}  {title}" if title else s, loc="left", fontsize=7.5, pad=5)


def interval(ax, y, lo95, hi95, lo50, hi50, mid, color, light, h95=0.42, h50=0.42, ms=17, horizontal=True):
    """Wide light bar = 95% interval, dark bar = 50% interval, white-ringed point = estimate."""
    ax.barh(y, hi95 - lo95, left=lo95, height=h95, color=light, lw=0, zorder=2)
    ax.barh(y, hi50 - lo50, left=lo50, height=h50 * 0.45, color=color, lw=0, zorder=3)
    ax.scatter(mid, y, s=ms, color="white", edgecolor=color, lw=1.2, zorder=4)


def outlines():
    sz = gpd.read_file(RAW / "subzones.geojson").to_crs(3414)
    return sz.union_all(), sz.dissolve(by="PLN_AREA_N")


def mapframe(ax, land, pa=None, xlim=(X0, X1 - 2000), ylim=(Y0 + 4000, Y1 - 2500)):
    gpd.GeoSeries([land]).plot(ax=ax, color="#eef1ee", edgecolor="none", zorder=0)
    if pa is not None:
        pa.boundary.plot(ax=ax, color="white", lw=0.35, zorder=3)
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal"); ax.axis("off")


def scalebar(ax, x, y, km=5):
    ax.plot([x, x + km * 1000], [y, y], color=INK, lw=1.0, solid_capstyle="butt")
    ax.text(x + km * 500, y + 450, f"{km} km", ha="center", va="bottom", fontsize=6, color=INK)


def raster(ax, arr, cmap, norm, land):
    ax.imshow(np.where(land, arr, np.nan), extent=(X0, X1, Y0, Y1), cmap=cmap, norm=norm, interpolation="nearest", zorder=1)


def xgrid(ax):
    ax.grid(axis="x", color=GRID, lw=0.4, zorder=0)


# ----------------------------------------------------------------------------- Fig 1 heat
def fig_heat(b, an):
    land, pa = outlines()
    land30 = np.load(SAT / "landmask_30m.npy")
    now, then = np.load(SAT / "lst_now.npz"), np.load(SAT / "lst_then.npz")
    fig = plt.figure(figsize=(180 * MM, 136 * MM))
    top = fig.add_gridspec(1, 2, left=0.0, right=1.0, top=0.98, bottom=0.56, wspace=0.04)
    gs = fig.add_gridspec(1, 3, left=0.1, right=0.99, top=0.42, bottom=0.08, width_ratios=[0.9, 1.1, 0.85], wspace=0.6)
    norm = TwoSlopeNorm(0, -6, 6)
    for k, (arr, t) in enumerate([(now["anom"], "Surface heat, 2021–25 (Landsat 8/9, 52 scenes)"),
                                  (now["anom"] - then["anom"], "Change since 1988–97 (Landsat 5, 37 scenes)")]):
        ax = fig.add_subplot(top[0, k]); mapframe(ax, land, pa); raster(ax, arr, HEAT, norm, land30)
        letter(ax, "ab"[k], t)
        if k == 0:
            scalebar(ax, 6000, 26000)
    cax = fig.add_axes([0.40, 0.535, 0.2, 0.009])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=HEAT), cax=cax, orientation="horizontal")
    cb.set_label("°C vs island median (cooler ← → hotter)", fontsize=6); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=5.5, length=0)

    # c: change by build era, interval style
    hh = pd.DataFrame(an["heat_history"]["by_era"])
    ax = fig.add_subplot(gs[0, 0]); letter(ax, "c", "Change by block build era")
    d = b.assign(change=b.lst_anom - b.lst_anom_1990s).dropna(subset=["change"])
    d["era"] = pd.cut(d.year, [0, 1979, 1989, 1997, 2009, 2100], labels=hh.era.tolist())
    for i, e in enumerate(hh.era):
        v = d.loc[d.era == e, "change"].values
        q = np.percentile(v, [5, 25, 50, 75, 95])
        hot = q[2] > 0.5
        interval(ax, i, q[0], q[4], q[1], q[3], q[2], "#c0392b" if hot else GREY, "#f6d3cc" if hot else GREY_XL)
    ax.axvline(0, color=BASE, lw=0.6, zorder=1)
    ax.set_yticks(range(len(hh)), [f"{e}\n(n={n:,})" for e, n in zip(hh.era, hh["count"])], fontsize=5.8)
    ax.invert_yaxis(); xgrid(ax); ax.set_xlabel("Δ surface-heat anomaly (°C)")

    # d: heat drivers, forest plot
    hd = an["heat_drivers"]
    coef = pd.DataFrame(hd["coef"]).sort_values("beta_std")
    names = {"canopy200": "Tree canopy ≤200 m", "impervious100": "Impervious ≤100 m", "park_area800": "Park area ≤800 m",
             "blue_dist": "Distance to water", "floors": "Block height", "year_built": "Year built",
             "hdb_footprint200": "HDB footprint ≤200 m"}
    ax = fig.add_subplot(gs[0, 1]); letter(ax, "d", f"Heat drivers (OLS, town FE, n = {hd['n']:,})")
    for i, r in enumerate(coef.itertuples()):
        lead = r.feature == "canopy200"
        interval(ax, i, r.ci_lo, r.ci_hi, r.ci50_lo, r.ci50_hi, r.beta_std, GREEN if lead else GREY, GREEN_XL if lead else GREY_XL, h95=0.5)
    ax.axvline(0, color=BASE, lw=0.6, zorder=1)
    ax.set_yticks(range(len(coef)), [names[f] for f in coef.feature], fontsize=5.8)
    for t, f in zip(ax.get_yticklabels(), coef.feature):
        if f == "canopy200":
            t.set_color(GREEN); t.set_fontweight("bold")
    xgrid(ax); ax.set_xlabel("°C per 1 s.d.  (bars: 95% and 50% CI, town-clustered)")
    ax.text(0.0, -0.24, f"R² = {hd['ols_r2']:.2f};  boosted trees, leave-one-town-out R² = {hd['gbm_r2_leave_one_town_out']:.2f}",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.6, color=INK2)

    # e: partial dependence with model band
    ax = fig.add_subplot(gs[0, 2]); letter(ax, "e", "More canopy, cooler blocks")
    p = hd["pdp_canopy"]
    ax.fill_between(p["x"], p["lo"], p["hi"], color=GREEN_XL, lw=0, label=f"5–95% across {p['n_models']} held-out-town models")
    ax.fill_between(p["x"], p["q25"], p["q75"], color=GREEN_L, lw=0, alpha=0.8, label="25–75%")
    ax.plot(p["x"], p["y"], color=GREEN, lw=1.6, label="median")
    ax.set_xlabel("Tree canopy within 200 m (%)"); ax.set_ylabel("Δ predicted surface heat (°C)")
    ax.spines["left"].set_visible(True); ax.tick_params(axis="y", length=2)
    ax.grid(axis="y", color=GRID, lw=0.4)
    ax.legend(loc="lower left", fontsize=5.3, handlelength=1.2)
    ax.text(0.97, 0.96, f"OLS: +10 pp ≈ {hd['canopy_10pp_effect_c']:.2f} °C", transform=ax.transAxes, ha="right", va="top", fontsize=5.8, color=GREEN)
    save(fig, "fig1_heat")


# ----------------------------------------------------------------------------- Fig 2 index
def fig_index(b, towns, an):
    land, pa = outlines()
    fig = plt.figure(figsize=(180 * MM, 132 * MM))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.3, 0.62, 0.5], height_ratios=[1, 0.78], hspace=0.36, wspace=0.42)
    ax = fig.add_subplot(gs[0, 0]); mapframe(ax, land, pa)
    norm = TwoSlopeNorm(50, 10, 90)
    o = b.sort_values("need")
    ax.scatter(o.geometry.x, o.geometry.y, c=o.score, cmap=SCORE, norm=norm, s=1.3, lw=0, zorder=4)
    letter(ax, "a", f"UrbanPulse index, {len(b):,} HDB blocks"); scalebar(ax, 6000, 26000)
    cax = fig.add_axes([0.13, 0.575, 0.18, 0.008])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SCORE), cax=cax, orientation="horizontal")
    cb.set_label("block score (less ← → more resilient)", fontsize=5.8); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=5.3, length=0)

    mc = an["robustness"]["weight_mc"]
    t = towns.sort_values("score")
    y = np.arange(len(t))
    ax = fig.add_subplot(gs[0, 1]); letter(ax, "b", "Town score")
    for i, r in enumerate(t.itertuples()):
        m = mc[r.town]
        interval(ax, i, m["s5"], m["s95"], m["s25"], m["s75"], r.score, "#01665e" if r.score >= 50 else "#8c510a",
                 "#cfe9e2" if r.score >= 50 else "#efe0c4", h95=0.7, ms=10)
    ax.axvline(50, color=BASE, lw=0.6, zorder=1)
    ax.set_yticks(y, t.town, fontsize=5.6); ax.set_xlim(25, 70); xgrid(ax)
    ax.set_xlabel("need-weighted; bars = 5–95% and\n25–75% over 2,000 weightings")
    ax2 = fig.add_subplot(gs[0, 2], sharey=ax); letter(ax2, "c", "Inclusion gap")
    top3 = set(t.nlargest(3, "inclusion_gap").town)
    ax2.hlines(y, 0, t.inclusion_gap, color=[GREEN if tw in top3 else GREY_L for tw in t.town], lw=1.4)
    ax2.scatter(t.inclusion_gap, y, s=12, color=[GREEN if tw in top3 else GREY for tw in t.town], zorder=3)
    for yy, g, tw in zip(y, t.inclusion_gap, t.town):
        if tw in top3:
            ax2.text(g + 0.8, yy, f"{g:.0f}", va="center", fontsize=5.6, color=GREEN, fontweight="bold")
    ax2.set_xlabel("median − worst 20%\n(points)"); plt.setp(ax2.get_yticklabels(), visible=False); xgrid(ax2); ax2.set_xlim(0, 28)

    ax = fig.add_subplot(gs[1, :]); letter(ax, "d", "Pillar profile by town (0–100; brief weights 25/20/15/15/15/10)")
    tt = towns.sort_values("score", ascending=False)
    M = tt[list(PILLAR_N)].values.T
    ax.imshow(M, cmap=SCORE, norm=norm, aspect="auto")
    ax.set_yticks(range(6), list(PILLAR_N.values())); ax.set_xticks(range(len(tt)), tt.town, rotation=55, ha="right", fontsize=5.6)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=4.6, color=INK if 22 < M[i, j] < 78 else "white")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "fig2_index")


# ----------------------------------------------------------------------------- Fig 3 tweaks
def fig_tweaks(tw, tb):
    land, pa = outlines()
    fig = plt.figure(figsize=(180 * MM, 78 * MM))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 0.8, 0.8], wspace=0.45, left=0.01, right=0.99, top=0.9, bottom=0.3)
    b = gpd.GeoDataFrame(tb, geometry=gpd.points_from_xy(tb.lon, tb.lat), crs=4326).to_crs(3414)
    ax = fig.add_subplot(gs[0]); mapframe(ax, land, pa, xlim=(b.geometry.x.min() - 500, b.geometry.x.max() + 500),
                                          ylim=(b.geometry.y.min() - 500, b.geometry.y.max() + 500))
    d = (b.score_after_inclusive - b.score_before).values
    norm = plt.Normalize(0, 4)
    cm = LinearSegmentedColormap.from_list("gain", ["#e6e9e6", GREEN_L, GREEN, "#0b4a30"])
    o = np.argsort(d)
    ax.scatter(b.geometry.x.values[o], b.geometry.y.values[o], c=d[o], cmap=cm, norm=norm, s=4, lw=0, zorder=4)
    w = b[b.worst20.astype(str) == "True"]
    ax.scatter(w.geometry.x, w.geometry.y, s=7, facecolor="none", edgecolor=INK, lw=0.3, zorder=5)
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 3414, always_xy=True)
    for c in tw["inclusion_aware"]["package"]:
        x, y = tf.transform(c["lon"], c["lat"])
        ax.scatter(x, y, marker="D" if c["type"] == "green_pocket" else "s", s=30, color=TYPE_C[c["type"]], edgecolor="white", lw=0.8, zorder=6)
    letter(ax, "a", "Woodlands: inclusion-aware package")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", ms=3.5, mfc="none", mec=INK, mew=0.4, label="Worst-served 20% of blocks today"),
                       Line2D([], [], marker="D", ls="", ms=4.5, mfc=TYPE_C["green_pocket"], mec="white", label="Green pocket (MP2025 reserve / open-space parcel)"),
                       Line2D([], [], marker="s", ls="", ms=4.5, mfc=TYPE_C["rooftop_farm"], mec="white", label="Community farm on car-park roof")],
              loc="upper left", bbox_to_anchor=(0, -0.02), fontsize=5.6)
    cax = fig.add_axes([0.30, 0.13, 0.12, 0.01])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax, orientation="horizontal")
    cb.set_label("block score gain", fontsize=5.6); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=5.2, length=0)

    base = tw["baseline"]
    rows = [("Town score\n(higher is better)", tw["average_first"]["final"]["score"] - base["score"], tw["inclusion_aware"]["final"]["score"] - base["score"]),
            ("Worst-served 20%\n(higher is better)", tw["average_first"]["worst20"] - tw["baseline_worst20"], tw["inclusion_aware"]["worst20"] - tw["baseline_worst20"]),
            ("Inclusion gap\n(lower is better)", tw["average_first"]["final"]["gap"] - base["gap"], tw["inclusion_aware"]["final"]["gap"] - base["gap"])]
    ax = fig.add_subplot(gs[1]); letter(ax, "b", "Six tweaks, two rankings")
    for i, (lab, a_, i_) in enumerate(rows):
        for off, v, c in ((-0.18, a_, GREY_L), (0.18, i_, GREEN)):
            ax.barh(i + off, v, height=0.3, color=c)
            ax.text(v + (0.06 if v >= 0 else -0.06), i + off, f"{v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=5.8,
                    color=GREEN if c == GREEN else INK2, fontweight="bold" if c == GREEN else "normal")
    ax.axvline(0, color=BASE, lw=0.6); ax.set_yticks(range(3), [r[0] for r in rows], fontsize=5.8); ax.invert_yaxis()
    ax.set_xlim(-0.9, 3.4); ax.set_xlabel("change vs today (points)"); xgrid(ax)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GREY_L, label="Average-first"),
                       plt.Rectangle((0, 0), 1, 1, color=GREEN, label="Inclusion-aware")], loc="upper left", bbox_to_anchor=(0, -0.2), fontsize=5.8, ncol=2)

    ax = fig.add_subplot(gs[2]); letter(ax, "c", "Who gains")
    q = tb.sort_values("score_before")
    for col, c, lab in (("score_after_average", GREY, "Average-first"), ("score_after_inclusive", GREEN, "Inclusion-aware")):
        g = (q[col] - q.score_before).rolling(120, center=True, min_periods=30)
        mean, sd = g.mean(), g.std()
        ax.fill_between(q.score_before, mean - sd / np.sqrt(120), mean + sd / np.sqrt(120), color=c, alpha=0.18, lw=0)
        ax.plot(q.score_before, mean, color=c, lw=1.4)
        ax.text(q.score_before.iloc[-60], mean.iloc[-60] + 0.18, lab, color=c, fontsize=5.8, ha="right", fontweight="bold" if c == GREEN else "normal")
    ax.axvspan(q.score_before.min(), q.score_before.quantile(0.2), color=GREY_XL, lw=0, zorder=0)
    ax.text(q.score_before.quantile(0.1), 0.04, "worst 20%", ha="center", va="bottom", fontsize=5.6, color=INK2, transform=ax.get_xaxis_transform())
    ax.set_xlabel("block score today"); ax.set_ylabel("mean score gain (rolling, ±1 s.e.)")
    ax.spines["left"].set_visible(True); ax.tick_params(axis="y", length=2); ax.grid(axis="y", color=GRID, lw=0.4)
    save(fig, "fig3_tweaks")


# ----------------------------------------------------------------------------- Fig 4 value + robustness
def fig_value_robust(an):
    fig, axs = plt.subplots(1, 2, figsize=(180 * MM, 74 * MM), gridspec_kw=dict(width_ratios=[1, 1.1], wspace=0.55))
    v = an["value_lens"]
    eff = pd.DataFrame([dict(k=k.replace("degC", "°C"), **e) for k, e in v["effects"].items()])
    ax = axs[0]; letter(ax, "a", f"Value lens: HDB resale {v['period']} (n = {v['n']:,})")
    for i, r in enumerate(eff.itertuples()):
        lead = "canopy" in r.k or "heat" in r.k
        interval(ax, i, r.lo, r.hi, r.lo50, r.hi50, r.pct, GREEN if lead else GREY, GREEN_XL if lead else GREY_XL, h95=0.5)
    ax.axvline(0, color=BASE, lw=0.6, zorder=1); ax.set_yticks(range(len(eff)), eff.k); ax.invert_yaxis(); xgrid(ax)
    ax.set_xlim(eff.lo.min() - 0.12, eff.hi.max() + 0.12)
    ax.set_xlabel("% change in resale price  (bars: 95% and 50% CI, block-clustered)")
    ax.text(0.0, -0.2, "Within town and month, controlling for flat type, model, size, storey and lease.\nAssociations, not causal effects.",
            transform=ax.transAxes, fontsize=5.6, color=INK2, va="top")
    rb = an["robustness"]["weight_mc"]
    df = pd.DataFrame([dict(town=t, **r) for t, r in rb.items()]).sort_values("p50")
    ax = axs[1]; letter(ax, "b", f"Rank stability under {an['robustness']['mc_draws']:,} random weightings")
    for i, r in enumerate(df.itertuples()):
        ax.barh(i, r.p95 - r.p5 + 0.6, left=r.p5 - 0.3, height=0.62, color=GREEN_XL, lw=0)
        ax.scatter(r.p50, i, s=10, color=GREEN, zorder=3)
    ax.set_yticks(range(len(df)), df.town, fontsize=5.6); ax.invert_yaxis(); xgrid(ax)
    ax.set_xlabel("town rank (median and 5–95% interval)")
    lens = an["robustness"]["lenses"]
    txt = ";  ".join(f"{k}: ρ = {x['spearman_vs_default']:.2f}" for k, x in lens.items() if not k.startswith("Balanced"))
    ax.text(0.0, -0.17, "Stakeholder weight lenses (AHP) vs default ranking: " + txt, transform=ax.transAxes, ha="left", va="top", fontsize=5.6, color=INK2)
    save(fig, "fig4_value_robustness")


# ----------------------------------------------------------------------------- Fig 5 developer case
def fig_case():
    opt = json.loads((CASE / "optimization.json").read_text()); an = json.loads((CASE / "analysis.json").read_text())
    D = opt["designs"]; names = ["Compliance-minimum", "Typical showcase", "Index-guided design"]
    short = ["Compliance\nminimum", "Typical\nshowcase", "Index-\nguided"]
    fig = plt.figure(figsize=(180 * MM, 118 * MM))
    top = fig.add_gridspec(1, 3, left=0.04, right=0.98, top=0.9, bottom=0.62, wspace=0.35)
    bot = fig.add_gridspec(1, 2, left=0.2, right=0.98, top=0.47, bottom=0.08, width_ratios=[1.1, 1], wspace=0.35)
    for k, (key, lab, scale, fmt) in enumerate([("lcc", "30-yr greenery life-cycle cost (S$M)", 1e6, "{:.2f}"),
                                                 ("fee_unit_month", "Greenery upkeep (S$ per unit per month)", 1, "{:.0f}"),
                                                 ("r200", "Seniors + rental households ≤200 m of a public cool refuge", 1, "{:,.0f}")]):
        ax = fig.add_subplot(top[0, k])
        vals = [D[n][key] / scale for n in names]
        ax.barh(range(3), vals, color=[GREY_L, GREY_L, GREEN], height=0.56)
        for i, vv in enumerate(vals):
            ax.text(vv + max(vals) * 0.02, i, fmt.format(vv), va="center", fontsize=6, color=GREEN if i == 2 else INK2,
                    fontweight="bold" if i == 2 else "normal")
        ax.set_yticks(range(3), [s_.replace("\n", " ") for s_ in short], fontsize=5.8); ax.invert_yaxis()
        ax.set_xticks([]); ax.spines["bottom"].set_visible(False); ax.set_xlim(0, max(vals) * 1.25)
        ax.set_title(lab, fontsize=6.3, fontweight="normal", color=INK2, loc="left")
    fig.text(0.04, 0.975, "a  Three landscape designs under identical URA greenery rules (GnPR 3.5)", fontsize=7.5, fontweight="bold", color=INK)

    z = np.load(CASE / "mc_samples.npz")
    rows = [("Typical showcase", "Typical_showcase", GREY), ("Compliance-minimum", "Compliance-minimum", GREY),
            ("Index-guided, unverified", "Index-guided_design_no_MRV", GREEN_L), ("Index-guided + verified, after fees", "Index-guided_design_plus_MRV", GREEN)]
    ax = fig.add_subplot(bot[0, 0]); letter(ax, "b", "30-year net value per site, 20,000 Monte Carlo draws")
    for i, (lab, key, c) in enumerate(rows):
        v = z[key] / 1e6
        q = np.percentile(v, [10, 25, 50, 75, 90])
        interval(ax, i, q[0], q[4], q[1], q[3], q[2], GREY if c == GREY else GREEN, GREY_XL if c == GREY else GREEN_XL, h95=0.6, ms=14)
        ax.text(q[4] + 0.25, i, f"median {q[2]:.1f}", va="center", fontsize=5.8, color=GREEN if c == GREEN else INK2,
                fontweight="bold" if c == GREEN else "normal")
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=6); ax.invert_yaxis(); ax.axvline(0, color=BASE, lw=0.6); xgrid(ax)
    ax.set_xlim(-4, 11); ax.set_xlabel("S$M  (bars: P10–P90 and P25–P75)")
    m = an["mc"]["uplift_vs_showcase"]
    ax.text(1.0, -0.2, f"Gain vs showcase: median +S${m['p50'] / 1e6:.1f}M, positive in {m['prob_positive']:.0%} of draws",
            transform=ax.transAxes, ha="right", va="top", fontsize=5.8, color=GREEN, fontweight="bold")

    f = pd.DataFrame(an["flywheel"])
    x = np.log1p(f.n)
    ax = fig.add_subplot(bot[0, 1]); letter(ax, "c", "Verification flywheel: each site de-risks the next")
    ax.fill_between(x, f.p10 / 1e6, f.p90 / 1e6, color=GREEN_XL, lw=0, label="P10–P90")
    ax.plot(x, f.p50 / 1e6, color=GREEN_L, lw=1.2, label="median")
    ax.plot(x, f.p10 / 1e6, color=GREEN, lw=1.8, label="bankable value (P10)")
    ax.axhline(0, color=BASE, lw=0.6)
    ticks = [0, 1, 2, 5, 10, 20, 50]
    ax.set_xticks(np.log1p(ticks), [str(t) for t in ticks])
    ax.set_xlabel("verified sites in the evidence library"); ax.set_ylabel("S$M per site, after fees")
    ax.spines["left"].set_visible(True); ax.tick_params(axis="y", length=2); ax.grid(axis="y", color=GRID, lw=0.4)
    ax.legend(loc="upper right", fontsize=5.4)
    p0, p8 = f.loc[f.n == 0, "p10"].iloc[0] / 1e6, f.loc[f.n == 8, "p10"].iloc[0] / 1e6
    ax.annotate(f"P10 {p0:+.1f} → {p8:+.1f} after 8 sites", xy=(np.log1p(8), p8), xytext=(np.log1p(0.4), 3.6), fontsize=5.8,
                color=GREEN, fontweight="bold", arrowprops=dict(arrowstyle="-", color=GREEN, lw=0.6))
    save(fig, "fig5_developer_case")


def run():
    b = gpd.read_file(PROC / "blocks_scored.gpkg")
    towns = pd.read_csv(PROC / "towns.csv")
    an = json.loads((PROC / "analysis.json").read_text())
    tw = json.loads((PROC / "tweaks_woodlands.json").read_text())
    tb = pd.read_csv(PROC / "tweaks_woodlands_blocks.csv")
    fig_heat(b, an); fig_index(b, towns, an); fig_tweaks(tw, tb); fig_value_robust(an); fig_case()


if __name__ == "__main__":
    run()
