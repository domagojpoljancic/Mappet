"""Candidate loop generators — out-back, multi-waypoint, random-walk (T0.2/T0.6)."""

from __future__ import annotations

import hashlib
import logging
import math
import random
from dataclasses import dataclass
from typing import Any, Sequence

import networkx as nx

from mappet_spike.graph import haversine_m, nearest_node

logger = logging.getLogger(__name__)

QUIET_HIGHWAYS = frozenset(
    {
        "path",
        "footway",
        "pedestrian",
        "living_street",
        "residential",
        "track",
        "cycleway",
        "steps",
        "service",
    }
)


@dataclass
class Loop:
    """A closed candidate route as an ordered lat/lng polyline."""

    nodes: list[Any]
    polyline: list[tuple[float, float]]  # (lat, lng)
    length_m: float
    bearing_deg: float | None = None
    strategy: str = "out_back"

    @property
    def geometry_hash(self) -> str:
        pts = [
            (round(lat, 4), round(lng, 4))
            for lat, lng in self.polyline[:: max(1, len(self.polyline) // 32)]
        ]
        raw = repr(pts).encode()
        return hashlib.sha1(raw).hexdigest()[:12]


def _node_latlng(graph: nx.Graph, node: Any) -> tuple[float, float]:
    data = graph.nodes[node]
    return float(data["y"]), float(data["x"])


def _path_length_m(graph: nx.Graph, nodes: Sequence[Any]) -> float:
    total = 0.0
    for u, v in zip(nodes, nodes[1:]):
        edges = graph.get_edge_data(u, v)
        if not edges:
            return float("inf")
        best = min(float(d.get("length", 1.0)) for d in edges.values())
        total += best
    return total


def _path_polyline(graph: nx.Graph, nodes: Sequence[Any]) -> list[tuple[float, float]]:
    return [_node_latlng(graph, n) for n in nodes]


def _destination_point(
    lat: float, lng: float, bearing_deg: float, distance_m: float
) -> tuple[float, float]:
    r = 6_371_000.0
    br = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lng1 = math.radians(lng)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_m / r)
        + math.cos(lat1) * math.sin(distance_m / r) * math.cos(br)
    )
    lng2 = lng1 + math.atan2(
        math.sin(br) * math.sin(distance_m / r) * math.cos(lat1),
        math.cos(distance_m / r) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lng2)


def _shortest_path_weighted(
    graph: nx.Graph, source: Any, target: Any, weight: str = "weight"
) -> list[Any] | None:
    try:
        return nx.shortest_path(graph, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _penalise_edges(
    graph: nx.Graph, nodes: Sequence[Any], factor: float = 4.0
) -> dict[tuple[Any, Any, Any], float]:
    originals: dict[tuple[Any, Any, Any], float] = {}
    for u, v in zip(nodes, nodes[1:]):
        edges = graph.get_edge_data(u, v) or {}
        for k, data in edges.items():
            key = (u, v, k)
            if key not in originals:
                originals[key] = float(data.get("weight", data.get("length", 1.0)))
            data["weight"] = originals[key] * factor
            rev = graph.get_edge_data(v, u) or {}
            for rk, rdata in rev.items():
                rkey = (v, u, rk)
                if rkey not in originals:
                    originals[rkey] = float(rdata.get("weight", rdata.get("length", 1.0)))
                rdata["weight"] = originals[rkey] * factor
    return originals


def _restore_weights(
    graph: nx.Graph, originals: dict[tuple[Any, Any, Any], float]
) -> None:
    for (u, v, k), w in originals.items():
        if graph.has_edge(u, v, k):
            graph[u][v][k]["weight"] = w


def _edge_overlap_ratio(a: Sequence[Any], b: Sequence[Any]) -> float:
    def edges(nodes: Sequence[Any]) -> set[tuple[Any, Any]]:
        out: set[tuple[Any, Any]] = set()
        for u, v in zip(nodes, nodes[1:]):
            out.add((u, v) if u <= v else (v, u))
        return out

    ea, eb = edges(a), edges(b)
    if not ea:
        return 1.0
    return len(ea & eb) / len(ea)


def _to_undirected_multi(graph: nx.MultiDiGraph) -> nx.MultiGraph:
    g = nx.MultiGraph()
    for node, data in graph.nodes(data=True):
        g.add_node(node, **data)
    for u, v, _k, data in graph.edges(keys=True, data=True):
        length = float(data.get("length") or 1.0)
        pleasant = float(data.get("pleasantness") or 0.55)
        weight = float(data.get("weight") or (length / max(pleasant, 0.05)))
        attrs = {
            "length": length,
            "pleasantness": pleasant,
            "weight": weight,
            "highway": data.get("highway"),
        }
        if g.has_edge(u, v):
            existing = g.get_edge_data(u, v)
            best_existing = min(float(d.get("weight", 1e18)) for d in existing.values())
            if weight >= best_existing:
                continue
        g.add_edge(u, v, **attrs)
    return g


def _highway_str(hw: Any) -> str | None:
    if hw is None:
        return None
    if isinstance(hw, list):
        return str(hw[0]) if hw else None
    return str(hw)


def _node_quiet_score(graph: nx.Graph, node: Any) -> float:
    """Average pleasantness of incident edges — proxy for park/quiet preference."""
    total = 0.0
    count = 0
    for _, _, data in graph.edges(node, data=True):
        total += float(data.get("pleasantness") or 0.55)
        hw = _highway_str(data.get("highway"))
        if hw in QUIET_HIGHWAYS:
            total += 0.15
        count += 1
    return (total / count) if count else 0.5


def _maybe_add(
    loops: list[Loop],
    seen: set[str],
    graph: nx.Graph,
    nodes: list[Any],
    *,
    lo: float,
    hi: float,
    closure_m: float,
    bearing: float | None,
    strategy: str,
    limit: int,
) -> bool:
    if len(loops) >= limit:
        return False
    if not nodes or nodes[0] != nodes[-1]:
        return False
    length = _path_length_m(graph, nodes)
    if not (lo <= length <= hi):
        return False
    start = _node_latlng(graph, nodes[0])
    end = _node_latlng(graph, nodes[-1])
    if haversine_m(start[0], start[1], end[0], end[1]) > closure_m:
        return False
    poly = _path_polyline(graph, nodes)
    loop = Loop(
        nodes=nodes,
        polyline=poly,
        length_m=length,
        bearing_deg=bearing,
        strategy=strategy,
    )
    if loop.geometry_hash in seen:
        return False
    seen.add(loop.geometry_hash)
    loops.append(loop)
    return True


def _generate_out_back(
    g: nx.MultiGraph,
    graph_wgs: nx.MultiDiGraph,
    origin_node: Any,
    lat: float,
    lng: float,
    *,
    target_m: float,
    lo: float,
    hi: float,
    closure_m: float,
    rng: random.Random,
    loops: list[Loop],
    seen: set[str],
    quota: int,
) -> int:
    half = target_m / 2.0
    try:
        dist_from_origin = nx.single_source_dijkstra_path_length(
            g, origin_node, weight="length"
        )
    except Exception:
        dist_from_origin = {}

    band_lo, band_hi = half * 0.55, half * 1.35
    band_nodes = [
        node
        for node, d in dist_from_origin.items()
        if band_lo <= d <= band_hi and node != origin_node
    ]
    band_nodes.sort(key=lambda nd: _node_quiet_score(g, nd), reverse=True)

    bearings = [i * (360.0 / max(quota, 1)) for i in range(max(quota, 1))]
    radius_factors = [0.65, 0.8, 0.95, 1.1, 1.25]
    penalty_factors = [4.0, 8.0, 16.0]
    attempts = 0
    max_attempts = max(quota * 10, 400)
    limit = len(loops) + quota

    def try_anchor(anchor: Any, bearing: float | None) -> None:
        nonlocal attempts
        if len(loops) >= limit or attempts >= max_attempts:
            return
        if anchor == origin_node:
            return
        attempts += 1
        out_path = _shortest_path_weighted(g, origin_node, anchor)
        if not out_path or len(out_path) < 2:
            return
        for factor in penalty_factors:
            if len(loops) >= limit or attempts >= max_attempts:
                return
            originals = _penalise_edges(g, out_path, factor=factor)
            try:
                back_path = _shortest_path_weighted(g, anchor, origin_node)
            finally:
                _restore_weights(g, originals)
            if not back_path or len(back_path) < 2:
                continue
            if _edge_overlap_ratio(out_path, list(reversed(back_path))) > 0.55:
                continue
            nodes = list(out_path) + list(back_path[1:])
            if _maybe_add(
                loops,
                seen,
                g,
                nodes,
                lo=lo,
                hi=hi,
                closure_m=closure_m,
                bearing=bearing,
                strategy="out_back",
                limit=limit,
            ):
                return

    for bearing in bearings:
        if len(loops) >= limit or attempts >= max_attempts:
            break
        for rf in radius_factors:
            dest_lat, dest_lng = _destination_point(lat, lng, bearing, half * rf)
            try:
                anchor = nearest_node(graph_wgs, dest_lat, dest_lng)
            except Exception:
                continue
            try_anchor(anchor, bearing)

    for anchor in band_nodes:
        if len(loops) >= limit or attempts >= max_attempts:
            break
        try_anchor(anchor, None)

    return attempts


def _generate_multi_waypoint(
    g: nx.MultiGraph,
    graph_wgs: nx.MultiDiGraph,
    origin_node: Any,
    lat: float,
    lng: float,
    *,
    target_m: float,
    lo: float,
    hi: float,
    closure_m: float,
    rng: random.Random,
    loops: list[Loop],
    seen: set[str],
    quota: int,
) -> int:
    """Polygonal circuits via waypoints on a circle — fatter blob shapes."""
    attempts = 0
    max_attempts = max(quota * 25, 500)
    limit = len(loops) + quota
    base_radius = target_m / (2.0 * math.pi)

    while len(loops) < limit and attempts < max_attempts:
        attempts += 1
        k = rng.choice([2, 2, 3, 3, 4])
        radius_m = base_radius * rng.uniform(0.75, 1.35)
        stretch = rng.uniform(0.85, 1.25)
        base_bearing = rng.uniform(0, 360)
        waypoints: list[Any] = []
        for i in range(k):
            bearing = (base_bearing + i * (360.0 / k) + rng.uniform(-18, 18)) % 360
            r = radius_m * (stretch if i % 2 == 0 else 1.0 / stretch)
            dlat, dlng = _destination_point(lat, lng, bearing, r)
            try:
                wp = nearest_node(graph_wgs, dlat, dlng)
            except Exception:
                wp = None
            if wp is None or wp == origin_node or wp in waypoints:
                continue
            waypoints.append(wp)
        if len(waypoints) < 2:
            continue

        quiet = sum(_node_quiet_score(g, wp) for wp in waypoints) / len(waypoints)
        if quiet < 0.50 and rng.random() < 0.35:
            continue

        chain = [origin_node] + waypoints + [origin_node]
        nodes: list[Any] = [origin_node]
        used: list[Any] = []
        ok = True
        for a, b in zip(chain, chain[1:]):
            originals = _penalise_edges(g, used, factor=5.0) if used else {}
            try:
                seg = _shortest_path_weighted(g, a, b)
            finally:
                if originals:
                    _restore_weights(g, originals)
            if not seg or len(seg) < 2:
                ok = False
                break
            nodes.extend(seg[1:])
            used.extend(seg)
        if not ok:
            continue

        _maybe_add(
            loops,
            seen,
            g,
            nodes,
            lo=lo,
            hi=hi,
            closure_m=closure_m,
            bearing=base_bearing,
            strategy="multi_waypoint",
            limit=limit,
        )

    return attempts


def _generate_random_walk(
    g: nx.MultiGraph,
    origin_node: Any,
    *,
    target_m: float,
    lo: float,
    hi: float,
    closure_m: float,
    rng: random.Random,
    loops: list[Loop],
    seen: set[str],
    quota: int,
) -> int:
    """Pleasantness-biased walk that homes when projected length enters [lo, hi].

    At each step prefer edges that keep (spent + edge + return_home) near the
    target. Close as soon as the projected length falls inside tolerance.
    """
    attempts = 0
    max_attempts = max(quota * 25, 500)
    limit = len(loops) + quota
    try:
        return_dist = nx.single_source_dijkstra_path_length(
            g, origin_node, weight="length"
        )
    except Exception:
        return_dist = {origin_node: 0.0}

    while len(loops) < limit and attempts < max_attempts:
        attempts += 1
        path = [origin_node]
        length = 0.0
        visited_edges: set[tuple[Any, Any]] = set()
        closed = False

        for _step in range(600):
            cur = path[-1]
            back = float(return_dist.get(cur, float("inf")))

            # Close as soon as going home lands in the tolerance band.
            if (
                cur != origin_node
                and back < float("inf")
                and lo <= length + back <= hi
                and length >= lo * 0.35
            ):
                home = _shortest_path_weighted(g, cur, origin_node, weight="length")
                if home and len(home) >= 2:
                    path.extend(home[1:])
                    closed = True
                    break

            # Already too long even if we teleport home — abort.
            if back < float("inf") and length + back > hi and length > target_m * 0.3:
                break

            candidates = []
            for nbr in g.neighbors(cur):
                if nbr == origin_node and length < lo * 0.4:
                    continue
                edge_key = (cur, nbr) if cur <= nbr else (nbr, cur)
                revisit_pen = 0.15 if edge_key in visited_edges else 1.0
                edges = g.get_edge_data(cur, nbr) or {}
                best = min(edges.values(), key=lambda d: float(d.get("weight", 1.0)))
                elen = float(best.get("length") or 1.0)
                pleasant = float(best.get("pleasantness") or 0.55)
                nbr_back = float(return_dist.get(nbr, float("inf")))
                if nbr_back == float("inf"):
                    continue
                projected = length + elen + nbr_back
                # How close is projected length to the target?
                err = abs(projected - target_m) / target_m
                if projected > hi * 1.05:
                    continue
                # Score: prefer near-target projection + pleasant edges.
                score = (pleasant ** 1.5) * revisit_pen / (0.15 + err)
                # Bonus if taking this edge would let us close immediately after.
                if lo <= projected <= hi:
                    score *= 3.0
                candidates.append((nbr, elen, edge_key, score, projected))

            if not candidates:
                break

            # Mostly pick by score; occasionally explore.
            if rng.random() < 0.15:
                pick = rng.choice(candidates)
            else:
                weights = [max(s, 1e-6) for _, _, _, s, _ in candidates]
                pick = rng.choices(candidates, weights=weights, k=1)[0]

            nbr, elen, edge_key, _score, _proj = pick
            path.append(nbr)
            length += elen
            visited_edges.add(edge_key)
            if length > hi:
                break

        if not closed:
            continue
        _maybe_add(
            loops,
            seen,
            g,
            path,
            lo=lo,
            hi=hi,
            closure_m=closure_m,
            bearing=None,
            strategy="random_walk",
            limit=limit,
        )

    return attempts


def generate_loops(
    graph: nx.MultiDiGraph,
    origin: tuple[float, float],
    distance_km: float,
    tolerance: float = 0.15,
    n: int = 200,
    *,
    closure_m: float = 40.0,
    seed: int = 42,
) -> list[Loop]:
    """Generate up to n distinct loops near `distance_km` that close at origin.

    Mixes three strategies (T0.6) with reserved quotas:
    - out-and-different-back across bearings (quiet-biased band fill)
    - multi-waypoint polygonal circuits (fatter shapes)
    - pleasantness-biased random walks that home when budget is spent
    """
    rng = random.Random(seed)
    lat, lng = origin
    target_m = distance_km * 1000.0
    lo, hi = target_m * (1.0 - tolerance), target_m * (1.0 + tolerance)

    origin_node = nearest_node(graph, lat, lng)
    o_lat, o_lng = _node_latlng(graph, origin_node)
    if haversine_m(lat, lng, o_lat, o_lng) > closure_m * 3:
        logger.warning(
            "Nearest graph node is far from origin (%.0fm)",
            haversine_m(lat, lng, o_lat, o_lng),
        )

    g = _to_undirected_multi(graph)
    loops: list[Loop] = []
    seen: set[str] = set()

    q_out = max(1, n // 3)
    q_multi = max(1, n // 3)
    q_walk = max(1, n - q_out - q_multi)

    shared = dict(
        target_m=target_m,
        lo=lo,
        hi=hi,
        closure_m=closure_m,
        rng=rng,
        loops=loops,
        seen=seen,
    )

    a1 = _generate_out_back(
        g, graph, origin_node, lat, lng, quota=q_out, **shared
    )
    a2 = _generate_multi_waypoint(
        g, graph, origin_node, lat, lng, quota=q_multi, **shared
    )
    a3 = _generate_random_walk(g, origin_node, quota=q_walk, **shared)

    remaining = n - len(loops)
    if remaining > 0:
        a1 += _generate_out_back(
            g, graph, origin_node, lat, lng, quota=remaining, **shared
        )

    by_strategy: dict[str, int] = {}
    for lp in loops:
        by_strategy[lp.strategy] = by_strategy.get(lp.strategy, 0) + 1

    logger.info(
        "Generated %d loops (target=%.0fm tol=±%.0f%% attempts=%d/%d/%d) %s",
        len(loops),
        target_m,
        tolerance * 100,
        a1,
        a2,
        a3,
        by_strategy,
    )
    return loops[:n]
