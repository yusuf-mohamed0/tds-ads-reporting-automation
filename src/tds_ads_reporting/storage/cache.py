from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "reporting.sqlite"

log = logging.getLogger("tds.storage")


@dataclass
class CacheEntry:
    client_id: str
    month: str
    platform: str
    payload: dict[str, Any]
    fetched_at: str


class SummaryCache:
    """SQLite-backed cache for per-client/month API summaries."""

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                client_id TEXT NOT NULL,
                month TEXT NOT NULL,
                platform TEXT NOT NULL,
                payload TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (client_id, month, platform)
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def get(self, client_id: str, month: str, platform: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT payload FROM summaries WHERE client_id=? AND month=? AND platform=?",
            (client_id, month, platform),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def set(self, client_id: str, month: str, platform: str, payload: dict[str, Any]) -> None:
        self._conn.execute(
            """
            INSERT INTO summaries (client_id, month, platform, payload, fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(client_id, month, platform)
            DO UPDATE SET payload=excluded.payload, fetched_at=excluded.fetched_at
            """,
            (
                client_id,
                month,
                platform,
                json.dumps(payload, ensure_ascii=False),
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def list_months(self, client_id: str | None = None) -> list[str]:
        if client_id:
            rows = self._conn.execute(
                "SELECT DISTINCT month FROM summaries WHERE client_id=? ORDER BY month DESC",
                (client_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT DISTINCT month FROM summaries ORDER BY month DESC"
            ).fetchall()
        return [r[0] for r in rows]
