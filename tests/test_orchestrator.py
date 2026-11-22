"""Verify that M4 routes and commits only the unverified T01 submission."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from core import llm
from core.message_bus import MessageBus
from core.orchestrator import run_t01
from core.schema import Agent, MsgType
from core.workspace import Workspace


def test_t01_runs_through_bus_and_commits_unverified_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requirements = "Add a health endpoint."
    backlog = (
        '```json\n[{"id":"T01","title":"Health","needs_ui":false,"acceptance":["HTTP 200"]},'
        '{"id":"T02","title":"Database","needs_ui":false,"acceptance":["Creates a table"]}]\n```'
    )
    brief = "## Objective\nBuild health.\n## Acceptance criteria\n- HTTP 200\n## Notes for the team"
    output = (
        '### FILE: app/main.py\n```python\nAPP_TITLE = "To-do"\n```\n'
        '### FILE: requirements.txt\n```text\nfastapi\n```\n'
        '### FILE: README.md\n```markdown\n# To-do\n```'
    )
    bus = MessageBus("run-test", tmp_path / "logs")
    workspace = Workspace(tmp_path / "workspace")
    commit = Mock()
    monkeypatch.setattr(workspace, "git_commit", commit)

    def chat(role: str, system: str, prompt: str) -> llm.LLMResult:
        if prompt.startswith("MODE: PLAN"):
            assert role == "pm"
            assert bus.inbox(Agent.PM)[-1].content == requirements
            reply = backlog
        elif prompt.startswith("MODE: ASSIGN"):
            assert role == "pm"
            assert bus.inbox(Agent.ORCHESTRATOR)[-1].content == backlog
            assert "T02" not in prompt
            reply = brief
        else:
            assert role == "coder"
            assert bus.inbox(Agent.CODER, "T01")[-1].content == brief
            assert brief in prompt
            reply = output
        return llm.LLMResult(reply, "test-model", 20, 5, 10)

    monkeypatch.setattr(llm, "chat", chat)
    run_t01(requirements, bus, workspace)

    messages = bus.history()
    assert [message.type for message in messages] == [
        MsgType.REQUIREMENT, MsgType.TASK_ASSIGN, MsgType.TASK_ASSIGN,
        MsgType.CODE_SUBMIT, MsgType.CODE_SUBMIT,
    ]
    assert {message.task_id for message in messages if message.task_id} == {"T01"}
    assert messages[3].meta["tokens_in"] == 20
    assert "workspace/app/main.py" in messages[3].artifacts
    assert messages[4].status == "UNVERIFIED"
    assert (workspace.root / "app/main.py").read_text(encoding="utf-8") == 'APP_TITLE = "To-do"\n'
    assert not (workspace.root / "tests").exists()
    commit.assert_called_once_with("T01: coder output (chưa qua Tester)")
