"""The two LLM steps: turn an ICP into search queries, and judge found signals against it."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from .icp import icp_prompt
from .llm import LLM, LLMError
from .models import ICP, Intent, Qualification, QualificationBatch, QueryPlan, Signal

PLANNER_SYSTEM = """You plan searches that find people and companies who need a product right now.
Write short keyword queries (2-5 words) for a full-text search engine over public discussions.
Mix: the problem in the customer's words, "looking for"/"recommend" + category, and switching away from
known alternatives. Do not include site names, quotes or boolean operators."""

JUDGE_SYSTEM = """You qualify sales leads for a B2B team. For each public post decide:
- intent: buying (actively looking to buy or switch), asking_for_recommendation, describing_a_problem the product
  solves, unhappy_with_competitor, hiring (wants to hire for this work), or not_relevant.
- fit_score 0-100 for the ideal customer profile. 80+ only with clear intent AND a good customer fit.
  Sellers promoting their own product, job seekers, students, news and opinion pieces are not_relevant (score < 20).
- reasons: up to three short facts from the post.
- summary: one sentence on what they need.
- suggested_opener: the first sentence of a genuinely helpful public reply (no hard sell); empty if not relevant.
Judge only from the post text. Copy each id exactly."""


def plan_queries(icp: ICP, llm: LLM, max_queries: int = 6) -> list[str]:
    plan = llm.structured(PLANNER_SYSTEM, icp_prompt(icp), QueryPlan)
    seen: set[str] = set()
    queries: list[str] = []
    for q in plan.queries:
        q = " ".join(q.replace('"', "").split())
        if q and q.lower() not in seen:
            seen.add(q.lower())
            queries.append(q)
    return queries[:max_queries]


def _batches(items: list[Signal], size: int) -> Iterator[list[Signal]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _post_block(s: Signal) -> dict:
    return {"id": s.id, "title": s.title, "text": s.text[:1500], "source": s.source}


def qualify(signals: Iterable[Signal], icp: ICP, llm: LLM, batch_size: int = 8) -> Iterator[Qualification]:
    """Judges signals in batches. Results the model invents for unknown ids are dropped, and a
    batch that fails is retried one post at a time so one bad post doesn't lose the batch."""
    items = list(signals)
    for batch in _batches(items, batch_size):
        try:
            yield from _judge(batch, icp, llm)
        except LLMError:
            if len(batch) == 1:
                continue
            for single in batch:
                try:
                    yield from _judge([single], icp, llm)
                except LLMError:
                    continue


def _judge(batch: list[Signal], icp: ICP, llm: LLM) -> list[Qualification]:
    ids = {s.id for s in batch}
    user = (
        f"Ideal customer profile:\n{icp_prompt(icp)}\n\n"
        f"Posts to judge (JSON):\n{json.dumps([_post_block(s) for s in batch], ensure_ascii=False)}"
    )
    result = llm.structured(JUDGE_SYSTEM, user, QualificationBatch).results
    judged = [q for q in result if q.id in ids]
    for q in judged:
        if q.intent == Intent.NOT_RELEVANT:
            q.fit_score = min(q.fit_score, 19)
            q.suggested_opener = ""
        q.reasons = q.reasons[:3]
    return judged
