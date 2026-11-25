import httpx
import respx

from lead_agent.sources.hackernews import API, HackerNewsSource, clean_html

HITS = {
    "hits": [
        {
            "objectID": "101",
            "_tags": ["comment", "author_alice"],
            "author": "alice",
            "comment_text": "We&#x27;re drowning in tickets.<p>Any <i>helpdesk</i> tips?",
            "story_title": "Ask HN: Support tools",
            "created_at_i": 1_764_000_000,
        },
        {
            "objectID": "102",
            "_tags": ["story", "author_bob"],
            "author": "bob",
            "title": "Ask HN: Zendesk alternatives?",
            "story_text": None,
            "points": 42,
            "created_at_i": 1_764_000_100,
        },
        {"objectID": "103", "_tags": ["comment"], "comment_text": "", "story_title": None},
    ]
}


@respx.mock
def test_parses_comments_and_stories():
    route = respx.get(API).mock(return_value=httpx.Response(200, json=HITS))
    signals = HackerNewsSource().search("helpdesk", days=7, limit=10)

    assert route.called
    params = route.calls[0].request.url.params
    assert params["query"] == "helpdesk"
    assert params["numericFilters"].startswith("created_at_i>")

    assert [s.id for s in signals] == ["hn:101", "hn:102"]  # empty hit skipped
    comment, story = signals
    assert comment.title == "Re: Ask HN: Support tools"
    assert comment.text == "We're drowning in tickets.\n\nAny helpdesk tips?"
    assert comment.url == "https://news.ycombinator.com/item?id=101"
    assert story.points == 42 and story.author == "bob"


def test_clean_html():
    assert clean_html("a &amp; b<p><a href='x'>link</a>") == "a & b\n\nlink"
