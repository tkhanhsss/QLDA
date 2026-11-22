"""Exercise the 9Router client without sending network requests."""

import json
from functools import partial

import httpx
import pytest
from openai import OpenAI

from core import llm


@pytest.fixture(autouse=True)
def router_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROUTER_BASE_URL", "http://router.test/v1")
    monkeypatch.setenv("ROUTER_API_KEY", "test-router-key")
    monkeypatch.setenv("MODEL_DEFAULT", "provider/default")
    monkeypatch.setenv("MODEL_PM", "")


def use_router(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    monkeypatch.setattr(
        llm, "OpenAI", partial(OpenAI, http_client=httpx.Client(transport=handler))
    )


def completion(*, with_usage: bool) -> httpx.Response:
    body = {
        "model": "provider/actual",
        "choices": [{"message": {"role": "assistant", "content": "4"}}],
    }
    if with_usage:
        body["usage"] = {
            "prompt_tokens": 12,
            "completion_tokens": 1,
            "total_tokens": 13,
        }
    return httpx.Response(200, json=body)


def test_check_router_uses_models_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/models"
        assert request.headers["Authorization"] == "Bearer test-router-key"
        assert request.extensions["timeout"]["read"] == 120
        return httpx.Response(200, json={"object": "list", "data": []})

    use_router(monkeypatch, httpx.MockTransport(handler))
    llm.check_router()


@pytest.mark.parametrize("with_usage", [True, False])
def test_chat_selects_model_and_reads_usage(
    monkeypatch: pytest.MonkeyPatch, with_usage: bool
) -> None:
    if with_usage:
        monkeypatch.setenv("MODEL_PM", "provider/pm")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert json.loads(request.content) == {
            "model": "provider/pm" if with_usage else "provider/default",
            "messages": [
                {"role": "system", "content": "Answer briefly."},
                {"role": "user", "content": "What is 2 + 2?"},
            ],
        }
        return completion(with_usage=with_usage)

    use_router(monkeypatch, httpx.MockTransport(handler))
    result = llm.chat("pm", "Answer briefly.", "What is 2 + 2?")
    assert (result.text, result.model) == ("4", "provider/actual")
    assert (result.tokens_in, result.tokens_out) == (
        (12, 1) if with_usage else (None, None)
    )
    assert result.duration_ms >= 0


def test_chat_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = iter([429, 503, None, 200])
    pauses: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(outcomes)
        if status is None:
            raise httpx.ReadTimeout("Timed out", request=request)
        if status == 200:
            return completion(with_usage=True)
        return httpx.Response(status)

    use_router(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setattr(llm, "sleep", pauses.append)
    assert llm.chat("pm", "System", "User").text == "4"
    assert pauses == [1, 2, 4]


@pytest.mark.parametrize(("status", "expected_pauses"), [(429, [1, 2, 4]), (401, [])])
def test_chat_limits_retries_and_redacts_key(
    monkeypatch: pytest.MonkeyPatch, status: int, expected_pauses: list[int]
) -> None:
    pauses: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status, json={"error": {"message": "Rejected test-router-key"}}
        )

    use_router(monkeypatch, httpx.MockTransport(handler))
    monkeypatch.setattr(llm, "sleep", pauses.append)
    with pytest.raises(llm.LLMError, match=r"Rejected \[redacted\]") as error:
        llm.chat("pm", "System", "User")
    assert "test-router-key" not in str(error.value)
    assert pauses == expected_pauses
