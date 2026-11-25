from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .agent import plan_queries, qualify
from .llm import LLM
from .models import ICP, Lead
from .sources import Source
from .store import Store


@dataclass
class RunReport:
    queries: list[str] = field(default_factory=list)
    found: int = 0
    new: int = 0
    judged: int = 0
    leads: list[Lead] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run(
    icp: ICP,
    sources: list[Source],
    llm: LLM,
    store: Store,
    per_query: int = 25,
    queries: list[str] | None = None,
    progress: Callable[[str], None] = lambda _: None,
) -> RunReport:
    """plan -> search every source -> dedupe -> judge only new signals -> leads above min_score."""
    report = RunReport()
    report.queries = queries or plan_queries(icp, llm)
    progress(f"Queries: {', '.join(report.queries)}")

    for source in sources:
        for query in report.queries:
            try:
                found = source.search(query, days=icp.days, limit=per_query)
            except Exception as error:  # a source failing must not stop the run
                report.errors.append(f"{source.name} '{query}': {error}")
                continue
            report.found += len(found)
            report.new += len(store.add_signals(found))
            progress(f"{source.name} · {query}: {len(found)} results")

    pending = store.unqualified()
    progress(f"Judging {len(pending)} new signals with {llm.model}")
    judged = list(qualify(pending, icp, llm))
    store.save_qualifications(judged, llm.model)
    report.judged = len(judged)
    report.leads = store.leads(min_score=icp.min_score)
    return report
