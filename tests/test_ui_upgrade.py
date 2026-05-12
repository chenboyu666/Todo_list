from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os

import pytest
from PySide6.QtCore import QDateTime, QTimeZone, Qt
from PySide6.QtWidgets import QApplication

from floating_todo.domain import Task
from floating_todo.settings import AppSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryStore:
    def __init__(self, tasks: list[Task]) -> None:
        self._tasks = list(tasks)
        self.saved_tasks: list[Task] | None = None

    def load_tasks(self) -> list[Task]:
        return list(self._tasks)

    def save_tasks(self, tasks: list[Task]) -> None:
        self.saved_tasks = list(tasks)
        self._tasks = list(tasks)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def make_task(title: str, task_id: str, *, status: str = "active") -> Task:
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id=task_id,
        title=title,
        priority="P1",
        effort_minutes=30,
        deadline=now,
        progress=10,
        status=status,
        created_at=now,
        updated_at=now,
        completed_at=now if status == "done" else None,
        notes="",
        notification_state={},
    )


def test_window_is_frameless_and_focus_task_can_be_selected(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [make_task("普通任务", "task-1"), make_task("拖入进行中", "task-2")]
    window = MainWindow(MemoryStore(tasks), AppSettings(), tmp_path / "settings.json")

    assert window.windowFlags() & Qt.FramelessWindowHint

    window.set_focus_task("task-2")

    assert window.settings.focus_task_id == "task-2"
    assert window.focus_title_label.text() == "拖入进行中"

    window.close()


def test_progress_slider_updates_task_progress(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    task = make_task("拖动进度", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    window.focus_progress.setValue(64)

    assert store.saved_tasks is not None
    assert store.saved_tasks[0].progress == 64

    window.close()


def test_focus_progress_slider_updates_auto_selected_task(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    task = make_task("自动聚焦进度", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(), tmp_path / "settings.json")

    window.focus_progress.setValue(72)

    assert store.saved_tasks is not None
    assert store.saved_tasks[0].progress == 72

    window.close()


def test_deadline_minute_selector_supports_every_minute(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    deadline = datetime(2026, 5, 12, 10, 37, tzinfo=timezone.utc)
    dialog.deadline_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(deadline.timestamp()), QTimeZone.utc()))

    assert dialog.deadline_minute_input.count() == 60
    assert dialog.deadline_minute_input.itemText(37) == "37"
    assert dialog.build_task().deadline == deadline

    dialog.close()


def test_background_settings_are_applied(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    image_path = tmp_path / "background.png"
    image_path.write_bytes(b"not-a-real-image-but-path-exists")
    settings = AppSettings(background_enabled=True, background_image_path=str(image_path), background_overlay=0.55)
    window = MainWindow(MemoryStore([]), settings, tmp_path / "settings.json")

    assert "border-image" in window.root_widget.styleSheet()
    assert image_path.as_posix() in window.root_widget.styleSheet()

    window.close()


def test_history_window_saves_reflection(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = make_task("完成任务", "done-1", status="done")
    store = MemoryStore([task])
    window = HistoryWindow([task], store)

    window.save_reflection("done-1", "这次要提前拆小任务")

    assert store.saved_tasks == [replace(task, reflection="这次要提前拆小任务")]

    window.close()
