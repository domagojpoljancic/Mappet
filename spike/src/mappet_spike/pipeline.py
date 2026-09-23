"""End-to-end Phase 0 eval: graph → loops → silhouettes → CLIP → HTML grid."""

from __future__ import annotations

import html
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mappet_spike.graph import GraphPreferences, build_graph
from mappet_spike.loops import generate_loops
from mappet_spike.recognise import clip_available, score_silhouette
from mappet_spike.silhouette import render_silhouette, silhouette_png_bytes

logger = logging.getLogger(__name__)


@dataclass
class EvalItem:
    origin_label: str
    lat: float
    lng: float
    loop_index: int
    length_m: float
    label_guess: str
    score: float
    image_relpath: str
    bearing_deg: float | None


def parse_origin(spec: str) -> tuple[float, float, str]:
    parts = [p.strip() for p in spec.split(",")]
    if len(parts) < 2:
        raise ValueError(f"Origin must be lat,lng[,label] — got {spec!r}")
    lat, lng = float(parts[0]), float(parts[1])
    label = parts[2] if len(parts) > 2 else f"{lat:.3f},{lng:.3f}"
    return lat, lng, label


def run_eval(
    *,
    origins: list[str],
    distance_km: float,
    n_candidates: int,
    tolerance: float,
    out_dir: Path,
    skip_clip: bool = False,
    top_k: int = 40,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    img_dir = out_dir / "silhouettes"
    img_dir.mkdir(parents=True, exist_ok=True)

    use_clip = (not skip_clip) and clip_available()
    if not skip_clip and not use_clip:
        logger.warning("open-clip/torch not installed — silhouettes only")

    items: list[EvalItem] = []
    origin_summaries: list[dict[str, Any]] = []

    for spec in origins:
        lat, lng, label = parse_origin(spec)
        logger.info("=== Origin %s (%.5f, %.5f) ===", label, lat, lng)
        built = build_graph(
            lat,
            lng,
            distance_km,
            activity="run",
            prefs=GraphPreferences(),
        )
        loops = generate_loops(
            built.graph,
            (lat, lng),
            distance_km,
            tolerance=tolerance,
            n=n_candidates,
        )
        scored: list[EvalItem] = []
        for i, loop in enumerate(loops):
            img = render_silhouette(loop.polyline)
            fname = f"{label.replace(' ', '_')}_{i:04d}.png"
            # Keep filename filesystem-safe.
            fname = "".join(c if c.isalnum() or c in "._-" else "_" for c in fname)
            rel = f"silhouettes/{fname}"
            (img_dir / fname).write_bytes(silhouette_png_bytes(img))

            guess, score = "unscored", 0.0
            if use_clip:
                result = score_silhouette(img)
                guess, score = result.label_guess, result.score

            scored.append(
                EvalItem(
                    origin_label=label,
                    lat=lat,
                    lng=lng,
                    loop_index=i,
                    length_m=loop.length_m,
                    label_guess=guess,
                    score=score,
                    image_relpath=rel,
                    bearing_deg=loop.bearing_deg,
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        keep = scored[:top_k] if use_clip else scored[:top_k]
        items.extend(keep)
        origin_summaries.append(
            {
                "label": label,
                "lat": lat,
                "lng": lng,
                "from_cache": built.from_cache,
                "nodes": built.node_count,
                "edges": built.edge_count,
                "loops": len(loops),
                "kept": len(keep),
            }
        )

    items.sort(key=lambda x: x.score, reverse=True)
    html_path = out_dir / "index.html"
    html_path.write_text(_render_html(items, origin_summaries, use_clip), encoding="utf-8")
    meta = {
        "distance_km": distance_km,
        "tolerance": tolerance,
        "n_candidates": n_candidates,
        "clip": use_clip,
        "origins": origin_summaries,
        "items": [asdict(it) for it in items],
        "html": str(html_path),
    }
    (out_dir / "results.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    logger.info("Wrote eval grid → %s (%d items)", html_path, len(items))
    return {
        "html": str(html_path),
        "count": len(items),
        "clip": use_clip,
        "origins": origin_summaries,
    }


def _render_html(
    items: list[EvalItem],
    origins: list[dict[str, Any]],
    use_clip: bool,
) -> str:
    cards = []
    for it in items:
        cards.append(
            f"""
            <figure class="card">
              <img src="{html.escape(it.image_relpath)}" alt="{html.escape(it.label_guess)}" width="192" height="192" />
              <figcaption>
                <strong>{html.escape(it.label_guess)}</strong>
                <span class="score">{it.score:.3f}</span><br/>
                <span class="meta">{html.escape(it.origin_label)} · {it.length_m/1000:.2f} km</span>
              </figcaption>
            </figure>
            """
        )
    origin_rows = "".join(
        f"<li><b>{html.escape(o['label'])}</b> — {o['loops']} loops "
        f"({o['nodes']} nodes / {o['edges']} edges, cache={o['from_cache']})</li>"
        for o in origins
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Mappet Phase 0 — silhouette eval</title>
  <style>
    :root {{ color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
    body {{ margin: 0; padding: 1.5rem; background: #0b0d10; color: #e8eaed; }}
    h1 {{ font-weight: 600; letter-spacing: -0.02em; }}
    .meta {{ color: #9aa0a6; font-size: 0.85rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }}
    .card {{ margin: 0; background: #15181e; border-radius: 8px; overflow: hidden; }}
    .card img {{ display: block; width: 100%; height: auto; background: #000; }}
    figcaption {{ padding: 0.6rem 0.75rem 0.9rem; font-size: 0.9rem; }}
    .score {{ float: right; color: #8ab4f8; font-variant-numeric: tabular-nums; }}
  </style>
</head>
<body>
  <h1>Mappet Phase 0 — human eval grid</h1>
  <p class="meta">CLIP scoring: {"on" if use_clip else "off"} · sorted by score · open locally to eyeball recognisability</p>
  <ul>{origin_rows}</ul>
  <div class="grid">
    {''.join(cards)}
  </div>
</body>
</html>
"""
