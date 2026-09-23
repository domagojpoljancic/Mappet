# Product Requirements Document — Mappet

> **Name:** _Mappet_ (a.k.a. "GPS doodle route finder"). Every reference to "Mappet" below means this product.

**Status:** Draft v1 — approved scope for MVP (discovery-only).
**Owner:** Product (you).
**Last updated:** 2026-09-23.

---

## 1. One-liner

**Mappet points at where you are and surfaces nearby running/walking loops whose shape, when traced on the map, looks like a recognisable object.**

It flips the "Strava art" workflow. Instead of spending hours manually planning a route that looks like a cat, you let Mappet scan the real street/path network around you and hand you a short list of loops that already resemble something — a duck, a heart, a key, a fish — ready to run and export.

---

## 2. Background & motivation

"GPS drawing" / "Strava art" is a beloved niche: athletes plan routes that render as pictures on the map, then run them and share the artwork. Today this is:

- **Manual and slow** — hours in a route planner nudging waypoints.
- **Expert-only** — requires spatial imagination and patience.
- **Location-locked** — a great idea in one city is useless in another.

**Insight:** the street network already contains countless loops that *accidentally* look like things. Nobody has time to hunt for them. Mappet automates the hunt: it is a **discovery engine for serendipitous, recognisable route shapes**, personalised to your location and distance.

---

## 3. Goals & non-goals

### 3.1 Goals (what v1 must achieve)

- **G1 — Discovery works:** Given a location + activity + distance range, return a ranked list of loop routes that resemble recognisable objects, each with a name/label and a shape preview.
- **G2 — Runnable output:** Each route is a real, followable loop on walkable/runnable ways, returns to start, and can be exported as GPX / opened in a partner app.
- **G3 — The "wow":** The recognition/labeling must feel magical enough that a user wants to screenshot and share it.
- **G4 — Zero/low cost to operate:** Built on free OpenStreetMap data and cheap or local models; runs anywhere OSM coverage is good.
- **G5 — Agent-buildable:** Architecture and backlog are decomposed into tickets an autonomous coding agent (Cursor Auto mode) can execute mostly independently.

### 3.2 Non-goals (explicitly out of scope for v1)

- **Design mode** ("draw me a specific dog") — the reverse, target-shape planning problem. Deferred to a later phase.
- **"Funny" as a requirement** — per product decision, the bar is **recognisable**, not comedic. Humor is a nice side effect, not a filter.
- **In-app turn-by-turn navigation** — v1 exports GPX / hands off to Strava/Komoot/Garmin.
- **Native iOS/Android apps** — v1 is a mobile-first installable PWA.
- **Accounts, social feed, leaderboards** — no auth in v1 (Strava OAuth is a fast-follow, see §11).
- **Cycling & trail/hiking routing** — v1 is running + walking on city roads/paths. Trails/cycling are phase 3.

---

## 4. Target users & personas

| Persona | Who | Primary need |
|---|---|---|
| **The casual delight-seeker** | Runs/walks a few times a week, on Strava, loves a shareable moment | "Give me a fun loop from my door today, no planning." |
| **The Strava-art curious** | Has seen GPS art, wants to try but finds planning tedious | "Do the hard part for me — find the shape." |
| **The traveller** | In a new city, wants a memorable run | Drop a pin at the hotel, get a recognisable loop nearby. |

**Primary persona for v1:** the casual delight-seeker in a city, running or walking 2–100 km loops (see §6).

---

## 5. Core user stories

- **US1:** As a runner, I open the app and it uses my GPS location so I can immediately search near me.
- **US2:** As a traveller, I can drop/move a pin to plan from anywhere (home, hotel) instead of my current spot.
- **US3:** As a user, I pick an activity (run/walk) and a target distance so results match what I'm willing to do today.
- **US4:** As a user, I set preferences (avoid busy roads, prefer parks/quiet) so routes feel safe and pleasant.
- **US5:** As a user, I get a ranked list of up to 5 loops, each with a shape preview and a label ("The Duck 🦆").
- **US6:** As a user, I can open a route to see it drawn on the map and its stats (distance, est. time, surface mix).
- **US7:** As a user, I can export a route as GPX and/or open it in Strava/Komoot so I can navigate and record it.
- **US8:** As a user, I can share a route (image + link) so friends can see or run the same doodle.
- **US9:** As a user, when no strong shapes exist nearby, I'm told honestly and offered the best available / a wider search.

---

## 6. Functional requirements

### 6.1 Location & inputs
- **FR1** Request browser geolocation on demand; default the search origin to current position.
- **FR2** Allow the user to drop and drag a pin anywhere on the map to override the origin.
- **FR3** Activity selector: **Run** or **Walk** (affects allowed ways and default pace for time estimate).
- **FR4** Distance control: a slider from **2 km to 100 km** with a tolerance band (e.g. ±15%). Loop must return to the start.
- **FR5** Preferences (toggles): **Avoid busy roads** (default on), **Prefer parks/quiet streets** (default on), **Limit elevation** (default off, phase 2).

### 6.2 Route discovery engine (the core — see ARCHITECTURE.md)
- **FR6** Build a routable graph of walkable/runnable ways around the origin from OpenStreetMap, filtered by preferences (exclude motorway/trunk; down-weight busy roads; up-weight park/quiet/path ways).
- **FR7** Generate many candidate loops that (a) start and end at the origin and (b) fall within the distance tolerance band.
- **FR8** Render each candidate into a normalised silhouette image (centered, scale-normalised).
- **FR9** Score each candidate for **recognisability** using a fast image/shape model (cheap pre-filter over many candidates).
- **FR10** For the top candidates only, call a **vision model** to produce a **single-word object label + confidence** ("duck", 0.78). Cap the number of vision calls per search for cost control.
- **FR11** Rank by a blended score (recognisability + vision confidence + route quality: distance fit, loop closure, low self-overlap, safety/quietness). Return the **top 5**.
- **FR12** Each result includes: label, confidence, shape preview, map polyline, distance, estimated time, surface/quiet mix, and a stable shareable id.

### 6.3 Results & detail
- **FR13** Results list shows shape thumbnails + labels + distance; tap opens a detail view with the route on an interactive map.
- **FR14** Detail view: export **GPX**, "Open in Strava / Komoot", copy share link, and a "shape vs. map" toggle.
- **FR15** Empty/weak-result state: if no candidate exceeds a confidence threshold, say so plainly and offer "show best guesses anyway" and "widen search."

### 6.4 Sharing
- **FR16** Generate a shareable image (route drawn + label) and a link that reopens the same route (route encoded/served by id).

---

## 7. Non-functional requirements

- **NFR1 — Latency:** A search returns first results in a reasonable interactive time; show progressive/loading states and allow the heavy search to stream or poll. Long searches (large distances) must not block the UI.
- **NFR2 — Cost:** Prefer free OSM data and a free/local recognition model; vision-model calls are capped per search. Cache OSM graphs and results aggressively.
- **NFR3 — Coverage:** Works anywhere OSM has good pedestrian coverage; degrade gracefully where data is sparse.
- **NFR4 — Mobile-first:** Fully usable one-handed on a phone browser; installable PWA.
- **NFR5 — Privacy:** Location is used only to run a search; no account, no persistent tracking in v1. Location never leaves the request path beyond what the search needs. State this clearly in-app.
- **NFR6 — Reliability:** Graceful handling of geolocation denial, offline, OSM/Overpass timeouts, and vision-model failures (fall back to shape-library labels).
- **NFR7 — Accessibility:** Sufficient contrast, keyboard/screen-reader friendly controls, non-color-only cues.

---

## 8. Key product decisions (locked for v1)

| # | Decision | Choice |
|---|---|---|
| A.1 | Mode | **Discovery only** (no design/target-shape mode) |
| A.2 | Bar for a "hit" | **Recognisable object** (need not be funny) |
| B.3 | Activities | **Run + Walk**, city roads/paths first |
| B.4 | Length control | **Distance slider, 2–100 km**, loop back to start |
| C.5 | Origin | **GPS by default + draggable pin** |
| C.6 | Route preferences | Prefer quiet/parks + **avoid busy roads** |
| D.7 | Recognition | **AI vision captioning** (top-N) + **shape-library fallback** |
| D.8 | Output | **Top 5**, auto-named, shareable |
| E.9 | Navigation | **GPX export + open in Strava/Komoot** (no in-app nav) |
| E.10 | Strava | **OAuth is a fast-follow**, not in v1 |
| F.11 | Platform | **Next.js + TypeScript + Tailwind PWA**, mobile-first |
| F.12 | Maps/data | **OSM street graph** (routing/shape-finding) + **free tiles** (display) |
| G.13 | Cost | **Near-zero-cost** operation |
| G.14 | Ambition | **Usable MVP slice first**, then polish |

---

## 9. Success metrics

- **Activation:** % of searches that return ≥1 route above the recognisability threshold.
- **Wow / share:** share-image generations per session; route detail → export/share conversion.
- **Quality (human eval):** blind rating of "is this recognisable as the label?" on a sample (target: majority "yes/kinda").
- **Repeat:** returning searches per user (proxy via local storage in v1).
- **Cost:** average vision-model calls & compute per successful search (must stay within the free/near-zero budget).

---

## 10. Primary risk & de-risking

**The single biggest risk is recognition quality:** random street loops rarely resemble clean objects, and the "looks like a duck" step is what makes or breaks the product.

**Mitigations (must be validated in Phase 0):**
- Generate a **large** candidate pool so the rare good shapes surface.
- Use an **embedding/CLIP-style similarity** against a curated object vocabulary as the cheap pre-filter, so the vision model only judges pre-selected strong candidates.
- Be **honest in UX** — present results as "best matches," with confidence, and an empty-state that doesn't overpromise.
- Allow **wider search radius / larger distance** to increase the odds of a good shape.

> Phase 0 is a throwaway experiment to prove that, for a real city location, we can surface at least a few genuinely recognisable loops. Everything else is standard app-building; this is the part to prove first.

---

## 11. Fast-follows & later phases (context, not v1 scope)

- **Strava OAuth + upload** finished drawings; import past activities.
- **In-app turn-by-turn** navigation.
- **Save / collections** of favourite doodles (needs accounts + DB).
- **Design mode:** plan a route to match a chosen target shape.
- **Trails & cycling**, elevation-aware routing, offline maps.

---

## 12. Open questions (non-blocking for MVP build)

- Which specific vision model / provider for captioning (local CLIP vs. hosted vision LLM) — decided in Phase 0 based on quality vs. cost.
- Exact recognisability threshold and object vocabulary — tuned empirically in Phase 0/1.
- Which 2–3 launch cities to hand-verify quality in.

See `ARCHITECTURE.md` for the technical design and `DEVELOPMENT_PLAN.md` + `BACKLOG.md` for the agent-ready build plan.
