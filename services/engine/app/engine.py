"""Mock route-discovery engine for Mappet.

This is a credential-free, network-free placeholder for the real route engine
described in docs/ARCHITECTURE.md. Instead of building an OSM graph and running
CLIP recognition, it synthesises deterministic loop shapes around the origin so
the rest of the stack (API + frontend) can be developed and demonstrated
end-to-end. Swap this out for the real pipeline (graph -> loops -> silhouette ->
recognise -> rank) in Phase 1 (see docs/BACKLOG.md T1.2).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Callable

EARTH_RADIUS_M = 6_371_000.0
DEG_LAT_M = 111_320.0  # metres per degree of latitude (approx)


@dataclass
class ShapeTemplate:
    label: str
    emoji: str
    # Returns a closed list of (x, y) unit points in roughly [-1, 1].
    points: Callable[[], list[tuple[float, float]]]


def _circle(n: int = 64) -> list[tuple[float, float]]:
    return [
        (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
        for i in range(n + 1)
    ]


def _heart(n: int = 80) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 17.0, y / 17.0))
    return pts


def _star(points: int = 5) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    step = math.pi / points
    for i in range(2 * points + 1):
        r = 1.0 if i % 2 == 0 else 0.42
        ang = i * step - math.pi / 2
        pts.append((r * math.cos(ang), r * math.sin(ang)))
    return pts


def _fish() -> list[tuple[float, float]]:
    # A simple fish: body ellipse-ish plus a tail triangle.
    body = [
        (math.cos(a) * 1.0, math.sin(a) * 0.5)
        for a in [2 * math.pi * i / 48 for i in range(37)]  # ~3/4 of an ellipse
    ]
    tail = [(-1.0, 0.35), (-1.6, 0.7), (-1.6, -0.7), (-1.0, -0.35)]
    loop = body + tail
    loop.append(loop[0])
    return loop


def _key() -> list[tuple[float, float]]:
    # A key: round bow + a shaft with a couple of teeth.
    bow = [
        (0.55 + 0.45 * math.cos(a), 0.45 * math.sin(a))
        for a in [2 * math.pi * i / 40 for i in range(41)]
    ]
    shaft = [
        (0.1, 0.08),
        (-1.2, 0.08),
        (-1.2, -0.08),
        (-0.95, -0.08),
        (-0.95, -0.28),
        (-0.8, -0.28),
        (-0.8, -0.08),
        (-0.6, -0.08),
        (-0.6, -0.24),
        (-0.45, -0.24),
        (-0.45, -0.08),
        (0.1, -0.08),
    ]
    loop = bow + shaft
    loop.append(loop[0])
    return loop


def _duck() -> list[tuple[float, float]]:
    # Very schematic duck: round body + head bump.
    body = [
        (math.cos(a), 0.7 * math.sin(a))
        for a in [math.pi * i / 24 for i in range(25)]  # top half
    ]
    tail_and_base = [
        (-1.0, 0.0),
        (-1.1, 0.25),
        (-0.7, 0.15),
        (-0.5, 0.0),
    ]
    head = [
        (0.85, 0.0),
        (1.15, 0.35),
        (1.5, 0.55),
        (1.5, 0.8),
        (1.15, 0.75),
        (1.0, 0.45),
    ]
    loop = body + head + [(1.0, 0.0)] + tail_and_base
    loop.append(loop[0])
    return loop


SHAPES: list[ShapeTemplate] = [
    ShapeTemplate("duck", "\U0001F986", _duck),
    ShapeTemplate("heart", "\u2764\uFE0F", _heart),
    ShapeTemplate("fish", "\U0001F41F", _fish),
    ShapeTemplate("star", "\u2B50", _star),
    ShapeTemplate("key", "\U0001F511", _key),
    ShapeTemplate("circle", "\u2B55", _circle),
]


@dataclass
class RouteResult:
    route_id: str
    label: str
    emoji: str
    confidence: float
    distance_m: float
    est_time_s: int
    pleasantness: float
    surface_mix: dict[str, float]
    polyline: list[list[float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "label": self.label,
            "emoji": self.emoji,
            "confidence": round(self.confidence, 2),
            "distance_m": round(self.distance_m),
            "est_time_s": self.est_time_s,
            "pleasantness": round(self.pleasantness, 2),
            "surface_mix": self.surface_mix,
            "polyline": self.polyline,
        }


def _seeded_unit(*parts: object) -> float:
    """Deterministic pseudo-random value in [0, 1) from the given parts."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _unit_perimeter(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        total += math.hypot(x2 - x1, y2 - y1)
    return total or 1.0


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _polyline_length_m(poly: list[list[float]]) -> float:
    total = 0.0
    for (lat1, lng1), (lat2, lng2) in zip(poly, poly[1:]):
        total += _haversine(lat1, lng1, lat2, lng2)
    return total


def _shape_to_polyline(
    shape: ShapeTemplate,
    origin_lat: float,
    origin_lng: float,
    distance_km: float,
    rotation: float,
) -> list[list[float]]:
    pts = shape.points()
    perim = _unit_perimeter(pts)
    target_m = distance_km * 1000.0
    scale_m = target_m / perim  # metres per unit length

    cos_r, sin_r = math.cos(rotation), math.sin(rotation)
    cos_lat = max(math.cos(math.radians(origin_lat)), 1e-6)

    poly: list[list[float]] = []
    for x, y in pts:
        # Rotate in unit space for visual variety.
        rx = x * cos_r - y * sin_r
        ry = x * sin_r + y * cos_r
        east_m = rx * scale_m
        north_m = ry * scale_m
        dlat = north_m / DEG_LAT_M
        dlng = east_m / (DEG_LAT_M * cos_lat)
        poly.append([round(origin_lat + dlat, 6), round(origin_lng + dlng, 6)])
    return poly


# Surface mixes keyed by whether "prefer_quiet" is on.
def _surface_mix(seed: float, prefer_quiet: bool) -> dict[str, float]:
    park = 0.45 if prefer_quiet else 0.2
    park += (seed - 0.5) * 0.1
    park = min(max(park, 0.05), 0.6)
    residential = min(max(0.8 - park + (seed - 0.5) * 0.1, 0.1), 0.85)
    other = max(0.0, 1.0 - park - residential)
    total = park + residential + other
    return {
        "park": round(park / total, 2),
        "residential": round(residential / total, 2),
        "other": round(other / total, 2),
    }


def search(
    origin_lat: float,
    origin_lng: float,
    activity: str,
    distance_km: float,
    tolerance: float = 0.15,
    prefer_quiet: bool = True,
    avoid_busy_roads: bool = True,
    top_k: int = 5,
) -> list[RouteResult]:
    """Return up to ``top_k`` mock recognisable loops around the origin."""
    pace_s_per_km = 360 if activity == "run" else 720  # 6 or 12 min/km

    candidates: list[RouteResult] = []
    for idx, shape in enumerate(SHAPES):
        seed = _seeded_unit(
            round(origin_lat, 3),
            round(origin_lng, 3),
            activity,
            round(distance_km, 1),
            shape.label,
        )
        rotation = seed * 2 * math.pi
        # Jitter the requested distance within tolerance, deterministically.
        jitter = 1.0 + (seed - 0.5) * 2 * tolerance
        eff_km = distance_km * jitter
        poly = _shape_to_polyline(shape, origin_lat, origin_lng, eff_km, rotation)
        dist_m = _polyline_length_m(poly)

        base_conf = 0.6 + seed * 0.35  # 0.60 .. 0.95
        pleasant = 0.55 + seed * 0.4
        if prefer_quiet:
            pleasant = min(pleasant + 0.05, 0.99)

        route_id = "r_" + hashlib.sha256(
            f"{origin_lat:.4f}:{origin_lng:.4f}:{activity}:{distance_km}:{shape.label}".encode()
        ).hexdigest()[:10]

        candidates.append(
            RouteResult(
                route_id=route_id,
                label=shape.label,
                emoji=shape.emoji,
                confidence=base_conf,
                distance_m=dist_m,
                est_time_s=int(dist_m / 1000.0 * pace_s_per_km),
                pleasantness=pleasant,
                surface_mix=_surface_mix(seed, prefer_quiet),
                polyline=poly,
            )
        )

    candidates.sort(key=lambda r: r.confidence, reverse=True)
    return candidates[:top_k]
