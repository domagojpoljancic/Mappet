# Mappet 🏃‍♀️✏️🗺️

> ⚠️ **WIP — early spike in progress.** Docs are still speculative; Phase 0 recognition spike code lives under `spike/`. Nothing production-ready yet.

> **Mappet** — a working name for the GPS doodle-route finder idea described here.

**Mappet points at where you are and surfaces nearby running/walking loops whose shape, traced on the map, looks like a recognisable object** — a duck, a heart, a fish, a key. It flips the "Strava art" workflow: instead of spending hours planning a route that looks like something, Mappet scans the real street/path network around you and hands you a short list of loops that already resemble something, ready to run and export.

---

## Docs

| Doc | What it is |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Product requirements — problem, users, scope, decisions, metrics |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technical design, esp. the route-discovery engine + API contract |
| [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) | Phased plan (Phase 0 spike → MVP → stickiness → expand) |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Agent-ready tickets with acceptance criteria |

---

## Project status

### Docs
| Item | Status |
|---|---|
| PRD | ✅ Drafted (idea notes only) |
| Architecture | ✅ Drafted |
| Development plan | ✅ Drafted |
| Agent-ready backlog | ✅ Drafted |

### Phase 0 spike (`spike/`)
| Capability | Status |
|---|---|
| T0.1 OSM graph builder + disk cache + edge filter | ✅ Done |
| T0.2 Candidate loop generator (≥100 in dense cities) | ✅ Done |
| T0.3 Silhouette renderer + local CLIP | ✅ Done |
| T0.4 Human-eval HTML grid + FINDINGS.md | ✅ Done — **conditional no-go** on recognition quality (see [`spike/FINDINGS.md`](spike/FINDINGS.md)) |
| T0.5 Geometry filters (compactness/area) | ✅ Done — improves pool, still not human-recognisable |
| T0.5b Filled silhouette render (`--filled`) | ✅ Done — does not help local CLIP |
| T0.6 Alternate generators (multi-waypoint + random-walk) | ✅ Done — all three strategies fill quotas; recognition still no-go |
| T0.7 Vision-LLM top-N labeling | ⏳ Blocked on API key |

### Product (planned — not built)
| Capability | Status |
|---|---|
| Route Engine (Python/FastAPI): graph → loops → silhouette → recognise → rank | ⏳ After Phase 0 go |
| Frontend PWA (Next.js): GPS/pin, controls, results, detail | ⏳ TBD |
| GPX export + share image | ⏳ TBD |
| Strava OAuth + upload | 🔮 Fast-follow (Phase 2) |
| In-app turn-by-turn | 🔮 Later |
| Design mode (draw a chosen shape) | 🔮 Later (Phase 3) |
| Trails / cycling / offline | 🔮 Later (Phase 3) |

Legend: ✅ done · ⏳ planned/next · 🔮 later phase.

---

## Imagined MVP scope (if this were ever built)

- **Discovery only** — find recognisable shapes near you (no "draw me a specific thing" yet).
- Bar for a hit is **recognisable**, not necessarily funny.
- **Run + Walk**, city roads/paths; **distance slider 2–100 km**, loop back to start.
- Origin = **GPS by default + draggable pin**; **avoid busy roads / prefer quiet & parks**.
- **AI vision captioning** (top-N) with **local-CLIP fallback** so it runs credential-free.
- **Top 5** results, auto-named, shareable; **GPX export + open in Strava/Komoot**.
- Platform: **Next.js + TypeScript + Tailwind PWA**, mobile-first.
- Data: **OpenStreetMap** street graph + free tiles. **Near-zero-cost** to operate.

Full detail and rationale in [`docs/PRD.md`](docs/PRD.md).

---

## The one thing to prove first

The make-or-break risk is **recognition quality** — do random street loops actually look like recognisable objects? Before building the full app, run the **Phase 0 spike** (see [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) and tickets T0.1–T0.4): generate many candidate loops for a real location, render silhouettes, score with CLIP, and eyeball an HTML grid. If genuinely recognisable shapes show up, proceed to the MVP.

---

## Quick start (Phase 0 spike)

```bash
cd spike
uv sync --extra clip --extra dev
uv run pytest
uv run mappet-spike eval \
  --origin 45.8150,15.9819,Zagreb \
  --origin 52.5200,13.4050,Berlin \
  --origin 51.5074,-0.1278,London \
  --distance-km 5 -n 150 --out output/eval
```

Open `spike/output/eval/index.html`. See [`spike/README.md`](spike/README.md).

There is no full app yet. Once Phase 1 lands, this section will document `docker-compose up` for the web app + Route Engine.
