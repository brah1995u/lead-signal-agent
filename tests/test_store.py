from lead_agent.models import Intent, Qualification

from .conftest import signal


def test_dedupes_across_runs(store):
    assert len(store.add_signals([signal(1), signal(2)])) == 2
    assert [s.id for s in store.add_signals([signal(2), signal(3)])] == ["fake:3"]
    assert store.counts() == {"signals": 3, "qualified": 0}


def test_leads_sorted_filtered_and_without_not_relevant(store):
    store.add_signals([signal(1), signal(2), signal(3)])
    store.save_qualifications(
        [
            Qualification(
                id="fake:1", intent=Intent.BUYING, fit_score=70, reasons=[], summary="a", suggested_opener=""
            ),
            Qualification(
                id="fake:2",
                intent=Intent.NOT_RELEVANT,
                fit_score=90,
                reasons=[],
                summary="b",
                suggested_opener="",
            ),
            Qualification(
                id="fake:3",
                intent=Intent.PROBLEM,
                fit_score=92,
                reasons=["x"],
                summary="c",
                suggested_opener="Hi",
            ),
        ],
        model="m",
    )
    leads = store.leads(min_score=60)
    assert [lead.signal.id for lead in leads] == ["fake:3", "fake:1"]
    assert leads[0].qualification.reasons == ["x"]
    assert store.unqualified() == []
