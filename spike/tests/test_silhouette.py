"""Unit tests for silhouette rendering (T0.3)."""

from __future__ import annotations

from mappet_spike.silhouette import (
    render_silhouette,
    silhouette_deterministic,
    silhouette_hash,
    silhouette_png_bytes,
)


def _square_loop() -> list[tuple[float, float]]:
    # Small closed square around Zagreb coords.
    return [
        (45.8100, 15.9800),
        (45.8105, 15.9800),
        (45.8105, 15.9807),
        (45.8100, 15.9807),
        (45.8100, 15.9800),
    ]


def test_silhouette_deterministic():
    poly = _square_loop()
    img1, h1 = silhouette_deterministic(poly)
    img2, h2 = silhouette_deterministic(poly)
    assert h1 == h2
    assert silhouette_hash(img1) == silhouette_hash(img2)
    assert img1.size == (256, 256)


def test_silhouette_png_nonempty():
    img = render_silhouette(_square_loop())
    raw = silhouette_png_bytes(img)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 100


def test_filled_silhouette_differs_from_stroke():
    poly = _square_loop()
    stroke = render_silhouette(poly, filled=False, stroke_width=2)
    filled = render_silhouette(poly, filled=True)
    assert silhouette_hash(stroke) != silhouette_hash(filled)
