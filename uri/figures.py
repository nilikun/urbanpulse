"""Paper figures (Nature-style: Arial, hairlines, lowercase bold panel letters). Output: figures/*.png|pdf|svg

Colour roles: diverging red<->blue with a grey midpoint (red = hotter / less resilient), one accent
(orange) for the element the study adds, greys for context. Usage: python -m uri.figures
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

DIV = LinearSegmentedColormap.from_list("div", ["#0d366b", "#256abf", "#86b6ef", "#f0efec", "#f6b1a8", "#e34948", "#9a1d22"])
DIV_R = DIV.reversed()
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
ACCENT, BLUE, RED, GREY = "#eb6834", "#2a78d6", "#e34948", "#9a9890"
PILLAR_C = {"heat": "#eb6834", "shade": "#1baf7a", "green": "#008300", "community": "#e87ba4", "access": "#2a78d6", "flood": "#4a3aa7"}
PILLAR_N = {"heat": "Heat", "shade": "Shade", "green": "Green-blue", "community": "Community", "access": "Access", "flood": "Flood"}
TYPE_C = {"green_pocket": "#008300", "rooftop_farm": "#e87ba4", "shade_walkway": "#2a78d6"}
TYPE_N = {"green_pocket": "Green pocket", "rooftop_farm": "Rooftop farm", "shade_walkway": "Shaded walkway"}

plt.rcParams.update({
    "font.family": "Arial", "font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5, "axes.edgecolor": BASE, "axes.linewidth": 0.5, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "xtick.major.size": 2, "ytick.major.size": 2, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 6.5, "savefig.dpi": 300, "pdf.fonttype": 42, "svg.fonttype": "none",
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
    ax.set_title(f"{s}  {title}" if title else s, loc="left", fontsize=7.5, pad=4)


def outlines():
    sz = gpd.read_file(RAW / "subzones.geojson").to_crs(3414)
    pa = sz.dissolve(by="PLN_AREA_N")
    return sz.union_all(), pa


def mapframe(ax, land, pa=None, xlim=(X0, X1 - 2000), ylim=(Y0 + 4000, Y1 - 2500)):
    gpd.GeoSeries([land]).plot(ax=ax, color="#f4f3ef", edgecolor="none", zorder=0)
    if pa is not None:
        pa.boundary.plot(ax=ax, color="white", lw=0.35, zorder=3)
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal"); ax.axis("off")


def scalebar(ax, x, y, km=5):
    ax.plot([x, x + km * 1000], [y, y], color=INK, lw=1.2, solid_capstyle="butt")
    ax.text(x + km * 500, y + 500, f"{km} km", ha="center", va="bottom", fontsize=6, color=INK)


def raster(ax, arr, cmap, norm, land):
    ax.imshow(np.where(land, arr, np.nan), extent=(X0, X1, Y0, Y1), cmap=cmap, norm=norm, interpolation="nearest", zorder=1)


# ----------------------------------------------------------------------------- Fig 1 heat
def fig_heat(b, an):
    land, pa = outlines()
    land30 = np.load(SAT / "landmask_30m.npy")
    now, then = np.load(SAT / "lst_now.npz"), np.load(SAT / "lst_then.npz")
    fig = plt.figure(figsize=(180 * MM, 135 * MM))
    top = fig.add_gridspec(1, 2, left=0.0, right=1.0, top=0.98, bottom=0.56, wspace=0.04)
    gs = fig.add_gridspec(1, 3, left=0.1, right=0.99, top=0.42, bottom=0.08, width_ratios=[0.9, 1.1, 0.8], wspace=0.6)
    norm = TwoSlopeNorm(0, -6, 6)
    for k, (arr, t) in enumerate([(now["anom"], "Surface heat, 2021–25 (Landsat 8/9, 52 scenes)"),
                                  (now["anom"] - then["anom"], "Change since 1988–97 (Landsat 5, 37 scenes)")]):
        ax = fig.add_subplot(top[0, k]); mapframe(ax, land, pa); raster(ax, arr, DIV, norm, land30)
        letter(ax, "ab"[k], t)
        if k == 0:
            scalebar(ax, 6000, 26000)
    cax = fig.add_axes([0.40, 0.535, 0.2, 0.01])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=DIV), cax=cax, orientation="horizontal")
    cb.set_label("°C vs island median (cooler ← → hotter)", fontsize=6); cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=5.5)

    hh = pd.DataFrame(an["heat_history"]["by_era"])
    ax = fig.add_subplot(gs[0, 0]); letter(ax, "c", "Change by block build era")
    d = b.assign(change=b.lst_anom - b.lst_anom_1990s).dropna(subset=["change"])
    d["era"] = pd.cut(d.year, [0, 1979, 1989, 1997, 2009, 2100], labels=hh.era.tolist())
    data = [d.loc[d.era == e, "change"].values for e in hh.era]
    bp = ax.boxplot(data, orientation="horizontal", widths=0.55, showfliers=False, patch_artist=True,
                    medianprops=dict(color=INK, lw=1), whiskerprops=dict(color=MUTED, lw=0.6), capprops=dict(color=MUTED, lw=0.6))
    for patch, m in zip(bp["boxes"], hh["median"]):
        patch.set(facecolor=DIV(0.5 + np.clip(m, -2, 2) / 4 * 0.45), edgecolor="none")
    ax.axvline(0, color=BASE, lw=0.5, zorder=0)
    ax.set_yticks(range(1, len(hh) + 1), [f"{e}\n(n={n:,})" for e, n in zip(hh.era, hh["count"])], fontsize=5.8)
    ax.set_xlabel("Δ surface-heat anomaly (°C)"); ax.invert_yaxis()

    hd = an["heat_drivers"]
    coef = pd.DataFrame(hd["coef"]).sort_values("beta_std")
    names = {"canopy200": "Tree canopy ≤200 m", "impervious100": "Impervious ≤100 m", "park_area800": "Park area ≤800 m",
             "blue_dist": "Distance to water", "floors": "Block height", "year_built": "Year built",
             "hdb_footprint200": "HDB footprint ≤200 m"}
    ax = fig.add_subplot(gs[0, 1]); letter(ax, "d", f"Heat drivers (OLS, town FE, n = {hd['n']:,})")
    y = np.arange(len(coef))
    cols = [ACCENT if f == "canopy200" else GREY for f in coef.feature]
    ax.hlines(y, coef.ci_lo, coef.ci_hi, color=cols, lw=1.2)
    ax.scatter(coef.beta_std, y, s=18, color=cols, zorder=3, edgecolor="white", lw=0.6)
    ax.axvline(0, color=BASE, lw=0.5)
    ax.set_yticks(y, [names[f] for f in coef.feature], fontsize=5.8); ax.set_xlabel("°C per 1 s.d. (95% CI)")
    ax.text(0.0, -0.22, f"R² = {hd['ols_r2']:.2f}; boosted trees, leave-one-town-out R² = {hd['gbm_r2_leave_one_town_out']:.2f}",
            transform=ax.transAxes, ha="left", va="top", fontsize=5.6, color=INK2)

    ax = fig.add_subplot(gs[0, 2]); letter(ax, "e", "Canopy partial dependence")
    p = hd["pdp_canopy"]; ax.plot(p["x"], p["y"], color=ACCENT, lw=1.5)
    ax.set_xlabel("Tree canopy within 200 m (%)"); ax.set_ylabel("Predicted anomaly (°C)")
    ax.text(0.97, 0.95, f"+10 pp canopy ≈ {hd['canopy_10pp_effect_c']:.2f} °C\n(OLS, all else equal)", transform=ax.transAxes,
            ha="right", va="top", fontsize=5.6, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.4)
    save(fig, "fig1_heat")


# ----------------------------------------------------------------------------- Fig 2 index
def fig_index(b, towns):
    land, pa = outlines()
    fig = plt.figure(figsize=(180 * MM, 128 * MM))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.35, 0.55, 0.55], height_ratios=[1, 0.8], hspace=0.32, wspace=0.35)
    ax = fig.add_subplot(gs[0, 0]); mapframe(ax, land, pa)
    norm = TwoSlopeNorm(50, 10, 90)
    o = b.sort_values("need")
    ax.scatter(o.geometry.x, o.geometry.y, c=o.score, cmap=DIV_R, norm=norm, s=1.3, lw=0, zorder=4)
    letter(ax, "a", f"Urban Resilience Index, {len(b):,} HDB blocks"); scalebar(ax, 6000, 26000)
    cax = fig.add_axes([0.13, 0.57, 0.18, 0.01])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=DIV_R), cax=cax, orientation="horizontal")
    cb.set_label("block score (0–100)", fontsize=6); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=5.5)

    t = towns.sort_values("score")
    y = np.arange(len(t))
    ax = fig.add_subplot(gs[0, 1]); letter(ax, "b", "Town score")
    ax.barh(y, t.score, color=[DIV_R(norm(v)) for v in t.score], height=0.72)
    ax.set_yticks(y, t.town, fontsize=5.6); ax.set_xlim(0, 70); ax.axvline(50, color=BASE, lw=0.5)
    ax.set_xlabel("need-weighted mean")
    ax2 = fig.add_subplot(gs[0, 2], sharey=ax); letter(ax2, "c", "Inclusion gap")
    ax2.barh(y, t.inclusion_gap, color=[ACCENT if g >= 18 else GREY for g in t.inclusion_gap], height=0.72)
    ax2.set_xlabel("median − worst 20% (points)"); plt.setp(ax2.get_yticklabels(), visible=False)
    for yy, g in zip(y, t.inclusion_gap):
        if g >= 18:
            ax2.text(g + 0.4, yy, f"{g:.0f}", va="center", fontsize=5.6, color=INK)

    ax = fig.add_subplot(gs[1, :]); letter(ax, "d", "Pillar profile by town (0–100; brief weights 25/20/15/15/15/10)")
    tt = towns.sort_values("score", ascending=False)
    M = tt[list(PILLAR_N)].values.T
    ax.imshow(M, cmap=DIV_R, norm=norm, aspect="auto")
    ax.set_yticks(range(6), [f"{PILLAR_N[p]}" for p in PILLAR_N]); ax.set_xticks(range(len(tt)), tt.town, rotation=55, ha="right", fontsize=5.6)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0f}", ha="center", va="center", fontsize=4.6, color=INK if 25 < M[i, j] < 75 else "white")
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
    cm = LinearSegmentedColormap.from_list("gain", ["#e8e6df", "#f6b1a8", ACCENT, "#9a1d22"])
    o = np.argsort(d)
    ax.scatter(b.geometry.x.values[o], b.geometry.y.values[o], c=d[o], cmap=cm, norm=norm, s=4, lw=0, zorder=4)
    w = b[b.worst20]
    ax.scatter(w.geometry.x, w.geometry.y, s=7, facecolor="none", edgecolor=INK, lw=0.3, zorder=5)
    from pyproj import Transformer
    tf = Transformer.from_crs(4326, 3414, always_xy=True)
    for c in tw["inclusion_aware"]["package"]:
        x, y = tf.transform(c["lon"], c["lat"])
        ax.scatter(x, y, marker="D" if c["type"] == "green_pocket" else "s", s=30, color=TYPE_C[c["type"]], edgecolor="white", lw=0.8, zorder=6)
    letter(ax, "a", "Woodlands: inclusion-aware package")
    scalebar(ax, b.geometry.x.min() - 300, b.geometry.y.min() - 350, km=1)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", ms=3.5, mfc="none", mec=INK, mew=0.4, label="Worst-served 20% of blocks today"),
                       Line2D([], [], marker="D", ls="", ms=4.5, mfc=TYPE_C["green_pocket"], mec="white", label="Green pocket (MP2025 reserve / open-space parcel)"),
                       Line2D([], [], marker="s", ls="", ms=4.5, mfc=TYPE_C["rooftop_farm"], mec="white", label="Community farm on car-park roof")],
              loc="upper left", bbox_to_anchor=(0, -0.02), fontsize=5.6)
    cax = fig.add_axes([0.30, 0.13, 0.12, 0.012])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax, orientation="horizontal")
    cb.set_label("block score gain", fontsize=5.6); cb.outline.set_visible(False); cb.ax.tick_params(labelsize=5.2)

    base = tw["baseline"]
    rows = [("Town score\n(higher is better)", tw["average_first"]["final"]["score"] - base["score"], tw["inclusion_aware"]["final"]["score"] - base["score"]),
            ("Worst-served 20%\n(higher is better)", tw["average_first"]["worst20"] - tw["baseline_worst20"], tw["inclusion_aware"]["worst20"] - tw["baseline_worst20"]),
            ("Inclusion gap\n(lower is better)", tw["average_first"]["final"]["gap"] - base["gap"], tw["inclusion_aware"]["final"]["gap"] - base["gap"])]
    ax = fig.add_subplot(gs[1]); letter(ax, "b", "Six tweaks, two rankings")
    for i, (lab, a_, i_) in enumerate(rows):
        for off, v, c in ((-0.18, a_, GREY), (0.18, i_, ACCENT)):
            ax.barh(i + off, v, height=0.32, color=c)
            ax.text(v + (0.06 if v >= 0 else -0.06), i + off, f"{v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=5.8, color=INK)
    ax.axvline(0, color=BASE, lw=0.6); ax.set_yticks(range(3), [r[0] for r in rows], fontsize=5.8); ax.invert_yaxis()
    ax.set_xlim(-0.9, 3.4); ax.set_xlabel("change vs today (points)")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=GREY, label="Average-first"),
                       plt.Rectangle((0, 0), 1, 1, color=ACCENT, label="Inclusion-aware")], loc="upper left", bbox_to_anchor=(0, -0.2), fontsize=5.8, ncol=2)

    ax = fig.add_subplot(gs[2]); letter(ax, "c", "Who gains")
    q = tb.sort_values("score_before")
    for col, c, lab in (("score_after_average", GREY, "Average-first"), ("score_after_inclusive", ACCENT, "Inclusion-aware")):
        g = (q[col] - q.score_before).rolling(120, center=True, min_periods=30).mean()
        ax.plot(q.score_before, g, color=c, lw=1.4)
        ax.text(q.score_before.iloc[-60], g.iloc[-60] + 0.15, lab, color=c if c == ACCENT else INK2, fontsize=5.8, ha="right")
    ax.axvspan(q.score_before.min(), q.score_before.quantile(0.2), color="#f6b1a8", alpha=0.3, lw=0)
    ax.text(q.score_before.quantile(0.1), 0.05, "worst 20%", ha="center", va="bottom", fontsize=5.6, color=INK2, transform=ax.get_xaxis_transform())
    ax.set_xlabel("block score today"); ax.set_ylabel("mean score gain (rolling)"); ax.grid(axis="y", color=GRID, lw=0.4)
    save(fig, "fig3_tweaks")


# ----------------------------------------------------------------------------- Fig 4 value + robustness
def fig_value_robust(an):
    fig, axs = plt.subplots(1, 2, figsize=(180 * MM, 74 * MM), gridspec_kw=dict(width_ratios=[1, 1.1], wspace=0.55))
    v = an["value_lens"]
    eff = pd.DataFrame([dict(k=k.replace("degC", "°C"), **e) for k, e in v["effects"].items()])
    ax = axs[0]; letter(ax, "a", f"Value lens: HDB resale, {v['period']} (n = {v['n']:,})")
    y = np.arange(len(eff))[::-1]
    cols = [ACCENT if "canopy" in k or "heat" in k else GREY for k in eff.k]
    ax.hlines(y, eff.lo, eff.hi, color=cols, lw=1.2); ax.scatter(eff.pct, y, color=cols, s=16, zorder=3, edgecolor="white", lw=0.5)
    ax.axvline(0, color=BASE, lw=0.5); ax.set_yticks(y, eff.k); ax.set_xlabel("% change in resale price (95% CI)")
    ax.text(0.0, -0.17, "Within town and month, controlling for flat type, model, size, storey and lease.\nAssociations, not causal effects.",
            transform=ax.transAxes, fontsize=5.6, color=INK2, va="top")
    rb = an["robustness"]["weight_mc"]
    df = pd.DataFrame([dict(town=t, **r) for t, r in rb.items()]).sort_values("p50")
    ax = axs[1]; letter(ax, "b", f"Rank stability under {an['robustness']['mc_draws']:,} random weightings")
    y = np.arange(len(df))
    ax.hlines(y, df.p5, df.p95, color=BASE, lw=2.2); ax.scatter(df.p50, y, color=INK, s=8, zorder=3)
    ax.set_yticks(y, df.town, fontsize=5.6); ax.invert_yaxis(); ax.set_xlabel("town rank (median, 5–95%)")
    lens = an["robustness"]["lenses"]
    txt = "\n".join(f"{k}: ρ = {v['spearman_vs_default']:.2f}" for k, v in lens.items() if not k.startswith("Balanced"))
    ax.text(1.0, 0.02, "Stakeholder lenses vs default\n" + txt, transform=ax.transAxes, ha="right", va="bottom", fontsize=5.6, color=INK2)
    save(fig, "fig4_value_robustness")


# ----------------------------------------------------------------------------- Fig 5 developer case
def fig_case():
    opt = json.loads((CASE / "optimization.json").read_text()); an = json.loads((CASE / "analysis.json").read_text())
    D = opt["designs"]; names = ["Compliance-minimum", "Typical showcase", "Index-guided design"]
    short = ["Compl.\nmin.", "Typical\nshowcase", "Index-\nguided"]
    fig, axs = plt.subplots(1, 4, figsize=(180 * MM, 52 * MM), gridspec_kw=dict(wspace=0.6))
    for ax, (key, lab, scale, fmt) in zip(axs[:3], [("lcc", "30-yr greenery cost (S$M)", 1e6, "{:.2f}"),
                                                    ("fee_unit_month", "Upkeep fee (S$/unit/month)", 1, "{:.0f}"),
                                                    ("r200", "Seniors + rental households\n≤200 m of a public cool refuge", 1, "{:,.0f}")]):
        vals = [D[n][key] / scale for n in names]
        ax.bar(range(3), vals, color=[GREY, GREY, ACCENT], width=0.62)
        for i, vv in enumerate(vals):
            ax.text(i, vv, fmt.format(vv), ha="center", va="bottom", fontsize=6)
        ax.set_xticks(range(3), short, fontsize=5.8); ax.set_ylabel(lab, fontsize=6.2)
    letter(axs[0], "a", "Same URA greenery rules (GnPR 3.5)")
    up = np.load(CASE / "mc_uplift.npz")["vs_showcase"] / 1e6
    ax = axs[3]; letter(ax, "b", "Net gain vs showcase")
    ax.hist(up, bins=60, color=ACCENT, alpha=0.85)
    m = an["mc"]["uplift_vs_showcase"]
    ax.axvline(m["p50"] / 1e6, color=INK, lw=0.8)
    ax.text(m["p50"] / 1e6, ax.get_ylim()[1] * 0.95, f" P50 +S${m['p50'] / 1e6:.1f}M\n {m['prob_positive']:.0%} of 20,000\n draws > 0",
            fontsize=5.8, va="top")
    ax.set_xlabel("S$M per site, 30 yr, after fees"); ax.set_yticks([])
    save(fig, "fig5_developer_case")


def run():
    b = gpd.read_file(PROC / "blocks_scored.gpkg")
    towns = pd.read_csv(PROC / "towns.csv")
    an = json.loads((PROC / "analysis.json").read_text())
    tw = json.loads((PROC / "tweaks_woodlands.json").read_text())
    tb = pd.read_csv(PROC / "tweaks_woodlands_blocks.csv")
    fig_heat(b, an); fig_index(b, towns); fig_tweaks(tw, tb); fig_value_robust(an); fig_case()


if __name__ == "__main__":
    run()
