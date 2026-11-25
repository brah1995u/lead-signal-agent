import csv

from lead_agent.evaluate import evaluate
from lead_agent.export import COLUMNS, to_csv
from lead_agent.models import ICP, Intent, Qualification

from .conftest import FakeLLM, signal


def test_csv_export(store, tmp_path):
    store.add_signals([signal(1)])
    store.save_qualifications(
        [
            Qualification(
                id="fake:1",
                intent=Intent.BUYING,
                fit_score=88,
                reasons=["a", "b"],
                summary="s",
                suggested_opener="o",
            )
        ],
        "m",
    )
    path = to_csv(store.leads(), tmp_path / "out" / "leads.csv")
    header, row = list(csv.reader(path.open()))
    assert header == COLUMNS
    assert row[0] == "88" and row[-1] == "a | b"


def test_evaluate_metrics():
    dataset = [
        {"id": "a", "text": "need a helpdesk", "is_lead": True, "intent": "buying"},
        {"id": "b", "text": "my own bot launch", "is_lead": False, "intent": "not_relevant"},
        {"id": "c", "text": "tickets everywhere", "is_lead": True, "intent": "describing_a_problem"},
    ]

    def judge(post):
        lead = post["id"] in {"a", "b"}
        return Qualification(
            id=post["id"],
            intent=Intent.BUYING if lead else Intent.NOT_RELEVANT,
            fit_score=90 if lead else 5,
            reasons=[],
            summary="",
            suggested_opener="",
        )

    result = evaluate(dataset, ICP(product="p", customers="c"), FakeLLM(judge=judge))
    assert (result.tp, result.fp, result.fn, result.tn) == (1, 1, 1, 0)
    assert result.precision == 0.5 and result.recall == 0.5
    assert result.intent_correct == 1
