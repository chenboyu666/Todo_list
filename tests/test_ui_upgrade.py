from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os

import pytest
from PySide6.QtCore import QDateTime, QTimeZone, Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit

from floating_todo.domain import Task
from floating_todo.settings import AppSettings
from floating_todo.ui.controls import NoWheelSlider

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
    from floating_todo.ui.main_window import CornerResizeGrip, MainWindow

    tasks = [make_task("普通任务", "task-1"), make_task("拖入进行中", "task-2")]
    window = MainWindow(MemoryStore(tasks), AppSettings(), tmp_path / "settings.json")

    assert window.windowFlags() & Qt.FramelessWindowHint
    assert isinstance(window.resize_grip, CornerResizeGrip)
    assert window.resize_grip.toolTip() == "拖动调整窗口大小"

    window.set_focus_task("task-2")

    assert window.settings.focus_task_id == "task-2"
    assert window.focus_title_label.text() == "拖入进行中"

    window.close()


def test_progress_slider_updates_task_progress(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    task = make_task("拖动进度", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    assert isinstance(window.focus_progress, NoWheelSlider)

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


def test_progress_slider_drag_defers_save_until_release(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    task = make_task("连续拖动进度", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    window.focus_progress.setSliderDown(True)
    window.focus_progress.setValue(43)

    assert store.saved_tasks is None

    window.focus_progress.setSliderDown(False)
    window.commit_focus_progress()

    assert store.saved_tasks is not None
    assert store.saved_tasks[0].progress == 43

    window.close()


def test_task_rows_show_deadline_date_urgency_and_focus_button(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow, TaskDragHandle

    task = make_task("临近任务", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(), tmp_path / "settings.json")

    row_labels = "\n".join(label.text() for label in window.task_rows_container.findChildren(QLabel))
    button_text = "\n".join(button.text() for button in window.task_rows_container.findChildren(QPushButton))
    button_tooltips = "\n".join(button.toolTip() for button in window.task_rows_container.findChildren(QPushButton))

    assert "截止" in row_labels
    assert "2026-" in row_labels
    assert "已超时" in row_labels
    assert "进行中" in button_text
    assert isinstance(window.task_rows_container.findChildren(NoWheelSlider)[0], NoWheelSlider)
    assert "设为当前置顶任务" in button_tooltips
    assert window.focus_card.toolTip() == "把任务拖到这里设为进行中"
    drag_handles = window.task_rows_container.findChildren(TaskDragHandle)
    assert drag_handles
    assert drag_handles[0].toolTip() == "拖到上方设为进行中"

    window.close()


def test_set_focus_task_button_can_replace_current_task(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [make_task("当前", "task-1"), make_task("后面的任务", "task-2")]
    store = MemoryStore(tasks)
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    buttons = window.task_rows_container.findChildren(QPushButton)
    focus_button = next(button for button in buttons if button.text() == "置顶")
    focus_button.click()

    assert window.settings.focus_task_id == "task-2"
    assert window.focus_title_label.text() == "后面的任务"

    window.close()


def test_task_drag_defers_refresh_until_drag_finishes(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [make_task("当前", "task-1"), make_task("后面的任务", "task-2")]
    store = MemoryStore(tasks)
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")
    first_row = window.task_list_layout.itemAt(0).widget()

    window.begin_task_drag()
    window.set_focus_task("task-2")

    assert window.is_task_drag_active is True
    assert window.task_list_layout.itemAt(0).widget() is first_row
    assert window.focus_title_label.text() == "当前"

    window.end_task_drag()

    assert window.is_task_drag_active is False
    assert window.focus_title_label.text() == "后面的任务"

    window.close()


def test_deadline_minute_selector_supports_every_minute(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    deadline = datetime(2026, 5, 12, 10, 37, tzinfo=timezone.utc)
    dialog.deadline_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(deadline.timestamp()), QTimeZone.utc()))

    assert isinstance(dialog.progress_slider, NoWheelSlider)
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

    assert window.root_widget.background_enabled is True
    assert window.root_widget.background_image_path == str(image_path)
    assert window.root_widget.background_overlay == 0.55

    window.close()


def test_history_window_saves_reflection(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = make_task("完成任务", "done-1", status="done")
    store = MemoryStore([task])
    window = HistoryWindow([task], store)

    assert window.windowFlags() & Qt.FramelessWindowHint

    window.save_reflection("done-1", "这次要提前拆小任务")

    assert store.saved_tasks == [replace(task, reflection="这次要提前拆小任务")]

    window.close()


def test_history_window_is_compact_and_searchable(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    first = make_task("完成任务", "done-1", status="done")
    second = replace(make_task("另一条记录", "done-2", status="done"), priority="P2")
    store = MemoryStore([first, second])
    window = HistoryWindow([first, second], store)

    editors = window.findChildren(QTextEdit)
    assert editors
    assert editors[0].minimumHeight() == 58
    assert editors[0].maximumHeight() == 58

    window.search_input.setText("另一条")

    assert window.count_label.text() == "1 条"
    labels = "\n".join(label.text() for label in window.findChildren(QLabel))
    assert "2026-05-12 · 1 条" in labels

    window.search_input.clear()
    window.group_mode.setCurrentText("按等级")

    labels = "\n".join(label.text() for label in window.findChildren(QLabel))
    assert "P1 · 1 条" in labels
    assert "P2 · 1 条" in labels

    window.close()


def test_delete_dialog_uses_frameless_app_chrome(qapp: QApplication) -> None:
    from floating_todo.ui.confirmation_dialog import DeleteTaskDialog

    task = make_task("删除确认", "delete-1")
    dialog = DeleteTaskDialog(task)

    assert dialog.windowFlags() & Qt.FramelessWindowHint
    assert dialog.windowTitle() == "删除任务"

    dialog.close()
