"""Exercise all five agents once against the configured 9Router."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from rich.console import Console

# Allow direct invocation from the repository without an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.base import Agent, AgentFormatError, AgentResult, redact_api_key
from core import llm
from core.workspace import Workspace

CONSOLE = Console(markup=False, highlight=False)
HELLO_FILE = "hello.py"
HELLO_SOURCE = 'def hello() -> str:\n    return "Hello"\n'
HEALTH_REQUIREMENTS = 'GET /health returns HTTP 200 and {"status": "ok"}.'
HELLO_SECTIONS = {
    "TASK BRIEF": "Provide a function named hello in hello.py.",
    "ACCEPTANCE CRITERIA": "Calling hello() returns the case-sensitive string Hello.",
    "PRODUCT REQUIREMENTS": "Use one Python 3.11 source file and no dependencies.",
}


def show_usage(tokens_in: int | None, tokens_out: int | None) -> str:
    """Format token counts even when the router omits usage."""
    incoming = "không có" if tokens_in is None else str(tokens_in)
    outgoing = "không có" if tokens_out is None else str(tokens_out)
    return f"token vào/ra: {incoming}/{outgoing}"


def run_agent(
    role: str, sections: dict[str, str], *, mode: str | None = None, task_id: str | None = None
) -> AgentResult | None:
    """Print a reply or error and allow the remaining agents to run."""
    label = role.upper()
    try:
        result = Agent(role).run(sections, mode=mode, task_id=task_id)
    except AgentFormatError as error:
        usage = show_usage(error.usage.tokens_in, error.usage.tokens_out)
        CONSOLE.print(redact_api_key(f"{label} KHÔNG ĐẠT ({usage}): {error}"))
        return None
    except llm.LLMError as error:
        CONSOLE.print(redact_api_key(f"{label} KHÔNG ĐẠT ({show_usage(None, None)}): {error}"))
        return None
    usage = show_usage(result.tokens_in, result.tokens_out)
    if role == "coder" and isinstance(result.parsed, dict) and set(result.parsed) != {HELLO_FILE}:
        CONSOLE.print(f"{label} KHÔNG ĐẠT ({usage}): cần đúng một file {HELLO_FILE}.")
        return None
    CONSOLE.print(redact_api_key(f"{label} ĐẠT ({usage})\n{result.text}\n"))
    return result


def main() -> int:
    """Call each role with an independent brief and print the results."""
    pm = run_agent("pm", {"PRODUCT REQUIREMENTS": HEALTH_REQUIREMENTS}, mode="PLAN")
    designer = run_agent("designer", {
        "TASK BRIEF": "Design a one-column Vietnamese To-do page.",
        "ACCEPTANCE CRITERIA": "Include task-form, task-input, task-list and a Thêm button.",
        "PRODUCT REQUIREMENTS": "Use system fonts and support widths below 600px.",
    })
    coder = run_agent("coder", {**HELLO_SECTIONS, "PROJECT FILES": "(empty)"})

    if coder is None:
        CONSOLE.print("Reviewer sẽ dùng hello.py mẫu.")
    source = coder.parsed[HELLO_FILE] if coder and isinstance(coder.parsed, dict) else HELLO_SOURCE
    with TemporaryDirectory(prefix="qlda-smoke-") as directory:
        workspace = Workspace(directory)
        workspace.write_files({HELLO_FILE: source})
        lint = workspace.run_ruff()
        reviewer = run_agent("reviewer", {
            **HELLO_SECTIONS,
            "CHANGED FILES": f"### FILE: {HELLO_FILE}\n```python\n{source}```",
            "RUFF OUTPUT": f"Exit code: {lint.returncode}\n{lint.stdout}{lint.stderr}",
        })

    tester = run_agent("tester", {
        "TASK": "T01 — Check the health endpoint.",
        "ACCEPTANCE CRITERIA": "Assert the status code and the exact JSON response.",
        "PRODUCT REQUIREMENTS": HEALTH_REQUIREMENTS,
        "EXISTING TESTS": "There is a shared client fixture for the FastAPI app.",
    }, mode="WRITE_TESTS", task_id="T01")
    return 0 if all((pm, designer, coder, reviewer, tester)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
