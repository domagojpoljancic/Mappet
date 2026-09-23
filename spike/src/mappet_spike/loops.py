"""Candidate loop generator — out-and-different-back across bearings (T0.2)."""

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


@dataclass
class Loop:
    """A closed candidate route as an ordered lat/lng polyline."""

    nodes: list[Any]
    polyline: list[tuple[float, float]]  # (lat, lng)
    length_m: float
    bearing_deg: float | None = None

    @property
    def geometry_hash(self) -> str:
        # Coarse grid hash for near-duplicate detection.
        pts = [
            (round(lat, 4), round(lng, 4))
            for lat, lng in self.polyline[:: max(1, len(self.polyline) // 32)]
        ]
        raw = repr(pts).encode()
        return hashlib.sha1(raw).hexdigest()[:12]


def _node_latlng(graph: nx.MultiDiGraph, node: Any) -> tuple[float, float]:
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
    """Move distance_m along bearing from (lat, lng); return new (lat, lng)."""
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
    """Temporarily inflate weights along a path; return original weights to restore."""
    originals: dict[tuple[Any, Any, Any], float] = {}
    for u, v in zip(nodes, nodes[1:]):
        edges = graph.get_edge_data(u, v) or {}
        for k, data in edges.items():
            key = (u, v, k)
            if key not in originals:
                originals[key] = float(data.get("weight", data.get("length", 1.0)))
            data["weight"] = originals[key] * factor
            # Also penalise reverse edge if present (undirected MultiGraph).
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
    """Fraction of undirected edges in `a` that also appear in `b`."""
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
    """Undirected copy so walk routing ignores one-way quirks."""
    g = nx.MultiGraph()
    for node, data in graph.nodes(data=True):
        g.add_node(node, **data)
    for u, v, _k, data in graph.edges(keys=True, data=True):
        # Keep a single parallel edge with the nicer weight if duplicates exist.
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
            # Prefer shorter / nicer existing edge.
            existing = g.get_edge_data(u, v)
            best_existing = min(float(d.get("weight", 1e18)) for d in existing.values())
            if weight >= best_existing:
                continue
        g.add_edge(u, v, **attrs)
    return g


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

    Strategy: sample anchors across bearings at ~distance/2, shortest path out,
    strongly penalise used edges, shortest path back. Also sample random nodes
    in a distance band. Deduplicate near-identical geometry.
    """
    rng = random.Random(seed)
    lat, lng = origin
    target_m = distance_km * 1000.0
    lo, hi = target_m * (1.0 - tolerance), target_m * (1.0 + tolerance)
    half = target_m / 2.0

    origin_node = nearest_node(graph, lat, lng)
    o_lat, o_lng = _node_latlng(graph, origin_node)
    if haversine_m(lat, lng, o_lat, o_lng) > closure_m * 3:
        logger.warning(
            "Nearest graph node is far from origin (%.0fm)",
            haversine_m(lat, lng, o_lat, o_lng),
        )

    g = _to_undirected_multi(graph)

    # Precompute node distances from origin for random-band sampling.
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

    bearings = [i * (360.0 / max(n, 1)) for i in range(n)]
    radius_factors = [0.65, 0.8, 0.95, 1.1, 1.25]
    penalty_factors = [4.0, 8.0, 16.0]

    loops: list[Loop] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = max(n * 12, 800)

    def try_anchor(anchor: Any, bearing: float | None) -> None:
        nonlocal attempts
        if len(loops) >= n or attempts >= max_attempts:
            return
        if anchor == origin_node:
            return
        attempts += 1

        out_path = _shortest_path_weighted(g, origin_node, anchor)
        if not out_path or len(out_path) < 2:
            return

        for factor in penalty_factors:
            if len(loops) >= n or attempts >= max_attempts:
                return
            originals = _penalise_edges(g, out_path, factor=factor)
            try:
                back_path = _shortest_path_weighted(g, anchor, origin_node)
            finally:
                _restore_weights(g, originals)

            if not back_path or len(back_path) < 2:
                continue
            # Reject near out-and-back along the same corridor.
            if _edge_overlap_ratio(out_path, list(reversed(back_path))) > 0.55:
                continue

            nodes = list(out_path) + list(back_path[1:])
            if nodes[0] != nodes[-1]:
                continue

            length = _path_length_m(g, nodes)
            if not (lo <= length <= hi):
                continue

            start = _node_latlng(g, nodes[0])
            end = _node_latlng(g, nodes[-1])
            if haversine_m(start[0], start[1], end[0], end[1]) > closure_m:
                continue

            poly = _path_polyline(g, nodes)
            loop = Loop(nodes=nodes, polyline=poly, length_m=length, bearing_deg=bearing)
            if loop.geometry_hash in seen:
                continue
            seen.add(loop.geometry_hash)
            loops.append(loop)
            return  # one success per anchor is enough

    for bearing in bearings:
        if len(loops) >= n or attempts >= max_attempts:
            break
        for rf in radius_factors:
            dest_lat, dest_lng = _destination_point(lat, lng, bearing, half * rf)
            try:
                anchor = nearest_node(graph, dest_lat, dest_lng)
            except Exception:
                continue
            try_anchor(anchor, bearing)

    # Fill remaining quota with random band anchors.
    rng.shuffle(band_nodes)
    for anchor in band_nodes:
        if len(loops) >= n or attempts >= max_attempts:
            break
        try_anchor(anchor, None)

    logger.info(
        "Generated %d loops (target=%.0fm tol=±%.0f%% attempts=%d band=%d)",
        len(loops),
        target_m,
        tolerance * 100,
        attempts,
        len(band_nodes),
    )
    return loops
