"""Validate the Designer prompt and its format retries with a fake router."""

from unittest.mock import Mock

import pytest

from agents.designer import Designer
from core import llm

DESIGN_SPEC = """## Overview
Quản lý công việc uses one centered column.
## Layout
Place the form above the filters and list.
## Components
Use `task-form`, `task-input`, `task-list`, `filter-all`, `filter-todo`,
`filter-done`, and `search-input`. Label the submit button Thêm.
## Visual style
Use system fonts.
## States and behavior
Show Chưa có công việc nào when the list is empty.
## Responsive behavior
Wrap controls below 600px.
## Accessibility
Show focus outlines and label every input."""


@pytest.mark.parametrize(("invalid", "reason"), [
    (DESIGN_SPEC.replace("## Layout\n", ""), "Expected headings"),
    (DESIGN_SPEC.replace("task-input", "task-input-renamed"), "task-input"),
    (DESIGN_SPEC.replace("Quản lý công việc", "Quản lý tác vụ"), "Quản lý công việc"),
    (DESIGN_SPEC + "\n" + "word " * 450, "at most 450 words"),
    (DESIGN_SPEC + "\n### Extra", "exactly the seven required headings"),
    (DESIGN_SPEC + '\n`<form id="task-form">`', "without HTML, CSS or JavaScript"),
    (DESIGN_SPEC + "\n`.row { color: #fff; }`", "without HTML, CSS or JavaScript"),
    (DESIGN_SPEC + '\n`document.querySelector("#task-list")`', "without HTML, CSS or JavaScript"),
])
def test_retries_invalid_specification(
    monkeypatch: pytest.MonkeyPatch, invalid: str, reason: str,
) -> None:
    chat = Mock(side_effect=[
        llm.LLMResult(invalid, "fake/model", 10, 8, 20),
        llm.LLMResult(DESIGN_SPEC, "fake/model", 10, 8, 20),
    ])
    monkeypatch.setattr(llm, "chat", chat)
    result = Designer().run({
        "PRODUCT REQUIREMENTS": "FR-7",
        "ACCEPTANCE CRITERIA": "HTTP 200",
        "TASK BRIEF": "Build the UI.",
        "FEEDBACK": "Describe mobile behavior.",
    })

    assert result.text == result.parsed == DESIGN_SPEC
    assert chat.call_count == 2
    role, _, first_prompt = chat.call_args_list[0].args
    assert role == "designer"
    assert first_prompt == (
        "## TASK BRIEF\nBuild the UI.\n\n## ACCEPTANCE CRITERIA\nHTTP 200\n\n"
        "## PRODUCT REQUIREMENTS\nFR-7\n\n## FEEDBACK\nDescribe mobile behavior."
    )
    assert "Đầu ra trước không hợp lệ vì:" in chat.call_args.args[2]
    assert reason in chat.call_args.args[2]
