# Mappet 🏃‍♀️✏️🗺️

> ⚠️ **Just a random idea — nothing more.** This is an early, half-baked brainstorm, **very far from a product** (or a company, a commitment, or a plan anyone is executing). Nothing here has been built, tested, or validated. Treat everything below as a napkin sketch that may never happen.

> **Mappet** — a working name for the GPS doodle-route finder idea described here.

**Mappet points at where you are and surfaces nearby running/walking loops whose shape, traced on the map, looks like a recognisable object** — a duck, a heart, a fish, a key. It flips the "Strava art" workflow: instead of spending hours planning a route that looks like something, Mappet scans the real street/path network around you and hands you a short list of loops that already resemble something, ready to run and export.

---

## 🚧 Just notes — no application code, no active project

This repository currently contains **rough idea notes only**. There is **no runnable app**, no team, no timeline — just some speculative "what if" writing. The notes are structured *as if* they were specs so they could, in theory, be handed to autonomous coding agents (Cursor **Auto mode**) — but nobody is doing that today, and this may never go anywhere.

Start here:

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

### Product (planned — not built)
| Capability | Status |
|---|---|
| Phase 0 recognition spike | ⏳ TBD (build first — de-risks everything) |
| Route Engine (Python/FastAPI): graph → loops → silhouette → recognise → rank | ⏳ TBD |
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

## How to build this with agents (Auto mode)

1. Pick a ticket from [`docs/BACKLOG.md`](docs/BACKLOG.md) (start with T0.1).
2. Hand the agent that ticket + `PRD.md` + `ARCHITECTURE.md`.
3. Prefer one ticket per agent run; require its acceptance criteria (build + tests) to pass.
4. Work bottom-up: engine primitives → pipeline → API → frontend → polish.
5. Keep these status tables current as tickets land.

---

## Quick start

There is nothing to run yet. Once Phase 1 lands, this section will document `docker-compose up` for the web app + Route Engine, plus a credential-free local mode. Until then, read the docs above.
