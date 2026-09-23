"""Unit tests for geometry shape-likeness filters."""

from __future__ import annotations

from mappet_spike.geometry import is_shape_like, loop_metrics


def _square(size_m: float = 800.0) -> list[tuple[float, float]]:
    # Rough metres → degrees at 45°N
    dlat = size_m / 111_320.0
    dlng = size_m / (111_320.0 * 0.7)
    lat0, lng0 = 45.81, 15.98
    return [
        (lat0, lng0),
        (lat0 + dlat, lng0),
        (lat0 + dlat, lng0 + dlng),
        (lat0, lng0 + dlng),
        (lat0, lng0),
    ]


def _skinny_corridor() -> list[tuple[float, float]]:
    # Long thin out-and-back style zigzag
    lat0, lng0 = 45.81, 15.98
    pts = [(lat0, lng0)]
    for i in range(20):
        pts.append((lat0 + i * 0.00005, lng0 + i * 0.0008))
    for i in range(20, -1, -1):
        pts.append((lat0 + i * 0.00005 + 0.0002, lng0 + i * 0.0008))
    pts.append((lat0, lng0))
    return pts


def test_square_is_shape_like():
    poly = _square()
    m = loop_metrics(poly)
    assert m["compactness"] > 0.5
    assert is_shape_like(poly)


def test_skinny_corridor_rejected():
    poly = _skinny_corridor()
    assert not is_shape_like(poly)
