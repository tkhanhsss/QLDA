"""Exercise workspace parsing, path validation, and command execution."""

import os
import subprocess
from pathlib import Path
from unittest.mock import call, patch

import pytest

from core.schema import Agent
from core.workspace import Workspace, parse_files


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """Keep every test project within its own temporary directory."""
    return Workspace(tmp_path / "workspace")


def test_parse_and_write_nested_files(workspace: Workspace) -> None:
    text = (
        "### FILE: app/main.py\r\n```python\r\nTITLE = 'Công việc'\r\n```\r\n\r\n"
        "### FILE: app\\routes\\health.py\r\n```\r\n# health\r\n```\r\n"
        "### FILE: app/__init__.py\r\n```python\r\n```"
    )
    files = parse_files(text)
    assert files == {
        "app/main.py": "TITLE = 'Công việc'\n",
        "app/routes/health.py": "# health\n",
        "app/__init__.py": "",
    }
    workspace.write_files(files)
    for path, content in files.items():
        assert (workspace.root / path).read_bytes() == content.encode("utf-8")


@pytest.mark.parametrize(
    "text",
    [
        "### FILE: app/main.py\nno fence\n",
        "### FILE: app/main.py\n```python\nvalue = 1\n",
        "### FILE: a.py\n```python\nx = 1\n### FILE: b.py\n```python\ny = 2\n```\n",
        "### FILE: app/main.py\n```python\n```\n```python\n```\n",
    ],
)
def test_parse_rejects_missing_or_extra_fences(text: str) -> None:
    with pytest.raises(ValueError, match="one fenced code block"):
        parse_files(text)


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("../outside.py", "Invalid workspace-relative path"),
        ("app\\..\\outside.py", "Invalid workspace-relative path"),
        ("/outside.py", "Invalid workspace-relative path"),
        ("C:\\outside.py", "Invalid workspace-relative path"),
        ("C:outside.py", "Invalid workspace-relative path"),
        ("\\\\server\\share\\outside.py", "Invalid workspace-relative path"),
        ("tests/test_T01.py", "Coder cannot write to tests/"),
        ("Tests\\test_T01.py", "Coder cannot write to tests/"),
    ],
)
def test_unsafe_paths_are_rejected_before_writing(
    workspace: Workspace, path: str, error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        parse_files(f"### FILE: {path}\n```python\n```\n")
    with pytest.raises(ValueError, match=error):
        workspace.write_files({"valid.py": "", path: ""})
    assert list(workspace.root.iterdir()) == []


def test_write_replaces_hard_link_without_changing_outside_file(
    workspace: Workspace, tmp_path: Path,
) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("original", encoding="utf-8")
    target = workspace.root / "file.py"
    os.link(outside, target)

    workspace.write_files({"file.py": "replacement"})

    assert outside.read_text(encoding="utf-8") == "original"
    assert target.read_text(encoding="utf-8") == "replacement"


def test_tester_can_write_tests(workspace: Workspace) -> None:
    files = parse_files(
        "### FILE: tests/test_T01.py\n```python\ndef test_example():\n    assert True\n```\n",
        agent=Agent.TESTER,
    )
    workspace.write_files(files, agent=Agent.TESTER)
    assert (workspace.root / "tests" / "test_T01.py").is_file()


def test_review_context_and_rollback_use_pre_task_content(workspace: Workspace) -> None:
    original = {"app/main.py": "VALUE = 1\n"}
    revision = {"app/main.py": "VALUE = 2\n", "pytest.ini": "[pytest]\npythonpath = .\n"}
    workspace.write_files(original)
    workspace.begin_task()
    assert workspace.unchanged_files(original) == ["app/main.py"]
    workspace.write_files(revision)
    assert workspace.unchanged_files(revision) == []
    assert workspace.unchanged_files(original) == ["app/main.py"]
    workspace.finish_task(keep_changes=False)
    assert (workspace.root / "app/main.py").read_text(encoding="utf-8") == original["app/main.py"]
    assert not (workspace.root / "pytest.ini").exists()


@pytest.mark.parametrize("cmd", [["cmd", "/c", "dir"], ["python", "-c", "pass"], ["python"]])
def test_run_rejects_commands_outside_allowlist(workspace: Workspace, cmd: list[str]) -> None:
    with pytest.raises(ValueError, match="Command not allowed"):
        workspace.run(cmd, timeout=1)


def test_run_captures_output_and_exit_code_in_workspace(workspace: Workspace) -> None:
    workspace.write_files({"check_cwd.py": "from pathlib import Path\nprint(Path.cwd())\n"})
    result = workspace.run(["python", "-m", "check_cwd"], timeout=10)
    assert result.returncode == 0
    assert Path(result.stdout.strip()) == workspace.root


def test_run_kills_command_after_timeout(workspace: Workspace) -> None:
    workspace.write_files({"slow_task.py": "from time import sleep\nsleep(1)\n"})
    with pytest.raises(TimeoutError, match=r"python -m.*0\.05 seconds.*killed"):
        workspace.run(["python", "-m", "slow_task"], timeout=0.05)


def test_pytest_and_ruff_run_in_workspace(workspace: Workspace) -> None:
    workspace.write_files(
        {"tests/test_T01.py": "def test_example():\n    assert False\n"}, agent=Agent.TESTER,
    )
    result = workspace.run_pytest("tests/test_T01.py")
    assert result.returncode == 1
    assert "test_example" in result.stdout
    assert workspace.run_ruff().returncode == 0


def test_sort_test_imports_formats_source_without_writing_workspace(workspace: Workspace) -> None:
    name = "tests/test_T01.py"
    source = "from pathlib import Path\nimport re\n\nFILES = Path('.')\n"
    expected = "import re\nfrom pathlib import Path\n\nFILES = Path('.')\n"

    assert workspace.sort_test_imports(name, source) == expected
    assert not (workspace.root / name).exists()


def test_git_commit_initializes_and_stages_before_commit(workspace: Workspace) -> None:
    result = subprocess.CompletedProcess(args=[], returncode=0)
    git = ["git", "--git-dir=.git", "--work-tree=."]
    with patch.object(workspace, "run", return_value=result) as run:
        assert workspace.git_commit("T01: passed") == result
    assert run.call_args_list == [
        call([*git, "init"]),
        call([*git, "add", "-A"]),
        call([*git, "commit", "-m", "T01: passed"]),
    ]
