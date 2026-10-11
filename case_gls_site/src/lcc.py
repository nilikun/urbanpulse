"""30-year life-cycle cost (LCC) per m2 for each greenery typology (S$, real, discounted)."""
from params import TYPES, FIN


def annuity(r, n, start=1):
    return sum((1 + r) ** -t for t in range(start, n + 1))


def lcc_parts(t, r=None, n=None, capex_mult=1.0, om_mult=1.0):
    r = FIN["r"] if r is None else r
    n = FIN["horizon"] if n is None else n
    capex = t.capex * capex_mult
    om = t.om * om_mult * annuity(r, n) + t.om_early * om_mult * annuity(r, 3)
    repl = sum(f * capex * (1 + r) ** -yr for yr, f in t.life_repl if yr <= n)
    rent = t.rent * annuity(r, n)
    return dict(capex=capex, om=om, repl=repl, rent=rent, total=capex + om + repl - rent)


def table():
    rows = []
    for t in TYPES:
        p = lcc_parts(t)
        p.update(key=t.key, label=t.label, lai=t.lai,
                 per_leaf=(p["capex"] + p["om"] + p["repl"]) / t.lai if t.lai else float("nan"),
                 per_cool=(p["capex"] + p["om"] + p["repl"]) / t.tau if t.tau else float("nan"))
        rows.append(p)
    return rows


if __name__ == "__main__":
    for r in table():
        print(f'{r["key"]:6s} capex {r["capex"]:6.0f} om {r["om"]:6.0f} repl {r["repl"]:5.0f} rent {r["rent"]:5.0f} '
              f'LCC {r["total"]:6.0f} | per leaf-m2 {r["per_leaf"]:6.0f} | per C {r["per_cool"]:6.0f}')
