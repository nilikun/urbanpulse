"""Tweak engine: specific nature-based changes for one town, each with the score it would add.

Brief, step 4: "the model proposes specific nature-based changes with their score gain (e.g. 'green
pocket at site X: +6 access, 42 more rental households reached'); the user accepts or rejects each."

Three tweak types, each touching only the indicators it physically changes:
  shade_walkway  Shade an unshaded walkway that many residents use to reach daily needs
                 (covered linkway or tree-lining)       -> access (heat-adjusted walks), route shade
  green_pocket   Plant a pocket park on a URA Master Plan 2025 'Reserve site' / 'Open space' parcel
                 near the blocks                        -> park walk, park area, canopy within 200 m
  rooftop_farm   Community farm on an HDB multi-storey car-park roof (HDB has tendered MSCP roofs to
                 urban farms since 2020)                -> community gardens within 400 m
Scores are re-computed against the fixed island-wide reference, so a gain is a real move up the
national distribution, not a re-ranking. Sizes and canopy shares below are design assumptions.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from .blocks import street_code_table
from .index import INDICATORS, IND, Scorer, inclusion_gap, load_points
from .network import Network

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC = ROOT / "data" / "raw", ROOT / "data" / "processed"
CRS = "EPSG:3414"
POCKET_MAX_M2, POCKET_CANOPY = 3_000.0, 0.6      # pocket size cap and planted canopy share (assumptions)
WALKWAY_MIN, WALKWAY_MAX = 30.0, 400.0           # unshaded length of a walkway worth shading, m
ACCESS = [("walk_aac", "eldercare.geojson"), ("walk_clinic", "chas_clinics.geojson"),
          ("walk_hawker", "hawker_centres.geojson"), ("walk_mrt", "mrt_exits.geojson"), ("walk_bus", "bus_stops.geojson")]
TO_LL = Transformer.from_crs(3414, 4326, always_xy=True)


class Engine:
    def __init__(self, town="Woodlands", alpha=0.5):
        allb = gpd.read_file(PROC / "blocks_scored.gpkg")
        self.ref = allb[[i.key for i in INDICATORS]]
        self.scorer = Scorer(self.ref)
        self.b = allb[allb.town == town].reset_index(drop=True)
        self.town, self.alpha = town, alpha
        self.bx, self.by = self.b.geometry.x.values, self.b.geometry.y.values
        self.net = Network()
        self.shade = self.net.shade.copy()
        self.sources = {k: load_points(f) for k, f in ACCESS}
        self.base = self.b[[i.key for i in INDICATORS]].copy()
        # screening weight: need x resilience shortfall, so candidates are searched where the worst-served live
        self.wt = self.b.need.values * (100 - self.b.score.values) / 50
        self.state = self.base.copy()

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, ind):
        s = self.scorer.score(ind)
        w = self.b.need.values
        return dict(score=float(np.average(s.score, weights=w)), gap=inclusion_gap(s.score),
                    pillars={p: float(np.average(s[p], weights=w)) for p in ("heat", "shade", "green", "community", "access", "flood")},
                    block_scores=s.score.values)

    def reached(self, before, after, thr=0.5):
        m = (after - before) >= thr
        return dict(blocks=int(m.sum()), rental_households=int(self.b.rental[m].sum()),
                    seniors=int(round(self.b.seniors[m].sum())), households=int(self.b.units[m].sum()))

    # ------------------------------------------------------------------ access with a given shade vector
    def access(self, shade):
        G = self.net.set_alpha(self.alpha, shade)
        out = {}
        for k, p in self.sources.items():
            out[k] = self.net.dist_to_nearest(p[:, 0], p[:, 1], self.bx, self.by, G=G)
        return out

    # ------------------------------------------------------------------ candidates
    def walkway_candidates(self, n=12):
        """Unshaded ways most used on residents' shortest heat-adjusted walks to the 5 daily needs,
        weighted by block need."""
        G = self.net.set_alpha(self.alpha, self.shade)
        use = np.zeros(len(self.net.u))
        eid = {}
        for i, (a, b) in enumerate(zip(self.net.u, self.net.v)):
            eid[(a, b)] = eid[(b, a)] = i
        bi, _ = self.net.snap(self.bx, self.by)
        for k, p in self.sources.items():
            si, _ = self.net.snap(p[:, 0], p[:, 1])
            _, pred, _ = dijkstra(G, directed=False, indices=np.unique(si), min_only=True, return_predecessors=True)
            for node, w in zip(bi, self.wt):
                steps = 0
                while pred[node] >= 0 and steps < 3000:
                    e = eid.get((node, pred[node]))
                    if e is not None:
                        use[e] += w
                    node = pred[node]; steps += 1
        df = pd.DataFrame(dict(way=self.net.way, use=use, L=self.net.length, s=self.shade,
                               mx=self.net.mx, my=self.net.my))
        df["unshaded_m"] = df.L * (1 - df.s)
        g = df[df.use > 0].groupby("way").agg(use=("use", "max"), unshaded_m=("unshaded_m", "sum"),
                                                length=("L", "sum"), mx=("mx", "mean"), my=("my", "mean"))
        g = g[(g.unshaded_m >= WALKWAY_MIN) & (g.unshaded_m <= WALKWAY_MAX)]
        g["priority"] = g.use * g.unshaded_m
        return g.sort_values("priority", ascending=False).head(n).reset_index()

    def pocket_candidates(self, n=12):
        lu = gpd.read_file(RAW / "landuse_mp2025_subset.gpkg")
        lu = lu[lu.LU_DESC.isin(["RESERVE SITE", "OPEN SPACE"])].to_crs(CRS)
        hull = gpd.GeoSeries(self.b.geometry, crs=CRS).union_all().convex_hull.buffer(200)
        lu = lu[lu.intersects(hull)].copy()
        lu["area"] = lu.area
        lu = lu[lu.area >= 1_000]
        parks = gpd.read_file(RAW / "nparks_parks_reserves.geojson").to_crs(CRS)
        lu = lu[~lu.representative_point().within(parks.union_all())]
        pts = lu.representative_point()
        lu["px"], lu["py"] = pts.x, pts.y
        d = np.hypot(self.bx[None, :] - lu.px.values[:, None], self.by[None, :] - lu.py.values[:, None])
        lu["need400"] = (np.where(d <= 400, 1, 0) * self.wt[None, :]).sum(1)
        return lu.sort_values("need400", ascending=False).head(n).reset_index(drop=True)

    def farm_candidates(self, n=12):
        pi = json.loads((RAW / "hdb_property_info.json").read_text())
        fp = gpd.read_file(RAW / "hdb_buildings.geojson").set_crs(4326, allow_override=True).to_crs(CRS)
        fp["BLK_NO"] = fp.BLK_NO.astype(str).str.upper()
        table = street_code_table(fp, pi)
        cent = {(r.ST_COD, r.BLK_NO): (r.geometry.centroid.x, r.geometry.centroid.y, r.geometry.area) for _, r in fp.iterrows()}
        rows = []
        for r in pi:
            if r["multistorey_carpark"] == "Y" and r["residential"] == "N" and r["bldg_contract_town"] == self.b.town_code.iloc[0]:
                c = cent.get((table.get(r["street"], (None,))[0], r["blk_no"].upper()))
                if c:
                    rows.append(dict(blk=r["blk_no"], street=r["street"], px=c[0], py=c[1], roof_m2=c[2]))
        df = pd.DataFrame(rows)
        d = np.hypot(self.bx[None, :] - df.px.values[:, None], self.by[None, :] - df.py.values[:, None])
        df["need400"] = (np.where(d <= 400, 1, 0) * self.wt[None, :]).sum(1)
        return df.sort_values("need400", ascending=False).head(n).reset_index(drop=True)

    # ------------------------------------------------------------------ effects
    def apply_walkway(self, ind, shade, way):
        sh = shade.copy(); sh[self.net.way == way] = 1.0
        new = ind.copy()
        for k, v in self.access(sh).items():
            new[k] = np.minimum(new[k].values, v)
        idx = self.net.mid_tree.query_ball_point(np.c_[self.bx, self.by], 400)
        new["route_shade400"] = [100 * (self.net.length[i] * sh[i]).sum() / max(self.net.length[i].sum(), 1) for i in map(np.asarray, idx)]
        return new, sh

    def apply_pocket(self, ind, px, py, area):
        A = min(area, POCKET_MAX_M2)
        d = np.hypot(self.bx - px, self.by - py)
        new = ind.copy()
        new["canopy200"] = ind.canopy200 + np.where(d <= 200, 100 * POCKET_CANOPY * A / (np.pi * 200 ** 2), 0)
        new["park_area800"] = ind.park_area800 + np.where(d <= 800, A / 1e4, 0)
        G0 = self.net.set_alpha(0.0)
        si, sd = self.net.snap([px], [py])
        bi, bd = self.net.snap(self.bx, self.by)
        D = dijkstra(G0, directed=False, indices=si[0], limit=3000)
        walk = D[bi] + bd + sd[0] - np.sqrt(A / np.pi)       # to the pocket edge, not its centre
        new["park_walk"] = np.minimum(ind.park_walk.values, np.maximum(walk, 10))
        return new

    def apply_farm(self, ind, px, py):
        d = np.hypot(self.bx - px, self.by - py)
        new = ind.copy()
        new["gardens400"] = ind.gardens400 + (d <= 400)
        return new

    # ------------------------------------------------------------------ run
    def run(self, n_each=15, package=6, max_per_type=3):
        base = self.evaluate(self.base)
        cands = []
        for _, r in self.walkway_candidates(n_each).iterrows():
            new, _ = self.apply_walkway(self.base, self.shade, r.way)
            cands.append(dict(type="shade_walkway", ref=int(r.way), x=r.mx, y=r.my,
                              label=f"Shade {r.unshaded_m:.0f} m of walkway (OSM way {int(r.way)})",
                              size=round(float(r.unshaded_m)), new=new))
        for _, r in self.pocket_candidates(n_each).iterrows():
            A = min(r.area, POCKET_MAX_M2)
            cands.append(dict(type="green_pocket", ref=f"{r.LU_DESC} parcel", x=r.px, y=r.py,
                              label=f"{A:,.0f} m2 green pocket on {'an' if r.LU_DESC.lower()[0] in 'aeiou' else 'a'} {r.LU_DESC.lower()} parcel", size=round(A),
                              new=self.apply_pocket(self.base, r.px, r.py, r.area)))
        for _, r in self.farm_candidates(n_each).iterrows():
            cands.append(dict(type="rooftop_farm", ref=f"MSCP {r.blk} {r.street}", x=r.px, y=r.py,
                              label=f"Community rooftop farm on car park {r.blk} {r.street.title()}",
                              size=round(float(r.roof_m2)), new=self.apply_farm(self.base, r.px, r.py)))
        out = []
        for c in cands:
            ev = self.evaluate(c["new"])
            lon, lat = TO_LL.transform(c["x"], c["y"])
            out.append(dict(type=c["type"], label=c["label"], ref=c["ref"], size=c["size"], lon=lon, lat=lat,
                            d_score=ev["score"] - base["score"], d_gap=ev["gap"] - base["gap"],
                            d_pillars={p: ev["pillars"][p] - base["pillars"][p] for p in base["pillars"]},
                            **self.reached(base["block_scores"], ev["block_scores"])))
        worst = base["block_scores"] <= np.quantile(base["block_scores"], 0.2)   # baseline worst-served 20%
        for c, o in zip(cands, out):
            o["d_worst20"] = float(self.evaluate(c["new"])["block_scores"][worst].mean() - base["block_scores"][worst].mean())
            o["inclusive_gain"] = 0.5 * o["d_score"] + 0.5 * o["d_worst20"]

        def build_package(order):
            state, shade, chosen, steps = self.base.copy(), self.shade.copy(), [], []
            for i in order:
                if len(chosen) == package:
                    break
                c = cands[i]
                if any(out[i]["type"] == out[j]["type"] and np.hypot(c["x"] - cands[j]["x"], c["y"] - cands[j]["y"]) < 300
                       for j in chosen):
                    continue                                # spread the package: no two of a kind within 300 m
                if sum(out[j]["type"] == out[i]["type"] for j in chosen) >= max_per_type:
                    continue                                # each type is delivered by a different agency / budget line
                if c["type"] == "shade_walkway":
                    state, shade = self.apply_walkway(state, shade, c["ref"])
                elif c["type"] == "green_pocket":
                    state = self.apply_pocket(state, c["x"], c["y"], c["size"])
                else:
                    state = self.apply_farm(state, c["x"], c["y"])
                chosen.append(i)
                ev = self.evaluate(state)
                steps.append(dict(step=len(chosen), candidate=i, score=ev["score"], gap=ev["gap"],
                                  worst20=float(ev["block_scores"][worst].mean())))
            final = self.evaluate(state)
            return dict(package=[out[i] for i in chosen], steps=steps,
                        final={k: v for k, v in final.items() if k != "block_scores"},
                        worst20=float(final["block_scores"][worst].mean()),
                        reach=self.reached(base["block_scores"], final["block_scores"])), final["block_scores"]

        avg_pkg, avg_scores = build_package(sorted(range(len(out)), key=lambda i: -out[i]["d_score"]))
        inc_pkg, inc_scores = build_package(sorted(range(len(out)), key=lambda i: -out[i]["inclusive_gain"]))
        blocks_out = self.b[["block_id", "blk", "street", "units", "rental", "seniors", "need"]].copy()
        blocks_out["score_before"] = base["block_scores"]
        blocks_out["score_after_average"] = avg_scores
        blocks_out["score_after_inclusive"] = inc_scores
        blocks_out["worst20"] = worst
        lon, lat = TO_LL.transform(self.bx, self.by)
        blocks_out["lon"], blocks_out["lat"] = lon, lat
        res = dict(town=self.town, alpha=self.alpha, package_rules=dict(size=package, max_per_type=max_per_type, min_spacing_m=300), baseline={k: v for k, v in base.items() if k != "block_scores"},
                   baseline_worst20=float(base["block_scores"][worst].mean()),
                   candidates=sorted(out, key=lambda o: -o["inclusive_gain"]),
                   average_first=avg_pkg, inclusion_aware=inc_pkg)
        (PROC / f"tweaks_{self.town.lower().replace('/', '_')}.json").write_text(json.dumps(res, indent=1, default=float))
        blocks_out.to_csv(PROC / f"tweaks_{self.town.lower().replace('/', '_')}_blocks.csv", index=False)
        for name, pk in (("average-first", avg_pkg), ("inclusion-aware", inc_pkg)):
            print(f"{self.town} [{name}]: score {base['score']:.1f} -> {pk['final']['score']:.1f}, gap {base['gap']:.1f} -> "
                  f"{pk['final']['gap']:.1f}, worst-20% {res['baseline_worst20']:.1f} -> {pk['worst20']:.1f}, reach {pk['reach']}")
            for c in pk["package"]:
                print(f"  {c['type']:14s} {c['d_score']:+.2f} worst20 {c['d_worst20']:+.2f}  rental hh {c['rental_households']:5d}  {c['label']}")
        return res


if __name__ == "__main__":
    import sys
    Engine(sys.argv[1] if len(sys.argv) > 1 else "Woodlands").run()
