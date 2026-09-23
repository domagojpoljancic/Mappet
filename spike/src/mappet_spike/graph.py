"""OSM pedestrian graph builder with caching and preference weighting.

Architecture §3.1 — build a filtered walk graph around an origin, exclude
motorways/trunks, attach per-edge pleasantness, and cache to disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import networkx as nx
import osmnx as ox

logger = logging.getLogger(__name__)

Activity = Literal["run", "walk"]

# Highways that are never walkable for our purposes.
EXCLUDED_HIGHWAYS = frozenset(
    {"motorway", "trunk", "motorway_link", "trunk_link"}
)

# Quieter / park-adjacent ways get a pleasantness boost.
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

# Busy roads get a pleasantness penalty when avoid_busy_roads is on.
BUSY_HIGHWAYS = frozenset({"primary", "secondary", "tertiary", "primary_link", "secondary_link"})

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "graphs"


@dataclass(frozen=True)
class GraphPreferences:
    avoid_busy_roads: bool = True
    prefer_quiet: bool = True


@dataclass
class BuiltGraph:
    """Result of build_graph."""

    graph: nx.MultiDiGraph
    origin: tuple[float, float]
    radius_m: float
    cache_key: str
    from_cache: bool
    edge_count: int
    node_count: int


def search_radius_m(distance_km: float) -> float:
    """Generous search radius so a loop of length D fits with headroom.

    A circle of circumference D has radius D/(2π) ≈ D/6. We fetch ~D/2.5 so
    out-and-back anchors near D/2 still sit inside the cached graph.
    """
    d_m = distance_km * 1000.0
    radius = d_m / 2.5
    return float(max(1000.0, min(radius, 25_000.0)))


def _round_coord(value: float, places: int = 3) -> float:
    return round(value, places)


def cache_key(
    lat: float,
    lng: float,
    distance_km: float,
    activity: Activity,
    prefs: GraphPreferences,
) -> str:
    radius = search_radius_m(distance_km)
    payload = {
        "lat": _round_coord(lat),
        "lng": _round_coord(lng),
        "radius_m": int(radius),
        "activity": activity,
        "avoid_busy": prefs.avoid_busy_roads,
        "prefer_quiet": prefs.prefer_quiet,
        "v": 1,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _highway_tag(data: dict[str, Any]) -> str | None:
    hw = data.get("highway")
    if hw is None:
        return None
    if isinstance(hw, list):
        return str(hw[0]) if hw else None
    return str(hw)


def is_excluded_highway(highway: str | None) -> bool:
    """True if this highway tag must be dropped from the walk graph."""
    if highway is None:
        return False
    return highway in EXCLUDED_HIGHWAYS


def edge_pleasantness(
    data: dict[str, Any],
    prefs: GraphPreferences,
) -> float:
    """Score in roughly [0, 1]; higher = nicer to run/walk."""
    hw = _highway_tag(data)
    score = 0.55

    if prefs.prefer_quiet and hw in QUIET_HIGHWAYS:
        score += 0.25
    if prefs.avoid_busy_roads and hw in BUSY_HIGHWAYS:
        score -= 0.30

    # Sidewalk / park cues when present on the way tags.
    if data.get("foot") in ("yes", "designated"):
        score += 0.05
    if data.get("sidewalk") in ("both", "left", "right", "yes"):
        score += 0.05
    if data.get("leisure") == "park" or data.get("landuse") == "recreation_ground":
        score += 0.15

    maxspeed = data.get("maxspeed")
    if maxspeed is not None and prefs.avoid_busy_roads:
        try:
            # OSM maxspeed can be "50" or "50 mph" — take leading digits.
            digits = "".join(ch for ch in str(maxspeed).split()[0] if ch.isdigit())
            if digits and int(digits) >= 60:
                score -= 0.15
        except (TypeError, ValueError):
            pass

    return float(max(0.05, min(1.0, score)))


def filter_graph_edges(
    graph: nx.MultiDiGraph,
    prefs: GraphPreferences,
) -> nx.MultiDiGraph:
    """Drop excluded highways and attach pleasantness + length-based weight."""
    g = graph.copy()
    to_remove: list[tuple[Any, Any, Any]] = []

    for u, v, k, data in g.edges(keys=True, data=True):
        hw = _highway_tag(data)
        if is_excluded_highway(hw):
            to_remove.append((u, v, k))
            continue

        pleasant = edge_pleasantness(data, prefs)
        data["pleasantness"] = pleasant
        length = float(data.get("length") or 1.0)
        # Routing cost: length scaled so pleasant edges are cheaper.
        # weight = length / pleasantness  → higher pleasantness ⇒ lower cost.
        data["weight"] = length / max(pleasant, 0.05)

    g.remove_edges_from(to_remove)
    # Drop isolated nodes left after filtering.
    isolates = list(nx.isolates(g))
    g.remove_nodes_from(isolates)
    return g


def _graph_paths(cache_dir: Path, key: str) -> tuple[Path, Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{key}.graphml", cache_dir / f"{key}.meta.json"


def save_graph(graph: nx.MultiDiGraph, path: Path) -> None:
    ox.save_graphml(graph, filepath=path)


def load_graph(path: Path) -> nx.MultiDiGraph:
    g = ox.load_graphml(filepath=path)
    # GraphML round-trips numeric attrs as strings — coerce what we need.
    for _, _, _, data in g.edges(keys=True, data=True):
        if "length" in data:
            data["length"] = float(data["length"])
        if "pleasantness" in data:
            data["pleasantness"] = float(data["pleasantness"])
        if "weight" in data:
            data["weight"] = float(data["weight"])
    return g


def fetch_walk_graph(lat: float, lng: float, radius_m: float) -> nx.MultiDiGraph:
    """Download a walk network from OSM around the origin."""
    logger.info("Fetching OSM walk graph lat=%.5f lng=%.5f radius=%.0fm", lat, lng, radius_m)
    return ox.graph_from_point(
        (lat, lng),
        dist=radius_m,
        network_type="walk",
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )


def build_graph(
    lat: float,
    lng: float,
    distance_km: float,
    activity: Activity = "run",
    prefs: GraphPreferences | None = None,
    *,
    cache_dir: Path | None = None,
    force_refresh: bool = False,
) -> BuiltGraph:
    """Build (or load from cache) a filtered pedestrian graph near origin.

    Second call with the same rounded origin/radius/prefs hits disk cache and
    does not touch the network.
    """
    prefs = prefs or GraphPreferences()
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    key = cache_key(lat, lng, distance_km, activity, prefs)
    graph_path, meta_path = _graph_paths(cache_dir, key)
    radius = search_radius_m(distance_km)

    if not force_refresh and graph_path.exists():
        logger.info("Graph cache hit key=%s path=%s", key, graph_path)
        g = load_graph(graph_path)
        return BuiltGraph(
            graph=g,
            origin=(lat, lng),
            radius_m=radius,
            cache_key=key,
            from_cache=True,
            edge_count=g.number_of_edges(),
            node_count=g.number_of_nodes(),
        )

    raw = fetch_walk_graph(lat, lng, radius)
    g = filter_graph_edges(raw, prefs)

    if g.number_of_edges() == 0:
        raise RuntimeError(
            f"Empty walk graph after filtering at ({lat}, {lng}) radius={radius}m"
        )

    save_graph(g, graph_path)
    meta = {
        "lat": lat,
        "lng": lng,
        "distance_km": distance_km,
        "radius_m": radius,
        "activity": activity,
        "prefs": {
            "avoid_busy_roads": prefs.avoid_busy_roads,
            "prefer_quiet": prefs.prefer_quiet,
        },
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "cache_key": key,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info(
        "Graph built+cached key=%s nodes=%d edges=%d",
        key,
        g.number_of_nodes(),
        g.number_of_edges(),
    )

    return BuiltGraph(
        graph=g,
        origin=(lat, lng),
        radius_m=radius,
        cache_key=key,
        from_cache=False,
        edge_count=g.number_of_edges(),
        node_count=g.number_of_nodes(),
    )


def nearest_node(graph: nx.MultiDiGraph, lat: float, lng: float) -> Any:
    """Nearest node to a lat/lng (graph nodes use WGS84 x=lng, y=lat).

    Uses a local equirectangular distance so we do not need scikit-learn /
    a projected CRS (OSMnx's `nearest_nodes` requires one of those).
    """
    best_node = None
    best_d2 = float("inf")
    # Metres-per-degree at this latitude — good enough for nearest-node search.
    m_lat = 111_320.0
    m_lng = 111_320.0 * math.cos(math.radians(lat))
    for node, data in graph.nodes(data=True):
        dy = (float(data["y"]) - lat) * m_lat
        dx = (float(data["x"]) - lng) * m_lng
        d2 = dx * dx + dy * dy
        if d2 < best_d2:
            best_d2 = d2
            best_node = node
    if best_node is None:
        raise ValueError("Graph has no nodes")
    return best_node


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
