# UrbanPulse methods

Every number on the website and in the README comes from the pipeline in [`uri/`](../uri) and [`case_gls_site/`](../case_gls_site), run by [`run_all.py`](../run_all.py). This note documents each step, its assumptions and how it was checked.

## 1. Block table ([`uri/blocks.py`](../uri/blocks.py))

**Units.** Residential HDB blocks from *HDB Property Information* (10,817 rows with `residential = Y`).

**Location without geocoding.** HDB's *Existing Building* footprints carry `BLK_NO` and a street code `ST_COD`, but no street name. Property Information carries block number and street name, but no code. For every street name and every street code we take the set of block numbers on it. We match names to codes by Jaccard similarity of those sets with the Hungarian algorithm, keeping matches with J ≥ 0.5. 649 of 657 streets match with J ≥ 0.8. Against 929 Woodlands blocks independently geocoded with OneMap, the match is right for 899, wrong for 2, and 28 have no footprint. **10,749 blocks (99.4%)** join to a footprint polygon; centroids are in SVY21 (EPSG:3414).

**Need weight.** Vulnerability weights blocks; it is not a pillar.

```
seniors_b = (units_b − rental_b) × 3.0 × share65(subzone of b)     # Census 2020, residents aged 65+
need_b    = (seniors_b + 1.5 × rental_b) × (1.3 if year_b < 1990 else 1)
```

The household size (3.0), rental weight (1.5) and old-block factor (1.3) are stated assumptions. Tengah's subzones had no residents in Census 2020, so its 156 blocks use the town median, which falls back to the island median.

## 2. Satellite layers ([`uri/satellite.py`](../uri/satellite.py))

All rasters sit on one SVY21 grid (X 2,000–56,000 m, Y 20,000–52,000 m): 30 m for Landsat and 10 m for Sentinel-2.

**Land surface temperature (LST).** Source: Landsat Collection 2 Level-2, WRS-2 path 125 / row 59, scenes with < 40% cloud. "Now" uses Landsat 8/9 for 2021–2025 (58 found, 52 used). "Then" uses Landsat 5 for 1988–1997 (50 found, 37 used). A scene is used if ≥ 25% of land pixels are clear.

*Why we do not use the official ST band.* It is empty wherever ASTER GED emissivity is missing. In Singapore this blanks large parts of Sengkang, Punggol and Yishun in every scene. We therefore invert the radiative-transfer equation for every pixel, using the L2 thermal radiance and atmospheric layers:

```
TRAD = τ·ε·B(Ts) + τ·(1 − ε)·L↓ + L↑          (TRAD, τ = ATRAN, L↑ = URAD, L↓ = DRAD)
Ts   = K2 / ln(K1 / B + 1)                      (K1, K2 per sensor, from USGS metadata)
ε    = 0.99·Pv + 0.97·(1 − Pv),   Pv = clip((NDVI − 0.2) / 0.3, 0, 1)²     (Sobrino et al. 2004)
```

Clouds, cloud shadow, cirrus, snow and water are masked with `QA_PIXEL`. Values outside 15–65 °C are dropped.

*Validation.* Where the official ST exists, our LST differs from it as follows:

| Period | Bias | RMSE | MAE | Pixels |
|---|---|---|---|---|
| Now | −0.47 °C | 0.99 °C | 0.72 °C | 469,749 |
| Then | −0.48 °C | 1.16 °C | — | 305,086 |

*Compositing.* Each scene is converted to an anomaly: LST minus that scene's island land median. The per-pixel median anomaly is the composite. This removes day-to-day and seasonal offsets and the constant bias above. The maps therefore show **where heat sits relative to Singapore that day, not absolute warming.** Median clear observations per pixel are 31 (now) and 21 (then).

**Sentinel-2.** Source: L2A, tile 48NUG, 2024–2025, < 20% cloud (7 scenes). Pixels are masked with the scene classification layer (cloud, shadow and cirrus removed), the baseline-04.00 offset (−1000) is applied, and bands are median-composited. Tree canopy is approximated as **NDVI > 0.6** at 10 m.

## 3. Walking network and shade ([`uri/osm.py`](../uri/osm.py), [`uri/network.py`](../uri/network.py))

OpenStreetMap ways a person can walk on (footways, paths, covered corridors, local and service roads; no motorways or private ways) come from the BBBike Singapore extract (base 2026-10-09). The result is 237,057 ways, 750,530 nodes and 16,087 km. Snapping uses only the largest connected component. Duplicate parallel edges keep the shortest weight.

Each edge has a **shade share** *s*:

* *s* = 1 if it is covered, arcade, colonnade, tunnel, building passage, indoor or a corridor (701 km);
* otherwise, *s* is the share of 10 m samples whose 3 × 3 Sentinel-2 neighbourhood has canopy.

Overall, 38.8% of walkable length is shaded. **Heat-adjusted length** = length × (1 + α(1 − *s*)), with α = 0.5. This is an assumption: an unshaded metre counts as 1.5 shaded metres. α is tested in §7. Distances to the nearest amenity use multi-source Dijkstra (SciPy) from every amenity point at once.

## 4. Indicators and scores ([`uri/index.py`](../uri/index.py))

| Key | Pillar | Definition | Better |
|---|---|---|---|
| `lst_anom` | heat | NaN-aware mean of the LST anomaly within 100 m (FFT disk filter) | lower |
| `canopy200` | shade | % of land within 200 m with NDVI > 0.6 | higher |
| `route_shade400` | shade | Length-weighted shade share of edges whose midpoint is within 400 m | higher |
| `park_walk` | green | Plain network walk to the nearest park boundary (NParks parks and reserves ≥ 2,000 m², boundary sampled every 25 m) | lower |
| `park_area800` | green | Park area within an 800 m buffer (ha) | higher |
| `blue_dist` | green | Distance to the nearest Park Connector or waterbody (≥ 5,000 m²) edge | lower |
| `gardens400` | community | Community in Bloom gardens within 400 m (proxy) | higher |
| `walk_aac`, `walk_clinic`, `walk_hawker`, `walk_mrt`, `walk_bus` | access | Heat-adjusted walks to eldercare/AAC, CHAS clinic, hawker centre, MRT exit, bus stop | lower |
| `flood_dist` | flood | Distance to the nearest of 36 PUB flood-prone locations (Nov 2025), each geocoded to one representative OneMap point | higher |

**Scoring.**
* Each indicator becomes a mid-rank percentile against a **fixed reference**: today's 10,749 blocks. A scenario or tweak is then scored on the same national scale without re-ranking everyone else.
* A pillar is the mean of its indicators.
* Block score = Σ *w*·pillar / Σ *w*, with default weights 25/20/15/15/15/10.
* Town score is the need-weighted mean of its block scores.
* **Inclusion gap** = median block score − mean of the lowest 20%.

**Five tests.**
* *Redundancy*: no pair of the 13 scored indicators has |Spearman ρ| > 0.8 ([`data/processed/indicator_spearman.csv`](../data/processed)).
* *WBGT*: it was computed (NEA, 27 stations, 1 Mar–31 May 2026; hours ≥ 31 °C, inverse-distance from the 3 nearest stations). It **fails the block-level test**: ρ with block surface heat is −0.05, and its highest values sit at forest and waterfront stations. It is reported as context only.

## 5. Analyses ([`uri/analysis.py`](../uri/analysis.py))

* **Benchmarks.** For each plannable indicator, the design target is the median, over the five best towns, of each town's median block.
* **Heat drivers.**
  * *OLS:* `lst_anom ~ canopy200 + impervious100 + park_area800 + blue_dist + floors + year_built + hdb_footprint200 + C(town)`, with standardised predictors and town-clustered errors. n = 10,749; R² = 0.68.
  * *Gradient-boosted trees:* scikit-learn HistGradientBoosting with **leave-one-town-out** validation. R² = 0.59 on the held-out town.
  * *Canopy effect:* +10 pp canopy ≈ −0.48 °C (unstandardised OLS).
* **Heat history.** Block-level change in anomaly between 1988–97 and 2021–25, by build era.
* **Value lens.**
  * *Data:* HDB resale transactions Jan 2024 – Oct 2026 joined to blocks (n = 73,304; 9,467 blocks).
  * *Model:* `log price ~ log floor area + storey + lease + lease² + C(flat type) + C(flat model) + C(month) + C(town) + canopy/10 + lst_anom + park walk/100 + MRT walk/100 + hawker walk/100`, with block-clustered errors. R² = 0.94.
  * *Status:* reported outside the index, as associations, not causal effects.

## 6. Tweak engine ([`uri/tweaks.py`](../uri/tweaks.py))

**Candidates for Woodlands.** Fifteen per type, screened by Σ need × (100 − score)/50 within 400 m:

* **Green pocket** on a URA Master Plan 2025 *Reserve site* or *Open space* parcel (≥ 1,000 m², not already a park), capped at 3,000 m² with 60% canopy. Its effects:
  * canopy within 200 m rises by 0.6·A / (π·200²);
  * park area within 800 m rises by A;
  * park walk = network distance to the pocket edge.
* **Rooftop farm** on an HDB multi-storey car park in the town: Community in Bloom count within 400 m + 1.
* **Shaded walkway**: OSM ways with 30–400 m unshaded length, ranked by need-weighted use on residents' shortest heat-adjusted routes to the five daily needs. Effect: *s* = 1 on that way, then all access walks and route shade are recomputed.

**Packages.** Six tweaks are chosen greedily, at most three per type and at least 300 m apart, and re-evaluated cumulatively. Two orderings are compared:
* *average-first*: by Δ town score;
* *inclusion-aware*: by ½ Δ town score + ½ Δ mean score of the baseline worst-served 20%.

## 7. Robustness

* **Stakeholder lenses.** Saaty AHP matrices give the weights for each lens (consistency ratio < 0.01 for all). Spearman ρ of town ranks vs the default lens: senior 0.97, developer/lender 0.94, planner 0.80.
* **Weight uncertainty.** 2,000 Dirichlet draws centred on the defaults (concentration 40) give a 5–95% town rank band (Figure 4b).
* **Heat penalty.** α = 0 and α = 1 give block-score ρ ≥ 0.999; the maximum town shift is 0.57 points.

## 8. Developer case ([`case_gls_site/`](../case_gls_site))

A mixed-integer programme in Gurobi for a 14,433 m², 348-unit GLS condominium site in Woodlands (anonymised; public GLS award and launch figures).

**Decision variables.**
* Area of each of 10 greenery types (turf, shrubs, layered trees, native microforest, canopy over paths, bioswale, extensive and communal roofs, rooftop farm, green wall).
* Size and siting of up to three public cool-refuge pockets, at 8 site edges or next to nearby HDB blocks.

**Constraints.**
* URA landscape replacement (35% overall, 30% on ground) and Green Plot Ratio ≥ 3.5, with vertical and extensive greenery capped at 10% of site.
* Zone capacities and minimum viable sizes.
* A maintenance-fee cap of S$30 per unit per month.
* Two sustainability-linked-loan KPIs (microforest ≥ 300 m², urban farm ≥ 400 m²), mirroring the KPIs of a [2026 developer SLL](https://www.cdl.com.sg/newsroom/cdl-and-dbs-launch-s-300-million-multi-currency-sustainability-linked-loan-to-advance-nature-based-urban-development-solutions-in-singapore).

**Objective.** Maximise 30-year NPV = sale premium (concave, tangent cuts) + verified SLL step-down + farm rent + energy − life-cycle cost.

**Equity.** An ε-constraint on vulnerable-resident cooling exposure Σ *V*·exp(−*d*/150 m). In this repository *V* comes from the index (need × resilience shortfall). The knee of the Pareto frontier is chosen.

**Size.** 129 variables (64 binary) and 183 constraints, solved to proven optimality in milliseconds.

**Uncertainty.** 20,000 Monte Carlo draws over premium, upkeep, capex, cooling, SLL step-down (2.5–10 bps) and farm rent. A hierarchical normal model shows how verified sites narrow the forecast (the "flywheel").

Assumptions are tagged one by one in [`params.py`](../case_gls_site/src/params.py).

## References

Sobrino, J.A., Jiménez-Muñoz, J.C., Paolini, L. (2004). Land surface temperature retrieval from LANDSAT TM 5. *Remote Sensing of Environment* 90, 434–440.
Saaty, T.L. (1980). *The Analytic Hierarchy Process.* McGraw-Hill.
Other sources: see [`concept-brief.md`](concept-brief.md#sources) and [`DATA.md`](DATA.md).
