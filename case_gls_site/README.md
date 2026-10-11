# Developer case: a 2023 GLS condominium site in Woodlands

How the project pass turns mandatory greenery into returns, tested on one real Government Land Sales site. The site is anonymised. Its figures (14,433 m² site, 348 units, land price, launch price) come from public GLS award and launch records.

## Run

```bash
python ../run_all.py --from index         # the index must exist first (data/processed/blocks_scored.gpkg)
python src/optimize.py                    # Gurobi MILP: 3 designs + Pareto frontier -> results/optimization.json
python src/analysis.py                    # Monte Carlo, flywheel, sensitivity, AHP, business -> results/analysis.json
```

`gurobipy` needs a licence; the free academic licence is enough.

## What the model decides

* m² of each of 10 greenery types: turf, shrubs, layered trees, native microforest, canopy over paths, bioswale, extensive roof, communal roof garden, rooftop farm, green wall.
* Where up to three **public cool-refuge pockets** go: 8 site edges, or next to nearby HDB blocks.

These choices are made subject to:

* URA landscape replacement and Green Plot Ratio rules;
* zone capacities;
* a maintenance-fee cap;
* two sustainability-linked-loan KPIs (microforest ≥ 300 m², urban farm ≥ 400 m²);
* an ε-constraint on cooling exposure for vulnerable residents.

**Upgrade over the hackathon version.** Vulnerability now comes from the island-wide index. Each nearby HDB block is weighted by its need (Census 2020 seniors + 1.5 × rental households, × 1.3 if built before 1990) times its resilience shortfall, (100 − score)/50. Pockets therefore go where the index sees the most need. `spatial.load_blocks(use_index=False)` reproduces the original version.

## Results

| Design | 30-yr life-cycle cost | Upkeep fee /unit/month | GnPR | Seniors + rental households ≤200 m of a refuge | Loan KPIs met |
|---|---|---|---|---|---|
| Compliance-minimum | S$3.03M | S$22 | 3.50 | 0 | 0/2 |
| Typical showcase (≥500 m² green wall, ≥600 m² roof garden) | S$4.76M | S$35 | 3.50 | 0 | 0/2 |
| **Index-guided design** | **S$2.81M** | **S$16** | 3.50 | **898** | 2/2 |

* Same pocket area at the single best on-site edge reaches 712; at the worst edge, 244.
* Net gain vs showcase after fees: **P50 +S$2.14M per site** (P10/P90 1.61/2.92). It is positive in 100% of 20,000 Monte Carlo draws. Vs compliance-minimum: P50 +S$0.48M, positive in 99%.
* One-at-a-time stress tests: sale premium 0.3–2×, upkeep −30%/+50%, capex −20%/+30%, loan step-down 2.5–10 bps, farm rent S$11–24/m²/yr. The gain stays between S$1.7M and S$2.7M across all of them.
* Verification "flywheel": the bankable (P10) value rises from −S$0.6M with no verified sites to +S$1.4M after 8.

## Assumptions to defend

Every input in [`src/params.py`](src/params.py) is tagged with its source or marked as an assumption. The main assumptions are:

* sale-premium ceiling of 1% of GDV;
* loan step-down of 5 bps, within the 2.5–10 bps market range;
* a 4% real discount rate;
* a 30-year horizon.

The Skyrise Greenery Incentive is **not** counted, because it co-funds existing buildings, not new GLS sites. Rooftop farms are not counted toward URA greenery, which is conservative. The site outline is approximated as a ~120 m square.
