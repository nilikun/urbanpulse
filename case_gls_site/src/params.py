"""All model inputs, each tagged with its source or marked as an assumption.

Currency: SGD, 2026 prices. Areas in m2.
"""
from dataclasses import dataclass

SQFT_PER_M2 = 10.7639

# --------------------------------------------------------------------------
# Reference site: a 99-year private condominium GLS site in Woodlands (awarded 2023), from public records
# --------------------------------------------------------------------------
SITE = dict(
    name="Reference GLS condominium site, Woodlands",
    area=14_433.0,                    # public project listing (155,351 sq ft)
    land_price=294.9e6,               # URA GLS award, 2023
    land_psf_ppr=904.0,               # S$ psf per plot ratio (GLS award)
    units=348,                        # developer launch release, 2024
    avg_psf=2_067.0,                  # developer release: average launch-weekend price
    blocks=4, storeys=11,             # developer release: four 11-storey blocks
    X=23272.40, Y=45585.87,           # OneMap SVY21 (site address)
    lat=1.428537, lon=103.790837,
)
SITE["gfa"] = SITE["land_price"] / SITE["land_psf_ppr"] / SQFT_PER_M2          # ~30,306 m2
SITE["gpr"] = SITE["gfa"] / SITE["area"]                                         # ~2.10
SITE["gdv"] = SITE["gfa"] * SQFT_PER_M2 * SITE["avg_psf"]                        # ~S$674M
SITE["footprint"] = SITE["gfa"] / SITE["storeys"]                                # ~2,755 m2

# URA Development Control Handbook, Flats & Condominiums, Greenery, Table 4
# (outside Strategic Areas, 1.4 < GPR < 2.8)
URA = dict(overall_pct=0.35, ground_pct=0.30, gnpr=3.5,
           vertical_extroof_cap_pct=0.10)   # Table 5: vertical + extensive roof count up to 10% of site

# Physical capacities (assumptions from site geometry)
CAP = dict(
    ground=SITE["area"] - SITE["footprint"] - 0.35 * SITE["area"],  # minus footprint and 35% hardscape (drives, pool deck, paths)
    roof=0.50 * SITE["footprint"],      # half the roof kept for M&E + PV (Green Mark Platinum SLE)
    facade=1_500.0,                     # publicly visible facade area suited to modular walls
    hard=0.35 * SITE["area"],          # canopy area that can overhang drives/paths (tree pits)
    edge_pocket=600.0,                  # max public-facing pocket area at one site edge
)

# --------------------------------------------------------------------------
# Greenery typologies
#  capex, om: S$/m2 and S$/m2/yr  | lai: leaf area index used for GnPR
#  tau: pedestrian-level cooling intensity (deg C, local daytime air temperature reduction)
#  amen: amenity weight for buyers (0-1) | bio: biodiversity weight (0-1)
# --------------------------------------------------------------------------
@dataclass
class Typ:
    key: str; label: str; zone: str
    capex: float; om: float; life_repl: tuple   # (year, fraction of capex) replacements
    lai: float; lra: bool; capped: bool          # counts as LRA; inside 10% vertical/extensive cap
    tau: float; amen: float; bio: float
    rent: float = 0.0; om_early: float = 0.0     # extra O&M in years 1-3 (establishment)

TYPES = [
    #   key       label                     zone     capex  om   repl          lai  lra   cap   tau  amen bio
    Typ("TURF",  "Turf lawn",              "ground",   25,  6, (),           2.0, True, False, 0.3, 0.2, 0.15),
    Typ("SHRUB", "Shrub & groundcover",    "ground",   90, 10, (),           4.0, True, False, 0.6, 0.35, 0.45),
    Typ("TREE",  "Layered shade-tree grove","ground", 220, 12, (),           7.0, True, False, 2.2, 1.0, 0.75),
    Typ("MICRO", "Native microforest",     "ground",  260,  5, (),           8.0, True, False, 3.0, 0.9, 1.0, om_early=13),
    Typ("TREEH", "Canopy trees over paths", "hard",     90,  4, (),           3.0, False, False, 1.5, 0.6, 0.4),
    Typ("SWALE", "Bioswale / rain garden", "ground",  280, 14, (),           3.5, True, False, 0.8, 0.6, 0.6),
    Typ("EXTR",  "Extensive green roof",   "roof",    180,  8, (),           2.0, True, True,  0.0, 0.0, 0.3),
    Typ("INTR",  "Communal roof garden",   "roof",    450, 25, (),           4.5, True, False, 1.0, 1.0, 0.55),
    Typ("FARM",  "Rooftop community farm", "roof",    300,  0, (),           0.0, False, False, 0.5, 0.8, 0.5, rent=15.0),
    Typ("WALL",  "Modular green wall",     "facade", 1200, 80, ((15, 0.40),), 3.0, True, True, 1.1, 0.5, 0.3),
]
T = {t.key: t for t in TYPES}

SOURCES_TYP = {
    "lai": "NParks LAI categories used in URA GnPR: turf 2.0; shrubs 3.5-4.5; trees 2.5/3.0/4.0 by canopy density (layered planting adds layers)",
    "capex_roof": "Developer-quoted S$150-400/m2 green roof for new buildings; NParks S$100-180/m2 (eco-business)",
    "capex_wall": "NParks: green walls typically S$1,000-1,500/m2",
    "om_wall": "Maintenance is the largest LCC share for green walls (systematic review); 6.7%/yr of capex assumed",
    "tau_tree": "Singapore park cool-island: mean daytime 2.21 C (2022 field study)",
    "tau_micro": "Singapore mall microforest: up to 5 C cooler, 70% more species (NUS study, 2026); 3.0 C used",
    "tau_wall": "Green wall: -1.1 C air at 1.5 m (Tan et al. 2014); surface up to -11.6 C (Wong et al. 2010)",
    "rent_farm": "SFA/HDB MSCP rooftop farm tenders 2020-21: S$11-24/m2/yr (median ~S$13.5)",
    "farm_lra": "Assumed NOT counted for LRA/GnPR (planters); conservative",
}

# --------------------------------------------------------------------------
# Finance
# --------------------------------------------------------------------------
FIN = dict(
    r=0.04,                 # real discount rate (assumption)
    horizon=30,             # whole-life horizon, years
    premium_max=0.010,      # max on-site greenery price premium, share of GDV (assumption; 1/3 of Belcher & Chisholm 2018 3% avg effect of vegetation)
    amen_sat=0.60,          # amenity-weighted greenery / site area at which premium saturates (assumption)
    loan_share=0.70,        # development loan / (land + construction) (assumption)
    build_cost=3_500.0,     # S$/m2 GFA construction (assumption)
    loan_avg_draw=0.60,     # average drawn share over tenor (assumption)
    loan_tenor=4,           # years to TOP (assumption)
    sll_bps=5.0,            # SLL margin step-down if KPIs verified (assumption; market practice 2.5-10 bps)
    sll_micro_min=300.0,    # KPI: microforest >= 300 m2 (mirrors a 2026 developer SLL KPI on microforests)
    sll_farm_min=400.0,     # KPI: urban farm >= 400 m2 (mirrors a 2026 developer SLL KPI on urban farming)
    mcst_cap=30.0,          # greenery O&M cap per unit per month, S$ (assumption: keeps fees acceptable)
    tariff=0.2859,          # SP Group household tariff Q4 2026, S$/kWh before GST
    roof_kwh=2.8,           # kWh/m2/yr saved under green roof (1-15% top-floor cooling-load saving, Singapore)
)
FIN["loan"] = FIN["loan_share"] * (SITE["land_price"] + FIN["build_cost"] * SITE["gfa"])
FIN["sll_value"] = FIN["loan"] * FIN["loan_avg_draw"] * FIN["sll_bps"] / 1e4 * FIN["loan_tenor"]

# --------------------------------------------------------------------------
# Spatial / people
# --------------------------------------------------------------------------
PEOPLE = dict(
    hh_size=3.0,            # persons per HDB household (assumption ~ SingStat GHS)
    share65=35_700 / 254_440,   # Woodlands planning area, 2025 (SingStat via citypopulation.de) = 14.0%
    rental_w=1.5,           # vulnerable persons per rental household (assumption)
    old_block_year=1990,    # older blocks: hotter interiors, more seniors (weight x1.3)
    old_block_w=1.3,
    lam=150.0,              # cooling distance-decay length, m (park cooling distance 100-200 m, avg 179 m)
    walk=400.0,             # walking catchment, m (URA/LTA 400 m threshold)
    radius=800.0,           # study neighbourhood radius, m
)

# --------------------------------------------------------------------------
# Business model (assumptions, benchmarked)
# --------------------------------------------------------------------------
BIZ = dict(
    pass_fee=80_000.0,      # one-off Project Pass per site
    monitor_fee=36_000.0,   # per development per year (S$8.6 per unit per month for 348 units)
    monitor_years=5,
    retrofit_fee=15_000.0,  # per existing building per year (SGIS-eligible retrofits)
    gls_units_2026=9_320,   # URA: 2026 Confirmed List supply (1H + 2H)
    gls_sites_2h2026=9,     # URA 2H2026 Confirmed List sites
)
