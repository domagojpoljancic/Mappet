# Development Plan — Mappet

A phased, agent-oriented plan. Each phase has a **goal**, an **exit criterion** (how you know it's done), and maps to tickets in `BACKLOG.md`. It is designed so each ticket can be handed to an autonomous agent (Cursor **Auto mode**) with minimal extra context.

> Prove the risky part first. The order is deliberate: **Phase 0 de-risks recognition before any real app is built.**

---

## How to use this with agents (Auto mode)

1. Give the agent: this file, `PRD.md`, `ARCHITECTURE.md`, and the specific ticket from `BACKLOG.md`.
2. Prefer **one ticket per agent run**. Tickets are sized to be independently completable and testable.
3. Each ticket lists **acceptance criteria** — instruct the agent to not stop until those pass (build + tests).
4. Work bottom-up: engine primitives → engine pipeline → API → frontend → polish.
5. Keep the README status tables (see repo README) updated as tickets land.

---

## Phase 0 — Prove the magic (throwaway spike) 🔬

**Goal:** Demonstrate that, for a real city origin + distance, the engine can surface at least a few **genuinely recognisable** loop shapes.

**Scope:** A minimal Python script (no app, no API): build graph → generate candidates → render silhouettes → CLIP recognisability → dump an HTML grid of shapes + guessed labels for human review.

**Exit criterion:** For 3+ real origins, a human looking at the output grid says "yes, that one clearly looks like a ___" for at least a couple of routes. Decision recorded: local CLIP vs. hosted vision LLM, rough thresholds, and whether candidate volume is sufficient.

**Tickets:** T0.1–T0.4.

> If Phase 0 fails to produce recognisable shapes even with a large candidate pool and wide search, **stop and revisit the approach** before building the app — this is the whole point of doing it first.

---

## Phase 1 — MVP app (the usable slice) 🚀

**Goal:** A mobile-first PWA where a user searches from GPS/pin, sets activity + distance + preferences, and gets top-5 recognisable loops with previews, labels, map detail, and GPX export.

**Scope:**
- **Route Engine** productionised from the Phase 0 spike: FastAPI service with the full pipeline, caching, async job API, tests.
- **Frontend** Next.js PWA: map, geolocation, pin, controls, results, detail, export, share image, all key states.
- **Glue:** docker-compose, env/mock fallback, README quick-start.

**Exit criterion:** From a phone browser, a user completes US1–US8 end-to-end against the real engine for a supported city; empty-state (US9) behaves honestly; `docker-compose up` runs the whole thing locally.

**Tickets:** T1.1–T1.12.

---

## Phase 2 — Stickiness & polish ✨

**Goal:** Make it something people return to and trust.

**Scope (candidate):**
- **Strava OAuth** + upload finished drawing / import activities (fast-follow from PRD §11).
- Better recognition (tuned vocabulary/thresholds, optional in-app turn-by-turn).
- **Save / collections** of favourite doodles (introduces accounts + DB).
- Performance: result streaming, smarter caching, pre-warmed launch cities.
- Elevation-aware preference.

**Exit criterion:** A returning user can connect Strava, run a discovered route, and upload the drawing; saved doodles persist.

**Tickets:** T2.x (to be expanded when Phase 1 lands).

---

## Phase 3 — Expand the surface 🌄

**Goal:** Broaden who and where it serves.

**Scope (candidate):**
- **Design mode:** plan a route to match a chosen target shape (the reverse problem).
- **Trails & cycling**, offline maps, richer sharing/social.

**Exit criterion:** defined when Phase 2 is stable.

---

## Cross-cutting workstreams (apply every phase)

- **Testing:** engine unit tests + golden fixtures; frontend component/e2e; human-eval harness (see ARCHITECTURE §8).
- **Cost guardrails:** cache everything cacheable; cap vision calls; prefer local models (NFR2).
- **Privacy:** no tracking in v1; clear location-use messaging (NFR5).
- **Docs/README hygiene:** keep the WIP banner + status tables current on every push.

---

## Milestone summary

| Phase | Outcome | Gate |
|---|---|---|
| **0** | Recognition proven on real data | Human says shapes are recognisable |
| **1** | Usable MVP PWA + engine, GPX export | Full US1–US9 e2e locally |
| **2** | Strava, saves, better recognition | Return-user loop closes |
| **3** | Design mode, trails, offline | TBD |

See `BACKLOG.md` for the concrete, agent-ready tickets.
