"""Run the PM-to-Coder workflow for T01 in milestone M4."""

import json
from typing import cast

from agents.base import Agent as LLMAgent
from agents.base import AgentResult, parse_backlog, redact_api_key
from core.message_bus import MessageBus
from core.schema import Agent, Message, MsgType
from core.workspace import Workspace

TASK_ID = "T01"
REQUIRED_FILES = {"app/main.py", "requirements.txt", "README.md"}
SKELETON_FILES = REQUIRED_FILES | {"app/__init__.py", ".gitignore"}
COMMIT_MESSAGE = "T01: coder output (chưa qua Tester)"


def _project_files(workspace: Workspace) -> dict[str, str]:
    """Read existing T01 files without following paths outside the workspace."""
    files = {}
    for name in sorted(SKELETON_FILES):
        path = workspace.root / name
        if path.resolve().is_relative_to(workspace.root) and path.is_file():
            files[name] = path.read_text(encoding="utf-8")
    return files


def _publish_reply(
    bus: MessageBus,
    result: AgentResult,
    *,
    sender: Agent,
    recipient: Agent,
    kind: MsgType,
    task_id: str | None = None,
    artifacts: list[str] | None = None,
) -> None:
    """Record an agent reply and the router usage reported for it."""
    bus.publish(Message(
        run_id=bus.run_id,
        task_id=task_id,
        sender=sender,
        to=recipient,
        type=kind,
        content=redact_api_key(result.text),
        artifacts=artifacts or [],
        meta={
            "model": result.model,
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "duration_ms": result.duration_ms,
        },
    ))


def run_t01(requirements: str, bus: MessageBus, workspace: Workspace) -> None:
    """Plan the backlog, assign T01, and commit the unverified Coder output."""
    bus.publish(Message(
        run_id=bus.run_id,
        sender=Agent.USER,
        to=Agent.PM,
        type=MsgType.REQUIREMENT,
        content=redact_api_key(requirements),
    ))
    product = {"PRODUCT REQUIREMENTS": bus.inbox(Agent.PM)[-1].content}
    pm = LLMAgent(Agent.PM)
    plan = pm.run(product, mode="PLAN")
    _publish_reply(bus, plan, sender=Agent.PM, recipient=Agent.ORCHESTRATOR,
                   kind=MsgType.TASK_ASSIGN)
    backlog = parse_backlog(bus.inbox(Agent.ORCHESTRATOR)[-1].content)
    task = backlog[0]  # The backlog validator requires the first item to be T01.
    if task["needs_ui"]:
        raise ValueError("PM đã gán UI cho T01. Hãy kiểm tra yêu cầu T01 trong requirements.md.")

    files = _project_files(workspace)
    tree = "\n".join(files) or "(empty)"
    brief = pm.run({
        **product,
        "BACKLOG ITEM": json.dumps(task, ensure_ascii=False, indent=2),
        "PROJECT STATE": f"No completed tasks in this run.\nWorkspace files:\n{tree}",
    }, mode="ASSIGN")
    _publish_reply(bus, brief, sender=Agent.PM, recipient=Agent.CODER,
                   kind=MsgType.TASK_ASSIGN, task_id=TASK_ID)

    criteria = cast(list[str], task["acceptance"])
    acceptance = "\n".join(f"- {criterion}" for criterion in criteria)
    sources = "\n\n".join(f"### FILE: {name}\n{content}" for name, content in files.items())
    submission = LLMAgent(Agent.CODER).run({
        **product,
        "TASK BRIEF": bus.inbox(Agent.CODER, TASK_ID)[-1].content,
        "ACCEPTANCE CRITERIA": acceptance,
        "PROJECT FILES": sources or "(empty workspace)",
    })
    output = submission.parsed
    if not isinstance(output, dict):
        raise TypeError("Coder phải trả về nội dung theo khối FILE.")
    artifacts = [f"workspace/{name}" for name in output]
    _publish_reply(bus, submission, sender=Agent.CODER, recipient=Agent.ORCHESTRATOR,
                   kind=MsgType.CODE_SUBMIT, task_id=TASK_ID, artifacts=artifacts)
    missing = REQUIRED_FILES - output.keys() - files.keys()
    if missing:
        raise ValueError("Coder chưa cung cấp các file T01: " + ", ".join(sorted(missing)))
    workspace.write_files(output, agent=Agent.CODER)
    workspace.git_commit(COMMIT_MESSAGE)
    bus.publish(Message(
        run_id=bus.run_id,
        task_id=TASK_ID,
        sender=Agent.ORCHESTRATOR,
        to=Agent.PM,
        type=MsgType.CODE_SUBMIT,
        status="UNVERIFIED",
        content="Đã commit mã T01 trong workspace. Task chưa được kiểm chứng bởi Tester.",
        artifacts=artifacts,
    ))
