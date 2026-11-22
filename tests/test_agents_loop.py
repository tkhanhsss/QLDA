"""Exercise Reviewer and Tester revision paths with real Ruff and pytest."""

from pathlib import Path

import pytest
from test_orchestrator import (
    APPROVE,
    BACKLOG,
    BLOCKED,
    BRIEF,
    DONE,
    REJECT,
    commits,
    fake_reply,
    file_block,
)

from core import llm
from core.message_bus import MessageBus
from core.orchestrator import run_project
from core.schema import Agent, MsgType
from core.workspace import Workspace


@pytest.mark.parametrize(("first_failure", "expected_status", "rounds", "writes"), [
    ("review", "DONE", [0, 1], 1),
    ("ruff", "DONE", [0, 1], 1),
    ("code", "DONE", [0, 1], 1),
    ("test", "DONE", [0], 2),
    ("test_twice", "BLOCKED", [0], 2),
    ("false_pass", "BLOCKED", [0], 1),
])
def test_revision_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    first_failure: str, expected_status: str, rounds: list[int], writes: int,
) -> None:
    for key in ("GIT_AUTHOR", "GIT_COMMITTER"):
        monkeypatch.setenv(f"{key}_NAME", "M5 test")
        monkeypatch.setenv(f"{key}_EMAIL", "test@example.invalid")
    bus = MessageBus("loop-test", tmp_path / "logs")
    workspace = Workspace(tmp_path / "workspace")
    workspace.write_files({".gitignore": "__pycache__/\n", "app/main.py": "VALUE = 1\n"})
    workspace.git_commit("T01: coder output (chưa qua Tester)")
    baseline = commits(workspace)
    submissions = 0
    test_writes = 0

    def chat(role: str, system: str, prompt: str) -> llm.LLMResult:
        nonlocal submissions, test_writes
        if prompt.startswith("MODE: PLAN"):
            return fake_reply(BACKLOG)
        if prompt.startswith("MODE: ASSIGN"):
            return fake_reply(BRIEF)
        if role == "coder":
            submissions += 1
            if submissions > 1:
                assert "Revision 1 of 3" in prompt
            value = int(submissions > 1 or first_failure not in {"code", "false_pass"})
            lint_issue = "import os\n\n" if first_failure == "ruff" and submissions == 1 else ""
            return fake_reply(file_block("app/main.py", f"{lint_issue}VALUE = {value}\n# CODER_SOURCE_ONLY"))
        if role == "reviewer":
            if first_failure == "review" and submissions == 1:
                return fake_reply(REJECT)
            if first_failure == "review":
                assert "## PREVIOUS FEEDBACK" in prompt and REJECT in prompt
            if first_failure == "ruff" and submissions == 1:
                assert "Exit code: 1" in prompt and "F401" in prompt
            return fake_reply(APPROVE)
        if prompt.startswith("MODE: WRITE_TESTS"):
            test_writes += 1
            assert "CODER_SOURCE_ONLY" not in prompt
            assert "### FILE: app/main.py" not in prompt
            assert "## CHANGED FILES" not in prompt
            assert "## PROJECT FILES" not in prompt
            if test_writes > 1:
                assert "## FEEDBACK\nCAUSE: TEST" in prompt
                assert "tests/conftest.py already exists" in prompt
            expected = 2 if first_failure == "test_twice" or (
                first_failure == "test" and test_writes == 1
            ) else 1
            output = file_block(
                "tests/test_T01.py",
                f"from app.main import VALUE\n\ndef test_value():\n    assert VALUE == {expected}",
            )
            if test_writes == 1:
                assert "tests/conftest.py is missing" in prompt
                output += "\n" + file_block("tests/conftest.py", "# Shared fixtures")
            return fake_reply(output)
        if prompt.startswith("MODE: REPORT"):
            assert commits(workspace) == baseline
            if "Exit code: 1" not in prompt or first_failure == "false_pass":
                return fake_reply("RESULT: PASS\nSUMMARY: One test passed in each run.")
            cause = "CODE" if first_failure == "code" else "TEST"
            return fake_reply(
                f"RESULT: FAIL\nCAUSE: {cause}\nSUMMARY: Assertion failed.\n"
                "FAILURES:\n- test_value | value differs | inspect the criterion\nCODER_SOURCE_ONLY"
            )
        assert prompt.startswith("MODE: CLOSE")
        if "PASSED" in prompt:
            assert commits(workspace)[1:] == baseline
            assert commits(workspace)[0] == f"T01: passed after {rounds[-1]} iterations"
            return fake_reply(DONE)
        return fake_reply(BLOCKED)

    monkeypatch.setattr(llm, "chat", chat)
    assert run_project("Build the app.", bus, workspace, only="T01") == {"T01": expected_status}
    assert test_writes == writes
    assert [m.iteration for m in bus.history("T01", sender=Agent.CODER)] == rounds
    reports = bus.history("T01", type=MsgType.TEST_REPORT)
    if first_failure in {"code", "test", "test_twice"}:
        assert reports[0].status == "FAIL" and reports[0].iteration == 0
        assert len(reports) == 2
    if expected_status == "DONE":
        assert reports[-1].status == "PASS"
    else:
        assert not bus.history("T01", type=MsgType.TASK_DONE)
        assert commits(workspace) == baseline
    log_paths = list((bus.db_path.parent / "artifacts" / "T01").glob("*.log"))
    assert len(log_paths) == max(1, len(reports)) * 2
    for report in reports:
        assert len(report.artifacts) == 2
        for artifact in report.artifacts:
            assert (tmp_path / artifact).read_text(encoding="utf-8").startswith("Exit code:")
