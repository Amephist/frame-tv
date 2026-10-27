"""Maps TV content_ids back to the museum works they came from."""
import sqlite3
from contextlib import closing

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS uploads (
    content_id TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    source_id  TEXT NOT NULL,
    title      TEXT,
    artist     TEXT,
    date       TEXT,
    mode       TEXT,
    matte      TEXT,
    bytes      INTEGER,
    created    TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


with closing(_conn()) as c:
    c.execute(SCHEMA)


def replace(old_content_ids: list[str], row: dict) -> None:
    """Drop rows for old_content_ids and add row, in one transaction."""
    with closing(_conn()) as c, c:
        c.executemany("DELETE FROM uploads WHERE content_id = ?", [(cid,) for cid in old_content_ids])
        c.execute(
            "INSERT INTO uploads (content_id, source, source_id, title, artist, date, mode, matte, bytes)"
            " VALUES (:content_id, :source, :source_id, :title, :artist, :date, :mode, :matte, :bytes)",
            row,
        )


def remove(content_id: str) -> None:
    with closing(_conn()) as c, c:
        c.execute("DELETE FROM uploads WHERE content_id = ?", (content_id,))


def all_by_content_id() -> dict[str, dict]:
    with closing(_conn()) as c:
        return {r["content_id"]: dict(r) for r in c.execute("SELECT * FROM uploads")}


def find(source: str, source_id: str) -> list[str]:
    with closing(_conn()) as c:
        rows = c.execute("SELECT content_id FROM uploads WHERE source = ? AND source_id = ?", (source, source_id))
        return [r[0] for r in rows]
