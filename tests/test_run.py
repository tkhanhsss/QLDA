"""Verify command-line setup and the router connectivity gate."""

from pathlib import Path

import pytest

from core import run
from core.llm import LLMError
from core.message_bus import MessageBus
from core.workspace import Workspace


@pytest.mark.parametrize("options", [[], ["--only", "T01"]])
def test_main_checks_router_before_running_t01(
    options: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.chdir(tmp_path)
    Path("requirements.md").write_text("Build GET /health.", encoding="utf-8")

    def run_t01(requirements: str, bus: MessageBus, workspace: Workspace) -> None:
        calls.append("run_t01")
        assert requirements == "Build GET /health."
        assert workspace.root == tmp_path.resolve() / "workspace"
        assert bus.db_path.is_file()
        assert bus.run_id in capsys.readouterr().out

    monkeypatch.setattr(run, "check_router", lambda: calls.append("check_router"))
    monkeypatch.setattr(run, "run_t01", run_t01)
    assert run.main(options) == 0
    assert calls == ["check_router", "run_t01"]


def test_main_exits_when_router_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def check_router() -> None:
        raise LLMError("Connection error.")

    def run_t01(requirements: str, bus: MessageBus, workspace: Workspace) -> None:
        pytest.fail("T01 ran after a failed router check.")

    monkeypatch.setattr(run, "check_router", check_router)
    monkeypatch.setattr(run, "run_t01", run_t01)
    assert run.main([]) == 1
    assert "Hãy chạy 9Router và kiểm tra .env." in capsys.readouterr().err
