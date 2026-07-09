import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from .config import settings


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


def init_db() -> None:
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with db() as conn:
        conn.executescript(schema)
        _migrate(conn)


def normalize_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().strip()
