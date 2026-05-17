from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os

import pytest
from PySide6.QtCore import QDateTime, QEvent, QPoint, QPointF, QTimeZone, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QGridLayout, QLabel, QProgressBar, QPushButton

from floating_todo.domain import Task
from floating_todo.settings import AppSettings
from floating_todo.ui.controls import NoWheelSlider, NoWheelSpinBox

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


def make_task(title: str, task_id: str, *, status: str = "active", notes: str = "") -> Task:
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
        notes=notes,
        notification_state={},
    )


def test_window_is_frameless_and_focus_task_can_be_selected(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import ClockDisplay, CornerResizeGrip, MainWindow

    tasks = [make_task("普通任务", "task-1"), make_task("拖入进行中", "task-2")]
    window = MainWindow(MemoryStore(tasks), AppSettings(), tmp_path / "settings.json")

    assert window.windowFlags() & Qt.FramelessWindowHint
    assert isinstance(window.resize_grip, CornerResizeGrip)
    assert window.resize_grip.toolTip() == "拖动调整窗口大小"
    assert isinstance(window.clock_label, ClockDisplay)
    assert window.clock_label.objectName() == "clockLabel"
    assert hasattr(window.clock_label, "_draw_clock_sweep")
    assert not hasattr(window.clock_label, "_draw_clock_stars")
    assert window.width() >= 540
    assert window.title_action_dock.height() == 46
    assert window.settings_button.height() == 38
    assert window.minimize_button.height() == 38
    assert window.close_button.height() == 38
    window.resize(560, 680)
    window.show()
    qapp.processEvents()
    title_bar = window.title_action_dock.parentWidget()
    assert title_bar is not None
    assert abs(window.title_action_dock.geometry().center().y() - title_bar.rect().center().y()) <= 1
    button_top = window.settings_button.mapTo(window.title_action_dock, QPoint(0, 0)).y()
    button_center = button_top + window.settings_button.height() // 2
    assert abs(button_center - window.title_action_dock.rect().center().y()) <= 1
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
    assert isinstance(window.focus_progress_label, NoWheelSpinBox)
    assert window.focus_progress_label.value() == 64

    window.focus_progress_label.setValue(38)

    assert window.focus_progress.value() == 38
    assert store.saved_tasks is not None
    assert store.saved_tasks[0].progress == 38

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
    slider.mouseMoveEvent(
        QMouseEvent(
            QEvent.MouseMove,
            QPointF(260, 14),
            QPointF(260, 14),
            Qt.NoButton,
            Qt.NoButton,
            Qt.NoModifier,
        )
    )
    assert slider.value() == 100

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


def test_task_rows_show_deadline_date_urgency_and_focus_button(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window
    from floating_todo.ui.main_window import (
        MainWindow,
        TaskDragHandle,
        _card_style,
        _countdown_display,
        _countdown_label_style,
        _priority_chip_style,
    )

    task = make_task("临近任务", "task-1", notes="先确认接口，再整理交付材料")
    store = MemoryStore([task])
    tick_animations: list[tuple[str, int]] = []
    monkeypatch.setattr(
        main_window,
        "animate_value_tick",
        lambda widget, duration=180: tick_animations.append((widget.objectName(), duration)),
    )
    window = MainWindow(store, AppSettings(), tmp_path / "settings.json")
    window.show()
    qapp.processEvents()

    window.resize(620, 620)
    qapp.processEvents()
    deadline_index = window.focus_top_layout.indexOf(window.focus_deadline_panel)
    assert window.focus_top_layout.getItemPosition(deadline_index) == (1, 0, 1, 4)

    window.resize(760, 620)
    qapp.processEvents()
    deadline_index = window.focus_top_layout.indexOf(window.focus_deadline_panel)
    assert window.focus_top_layout.getItemPosition(deadline_index) == (0, 4, 2, 1)

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
    assert window.focus_complete_button.text() == "完成"
    assert window.focus_delete_button.text() == "删除"
    assert window.focus_complete_button.isEnabled()
    assert window.focus_delete_button.isEnabled()
    assert _countdown_display("00:00:01", True) == "00:00:01"
    assert "font-size: 30px" in _countdown_label_style("normal", pulse=True)
    assert "#0A2740" in _countdown_label_style("normal", pulse=False)
    assert "#9A3B18" in _countdown_label_style("critical", pulse=False)
    assert "#5A2D12" in _priority_chip_style("P1")
    assert window.focus_priority_label.text() == "P1"
    assert "font-size: 24px" in window.focus_title_label.styleSheet()
    assert ("focusCountdownLabel", 170) not in tick_animations
    qapp.processEvents()
    window.focus_countdown_label.setText("00:00:00")
    window.refresh()
    assert ("focusCountdownLabel", 170) in tick_animations
    assert not window.focus_notes_label.isHidden()
    assert "备注：先确认接口" in window.focus_notes_label.text()
    assert window.focus_progress_label.text() == "10%"
    window.focus_progress.setSliderDown(True)
    window.focus_progress.setValue(67)
    assert window.focus_progress_label.text() == "67%"
    window.focus_progress.setSliderDown(False)
    current_buttons = [button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "进行中"]
    assert current_buttons[0].objectName() == "currentTaskButton"
    task_titles = window.task_rows_container.findChildren(QLabel, "activeTaskTitle")
    assert task_titles
    assert task_titles[0].minimumHeight() >= 38
    assert task_titles[0].toolTip() == "临近任务"
    deadlines = window.task_rows_container.findChildren(QLabel, "activeTaskDeadline")
    assert deadlines
    assert deadlines[0].wordWrap()
    assert deadlines[0].minimumHeight() >= 28
    expand_button = next(button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "展开")
    expand_button.click()
    qapp.processEvents()

    sliders = window.task_rows_container.findChildren(NoWheelSlider)
    assert sliders
    assert sliders[0].objectName() == "activeTaskProgress"
    progress_inputs = window.task_rows_container.findChildren(NoWheelSpinBox, "activeTaskProgressInput")
    assert progress_inputs
    assert progress_inputs[0].text() == "67%"
    progress_inputs[0].setValue(55)
    assert store.saved_tasks is not None
    assert store.saved_tasks[0].progress == 55
    assert any(button.text() == "收起" for button in window.task_rows_container.findChildren(QPushButton))
    task_notes = window.task_rows_container.findChildren(QLabel, "taskNotesPreview")
    assert task_notes
    assert "备注：先确认接口" in task_notes[0].text()

    drag_handles = window.task_rows_container.findChildren(TaskDragHandle)
    assert drag_handles == []

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
    assert isinstance(dialog.progress_spin, NoWheelSpinBox)
    dialog.progress_slider.setValue(34)
    assert dialog.progress_spin.value() == 34
    dialog.progress_spin.setValue(45)
    assert dialog.progress_slider.value() == 45
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
    assert window.root_widget.background_overlay == 0.68

    window.close()


def test_backdrop_supports_animated_gif_background(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.backdrop import AnimatedBackdrop

    gif_path = tmp_path / "background.gif"
    gif_path.write_bytes(b"GIF89a")
    backdrop = AnimatedBackdrop()

    backdrop.set_background_settings(True, str(gif_path), 0.55)

    assert backdrop._movie is not None
    assert backdrop._pixmap.isNull()

    backdrop.stop_animation()
    backdrop.close()


def test_backdrop_supports_builtin_animated_background(qapp: QApplication) -> None:
    from floating_todo.ui.backdrop import AnimatedBackdrop

    backdrop = AnimatedBackdrop()

    backdrop.set_background_settings(True, "builtin:bubu-motion", 0.55)

    assert backdrop._movie is not None
    assert backdrop.background_image_path == "builtin:bubu-motion"

    backdrop.stop_animation()
    backdrop.close()


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

    first = replace(
        make_task("完成任务", "done-1", status="done", notes="交付前确认了备注"),
        reflection="完成后觉得复盘有效",
    )
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
    assert window.priority_p1_label.text() == "P1 1"
    assert window.priority_p2_label.text() == "P2 1"
    assert window.priority_p3_label.text() == "P3 0"
    assert window.review_metric_label.text() == "复盘 1/2"
    assert window.findChildren(QProgressBar, "historyInlineProgress")
    assert window.export_button.text() == "导出 CSV"
    assert window.export_start_date.accessibleName() == "导出起始日期"
    assert window.export_end_date.accessibleName() == "导出结束日期"

    labels = rendered_history_text()
    assert "已复盘" in labels
    assert window.date_selector.currentData() == "2026-05-12"
    assert "1-1/1 条 · 1/1 页" in window.date_page_label.text()
    assert "完成任务" in labels
    assert "任务备注：交付前确认了备注" in labels
    assert "完成体会：完成后觉得复盘有效" in labels
    assert "另一条记录" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "1-1/1 条 · 1/1 页" in window.date_page_label.text()
    assert "完成任务" in labels

    window.search_input.setText("另一条")
    qapp.processEvents()

    assert window.count_label.text() == "1 条"
    assert window.date_selector.currentData() == "2026-05-11"
    assert "1-1/1 条 · 1/1 页" in window.date_page_label.text()

    window.search_input.clear()
    window.date_selector.setCurrentIndex(window.date_selector.findData("2026-05-11"))
    qapp.processEvents()

    labels = rendered_history_text()
    assert "另一条记录" in labels
    assert "完成任务" not in labels

    window.group_mode.setCurrentText("按等级")
    qapp.processEvents()

    labels = rendered_history_text()
    assert not window.date_pager_widget.isHidden()
    assert "按等级 · 1-2/2 条 · 1/1 页" in window.date_page_label.text()
    assert "P1 · 1 条" in labels
    assert "P2 · 1 条" in labels

    window.close()


def test_history_window_exports_filtered_records_as_csv(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    first = replace(
        make_task("完成任务", "done-1", status="done", notes="交付前确认备注"),
        reflection="下次提前拆分",
    )
    second = replace(
        make_task("另一条记录", "done-2", status="done"),
        priority="P2",
        completed_at=first.completed_at - timedelta(days=1),
        updated_at=first.updated_at - timedelta(days=1),
    )
    store = MemoryStore([first, second])
    window = HistoryWindow([first, second], store)
    window.search_input.setText("完成")
    qapp.processEvents()
    window.export_start_date.setDate(window.export_end_date.date())

    export_path = tmp_path / "history.csv"
    count = window.export_history_to_path(export_path)

    assert count == 1
    exported = export_path.read_text(encoding="utf-8-sig")
    assert "任务ID,标题,优先级" in exported
    assert "done-1,完成任务,P1" in exported
    assert "交付前确认备注" in exported
    assert "下次提前拆分" in exported
    assert "done-2" not in exported

    window.search_input.clear()
    qapp.processEvents()
    window.export_start_date.setDate(window.export_end_date.date())
    ranged_path = tmp_path / "history-range.csv"
    count = window.export_history_to_path(ranged_path)

    ranged = ranged_path.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "done-1" in ranged
    assert "done-2" not in ranged

    window.close()


def test_history_page_size_limits_date_results(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    base = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    tasks = [
        replace(
            make_task(f"完成记录 {index}", f"done-{index}", status="done"),
            completed_at=base - timedelta(minutes=index),
            updated_at=base - timedelta(minutes=index),
        )
        for index in range(6)
    ]
    store = MemoryStore(tasks)
    window = HistoryWindow(tasks, store)

    def rendered_history_text() -> str:
        parts: list[str] = []
        for index in range(window.list_layout.count()):
            widget = window.list_layout.itemAt(index).widget()
            if widget is None:
                continue
            parts.extend(label.text() for label in widget.findChildren(QLabel))
        return "\n".join(parts)

    labels = rendered_history_text()
    assert window.page_size_input.value() == 5
    assert "↑ 多" in window.page_size_step_hint.text()
    assert "↓ 少" in window.page_size_step_hint.text()
    assert window.date_selector.currentData() == "2026-05-12"
    assert "1-5/6 条 · 1/2 页" in window.date_page_label.text()
    assert "完成记录 0" in labels
    assert "完成记录 5" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "6-6/6 条 · 2/2 页" in window.date_page_label.text()
    assert "完成记录 5" in labels
    assert "完成记录 0" not in labels

    window.page_size_input.setValue(2)
    qapp.processEvents()

    assert "1-2/6 条 · 1/3 页" in window.date_page_label.text()

    window.group_mode.setCurrentText("按等级")
    qapp.processEvents()

    labels = rendered_history_text()
    assert "按等级 · 1-2/6 条 · 1/3 页" in window.date_page_label.text()
    assert "完成记录 0" in labels
    assert "完成记录 2" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "按等级 · 3-4/6 条 · 2/3 页" in window.date_page_label.text()
    assert "完成记录 2" in labels
    assert "完成记录 0" not in labels

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
    assert backdrop._click_pulses[0][1] == 8

    for _ in range(11):
        backdrop._tick()

    assert backdrop._click_pulses == []

    pixmap = QPixmap(240, 160)
    painter = QPainter(pixmap)
    backdrop._draw_nebula(painter, 240, 160)
    backdrop._draw_starfield(painter, 240, 160)
    backdrop._draw_meteors(painter, 240, 160)
    painter.end()

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
