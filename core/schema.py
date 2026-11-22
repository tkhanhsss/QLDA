"""Define the messages exchanged by agents through the bus."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Agent(str, Enum):
    """Identify a participant in a run."""

    USER = "user"
    PM = "pm"
    DESIGNER = "designer"
    CODER = "coder"
    REVIEWER = "reviewer"
    TESTER = "tester"
    ORCHESTRATOR = "orchestrator"


class MsgType(str, Enum):
    """Identify the purpose of a message."""

    REQUIREMENT = "requirement"
    TASK_ASSIGN = "task_assign"
    DESIGN_SPEC = "design_spec"
    CODE_SUBMIT = "code_submit"
    REVIEW_RESULT = "review_result"
    TEST_REPORT = "test_report"
    REVISION_REQUEST = "revision_request"
    TASK_DONE = "task_done"
    TASK_BLOCKED = "task_blocked"


class Message(BaseModel):
    """Carry message content, routing information, and optional artifacts."""

    model_config = ConfigDict(populate_by_name=True)

    id: int | None = None
    run_id: str
    timestamp: str = ""  # Set by the bus on publish.
    task_id: str | None = None
    iteration: int = 0
    sender: Agent = Field(alias="from")
    to: Agent
    type: MsgType
    status: str | None = None
    content: str
    artifacts: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
