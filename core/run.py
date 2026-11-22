"""Check 9Router and run milestone M4 from the command line."""

import argparse
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CalledProcessError

from rich.console import Console

from agents.base import AgentFormatError, redact_api_key
from core.llm import LLMError, check_router
from core.message_bus import MessageBus
from core.orchestrator import TASK_ID, run_t01
from core.workspace import Workspace


def main(argv: Sequence[str] | None = None) -> int:
    """Run T01 after a successful router connectivity check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement", type=Path, default=Path("requirements.md"))
    parser.add_argument("--only", choices=[TASK_ID], default=TASK_ID)
    args = parser.parse_args(argv)

    errors = Console(stderr=True)
    try:
        check_router()
    except LLMError as error:
        errors.print(f"{error}\nHãy chạy 9Router và kiểm tra .env.", markup=False)
        return 1

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    Console().print(f"Run ID: {run_id}")
    try:
        requirements = args.requirement.read_text(encoding="utf-8")
        run_t01(requirements, MessageBus(run_id), Workspace())
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
