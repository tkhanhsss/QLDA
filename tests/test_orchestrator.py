"""Verify graph selection, blocked tasks, and commit ordering."""

from pathlib import Path

import pytest
from test_designer import DESIGN_SPEC

from core import llm
from core.message_bus import MessageBus
from core.orchestrator import run_project
from core.schema import Agent, MsgType
from core.workspace import Workspace

BACKLOG = (
    ' ```json\n[{"id":"T01","title":"Health","needs_ui":false,"acceptance":["HTTP 200"]},'
    '{"id":"T02","title":"Database","needs_ui":false,"acceptance":["Creates a table"]}]\n```'
).lstrip()
BRIEF = "## Objective\nBuild it.\n## Acceptance criteria\n- Works.\n## Notes for the team"
APPROVE = "VERDICT: APPROVE\nChecked the files."
REJECT = "VERDICT: REQUEST_CHANGES\n- [app/main.py:1] Fix the status."
DONE = "DECISION: DONE\nSUMMARY: Passed."
BLOCKED = "DECISION: BLOCKED\nSUMMARY: Failed."


def file_block(path: str, source: str) -> str:
    return f"### FILE: {path}\n```python\n{source}\n```"


def fake_reply(text: str) -> llm.LLMResult:
    return llm.LLMResult(text, "test-model", 20, 5, 10)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[MessageBus, Workspace]:
    for key in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{key}_NAME", "M5 test")
        monkeypatch.setenv(f"{key}_EMAIL", "test@example.invalid")
    bus = MessageBus("run-test", tmp_path / "logs")
    workspace = Workspace(tmp_path / "workspace")
    workspace.write_files({".gitignore": "__pycache__/\n", "app/main.py": "VALUE = 0\n"})
    workspace.git_commit("T01: coder output (chưa qua Tester)")
    return bus, workspace


def commits(workspace: Workspace) -> list[str]:
    result = workspace.run(["git", "log", "--format=%s"])
    result.check_returncode()
    return result.stdout.splitlines()


@pytest.mark.parametrize("selection", [{"until": "T02"}, {"only": "T02"}])
def test_blocked_task_never_commits_and_graph_runs_selected_next_task(
    project: tuple[MessageBus, Workspace], monkeypatch: pytest.MonkeyPatch,
    selection: dict[str, str],
) -> None:
    bus, workspace = project
    baseline = commits(workspace)
    task_id = ""

    def chat(role: str, system: str, prompt: str) -> llm.LLMResult:
        nonlocal task_id
        if prompt.startswith("MODE: PLAN"):
            assert bus.inbox(Agent.PM)[-1].content == "Build the app."
            return fake_reply(BACKLOG)
        if prompt.startswith("MODE: ASSIGN"):
            task_id = "T01" if '"id": "T01"' in prompt else "T02"
            assert bus.inbox(Agent.ORCHESTRATOR)[0].content == BACKLOG
            return fake_reply(BRIEF)
        if role == "coder":
            assert "## DESIGN SPEC" not in prompt
            assert bus.inbox(Agent.CODER, task_id)[0].content == BRIEF
            return fake_reply(file_block("app/main.py", "VALUE = 1") if task_id == "T02"
                              else file_block("blocked.py", "BAD = True"))
        if role == "reviewer":
            assert "Exit code: 0" in prompt and "All checks passed!" in prompt
            return fake_reply(REJECT if task_id == "T01" else APPROVE)
        if prompt.startswith("MODE: WRITE_TESTS"):
            assert task_id == "T02"
            return fake_reply(
                file_block("tests/test_T02.py", "from app.main import VALUE\n\ndef test_value():\n    assert VALUE == 1")
                + "\n" + file_block("tests/conftest.py", "# Shared fixtures")
            )
        if prompt.startswith("MODE: REPORT"):
            assert prompt.count("Exit code: 0") == 2
            assert commits(workspace) == baseline
            return fake_reply("RESULT: PASS\nSUMMARY: One test passed in each run.")
        assert prompt.startswith("MODE: CLOSE")
        if task_id == "T01":
            assert "FAILED after 3 revision rounds" in prompt
            assert commits(workspace) == baseline
            return fake_reply(BLOCKED)
        assert "PASSED" in prompt
        assert commits(workspace) == ["T02: passed after 0 iterations", *baseline]
        return fake_reply(DONE)

    monkeypatch.setattr(llm, "chat", chat)
    statuses = run_project("Build the app.", bus, workspace, **selection)
    expected = {"T01": "BLOCKED", "T02": "DONE"} if "until" in selection else {"T02": "DONE"}
    assert statuses == expected
    assert not (workspace.root / "blocked.py").exists()
    attempts = bus.history("T01", sender=Agent.CODER, type=MsgType.CODE_SUBMIT)
    assert [message.iteration for message in attempts] == ([0, 1, 2, 3] if "until" in selection else [])
    assert not bus.history("T01", type=MsgType.TASK_DONE)
    report = bus.history("T02", type=MsgType.TEST_REPORT)[0]
    done = bus.history("T02", type=MsgType.TASK_DONE)[0]
    assert report.id < done.id
    assert report.meta["tokens_in"] == 20
    assert not bus.history(type=MsgType.DESIGN_SPEC)


def test_ui_spec_is_published_before_code_and_reused_on_revisions(
    project: tuple[MessageBus, Workspace], monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus, workspace = project
    roles = []
    coder_prompts = []

    def chat(role: str, system: str, prompt: str) -> llm.LLMResult:
        roles.append(role)
        if prompt.startswith("MODE: PLAN"):
            return fake_reply(BACKLOG.replace('"needs_ui":false', '"needs_ui":true', 1))
        if prompt.startswith("MODE: ASSIGN"):
            return fake_reply(BRIEF)
        if role == "designer":
            assert bus.inbox(Agent.DESIGNER, "T01")[0].content == BRIEF
            assert "## PROJECT FILES" not in prompt
            return fake_reply(DESIGN_SPEC)
        if role == "coder":
            published, = bus.history("T01", type=MsgType.DESIGN_SPEC)
            assert published.content == DESIGN_SPEC
            assert f"## DESIGN SPEC\n{DESIGN_SPEC}\n\n## PROJECT FILES" in prompt
            coder_prompts.append(prompt)
            return fake_reply(file_block("app/main.py", f"VALUE = {len(coder_prompts)}"))
        if role == "reviewer":
            return fake_reply(REJECT if len(coder_prompts) == 1 else APPROVE)
        if prompt.startswith("MODE: WRITE_TESTS"):
            assert "## DESIGN SPEC" not in prompt
            return fake_reply(
                file_block("tests/test_T01.py", "from app.main import VALUE\n\ndef test_value():\n    assert VALUE == 3")
                + "\n" + file_block("tests/conftest.py", "# Shared fixtures")
            )
        if prompt.startswith("MODE: REPORT"):
            if len(coder_prompts) == 2:
                assert prompt.count("Exit code: 1") == 2
                return fake_reply("RESULT: FAIL\nCAUSE: CODE\nSUMMARY: Incorrect value.")
            assert prompt.count("Exit code: 0") == 2
            return fake_reply("RESULT: PASS\nSUMMARY: Both suites passed.")
        assert prompt.startswith("MODE: CLOSE")
        return fake_reply(DONE)

    monkeypatch.setattr(llm, "chat", chat)
    assert run_project("Build the app.", bus, workspace, only="T01") == {"T01": "DONE"}
    assert roles.count("designer") == 1
    assert len(coder_prompts) == 3
    assert "## FEEDBACK" not in coder_prompts[0]
    assert all("## FEEDBACK" in prompt for prompt in coder_prompts[1:])
    spec, = bus.history("T01", type=MsgType.DESIGN_SPEC)
    submissions = bus.history("T01", sender=Agent.CODER, type=MsgType.CODE_SUBMIT)
    assert (spec.sender, spec.to, spec.iteration) == (Agent.DESIGNER, Agent.CODER, 0)
    assert all(spec.id < submission.id for submission in submissions)
    assert spec.artifacts == ["logs/artifacts/T01/design_spec.md"]
    assert (bus.db_path.parent / "artifacts/T01/design_spec.md").read_text(encoding="utf-8") == DESIGN_SPEC
