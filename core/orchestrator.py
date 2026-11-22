"""Run the M5 task lifecycle through LangGraph and the MessageBus."""

import json
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from agents.base import Agent as LLMAgent
from agents.base import (
    AgentFormatError,
    AgentUsage,
    command_output,
    parse_backlog,
    redact_api_key,
)
from agents.reviewer import Reviewer
from agents.tester import Tester
from core.message_bus import MessageBus
from core.schema import Agent, Message, MsgType
from core.workspace import Workspace

MAX_REVISIONS = 3
SOURCE_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".html", ".css", ".js", ".json", ".sql"}
TEST_FAILURE = re.compile(
    r"^(?:FAILED|ERROR) (tests/[\w/]+\.py(?:::[\w]+)*)\b", re.MULTILINE
)


class RunState(TypedDict):
    """Track the backlog, current task, and its revision state."""

    run_id: str
    backlog: list[dict[str, object]]
    current_task: int
    iteration: int
    statuses: dict[str, str]
    tests_written: bool
    test_rewritten: bool
    test_feedback: str
    blocked_reason: str
    format_failure: AgentUsage | None
    next_step: str


def _source_files(root: Path) -> dict[str, str]:
    """Read the product's current text files for Coder and PM context."""
    files = {}
    for directory, dirs, names in os.walk(root):
        parent = Path(directory)
        dirs[:] = [
            name for name in sorted(dirs)
            if not name.startswith((".", "__"))
            and (parent != root or name.casefold() != "tests")
            and (parent / name).resolve() == parent / name
        ]
        for name in sorted(names):
            path = parent / name
            if path.suffix not in SOURCE_EXTENSIONS and name != ".gitignore":
                continue
            if path.resolve() != path:
                continue
            try:
                files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return files


def _file_blocks(files: Mapping[str, str]) -> str:
    return "\n\n".join(f"### FILE: {name}\n{content}" for name, content in files.items())


class TaskWorkflow:
    """Execute graph nodes while their messages and artifacts stay in the bus."""

    def __init__(self, bus: MessageBus, workspace: Workspace, requirements: str) -> None:
        self.bus = bus
        self.workspace = workspace
        self.publish(Agent.USER, Agent.PM, MsgType.REQUIREMENT, requirements)
        self.product = {"PRODUCT REQUIREMENTS": bus.inbox(Agent.PM)[-1].content}
        self.pm = LLMAgent(Agent.PM)
        self.coder = LLMAgent(Agent.CODER)
        self.reviewer = Reviewer()
        self.tester = Tester()

    def publish(
        self, sender: Agent, to: Agent, kind: MsgType, content: str, *,
        state: RunState | None = None, status: str | None = None,
        usage: AgentUsage | None = None, artifacts: list[str] | None = None,
    ) -> Message:
        """Publish a message with its task, revision, and router metadata."""
        meta = {}
        if usage:
            meta = {
                "model": usage.model, "tokens_in": usage.tokens_in,
                "tokens_out": usage.tokens_out, "duration_ms": usage.duration_ms,
            }
        return self.bus.publish(Message(
            run_id=state["run_id"] if state else self.bus.run_id,
            task_id=self.task_id(state) if state else None,
            iteration=state["iteration"] if state else 0,
            sender=sender, to=to, type=kind, status=status,
            content=redact_api_key(content), artifacts=artifacts or [], meta=meta,
        ))

    def plan(self) -> list[dict[str, object]]:
        """Record and read the PM's ordered backlog."""
        result = self.pm.run(self.product, mode="PLAN")
        self.publish(Agent.PM, Agent.ORCHESTRATOR, MsgType.TASK_ASSIGN, result.text, usage=result)
        return parse_backlog(self.bus.inbox(Agent.ORCHESTRATOR)[-1].content)

    @staticmethod
    def task(state: RunState) -> dict[str, object]:
        return state["backlog"][state["current_task"]]

    def task_id(self, state: RunState) -> str:
        return cast(str, self.task(state)["id"])

    def history(self, state: RunState, kind: MsgType) -> list[Message]:
        return self.bus.history(task_id=self.task_id(state), type=kind)

    def task_sections(self, state: RunState) -> dict[str, str]:
        return {
            **self.product,
            "TASK BRIEF": self.history(state, MsgType.TASK_ASSIGN)[-1].content,
            "ACCEPTANCE CRITERIA": "\n".join(
                f"- {criterion}" for criterion in cast(list[str], self.task(state)["acceptance"])
            ),
        }

    def assign(self, state: RunState) -> dict:
        """Ask PM to brief the next task. M5 goes directly to Coder."""
        self.workspace.begin_task()
        tree = "\n".join(_source_files(self.workspace.root)) or "(empty)"
        status = "\n".join(
            f"{task}: {value}" for task, value in state["statuses"].items()
            if value in {"DONE", "BLOCKED"}
        )
        result = self.pm.run({
            **self.product,
            "BACKLOG ITEM": json.dumps(self.task(state), ensure_ascii=False, indent=2),
            "PROJECT STATE": f"{status or 'No tasks closed in this run.'}\nWorkspace files:\n{tree}",
        }, mode="ASSIGN")
        self.publish(Agent.PM, Agent.CODER, MsgType.TASK_ASSIGN, result.text, state=state, usage=result)
        return {
            "next_step": "code",
            "statuses": {**state["statuses"], self.task_id(state): "IN_PROGRESS"},
        }

    def code(self, state: RunState) -> dict:
        """Read the assignment and any revision request, then apply the submission."""
        sections = self.task_sections(state)
        sources = _source_files(self.workspace.root)
        sections["PROJECT FILES"] = _file_blocks(sources) or "(empty workspace)"
        if state["iteration"]:
            feedback = self.history(state, MsgType.REVISION_REQUEST)[-1].content
            sections["FEEDBACK"] = f"Revision {state['iteration']} of {MAX_REVISIONS}\n{feedback}"
        result = self.coder.run(sections)
        files = cast(dict[str, str], result.parsed)
        self.publish(
            Agent.CODER, Agent.REVIEWER, MsgType.CODE_SUBMIT, result.text, state=state,
            usage=result, artifacts=[f"workspace/{name}" for name in files],
        )
        self.workspace.write_files(files, agent=Agent.CODER)
        return {"next_step": "review"}

    def revise(self, state: RunState, feedback: str) -> dict:
        """Schedule up to three Coder revisions."""
        if state["iteration"] >= MAX_REVISIONS:
            return {"next_step": "blocked", "blocked_reason": "FAILED after 3 revision rounds"}
        updated = {**state, "iteration": state["iteration"] + 1}
        self.publish(
            Agent.ORCHESTRATOR, Agent.CODER, MsgType.REVISION_REQUEST, feedback, state=updated,
        )
        return {"iteration": updated["iteration"], "next_step": "code"}

    def review(self, state: RunState) -> dict:
        """Review the submitted files with Ruff before allowing tests."""
        submission = self.history(state, MsgType.CODE_SUBMIT)[-1]
        previous = [m for m in self.history(state, MsgType.REVIEW_RESULT)
                    if m.status == "REQUEST_CHANGES"]
        result = self.reviewer.review(
            self.task_sections(state), submission.content, self.workspace.run_ruff(include_tests=False),
            previous[-1].content if previous else None,
        )
        verdict = cast(str, result.parsed).removeprefix("VERDICT: ")
        message = self.publish(
            Agent.REVIEWER, Agent.TESTER if verdict == "APPROVE" else Agent.CODER,
            MsgType.REVIEW_RESULT, result.text, state=state, status=verdict, usage=result,
        )
        if verdict == "REQUEST_CHANGES":
            return self.revise(state, message.content)
        return {
            "next_step": "test" if state["tests_written"] else "write_tests",
            "statuses": {**state["statuses"], self.task_id(state): "TESTING"},
        }

    def write_tests(self, state: RunState) -> dict:
        """Provide only acceptance criteria and Tester-owned context."""
        task_id = self.task_id(state)
        test_dir = self.workspace.root / "tests"
        fixture = test_dir / "conftest.py"
        if test_dir.resolve() != test_dir or fixture.resolve() != fixture:
            raise ValueError("Tester paths must be regular workspace paths.")
        create_fixture = not fixture.is_file()
        names = "\n".join(sorted(p.name for p in test_dir.glob("test_*.py")))
        fixture_context = (
            "tests/conftest.py is missing." if create_fixture else
            "tests/conftest.py already exists:\n" + fixture.read_text(encoding="utf-8")
        )
        feedback = state["test_feedback"]
        if feedback:
            current = test_dir / f"test_{task_id}.py"
            if current.resolve() != current:
                raise ValueError("The task test must be a regular workspace file.")
            feedback += "\n\nYour current test file:\n" + current.read_text(encoding="utf-8")
        sections = self.task_sections(state)
        result = self.tester.write_tests(
            task_id=task_id, task=f"{task_id} — {self.task(state)['title']}\n{sections['TASK BRIEF']}",
            acceptance=sections["ACCEPTANCE CRITERIA"], requirements=sections["PRODUCT REQUIREMENTS"],
            existing_tests=f"{names or '(no test files)'}\n\n{fixture_context}",
            create_fixture=create_fixture, feedback=feedback or None,
        )
        files = cast(dict[str, str], result.parsed)
        self.publish(
            Agent.TESTER, Agent.ORCHESTRATOR, MsgType.CODE_SUBMIT, result.text, state=state,
            usage=result, artifacts=[f"workspace/{name}" for name in files],
        )
        self.workspace.write_files(files, agent=Agent.TESTER)
        return {"tests_written": True, "next_step": "test"}

    def test(self, state: RunState) -> dict:
        """Run both pytest commands, preserve their logs, and route their result."""
        task_id = self.task_id(state)
        task_tests = self.workspace.run_pytest(f"tests/test_{task_id}.py")
        full_suite = self.workspace.run_pytest("tests/")
        artifacts = [
            self.save_test_log(state, "task", command_output(task_tests)),
            self.save_test_log(state, "regression", command_output(full_suite)),
        ]
        passed = task_tests.returncode == full_suite.returncode == 0
        try:
            result = self.tester.report(f"{task_id} — {self.task(state)['title']}", task_tests, full_suite)
        except AgentFormatError as error:
            self.publish(
                Agent.ORCHESTRATOR, Agent.PM, MsgType.TEST_REPORT,
                f"RESULT: {'PASS' if passed else 'FAIL'}\n"
                f"Pytest exit codes: task {task_tests.returncode}, regression {full_suite.returncode}.\n"
                f"{error}",
                state=state, status="PASS" if passed else "FAIL", artifacts=artifacts,
            )
            raise
        test_error = not passed and "CAUSE: TEST" in result.text.splitlines()
        recipient = Agent.PM if passed else Agent.ORCHESTRATOR if test_error else Agent.CODER
        message = self.publish(
            Agent.TESTER, recipient, MsgType.TEST_REPORT, result.text, state=state,
            status="PASS" if passed else "FAIL", usage=result, artifacts=artifacts,
        )
        if passed:
            return {"next_step": "done"}
        if not test_error:
            return self.revise(state, message.content)
        if state["test_rewritten"]:
            return {
                "next_step": "blocked",
                "blocked_reason": "FAILED: CAUSE: TEST persisted after one test rewrite.",
            }
        # Pytest tracebacks and REPORT prose may quote application source. Only pass
        # test identifiers and exit codes to WRITE_TESTS, alongside its own test file.
        names = sorted(set(TEST_FAILURE.findall(
            f"{task_tests.stdout}\n{full_suite.stdout}"
        )))
        feedback = (
            f"CAUSE: TEST. Pytest exit codes: task {task_tests.returncode}, "
            f"regression {full_suite.returncode}.\n"
            f"Affected tests: {', '.join(names) or '(no test identifier in the summary)'}.\n"
            "Check the current test for collection, fixture, or assertion errors "
            "and correct it against the acceptance criteria."
        )
        self.publish(
            Agent.ORCHESTRATOR, Agent.TESTER, MsgType.REVISION_REQUEST, feedback, state=state,
        )
        return {
            "test_rewritten": True,
            "test_feedback": self.bus.inbox(Agent.TESTER, task_id)[-1].content,
            "next_step": "write_tests",
        }

    def save_test_log(self, state: RunState, suite: str, output: str) -> str:
        """Save a new log for each invocation, even within the same revision."""
        logs = self.bus.db_path.parent
        directory = logs / "artifacts" / self.task_id(state)
        directory.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=directory,
            prefix=f"{state['run_id']}-r{state['iteration']}-{suite}-", suffix=".log",
        ) as log:
            log.write(output + "\n")
        return f"{logs.name}/{Path(log.name).relative_to(logs.resolve()).as_posix()}"

    def close(self, state: RunState, *, passed: bool) -> dict:
        """Commit green work, or restore failed task edits, then close with PM."""
        task_id = self.task_id(state)
        if passed:
            self.workspace.git_commit(
                f"{task_id}: passed after {state['iteration']} iterations", allow_empty=True,
            )
        self.workspace.finish_task(keep_changes=passed)
        decision = "DONE" if passed else "BLOCKED"
        kind = MsgType.TASK_DONE if passed else MsgType.TASK_BLOCKED
        outcome = f"PASSED after {state['iteration']} iteration(s)" if passed else state["blocked_reason"]
        if state["format_failure"] is not None:
            self.publish(
                Agent.ORCHESTRATOR, Agent.PM, kind, outcome,
                state=state, status=decision, usage=state["format_failure"],
            )
            return self.advance(state, decision)
        for report in (MsgType.REVIEW_RESULT, MsgType.TEST_REPORT):
            messages = self.history(state, report)
            if messages:
                outcome += f"\n\nLast {report.value}:\n{messages[-1].content}"
        try:
            result = self.pm.run({
                "TASK": json.dumps(self.task(state), ensure_ascii=False), "OUTCOME": outcome,
            }, mode="CLOSE", expected_first_line=f"DECISION: {decision}")
        except AgentFormatError as error:
            decision = "BLOCKED"
            self.publish(
                Agent.ORCHESTRATOR, Agent.PM, MsgType.TASK_BLOCKED,
                f"{outcome.splitlines()[0]} — {error}", state=state, status=decision,
                usage=error.usage,
            )
        else:
            content = result.text if passed else f"{outcome.splitlines()[0]}\n{result.text}"
            self.publish(Agent.PM, Agent.ORCHESTRATOR, kind, content,
                         state=state, status=decision, usage=result)
        return self.advance(state, decision)

    def advance(self, state: RunState, decision: str) -> dict:
        """Reset the per-task state after recording the final decision."""
        return {
            "statuses": {**state["statuses"], self.task_id(state): decision},
            "current_task": state["current_task"] + 1,
            "iteration": 0, "tests_written": False, "test_rewritten": False,
            "test_feedback": "", "blocked_reason": "", "format_failure": None,
        }

    def guard(self, node: Callable[[RunState], dict]) -> Callable[[RunState], dict]:
        """Convert invalid agent replies into a blocked task with recorded usage."""
        def execute(state: RunState) -> dict:
            try:
                return node(state)
            except AgentFormatError as error:
                return {
                    "next_step": "blocked", "blocked_reason": f"FAILED: {error}",
                    "format_failure": error.usage,
                }

        return execute


def _next_task(state: RunState) -> str:
    return "assign" if state["current_task"] < len(state["backlog"]) else END


def _next_step(state: RunState) -> str:
    return state["next_step"]


def run_project(
    requirements: str, bus: MessageBus, workspace: Workspace, *,
    only: str | None = None, until: str | None = None,
) -> dict[str, str]:
    """Execute the selected backlog in order and return each task's final status."""
    workflow = TaskWorkflow(bus, workspace, requirements)
    try:
        backlog = workflow.plan()
    except AgentFormatError as error:
        workflow.publish(
            Agent.ORCHESTRATOR, Agent.PM, MsgType.TASK_BLOCKED, str(error),
            status="BLOCKED", usage=error.usage,
        )
        raise
    target = only or until
    if target:
        ids = [task["id"] for task in backlog]
        if target not in ids:
            raise ValueError(f"Task {target} không có trong backlog của PM.")
        index = ids.index(target)
        backlog = backlog[index:index + 1] if only else backlog[:index + 1]

    graph = StateGraph(RunState)
    edges = {
        "assign": ["code"],
        "code": ["review"],
        "review": ["code", "write_tests", "test"],
        "write_tests": ["test"],
        "test": ["code", "write_tests", "done"],
    }
    for name, routes in edges.items():
        graph.add_node(name, workflow.guard(getattr(workflow, name)))
        graph.add_conditional_edges(name, _next_step, [*routes, "blocked"])
    graph.add_node("done", lambda state: workflow.close(state, passed=True))
    graph.add_node("blocked", lambda state: workflow.close(state, passed=False))
    for name in ("done", "blocked"):
        graph.add_conditional_edges(name, _next_task, ["assign", END])
    graph.add_edge(START, "assign")
    initial: RunState = {
        "run_id": bus.run_id, "backlog": backlog, "current_task": 0, "iteration": 0,
        "statuses": {cast(str, task["id"]): "TODO" for task in backlog},
        "tests_written": False, "test_rewritten": False,
        "test_feedback": "", "blocked_reason": "", "format_failure": None, "next_step": "assign",
    }
    try:
        return graph.compile().invoke(
            initial, config={"recursion_limit": len(backlog) * (3 * MAX_REVISIONS + 8)},
        )["statuses"]
    finally:
        workspace.finish_task(keep_changes=False)
