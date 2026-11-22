"""Verify dashboard persistence, aggregation, and safe reads without Streamlit."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from core.message_bus import MessageBus
from core.schema import Agent, Message, MsgType
from dashboard import data


def message(kind: MsgType, task_id: str | None = None, **overrides: object) -> Message:
    values = {"run_id": "first", "sender": Agent.PM, "to": Agent.ORCHESTRATOR,
              "type": kind, "task_id": task_id, "content": "Example message"}
    return Message.model_validate({**values, **overrides})


def test_kanban_tracks_backlog_assignment_testing_and_final_decisions() -> None:
    plan = message(MsgType.TASK_ASSIGN, content='```json\n[{"id":"T01"}]\n```')
    messages = [plan, *(message(MsgType.TASK_ASSIGN, f"T{number:02}") for number in range(2, 8)),
                message(MsgType.CODE_SUBMIT, "T03"), message(MsgType.REVIEW_RESULT, "T04"),
                message(MsgType.TASK_DONE, "T04"), message(MsgType.TASK_BLOCKED, "T05"),
                message(MsgType.CODE_SUBMIT, "T05"), message(MsgType.REVIEW_RESULT, "T06"),
                message(MsgType.TEST_REPORT, "T06", status="PASS"),
                message(MsgType.CODE_SUBMIT, "T07"),
                message(MsgType.TEST_REPORT, "T07", status="FAIL"),
                message(MsgType.CODE_SUBMIT, "T07", iteration=1)]
    assert data.build_kanban(messages) == {
        "T01": "Todo", "T02": "In progress", "T03": "Testing", "T04": "Done",
        "T05": "Blocked", "T06": "In progress", "T07": "Testing",
    }
    assert data.build_kanban([*messages, message(MsgType.REVISION_REQUEST, "T07", to=Agent.CODER)])[
        "T07"
    ] == "In progress"


def test_stats_count_tokens_and_ignore_none() -> None:
    messages = [
        message(MsgType.TASK_ASSIGN, "T01", timestamp="2026-11-23T12:00:00+00:00",
                meta={"tokens_in": None, "tokens_out": 8}),
        message(MsgType.CODE_SUBMIT, "T01", sender=Agent.CODER, iteration=2,
                meta={"tokens_in": 41, "tokens_out": None}),
        message(MsgType.TASK_DONE, "T01", iteration=1, timestamp="2026-11-23T12:01:05+00:00"),
    ]
    assert data.compute_stats(messages) == data.RunStats(
        total_messages=3, messages_by_agent={Agent.PM: 2, Agent.CODER: 1},
        tokens_in=41, tokens_out=8, duration_seconds=65, revisions_by_task={"T01": 2},
    )
    assert data.compute_stats([]) == data.RunStats(0, {}, 0, 0, 0, {})


def test_read_filters_runs_and_leaves_database_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_bus = MessageBus("first", tmp_path)
    second_bus = MessageBus("second", tmp_path)
    first = first_bus.publish(message(MsgType.TASK_ASSIGN, "T01"))
    second_bus.publish(message(MsgType.TASK_ASSIGN, "T01", run_id="second"))
    report = first_bus.publish(message(MsgType.TEST_REPORT, "T01", sender=Agent.TESTER,
                                       status="PASS", artifacts=["task.log"], meta={"tokens_in": None}))
    first_bus.publish(message(MsgType.TEST_REPORT, "T02", sender=Agent.TESTER))
    database = first_bus.db_path
    monkeypatch.setattr(data, "DB_PATH", database)
    before = database.read_bytes(), database.stat().st_mtime_ns

    assert data.list_runs() == ["second", "first"]
    assert data.load_messages("first")[:2] == [first, report]
    assert data.load_messages("first", "T01", "tester", "test_report") == [report]
    assert data.load_messages("first' OR 1=1 --") == []
    with closing(sqlite3.connect(database)) as db:
        assert db.execute("SELECT COUNT(*) FROM messages").fetchone() == (4,)
    assert (database.read_bytes(), database.stat().st_mtime_ns) == before


def test_missing_database_is_not_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database = tmp_path / "missing.db"
    monkeypatch.setattr(data, "DB_PATH", database)
    assert data.list_runs() == data.load_messages("run") == []
    assert not database.exists()


def test_load_artifact_checks_task_and_relative_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data, "ARTIFACTS_DIR", tmp_path)
    directory = tmp_path / "T07" / "later-run"
    directory.mkdir(parents=True)
    (directory / "design_spec.md").write_text("## Overview", encoding="utf-8")
    assert data.load_artifact("T07", "later-run/design_spec.md") == "## Overview"
    assert data.load_artifact("T07", "missing.log") is None
    for name in ("../private.txt", "later-run/../design_spec.md", r"..\private.txt", "/private.txt",
                 "C:/private.txt"):
        with pytest.raises(ValueError):
            data.load_artifact("T07", name)
    with pytest.raises(ValueError):
        data.load_artifact("../T07", "design_spec.md")
