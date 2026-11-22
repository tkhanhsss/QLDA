"""Exercise message persistence, run isolation, and transcript export."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pytest

from core.message_bus import MessageBus
from core.schema import Agent, Message, MsgType


def requirement(run_id: str) -> Message:
    """Build a draft requirement without a bus-assigned timestamp."""
    return Message(
        run_id=run_id,
        sender=Agent.USER,
        to=Agent.PM,
        type=MsgType.REQUIREMENT,
        content="Quản lý công việc\nCó kiểm thử.",
    )


def test_publish_three_messages_to_all_logs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bus = MessageBus("run-1", tmp_path)
    draft = requirement("run-1")
    first = bus.publish(draft)
    second = bus.publish(
        Message(
            run_id="run-1",
            task_id="T01",
            sender=Agent.PM,
            to=Agent.CODER,
            type=MsgType.TASK_ASSIGN,
            content="Tạo API health",
        )
    )
    third = bus.publish(
        Message(
            run_id="run-1",
            id=999,
            timestamp="draft",
            task_id="T01",
            iteration=2,
            sender=Agent.TESTER,
            to=Agent.CODER,
            type=MsgType.TEST_REPORT,
            status="PASS",
            content="Kiểm thử đạt",
            artifacts=["logs/artifacts/T01/test.log"],
            meta={"tokens_in": None, "tokens_out": 42},
        )
    )

    assert draft.id is None
    assert draft.timestamp == ""
    assert [first.id, second.id, third.id] == [1, 2, 3]
    for msg in (first, second, third):
        assert datetime.fromisoformat(msg.timestamp).tzinfo is not None
    with closing(sqlite3.connect(tmp_path / "messages.db")) as db:
        rows = db.execute(
            "SELECT id, run_id, sender, content FROM messages ORDER BY id"
        )
        assert rows.fetchall() == [
            (msg.id, msg.run_id, msg.sender.value, msg.content)
            for msg in (first, second, third)
        ]
    assert MessageBus("run-1", tmp_path).history() == [first, second, third]

    lines = (tmp_path / "messages.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        msg.model_dump(mode="json", by_alias=True) for msg in (first, second, third)
    ]
    assert json.loads(lines[2])["from"] == "tester"
    assert "sender" not in json.loads(lines[2])

    transcript = (tmp_path / "transcript.md").read_text(encoding="utf-8").splitlines()
    assert len(transcript) == 3
    assert (
        "**User → PM** (-, vòng 0, requirement): Quản lý công việc Có kiểm thử."
        in transcript[0]
    )
    assert "**PM → Coder** (T01, vòng 0, task_assign): Tạo API health" in transcript[1]
    assert (
        "**Tester → Coder** (T01, vòng 2, test_report, PASS): Kiểm thử đạt"
        in transcript[2]
    )
    terminal = capsys.readouterr().out
    assert "User → PM" in terminal
    assert "PM → Coder" in terminal
    assert "Tester → Coder" in terminal


def test_queries_are_scoped_to_a_run_and_export_keeps_all_runs(tmp_path: Path) -> None:
    bus = MessageBus("run-1", tmp_path)
    other_bus = MessageBus("run-2", tmp_path)
    first = bus.publish(requirement("run-1"))
    other = other_bus.publish(requirement("run-2"))
    assigned = bus.publish(
        Message(
            run_id="run-1",
            task_id="T01",
            sender=Agent.PM,
            to=Agent.CODER,
            type=MsgType.TASK_ASSIGN,
            content="Tạo API health",
        )
    )

    assert bus.inbox(Agent.PM) == [first]
    assert bus.inbox(Agent.CODER, task_id="T01") == [assigned]
    assert bus.inbox(Agent.CODER, task_id="T02") == []
    assert bus.history(task_id="T01", sender=Agent.PM, type=MsgType.TASK_ASSIGN) == [
        assigned
    ]
    assert bus.history(task_id="T01", sender=Agent.USER) == []
    assert other_bus.history() == [other]

    with pytest.raises(ValueError, match="run_id"):
        bus.publish(requirement("run-2"))
    transcript_path = tmp_path / "transcript.md"
    expected = transcript_path.read_text(encoding="utf-8")
    assert len(expected.splitlines()) == 3
    transcript_path.unlink()
    assert other_bus.export_transcript() == expected
    assert transcript_path.read_text(encoding="utf-8") == expected


def test_failed_commit_rolls_back_all_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingConnection(sqlite3.Connection):
        def commit(self) -> None:
            raise sqlite3.OperationalError("commit failed")

    def failing_connect() -> sqlite3.Connection:
        return sqlite3.connect(bus.db_path, factory=FailingConnection)

    bus = MessageBus("run-1", tmp_path)
    first = bus.publish(requirement("run-1"))
    paths = [bus.jsonl_path, bus.transcript_path]
    original_logs = [path.read_bytes() for path in paths]
    with monkeypatch.context() as patch:
        patch.setattr(bus, "_connect", failing_connect)
        with pytest.raises(sqlite3.OperationalError, match="commit failed"):
            bus.publish(requirement("run-1"))

    assert bus.history() == [first]
    assert [path.read_bytes() for path in paths] == original_logs
    second = bus.publish(requirement("run-1"))
    assert bus.history() == [first, second]
