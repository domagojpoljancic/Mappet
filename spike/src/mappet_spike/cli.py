"""CLI entrypoints for the Phase 0 spike."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from mappet_spike.graph import GraphPreferences, build_graph
from mappet_spike.loops import generate_loops
from mappet_spike.pipeline import run_eval


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def cmd_build_graph(args: argparse.Namespace) -> int:
    prefs = GraphPreferences(
        avoid_busy_roads=not args.allow_busy,
        prefer_quiet=not args.no_quiet,
    )
    result = build_graph(
        args.lat,
        args.lng,
        args.distance_km,
        activity=args.activity,
        prefs=prefs,
        force_refresh=args.refresh,
    )
    print(
        json.dumps(
            {
                "cache_key": result.cache_key,
                "from_cache": result.from_cache,
                "nodes": result.node_count,
                "edges": result.edge_count,
                "radius_m": result.radius_m,
            },
            indent=2,
        )
    )
    return 0


def cmd_loops(args: argparse.Namespace) -> int:
    built = build_graph(args.lat, args.lng, args.distance_km, activity=args.activity)
    loops = generate_loops(
        built.graph,
        (args.lat, args.lng),
        args.distance_km,
        tolerance=args.tolerance,
        n=args.n,
    )
    print(
        json.dumps(
            {
                "count": len(loops),
                "lengths_m": [round(lp.length_m, 1) for lp in loops[:20]],
                "from_cache": built.from_cache,
            },
            indent=2,
        )
    )
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    out = Path(args.out)
    report = run_eval(
        origins=args.origin,
        distance_km=args.distance_km,
        n_candidates=args.n,
        tolerance=args.tolerance,
        out_dir=out,
        skip_clip=args.skip_clip,
        top_k=args.top_k,
        require_shape_like=not args.no_shape_filter,
        filled=args.filled,
        stroke_width=args.stroke_width,
        recognition=args.recognition,
    )
    print(json.dumps(report, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mappet-spike", description="Mappet Phase 0 spike")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("build-graph", help="Fetch/cache OSM walk graph (T0.1)")
    g.add_argument("--lat", type=float, required=True)
    g.add_argument("--lng", type=float, required=True)
    g.add_argument("--distance-km", type=float, default=5.0)
    g.add_argument("--activity", choices=["run", "walk"], default="run")
    g.add_argument("--allow-busy", action="store_true")
    g.add_argument("--no-quiet", action="store_true")
    g.add_argument("--refresh", action="store_true")
    g.set_defaults(func=cmd_build_graph)

    l = sub.add_parser("loops", help="Generate candidate loops (T0.2)")
    l.add_argument("--lat", type=float, required=True)
    l.add_argument("--lng", type=float, required=True)
    l.add_argument("--distance-km", type=float, default=5.0)
    l.add_argument("--activity", choices=["run", "walk"], default="run")
    l.add_argument("--tolerance", type=float, default=0.15)
    l.add_argument("-n", type=int, default=200)
    l.set_defaults(func=cmd_loops)

    e = sub.add_parser("eval", help="Run pipeline + HTML grid (T0.4)")
    e.add_argument(
        "--origin",
        action="append",
        required=True,
        help="lat,lng[,label] — repeat for multiple origins",
    )
    e.add_argument("--distance-km", type=float, default=5.0)
    e.add_argument("--tolerance", type=float, default=0.15)
    e.add_argument("-n", type=int, default=120)
    e.add_argument("--out", type=str, default="output/eval")
    e.add_argument("--top-k", type=int, default=40)
    e.add_argument(
        "--skip-clip",
        action="store_true",
        help="Skip CLIP scoring (silhouettes only) — useful without torch",
    )
    e.add_argument(
        "--no-shape-filter",
        action="store_true",
        help="Keep skinny corridor loops (disable compactness/area filter)",
    )
    e.add_argument(
        "--filled",
        action="store_true",
        help="Render filled silhouettes instead of stroke outlines",
    )
    e.add_argument("--stroke-width", type=int, default=3)
    e.add_argument(
        "--recognition",
        choices=["baseline", "ensemble"],
        default="baseline",
        help="CLIP scoring mode: baseline single prompt, or prompt-ensemble + sketch vocab",
    )
    e.set_defaults(func=cmd_eval)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main(sys.argv[1:])
