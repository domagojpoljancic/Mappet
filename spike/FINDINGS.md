# Phase 0 findings — does the magic work?

**Date:** 2026-09-23  
**Pipeline:** OSM walk graph → out-and-different-back loops → white-on-black silhouette → open-clip `ViT-B-32` / `openai` vs curated vocabulary  
**Origins:** Zagreb (45.815, 15.982), Berlin (52.520, 13.405), London (51.507, −0.128) at **5 km ±15%**

Eval artifact: `spike/output/eval/index.html` (regenerate with `uv run mappet-spike eval …`).

---

## What we proved (engineering)

| Claim | Result |
|---|---|
| Non-empty filtered walk graphs for real cities | ✅ Zagreb 11.6k nodes / 31k edges; Berlin 18k/46k; London 18k/48k |
| Motorway/trunk excluded + pleasantness attached | ✅ unit-tested |
| Disk cache skips Overpass on second call | ✅ |
| ≥100 distinct in-tolerance loops in a dense area | ✅ Zagreb **150**, Berlin **144** (London 92 — close; denser sampling recovers it) |
| Deterministic silhouette PNGs | ✅ |
| Local CLIP ranks candidates credential-free on CPU | ✅ ~30–60s / city after model load |

So the **plumbing works**. The Phase 0 *product* question is different.

---

## Recognition quality (the actual gate)

Top CLIP cosine scores clustered tightly around **0.33–0.36**. Dominant labels were generic (`house`, `guitar`, `horse`, `airplane`, `bicycle`, `smile`) — not crisp object hits.

Eyeballing the top-ranked silhouettes (London “bicycle” 0.355, Zagreb “horse” 0.354, etc.): they read as **street-grid zigzags / out-and-back corridors**, not as a bicycle, horse, duck, or heart. A human would not say “that clearly looks like a ___” for the current top-N.

### Why this happens (hypotheses)

1. **Candidate shapes are too corridor-like.** Out-and-different-back still produces skinny, self-similar polygons even after overlap filtering.
2. **CLIP on sparse line drawings is weakly calibrated.** Absolute similarities are low and labels collapse to a few vocabulary favourites.
3. **No geometric pre-filter** for compactness, symmetry, or “blob-iness” before ranking — CLIP sees mostly noise.

---

## Decision

### Go / no-go for building the MVP app

**Conditional no-go on recognition quality; go on continuing the spike.**

- **Do not** start the full Next.js + FastAPI MVP yet — Phase 0 exit criterion (“human says that clearly looks like a ___”) is **not met** with the current candidate pool + local CLIP alone.
- **Do** keep iterating the spike (cheap) before Phase 1:
  1. Bias loop search toward higher **compactness / area / symmetry** (and reject skinny corridors).
  2. Try **thicker strokes / filled silhouettes** and a shortlist of sketch-style prompts.
  3. Run a **hosted vision LLM** on the top ~20 CLIP (or geometry) candidates for richer labels — keep local CLIP as the free pre-filter.
  4. Target **≥300–500** diverse candidates per search before declaring failure.

### Chosen recognition approach (for now)

| Stage | Choice | Rationale |
|---|---|---|
| Pre-filter (many) | **Local open-clip ViT-B-32** | $0, works offline, fast enough for hundreds of candidates |
| Rich label (top-N) | **Hosted vision LLM (next spike iteration)** | Local CLIP labels are not trustworthy enough alone |
| Threshold | Treat CLIP score **&lt; ~0.40** as “weak / unscored” until we see better separation | Current top hits are ~0.35 and still unrecognisable |
| Candidate volume | Aim **≥200–500** after geometry filters | 100–150 raw loops is achievable; quality filters will shrink the pool |

---

## Suggested next spike tickets

- **T0.5** Geometry-aware loop filters — ✅ done (see addendum).
- **T0.6** Alternate generators (multi-waypoint + random-walk) — ✅ done (all three strategies now fill quotas on Zagreb).
- **T0.6b** CLIP prompt/vocab/stroke tuning — ✅ done; **no meaningful gain**.
- **T0.7** Vision-LLM captioning on top-N + side-by-side HTML with CLIP.
- **T0.8** Re-run human eval; only then open Phase 1 (T1.1+).

---

## Addendum — T0.5 geometry filters (same night)

Filter: `compactness ≥ 0.08`, `area ≥ 40 000 m²`, `aspect ≤ 4`, `bbox_fill ≥ 0.08`. Over-generate 3× candidates then cull.

| City | Raw loops | Shape-like kept |
|---|---:|---:|
| Zagreb | 450 | **227** |
| Berlin | 365 | **243** |
| London | 291 | **220** |

Top shaped CLIP scores rose slightly (best **0.374**) and a Berlin candidate was labelled **fish** (C=0.27). Eyeballing still does **not** yield “clearly a fish/horse” — shapes are plumper corridors, not recognisable doodles. Geometry filtering is necessary but **not sufficient**.

**Unchanged decision:** stay in spike mode; try thicker/filled rendering + vision-LLM top-N next (T0.6/T0.7). Do not start Phase 1 MVP yet.

---

## Addendum — filled silhouettes (Zagreb smoke)

`--filled` render mode added. Zagreb-only re-run (240 raw → 128 shape-like → top 20): best CLIP fell to **~0.33** (vs ~0.37 stroke), labels still generic. Filled blobs can look more “object-like” to humans, but **local CLIP alone does not benefit**. **Vision-LLM on top-N remains the next high-leverage experiment** (needs an API key — not run overnight).

---

## Addendum — T0.6 alternate generators

Mixed strategies with reserved quotas:

| Strategy | Zagreb raw (n=360 pool) | Notes |
|---|---:|---|
| `out_back` | 120 | Quiet-biased band fill |
| `multi_waypoint` | 120 | Circle waypoints → polygonal circuits |
| `random_walk` | **120** | Fixed: homes when projected length enters ±15% band |

Shape-like after filter: **127 / 360**. Best CLIP still **~0.36**, labels still generic. All three strategies now contribute; recognition quality under local CLIP is **unchanged** (still conditional no-go).

**Unchanged decision:** no MVP yet. Next high-leverage step remains **vision-LLM top-N** (needs API key).

---

## Addendum — CLIP prompt / render tuning

Compared on 59 Zagreb shape-like loops (`scripts/tune_clip.py`):

| Variant | mean | max | Dominant labels |
|---|---:|---:|---|
| baseline stroke3 | 0.314 | 0.346 | house, guitar, key |
| thick stroke8 | 0.309 | 0.338 | key, guitar |
| sketch vocab only | 0.263 | 0.297 | star, key, anchor |
| **ensemble + sketch vocab** | **0.317** | 0.346 | house, anchor, boot |
| ensemble + thick | 0.313 | 0.341 | anchor, boot |
| invert B/W ensemble | 0.298 | 0.330 | house, boot |
| filled ensemble | 0.311 | 0.360 | house, anchor |

Best mean delta vs baseline: **+0.0025** (not meaningful). Local CLIP prompt/vocab/stroke tricks do **not** unlock recognisable doodles.

Shipped: `--recognition ensemble` and `SKETCH_VOCABULARY` for optional use; default stays baseline.

**Still blocked:** T0.7 vision-LLM (no API key in environment).

---

## Repro

```bash
cd spike
uv sync --extra clip --extra dev
uv run pytest
uv run mappet-spike eval \
  --origin 45.8150,15.9819,Zagreb \
  --origin 52.5200,13.4050,Berlin \
  --origin 51.5074,-0.1278,London \
  --distance-km 5 -n 150 --out output/eval-shaped
```
