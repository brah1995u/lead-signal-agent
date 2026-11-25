"""Web search through Firecrawl (optional, needs FIRECRAWL_API_KEY). Keeps only the page's
title, URL and search snippet: no profile extraction."""

from __future__ import annotations

import hashlib

import httpx

from ..models import Signal

API = "https://api.firecrawl.dev/v1/search"


class FirecrawlSource:
    name = "web"

    def __init__(self, api_key: str, sites: list[str] | None = None, client: httpx.Client | None = None):
        self.api_key = api_key
        # e.g. ["reddit.com", "quora.com", "indiehackers.com"]: restricts the search to discussion sites.
        self.sites = sites or []
        self.client = client or httpx.Client(timeout=60)

    def search(self, query: str, days: int = 30, limit: int = 10) -> list[Signal]:
        site_filter = " OR ".join(f"site:{s}" for s in self.sites)
        full_query = f"{query} ({site_filter})" if site_filter else query
        response = self.client.post(
            API,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"query": full_query, "limit": min(limit, 20), "tbs": f"qdr:{'m' if days > 7 else 'w'}"},
        )
        response.raise_for_status()
        signals: list[Signal] = []
        for item in response.json().get("data", []):
            url = item.get("url")
            if not url:
                continue
            signals.append(
                Signal(
                    id="web:" + hashlib.sha1(url.encode()).hexdigest()[:16],
                    source=self.name,
                    url=url,
                    title=item.get("title") or "",
                    text=(item.get("description") or "")[:2000],
                    query=query,
                )
            )
        return signals
