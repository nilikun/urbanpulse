"""Walking network with shade, and heat-adjusted walking distances.

Brief: "Shade feeds access only through heat-adjusted routes, so it is not counted twice."
Every network edge gets a shade share s in [0, 1]:
  s = 1      if OSM marks it covered / tunnel / indoor (covered linkways, void decks, underpasses)
  s = share of 10 m samples whose 3x3 Sentinel-2 neighbourhood (30 m) has NDVI > CANOPY_NDVI
           (tree canopy over or beside the path)
Heat-adjusted length = length * (1 + ALPHA * (1 - s)). ALPHA = 0.5 means an unshaded metre "feels"
like 1.5 shaded metres. This penalty is an assumption, not a measured value; it is exposed as
a parameter and tested in the sensitivity analysis.
"""
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy import sparse
from scipy.ndimage import maximum_filter
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
RAW, SAT, PROC = ROOT / "data" / "raw", ROOT / "data" / "satellite", ROOT / "data" / "processed"
ALPHA = 0.5
CANOPY_NDVI = 0.6
X0, Y1, RES = 2_000, 52_000, 10


class Network:
    def __init__(self, alpha=ALPHA):
        d = json.loads((RAW / "osm_walk.json").read_text())
        self.osm_timestamp = d["timestamp"]
        tf = Transformer.from_crs(4326, 3414, always_xy=True)
        ndvi = np.load(SAT / "s2_2024_2025.npz")["ndvi"]
        canopy = maximum_filter(np.nan_to_num(ndvi) > CANOPY_NDVI, size=3)
        H, W = canopy.shape

        key, xs, ys, U, V, L, S, cov, WID = {}, [], [], [], [], [], [], [], []

        def node(x, y):
            k = (round(x, 2), round(y, 2))
            if k not in key:
                key[k] = len(xs); xs.append(x); ys.append(y)
            return key[k]

        for w in d["ways"]:
            t = w["tags"]
            covered = t.get("covered") in ("yes", "arcade", "colonnade") or t.get("tunnel") in ("yes", "building_passage") \
                or t.get("indoor") == "yes" or t.get("highway") == "corridor"
            lon, lat = zip(*w["geom"])
            X, Y = tf.transform(np.array(lon), np.array(lat))
            for i in range(len(X) - 1):
                a, b = node(X[i], Y[i]), node(X[i + 1], Y[i + 1])
                if a == b:
                    continue
                seg = float(np.hypot(X[i + 1] - X[i], Y[i + 1] - Y[i]))
                if covered:
                    s = 1.0
                else:
                    n = max(2, int(seg / 10) + 1)
                    px = np.linspace(X[i], X[i + 1], n); py = np.linspace(Y[i], Y[i + 1], n)
                    c = ((px - X0) / RES).astype(int); r = ((Y1 - py) / RES).astype(int)
                    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
                    s = float(canopy[r[ok], c[ok]].mean()) if ok.any() else 0.0
                U.append(a); V.append(b); L.append(seg); S.append(s); cov.append(covered); WID.append(w["id"])
        self.x, self.y = np.array(xs), np.array(ys)
        self.u, self.v = np.array(U), np.array(V)
        self.length, self.shade, self.covered, self.way = np.array(L), np.array(S), np.array(cov), np.array(WID)
        self.mx, self.my = (self.x[self.u] + self.x[self.v]) / 2, (self.y[self.u] + self.y[self.v]) / 2
        self.mid_tree = cKDTree(np.c_[self.mx, self.my])
        self.set_alpha(alpha)
        # snap only to the largest connected component (isolated OSM fragments would give infinite distances)
        _, lab = connected_components(self.G, directed=False)
        self.giant = np.flatnonzero(lab == np.bincount(lab).argmax())
        self.tree = cKDTree(np.c_[self.x[self.giant], self.y[self.giant]])

    def set_alpha(self, alpha, shade=None):
        s = self.shade if shade is None else shade
        w = self.length * (1 + alpha * (1 - s))
        n = len(self.x)
        a, b = np.minimum(self.u, self.v), np.maximum(self.u, self.v)
        order = np.lexsort((w, b, a))                       # duplicate (a, b) pairs: keep the shortest
        a, b, w = a[order], b[order], w[order]
        first = np.r_[True, (a[1:] != a[:-1]) | (b[1:] != b[:-1])]
        a, b, w = a[first], b[first], w[first]
        self.G = sparse.coo_matrix((np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
        return self.G

    def snap(self, px, py, max_d=300.0):
        d, i = self.tree.query(np.c_[px, py])
        return self.giant[i], d

    def dist_to_nearest(self, src_x, src_y, dst_x, dst_y, G=None, limit=np.inf):
        """Heat-adjusted network distance from every destination point to the nearest source point
        (multi-source Dijkstra on the undirected graph). Snapping offsets are added as straight lines."""
        si, sd = self.snap(src_x, src_y)
        di, dd = self.snap(dst_x, dst_y)
        D = dijkstra(G if G is not None else self.G, directed=False, indices=np.unique(si), min_only=True, limit=limit)
        return D[di] + dd + np.median(sd)

    def shade_share_within(self, px, py, r=400.0):
        """Length-weighted shaded share of all walkable edges whose midpoint lies within r of each point."""
        out = np.empty(len(px))
        for k, idx in enumerate(self.mid_tree.query_ball_point(np.c_[px, py], r)):
            idx = np.asarray(idx, int)
            out[k] = (self.length[idx] * self.shade[idx]).sum() / max(self.length[idx].sum(), 1.0)
        return out

    def summary(self):
        return dict(nodes=len(self.x), edges=len(self.u), giant_nodes=len(self.giant), km=round(self.length.sum() / 1e3),
                    covered_km=round(self.length[self.covered].sum() / 1e3),
                    shaded_share=round(float((self.length * self.shade).sum() / self.length.sum()), 3),
                    osm_timestamp=self.osm_timestamp)


if __name__ == "__main__":
    net = Network()
    print(net.summary())
