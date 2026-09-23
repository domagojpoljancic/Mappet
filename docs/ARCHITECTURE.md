# Architecture — Mappet

> ⚠️ **Just a random idea — very far from a product.** This is a speculative sketch of *how one might* build the idea. None of it exists or has been implemented; treat it as thinking-out-loud, not a real system.

This document describes a possible technical design for Mappet, with emphasis on the **route-discovery engine** (the hard, differentiating part). It is written to be actionable for autonomous coding agents, *if* the idea is ever pursued.

> Read alongside `PRD.md` (what/why) and `DEVELOPMENT_PLAN.md` + `BACKLOG.md` (how/when).

---

## 1. High-level shape

```
┌──────────────────────────────────────────────────────────────┐
│  Client — Next.js PWA (TypeScript, Tailwind, shadcn/ui)        │
│  • Geolocation + draggable pin (Leaflet / MapLibre)            │
│  • Activity + distance slider + preference toggles             │
│  • Results list, route detail, GPX export, share image         │
└───────────────▲───────────────────────────┬──────────────────┘
                │ REST/JSON (poll or stream) │
┌───────────────┴───────────────────────────▼──────────────────┐
│  Route Engine — Python service (FastAPI)                       │
│  1. Fetch/cebuild routable graph from OSM (bbox around origin) │
│  2. Generate candidate loops (distance-bounded, return-to-start)│
│  3. Render normalised silhouettes                              │
│  4. Cheap recognisability pre-filter (CLIP/embedding + shapes) │
│  5. Vision captioning on top-N (label + confidence)           │
│  6. Rank → return top 5 with polylines + metadata             │
└───────────────┬───────────────────────────┬──────────────────┘
                │                            │
        ┌───────▼────────┐          ┌────────▼─────────┐
        │ OSM data        │          │ Vision model      │
        │ (Overpass /     │          │ (hosted vision    │
        │  extracts) +    │          │  LLM or local     │
        │  graph cache    │          │  CLIP)            │
        └─────────────────┘          └───────────────────┘
```

**Why two services (Next.js + Python)?** The discovery core needs the mature geospatial + CV Python ecosystem (OSMnx, NetworkX, NumPy, Shapely, OpenCV, open-clip). Doing that in TS would be fighting the tooling. The Next.js app owns UX, PWA, sharing, and export; the Python **Route Engine** owns the heavy lifting. They talk over a small REST contract (§6). For local dev they run side by side; a `docker-compose` ties them together.

> If the building agent finds a compelling all-TypeScript path for Phase 1 that keeps quality, that's acceptable — but the default and recommended split is Next.js + Python.

---

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (App Router) + TypeScript | PWA, mobile-first |
| Styling/UI | Tailwind CSS + shadcn/ui | Use shadcn primitives, don't hand-roll |
| Map display | Leaflet or MapLibre GL + free OSM tiles | Free tile source; respect usage policy |
| Route engine | Python 3.11+ + FastAPI + Uvicorn | Heavy compute service |
| Geo/graph | OSMnx, NetworkX, Shapely, GeoPandas | Graph build + routing + geometry |
| Rendering/CV | NumPy, OpenCV / Pillow, Matplotlib (offscreen) | Silhouette rasterisation |
| Recognition (cheap) | open-clip (local) or hosted embeddings | Similarity vs. object vocabulary |
| Recognition (rich) | Hosted vision LLM **or** local CLIP top-1 | Label + confidence, top-N only |
| Caching | On-disk graph cache + result cache (Redis or file) | Cost & latency control |
| GPX | Server- or client-side GPX writer | Standard `.gpx` track |
| Packaging | Docker + docker-compose | One-command local run |

**Cost posture (G4/NFR2):** OSM + local CLIP = ~$0 marginal. If a hosted vision LLM is used, cap calls to top-N (e.g. ≤8) per search and cache by candidate-shape hash.

---

## 3. The route-discovery engine (core algorithm)

### 3.1 Build the routable graph
- Input: origin `(lat, lng)`, distance target `D`, activity, preferences.
- Determine a **search radius** from `D` (a loop of length `D` roughly fits in radius `~D / (2π)` to `~D/4`; use a generous multiplier and clamp for large `D`).
- Fetch the pedestrian/running graph for the bounding box via OSMnx (`network_type='walk'`) or Overpass. **Cache** the graph per (rounded bbox, network_type).
- **Edge weighting by preference:**
  - Exclude `highway in {motorway, trunk, motorway_link, trunk_link}` and non-walkable ways.
  - **Avoid busy roads:** up-weight (penalise) `primary`/`secondary` and high-`maxspeed` / no-sidewalk ways.
  - **Prefer quiet/parks:** down-weight (reward) `path`, `footway`, `pedestrian`, `living_street`, `residential`, and ways inside/adjacent to parks (`leisure=park`, `landuse=recreation_ground`).
  - Store a per-edge `pleasantness` score for later route-quality ranking.

### 3.2 Generate candidate loops
Goal: many distinct loops that start and end at the origin and have length in `[D·(1-tol), D·(1+tol)]`.

Recommended strategies (implement one solid one first, add others to improve variety):
- **Randomised out-and-different-back:** pick a random far anchor at ~`D/2` graph-distance, shortest path out, penalise used edges, shortest path back → a loop; repeat with many anchors/seeds.
- **Directional exploration:** sample anchors across bearings (N/NE/E/…) to diversify shapes.
- **Random-walk with length budget** biased by `pleasantness`, closing back to origin.
- Deduplicate near-identical loops (geometry hash / Fréchet-ish similarity). Aim for a candidate pool in the hundreds; cap by a time budget.

### 3.3 Normalise & render silhouettes
- Convert each loop to an ordered polyline (project to a local metric CRS so aspect ratio is correct).
- Render to a fixed square canvas: center, scale to fit with padding, consistent stroke width, white-on-black (or black-on-white) — a clean **line-drawing silhouette**.
- Keep both the raster (for the model) and the raw polyline (for the map/GPX).

### 3.4 Recognisability pre-filter (cheap, over many)
- Embed each silhouette with **CLIP** (image encoder) and compare (cosine similarity) against a **curated object vocabulary** of text/image prompts ("a simple line drawing of a duck", "…a heart", "…a fish", letters, etc.).
- Score = best match similarity; keep a `label_guess` + `score`.
- Optionally add classic shape cues (compactness, symmetry, closed-ness via Hu moments) as tie-breakers.
- Sort; take **top-N** (e.g. 8) for the rich step.

### 3.5 Rich captioning (top-N only)
- Either take CLIP top-1 label directly, **or** send the top-N silhouettes to a **vision LLM** with a strict prompt:
  > "This is a route drawn on a map. What single everyday object does this line most resemble? Reply with one lowercase noun and a confidence 0–1. If nothing recognisable, reply 'none'."
- Parse `{label, confidence}`. Cache by silhouette hash. Enforce the per-search call cap.

### 3.6 Rank & return
- Blended score, e.g.:
  `score = w1·recognisability + w2·vision_confidence + w3·distance_fit + w4·loop_closure + w5·mean_pleasantness − w6·self_overlap`
- Drop candidates below a **confidence threshold** (feeds the honest empty-state, FR15).
- Return **top 5** with: `label`, `confidence`, `distance_m`, `est_time_s`, `pleasantness`, `surface_mix`, `polyline` (encoded or coordinate list), `silhouette_png` (or URL), and a stable `route_id`.

### 3.7 Performance & UX
- Enforce a **time/candidate budget** per search; return best-so-far if hit.
- Support **async**: `POST /search` returns a `job_id`; client polls `GET /search/{job_id}` for progressive results (NFR1). A synchronous mode is fine for small `D` in early phases.

---

## 4. Data & caching
- **Graph cache:** keyed by rounded bbox + network_type; disk-persisted (GraphML/pickle). Avoid re-hitting Overpass for nearby searches.
- **Result cache:** keyed by (rounded origin, activity, distance bucket, prefs); short TTL. Big latency + cost win for repeated/nearby searches.
- **Vision cache:** keyed by silhouette hash.
- **Launch cities:** optionally pre-warm graphs for 2–3 hand-verified cities.

---

## 5. Frontend design notes
- **Mobile-first**, one-handed. Bottom sheet for controls; full-screen map.
- States for: locating, searching (progress), results, detail, empty/weak, geolocation-denied, offline, engine-error.
- **PWA:** manifest + service worker; installable; cache the app shell.
- **Share image:** render route + label to a canvas → PNG for share sheet; share link reopens by `route_id`.
- **Export:** GPX download + deep links to Strava/Komoot route import where supported.

---

## 6. API contract (Client ⇆ Route Engine)

`POST /search`
```jsonc
// request
{
  "origin": { "lat": 45.815, "lng": 15.982 },
  "activity": "run",            // "run" | "walk"
  "distance_km": 5.0,
  "tolerance": 0.15,
  "preferences": { "avoid_busy_roads": true, "prefer_quiet": true }
}
// response (sync) or via job polling
{
  "job_id": "abc123",
  "status": "complete",         // "pending" | "running" | "complete" | "error"
  "results": [
    {
      "route_id": "r_001",
      "label": "duck",
      "confidence": 0.78,
      "distance_m": 5120,
      "est_time_s": 1830,
      "pleasantness": 0.82,
      "surface_mix": { "park": 0.4, "residential": 0.5, "other": 0.1 },
      "polyline": [[45.815,15.982], [45.816,15.983], "..."],
      "silhouette_png": "data:image/png;base64,..." // or URL
    }
  ]
}
```

`GET /search/{job_id}` → same response shape (for async polling).
`GET /route/{route_id}/gpx` → `.gpx` file (or export handled client-side).

---

## 7. Environment & secrets
- `.env` for the Route Engine: vision-model provider + key (optional if using local CLIP), Overpass endpoint override, cache dir, call caps.
- Provide a **local/mock fallback**: if no vision key, use local CLIP top-1 so the app runs with zero external credentials (NFR2/NFR5). Document this in the README.

---

## 8. Testing strategy
- **Engine unit tests:** graph filtering (excludes motorways), loop length within tolerance, loop closure, silhouette normalisation determinism.
- **Golden fixtures:** a few saved OSM subgraphs so tests don't hit the network; snapshot the top labels for a known origin.
- **Frontend:** component tests for controls/states; e2e happy path (search → results → detail → export) against a mocked engine.
- **Human eval harness:** script that runs N origins and dumps silhouettes+labels to an HTML grid for quick "recognisable? y/n" review (this is how Phase 0 is judged).
