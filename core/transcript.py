"""Format published messages for the Markdown transcript."""

import re
from datetime import datetime

from core.schema import Agent, Message


def agent_label(agent: Agent) -> str:
    """Return a readable agent name, preserving acronyms."""
    return "PM" if agent == Agent.PM else agent.value.capitalize()


def format_entry(message: Message) -> str:
    """Render a message as one Markdown line with a short preview."""
    time = datetime.fromisoformat(message.timestamp).strftime("%H:%M:%S")
    details = [message.task_id or "-", f"vòng {message.iteration}", message.type.value]
    if message.status:
        details.append(message.status)

    preview = " ".join(message.content.split())
    if len(preview) > 160:
        preview = preview[:159].rstrip() + "…"
    preview = re.sub(r"([\\`*_\[\]<>~&])", r"\\\1", preview)
    route = f"{agent_label(message.sender)} → {agent_label(message.to)}"
    return f"[{time}] **{route}** ({', '.join(details)}): {preview}"
