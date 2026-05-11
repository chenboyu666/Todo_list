from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from floating_todo.domain import Task

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryStore:
    def __init__(self, tasks: list[Task]) -> None:
        self._tasks = tasks

    def load_tasks(self) -> list[Task]:
        return list(self._tasks)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app


def make_task(
    title: str,
    *,
    task_id: str | None = None,
    priority: str = "P1",
    progress: int = 25,
    effort_minutes: int = 45,
    deadline_delta: timedelta | None = timedelta(hours=2),
    status: str = "active",
) -> Task:
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id=task_id or title,
        title=title,
        priority=priority,
        effort_minutes=effort_minutes,
        deadline=now + deadline_delta if deadline_delta is not None else None,
        progress=progress,
        status=status,
        created_at=now,
        updated_at=now,
        completed_at=now if status == "done" else None,
        notes="",
    )


def test_main_window_constructs_with_empty_state(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]))

    assert window.windowTitle() == "FloatingTodo"
    assert window.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.minimumWidth() >= 410
    assert not window.empty_state_widget.isHidden()
    assert window.empty_state_label.text() == "没有进行中的任务"
    assert window.empty_state_hint_label.text() == "点击新增任务开始"
    assert window.focus_progress.value() == 0
    assert window.active_count_label.text() == "0"
    assert window.today_completion_label.text() == "0%"

    window.close()


def test_refresh_renders_focus_summary_and_task_rows(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [
        make_task("完成归档", status="done", progress=100),
        make_task("低优先任务", priority="P3", progress=10, effort_minutes=20),
        make_task("关键交付", priority="P1", progress=60, effort_minutes=90),
    ]
    window = MainWindow(MemoryStore(tasks))

    assert window.empty_state_widget.isHidden()
    assert window.active_count_label.text() == "2"
    assert window.today_completion_label.text() == "33%"
    assert window.focus_title_label.text() == "关键交付"
    assert window.focus_meta_label.text() == "P1 · 工作量 90 min"
    assert window.focus_progress.value() == 60
    assert window.task_list_layout.count() == 2

    row_labels = window.task_rows_container.findChildren(QLabel)
    row_text = "\n".join(label.text() for label in row_labels)
    assert "关键交付" in row_text
    assert "低优先任务" in row_text
    assert "截止" in row_text
    assert "60%" in row_text

    window.close()
