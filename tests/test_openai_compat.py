import httpx
import pytest
import respx

from lead_agent.llm import LLMError, OpenAICompatibleLLM
from lead_agent.models import QueryPlan

URL = "http://local/v1/chat/completions"


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@respx.mock
def test_valid_json_with_code_fences():
    respx.post(URL).mock(return_value=reply('```json\n{"queries": ["a b", "c d"]}\n```'))
    plan = OpenAICompatibleLLM("http://local/v1", "m").structured("sys", "user", QueryPlan)
    assert plan.queries == ["a b", "c d"]


@respx.mock
def test_retries_once_with_the_validation_error():
    route = respx.post(URL).mock(side_effect=[reply('{"query": "oops"}'), reply('{"queries": ["fixed"]}')])
    plan = OpenAICompatibleLLM("http://local/v1", "m").structured("sys", "user", QueryPlan)
    assert plan.queries == ["fixed"]
    second = route.calls[1].request.content.decode()
    assert "invalid" in second and "json_schema" in second


@respx.mock
def test_server_errors_become_llm_errors():
    respx.post(URL).mock(return_value=httpx.Response(500, text="model not found"))
    with pytest.raises(LLMError, match="500"):
        OpenAICompatibleLLM("http://local/v1", "m").structured("sys", "user", QueryPlan)
