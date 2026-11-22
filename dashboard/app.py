"""Monitor agent runs in Streamlit using the read-only dashboard data layer."""

import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from html import escape
from pathlib import PurePosixPath

import streamlit as st

from core.schema import Agent, Message, MsgType
from core.transcript import agent_label
from dashboard.data import (
    KANBAN_COLUMNS,
    RunStats,
    build_kanban,
    compute_stats,
    list_runs,
    load_artifact,
    load_messages,
    load_workspace_file,
)

AGENT_STYLE = {
    Agent.USER: ("#334155", "#F1F5F9"),
    Agent.PM: ("#155E75", "#CFFAFE"),
    Agent.DESIGNER: ("#86198F", "#FAE8FF"),
    Agent.CODER: ("#166534", "#DCFCE7"),
    Agent.REVIEWER: ("#854D0E", "#FEF9C3"),
    Agent.TESTER: ("#1E40AF", "#DBEAFE"),
    Agent.ORCHESTRATOR: ("#991B1B", "#FEE2E2"),
}
STATUS_COLOR = dict(zip(KANBAN_COLUMNS, ("gray", "orange", "blue", "green", "red"), strict=True))
CODE_LANGUAGES = {".py": "python", ".html": "html", ".md": "markdown", ".js": "javascript",
                  ".css": "css", ".json": "json", ".ini": "ini", ".toml": "toml"}


def _stats(stats: RunStats) -> None:
    messages, tokens, duration, revisions = st.columns(4)
    messages.metric("Tin nhắn", stats.total_messages)
    tokens.metric("Tổng token", stats.tokens_in + stats.tokens_out)
    duration.metric("Thời gian chạy", str(timedelta(seconds=int(stats.duration_seconds))))
    revisions.metric("Tổng vòng sửa", sum(stats.revisions_by_task.values()))
    st.caption(f"Token vào {stats.tokens_in:,} · Token ra {stats.tokens_out:,}")
    if stats.messages_by_agent:
        counts = " · ".join(f"{agent_label(agent)} {count}" for agent, count in stats.messages_by_agent.items())
        st.caption(counts)


def _kanban(tasks: dict[str, str]) -> None:
    st.subheader("Kanban")
    for column, status in zip(st.columns(5), KANBAN_COLUMNS, strict=True):
        with column.container(border=True):
            st.markdown(f":{STATUS_COLOR[status]}[**{status}**]")
            assigned = [task_id for task_id, state in tasks.items() if state == status]
            if assigned:
                for task_id in assigned:
                    st.text(task_id)
            else:
                st.caption("—")


def _timeline(messages: Sequence[Message], task_ids: list[str], run_id: str) -> None:
    st.subheader("Timeline")
    tasks, agents, types = st.columns(3)
    task_id = tasks.selectbox("Lọc theo task", [None, *task_ids], format_func=lambda value: value or "Tất cả",
                              key=f"timeline-task:{run_id}")
    sender = agents.selectbox("Lọc theo agent", [None, *Agent],
                              format_func=lambda value: agent_label(value) if value else "Tất cả",
                              key=f"timeline-agent:{run_id}")
    kind = types.selectbox("Lọc theo loại tin nhắn", [None, *MsgType],
                           format_func=lambda value: value.value if value else "Tất cả",
                           key=f"timeline-type:{run_id}")
    filtered = [message for message in messages if (task_id is None or message.task_id == task_id)
                and (sender is None or message.sender == sender) and (kind is None or message.type == kind)]
    st.caption(f"Hiển thị {len(filtered)} / {len(messages)} tin nhắn")
    if not filtered:
        st.info("Không có tin nhắn khớp bộ lọc.")
        return
    for message in filtered:
        _chat_message(message)


def _chat_message(message: Message) -> None:
    time = datetime.fromisoformat(message.timestamp).strftime("%H:%M:%S")
    details = [message.task_id or "—", f"vòng {message.iteration}", message.type.value]
    if message.status:
        details.append(message.status)
    sender = agent_label(message.sender)
    label = f"[{time}] {sender} → {agent_label(message.to)} ({', '.join(details)})"
    preview = " ".join(message.content.split())
    if len(preview) > 160:
        preview = preview[:159].rstrip() + "…"
    foreground, background = AGENT_STYLE[message.sender]
    with st.container(border=True):
        st.html(
            f'<strong style="background:{background};color:{foreground};padding:0.15rem 0.4rem;'
            f'border-radius:0.3rem">{escape(label)}</strong><p>{escape(preview)}</p>'
        )
        with st.expander("Xem đầy đủ"):
            st.code(message.content, language=None, wrap_lines=True)


def _attachments(messages: Sequence[Message], kind: MsgType, prefix: str) -> list[str]:
    return list(dict.fromkeys(
        path.removeprefix(prefix)
        for message in messages if message.type == kind
        for path in message.artifacts if path.startswith(prefix)
    ))


def _show_files(names: list[str], reader: Callable[[str], str | None], empty: str) -> None:
    if not names:
        st.caption(empty)
    for name in names:
        with st.expander(name):
            try:
                content = reader(name)
            except (OSError, UnicodeError, ValueError):
                st.warning("Không thể đọc tệp này.")
                continue
            if content is None:
                st.caption("Tệp không còn ở vị trí đã ghi trong tin nhắn.")
            else:
                st.code(content, language=CODE_LANGUAGES.get(PurePosixPath(name).suffix),
                        wrap_lines=True, height=340)


def _task_details(
    messages: Sequence[Message], tasks: dict[str, str], stats: RunStats, run_id: str,
) -> None:
    st.subheader("Chi tiết task")
    task_id = st.selectbox("Chọn task để xem", [None, *tasks],
                           format_func=lambda value: value or "Chọn task", key=f"detail-task:{run_id}")
    if task_id is None:
        return
    st.write(f"**{task_id} · {tasks[task_id]}** · {stats.revisions_by_task.get(task_id, 0)} vòng sửa")
    history = [message for message in messages if message.task_id == task_id]
    code, tests, design = st.tabs(["Code", "Log pytest", "Thiết kế"])
    artifact_prefix = f"logs/artifacts/{task_id}/"

    def read_artifact(name: str) -> str | None:
        return load_artifact(task_id, name)

    with code:
        st.caption("Nội dung tệp đang có trong workspace. Bản nộp gốc nằm trong timeline của run.")
        _show_files(_attachments(history, MsgType.CODE_SUBMIT, "workspace/"),
                    load_workspace_file, "Task chưa gửi tệp code.")
    with tests:
        _show_files(_attachments(history, MsgType.TEST_REPORT, artifact_prefix),
                    read_artifact, "Task chưa có log pytest.")
    with design:
        paths = _attachments(history, MsgType.DESIGN_SPEC, artifact_prefix)
        specs = [message for message in history if message.type == MsgType.DESIGN_SPEC]
        if specs:
            name = paths[-1] if paths else "design_spec.md"
            try:
                content = read_artifact(name) if paths else None
            except (OSError, UnicodeError, ValueError):
                content = None
            st.caption(name)
            st.code(content if content is not None else specs[-1].content, language="markdown", wrap_lines=True)
        else:
            st.caption("Task chưa có bản thiết kế.")


@st.fragment(run_every=2)
def _live_view(known_runs: list[str], selected: str | None) -> None:
    """Refresh the active run and rebuild the sidebar when the list changes."""
    try:
        runs = list_runs()
        if runs != known_runs:
            st.rerun()
        if not runs:
            st.info("Chưa có tin nhắn. Chạy `python -m core.run` để tạo log cho dashboard.")
            return
        run_id = selected or runs[0]
        messages = load_messages(run_id)
    except sqlite3.Error:
        st.warning("Tạm thời không đọc được `logs/messages.db`. Dashboard sẽ thử lại sau 2 giây.")
        return
    st.caption(f"Run {run_id} · Giờ UTC · Tự làm mới mỗi 2 giây")
    tasks = build_kanban(messages)
    stats = compute_stats(messages)
    _stats(stats)
    _kanban(tasks)
    _task_details(messages, tasks, stats, run_id)
    _timeline(messages, list(tasks), run_id)


def main() -> None:
    """Display the run selector and dashboard."""
    st.set_page_config(page_title="Theo dõi AI Agent", layout="wide")
    st.title("Theo dõi AI Agent")
    try:
        runs = list_runs()
    except sqlite3.Error:
        runs = []
    selected = st.sidebar.selectbox("Chọn run", [None, *runs],
                                    format_func=lambda value: value or "Run mới nhất (tự theo dõi)",
                                    key="selected-run")
    _live_view(runs, selected)


if __name__ == "__main__":
    main()
