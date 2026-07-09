import logging
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .config import settings

log = logging.getLogger(__name__)

# Transfermarkt placeholder "clubs" (free agency, retirement, …). Two players
# both without a club in the same season were never teammates, so these must
# never produce squad memberships or graph edges.
PLACEHOLDER_CLUB_IDS = {"515", "123", "75"}  # Without Club, Retired, Unknown
PLACEHOLDER_CLUB_NAMES = {
    "without club",
    "vereinslos",
    "retired",
    "karriereende",
    "unknown",
    "career break",
    "pause",
    "ban",
}


def is_placeholder_club(club_id: str | None, name: str | None) -> bool:
    if club_id is not None and str(club_id) in PLACEHOLDER_CLUB_IDS:
        return True
    return bool(name) and name.strip().lower() in PLACEHOLDER_CLUB_NAMES


def connect() -> sqlite3.Connection:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations for existing databases (no migration framework yet;
    schema.sql only handles brand-new tables via CREATE TABLE IF NOT EXISTS)."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(players)")}
    if "transfers_synced_at" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN transfers_synced_at TEXT")


def _purge_placeholder_memberships(conn: sqlite3.Connection) -> None:
    """Drop memberships already recorded against placeholder clubs; runs before
    the graph is built so stale rows can't create phantom teammate edges."""
    bad_ids = set(PLACEHOLDER_CLUB_IDS)
    name_marks = ",".join("?" for _ in PLACEHOLDER_CLUB_NAMES)
    bad_ids.update(
        row["id"]
        for row in conn.execute(
            f"SELECT id FROM clubs WHERE lower(trim(name)) IN ({name_marks})",
            tuple(PLACEHOLDER_CLUB_NAMES),
        )
    )
    id_marks = ",".join("?" for _ in bad_ids)
    cur = conn.execute(
        f"DELETE FROM squad_memberships WHERE club_id IN ({id_marks})", tuple(bad_ids)
    )
    if cur.rowcount:
        log.info("purged %d placeholder-club squad memberships", cur.rowcount)


def init_db() -> None:
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with db() as conn:
        conn.executescript(schema)
        _migrate(conn)
        _purge_placeholder_memberships(conn)


def normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().strip()
