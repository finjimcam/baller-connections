import hashlib
import logging
import random
import sqlite3
from datetime import datetime, timezone

from .config import settings
from .graph import Graph
from .models import StintLink

log = logging.getLogger(__name__)

# difficulty -> (min hops, max hops, fame pool size)
DIFFICULTIES = {
    "easy": (2, 2, 200),
    "medium": (3, 4, 800),
    "hard": (5, 6, 2500),
}

DAILY_BAND = (3, 5, 400)


class PuzzleUnavailable(Exception):
    pass


def fame_pool(conn: sqlite3.Connection, n: int) -> list[str]:
    rows = conn.execute(
        """SELECT id FROM players WHERE imported = 0
           ORDER BY COALESCE(peak_market_value, 0) DESC, membership_count DESC, id
           LIMIT ?""",
        (n,),
    ).fetchall()
    return [r["id"] for r in rows]


def _pick_pair(
    graph: Graph,
    pool: list[str],
    rng: random.Random,
    lo: int,
    hi: int,
    attempts: int = 60,
) -> tuple[str, str, int] | None:
    if not pool:
        return None
    for _ in range(attempts):
        start = rng.choice(pool)
        dist = graph.distances_from(start, hi)
        # iterate the pool list (stable order) so daily picks are deterministic
        candidates = [p for p in pool if p != start and lo <= dist.get(p, 99) <= hi]
        if candidates:
            target = rng.choice(candidates)
            return start, target, dist[target]
    return None


def get_daily(conn: sqlite3.Connection, graph: Graph) -> tuple[str, str, str, int]:
    """Returns (date, start_id, target_id, par). Persisted on first generation."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT * FROM daily_puzzles WHERE puzzle_date = ?", (today,)
    ).fetchone()
    if row:
        return today, row["start_player_id"], row["target_player_id"], row["shortest_len"]

    seed = hashlib.sha256(f"{today}:{settings.daily_salt}".encode()).hexdigest()
    rng = random.Random(seed)
    lo, hi, pool_size = DAILY_BAND
    pool = fame_pool(conn, pool_size)
    if len(pool) < 20:
        raise PuzzleUnavailable("not enough players in the database — run the ingest backfill")
    picked = _pick_pair(graph, pool, rng, lo, hi) or _pick_pair(graph, pool, rng, 2, 6)
    if picked is None:
        raise PuzzleUnavailable("could not find a suitable daily pair")
    start, target, dist = picked
    conn.execute(
        """INSERT OR IGNORE INTO daily_puzzles
           (puzzle_date, start_player_id, target_player_id, shortest_len, created_at)
           VALUES (?, ?, ?, ?, datetime('now'))""",
        (today, start, target, dist),
    )
    conn.commit()
    log.info("daily puzzle %s: %s -> %s (par %d)", today, start, target, dist)
    return today, start, target, dist


def free_game(
    conn: sqlite3.Connection, graph: Graph, difficulty: str
) -> tuple[str, str, int]:
    if difficulty not in DIFFICULTIES:
        raise PuzzleUnavailable(f"unknown difficulty: {difficulty}")
    lo, hi, pool_size = DIFFICULTIES[difficulty]
    pool = fame_pool(conn, pool_size)
    if len(pool) < 20:
        raise PuzzleUnavailable("not enough players in the database — run the ingest backfill")
    rng = random.Random()
    picked = _pick_pair(graph, pool, rng, lo, hi) or _pick_pair(graph, pool, rng, 2, 6)
    if picked is None:
        raise PuzzleUnavailable("could not find a pair for this difficulty")
    return picked


def _season_label(season_id: str) -> str:
    if not season_id.isdigit():
        return season_id
    year = int(season_id)
    return f"{year}/{(year + 1) % 100:02d}"


def _collapse_seasons(years: list[int]) -> list[str]:
    """[2015, 2016, 2017, 2020] -> ["2015/16–2017/18", "2020/21"]"""
    labels: list[str] = []
    run_start = prev = years[0]
    for y in years[1:] + [None]:
        if y is not None and y == prev + 1:
            prev = y
            continue
        if run_start == prev:
            labels.append(_season_label(str(run_start)))
        else:
            labels.append(f"{_season_label(str(run_start))}–{_season_label(str(prev))}")
        if y is not None:
            run_start = prev = y
    return labels


def shared_stints(conn: sqlite3.Connection, a: str, b: str) -> list[StintLink]:
    """All (club, season) squads the two players shared, grouped per club."""
    rows = conn.execute(
        """SELECT c.id AS club_id, c.name AS club_name, c.is_national_team,
                  m1.season_id
           FROM squad_memberships m1
           JOIN squad_memberships m2
             ON m1.club_id = m2.club_id AND m1.season_id = m2.season_id
           JOIN clubs c ON c.id = m1.club_id
           WHERE m1.player_id = ? AND m2.player_id = ?
           ORDER BY c.name, m1.season_id""",
        (a, b),
    ).fetchall()
    links: list[StintLink] = []
    by_club: dict[str, dict] = {}
    for r in rows:
        entry = by_club.setdefault(
            r["club_id"],
            {"name": r["club_name"], "nt": bool(r["is_national_team"]), "years": []},
        )
        if r["season_id"].isdigit():
            entry["years"].append(int(r["season_id"]))
    for club_id, entry in by_club.items():
        years = sorted(set(entry["years"]))
        links.append(
            StintLink(
                club_id=club_id,
                club_name=entry["name"],
                is_national_team=entry["nt"],
                crest=f"/api/clubs/{club_id}/crest",
                seasons=_collapse_seasons(years) if years else [],
            )
        )
    return links
