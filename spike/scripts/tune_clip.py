"""Compare CLIP prompt/vocab/render variants on a fixed Zagreb candidate set."""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

from mappet_spike.geometry import is_shape_like
from mappet_spike.graph import GraphPreferences, build_graph
from mappet_spike.loops import generate_loops
from mappet_spike.recognise import (
    DEFAULT_VOCABULARY,
    SKETCH_VOCABULARY,
    score_silhouette,
    score_silhouette_ensemble,
)
from mappet_spike.silhouette import render_silhouette

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("tune_clip")


def main() -> None:
    lat, lng = 45.8150, 15.9819
    distance_km = 5.0
    built = build_graph(lat, lng, distance_km, prefs=GraphPreferences())
    loops = generate_loops(built.graph, (lat, lng), distance_km, n=180, tolerance=0.15)
    shaped = [lp for lp in loops if is_shape_like(lp.polyline)][:80]
    logger.info("candidates: %d raw → %d shape-like (using %d)", len(loops), len(shaped), len(shaped))

    variants = [
        ("baseline_stroke3", dict(stroke_width=3, filled=False, invert=False), "single", "line_drawing", DEFAULT_VOCABULARY),
        ("thick_stroke8", dict(stroke_width=8, filled=False, invert=False), "single", "line_drawing", DEFAULT_VOCABULARY),
        ("sketch_vocab", dict(stroke_width=3, filled=False, invert=False), "single", "sketch", SKETCH_VOCABULARY),
        ("ensemble_sketch", dict(stroke_width=3, filled=False, invert=False), "ensemble", None, SKETCH_VOCABULARY),
        ("ensemble_thick", dict(stroke_width=8, filled=False, invert=False), "ensemble", None, SKETCH_VOCABULARY),
        ("invert_bw", dict(stroke_width=3, filled=False, invert=True), "ensemble", None, SKETCH_VOCABULARY),
        ("filled_ensemble", dict(stroke_width=3, filled=True, invert=False), "ensemble", None, SKETCH_VOCABULARY),
    ]

    report: dict = {"n": len(shaped), "variants": {}}

    for name, render_kwargs, mode, style, vocab in variants:
        scores = []
        labels = []
        for lp in shaped:
            ink = (0, 0, 0) if render_kwargs["invert"] else (255, 255, 255)
            bg = (255, 255, 255) if render_kwargs["invert"] else (0, 0, 0)
            img = render_silhouette(
                lp.polyline,
                stroke_width=render_kwargs["stroke_width"],
                filled=render_kwargs["filled"],
                ink=ink,
                background=bg,
            )
            if mode == "ensemble":
                result = score_silhouette_ensemble(img, vocabulary=vocab)
            else:
                result = score_silhouette(
                    img, vocabulary=vocab, prompt_style=style or "line_drawing"
                )
            scores.append(result.score)
            labels.append(result.label_guess)

        scores_sorted = sorted(scores, reverse=True)
        report["variants"][name] = {
            "mean": sum(scores) / len(scores),
            "p50": scores_sorted[len(scores) // 2],
            "p90": scores_sorted[max(0, int(len(scores) * 0.1))],
            "max": max(scores),
            "top_labels": Counter(labels).most_common(8),
        }
        v = report["variants"][name]
        logger.info(
            "%-18s mean=%.3f p50=%.3f max=%.3f labels=%s",
            name,
            v["mean"],
            v["p50"],
            v["max"],
            v["top_labels"][:5],
        )

    out = Path("output/clip_tuning.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("wrote %s", out)

    # Pick best mean among variants.
    best_name, best = max(report["variants"].items(), key=lambda kv: kv[1]["mean"])
    baseline = report["variants"]["baseline_stroke3"]
    delta = best["mean"] - baseline["mean"]
    report["verdict"] = {
        "best_variant": best_name,
        "best_mean": best["mean"],
        "baseline_mean": baseline["mean"],
        "delta_mean": delta,
        "improved": delta > 0.01,
    }
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["verdict"], indent=2))


if __name__ == "__main__":
    main()
