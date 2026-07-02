"""
SQLite wrapper para persistir tokens OAuth de QuickBooks Online.
Siempre usa id=1 (una sola cuenta conectada).
"""
import sqlite3
import os
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("QBO_DB_PATH", "qbo_tokens.db"))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tokens (
    id            INTEGER PRIMARY KEY,
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    realm_id      TEXT NOT NULL,
    company_name  TEXT,
    updated_at    TEXT NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute(_SCHEMA)
    c.commit()
    return c


def save_tokens(
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    realm_id: str,
    company_name: str = "",
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO tokens (id, access_token, refresh_token, expires_at,
                                realm_id, company_name, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                access_token  = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at    = excluded.expires_at,
                realm_id      = excluded.realm_id,
                company_name  = excluded.company_name,
                updated_at    = excluded.updated_at
            """,
            (
                access_token,
                refresh_token,
                expires_at.isoformat(),
                realm_id,
                company_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def get_tokens() -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM tokens WHERE id = 1").fetchone()
        if row is None:
            return None
        return dict(row)


def has_tokens() -> bool:
    return get_tokens() is not None


def clear_tokens() -> None:
    with _conn() as c:
        c.execute("DELETE FROM tokens WHERE id = 1")
