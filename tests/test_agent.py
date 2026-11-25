from lead_agent.agent import plan_queries, qualify
from lead_agent.llm import LLMError
from lead_agent.models import ICP, Intent, Qualification

from .conftest import FakeLLM, signal

ICP_ = ICP(product="AI support agent", customers="SaaS teams")


def test_plan_queries_cleans_and_dedupes():
    llm = FakeLLM(
        queries=['"helpdesk" tool', "Helpdesk tool", "zendesk   alternative", "", "a", "b", "c", "d"]
    )
    assert plan_queries(ICP_, llm) == ["helpdesk tool", "zendesk alternative", "a", "b", "c", "d"]


def test_qualify_batches_and_drops_unknown_ids():
    def judge(post):
        return Qualification(
            id=post["id"] + "-typo" if post["id"] == "fake:2" else post["id"],
            intent=Intent.BUYING,
            fit_score=80,
            reasons=["a", "b", "c", "d"],
            summary="s",
            suggested_opener="o",
        )

    llm = FakeLLM(judge=judge)
    results = list(qualify([signal(i) for i in range(10)], ICP_, llm, batch_size=4))
    assert len(llm.calls) == 3  # 4 + 4 + 2
    assert "fake:2" not in {q.id for q in results}
    assert all(len(q.reasons) == 3 for q in results)


def test_not_relevant_is_clamped():
    llm = FakeLLM(
        judge=lambda p: Qualification(
            id=p["id"],
            intent=Intent.NOT_RELEVANT,
            fit_score=95,
            reasons=[],
            summary="ad",
            suggested_opener="Buy now",
        )
    )
    [q] = list(qualify([signal(1)], ICP_, llm))
    assert q.fit_score < 20 and q.suggested_opener == ""


def test_failed_batch_falls_back_to_single_posts():
    class Flaky(FakeLLM):
        def structured(self, system, user, schema):
            if user.count('"id"') > 1:
                raise LLMError("batch too big")
            return super().structured(system, user, schema)

    llm = Flaky()
    results = list(qualify([signal(1), signal(2), signal(3)], ICP_, llm, batch_size=3))
    assert [q.id for q in results] == ["fake:1", "fake:2", "fake:3"]
