"""Build agent prompts and validate structured text from 9Router."""

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess

from core import llm
from core.schema import Agent as Role
from core.workspace import parse_files

PROMPTS_DIR = Path(__file__).with_name("prompts")
MAX_FORMAT_RETRIES = 2

TASK_SECTIONS = ("TASK BRIEF", "ACCEPTANCE CRITERIA", "PRODUCT REQUIREMENTS")
INPUT_SECTIONS = {
    Role.PM: {
        "PLAN": ("PRODUCT REQUIREMENTS",),
        "ASSIGN": ("BACKLOG ITEM", "PROJECT STATE", "PRODUCT REQUIREMENTS"),
        "CLOSE": ("TASK", "OUTCOME"),
    },
    Role.DESIGNER: {None: (*TASK_SECTIONS, "FEEDBACK?")},
    Role.CODER: {None: (*TASK_SECTIONS, "DESIGN SPEC?", "PROJECT FILES", "FEEDBACK?")},
    Role.REVIEWER: {
        None: (*TASK_SECTIONS, "CHANGED FILES", "RUFF OUTPUT", "PREVIOUS FEEDBACK?")
    },
    Role.TESTER: {
        "WRITE_TESTS": (
            "TASK", "ACCEPTANCE CRITERIA", "PRODUCT REQUIREMENTS", "EXISTING TESTS", "FEEDBACK?"
        ),
        "REPORT": ("TASK", "TASK TESTS", "FULL SUITE"),
    },
}
DESIGN_HEADINGS = (
    "Overview", "Layout", "Components", "Visual style", "States and behavior",
    "Responsive behavior", "Accessibility",
)
ASSIGN_HEADINGS = ("Objective", "Acceptance criteria", "Notes for the team")
REVIEW_ISSUE = re.compile(r"^- \[[^\]\n]+:[1-9][0-9]*\][ \t]+\S", re.MULTILINE)
JSON_BLOCK = re.compile(r"```json[ \t]*\n(.*?)\n```", re.DOTALL)
CODER_NOTES = re.compile(r"(?:NOTE:[^\n]*\n){0,3}")
TASK_ID = re.compile(r"T[0-9]{2}")

ParsedOutput = str | dict[str, str] | list[dict[str, object]]


@dataclass(frozen=True)
class AgentUsage:
    """Router metadata across replies, including format retries."""

    model: str
    tokens_in: int | None
    tokens_out: int | None
    duration_ms: int


@dataclass(frozen=True)
class AgentResult(AgentUsage):
    """Validated text and its parsed representation."""

    text: str
    parsed: ParsedOutput


class AgentFormatError(RuntimeError):
    """The final response remained invalid after the permitted retries."""

    def __init__(self, role: Role, reason: str, usage: AgentUsage) -> None:
        attempts = MAX_FORMAT_RETRIES + 1
        super().__init__(f"{role.value}: đầu ra không hợp lệ sau {attempts} lần gọi. {reason}")
        self.usage = usage


def redact_api_key(text: str) -> str:
    """Hide the configured key in text destined for logs or the terminal."""
    key = os.getenv("ROUTER_API_KEY", "").strip()
    return text.replace(key, "[redacted]") if key else text


def command_output(result: CompletedProcess[str]) -> str:
    """Format the exit code and both output streams for an agent."""
    return redact_api_key(
        f"Exit code: {result.returncode}\n{result.stdout}{result.stderr}"
    ).rstrip()


def _headings(text: str, expected: tuple[str, ...]) -> str:
    actual = re.findall(r"^##[ \t]+(.+)$", text, re.MULTILINE)
    if actual != list(expected):
        raise ValueError("Expected headings in this order: " + ", ".join(expected) + ".")
    return text


def _first_line(text: str, *choices: str) -> str:
    line = text.partition("\n")[0]
    if line not in choices:
        raise ValueError("First line must be " + " or ".join(choices) + ".")
    return line


def parse_backlog(text: str) -> list[dict[str, object]]:
    """Validate the PM's fenced backlog and return the ordered tasks."""
    block = JSON_BLOCK.fullmatch(text.replace("\r\n", "\n").rstrip("\n"))
    if block is None:
        raise ValueError("Expected exactly one fenced json block containing the backlog.")
    try:
        backlog = json.loads(block[1])
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid backlog JSON at line {error.lineno}: {error.msg}.") from None
    if not isinstance(backlog, list) or not 1 <= len(backlog) <= 7:
        raise ValueError("Backlog must be a JSON array of 1 to 7 tasks.")
    for index, task in enumerate(backlog, start=1):
        if not isinstance(task, dict):
            raise TypeError(f"Expected a JSON object at backlog item {index}.")
        acceptance = task.get("acceptance")
        if (
            task.get("id") != f"T{index:02}"
            or not isinstance(task.get("title"), str)
            or not task["title"].strip()
            or not isinstance(task.get("needs_ui"), bool)
            or not isinstance(acceptance, list)
            or not acceptance
            or any(not isinstance(item, str) or not item.strip() for item in acceptance)
        ):
            raise ValueError(
                f"Backlog item {index} needs id T{index:02}, a nonempty title, "
                "boolean needs_ui, and a nonempty array of acceptance criteria."
            )
    return backlog


def _parse_pm(text: str, mode: str | None) -> ParsedOutput:
    if mode == "PLAN":
        return parse_backlog(text)
    if mode == "ASSIGN":
        return _headings(text, ASSIGN_HEADINGS)
    return _first_line(text, "DECISION: DONE", "DECISION: BLOCKED")


def _parse_tester(
    text: str, mode: str | None, task_id: str | None, create_fixture: bool
) -> ParsedOutput:
    if mode == "WRITE_TESTS":
        expected = f"tests/test_{task_id}.py"
        files = parse_files(text, Role.TESTER)
        paths = [expected, "tests/conftest.py"] if create_fixture else [expected]
        if list(files) != paths or text.partition("\n")[0] != f"### FILE: {expected}":
            raise ValueError(
                f"Expected FILE blocks in this order: {', '.join(paths)}."
                if create_fixture else f"Expected only one FILE block for {expected}."
            )
        return files
    result = _first_line(text, "RESULT: PASS", "RESULT: FAIL")
    if result == "RESULT: FAIL":
        causes = [line for line in text.splitlines() if line.startswith("CAUSE:")]
        if causes not in (["CAUSE: CODE"], ["CAUSE: TEST"]):
            raise ValueError("RESULT: FAIL requires exactly one CAUSE: CODE or CAUSE: TEST.")
    return result


def _parse_output(
    role: Role, text: str, mode: str | None, task_id: str | None, create_fixture: bool
) -> ParsedOutput:
    if role == Role.CODER:
        notes = CODER_NOTES.match(text)
        return parse_files(text[notes.end():], Role.CODER)
    if role == Role.REVIEWER:
        verdict = _first_line(text, "VERDICT: APPROVE", "VERDICT: REQUEST_CHANGES")
        if verdict == "VERDICT: REQUEST_CHANGES" and not REVIEW_ISSUE.search(text):
            raise ValueError("REQUEST_CHANGES requires at least one issue like - [file:42] description.")
        return verdict
    if role == Role.DESIGNER:
        return _headings(text, DESIGN_HEADINGS)
    if role == Role.PM:
        return _parse_pm(text, mode)
    return _parse_tester(text, mode, task_id, create_fixture)


class Agent:
    """Use the same prompt and retry logic for any of the five agent roles."""

    def __init__(self, role: Role | str) -> None:
        if role not in INPUT_SECTIONS:
            raise ValueError("Expected one of the five LLM agent roles.")
        self.role = Role(role)
        self.system_prompt = (PROMPTS_DIR / f"{self.role.value}.md").read_text(encoding="utf-8")

    def build_input(self, sections: Mapping[str, str], *, mode: str | None = None) -> str:
        """Render required and optional sections in the order of the system prompt."""
        modes = INPUT_SECTIONS[self.role]
        if mode not in modes:
            valid_modes = ", ".join(name or "(no mode)" for name in modes)
            raise ValueError(f"{self.role.value} requires mode {valid_modes}.")
        headings = modes[mode]
        missing = [heading for heading in headings if not heading.endswith("?") and heading not in sections]
        if missing:
            raise ValueError("Missing input sections: " + ", ".join(missing) + ".")
        if sections.keys() - {heading.removesuffix("?") for heading in headings}:
            raise ValueError(f"Unexpected input section for {self.role.value}.")
        blocks = [f"MODE: {mode}"] if mode else []
        for heading in headings:
            heading = heading.removesuffix("?")
            if heading in sections:
                blocks.append(f"## {heading}\n{sections[heading]}")
        return "\n\n".join(blocks)

    def run(
        self,
        sections: Mapping[str, str],
        *,
        mode: str | None = None,
        task_id: str | None = None,
        create_fixture: bool = False,
        expected_first_line: str | None = None,
    ) -> AgentResult:
        """Call 9Router, retry invalid formats, and return the validated reply."""
        original = self.build_input(sections, mode=mode)
        if self.role == Role.TESTER and mode == "WRITE_TESTS" and not TASK_ID.fullmatch(task_id or ""):
            raise ValueError("WRITE_TESTS requires a task_id such as T01.")
        user_prompt = original
        tokens_in: list[int] = []
        tokens_out: list[int] = []
        duration_ms = 0
        for attempt in range(MAX_FORMAT_RETRIES + 1):
            try:
                reply = llm.chat(self.role.value, self.system_prompt, user_prompt)
            except llm.LLMError as error:
                raise llm.LLMError(redact_api_key(str(error))) from None
            if reply.tokens_in is not None:
                tokens_in.append(reply.tokens_in)
            if reply.tokens_out is not None:
                tokens_out.append(reply.tokens_out)
            duration_ms += reply.duration_ms
            usage = AgentUsage(
                redact_api_key(reply.model),
                sum(tokens_in) if tokens_in else None,
                sum(tokens_out) if tokens_out else None,
                duration_ms,
            )
            normalized = reply.text.replace("\r\n", "\n").rstrip("\n")
            try:
                parsed = _parse_output(self.role, normalized, mode, task_id, create_fixture)
                if expected_first_line is not None:
                    _first_line(normalized, expected_first_line)
            except (ValueError, TypeError) as error:
                reason = redact_api_key(str(error))
                if attempt == MAX_FORMAT_RETRIES:
                    raise AgentFormatError(self.role, reason, usage) from None
                user_prompt = (
                    f"{original}\n\nĐầu ra trước không hợp lệ vì: {reason.removesuffix('.')}."
                    " Hãy trả lại đúng định dạng."
                )
            else:
                return AgentResult(
                    usage.model, usage.tokens_in, usage.tokens_out, usage.duration_ms, reply.text, parsed
                )
