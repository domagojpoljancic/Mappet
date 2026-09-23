"""Unit tests for loop length + closure (T0.2)."""

from __future__ import annotations

import math

import networkx as nx

from mappet_spike.loops import Loop, generate_loops


def _grid_graph(n: int = 21, spacing_m: float = 50.0) -> tuple[nx.MultiDiGraph, tuple[float, float]]:
    """Synthetic walkable grid around Zagreb-ish coords for offline tests."""
    # metres → rough degrees at ~45°N
    dlat = spacing_m / 111_320.0
    dlng = spacing_m / (111_320.0 * math.cos(math.radians(45.81)))
    origin_lat, origin_lng = 45.8100, 15.9800
    half = n // 2

    g = nx.MultiDiGraph()
    node_id = {}
    for i in range(n):
        for j in range(n):
            lat = origin_lat + (i - half) * dlat
            lng = origin_lng + (j - half) * dlng
            nid = i * n + j
            node_id[(i, j)] = nid
            g.add_node(nid, y=lat, x=lng)

    for i in range(n):
        for j in range(n):
            u = node_id[(i, j)]
            for di, dj in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                ni, nj = i + di, j + dj
                if 0 <= ni < n and 0 <= nj < n:
                    v = node_id[(ni, nj)]
                    g.add_edge(
                        u,
                        v,
                        0,
                        highway="residential",
                        length=spacing_m,
                        pleasantness=0.7,
                        weight=spacing_m / 0.7,
                    )

    return g, (origin_lat, origin_lng)


def test_generate_loops_length_and_closure():
    g, origin = _grid_graph()
    # On a 50m grid, a ~2 km loop is feasible.
    loops = generate_loops(g, origin, distance_km=2.0, tolerance=0.20, n=80)

    assert len(loops) >= 10, f"expected many loops, got {len(loops)}"

    target = 2000.0
    lo, hi = target * 0.80, target * 1.20
    within = [lp for lp in loops if lo <= lp.length_m <= hi]
    assert len(within) / len(loops) >= 0.90

    for lp in loops:
        assert isinstance(lp, Loop)
        assert lp.polyline[0] == lp.polyline[-1] or (
            abs(lp.polyline[0][0] - lp.polyline[-1][0]) < 1e-8
            and abs(lp.polyline[0][1] - lp.polyline[-1][1]) < 1e-8
        )
        # Closure in metres via identical first/last node path.
        assert lp.nodes[0] == lp.nodes[-1]


def test_loops_are_deduplicated():
    g, origin = _grid_graph()
    loops = generate_loops(g, origin, distance_km=2.0, tolerance=0.20, n=40)
    hashes = [lp.geometry_hash for lp in loops]
    assert len(hashes) == len(set(hashes))
