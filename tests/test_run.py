"""Verify command-line task selection and the router connectivity gate."""

from pathlib import Path

import pytest

from core import run
from core.llm import LLMError
from core.message_bus import MessageBus
from core.workspace import Workspace


@pytest.mark.parametrize(("options", "selection"), [
    ([], ("T01", None)),
    (["--only", "T2"], ("T02", None)),
    (["--until", "T03"], (None, "T03")),
])
def test_main_checks_router_before_running_tasks(
    options: list[str], selection: tuple[str | None, str | None],
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls = []
    monkeypatch.chdir(tmp_path)
    Path("requirements.md").write_text("Build GET /health.", encoding="utf-8")

    def run_project(
        requirements: str, bus: MessageBus, workspace: Workspace, *, only: str, until: str,
    ) -> dict[str, str]:
        calls.append("run_project")
        assert (only, until) == selection
        assert requirements == "Build GET /health."
        assert workspace.root == tmp_path.resolve() / "workspace"
        assert bus.db_path.is_file()
        assert bus.run_id in capsys.readouterr().out
        return {only or until: "DONE"}

    monkeypatch.setattr(run, "check_router", lambda: calls.append("check_router"))
    monkeypatch.setattr(run, "run_project", run_project)
    assert run.main(options) == 0
    assert calls == ["check_router", "run_project"]


def test_main_exits_when_router_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def check_router() -> None:
        raise LLMError("Connection error.")

    def run_project(*args: object, **kwargs: object) -> None:
        pytest.fail("Pipeline ran after a failed router check.")

    monkeypatch.setattr(run, "check_router", check_router)
    monkeypatch.setattr(run, "run_project", run_project)
    assert run.main([]) == 1
    assert "Hãy chạy 9Router và kiểm tra .env." in capsys.readouterr().err
