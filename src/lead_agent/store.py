"""SQLite storage: dedupes signals across runs and keeps every qualification."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import Lead, Qualification, Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  text TEXT,
  author TEXT,
  created_at TEXT,
  points INTEGER,
  query TEXT,
  first_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS qualifications (
  signal_id TEXT PRIMARY KEY REFERENCES signals(id),
  intent TEXT NOT NULL,
  fit_score INTEGER NOT NULL,
  reasons TEXT NOT NULL,
  summary TEXT NOT NULL,
  suggested_opener TEXT NOT NULL,
  model TEXT NOT NULL,
  judged_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS qualifications_score ON qualifications(fit_score DESC);
"""


class Store:
    def __init__(self, path: str | Path = ".data/leads.db"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add_signals(self, signals: list[Signal]) -> list[Signal]:
        """Inserts signals and returns only the ones not seen before."""
        fresh: list[Signal] = []
        now = datetime.now(UTC).isoformat()
        for s in signals:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    s.id,
                    s.source,
                    s.url,
                    s.title,
                    s.text,
                    s.author,
                    s.created_at.isoformat() if s.created_at else None,
                    s.points,
                    s.query,
                    now,
                ),
            )
            if cur.rowcount:
                fresh.append(s)
        self.db.commit()
        return fresh

    def save_qualifications(self, items: list[Qualification], model: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.db.executemany(
            "INSERT OR REPLACE INTO qualifications VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    q.id,
                    q.intent.value,
                    q.fit_score,
                    json.dumps(q.reasons),
                    q.summary,
                    q.suggested_opener,
                    model,
                    now,
                )
                for q in items
            ],
        )
        self.db.commit()

    def unqualified(self) -> list[Signal]:
        rows = self.db.execute(
            "SELECT s.* FROM signals s LEFT JOIN qualifications q ON q.signal_id = s.id WHERE q.signal_id IS NULL"
        ).fetchall()
        return [_signal(r) for r in rows]

    def leads(self, min_score: int = 0, limit: int = 200) -> list[Lead]:
        rows = self.db.execute(
            """SELECT s.*, q.intent, q.fit_score, q.reasons, q.summary, q.suggested_opener
               FROM qualifications q JOIN signals s ON s.id = q.signal_id
               WHERE q.fit_score >= ? AND q.intent <> 'not_relevant'
               ORDER BY q.fit_score DESC, s.created_at DESC LIMIT ?""",
            (min_score, limit),
        ).fetchall()
        return [
            Lead(
                signal=_signal(r),
                qualification=Qualification(
                    id=r["id"],
                    intent=r["intent"],
                    fit_score=r["fit_score"],
                    reasons=json.loads(r["reasons"]),
                    summary=r["summary"],
                    suggested_opener=r["suggested_opener"],
                ),
            )
            for r in rows
        ]

    def counts(self) -> dict[str, int]:
        signals = self.db.execute("SELECT count(*) FROM signals").fetchone()[0]
        judged = self.db.execute("SELECT count(*) FROM qualifications").fetchone()[0]
        return {"signals": signals, "qualified": judged}


def _signal(r: sqlite3.Row) -> Signal:
    return Signal(
        id=r["id"],
        source=r["source"],
        url=r["url"],
        title=r["title"] or "",
        text=r["text"] or "",
        author=r["author"] or "",
        created_at=datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
        points=r["points"],
        query=r["query"] or "",
    )
