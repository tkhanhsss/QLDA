"""Read dashboard data from the existing message log and workspace."""

import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from core.schema import Agent, Message, MsgType

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "logs" / "messages.db"
ARTIFACTS_DIR = ROOT / "logs" / "artifacts"
WORKSPACE_DIR = ROOT / "workspace"
KANBAN_COLUMNS = ("Todo", "In progress", "Testing", "Done", "Blocked")
TASK_ID = re.compile(r"T[0-9]{2}")
BACKLOG = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


@contextmanager
def _read_database() -> Iterator[sqlite3.Connection | None]:
    if not DB_PATH.is_file():
        yield None
        return
    with closing(sqlite3.connect(f"{DB_PATH.resolve().as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        # A new MessageBus may still be creating its table.
        table = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages'")
        yield db if table.fetchone() else None


def list_runs() -> list[str]:
    """Return run IDs ordered by when their first message was published, newest first."""
    with _read_database() as db:
        if db is None:
            return []
        rows = db.execute("SELECT run_id FROM messages GROUP BY run_id ORDER BY MIN(id) DESC")
        return [row["run_id"] for row in rows]


def load_messages(
    run_id: str, task_id: str | None = None, sender: str | None = None, type: str | None = None,
) -> list[Message]:
    """Read messages in publication order, applying all supplied filters."""
    filters = {"run_id": run_id, "task_id": task_id, "sender": sender, "type": type}
    active = {column: value for column, value in filters.items() if value is not None}
    where = " AND ".join(f"{column} = ?" for column in active)
    with _read_database() as db:
        if db is None:
            return []
        rows = db.execute(f"SELECT * FROM messages WHERE {where} ORDER BY id", tuple(active.values()))
        messages = []
        for row in rows:
            values = dict(row)
            values["artifacts"] = json.loads(values["artifacts"])
            values["meta"] = json.loads(values["meta"])
            messages.append(Message.model_validate(values))
        return messages


def _planned_tasks(message: Message) -> list[str]:
    if (
        message.type != MsgType.TASK_ASSIGN or message.sender != Agent.PM
        or message.to != Agent.ORCHESTRATOR or message.task_id is not None
    ):
        return []
    block = BACKLOG.fullmatch(message.content.strip())
    if block is None:
        return []
    try:
        tasks = json.loads(block[1])
    except json.JSONDecodeError:
        return []
    if not isinstance(tasks, list):
        return []
    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    return [task_id for task_id in ids if isinstance(task_id, str) and TASK_ID.fullmatch(task_id)]


def build_kanban(messages: Sequence[Message]) -> dict[str, str]:
    """Map task IDs to columns using messages in publication order.

    The PM backlog introduces Todo tasks. Assignment moves them to In progress.
    Code submission or review moves them to Testing. A PASS/FAIL report ends
    Testing and returns the task to In progress until another submission,
    review, or final decision. A revision request to the Coder also marks In
    progress. Done and Blocked take precedence over these intermediate events.
    If two final decisions exist for a task, the later one takes precedence.
    """
    tasks: dict[str, str] = {}
    final = {MsgType.TASK_DONE: "Done", MsgType.TASK_BLOCKED: "Blocked"}
    for message in messages:
        task_id = message.task_id
        if task_id is None:
            for planned in _planned_tasks(message):
                tasks.setdefault(planned, "Todo")
            continue
        state = tasks.setdefault(task_id, "Todo")
        if message.type in final:
            tasks[task_id] = final[message.type]
        elif state in final.values():
            continue
        elif message.type in {MsgType.CODE_SUBMIT, MsgType.REVIEW_RESULT}:
            tasks[task_id] = "Testing"
        elif (
            message.type == MsgType.TASK_ASSIGN and state == "Todo"
            or message.type == MsgType.TEST_REPORT and message.status in {"PASS", "FAIL"}
            or message.type == MsgType.REVISION_REQUEST and message.to == Agent.CODER
        ):
            tasks[task_id] = "In progress"
    return dict(sorted(tasks.items()))


@dataclass(frozen=True)
class RunStats:
    """Aggregated counts and elapsed time for the displayed run."""

    total_messages: int
    messages_by_agent: dict[Agent, int]
    tokens_in: int
    tokens_out: int
    duration_seconds: float
    revisions_by_task: dict[str, int]


def compute_stats(messages: Sequence[Message]) -> RunStats:
    """Count messages and tokens, and record the maximum iteration per task."""
    revisions: dict[str, int] = {}
    for message in messages:
        if message.task_id is not None:
            revisions[message.task_id] = max(revisions.get(message.task_id, 0), message.iteration)
    duration = 0.0
    if len(messages) > 1:
        start = datetime.fromisoformat(messages[0].timestamp)
        end = datetime.fromisoformat(messages[-1].timestamp)
        duration = (end - start).total_seconds()
    return RunStats(
        total_messages=len(messages),
        messages_by_agent=dict(Counter(message.sender for message in messages)),
        tokens_in=sum(message.meta.get("tokens_in") or 0 for message in messages),
        tokens_out=sum(message.meta.get("tokens_out") or 0 for message in messages),
        duration_seconds=duration,
        revisions_by_task=revisions,
    )


def _read_under(directory: Path, name: str) -> str | None:
    relative = PurePosixPath(name.replace("\\", "/"))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts or ":" in name:
        raise ValueError("Đường dẫn tệp không hợp lệ.")
    directory = directory.resolve()
    target = (directory / relative).resolve()
    if not target.is_relative_to(directory):
        raise ValueError("Đường dẫn tệp nằm ngoài thư mục cho phép.")
    try:
        return target.read_text(encoding="utf-8") if target.is_file() else None
    except FileNotFoundError:
        return None


def load_artifact(task_id: str, name: str) -> str | None:
    """Read a task artifact, rejecting traversal and links outside its directory."""
    if not TASK_ID.fullmatch(task_id):
        raise ValueError("ID task không hợp lệ.")
    directory = ARTIFACTS_DIR.resolve() / task_id
    if directory.resolve() != directory:
        raise ValueError("Thư mục artifact không hợp lệ.")
    return _read_under(directory, name)


def load_workspace_file(name: str) -> str | None:
    """Read a referenced product file from the current workspace."""
    if any(part.startswith(".") and part != ".gitignore" for part in name.replace("\\", "/").split("/")):
        raise ValueError("Đường dẫn tệp workspace không hợp lệ.")
    return _read_under(WORKSPACE_DIR, name)
