"""On-demand import of players that exist on Transfermarkt but not in our seed.

Used as a fallback so an unknown player never produces an internal error:
search falls back to the live TM search, and validating a guess against a
player without memberships pulls their profile + transfer history, derives
(club, season) stints, and patches the in-memory graph.
"""

import logging
import sqlite3
from datetime import date
from urllib.parse import quote

from .db import normalize_name
from .graph import Graph
from .tm_client import TMClient, TMError, TMNotFound, TMUnavailable

log = logging.getLogger(__name__)

SEASON_BREAK_MONTH = 7  # seasons run Jul 1 -> Jun 30; season id = starting year


def _season_of(d: date) -> int:
    return d.year if d.month >= SEASON_BREAK_MONTH else d.year - 1


def _seasons_between(start: date, end: date) -> list[int]:
    return list(range(_season_of(start), _season_of(end) + 1))


def _position_of(profile: dict) -> str | None:
    pos = profile.get("position")
    if isinstance(pos, dict):
        return pos.get("main")
    if isinstance(pos, str):
        return pos
    return None


def _nationality_of(payload: dict) -> str | None:
    for key in ("citizenship", "nationalities", "nationality"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            return ", ".join(str(v) for v in value)
        if isinstance(value, str) and value:
            return value
    return None


def upsert_player_stub(
    conn: sqlite3.Connection,
    player_id: str,
    name: str,
    position: str | None = None,
    nationality: str | None = None,
    date_of_birth: str | None = None,
    market_value: int | None = None,
    image_url: str | None = None,
    imported: int = 1,
) -> None:
    conn.execute(
        """INSERT INTO players
             (id, name, normalized_name, position, nationality, date_of_birth,
              peak_market_value, imported, image_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name = excluded.name,
             normalized_name = excluded.normalized_name,
             position = COALESCE(excluded.position, players.position),
             nationality = COALESCE(excluded.nationality, players.nationality),
             date_of_birth = COALESCE(excluded.date_of_birth, players.date_of_birth),
             peak_market_value = MAX(COALESCE(players.peak_market_value, 0),
                                     COALESCE(excluded.peak_market_value, 0)),
             imported = MIN(players.imported, excluded.imported),
             image_url = COALESCE(excluded.image_url, players.image_url)""",
        (
            player_id,
            name,
            normalize_name(name),
            position,
            nationality,
            date_of_birth,
            market_value,
            imported,
            image_url,
        ),
    )


def _stints_from_transfers(payload: dict) -> list[tuple[str, str, list[int]]]:
    """Derive [(club_id, club_name, [season_year, ...])] from the transfer timeline."""
    dated: list[tuple[date, str, str]] = []
    for t in payload.get("transfers", []):
        if t.get("upcoming"):
            continue
        club = t.get("clubTo") or {}
        club_id = club.get("id")
        try:
            moved = date.fromisoformat(t["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if not club_id:
            continue
        dated.append((moved, str(club_id), club.get("name") or ""))
    dated.sort(key=lambda item: item[0])
    stints: list[tuple[str, str, list[int]]] = []
    today = date.today()
    for i, (start_d, club_id, club_name) in enumerate(dated):
        end_d = dated[i + 1][0] if i + 1 < len(dated) else today
        if end_d < start_d:
            continue
        stints.append((club_id, club_name, _seasons_between(start_d, end_d)))
    return stints


async def ensure_player_known(
    conn: sqlite3.Connection, tm: TMClient, graph: Graph, player_id: str
) -> sqlite3.Row | None:
    """Make sure the player's full TM transfer history has been pulled at least once,
    patching in any (club, season) stints the competition-scoped ingest never covered
    (e.g. a spell in a league outside the ingest config). Returns the player row, or
    None when the id is genuinely unknown. A TM outage degrades to whatever we already
    have — never raises.

    Gated on transfers_synced_at rather than membership_count: an ingested player can
    already have plenty of memberships from their top-5-league clubs and still be
    missing stints elsewhere, so "has some memberships" is not "fully resolved"."""
    row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
    if row and row["transfers_synced_at"]:
        return row

    try:
        profile = await tm.get(f"/players/{quote(player_id)}/profile")
    except TMNotFound:
        return row  # unknown on TM too (or only known locally as a stub)
    except (TMUnavailable, TMError):
        log.warning("lazy import: TM unavailable for player %s", player_id)
        return row

    market_value = profile.get("marketValue")
    upsert_player_stub(
        conn,
        player_id,
        name=profile.get("name") or (row["name"] if row else player_id),
        position=_position_of(profile),
        nationality=_nationality_of(profile),
        date_of_birth=profile.get("dateOfBirth"),
        market_value=market_value if isinstance(market_value, int) else None,
        image_url=profile.get("imageUrl"),
    )
    conn.execute(
        "UPDATE players SET profile_synced_at = datetime('now') WHERE id = ?", (player_id,)
    )

    try:
        transfers = await tm.get(f"/players/{quote(player_id)}/transfers")
        transfers_fetched = True
    except (TMNotFound, TMUnavailable, TMError):
        transfers = None
        transfers_fetched = False

    if transfers:
        inserted: set[tuple[str, str]] = set()
        for club_id, club_name, seasons in _stints_from_transfers(transfers):
            if club_name:
                conn.execute(
                    """INSERT INTO clubs (id, name) VALUES (?, ?)
                       ON CONFLICT(id) DO NOTHING""",
                    (club_id, club_name),
                )
            for season in seasons:
                conn.execute(
                    """INSERT OR IGNORE INTO squad_memberships
                       (player_id, club_id, season_id) VALUES (?, ?, ?)""",
                    (player_id, club_id, str(season)),
                )
                inserted.add((club_id, str(season)))
        conn.execute(
            """UPDATE players SET membership_count =
                 (SELECT COUNT(*) FROM squad_memberships m WHERE m.player_id = players.id)
               WHERE id = ?""",
            (player_id,),
        )
        # Patch the in-memory graph with edges to already-known squads.
        for club_id, season_id in inserted:
            teammates = [
                r["player_id"]
                for r in conn.execute(
                    "SELECT player_id FROM squad_memberships WHERE club_id = ? AND season_id = ?",
                    (club_id, season_id),
                )
            ]
            graph.add_player(player_id, teammates)
        log.info(
            "lazy import: player %s imported with %d club-season stints", player_id, len(inserted)
        )

    if transfers_fetched:
        # Only mark synced on a successful fetch (even an empty one) — a TM outage
        # should leave this unset so the next validate() retries instead of silently
        # skipping the player's stints forever.
        conn.execute(
            "UPDATE players SET transfers_synced_at = datetime('now') WHERE id = ?",
            (player_id,),
        )

    conn.commit()
    return conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()


async def search_fallback(
    conn: sqlite3.Connection, tm: TMClient, query: str, limit: int
) -> list[sqlite3.Row]:
    """Live TM player search used only when the local search finds nothing."""
    try:
        payload = await tm.get(f"/players/search/{quote(query)}")
    except (TMNotFound, TMUnavailable, TMError):
        return []
    ids: list[str] = []
    for result in payload.get("results", [])[:limit]:
        player_id = result.get("id")
        name = result.get("name")
        if not player_id or not name:
            continue
        market_value = result.get("marketValue")
        upsert_player_stub(
            conn,
            str(player_id),
            name=name,
            position=result.get("position"),
            nationality=_nationality_of(result),
            market_value=market_value if isinstance(market_value, int) else None,
        )
        ids.append(str(player_id))
    conn.commit()
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM players WHERE id IN ({placeholders})", ids
    ).fetchall()
    order = {pid: i for i, pid in enumerate(ids)}
    return sorted(rows, key=lambda r: order.get(r["id"], 99))
