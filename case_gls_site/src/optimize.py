"""Greenery portfolio + public-pocket siting MILP (Gurobi).

Decision: m2 of each greenery typology on site, and where public cool-refuge pockets go
(on-site edges or off-site community pockets next to HDB blocks).
Objective: 30-year whole-life net value (sale premium + verified SLL step-down + farm rent
+ energy savings - LCC), subject to URA greenery rules, site capacity, an MCST maintenance-fee
cap, and an epsilon-constraint on vulnerable-resident cooling exposure (EQ).
"""
import json, math
from pathlib import Path
import numpy as np
import gurobipy as gp
from gurobipy import GRB

from params import SITE, URA, CAP, TYPES, T, FIN, PEOPLE
from lcc import lcc_parts, annuity
import spatial

OUT = Path(__file__).resolve().parents[1] / "results"
OUT.mkdir(exist_ok=True)

Q0 = 0.25                 # premium curvature: f(q) = 1 - exp(-q/Q0), q = amenity-weighted greenery / site area
PUBLIC_AMEN = 0.5         # on-site public pockets keep half their amenity value for buyers (exclusivity loss)
POCKET_MIN, POCKET_MAX, OFF_MAX = 100.0, CAP["edge_pocket"], 800.0
MAX_POCKETS = 3
MIN_SIZE = {"MICRO": 100, "FARM": 200, "INTR": 200, "WALL": 50, "SWALE": 100, "EXTR": 200}
MAX_SIZE = {"MICRO": 0.12 * SITE["area"], "FARM": 800.0}   # patch-scale microforests; one farm operator
CONVENTIONAL = ["TURF", "SHRUB", "TREE", "TREEH", "EXTR", "INTR", "WALL"]   # status-quo landscape palette


def premium_f(q):
    return 1 - math.exp(-q / Q0)


def offsite_cost_m2(capex_mult=1.0, om_mult=1.0):
    t = T["MICRO"]   # developer funds planting + 5 years of establishment care, then hands over
    return t.capex * capex_mult + om_mult * (t.om * annuity(FIN["r"], 5) + t.om_early * annuity(FIN["r"], 3))


class Context:
    def __init__(self):
        self.blocks = spatial.load_blocks()
        self.elder = spatial.load_eldercare()
        self.cands = spatial.candidates(self.blocks)
        self.S, self.D, self.V = spatial.exposure(self.cands, self.blocks)
        # interpretable reach count: seniors + public-rental households (not need-weighted)
        self.P = np.array([b["seniors"] + b["rental"] for b in self.blocks])
        self.lcc = {t.key: lcc_parts(t) for t in TYPES}
        self.energy_pv = FIN["roof_kwh"] * FIN["tariff"] * annuity(FIN["r"], FIN["horizon"])


def build(ctx, mode, eps=0.0, fix=None, verbose=False):
    m = gp.Model(mode)
    m.Params.OutputFlag = 1 if verbose else 0
    A = SITE["area"]
    x = {t.key: m.addVar(lb=0, name=f"x_{t.key}") for t in TYPES}
    y = {t.key: m.addVar(vtype=GRB.BINARY, name=f"y_{t.key}") for t in TYPES}
    P = range(len(ctx.cands))
    z = {p: m.addVar(lb=0, name=f"z_{ctx.cands[p]['id']}") for p in P}
    u = {p: m.addVar(vtype=GRB.BINARY, name=f"u_{ctx.cands[p]['id']}") for p in P}
    ysll = m.addVar(vtype=GRB.BINARY, name="y_sll")
    capped = m.addVar(lb=0, ub=URA["vertical_extroof_cap_pct"] * A, name="lra_capped")
    prem = m.addVar(lb=0, name="premium")

    on = [p for p in P if ctx.cands[p]["onsite"]]
    off = [p for p in P if not ctx.cands[p]["onsite"]]

    # capacities and minimum viable sizes
    cap = {"ground": CAP["ground"], "roof": CAP["roof"], "facade": CAP["facade"], "hard": CAP["hard"]}
    for zone, c in cap.items():
        m.addConstr(gp.quicksum(x[t.key] for t in TYPES if t.zone == zone) <= c, f"cap_{zone}")
    for t in TYPES:
        m.addConstr(x[t.key] <= cap[t.zone] * y[t.key])
        m.addConstr(x[t.key] >= MIN_SIZE.get(t.key, 0) * y[t.key])
        if t.key in MAX_SIZE:
            m.addConstr(x[t.key] <= MAX_SIZE[t.key])

    # URA greenery (Table 4/5): overall LRA, on-ground LRA, Green Plot Ratio
    m.addConstr(capped <= x["EXTR"] + x["WALL"])
    m.addConstr(gp.quicksum(x[t.key] for t in TYPES if t.lra and not t.capped) + capped >= URA["overall_pct"] * A, "ura_overall")
    m.addConstr(gp.quicksum(x[t.key] for t in TYPES if t.lra and t.zone == "ground") >= URA["ground_pct"] * A, "ura_ground")
    m.addConstr(gp.quicksum(t.lai * x[t.key] for t in TYPES) >= URA["gnpr"] * A, "ura_gnpr")

    # public pockets: on-site ones are carved out of microforest/tree area; off-site ones are extra
    for p in P:
        hi = POCKET_MAX if ctx.cands[p]["onsite"] else OFF_MAX
        m.addConstr(z[p] <= hi * u[p]); m.addConstr(z[p] >= POCKET_MIN * u[p])
    m.addConstr(gp.quicksum(u[p] for p in P) <= MAX_POCKETS)
    m.addConstr(gp.quicksum(z[p] for p in on) <= x["MICRO"] + x["TREE"])

    # SLL KPIs (mirror a 2026 developer SLL whose KPIs include microforests + urban farming)
    m.addConstr(x["MICRO"] + gp.quicksum(z[p] for p in off) >= FIN["sll_micro_min"] * ysll)
    m.addConstr(x["FARM"] >= FIN["sll_farm_min"] * ysll)

    # MCST maintenance-fee cap (on-site O&M, steady state)
    if not (fix and fix.get("no_fee_cap")):
        m.addConstr(gp.quicksum(t.om * x[t.key] for t in TYPES) <= FIN["mcst_cap"] * SITE["units"] * 12, "mcst_fee")

    # concave sale premium via tangent cuts
    q = (gp.quicksum(t.amen * x[t.key] for t in TYPES) - (1 - PUBLIC_AMEN) * gp.quicksum(z[p] for p in on)) / A
    PG = FIN["premium_max"] * SITE["gdv"]
    for qi in np.linspace(0, 1.0, 41):
        f, df = premium_f(qi), math.exp(-qi / Q0) / Q0
        m.addConstr(prem <= PG * (f + df * (q - qi)))

    # equity: vulnerable-resident cooling exposure, MICRO cooling intensity per 100 m2 of pocket
    EQ = gp.quicksum(ctx.S[p] * z[p] for p in P) * T["MICRO"].tau / 1000.0
    if eps > 0:
        m.addConstr(EQ >= eps, "equity")

    capex = gp.quicksum(T[k].capex * x[k] for k in x) + gp.quicksum(offsite_cost_m2() * z[p] for p in off)
    lcc = gp.quicksum(ctx.lcc[k]["total"] * x[k] for k in x)
    energy = ctx.energy_pv * (x["EXTR"] + x["INTR"])
    npv = prem + FIN["sll_value"] * ysll + energy - lcc - gp.quicksum(offsite_cost_m2() * z[p] for p in off)

    if fix:
        for k, v in fix.get("min", {}).items():
            m.addConstr(x[k] >= v)
        for k, v in fix.get("max", {}).items():
            m.addConstr(x[k] <= v)
        if fix.get("palette"):
            for k in x:
                if k not in fix["palette"]:
                    m.addConstr(x[k] == 0)
        if fix.get("no_pockets"):
            m.addConstr(gp.quicksum(u[p] for p in P) == 0)
    if mode == "min_capex":
        m.setObjective(capex, GRB.MINIMIZE)
    elif mode == "max_eq":
        m.setObjective(EQ, GRB.MAXIMIZE)
    else:
        m.setObjective(npv, GRB.MAXIMIZE)
    m.Params.MIPGap = 1e-4
    m.optimize()
    assert m.Status == GRB.OPTIMAL, (mode, m.Status)
    sol = dict(x={k: x[k].X for k in x}, z={ctx.cands[p]["id"]: z[p].X for p in P if z[p].X > 1e-6},
               sll=ysll.X > 0.5, obj=m.ObjVal, eq=EQ.getValue(), mip_gap=m.MIPGap, runtime=m.Runtime,
               nvars=m.NumVars, nbin=m.NumBinVars, ncons=m.NumConstrs)
    return sol


def evaluate(ctx, sol, draws=None):
    """Exact (non-linearised) evaluation of a design. `draws` overrides uncertain inputs."""
    d = dict(capex=1.0, om=1.0, pmax=FIN["premium_max"], sll_bps=FIN["sll_bps"], rent=None, tau=1.0,
             premium_real=1.0, sll_ok=1.0)
    if draws:
        d.update(draws)
    A, x = SITE["area"], sol["x"]
    on = {c["id"]: c for c in ctx.cands}
    z_on = sum(v for k, v in sol["z"].items() if on[k]["onsite"])
    z_off = sum(v for k, v in sol["z"].items() if not on[k]["onsite"])
    q = (sum(T[k].amen * v for k, v in x.items()) - (1 - PUBLIC_AMEN) * z_on) / A
    prem = d["pmax"] * SITE["gdv"] * premium_f(q) * d["premium_real"]
    lcc, capex, om_yr = 0.0, 0.0, 0.0
    for k, v in x.items():
        t = T[k]
        parts = lcc_parts(t, capex_mult=d["capex"], om_mult=d["om"])
        rent_adj = 0.0
        if t.rent and d["rent"] is not None:
            rent_adj = (t.rent - d["rent"]) * annuity(FIN["r"], FIN["horizon"])
        lcc += (parts["total"] + rent_adj) * v
        capex += parts["capex"] * v
        om_yr += t.om * d["om"] * v
    off_cost = offsite_cost_m2(d["capex"], d["om"]) * z_off
    sll = FIN["sll_value"] * d["sll_bps"] / FIN["sll_bps"] * d["sll_ok"] if sol["sll"] else 0.0
    energy = ctx.energy_pv * (x["EXTR"] + x["INTR"])
    npv = prem + sll + energy - lcc - off_cost
    leaf = sum(T[k].lai * v for k, v in x.items())
    lra = sum(v for k, v in x.items() if T[k].lra and not T[k].capped) + min(x["EXTR"] + x["WALL"], URA["vertical_extroof_cap_pct"] * A)
    eq = sum(ctx.S[[c["id"] for c in ctx.cands].index(k)] * v for k, v in sol["z"].items()) * T["MICRO"].tau * d["tau"] / 1000
    # vulnerable residents within 200 m of a public cool refuge
    ids = [c["id"] for c in ctx.cands]
    near = np.zeros(len(ctx.blocks), bool)
    for k in sol["z"]:
        near |= ctx.D[ids.index(k)] <= 200
    r200 = float(ctx.P[near].sum())
    cool_area = sum(T[k].tau * v for k, v in x.items()) / A        # area-weighted on-site cooling (deg C)
    return dict(npv=npv, premium=prem, sll=sll, energy=energy, lcc=lcc, capex=capex + off_cost,
                capex_onsite=capex, offsite=off_cost, om_yr=om_yr,
                fee_unit_month=om_yr / SITE["units"] / 12, gnpr=leaf / A, lra_pct=lra / A, q=q,
                eq=eq, r200=r200, cool=cool_area, z_on=z_on, z_off=z_off)


def run():
    ctx = Context()
    print(f"blocks within {PEOPLE['radius']:.0f} m: {len(ctx.blocks)}, vulnerable-weighted residents: {ctx.V.sum():.0f}, "
          f"pocket candidates: {len(ctx.cands)} ({sum(c['onsite'] for c in ctx.cands)} on-site), eldercare: {len(ctx.elder)}")
    designs = {}
    designs["Compliance-minimum"] = build(ctx, "min_capex", fix={"no_pockets": True, "palette": CONVENTIONAL, "no_fee_cap": True})
    designs["Typical showcase"] = build(ctx, "min_capex", fix={"min": {"WALL": 500, "INTR": 600}, "no_pockets": True, "palette": CONVENTIONAL, "no_fee_cap": True})
    unconstrained = build(ctx, "max_npv")
    eq_max = build(ctx, "max_eq")["eq"]

    # Pareto frontier (epsilon-constraint on EQ)
    front = []
    for e in np.linspace(0, eq_max, 21):
        s = build(ctx, "max_npv", eps=float(e) * 0.9999)
        ev = evaluate(ctx, s)
        front.append(dict(eps=float(e), npv=ev["npv"], eq=ev["eq"], r200=ev["r200"], x=s["x"], z=s["z"], sll=s["sll"]))
    # knee: maximum EQ whose NPV stays within 5% of the unconstrained optimum
    best = evaluate(ctx, unconstrained)["npv"]
    knee = max((f for f in front if f["npv"] >= best - 0.05 * abs(best)), key=lambda f: f["eq"])
    designs["Index-guided design"] = build(ctx, "max_npv", eps=knee["eq"] * 0.9999)

    # naive placement benchmark: same pocket area as the index-guided design, at the best on-site edge only
    up = designs["Index-guided design"]
    area = sum(up["z"].values())
    on_ids = [i for i, c in enumerate(ctx.cands) if c["onsite"]]
    naive = max(on_ids, key=lambda i: ctx.S[i])
    worst = min(on_ids, key=lambda i: ctx.S[i])
    res = {name: evaluate(ctx, s) for name, s in designs.items()}
    for name, s in designs.items():
        res[name]["x"] = s["x"]; res[name]["z"] = s["z"]; res[name]["sll_on"] = s["sll"]
        res[name]["solver"] = {k: s[k] for k in ("mip_gap", "runtime", "nvars", "nbin", "ncons")}
    for tag, i in (("naive_edge_best", naive), ("naive_edge_worst", worst)):
        sol = dict(x=up["x"], z={ctx.cands[i]["id"]: area}, sll=up["sll"])
        res[tag] = evaluate(ctx, sol); res[tag]["z"] = sol["z"]

    out = dict(designs=res, frontier=front, knee=knee["eq"], eq_max=eq_max,
               cands=ctx.cands, S=ctx.S.tolist(),
               blocks=ctx.blocks, elder=ctx.elder,
               site={k: v for k, v in SITE.items()}, lcc={k: v for k, v in ctx.lcc.items()})
    (OUT / "optimization.json").write_text(json.dumps(out, indent=1, default=float))
    for name in ("Compliance-minimum", "Typical showcase", "Index-guided design", "naive_edge_best", "naive_edge_worst"):
        r = res[name]
        print(f"\n== {name}: NPV {r['npv']/1e6:7.2f}M | premium {r['premium']/1e6:5.2f}M | SLL {r['sll']/1e6:4.2f}M | "
              f"LCC {r['lcc']/1e6:5.2f}M | capex {r['capex']/1e6:5.2f}M | fee S${r['fee_unit_month']:.1f}/unit/mo | "
              f"GnPR {r['gnpr']:.2f} | LRA {r['lra_pct']:.0%} | EQ {r['eq']:.1f} | R200 {r['r200']:.0f} | cool {r['cool']:.2f}")
        if "x" in r:
            print("   ", {k: round(v) for k, v in r["x"].items() if v > 0.5}, {k: round(v) for k, v in r["z"].items()})
    print("\nfrontier:")
    for f in front:
        print(f"  eq {f['eq']:7.1f}  npv {f['npv']/1e6:6.2f}M  r200 {f['r200']:6.0f}  pockets {({k: round(v) for k, v in f['z'].items()})}")
    print("knee eq", knee["eq"], "eq_max", eq_max)
    return out


if __name__ == "__main__":
    run()
