"""Rebuild everything from open data, in order. Each step caches its downloads, so re-runs are fast.

    python run_all.py            # full pipeline
    python run_all.py --from index
"""
import subprocess
import sys

STEPS = [
    ("fetch", [sys.executable, "-m", "uri.fetch"]),                       # data.gov.sg datasets
    ("flood", [sys.executable, "scripts/geocode_flood.py"]),              # PUB flood-prone list -> points
    ("osm", [sys.executable, "-m", "uri.osm", "--pbf"]),                  # walking network (BBBike extract)
    ("wbgt", [sys.executable, "-m", "uri.wbgt"]),                         # NEA WBGT history
    ("satellite", [sys.executable, "-m", "uri.satellite"]),               # Landsat LST + Sentinel-2
    ("blocks", [sys.executable, "-m", "uri.blocks"]),                     # block table + need weights
    ("index", [sys.executable, "-m", "uri.index"]),                       # six pillars, scores, towns
    ("analysis", [sys.executable, "-m", "uri.analysis"]),                 # benchmark, drivers, value, robustness
    ("tweaks", [sys.executable, "-m", "uri.tweaks", "Woodlands"]),        # tweak engine
    ("case", [sys.executable, "case_gls_site/src/optimize.py"]),          # developer case: Gurobi MILP
    ("case_mc", [sys.executable, "case_gls_site/src/analysis.py"]),       # developer case: Monte Carlo
    ("figures", [sys.executable, "-m", "uri.figures"]),                   # paper figures
    ("web", [sys.executable, "-m", "uri.export_web"]),                    # website data + raster overlays
]

if __name__ == "__main__":
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else STEPS[0][0]
    names = [s[0] for s in STEPS]
    for name, cmd in STEPS[names.index(start):]:
        print(f"\n=== {name}: {' '.join(cmd[1:])}", flush=True)
        subprocess.run(cmd, check=True)
