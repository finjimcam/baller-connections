"""Config-driven, checkpointed ingest from the self-hosted transfermarkt-api.

Every (club, season) squad is one API request tracked in `sync_state`; re-runs
skip rows already marked done, so an interrupted backfill resumes for free.
All requests flow through the globally rate-limited TMClient.
"""

import logging
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from ..db import connect, normalize_name
from ..lazy_import import upsert_player_stub
from ..tm_client import TMClient, TMError, TMNotFound, TMUnavailable

log = logging.getLogger(__name__)

LOCK_KEY = "ingest_lock"
LOCK_STALE_AFTER = timedelta(hours=6)


class IngestLocked(RuntimeError):
    pass


def current_season() -> int:
    today = date.today()
    return today.year if today.month >= 7 else today.year - 1


def season_range(spec: dict) -> list[int]:
    to = spec.get("to", "current")
    to_year = current_season() if to == "current" else int(to)
    return list(range(int(spec["from"]), to_year + 1))


def load_config(path: str) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg.setdefault("competitions", [])
    cfg.setdefault("clubs", [])
    return cfg


def acquire_lock(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (LOCK_KEY,)).fetchone()
    if row:
        try:
            held_since = datetime.fromisoformat(row["value"])
        except ValueError:
            held_since = None
        if held_since and datetime.now(timezone.utc) - held_since < LOCK_STALE_AFTER:
            raise IngestLocked(f"another ingest has held the lock since {row['value']}")
        log.warning("taking over stale ingest lock from %s", row["value"])
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (LOCK_KEY, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def release_lock(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM meta WHERE key = ?", (LOCK_KEY,))
    conn.commit()


def _upsert_club(
    conn: sqlite3.Connection, club_id: str, name: str, is_national_team: bool = False
) -> None:
    conn.execute(
        """INSERT INTO clubs (id, name, is_national_team) VALUES (?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             is_national_team = MAX(clubs.is_national_team, excluded.is_national_team)""",
        (club_id, name, int(is_national_team)),
    )


def _mark_pending(conn: sqlite3.Connection, club_id: str, season_id: str) -> None:
    conn.execute(
        """INSERT INTO sync_state (club_id, season_id, status) VALUES (?, ?, 'pending')
           ON CONFLICT(club_id, season_id) DO NOTHING""",
        (club_id, season_id),
    )


async def _sync_club_lists(
    tm: TMClient, conn: sqlite3.Connection, cfg: dict, only_season: int | None = None
) -> None:
    """Resolve competitions to club lists, seeding clubs + pending sync_state rows.
    Competition-season pages already seen are skipped via meta keys, except the
    season passed as only_season (used by refresh to catch promoted clubs)."""
    for comp in cfg["competitions"]:
        comp_id = str(comp["id"])
        for season in season_range(comp["seasons"]):
            if only_season is not None and season != only_season:
                continue
            meta_key = f"comp_synced:{comp_id}:{season}"
            seen = conn.execute("SELECT 1 FROM meta WHERE key = ?", (meta_key,)).fetchone()
            if seen and season != only_season:
                continue
            try:
                payload = await tm.get(f"/competitions/{comp_id}/clubs", {"season_id": season})
            except TMNotFound:
                log.warning("competition %s season %s not found, skipping", comp_id, season)
                continue
            clubs = payload.get("clubs", [])
            for club in clubs:
                club_id = str(club.get("id") or "")
                if not club_id:
                    continue
                _upsert_club(conn, club_id, club.get("name") or club_id)
                _mark_pending(conn, club_id, str(season))
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (meta_key, "1"))
            conn.commit()
            log.info("competition %s season %s: %d clubs", comp_id, season, len(clubs))

    for club in cfg["clubs"]:
        club_id = str(club["id"])
        _upsert_club(conn, club_id, club.get("name") or club_id, bool(club.get("is_national_team")))
        for season in season_range(club["seasons"]):
            _mark_pending(conn, club_id, str(season))
    conn.commit()


async def _sync_pending_squads(tm: TMClient, conn: sqlite3.Connection) -> None:
    pending = conn.execute(
        """SELECT s.club_id, s.season_id, c.name AS club_name
           FROM sync_state s JOIN clubs c ON c.id = s.club_id
           WHERE s.status != 'done'
           ORDER BY s.season_id, s.club_id"""
    ).fetchall()
    total = len(pending)
    if not total:
        log.info("no pending club-seasons — nothing to do")
        return
    log.info("syncing %d pending club-season squads", total)
    started = time.monotonic()
    for i, row in enumerate(pending, start=1):
        club_id, season_id = row["club_id"], row["season_id"]
        try:
            payload = await tm.get(f"/clubs/{club_id}/players", {"season_id": season_id})
        except (TMNotFound, TMUnavailable, TMError) as exc:
            conn.execute(
                """UPDATE sync_state SET status = 'error', error = ?, synced_at = datetime('now')
                   WHERE club_id = ? AND season_id = ?""",
                (str(exc)[:500], club_id, season_id),
            )
            conn.commit()
            log.warning("[%d/%d] %s %s FAILED: %s", i, total, row["club_name"], season_id, exc)
            continue
        players = payload.get("players", [])
        for p in players:
            player_id = str(p.get("id") or "")
            name = p.get("name")
            if not player_id or not name:
                continue
            nationality = p.get("nationality")
            market_value = p.get("marketValue")
            upsert_player_stub(
                conn,
                player_id,
                name=name,
                position=p.get("position"),
                nationality=", ".join(nationality) if isinstance(nationality, list) else nationality,
                date_of_birth=p.get("dateOfBirth"),
                market_value=market_value if isinstance(market_value, int) else None,
                imported=0,
            )
            conn.execute(
                """INSERT OR IGNORE INTO squad_memberships (player_id, club_id, season_id)
                   VALUES (?, ?, ?)""",
                (player_id, club_id, season_id),
            )
        conn.execute(
            """UPDATE sync_state SET status = 'done', error = NULL, synced_at = datetime('now')
               WHERE club_id = ? AND season_id = ?""",
            (club_id, season_id),
        )
        conn.commit()
        elapsed = time.monotonic() - started
        eta_min = (elapsed / i) * (total - i) / 60
        log.info(
            "[%d/%d] %s %s — %d players, ETA %.0f min",
            i, total, row["club_name"], season_id, len(players), eta_min,
        )


def _update_membership_counts(conn: sqlite3.Connection) -> None:
    conn.execute(
        """UPDATE players SET membership_count =
             (SELECT COUNT(*) FROM squad_memberships m WHERE m.player_id = players.id)"""
    )
    conn.commit()


async def backfill(tm: TMClient, config_path: str) -> None:
    cfg = load_config(config_path)
    conn = connect()
    acquire_lock(conn)
    try:
        await _sync_club_lists(tm, conn, cfg)
        await _sync_pending_squads(tm, conn)
        _update_membership_counts(conn)
        log.info("backfill complete")
    finally:
        release_lock(conn)
        conn.close()


async def refresh(tm: TMClient, config_path: str) -> None:
    """Daily job: re-pull only the current season's squads (they change intra-season)."""
    cfg = load_config(config_path)
    season = current_season()
    conn = connect()
    acquire_lock(conn)
    try:
        conn.execute("UPDATE sync_state SET status = 'pending' WHERE season_id = ?", (str(season),))
        conn.commit()
        await _sync_club_lists(tm, conn, cfg, only_season=season)
        await _sync_pending_squads(tm, conn)
        _update_membership_counts(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_refresh', datetime('now'))"
        )
        conn.commit()
        log.info("refresh of season %s complete", season)
    finally:
        release_lock(conn)
        conn.close()


async def enrich_photos(tm: TMClient, top_n: int) -> None:
    """Pre-fetch profiles + portraits for the fame pool (players eligible to be
    puzzle endpoints), so daily puzzles always have faces from day one."""
    from ..config import settings

    conn = connect()
    try:
        rows = conn.execute(
            """SELECT id, name, image_url, profile_synced_at FROM players WHERE imported = 0
               ORDER BY COALESCE(peak_market_value, 0) DESC, membership_count DESC, id
               LIMIT ?""",
            (top_n,),
        ).fetchall()
        total = len(rows)
        log.info("enriching photos for top %d players", total)
        for i, row in enumerate(rows, start=1):
            player_id, image_url = row["id"], row["image_url"]
            if not image_url and not row["profile_synced_at"]:
                try:
                    profile = await tm.get(f"/players/{player_id}/profile")
                except (TMNotFound, TMUnavailable, TMError) as exc:
                    log.warning("[%d/%d] profile %s failed: %s", i, total, row["name"], exc)
                    continue
                image_url = profile.get("imageUrl")
                conn.execute(
                    """UPDATE players SET image_url = ?, profile_synced_at = datetime('now'),
                         date_of_birth = COALESCE(date_of_birth, ?)
                       WHERE id = ?""",
                    (image_url, profile.get("dateOfBirth"), player_id),
                )
                conn.commit()
            cache = Path(settings.image_cache_dir) / "players" / f"{player_id}.jpg"
            if cache.exists():
                continue
            cache.parent.mkdir(parents=True, exist_ok=True)
            if not image_url or "default" in image_url:
                cache.touch()  # permanent "no portrait" sentinel
                continue
            data = await tm.get_image(image_url)
            if data:
                cache.write_bytes(data)
                conn.execute(
                    "UPDATE players SET image_cached_at = datetime('now') WHERE id = ?",
                    (player_id,),
                )
                conn.commit()
            if i % 50 == 0:
                log.info("[%d/%d] photo enrichment progress", i, total)
        log.info("photo enrichment complete")
    finally:
        conn.close()
