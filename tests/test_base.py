"""Check shared agent prompt construction, retry behavior and safe errors."""

from unittest.mock import Mock

import pytest

from agents.base import PROMPTS_DIR, Agent, AgentFormatError
from core import llm

CODER_SECTIONS = {
    "FEEDBACK": "Fix the return value.",
    "PROJECT FILES": "hello.py",
    "DESIGN SPEC": "A design, when relevant.",
    "PRODUCT REQUIREMENTS": "Use Python.",
    "ACCEPTANCE CRITERIA": "Return Hello.",
    "TASK BRIEF": "Write hello.py.",
}
TESTER_SECTIONS = {
    "TASK": "T01",
    "ACCEPTANCE CRITERIA": "Return HTTP 200.",
    "PRODUCT REQUIREMENTS": "Add GET /health.",
    "EXISTING TESTS": "",
}


def test_build_input_orders_sections_and_keeps_optional_feedback() -> None:
    user = Agent("coder").build_input(CODER_SECTIONS)
    assert user == (
        "## TASK BRIEF\nWrite hello.py.\n\n"
        "## ACCEPTANCE CRITERIA\nReturn Hello.\n\n"
        "## PRODUCT REQUIREMENTS\nUse Python.\n\n"
        "## DESIGN SPEC\nA design, when relevant.\n\n"
        "## PROJECT FILES\nhello.py\n\n"
        "## FEEDBACK\nFix the return value."
    )


def test_validates_input_before_calling_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Mock()
    monkeypatch.setattr(llm, "chat", fake)
    with pytest.raises(ValueError, match="requires mode"):
        Agent("pm").run({})
    with pytest.raises(ValueError, match="Missing input sections: PRODUCT REQUIREMENTS"):
        Agent("pm").run({}, mode="PLAN")
    with pytest.raises(ValueError, match="Unexpected input section"):
        Agent("tester").run(
            {**TESTER_SECTIONS, "PROJECT FILES": "Coder source"},
            mode="WRITE_TESTS",
            task_id="T01",
        )
    with pytest.raises(ValueError, match="requires a task_id"):
        Agent("tester").run(TESTER_SECTIONS, mode="WRITE_TESTS")
    fake.assert_not_called()


def test_retry_uses_exact_instruction_and_returns_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "VERDICT: APPROVE\nThe submitted file meets the requirements."
    fake = Mock(side_effect=[
        llm.LLMResult("Looks good.", "mock/first", 5, 2, 10),
        llm.LLMResult(text, "mock/fallback", 30, None, 20),
    ])
    monkeypatch.setattr(llm, "chat", fake)
    agent = Agent("reviewer")
    sections = {
        "TASK BRIEF": "Review hello.py.",
        "ACCEPTANCE CRITERIA": "Return Hello.",
        "PRODUCT REQUIREMENTS": "Use Python.",
        "CHANGED FILES": "hello.py\ndef hello(): return 'Hello'",
        "RUFF OUTPUT": "Exit code: 0",
    }
    original = agent.build_input(sections)
    system = (PROMPTS_DIR / "reviewer.md").read_text(encoding="utf-8")
    result = agent.run(sections)
    assert [call.args for call in fake.call_args_list] == [
        ("reviewer", system, original),
        (
            "reviewer", system, original + "\n\nĐầu ra trước không hợp lệ vì: "
            "First line must be VERDICT: APPROVE or VERDICT: REQUEST_CHANGES. "
            "Hãy trả lại đúng định dạng.",
        ),
    ]
    assert (result.text, result.parsed) == (text, "VERDICT: APPROVE")
    assert (result.model, result.tokens_in, result.tokens_out, result.duration_ms) == (
        "mock/fallback", 35, 2, 30,
    )


def test_redacts_key_from_parser_errors_and_retry_prompts(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    key = "test-private-router-key"
    monkeypatch.setenv("ROUTER_API_KEY", key)
    fake = Mock(return_value=llm.LLMResult(
        f"### FILE: ../{key}\n```python\npass\n```", key, 1, 2, 3
    ))
    monkeypatch.setattr(llm, "chat", fake)
    with pytest.raises(AgentFormatError, match=r"\.\./\[redacted\]") as caught:
        Agent("coder").run(CODER_SECTIONS)
    assert caught.value.usage.model == "[redacted]"
    assert key not in str(caught.value)
    assert all(key not in call.args[2] for call in fake.call_args_list)
    output = capsys.readouterr()
    assert key not in caplog.text + output.out + output.err


def test_redacts_router_error_without_format_retry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    key = "test-private-router-key"
    monkeypatch.setenv("ROUTER_API_KEY", key)
    fake = Mock(side_effect=llm.LLMError(f"Rejected {key}"))
    monkeypatch.setattr(llm, "chat", fake)
    with pytest.raises(llm.LLMError, match=r"Rejected \[redacted\]") as caught:
        Agent("pm").run({"PRODUCT REQUIREMENTS": "Test."}, mode="PLAN")
    fake.assert_called_once()
    output = capsys.readouterr()
    assert key not in str(caught.value) + caplog.text + output.out + output.err
