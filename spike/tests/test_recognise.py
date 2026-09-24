"""Tests for CLIP prompt styles / ensemble (no network beyond model cache)."""

from __future__ import annotations

import pytest

from mappet_spike.recognise import (
    SKETCH_VOCABULARY,
    clip_available,
    score_silhouette,
    score_silhouette_ensemble,
)
from mappet_spike.silhouette import render_silhouette


pytestmark = pytest.mark.skipif(not clip_available(), reason="open-clip/torch missing")


def _square_img():
    poly = [
        (45.8100, 15.9800),
        (45.8105, 15.9800),
        (45.8105, 15.9807),
        (45.8100, 15.9807),
        (45.8100, 15.9800),
    ]
    return render_silhouette(poly, stroke_width=6)


def test_prompt_styles_return_ranked():
    img = _square_img()
    a = score_silhouette(img, prompt_style="line_drawing")
    b = score_silhouette(img, vocabulary=SKETCH_VOCABULARY, prompt_style="sketch")
    assert a.label_guess
    assert b.label_guess
    assert a.ranked and b.ranked


def test_ensemble_runs():
    img = _square_img()
    r = score_silhouette_ensemble(img)
    assert r.score > 0
    assert r.prompt_style.startswith("ensemble:")
