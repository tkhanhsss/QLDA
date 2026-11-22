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
        self._task_originals: dict[Path, bytes | None] | None = None

    def begin_task(self) -> None:
        """Track the original content of files this task writes."""
        self._task_originals = {}

    def finish_task(self, *, keep_changes: bool) -> None:
        """Restore only this task's writes when it could not pass."""
        if not keep_changes and self._task_originals is not None:
            for target, original in self._task_originals.items():
                if target.resolve() != target:
                    raise ValueError(f"Cannot restore a redirected workspace file: {target.name}")
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    self._replace(target, original)
        self._task_originals = None

    def unchanged_files(self, files: Mapping[str, str]) -> list[str]:
        """Identify submitted files whose content matches the start of the task."""
        originals = self._task_originals or {}
        unchanged = []
        for name, content in files.items():
            target = self._target(name, Agent.CODER)
            original = originals[target] if target in originals else (
                target.read_bytes() if target.is_file() else None
            )
            if original is not None and original.replace(b"\r\n", b"\n") == content.encode("utf-8"):
                unchanged.append(name)
        return unchanged

    @staticmethod
    def _replace(target: Path, content: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=target.parent) as temporary:
            temporary_path = Path(temporary) / "file"
            temporary_path.write_bytes(content)
            temporary_path.replace(target)

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
            if self._task_originals is not None and target not in self._task_originals:
                self._task_originals[target] = target.read_bytes() if target.exists() else None
            self._replace(target, content.encode("utf-8"))

    def run(
        self, cmd: Sequence[str], timeout: float = 60, *, input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
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
        if args[0] == "pytest":
            args = [sys.executable, "-B", "-m", *args]
        elif args[0] == "ruff":
            args = [sys.executable, "-m", *args]
        elif args[0] == "python":
            args[0] = sys.executable

        try:
            return subprocess.run(
                args, cwd=self.root, shell=False, check=False, timeout=timeout,
                input=input_text, capture_output=True, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError(
                f"Workspace command {command!r} exceeded {timeout:g} seconds and was killed."
            ) from error

    def run_pytest(self, path: str = "tests/") -> subprocess.CompletedProcess[str]:
        """Run pytest for a workspace-relative path with a 60-second limit."""
        target = self._target(path, Agent.TESTER).relative_to(self.root)
        command = ["pytest", "-p", "no:cacheprovider", "--", target.as_posix()]
        try:
            return self.run(command, timeout=60)
        except TimeoutError as error:
            timeout = error.__cause__
            if not isinstance(timeout, subprocess.TimeoutExpired):
                raise
            output = (timeout.stdout or b"").decode("utf-8", errors="replace")
            stderr = (timeout.stderr or b"").decode("utf-8", errors="replace")
            return subprocess.CompletedProcess(command, 124, output, f"{stderr}\n{error}\n")

    def run_ruff(self, *, include_tests: bool = True) -> subprocess.CompletedProcess[str]:
        """Run Ruff, optionally excluding the Tester-owned files from review."""
        options = [] if include_tests else ["--extend-exclude", "tests"]
        return self.run(["ruff", "check", "--no-cache", *options, "."])

    def sort_test_imports(self, name: str, source: str) -> str:
        """Apply Ruff's import-order fix to a Tester reply before writing it."""
        target = self._target(name, Agent.TESTER).relative_to(self.root).as_posix()
        result = self.run(
            ["ruff", "check", "--fix-only", "--select", "I001", "--no-cache",
             "--stdin-filename", target, "-"],
            input_text=source,
        )
        # Leave invalid source to the existing pytest and Tester repair flow.
        return result.stdout if result.returncode == 0 else source

    def git_commit(self, msg: str, *, allow_empty: bool = False) -> subprocess.CompletedProcess[str]:
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
        options = ["--allow-empty"] if allow_empty else []
        committed = self.run([*git, "commit", *options, "-m", msg])
        committed.check_returncode()
        return committed
