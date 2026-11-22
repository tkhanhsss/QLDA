"""Verify the transcript format and one-line content previews."""

from core.schema import Agent, Message, MsgType
from core.transcript import format_entry


def test_report_entry_includes_task_iteration_and_status() -> None:
    msg = Message(
        run_id="run-1",
        timestamp="2026-11-23T09:15:02+00:00",
        task_id="T03",
        iteration=2,
        sender=Agent.TESTER,
        to=Agent.CODER,
        type=MsgType.TEST_REPORT,
        status="FAIL",
        content="Thiếu dữ liệu.\n  Chạy lại.",
    )

    assert format_entry(msg) == (
        "[09:15:02] **Tester → Coder** (T03, vòng 2, test_report, FAIL): "
        "Thiếu dữ liệu. Chạy lại."
    )


def test_long_entry_without_task_or_status_escapes_markdown() -> None:
    msg = Message(
        run_id="run-1",
        timestamp="2026-11-23T09:15:02+00:00",
        sender=Agent.USER,
        to=Agent.PM,
        type=MsgType.REQUIREMENT,
        content="**Việc** " + "x" * 200,
    )

    assert format_entry(msg) == (
        r"[09:15:02] **User → PM** (-, vòng 0, requirement): \*\*Việc\*\* "
        + "x" * 150
        + "…"
    )
