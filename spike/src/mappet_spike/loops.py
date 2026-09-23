"""Candidate loop generator — out-and-different-back across bearings (T0.2)."""

from __future__ import annotations

import hashlib
import logging
import math
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


def _path_length_m(graph: nx.MultiDiGraph, nodes: Sequence[Any]) -> float:
    total = 0.0
    for u, v in zip(nodes, nodes[1:]):
        # Pick the shortest parallel edge if MultiDiGraph.
        edges = graph.get_edge_data(u, v)
        if not edges:
            # Try reverse for undirected-ish walk graphs that may be one-way odd.
            edges = graph.get_edge_data(v, u)
            if not edges:
                return float("inf")
        best = min(float(d.get("length", 1.0)) for d in edges.values())
        total += best
    return total


def _path_polyline(graph: nx.MultiDiGraph, nodes: Sequence[Any]) -> list[tuple[float, float]]:
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
    graph: nx.MultiDiGraph, source: Any, target: Any, weight: str = "weight"
) -> list[Any] | None:
    try:
        return nx.shortest_path(graph, source, target, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def _penalise_edges(
    graph: nx.MultiDiGraph, nodes: Sequence[Any], factor: float = 4.0
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
    return originals


def _restore_weights(
    graph: nx.MultiDiGraph, originals: dict[tuple[Any, Any, Any], float]
) -> None:
    for (u, v, k), w in originals.items():
        if graph.has_edge(u, v, k):
            graph[u][v][k]["weight"] = w


def generate_loops(
    graph: nx.MultiDiGraph,
    origin: tuple[float, float],
    distance_km: float,
    tolerance: float = 0.15,
    n: int = 200,
    *,
    closure_m: float = 40.0,
) -> list[Loop]:
    """Generate up to n distinct loops near `distance_km` that close at origin.

    Strategy: sample anchors across bearings at ~distance/2, shortest path out,
    penalise used edges, shortest path back. Deduplicate near-identical geometry.
    """
    lat, lng = origin
    target_m = distance_km * 1000.0
    lo, hi = target_m * (1.0 - tolerance), target_m * (1.0 + tolerance)
    half = target_m / 2.0

    origin_node = nearest_node(graph, lat, lng)
    o_lat, o_lng = _node_latlng(graph, origin_node)
    if haversine_m(lat, lng, o_lat, o_lng) > closure_m * 3:
        logger.warning("Nearest graph node is far from origin (%.0fm)", haversine_m(lat, lng, o_lat, o_lng))

    # Work on a copy so weight penalties don't leak.
    g = graph.copy()
    # Ensure every edge has a weight.
    for _, _, _, data in g.edges(keys=True, data=True):
        if "weight" not in data:
            length = float(data.get("length") or 1.0)
            pleasant = float(data.get("pleasantness") or 0.55)
            data["weight"] = length / max(pleasant, 0.05)

    bearings = [i * (360.0 / max(n, 1)) for i in range(n)]
    # Slight radial jitter so we don't always hit the same node.
    radius_factors = [0.85, 1.0, 1.15]

    loops: list[Loop] = []
    seen: set[str] = set()
    attempts = 0
    max_attempts = n * len(radius_factors) * 2

    for bearing in bearings:
        for rf in radius_factors:
            if len(loops) >= n or attempts >= max_attempts:
                break
            attempts += 1
            dest_lat, dest_lng = _destination_point(lat, lng, bearing, half * rf)
            try:
                anchor = nearest_node(g, dest_lat, dest_lng)
            except Exception:
                continue
            if anchor == origin_node:
                continue

            out_path = _shortest_path_weighted(g, origin_node, anchor)
            if not out_path or len(out_path) < 2:
                continue

            originals = _penalise_edges(g, out_path, factor=5.0)
            try:
                back_path = _shortest_path_weighted(g, anchor, origin_node)
            finally:
                _restore_weights(g, originals)

            if not back_path or len(back_path) < 2:
                continue

            # Concatenate; drop duplicate anchor at join.
            nodes = list(out_path) + list(back_path[1:])
            if nodes[0] != nodes[-1]:
                # Force close if routing returned near-origin different node.
                continue

            length = _path_length_m(g, nodes)
            if not (lo <= length <= hi):
                continue

            # Closure check in metres (should be ~0 since same node).
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

        if len(loops) >= n:
            break

    logger.info(
        "Generated %d loops (target=%.0fm tol=±%.0f%% attempts=%d)",
        len(loops),
        target_m,
        tolerance * 100,
        attempts,
    )
    return loops
