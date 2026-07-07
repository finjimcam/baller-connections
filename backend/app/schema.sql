CREATE TABLE IF NOT EXISTS players (
  id                TEXT PRIMARY KEY,          -- transfermarkt player id
  name              TEXT NOT NULL,
  normalized_name   TEXT NOT NULL,             -- lowercase, accents stripped
  position          TEXT,
  nationality       TEXT,                      -- comma-joined list
  date_of_birth     TEXT,                      -- ISO date
  peak_market_value INTEGER,                   -- EUR, MAX over all squad rows seen
  membership_count  INTEGER NOT NULL DEFAULT 0,
  imported          INTEGER NOT NULL DEFAULT 0,-- 1 = pulled on demand, not part of the seed
  image_url         TEXT,
  profile_synced_at TEXT,
  image_cached_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_players_norm ON players(normalized_name);
CREATE INDEX IF NOT EXISTS idx_players_fame ON players(peak_market_value DESC);

CREATE TABLE IF NOT EXISTS clubs (
  id               TEXT PRIMARY KEY,           -- transfermarkt club id
  name             TEXT NOT NULL,
  crest_url        TEXT,
  is_national_team INTEGER NOT NULL DEFAULT 0
);

-- The edge source: two players are connected if they share a (club, season) row.
CREATE TABLE IF NOT EXISTS squad_memberships (
  player_id TEXT NOT NULL,
  club_id   TEXT NOT NULL,
  season_id TEXT NOT NULL,                     -- starting year, "2015" = 2015/16
  PRIMARY KEY (player_id, club_id, season_id)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_memb_club_season ON squad_memberships(club_id, season_id);

-- Per club-season ingest bookkeeping; re-runs skip 'done' rows.
CREATE TABLE IF NOT EXISTS sync_state (
  club_id   TEXT NOT NULL,
  season_id TEXT NOT NULL,
  status    TEXT NOT NULL DEFAULT 'pending',   -- pending | done | error
  synced_at TEXT,
  error     TEXT,
  PRIMARY KEY (club_id, season_id)
);

CREATE TABLE IF NOT EXISTS daily_puzzles (
  puzzle_date      TEXT PRIMARY KEY,           -- YYYY-MM-DD (UTC)
  start_player_id  TEXT NOT NULL,
  target_player_id TEXT NOT NULL,
  shortest_len     INTEGER NOT NULL,           -- hops on the day it was generated
  created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
