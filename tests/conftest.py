from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import BaseModel

from lead_agent.models import Intent, Qualification, QualificationBatch, QueryPlan, Signal
from lead_agent.store import Store


class FakeLLM:
    """Answers structured calls from scripted handlers and records every prompt."""

    model = "fake-model"

    def __init__(
        self, judge: Callable[[dict], Qualification] | None = None, queries: list[str] | None = None
    ):
        self.judge = judge or (
            lambda post: Qualification(
                id=post["id"],
                intent=Intent.BUYING,
                fit_score=85,
                reasons=["asks for a tool"],
                summary="Needs a tool",
                suggested_opener="Hi!",
            )
        )
        self.queries = queries or ["helpdesk recommendation", "zendesk alternative"]
        self.calls: list[tuple[str, str]] = []

    def structured(self, system: str, user: str, schema: type[BaseModel]):
        self.calls.append((system, user))
        if schema is QueryPlan:
            return QueryPlan(queries=self.queries)
        if schema is QualificationBatch:
            posts = json.loads(user.split("Posts to judge (JSON):\n", 1)[1])
            return QualificationBatch(results=[self.judge(p) for p in posts])
        raise AssertionError(f"unexpected schema {schema}")


class FakeSource:
    name = "fake"

    def __init__(self, signals: list[Signal]):
        self.signals = signals
        self.queries: list[str] = []

    def search(self, query: str, days: int = 30, limit: int = 25) -> list[Signal]:
        self.queries.append(query)
        return self.signals


def signal(n: int, text: str = "We need a helpdesk") -> Signal:
    return Signal(id=f"fake:{n}", source="fake", url=f"https://example.com/{n}", title=f"Post {n}", text=text)


@pytest.fixture
def store() -> Store:
    return Store(":memory:")
