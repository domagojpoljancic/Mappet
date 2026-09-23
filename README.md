# Mappet 🏃‍♀️✏️🗺️

> ⚠️ **Just a random idea — still very early.** This began as a napkin-sketch brainstorm. There is now a **minimal runnable dev slice** (a frontend + a mock route engine) so the idea can be explored end-to-end, but it is **far from a product** and the "magic" (real route recognition) is **not built yet**. Treat everything here as experimental.

> **Mappet** — a working name for the GPS doodle-route finder idea described here.

**Mappet points at where you are and surfaces nearby running/walking loops whose shape, traced on the map, looks like a recognisable object** — a duck, a heart, a fish, a key. It flips the "Strava art" workflow: instead of spending hours planning a route that looks like something, Mappet scans the real street/path network around you and hands you a short list of loops that already resemble something, ready to run and export.

---

## 🚧 Where this is

The repository now contains a **thin, runnable vertical slice** that matches the documented architecture, plus the original idea notes. What runs today:

- **`apps/web`** — a Next.js + TypeScript + Tailwind frontend with an interactive Leaflet/OpenStreetMap map, geolocation + draggable origin pin, activity/distance/preference controls, a results list, and per-route GPX download.
- **`services/engine`** — a FastAPI **Route Engine** implementing the API contract from `docs/ARCHITECTURE.md`. Its pipeline is currently a **credential-free mock** that synthesises deterministic recognisable loop shapes around the origin, so the whole stack works with **zero external credentials**. The real graph → loops → silhouette → CLIP-recognition pipeline is the Phase 0/1 work in `docs/BACKLOG.md`.

The idea notes are structured *as if* they were specs so they can be handed to autonomous coding agents (Cursor **Auto mode**).

Start here:

| Doc | What it is |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Product requirements — problem, users, scope, decisions, metrics |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technical design, esp. the route-discovery engine + API contract |
| [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) | Phased plan (Phase 0 spike → MVP → stickiness → expand) |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Agent-ready tickets with acceptance criteria |

---

## Quick start

Requirements: **Node.js 20+** (developed on Node 22) and **Python 3.11+**.

```bash
git clone https://github.com/domagojpoljancic/mappet.git
cd mappet

# One-shot install for both apps (frontend deps + engine venv)
bash scripts/setup.sh
```

Then run the two services in separate terminals:

```bash
# Terminal 1 — Route Engine (FastAPI) on :8000
cd services/engine && . .venv/bin/activate && uvicorn app.main:app --port 8000

# Terminal 2 — Frontend (Next.js) on :4311
cd apps/web && npm run dev
```

Open **http://localhost:4311**, then click **✨ Find shapes**. The map draws the top-5 mock loops; click a result (or a route on the map) to highlight it, and use **GPX** to download a track.

> The frontend reads the engine URL from `NEXT_PUBLIC_ENGINE_URL` (default `http://localhost:8000`). See `apps/web/.env.example`.

---

## Project layout

```
apps/web/           Next.js + TS + Tailwind PWA-style frontend (Leaflet map)
services/engine/    FastAPI route engine (mock pipeline + tests)
scripts/setup.sh    Idempotent installer for both apps
docs/               PRD, architecture, development plan, backlog
.cursor/            Cloud Agent environment config
```

---

## Development

| Command | Where | What it does |
|---|---|---|
| `npm run dev` | `apps/web` | Next.js dev server on port 4311 |
| `npm run build` | `apps/web` | Production build + type check |
| `npm run lint` | `apps/web` | ESLint (next/core-web-vitals) |
| `npm run typecheck` | `apps/web` | `tsc --noEmit` |
| `uvicorn app.main:app --port 8000` | `services/engine` | Run the route engine |
| `python -m pytest` | `services/engine` | Engine unit tests |

### Route Engine API (see `docs/ARCHITECTURE.md` §6)

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe |
| `POST /search` | Return ranked top-5 loops for an origin/activity/distance |
| `GET /search/{job_id}` | Fetch a previous search (polling shape) |
| `GET /route/{route_id}/gpx` | Download a route as a GPX track |

---

## Project status

### Docs
| Item | Status |
|---|---|
| PRD | ✅ Drafted (idea notes) |
| Architecture | ✅ Drafted |
| Development plan | ✅ Drafted |
| Agent-ready backlog | ✅ Drafted |

### Product
| Capability | Status |
|---|---|
| Frontend scaffold (map, controls, results, GPX) | ✅ Runnable slice |
| Route Engine API (FastAPI) + GPX export | ✅ Runnable (mock pipeline) |
| Cloud Agent environment (`.cursor/environment.json`) | ✅ Done |
| Real Route Engine: graph → loops → silhouette → recognise → rank | ⏳ TBD (Phase 0/1) |
| Phase 0 recognition spike | ⏳ TBD (build first — de-risks everything) |
| GPX export + share image | 🟡 GPX done; share image TBD |
| Strava OAuth + upload | 🔮 Fast-follow (Phase 2) |
| Design mode / trails / offline | 🔮 Later (Phase 3) |

Legend: ✅ done · 🟡 partial · ⏳ planned/next · 🔮 later phase.

---

## The one thing to prove first

The make-or-break risk is **recognition quality** — do random street loops actually look like recognisable objects? The current engine returns *mock* shapes so the app is demonstrable; before investing in the full app, run the **Phase 0 spike** (see [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md), tickets T0.1–T0.4) to replace the mock with real graph loops scored by CLIP and eyeball an HTML grid. If genuinely recognisable shapes show up, proceed to the MVP.

---

## How to build this with agents (Auto mode)

1. Pick a ticket from [`docs/BACKLOG.md`](docs/BACKLOG.md) (start with T0.1).
2. Hand the agent that ticket + `PRD.md` + `ARCHITECTURE.md`.
3. Prefer one ticket per agent run; require its acceptance criteria (build + tests) to pass.
4. Work bottom-up: engine primitives → pipeline → API → frontend → polish.
5. Keep these status tables current as tickets land.
