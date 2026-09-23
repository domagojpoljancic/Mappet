"""Silhouette renderer — normalised line-drawing PNGs (T0.3)."""

from __future__ import annotations

import hashlib
import io
import math
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw


def project_to_local_meters(
    polyline: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Project (lat, lng) polyline to local metres relative to first point."""
    if not polyline:
        return []
    lat0, lng0 = polyline[0]
    lat0_r = math.radians(lat0)
    m_per_deg_lat = 111_320.0
    m_per_deg_lng = 111_320.0 * math.cos(lat0_r)
    return [
        ((lng - lng0) * m_per_deg_lng, (lat - lat0) * m_per_deg_lat)
        for lat, lng in polyline
    ]


def render_silhouette(
    polyline: Sequence[tuple[float, float]],
    *,
    size: int = 256,
    padding: float = 0.12,
    stroke_width: int = 3,
    ink: tuple[int, int, int] = (255, 255, 255),
    background: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Render a centered, scaled white-on-black silhouette of a lat/lng loop."""
    img = Image.new("RGB", (size, size), background)
    if len(polyline) < 2:
        return img

    pts = project_to_local_meters(polyline)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    span = max(span_x, span_y)

    # Fit into square with padding; keep aspect ratio.
    usable = size * (1.0 - 2.0 * padding)
    scale = usable / span
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    def to_px(x: float, y: float) -> tuple[float, float]:
        # Image y grows downward; flip so north is up.
        px = size / 2.0 + (x - cx) * scale
        py = size / 2.0 - (y - cy) * scale
        return px, py

    draw = ImageDraw.Draw(img)
    pixels = [to_px(x, y) for x, y in pts]
    draw.line(pixels, fill=ink, width=stroke_width, joint="curve")
    return img


def silhouette_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def silhouette_hash(image: Image.Image) -> str:
    arr = np.asarray(image.convert("L"), dtype=np.uint8)
    return hashlib.sha256(arr.tobytes()).hexdigest()[:16]


def silhouette_deterministic(
    polyline: Sequence[tuple[float, float]], **kwargs
) -> tuple[Image.Image, str]:
    """Render and return (image, content_hash) for determinism checks."""
    img = render_silhouette(polyline, **kwargs)
    return img, silhouette_hash(img)
