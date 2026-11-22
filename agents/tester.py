"""Write acceptance tests and interpret real pytest output."""

from subprocess import CompletedProcess

from agents.base import Agent, AgentResult, command_output
from core.schema import Agent as Role


class Tester(Agent):
    """Use task requirements and test-side context to write tests."""

    def __init__(self) -> None:
        super().__init__(Role.TESTER)

    def write_tests(
        self, *, task_id: str, task: str, acceptance: str, requirements: str,
        existing_tests: str, create_fixture: bool, feedback: str | None = None,
    ) -> AgentResult:
        sections = {
            "TASK": task,
            "ACCEPTANCE CRITERIA": acceptance,
            "PRODUCT REQUIREMENTS": requirements,
            "EXISTING TESTS": existing_tests,
        }
        if feedback:
            sections["FEEDBACK"] = feedback
        return self.run(
            sections, mode="WRITE_TESTS", task_id=task_id, create_fixture=create_fixture,
        )

    def report(
        self, task: str, task_tests: CompletedProcess[str], full_suite: CompletedProcess[str],
    ) -> AgentResult:
        status = "PASS" if task_tests.returncode == full_suite.returncode == 0 else "FAIL"
        return self.run({
            "TASK": task,
            "TASK TESTS": command_output(task_tests),
            "FULL SUITE": command_output(full_suite),
        }, mode="REPORT", expected_first_line=f"RESULT: {status}")
