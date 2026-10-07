"""SQLite storage for sequences and devices.

Single file, no external database. One lock guards all access because the
scheduler thread and the API threads share the connection.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sequences (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    enabled     INTEGER NOT NULL DEFAULT 1,
    blocks      TEXT NOT NULL DEFAULT '[]',
    edges       TEXT NOT NULL DEFAULT '[]',
    timezone    TEXT NOT NULL DEFAULT 'America/Los_Angeles',
    manual_time TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    ip          TEXT NOT NULL,
    token       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'tc002',
    created_at  TEXT NOT NULL
);
"""

# Migrations for databases created before a column existed.
MIGRATIONS = [
    "ALTER TABLE sequences ADD COLUMN author TEXT DEFAULT 'user'",
]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            for mig in MIGRATIONS:
                try:
                    self._conn.execute(mig)
                except sqlite3.OperationalError:
                    pass  # column already exists
            self._conn.commit()

    # -- helpers ------------------------------------------------------
    def _row_to_sequence(self, row: sqlite3.Row) -> dict:
        # author may be missing on very old rows; default to "user".
        try:
            author = row["author"] or "user"
        except (KeyError, IndexError):
            author = "user"
        return {
            "id": row["id"],
            "name": row["name"],
            "enabled": bool(row["enabled"]),
            "blocks": json.loads(row["blocks"]),
            "edges": json.loads(row["edges"]),
            "timezone": row["timezone"],
            "manual_time": row["manual_time"],
            "author": author,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _row_to_device(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "ip": row["ip"],
            "token": row["token"],
            "type": row["type"],
            "created_at": row["created_at"],
        }

    # -- sequences ----------------------------------------------------
    def list_sequences(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sequences ORDER BY created_at").fetchall()
        return [self._row_to_sequence(r) for r in rows]

    def get_sequence(self, seq_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM sequences WHERE id = ?", (seq_id,)).fetchone()
        return self._row_to_sequence(row) if row else None

    def create_sequence(self, seq_id: str, data: dict) -> dict:
        now = _utcnow()
        with self._lock:
            self._conn.execute(
                """INSERT INTO sequences
                   (id, name, enabled, blocks, edges, timezone, manual_time, author, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    seq_id,
                    data["name"],
                    1 if data.get("enabled", True) else 0,
                    json.dumps(data.get("blocks", [])),
                    json.dumps(data.get("edges", [])),
                    data.get("timezone", "America/Los_Angeles"),
                    data.get("manual_time"),
                    data.get("author", "user"),
                    now,
                    now,
                ),
            )
            self._conn.commit()
        return self.get_sequence(seq_id)

    def update_sequence(self, seq_id: str, data: dict) -> dict | None:
        existing = self.get_sequence(seq_id)
        if not existing:
            return None
        merged = {
            "name": data.get("name", existing["name"]),
            "enabled": data.get("enabled", existing["enabled"]),
            "blocks": data.get("blocks", existing["blocks"]),
            "edges": data.get("edges", existing["edges"]),
            "timezone": data.get("timezone", existing["timezone"]),
            "manual_time": data.get("manual_time", existing["manual_time"]),
            "author": data.get("author", existing.get("author", "user")),
        }
        with self._lock:
            self._conn.execute(
                """UPDATE sequences SET name=?, enabled=?, blocks=?, edges=?,
                                      timezone=?, manual_time=?, author=?, updated_at=? WHERE id=?""",
                (
                    merged["name"],
                    1 if merged["enabled"] else 0,
                    json.dumps(merged["blocks"]),
                    json.dumps(merged["edges"]),
                    merged["timezone"],
                    merged["manual_time"],
                    merged["author"],
                    _utcnow(),
                    seq_id,
                ),
            )
            self._conn.commit()
        return self.get_sequence(seq_id)

    def delete_sequence(self, seq_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM sequences WHERE id = ?", (seq_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- devices ------------------------------------------------------
    def list_devices(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM devices ORDER BY created_at").fetchall()
        return [self._row_to_device(r) for r in rows]

    def get_device(self, dev_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM devices WHERE id = ?", (dev_id,)).fetchone()
        return self._row_to_device(row) if row else None

    def create_device(self, dev_id: str, data: dict) -> dict:
        with self._lock:
            self._conn.execute(
                "INSERT INTO devices (id, name, ip, token, type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    dev_id,
                    data["name"],
                    data["ip"],
                    data["token"],
                    data.get("type", "tc002"),
                    _utcnow(),
                ),
            )
            self._conn.commit()
        return self.get_device(dev_id)

    def delete_device(self, dev_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM devices WHERE id = ?", (dev_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def close(self):
        with self._lock:
            self._conn.close()
