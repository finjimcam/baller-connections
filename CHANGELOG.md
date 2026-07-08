# Changelog

## 0.2 — Full rework

This version is a ground-up rebuild of Baller Connections as a real,
Dockerized full-stack app, replacing whatever came before with an
actual game backed by real football data instead of a static prototype.

- **Rebuilt as a Dockerized service topology.** Frontend, backend, and a
  self-hosted `transfermarkt-api` scraper now run as three `docker compose`
  services on one network, with the browser reaching the backend through the
  Vite dev proxy (no CORS). Nothing runs on the host except optional
  screenshot tooling.
- **Added a real backend.** FastAPI + SQLite replaces any client-only logic:
  a checkpointed, resumable ingest pipeline pulls squad history from
  transfermarkt-api into `squad_memberships`; an in-memory graph
  (`graph.py`) turns that into teammate edges and answers shortest-path
  queries via BFS; `puzzles.py` selects daily and free-play start/target
  pairs by difficulty band from a market-value-ranked fame pool.
- **Added on-demand player import.** `lazy_import.py` pulls a player's
  profile and transfer history live the first time they're guessed, so the
  game never fails a guess just because ingestion hasn't reached that player
  yet.
- **Added an image caching proxy.** `images.py` lazily fetches and caches
  player portraits and club crests so the browser never calls out to
  transfermarkt's CDN directly, and a zero-byte cache entry permanently
  short-circuits repeated "no image" lookups.
- **Built the actual game UI.** Physics-based bubble board
  (`d3-force` via `usePhysics`/`BubbleBoard`) with elastic cursor attraction
  and draggable bubbles, a search-combobox guess input, a difficulty picker,
  loading/error states, and a win screen that compares the player's route
  against the graph's true shortest path.
- **Added daily scheduling.** An in-process scheduler refreshes the
  current season's data once a day (`DAILY_REFRESH_HOUR_UTC`) and rebuilds
  the in-memory graph after ingest runs.
- **Added dev tooling.** Flat-config ESLint 9 setup, a host-run Puppeteer
  screenshot script (`screenshot.mjs`) for visual review against reference
  designs, and a documented ingest runbook.
- **Fixed:** backfill no longer aborts on a single failed competition page —
  it now skips and continues, with a raised scrape timeout to reduce
  false failures on slow responses.

## 0.1 — Scaffold

- Initial dockerized React + Vite + Tailwind SPA scaffold.
