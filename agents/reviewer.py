"""Combine a code review with Ruff's actual result."""

import re
from collections.abc import Mapping
from dataclasses import replace
from subprocess import CompletedProcess

from agents.base import Agent, AgentResult, command_output
from core.schema import Agent as Role


class Reviewer(Agent):
    """Review the task's changes using the real lint result."""

    def __init__(self) -> None:
        super().__init__(Role.REVIEWER)

    def review(
        self, task: Mapping[str, str], changes: str, ruff: CompletedProcess[str],
        previous_feedback: str | None = None,
    ) -> AgentResult:
        sections = {**task, "CHANGED FILES": changes, "RUFF OUTPUT": command_output(ruff)}
        if previous_feedback:
            sections["PREVIOUS FEEDBACK"] = previous_feedback
        result = self.run(sections)
        if ruff.returncode != 0 and result.parsed == "VERDICT: APPROVE":
            verdict = "VERDICT: REQUEST_CHANGES"
            location = re.search(r"-->\s+(.+:\d+):\d+\s*$", sections["RUFF OUTPUT"], re.MULTILINE)
            issue = f"- [{location[1] if location else '.:1'}] Resolve the Ruff failure below."
            return replace(
                result, text=f"{verdict}\n{issue}\n{sections['RUFF OUTPUT']}", parsed=verdict,
            )
        return result
