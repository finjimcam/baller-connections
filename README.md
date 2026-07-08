# Baller Connections

A daily puzzle game about football: connect two players through their real
teammate history. Given a start player and a target player, find the shortest
chain of shared clubs/seasons that links them — think "six degrees of
separation," but the graph is built from actual squad data.

> **Status:** early, actively-developed prototype (v0.2 rework). Core game
> loop, data ingestion, and UI are functional; content coverage and polish are
> still growing.

---

## How it works

1. The backend ingests historical squad data (who played for which club, in
   which season) from a self-hosted [transfermarkt-api](https://github.com/felipeall/transfermarkt-api)
   instance into a `squad_memberships` table.
2. That table is turned into an in-memory graph of players connected by
   "were teammates" edges (`backend/app/graph.py`), rebuilt on startup and
   refreshed daily.
3. Each day (and for free play) the backend picks a start/target pair from a
   pool of well-known players, at a target difficulty (`easy` / `medium` /
   `hard`, tuned by chain length — see `backend/app/puzzles.py`).
4. The player builds a chain from start to target, one shared-club link at a
   time. On completion, the result is compared against the graph's true
   shortest path (BFS) to show how close to optimal the guessed route was.
5. Players not yet in the local database are pulled in on demand
   (`lazy_import.py`) so a guess never fails just because the data hasn't
   been ingested yet.

## Tech stack

- **Frontend:** React + Vite + Tailwind CSS. The puzzle chain renders as a
  physics-driven bubble board (`d3-force`, `src/hooks/usePhysics.js`,
  `src/components/BubbleBoard.jsx`) with a search-based guess input and a
  win screen that replays the optimal route.
- **Backend:** FastAPI + SQLite (`backend/app/`), with a checkpointed/resumable
  ingest pipeline, an in-memory teammate graph, and a lazy image-caching proxy
  for player portraits/crests so the browser never hits transfermarkt's CDN
  directly.
- **Data source:** a self-hosted `transfermarkt-api` instance (pinned to a
  fixed upstream commit), scraping is rate-limited and run at most daily.
- **Infrastructure:** fully Dockerized — frontend, backend, and the
  transfermarkt-api scraper each run as their own `docker compose` service.
  Nothing runs on the host except optional Puppeteer screenshot tooling.

## Running it locally

Everything runs in containers; you don't need Node or Python installed on
the host.

```bash
cp .env.example .env   # fill in any required values
docker compose up -d --build
```

- Frontend: http://localhost:3000
- Backend (debug/curl only — the browser talks to it through the Vite proxy): http://localhost:8080

First run needs a data backfill before puzzles have real content:

```bash
docker compose exec -d backend uv run --no-sync python -m app.ingest backfill
docker compose exec backend tail -f /data/ingest.log   # watch progress
docker compose restart backend                          # rebuild the teammate graph once it's done
```

`backend/app/ingest/config/competitions.dev.yml` (one league, two seasons) is
the fast option for local testing; `competitions.yml` (top-5 leagues since
2000) is the production scope and takes a couple of hours.

## Project layout

```
src/                  React frontend
  components/         BubbleBoard, GuessInput, WinScreen, DifficultyPicker, ...
  hooks/               useGame (state/reducer), usePhysics (d3-force sim), useDebounce
  api/client.js        talks to the backend through the Vite /api proxy

backend/app/
  ingest/              squad-data backfill + daily refresh pipeline
  graph.py             in-memory teammate graph (BFS shortest path)
  puzzles.py           daily + free-play pair selection by difficulty
  lazy_import.py       on-demand import for players not yet in the DB
  images.py            caching proxy for player photos/club crests
  routers/             FastAPI route handlers (game, players)

docker-compose.yml     frontend + backend + transfermarkt-api services
```

See [`CLAUDE.md`](CLAUDE.md) for the full development/architecture reference,
and [`CHANGELOG.md`](CHANGELOG.md) for what changed in the current rework.

## Roadmap / known gaps

- Content coverage is currently limited by ingest scope (dev config is one
  league; prod config needs a multi-hour backfill to be meaningful).
- No persistent user accounts yet — daily progress is stored in
  `localStorage` per browser.
- Production-grade serving (the `runtime` Docker stage) exists but isn't
  wired into `docker-compose.yml` yet; local dev always runs the Vite dev
  server.
