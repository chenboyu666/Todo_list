from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os

import pytest
from PySide6.QtCore import QDateTime, QEvent, QPoint, QPointF, QTimeZone, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QDialog, QGridLayout, QLabel, QPushButton

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
    title_label = window.centralWidget().findChild(QLabel, "windowTitleLabel")
    assert title_label is not None
    assert title_label.parent().cursor().shape() == Qt.OpenHandCursor
    assert window.close_button.text() == "×"
    assert window.close_button.cursor().shape() == Qt.PointingHandCursor

    window.set_focus_task("task-2")

    assert window.settings.focus_task_id == "task-2"
    assert window.focus_title_label.text() == "拖入进行中"
    assert getattr(qapp, "_floating_todo_interaction_filter", None) is not None
    assert window.root_widget._click_pulses

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


def test_progress_slider_drags_from_any_track_position(qapp: QApplication) -> None:
    slider = NoWheelSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.resize(220, 28)
    release_count = 0

    def count_release() -> None:
        nonlocal release_count
        release_count += 1

    slider.sliderReleased.connect(count_release)

    slider.mousePressEvent(
        QMouseEvent(
            QEvent.MouseButtonPress,
            QPointF(12, 14),
            QPointF(12, 14),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
    )
    slider.mouseMoveEvent(
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(198, 14),
            QPointF(198, 14),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
    )

    assert slider.isSliderDown() is True
    assert slider.value() > 80

    slider.mouseReleaseEvent(
        QMouseEvent(
            QEvent.MouseButtonRelease,
            QPointF(198, 14),
            QPointF(198, 14),
            Qt.LeftButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
    )

    assert slider.isSliderDown() is False
    assert release_count == 1
    slider.close()


def test_task_rows_show_deadline_date_urgency_and_focus_button(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow, TaskDragHandle, _card_style

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
    assert "展开" in button_text
    assert isinstance(window.task_list_layout, QGridLayout)
    assert "border: none" in _card_style("normal")
    assert "border: 1px" not in _card_style("normal")
    assert window.task_rows_container.findChildren(NoWheelSlider) == []
    progress_values = window.task_rows_container.findChildren(QLabel, "activeTaskProgressValue")
    assert progress_values
    assert "设为当前置顶任务" in button_tooltips
    assert window.focus_card.toolTip() == "把任务拖到这里设为进行中"
    current_buttons = [button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "进行中"]
    assert current_buttons[0].objectName() == "currentTaskButton"
    expand_button = next(button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "展开")
    expand_button.click()
    qapp.processEvents()

    sliders = window.task_rows_container.findChildren(NoWheelSlider)
    assert sliders
    assert sliders[0].objectName() == "activeTaskProgress"
    assert any(button.text() == "收起" for button in window.task_rows_container.findChildren(QPushButton))

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
    second = replace(
        make_task("另一条记录", "done-2", status="done"),
        priority="P2",
        completed_at=first.completed_at - timedelta(days=1),
        updated_at=first.updated_at - timedelta(days=1),
    )
    store = MemoryStore([first, second])
    window = HistoryWindow([first, second], store)

    def rendered_history_text() -> str:
        parts: list[str] = []
        for index in range(window.list_layout.count()):
            widget = window.list_layout.itemAt(index).widget()
            if widget is None:
                continue
            if isinstance(widget, QLabel):
                parts.append(widget.text())
            parts.extend(label.text() for label in widget.findChildren(QLabel))
        return "\n".join(parts)

    note_buttons = [button for button in window.findChildren(QPushButton) if button.text() == "查看/编辑备注"]
    assert note_buttons

    labels = rendered_history_text()
    assert "2026-05-12 · 1 条 · 1/2" in window.date_page_label.text()
    assert "完成任务" in labels
    assert "另一条记录" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "2026-05-11 · 1 条 · 2/2" in window.date_page_label.text()
    assert "另一条记录" in labels
    assert "完成任务" not in labels

    window.search_input.setText("另一条")
    qapp.processEvents()

    assert window.count_label.text() == "1 条"
    assert "2026-05-11 · 1 条 · 1/1" in window.date_page_label.text()

    window.search_input.clear()
    window.group_mode.setCurrentText("按等级")
    qapp.processEvents()

    labels = rendered_history_text()
    assert window.date_pager_widget.isHidden()
    assert "P1 · 1 条" in labels
    assert "P2 · 1 条" in labels

    window.close()


def test_history_note_editor_saves_notes_and_reflection(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    import floating_todo.ui.history_window as history_window

    task = replace(make_task("完成任务", "done-1", status="done"), notes="旧备注", reflection="旧体会")
    store = MemoryStore([task])
    captured: dict[str, object] = {}

    class AcceptedNoteDialog:
        def __init__(self, task, parent=None) -> None:
            captured["task"] = task
            captured["parent"] = parent

        def exec(self) -> int:
            return QDialog.Accepted

        def notes(self) -> str:
            return "新的备注"

        def reflection(self) -> str:
            return "新的体会"

    monkeypatch.setattr(history_window, "HistoryNoteDialog", AcceptedNoteDialog)
    window = history_window.HistoryWindow([task], store)

    window.open_note_editor(task)

    assert captured["task"] == task
    assert captured["parent"] is window
    assert store.saved_tasks == [replace(task, notes="新的备注", reflection="新的体会")]

    window.close()


def test_history_note_dialog_shows_large_editors(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QTextEdit
    from floating_todo.ui.history_window import HistoryNoteDialog

    task = replace(make_task("完成任务", "done-1", status="done"), notes="旧备注", reflection="旧体会")
    dialog = HistoryNoteDialog(task)

    editors = dialog.findChildren(QTextEdit)

    assert len(editors) == 2
    assert dialog.notes() == "旧备注"
    assert dialog.reflection() == "旧体会"

    dialog.close()


def test_backdrop_click_pulse_records_and_expires(qapp: QApplication) -> None:
    from floating_todo.ui.backdrop import AnimatedBackdrop

    backdrop = AnimatedBackdrop()
    backdrop.add_click_pulse(QPoint(24, 32))

    assert len(backdrop._click_pulses) == 1

    for _ in range(11):
        backdrop._tick()

    assert backdrop._click_pulses == []

    backdrop.stop_animation()
    backdrop.close()


def test_global_interaction_effect_filter_installs_once(qapp: QApplication) -> None:
    from floating_todo.ui.effects import InteractionEffectFilter, install_global_interaction_effects

    first = install_global_interaction_effects(qapp)
    second = install_global_interaction_effects(qapp)

    assert first is second
    assert isinstance(first, InteractionEffectFilter)


def test_delete_dialog_uses_frameless_app_chrome(qapp: QApplication) -> None:
    from floating_todo.ui.confirmation_dialog import DeleteTaskDialog

    task = make_task("删除确认", "delete-1")
    dialog = DeleteTaskDialog(task)

    assert dialog.windowFlags() & Qt.FramelessWindowHint
    assert dialog.windowTitle() == "删除任务"

    dialog.close()
