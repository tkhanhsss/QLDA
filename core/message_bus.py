"""Persist and query messages shared by the agents in a run."""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from core.schema import Agent, Message, MsgType
from core.transcript import agent_label, format_entry

AGENT_COLORS = {
    Agent.USER: "white",
    Agent.PM: "cyan",
    Agent.DESIGNER: "magenta",
    Agent.CODER: "green",
    Agent.REVIEWER: "yellow",
    Agent.TESTER: "blue",
    Agent.ORCHESTRATOR: "red",
}


class MessageBus:
    """Keep a run's messages in SQLite, JSONL, and a Markdown transcript."""

    def __init__(self, run_id: str, logs_dir: str | Path = "logs") -> None:
        self.run_id = run_id
        directory = Path(logs_dir)
        directory.mkdir(parents=True, exist_ok=True)
        self.db_path = directory / "messages.db"
        self.jsonl_path = directory / "messages.jsonl"
        self.transcript_path = directory / "transcript.md"
        self.console = Console()
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    task_id TEXT,
                    iteration INTEGER NOT NULL,
                    sender TEXT NOT NULL,
                    "to" TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT,
                    content TEXT NOT NULL,
                    artifacts TEXT NOT NULL,
                    meta TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def publish(self, msg: Message) -> Message:
        """Assign an ID and UTC timestamp, then write the message to all logs."""
        if msg.run_id != self.run_id:
            raise ValueError("Message run_id must match the MessageBus run_id.")

        values = msg.model_dump(mode="json", exclude={"id"})
        values["artifacts"] = json.dumps(values["artifacts"], ensure_ascii=False)
        values["meta"] = json.dumps(values["meta"], ensure_ascii=False)
        with closing(self._connect()) as connection, connection:
            # Serialize file appends and exports through the SQLite writer lock.
            connection.execute("BEGIN IMMEDIATE")
            values["timestamp"] = datetime.now(UTC).isoformat()
            cursor = connection.execute(
                """
                INSERT INTO messages
                    (run_id, timestamp, task_id, iteration, sender, "to", type,
                     status, content, artifacts, meta)
                VALUES
                    (:run_id, :timestamp, :task_id, :iteration, :sender, :to, :type,
                     :status, :content, :artifacts, :meta)
                """,
                values,
            )
            published = msg.model_copy(
                update={"id": cursor.lastrowid, "timestamp": values["timestamp"]}
            )
            entry = format_entry(published)
            json_line = (published.model_dump_json(by_alias=True) + "\n").encode(
                "utf-8"
            )
            transcript_line = (entry + "\n").encode("utf-8")
            with (
                self.jsonl_path.open("ab", buffering=0) as jsonl,
                self.transcript_path.open("ab", buffering=0) as transcript,
            ):
                jsonl_start = jsonl.tell()
                transcript_start = transcript.tell()
                try:
                    if jsonl.write(json_line) != len(json_line):
                        raise OSError(
                            "Could not write the full message to messages.jsonl."
                        )
                    if transcript.write(transcript_line) != len(transcript_line):
                        raise OSError(
                            "Could not write the full message to transcript.md."
                        )
                    connection.commit()
                except BaseException:
                    jsonl.truncate(jsonl_start)
                    transcript.truncate(transcript_start)
                    raise

        route = f"{agent_label(published.sender)} → {agent_label(published.to)}"
        self.console.print(
            entry.replace(f"**{route}**", route, 1),
            style=AGENT_COLORS[published.sender],
            markup=False,
            highlight=False,
        )
        return published

    def inbox(self, agent: Agent, task_id: str | None = None) -> list[Message]:
        """Return messages addressed to an agent in publication order."""
        return self._query(task_id=task_id, recipient=agent)

    def history(
        self,
        task_id: str | None = None,
        sender: Agent | None = None,
        type: MsgType | None = None,
    ) -> list[Message]:
        """Return this run's messages matching all supplied filters."""
        return self._query(task_id=task_id, sender=sender, msg_type=type)

    def _query(
        self,
        task_id: str | None = None,
        sender: Agent | None = None,
        msg_type: MsgType | None = None,
        recipient: Agent | None = None,
    ) -> list[Message]:
        filters = {
            '"to"': recipient,
            "task_id": task_id,
            "sender": sender,
            "type": msg_type,
        }
        conditions = ["run_id = ?"]
        parameters = [self.run_id]
        for column, value in filters.items():
            if value is not None:
                conditions.append(f"{column} = ?")
                parameters.append(value)
        where = " AND ".join(conditions)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                f"SELECT * FROM messages WHERE {where} ORDER BY id", parameters
            )
            return [_row_to_message(row) for row in rows]

    def export_transcript(self) -> str:
        """Rebuild the shared transcript from SQLite and return its text."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM messages ORDER BY id")
            text = "".join(format_entry(_row_to_message(row)) + "\n" for row in rows)
            temporary_path = self.transcript_path.with_suffix(".tmp")
            try:
                temporary_path.write_text(text, encoding="utf-8", newline="\n")
                temporary_path.replace(self.transcript_path)
            finally:
                temporary_path.unlink(missing_ok=True)
        return text


def _row_to_message(row: sqlite3.Row) -> Message:
    values = dict(row)
    values["artifacts"] = json.loads(values["artifacts"])
    values["meta"] = json.loads(values["meta"])
    return Message.model_validate(values)
