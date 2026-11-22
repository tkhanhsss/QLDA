"""Verify the message schema used by the bus and JSONL log."""

import pytest
from pydantic import ValidationError

from core.schema import Agent, Message, MsgType


def test_message_accepts_sender_and_from_alias() -> None:
    message = Message(
        run_id="run-1",
        sender=Agent.USER,
        to=Agent.PM,
        type=MsgType.REQUIREMENT,
        content="Quản lý công việc",
    )

    payload = message.model_dump(mode="json", by_alias=True)
    assert payload["from"] == "user"
    assert "sender" not in payload
    assert Message.model_validate(payload) == message
    assert message.id is None
    assert message.task_id is None
    assert message.iteration == 0


def test_message_validates_enums_and_uses_independent_defaults() -> None:
    payload = {
        "run_id": "run-1",
        "from": "tester",
        "to": "coder",
        "type": "test_report",
        "content": "PASS",
    }
    message = Message.model_validate(payload)
    message.artifacts.append("logs/artifacts/T01/test.log")
    message.meta["tokens_in"] = 10

    other = Message.model_validate(payload)
    assert other.artifacts == []
    assert other.meta == {}
    with pytest.raises(ValidationError):
        Message.model_validate({**payload, "from": "unknown"})
