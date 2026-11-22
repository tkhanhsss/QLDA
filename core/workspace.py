"""Parse agent files and run project commands in a dedicated workspace."""

import math
import ntpath
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory

from core.schema import Agent

_FILE_BLOCK = re.compile(
    r"### FILE:[ \t]+(?P<path>[^\n]+)\n"
    r"```[^`\n]*\n(?P<content>(?:(?!^```)[^\n]*\n)*)^```[ \t]*(?:\n|$)",
    re.MULTILINE,
)
_WHITESPACE = re.compile(r"\s*")
_INVALID_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_ALLOWED_COMMANDS = {"pytest", "ruff", "git"}


def _is_reserved_windows_name(part: str) -> bool:
    """Check Windows file names across the supported Python versions."""
    if hasattr(ntpath, "isreserved"):
        return ntpath.isreserved(part)
    return PureWindowsPath(part).is_reserved()


def _relative_path(path: str, agent: Agent) -> PurePosixPath:
    """Normalize either slash style and reject unsafe workspace paths."""
    relative = PurePosixPath(path.replace("\\", "/"))
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in path
        or _INVALID_PATH_CHARS.search(path)
        or any(
            part.endswith((" ", ".")) or _is_reserved_windows_name(part)
            for part in relative.parts
        )
    ):
        raise ValueError(f"Invalid workspace-relative path: {path!r}")
    top_level = relative.parts[0].casefold()
    if top_level == ".git":
        raise ValueError(f"Agent files cannot access Git metadata: {path!r}")
    if agent == Agent.CODER and top_level == "tests":
        raise ValueError(f"Coder cannot write to tests/: {path!r}")
    return relative


def parse_files(text: str, agent: Agent = Agent.CODER) -> dict[str, str]:
    """Read a sequence of FILE blocks, preserving each file's content."""
    text = text.replace("\r\n", "\n")
    files: dict[str, str] = {}
    position = 0
    while (position := _WHITESPACE.match(text, position).end()) < len(text):
        block = _FILE_BLOCK.match(text, position)
        if block is None:
            line = text.count("\n", 0, position) + 1
            raise ValueError(f"Expected a FILE header and one fenced code block at line {line}.")
        path = _relative_path(block["path"].strip(), agent).as_posix()
        if path in files:
            raise ValueError(f"Duplicate FILE path: {path!r}")
        files[path] = block["content"]
        position = block.end()
    if not files:
        raise ValueError("Expected at least one FILE block.")
    return files


class Workspace:
    """Manage agent files and trusted command arguments for one project."""

    def __init__(self, root: str | Path = "workspace") -> None:
        """Create the workspace directory if it does not exist."""
        root = Path(root)
        if root.is_symlink() or root.resolve() != root.parent.resolve() / root.name:
            raise ValueError(f"Workspace root must be a regular directory: {root}")
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, path: str, agent: Agent) -> Path:
        """Validate both the supplied path and its resolved destination."""
        target = self.root / _relative_path(path, agent)
        resolved = target.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError(f"Path resolves outside the workspace: {path!r}")
        _relative_path(resolved.relative_to(self.root).as_posix(), agent)
        return resolved

    def write_files(self, files: Mapping[str, str], agent: Agent = Agent.CODER) -> None:
        """Validate all destinations, then replace each file with UTF-8 text."""
        targets: dict[Path, str] = {}
        for path, content in files.items():
            target = self._target(path, agent)
            if target in targets:
                raise ValueError(f"Duplicate file destination: {path!r}")
            targets[target] = content

        for target, content in targets.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(dir=target.parent) as temporary:
                temporary_path = Path(temporary) / "file"
                temporary_path.write_text(content, encoding="utf-8", newline="\n")
                temporary_path.replace(target)

    def run(self, cmd: Sequence[str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
        """Run an allowlisted argument vector and capture its result."""
        if isinstance(cmd, str) or not cmd:
            raise ValueError("Pass a nonempty argument list to Workspace.run().")
        args = list(cmd)
        python_module = args[:2] == ["python", "-m"] and len(args) >= 3 and bool(args[2])
        if args[0] not in _ALLOWED_COMMANDS and not python_module:
            raise ValueError(f"Command not allowed in workspace: {args[:2]!r}")
        command = "python -m" if python_module else args[0]
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Command timeout must be a positive number of seconds.")
        if args[0] in {"pytest", "ruff"}:
            args = [sys.executable, "-m", *args]
        elif args[0] == "python":
            args[0] = sys.executable

        try:
            return subprocess.run(
                args, cwd=self.root, shell=False, check=False, timeout=timeout,
                capture_output=True, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Workspace command {command!r} exceeded {timeout:g} seconds and was killed."
            ) from error

    def run_pytest(self, path: str = "tests/") -> subprocess.CompletedProcess[str]:
        """Run pytest for a workspace-relative path with a 60-second limit."""
        target = self._target(path, Agent.TESTER).relative_to(self.root)
        return self.run(["pytest", "--", target.as_posix()], timeout=60)

    def run_ruff(self) -> subprocess.CompletedProcess[str]:
        """Run Ruff over the workspace."""
        return self.run(["ruff", "check", "."])

    def git_commit(self, msg: str) -> subprocess.CompletedProcess[str]:
        """Initialize a local Git repository if needed, then stage and commit."""
        git_dir = self.root / ".git"
        if git_dir.resolve() != git_dir or (git_dir.exists() and not git_dir.is_dir()):
            raise ValueError("Workspace Git metadata must be a local .git directory.")
        git = ["git", "--git-dir=.git", "--work-tree=."]
        if not git_dir.exists():
            initialized = self.run([*git, "init"])
            initialized.check_returncode()
        staged = self.run([*git, "add", "-A"])
        staged.check_returncode()
        committed = self.run([*git, "commit", "-m", msg])
        committed.check_returncode()
        return committed
