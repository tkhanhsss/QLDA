"""Exercise the format contract of each agent with fake 9Router replies."""

import json
from unittest.mock import Mock

import pytest

from agents.base import Agent, AgentFormatError, ParsedOutput
from core import llm

TASK = {
    "TASK BRIEF": "Build GET /health.",
    "ACCEPTANCE CRITERIA": "GET /health returns HTTP 200.",
    "PRODUCT REQUIREMENTS": "Provide a health endpoint.",
}
REVIEW = {**TASK, "CHANGED FILES": "app/main.py", "RUFF OUTPUT": "Exit code: 0"}
PLAN = {"PRODUCT REQUIREMENTS": TASK["PRODUCT REQUIREMENTS"]}
ASSIGN = {"BACKLOG ITEM": "T01", "PROJECT STATE": "(empty)", **PLAN}
CLOSE = {"TASK": "T01", "OUTCOME": "PASSED after 1 iteration"}
WRITE_TESTS = {
    "TASK": "T01",
    "ACCEPTANCE CRITERIA": TASK["ACCEPTANCE CRITERIA"],
    "EXISTING TESTS": "client fixture exists.",
    **PLAN,
}
REPORT = {"TASK": "T01", "TASK TESTS": "Exit code: 1", "FULL SUITE": "Exit code: 1"}
DESIGN = (
    "## Overview\nA clean page.\n## Layout\nOne column.\n## Components\nA form.\n"
    "## Visual style\nSystem fonts.\n## States and behavior\nDisplay errors.\n"
    "## Responsive behavior\nUse the full width.\n## Accessibility\nLabel controls."
)
BRIEF = (
    "## Objective\nAdd GET /health.\n## Acceptance criteria\n- HTTP 200.\n"
    "## Notes for the team\n- Use FastAPI."
)
BACKLOG = [
    {"id": "T01", "title": "Health", "needs_ui": False, "acceptance": ["GET /health returns 200."]}
]
CODE = "### FILE: app/main.py\n```python\nSTATUS = 'ok'\n```"
TEST = "### FILE: tests/test_T01.py\n```python\ndef test_health():\n    pass\n```"


@pytest.mark.parametrize(("role", "mode", "sections", "text", "parsed"), [
    ("pm", "PLAN", PLAN, f"```json\n{json.dumps(BACKLOG)}\n```", BACKLOG),
    ("pm", "ASSIGN", ASSIGN, BRIEF, BRIEF),
    ("pm", "CLOSE", CLOSE, "DECISION: DONE\nSUMMARY: Tests passed.", "DECISION: DONE"),
    ("designer", None, TASK, DESIGN, DESIGN),
    ("coder", None, {**TASK, "PROJECT FILES": "(empty)"}, "NOTE: First file.\n" + CODE,
     {"app/main.py": "STATUS = 'ok'\n"}),
    ("reviewer", None, REVIEW, "VERDICT: APPROVE\nChecked the changes.", "VERDICT: APPROVE"),
    ("reviewer", None, REVIEW, "VERDICT: REQUEST_CHANGES\n- [app/main.py:2] Return 200.",
     "VERDICT: REQUEST_CHANGES"),
    ("tester", "WRITE_TESTS", WRITE_TESTS, TEST,
     {"tests/test_T01.py": "def test_health():\n    pass\n"}),
    ("tester", "REPORT", {**REPORT, "TASK TESTS": "Exit code: 0", "FULL SUITE": "Exit code: 0"},
     "RESULT: PASS\nSUMMARY: Both suites passed.", "RESULT: PASS"),
    ("tester", "REPORT", REPORT, "RESULT: FAIL\nCAUSE: CODE\nSUMMARY: Status mismatch.",
     "RESULT: FAIL"),
    ("tester", "REPORT", REPORT, "RESULT: FAIL\nCAUSE: TEST\nSUMMARY: Invalid fixture.",
     "RESULT: FAIL"),
])
def test_accepts_supported_formats(
    monkeypatch: pytest.MonkeyPatch, role: str, mode: str | None, sections: dict[str, str],
    text: str, parsed: ParsedOutput,
) -> None:
    chat = Mock(return_value=llm.LLMResult(text, "fake/model", 10, 7, 25))
    monkeypatch.setattr(llm, "chat", chat)
    result = Agent(role).run(sections, mode=mode, task_id="T01" if mode == "WRITE_TESTS" else None)
    assert result.parsed == parsed
    assert result.text == text
    chat.assert_called_once()
    agent_name, system, user = chat.call_args.args
    assert agent_name == role
    assert role in system.splitlines()[0].lower() or role == "pm" and "(PM)" in system
    assert user.splitlines()[0] == (f"MODE: {mode}" if mode else "## TASK BRIEF")
    assert all(f"## {heading}\n{value}" in user for heading, value in sections.items())


@pytest.mark.parametrize(("role", "mode", "sections", "text", "reason"), [
    ("pm", "PLAN", PLAN, "{}", "exactly one fenced json block"),
    ("pm", "PLAN", PLAN, '```json\n{"id":"T01"}\n```', "JSON array"),
    ("pm", "PLAN", PLAN, '```json\n["T01"]\n```', "JSON object at backlog item 1"),
    ("pm", "PLAN", PLAN, '```json\n[{"id":"T01","title":"Health"}]\n```', "boolean needs_ui"),
    ("pm", "ASSIGN", ASSIGN, "## Objective\nAdd a route.", "Expected headings"),
    ("pm", "CLOSE", CLOSE, "DECISION: PASS", "DECISION: DONE or DECISION: BLOCKED"),
    ("designer", None, TASK, DESIGN.replace("## Layout", "## Accessibility"), "Expected headings"),
    ("coder", None, {**TASK, "PROJECT FILES": ""}, "", "at least one FILE block"),
    ("coder", None, {**TASK, "PROJECT FILES": ""}, CODE.replace("app/", "../"), "workspace-relative"),
    ("coder", None, {**TASK, "PROJECT FILES": ""}, CODE.replace("app/", "/app/"), "workspace-relative"),
    ("coder", None, {**TASK, "PROJECT FILES": ""}, CODE.replace("app/", "C:/app/"), "workspace-relative"),
    ("coder", None, {**TASK, "PROJECT FILES": ""}, CODE.replace("app/", "tests/"), "cannot write to tests"),
    ("reviewer", None, REVIEW, "VERDICT: REQUEST_CHANGES\n- [app.py:main] Fix it.", "requires at least"),
    ("reviewer", None, REVIEW, "\nVERDICT: APPROVE", "First line must be"),
    ("tester", "REPORT", REPORT, "RESULT: FAIL\nCAUSE: UNKNOWN", "requires exactly one CAUSE"),
    ("tester", "REPORT", REPORT, "RESULT: FAIL\nCAUSE: CODE\nCAUSE: TEST", "requires exactly one CAUSE"),
    ("tester", "WRITE_TESTS", WRITE_TESTS, TEST.replace("T01", "T02"), "only one FILE block"),
    ("tester", "WRITE_TESTS", WRITE_TESTS,
     TEST + "\n" + TEST.replace("test_T01.py", "conftest.py"), "only one FILE block"),
    ("tester", "WRITE_TESTS", WRITE_TESTS, "NOTE: Test below\n" + TEST, "Expected a FILE header"),
])
def test_retries_invalid_formats_then_reports_reason(
    monkeypatch: pytest.MonkeyPatch, role: str, mode: str | None, sections: dict[str, str],
    text: str, reason: str,
) -> None:
    chat = Mock(return_value=llm.LLMResult(text, "fake/model", 10, 7, 25))
    monkeypatch.setattr(llm, "chat", chat)
    agent = Agent(role)
    with pytest.raises(AgentFormatError, match=reason) as error:
        agent.run(sections, mode=mode, task_id="T01" if mode == "WRITE_TESTS" else None)
    assert chat.call_count == 3
    assert error.value.usage.tokens_in == 10
    first, second, third = [call.args[2] for call in chat.call_args_list]
    assert first == agent.build_input(sections, mode=mode)
    assert second == third
    assert second.startswith(first + "\n\nĐầu ra trước không hợp lệ vì: ")
    assert second.endswith("Hãy trả lại đúng định dạng.")
