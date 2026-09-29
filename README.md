# Mappet 🏃‍♀️✏️🗺️

> **Status: archived concept — not an active product.**  
> This repository is a personal idea / Phase 0 recognition spike for a GPS “doodle route” finder. Development is **not continuing**. It is kept here as a reference / archive only.  
> **Do not treat this as a finished, maintained, or production-ready project.**

> **Mappet** — a working name for the GPS doodle-route finder idea described here.

**Mappet points at where you are and surfaces nearby running/walking loops whose shape, traced on the map, looks like a recognisable object** — a duck, a heart, a fish, a key. It flips the "Strava art" workflow: instead of spending hours planning a route that looks like something, Mappet scans the real street/path network around you and hands you a short list of loops that already resemble something, ready to run and export.

---

## Project status

**Archived concept / spike.** Docs plus a throwaway Python Phase 0 spike (`spike/`) that builds OSM graphs, generates candidate loops, renders silhouettes, and scores them with local CLIP. Recognition quality did **not** clear the go/no-go bar (see [`spike/FINDINGS.md`](spike/FINDINGS.md)). No full app was built. **Not maintained.**

If you found this on my GitHub profile: it is a learning / exploration experiment I chose to keep, not a shipping app.

---

## Docs

| Doc | What it is |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | Product requirements — problem, users, scope, decisions, metrics |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Technical design, esp. the route-discovery engine + API contract |
| [`docs/DEVELOPMENT_PLAN.md`](docs/DEVELOPMENT_PLAN.md) | Phased plan (Phase 0 spike → MVP → stickiness → expand) |
| [`docs/BACKLOG.md`](docs/BACKLOG.md) | Agent-ready tickets with acceptance criteria |
| [`spike/FINDINGS.md`](spike/FINDINGS.md) | Phase 0 go/no-go writeup |

---

## What was explored (spike)

### Docs
| Item | Status |
|---|---|
| PRD / Architecture / Dev plan / Backlog | ✅ Drafted (idea notes) |

### Phase 0 spike (`spike/`)
| Capability | Status |
|---|---|
| OSM graph builder + cache + edge filter | ✅ Done |
| Candidate loop generators (out-back / multi-waypoint / random-walk) | ✅ Done |
| Silhouette renderer + local CLIP | ✅ Done |
| Geometry filters + CLIP prompt tuning | ✅ Done — no meaningful recognition gain |
| Human-eval HTML grid + FINDINGS | ✅ Done — **conditional no-go** |
| Full MVP app (Next.js + FastAPI) | ❌ Not built |

---

## Quick start (spike only)

```bash
cd spike
uv sync --extra clip --extra dev
uv run pytest
uv run mappet-spike eval \
  --origin 45.8150,15.9819,Zagreb \
  --distance-km 5 -n 100 --out output/eval
```

Open `spike/output/eval/index.html`. Details in [`spike/README.md`](spike/README.md).
