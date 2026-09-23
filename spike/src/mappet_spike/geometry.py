"""Geometry helpers for loop quality / shape-likeness filters (T0.5)."""

from __future__ import annotations

import math
from typing import Sequence

from shapely.geometry import LineString, Polygon


def _to_local_meters(polyline: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if not polyline:
        return []
    lat0, lng0 = polyline[0]
    m_lat = 111_320.0
    m_lng = 111_320.0 * math.cos(math.radians(lat0))
    return [((lng - lng0) * m_lng, (lat - lat0) * m_lat) for lat, lng in polyline]


def loop_metrics(polyline: Sequence[tuple[float, float]]) -> dict[str, float]:
    """Compute compactness, area, perimeter, bbox aspect for a lat/lng loop."""
    pts = _to_local_meters(polyline)
    if len(pts) < 4:
        return {
            "area_m2": 0.0,
            "perimeter_m": 0.0,
            "compactness": 0.0,
            "aspect": 1.0,
            "bbox_fill": 0.0,
        }

    line = LineString(pts)
    perimeter = float(line.length)
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        area = float(abs(poly.area))
    except Exception:
        area = 0.0

    # Isoperimetric quotient: 4πA / P² ∈ (0, 1]; circle = 1.
    compactness = (4.0 * math.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    aspect = (max(w, h) / max(min(w, h), 1.0)) if (w > 0 and h > 0) else 99.0
    bbox_area = max(w, 1.0) * max(h, 1.0)
    bbox_fill = area / bbox_area if bbox_area > 0 else 0.0

    return {
        "area_m2": area,
        "perimeter_m": perimeter,
        "compactness": float(compactness),
        "aspect": float(aspect),
        "bbox_fill": float(bbox_fill),
    }


def is_shape_like(
    polyline: Sequence[tuple[float, float]],
    *,
    min_compactness: float = 0.08,
    min_area_m2: float = 40_000.0,  # ~200×200 m
    max_aspect: float = 4.0,
    min_bbox_fill: float = 0.08,
) -> bool:
    """Reject skinny corridors / needle loops that never look like objects."""
    m = loop_metrics(polyline)
    if m["area_m2"] < min_area_m2:
        return False
    if m["compactness"] < min_compactness:
        return False
    if m["aspect"] > max_aspect:
        return False
    if m["bbox_fill"] < min_bbox_fill:
        return False
    return True
