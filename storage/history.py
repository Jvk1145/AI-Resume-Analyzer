"""SQLite history of past analyses (scores only; no resume text is stored)."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    file_name TEXT NOT NULL,
    ats_score INTEGER NOT NULL,
    jd_match REAL,
    missing_skills TEXT NOT NULL DEFAULT '[]'
)
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open the database, creating the folder and table if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def add_record(
    file_name: str,
    ats_score: int,
    jd_match: Optional[float],
    missing_skills: list[str],
    db_path: Path = DEFAULT_DB,
    created_at: Optional[datetime] = None,
) -> int:
    """Store one analysis and return its row id."""
    timestamp = (created_at or datetime.now()).isoformat(timespec="seconds")
    with closing(_connect(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO analyses (created_at, file_name, ats_score, jd_match, missing_skills) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, file_name, int(ats_score), jd_match, json.dumps(missing_skills[:10])),
        )
        return int(cursor.lastrowid or 0)


def fetch_history(db_path: Path = DEFAULT_DB, limit: int = 500) -> list[dict[str, Any]]:
    """Return past analyses, oldest first."""
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT * FROM (SELECT * FROM analyses ORDER BY created_at DESC, id DESC LIMIT ?) "
            "ORDER BY created_at ASC, id ASC",
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "file_name": row["file_name"],
            "ats_score": row["ats_score"],
            "jd_match": row["jd_match"],
            "missing_skills": json.loads(row["missing_skills"] or "[]"),
        }
        for row in rows
    ]


def clear_history(db_path: Path = DEFAULT_DB) -> None:
    """Delete all stored analyses."""
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM analyses")
