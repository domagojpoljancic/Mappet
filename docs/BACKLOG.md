# Backlog — Doodler (agent-ready tickets)

Each ticket is scoped so an autonomous agent (Cursor **Auto mode**) can pick it up with just: this file's ticket + `PRD.md` + `ARCHITECTURE.md`. Every ticket has **context**, **tasks**, and **acceptance criteria** (the agent should not stop until AC pass, including build + tests).

**Legend:** `[E]` Route Engine (Python) · `[F]` Frontend (Next.js) · `[I]` Infra/glue.

---

## Phase 0 — Prove the magic (spike)

### T0.1 [E] Spike scaffold + OSM graph builder
- **Context:** ARCHITECTURE §3.1. Throwaway `spike/` folder is fine.
- **Tasks:** Python project (`uv`/`venv`), install OSMnx/NetworkX/Shapely. Function `build_graph(lat, lng, distance_km, activity, prefs)` returning a filtered pedestrian graph; exclude motorway/trunk; attach per-edge `pleasantness`. Cache graph to disk.
- **AC:** For a real coordinate, returns a non-empty graph with motorways excluded; second call hits cache (no network). Basic unit test on the edge filter.

### T0.2 [E] Candidate loop generator
- **Context:** ARCHITECTURE §3.2.
- **Tasks:** `generate_loops(graph, origin, distance_km, tolerance, n)` → list of loops (ordered polylines) starting/ending at origin, length within tolerance. Implement the out-and-different-back strategy across multiple bearings; dedupe near-identical loops.
- **AC:** Produces ≥100 distinct candidate loops for a 5 km target in a dense area; ≥90% fall within tolerance; all close within a small threshold of origin. Unit tests for length + closure.

### T0.3 [E] Silhouette renderer + CLIP recognisability
- **Context:** ARCHITECTURE §3.3–3.4.
- **Tasks:** Project polyline to metric CRS; render normalised silhouette PNG (centered, scaled, fixed stroke). Load local **open-clip**; score each silhouette vs. a curated object vocabulary; return `(label_guess, score)`.
- **AC:** Deterministic silhouette for a fixed input; produces ranked (label, score) list; runs on CPU in reasonable time for ~100 candidates.

### T0.4 [E] Human-eval HTML grid + decision writeup
- **Context:** DEVELOPMENT_PLAN Phase 0 exit criterion; ARCHITECTURE §8.
- **Tasks:** Script that runs the pipeline for a list of origins/distances and writes an HTML page: silhouette thumbnail + guessed label + score, sorted. Add a short `spike/FINDINGS.md` recording: does it work?, local CLIP vs. hosted vision decision, thresholds, candidate volume needed.
- **AC:** HTML grid generated for ≥3 real origins; `FINDINGS.md` states a clear go/no-go and the chosen recognition approach.

---

## Phase 1 — MVP app

### T1.1 [I] Monorepo + docker-compose skeleton
- **Tasks:** Repo layout: `apps/web` (Next.js) + `services/engine` (FastAPI). Root `docker-compose.yml` runs both; root README quick-start. `.env.example` for engine (vision provider optional, cache dir, call caps).
- **AC:** `docker-compose up` starts both services; web reaches engine health check.

### T1.2 [E] Engine: productionise pipeline from spike
- **Context:** ARCHITECTURE §3.
- **Tasks:** Move validated spike code into `services/engine` as clean modules: `graph`, `loops`, `render`, `recognise`, `rank`. Config via env; caching for graph/result/vision.
- **AC:** Module unit tests pass; a Python-level `search()` returns ranked top-5 for a real origin.

### T1.3 [E] Engine: FastAPI + async job API
- **Context:** ARCHITECTURE §6.
- **Tasks:** `POST /search` (returns `job_id`), `GET /search/{job_id}` (progressive/complete), `GET /route/{route_id}/gpx`, `GET /health`. Enforce time/candidate budget; honest empty-result when below threshold.
- **AC:** Endpoints match the contract; async flow returns best-so-far under budget; GPX validates as a proper track. API tests with a golden fixture graph (no network).

### T1.4 [E] Vision captioning + local fallback
- **Context:** ARCHITECTURE §3.5, §7.
- **Tasks:** Top-N captioning via chosen provider (from T0.4). If no key present, fall back to local CLIP top-1 so the app runs credential-free. Cache by silhouette hash; enforce per-search cap.
- **AC:** With no vision key set, search still returns labelled results; with a key, top-N get richer labels; call cap respected.

### T1.5 [F] Frontend scaffold + PWA shell
- **Tasks:** Next.js (App Router) + TS + Tailwind + shadcn/ui. PWA manifest + service worker; installable; mobile-first app shell. Uncommon dev port.
- **AC:** App builds and runs; Lighthouse PWA installability passes; app shell renders on mobile viewport.

### T1.6 [F] Map + geolocation + draggable pin
- **Context:** PRD FR1–FR2.
- **Tasks:** Leaflet/MapLibre with free OSM tiles; request geolocation; draggable origin pin overriding GPS; handle geolocation-denied gracefully.
- **AC:** Map shows current location by default; dragging pin updates origin; denial shows a helpful fallback (manual pin).

### T1.7 [F] Search controls (activity, distance 2–100 km, preferences)
- **Context:** PRD FR3–FR5.
- **Tasks:** Bottom-sheet controls: Run/Walk toggle, distance slider 2–100 km, "avoid busy roads" + "prefer quiet/parks" toggles (defaults on). Trigger search to engine.
- **AC:** Controls reflect PRD defaults; a search fires with correct payload; slider covers full 2–100 km range.

### T1.8 [F] Results list with shape previews + labels
- **Context:** PRD FR12–FR13.
- **Tasks:** Show top-5: silhouette thumbnail, label + confidence, distance, est. time. Loading/progress state while engine works (poll job).
- **AC:** Results render from engine response; progressive loading shown; tapping an item opens detail.

### T1.9 [F] Route detail (map + stats + shape/map toggle)
- **Context:** PRD FR13–FR14.
- **Tasks:** Full-screen route on map, stats (distance, time, surface/quiet mix), toggle between silhouette and map overlay.
- **AC:** Polyline draws correctly; stats match engine; toggle works.

### T1.10 [F] Export (GPX) + open in Strava/Komoot
- **Context:** PRD FR14; ARCHITECTURE §5.
- **Tasks:** Download GPX (from engine or client-generated); deep links / import instructions for Strava & Komoot.
- **AC:** Downloaded GPX imports cleanly into a standard tool; partner links present.

### T1.11 [F] Share image + share link
- **Context:** PRD FR16.
- **Tasks:** Render route + label to canvas → PNG for the share sheet; shareable link reopens the route by `route_id`.
- **AC:** Share image generated with route + label; opening the link restores the same route.

### T1.12 [F] Empty/weak-result & error states
- **Context:** PRD FR15, NFR6.
- **Tasks:** Honest empty-state when nothing beats threshold ("no strong shapes here") with "show best guesses" + "widen search"; handle engine/network/offline errors.
- **AC:** Forcing a weak/failed search shows the correct state and recovery actions; no crashes.

---

## Phase 2 — Stickiness (expand after Phase 1 lands)

- **T2.1 [F/E] Strava OAuth** login + upload finished drawing + import activities.
- **T2.2 [E] Recognition tuning** — vocabulary/threshold tuning, optional richer model.
- **T2.3 [F/E] Save / collections** of favourite doodles (introduces accounts + DB).
- **T2.4 [E] Performance** — result streaming, smarter caching, pre-warmed launch cities.
- **T2.5 [E] Elevation-aware** preference.
- **T2.6 [F] (Optional) in-app turn-by-turn.**

## Phase 3 — Expand

- **T3.1 Design mode** — plan a route to match a chosen target shape.
- **T3.2 Trails & cycling** routing.
- **T3.3 Offline maps** + richer sharing/social.

---

### Ticket-writing convention (for adding more)
Keep each ticket: **Context** (link PRD/ARCH sections) → **Tasks** (concrete, ordered) → **AC** (objectively checkable, includes tests + build). Size to one agent run.
