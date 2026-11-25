"""Hacker News through the public Algolia search API (no key needed)."""

from __future__ import annotations

import html
import re
import time
from datetime import UTC, datetime

import httpx

from ..models import Signal

API = "https://hn.algolia.com/api/v1/search"
_TAG = re.compile(r"<[^>]+>")


def clean_html(text: str) -> str:
    text = text.replace("<p>", "\n\n")
    return html.unescape(_TAG.sub("", text)).strip()


class HackerNewsSource:
    name = "hackernews"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=20, headers={"User-Agent": "lead-signal-agent/0.2"})

    def search(self, query: str, days: int = 30, limit: int = 30) -> list[Signal]:
        since = int(time.time()) - days * 86_400
        response = self.client.get(
            API,
            params={
                "query": query,
                "tags": "(story,comment)",
                "numericFilters": f"created_at_i>{since}",
                "hitsPerPage": min(limit, 100),
            },
        )
        response.raise_for_status()
        signals: list[Signal] = []
        for hit in response.json().get("hits", []):
            is_comment = "comment" in hit.get("_tags", [])
            text = clean_html(hit.get("comment_text") or hit.get("story_text") or "")
            title = hit.get("title") or hit.get("story_title") or ""
            if not (text or title):
                continue
            signals.append(
                Signal(
                    id=f"hn:{hit['objectID']}",
                    source=self.name,
                    url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    title=("Re: " + title) if is_comment and title else title,
                    text=text[:4000],
                    author=hit.get("author") or "",
                    created_at=datetime.fromtimestamp(hit["created_at_i"], UTC)
                    if hit.get("created_at_i")
                    else None,
                    points=hit.get("points"),
                    query=query,
                )
            )
        return signals
