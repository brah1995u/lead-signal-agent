from lead_agent.models import ICP
from lead_agent.pipeline import run

from .conftest import FakeLLM, FakeSource, signal


def test_end_to_end_and_no_rejudging(store):
    source = FakeSource([signal(1), signal(2)])
    llm = FakeLLM()
    icp = ICP(product="AI support agent", customers="SaaS", min_score=60)

    first = run(icp, [source], llm, store)
    assert first.queries == ["helpdesk recommendation", "zendesk alternative"]
    assert source.queries == first.queries
    assert (first.found, first.new, first.judged, len(first.leads)) == (4, 2, 2, 2)

    calls_before = len(llm.calls)
    second = run(icp, [source], llm, store, queries=["helpdesk"])
    assert (second.new, second.judged) == (0, 0)
    assert len(llm.calls) == calls_before  # nothing new to judge, no planning either


def test_a_failing_source_does_not_stop_the_run(store):
    class Broken:
        name = "broken"

        def search(self, query, days=30, limit=25):
            raise RuntimeError("timeout")

    report = run(
        ICP(product="p", customers="c"), [Broken(), FakeSource([signal(1)])], FakeLLM(), store, queries=["q"]
    )
    assert report.errors == ["broken 'q': timeout"]
    assert report.judged == 1


def test_model_errors_are_reported_once(store):
    from lead_agent.llm import LLMError

    class Down(FakeLLM):
        def structured(self, system, user, schema):
            raise LLMError("Model server not reachable at http://localhost:11434/v1")

    report = run(
        ICP(product="p", customers="c"), [FakeSource([signal(1), signal(2)])], Down(), store, queries=["q"]
    )
    assert report.judged == 0
    assert report.errors == ["model: Model server not reachable at http://localhost:11434/v1"]
