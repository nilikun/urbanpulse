"""Uncertainty (Monte Carlo), verification flywheel (Bayesian), AHP pillar weights, business model."""
import json
from pathlib import Path
import numpy as np

from params import FIN, BIZ, SITE
from optimize import Context, evaluate
from lcc import annuity

OUT = Path(__file__).resolve().parents[1] / "results"
rng = np.random.default_rng(20261010)
N = 20_000

# Reducible (epistemic) uncertainty as log-scale sigma on a multiplier, prior from literature spread,
# and irreducible site-to-site sigma. Posterior after n verified sites: normal-normal hierarchical model.
UNC = {               # prior sigma0, between-site sigma_b, measurement sigma_e
    "premium": (0.60, 0.25, 0.20),   # hedonic premium effect (literature 0.3%-3%)
    "om":      (0.35, 0.15, 0.05),   # real maintenance cost vs estimate
    "capex":   (0.20, 0.10, 0.03),
    "tau":     (0.50, 0.20, 0.10),   # cooling achieved vs predicted (1-5 C range in literature)
}


def predictive_sigma(key, n):
    s0, sb, se = UNC[key]
    post_var = 1 / (1 / s0 ** 2 + n / (sb ** 2 + se ** 2))
    return float(np.sqrt(post_var + sb ** 2))


def draws(n_verified, verified=True, size=N):
    """Sample uncertain inputs. Without verification the SLL step-down cannot be claimed
    (SLL Principles require annual external verification of each SPT)."""
    lg = lambda k: np.exp(rng.normal(-0.5 * predictive_sigma(k, n_verified) ** 2, predictive_sigma(k, n_verified), size))
    return dict(
        premium_real=lg("premium"), om=lg("om"), capex=lg("capex"), tau=lg("tau"),
        sll_bps=rng.uniform(2.5, 10.0, size), rent=rng.uniform(11.0, 24.0, size),
        sll_ok=np.ones(size) if verified else np.zeros(size),
    )


def mc_eval(ctx, sol, d):
    keys = list(d)
    out = np.empty(len(d[keys[0]]))
    for i in range(len(out)):
        out[i] = evaluate(ctx, sol, {k: float(d[k][i]) for k in keys})["npv"]
    return out


def ahp(M):
    M = np.asarray(M, float)
    w, v = np.linalg.eig(M)
    i = np.argmax(w.real)
    wt = np.abs(v[:, i].real); wt /= wt.sum()
    n = len(M); ci = (w[i].real - n) / (n - 1)
    ri = {3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32}[n]
    return wt, ci / ri


PILLARS = ["Heat exposure", "Shade & cooling", "Green-blue space", "Community use", "Access & mobility", "Flood resilience"]
# Saaty 1-9 pairwise judgements per stakeholder lens (row vs column importance)
AHP_LENS = {
    "Balanced (default)": [[1, 2, 2, 2, 2, 3], [1/2, 1, 1, 1, 1, 2], [1/2, 1, 1, 1, 1, 2],
                           [1/2, 1, 1, 1, 1, 2], [1/2, 1, 1, 1, 1, 2], [1/3, 1/2, 1/2, 1/2, 1/2, 1]],
    "Senior / resident":  [[1, 1, 3, 2, 1, 4], [1, 1, 3, 2, 1, 4], [1/3, 1/3, 1, 1/2, 1/3, 2],
                           [1/2, 1/2, 2, 1, 1/2, 3], [1, 1, 3, 2, 1, 4], [1/4, 1/4, 1/2, 1/3, 1/4, 1]],
    "Planner":            [[1, 2, 1, 3, 2, 1], [1/2, 1, 1/2, 2, 1, 1/2], [1, 2, 1, 3, 2, 1],
                           [1/3, 1/2, 1/3, 1, 1/2, 1/3], [1/2, 1, 1/2, 2, 1, 1/2], [1, 2, 1, 3, 2, 1]],
    "Developer / lender": [[1, 1/2, 2, 1/2, 2, 1], [2, 1, 3, 1, 3, 2], [1/2, 1/3, 1, 1/3, 1, 1/2],
                           [2, 1, 3, 1, 3, 2], [1/2, 1/3, 1, 1/3, 1, 1/2], [1, 1/2, 2, 1/2, 2, 1]],
}


def business(value_per_project):
    """5-year revenue build-up. New Project Passes per year (GLS + private launches), monitoring
    renews for 5 years, plus SGIS-eligible retrofits of existing buildings."""
    new_sites = np.array([3, 8, 15, 22, 30])
    retrofits = np.array([2, 6, 12, 20, 30])
    yrs = np.arange(1, 6)
    monitored = np.cumsum(new_sites)
    rev_pass = new_sites * BIZ["pass_fee"]
    rev_mon = monitored * BIZ["monitor_fee"]
    rev_retro = np.cumsum(retrofits) * BIZ["retrofit_fee"]
    fees_pv = BIZ["pass_fee"] + BIZ["monitor_fee"] * annuity(FIN["r"], BIZ["monitor_years"])
    return dict(years=yrs.tolist(), new_sites=new_sites.tolist(), monitored=monitored.tolist(),
                rev_pass=rev_pass.tolist(), rev_mon=rev_mon.tolist(), rev_retro=rev_retro.tolist(),
                rev_total=(rev_pass + rev_mon + rev_retro).tolist(), fees_pv_per_project=fees_pv,
                client_roi=value_per_project / fees_pv,
                gls_units_2026=BIZ["gls_units_2026"])


def run():
    ctx = Context()
    opt = json.loads((OUT / "optimization.json").read_text())
    D = opt["designs"]
    sols = {k: dict(x=D[k]["x"], z=D[k]["z"], sll=D[k]["sll_on"]) for k in ("Compliance-minimum", "Typical showcase", "Index-guided design")}

    # 1. Monte Carlo: current knowledge (n=0) -- baselines are never verified; the index-guided design with and without MRV
    res = {}
    d0 = draws(0, verified=False)
    for k in ("Compliance-minimum", "Typical showcase"):
        res[k] = mc_eval(ctx, sols[k], d0)
    res["Index-guided design, no MRV"] = mc_eval(ctx, sols["Index-guided design"], d0)
    d0v = {**d0, "sll_ok": np.ones(N)}
    res["Index-guided design + MRV"] = mc_eval(ctx, sols["Index-guided design"], d0v)
    fee = BIZ["pass_fee"] + BIZ["monitor_fee"] * annuity(FIN["r"], BIZ["monitor_years"])
    res["Index-guided design + MRV"] -= fee
    diff = res["Index-guided design + MRV"] - res["Typical showcase"]
    mc = {k: dict(p10=float(np.percentile(v, 10)), p50=float(np.percentile(v, 50)), p90=float(np.percentile(v, 90)),
                  mean=float(v.mean())) for k, v in res.items()}
    mc["uplift_vs_showcase"] = dict(p10=float(np.percentile(diff, 10)), p50=float(np.percentile(diff, 50)),
                                    p90=float(np.percentile(diff, 90)), prob_positive=float((diff > 0).mean()))
    np.savez_compressed(OUT / "mc_samples.npz", **{k.replace(" ", "_").replace(",", "").replace("+", "plus"): v[:5000] for k, v in res.items()})

    # 2. Verification flywheel: predictive uncertainty and bankable (P10) value vs verified sites
    fly = []
    for n in [0, 1, 2, 3, 5, 8, 12, 20, 30, 50]:
        d = draws(n, verified=True, size=4000)
        v = mc_eval(ctx, sols["Index-guided design"], d) - fee
        fly.append(dict(n=n, p10=float(np.percentile(v, 10)), p50=float(np.percentile(v, 50)), p90=float(np.percentile(v, 90)),
                        sig_tau=predictive_sigma("tau", n), sig_prem=predictive_sigma("premium", n),
                        ci90_tau=float(2 * 1.645 * predictive_sigma("tau", n))))
        print(f"n={n:3d}  P10 {fly[-1]['p10']/1e6:5.2f}M  P50 {fly[-1]['p50']/1e6:5.2f}M  P90 {fly[-1]['p90']/1e6:5.2f}M  sig_tau {fly[-1]['sig_tau']:.2f}")

    # 2b. one-at-a-time sensitivity of the uplift vs the typical showcase
    base = {"premium_real": 1.0, "om": 1.0, "capex": 1.0, "tau": 1.0, "sll_bps": FIN["sll_bps"], "rent": 15.0, "sll_ok": 1.0}
    def uplift(over):
        a = evaluate(ctx, sols["Index-guided design"], {**base, **over})["npv"] - fee
        b = evaluate(ctx, sols["Typical showcase"], {**base, **over, "sll_ok": 0.0})["npv"]
        return a - b
    sens_spec = [("Sale-premium effect (0.3x to 2x)", "premium_real", 0.3, 2.0),
                 ("Maintenance cost (-30% to +50%)", "om", 0.7, 1.5),
                 ("Capex (-20% to +30%)", "capex", 0.8, 1.3),
                 ("SLL step-down (2.5 to 10 bps)", "sll_bps", 2.5, 10.0),
                 ("Farm rent (S$11 to S$24/m2/yr)", "rent", 11.0, 24.0)]
    sens = dict(base=uplift({}), rows=[])
    for lab, k, lo, hi in sens_spec:
        sens["rows"].append(dict(label=lab, lo=uplift({k: lo}), hi=uplift({k: hi})))
    print("sensitivity", sens)
    dd = draws(0, verified=False)
    d_cm = mc_eval(ctx, sols["Compliance-minimum"], dd)
    d_up = mc_eval(ctx, sols["Index-guided design"], {**dd, "sll_ok": np.ones(N)}) - fee
    diff_cm = d_up - d_cm
    mc["uplift_vs_compliance"] = dict(p10=float(np.percentile(diff_cm, 10)), p50=float(np.percentile(diff_cm, 50)),
                                      p90=float(np.percentile(diff_cm, 90)), prob_positive=float((diff_cm > 0).mean()))
    np.savez_compressed(OUT / "mc_uplift.npz", vs_showcase=diff, vs_compliance=diff_cm)

    # 3. AHP
    ah = {}
    for lens, M in AHP_LENS.items():
        w, cr = ahp(M)
        ah[lens] = dict(w=w.tolist(), cr=float(cr))
        print(f"AHP {lens:20s} CR={cr:.3f} ", " ".join(f"{p.split()[0]}:{x:.2f}" for p, x in zip(PILLARS, w)))

    # 4. Business
    up, sh = D["Index-guided design"], D["Typical showcase"]
    value = up["npv"] - sh["npv"]
    biz = business(value)
    print("value per project vs showcase", value, "client ROI", biz["client_roi"], "rev", biz["rev_total"])

    out = dict(mc=mc, flywheel=fly, ahp=ah, pillars=PILLARS, business=biz, fee_pv=fee, sensitivity=sens)
    (OUT / "analysis.json").write_text(json.dumps(out, indent=1))
    for k, v in mc.items():
        print(k, {a: round(b / 1e6, 2) if a != "prob_positive" else b for a, b in v.items()})
    return out


if __name__ == "__main__":
    run()
