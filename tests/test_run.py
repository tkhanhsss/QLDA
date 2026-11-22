"""Verify the M0 command's terminal output."""

import pytest

from core import run
from core.llm import LLMError, LLMResult


def test_main_prints_response_and_tokens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []

    def chat(agent: str, system: str, user: str) -> LLMResult:
        calls.append("chat")
        return LLMResult("4", "provider/model", 12, 1, 200)

    monkeypatch.setattr(run, "check_router", lambda: calls.append("check_router"))
    monkeypatch.setattr(run, "chat", chat)
    assert run.main() == 0
    assert calls == ["check_router", "chat"]
    assert capsys.readouterr().out.splitlines() == [
        "4",
        "Model: provider/model",
        "Token vào: 12 | Token ra: 1",
    ]


def test_main_exits_when_router_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def check_router() -> None:
        raise LLMError("Connection error.")

    def chat(agent: str, system: str, user: str) -> LLMResult:
        pytest.fail("Chat ran after a failed router check.")

    monkeypatch.setattr(run, "check_router", check_router)
    monkeypatch.setattr(run, "chat", chat)
    assert run.main() == 1
    assert "Hãy chạy 9Router và kiểm tra .env." in capsys.readouterr().err
