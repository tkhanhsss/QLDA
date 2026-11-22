"""Check 9Router and run the M5 task workflow from the command line."""

import argparse
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError
from uuid import uuid4

from rich.console import Console

from agents.base import AgentFormatError, redact_api_key
from core.llm import LLMError, check_router
from core.message_bus import MessageBus
from core.orchestrator import run_project
from core.workspace import Workspace


def _task_id(value: str) -> str:
    """Accept T1 and T01 and normalize them to the backlog's IDs."""
    if value.upper() not in {f"T{n}" for n in range(1, 8)} | {f"T{n:02}" for n in range(1, 8)}:
        raise argparse.ArgumentTypeError("Dùng ID task từ T01 đến T07.")
    return f"T{int(value[1:]):02}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the selected tasks after a successful router connectivity check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement", type=Path, default=Path("requirements.md"))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--only", type=_task_id, help="Chạy một task (mặc định T01).")
    selection.add_argument("--until", type=_task_id, help="Chạy từ T01 đến task này.")
    args = parser.parse_args(argv)

    errors = Console(stderr=True)
    try:
        check_router()
    except LLMError as error:
        errors.print(f"{error}\nHãy chạy 9Router và kiểm tra .env.", markup=False)
        return 1

    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S.%fZ}-{uuid4().hex[:8]}"
    Console().print(f"Run ID: {run_id}")
    try:
        requirements = args.requirement.read_text(encoding="utf-8")
        statuses = run_project(
            requirements, MessageBus(run_id), Workspace(),
            only=args.only or (None if args.until else "T01"), until=args.until,
        )
    except LLMError as error:
        errors.print(
            f"{error}\nHãy kiểm tra tên model, API key và hạn mức trong dashboard 9Router.",
            markup=False,
        )
        return 1
    except CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        errors.print(f"Git trong workspace thất bại.\n{redact_api_key(detail)}", markup=False)
        return 1
    except (AgentFormatError, OSError, ValueError, sqlite3.Error) as error:
        errors.print(redact_api_key(str(error)), markup=False)
        return 1
    for task, status in statuses.items():
        Console().print(f"{task} {status}")
    return int("BLOCKED" in statuses.values())


if __name__ == "__main__":
    raise SystemExit(main())
