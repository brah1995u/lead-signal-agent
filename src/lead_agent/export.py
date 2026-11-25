"""Deterministic exports (the original asked an LLM to write the spreadsheet)."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Lead

COLUMNS = [
    "score",
    "intent",
    "summary",
    "suggested_opener",
    "title",
    "url",
    "source",
    "author",
    "posted",
    "reasons",
]


def rows(leads: list[Lead]) -> list[list[str]]:
    return [
        [
            str(lead.qualification.fit_score),
            lead.qualification.intent.value,
            lead.qualification.summary,
            lead.qualification.suggested_opener,
            lead.signal.title,
            lead.signal.url,
            lead.signal.source,
            lead.signal.author,
            lead.signal.created_at.date().isoformat() if lead.signal.created_at else "",
            " | ".join(lead.qualification.reasons),
        ]
        for lead in leads
    ]


def to_csv(leads: list[Lead], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows(rows(leads))
    return path


def to_google_sheets(leads: list[Lead], spreadsheet: str, credentials_file: str) -> str:
    """Writes leads to the first worksheet of an existing spreadsheet (shared with the service
    account). Needs the `sheets` extra: uv sync --extra sheets."""
    import gspread

    client = gspread.service_account(filename=credentials_file)
    sheet = client.open(spreadsheet).sheet1
    sheet.clear()
    sheet.update([COLUMNS, *rows(leads)])
    return sheet.url
