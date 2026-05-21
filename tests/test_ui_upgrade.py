from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os

import pytest
from PySide6.QtCore import QDateTime, QEvent, QPoint, QPointF, QTimeZone, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDateEdit, QDialog, QFrame, QGridLayout, QLabel, QProgressBar, QPushButton, QWidget

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


def test_main_surface_omits_progress_percentage_controls(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    task = make_task("紧凑进度", "task-1")
    store = MemoryStore([task])
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    assert not hasattr(window, "focus_progress")
    assert not hasattr(window, "focus_progress_label")
    assert window.focus_card.findChildren(NoWheelSlider) == []
    assert window.focus_card.findChildren(NoWheelSpinBox) == []
    assert "10%" not in "\n".join(label.text() for label in window.focus_card.findChildren(QLabel))

    row_text = "\n".join(label.text() for label in window.task_rows_container.findChildren(QLabel))
    assert "10%" not in row_text
    assert window.task_rows_container.findChildren(QLabel, "activeTaskProgressValue") == []
    assert window.task_rows_container.findChildren(QLabel, "taskProgressValue") == []

    next(button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "展开").click()
    qapp.processEvents()

    assert window.task_rows_container.findChildren(NoWheelSlider) == []
    assert window.task_rows_container.findChildren(NoWheelSpinBox, "activeTaskProgressInput") == []
    assert window.task_rows_container.findChildren(NoWheelSpinBox, "taskProgressInput") == []

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
    title_index = window.focus_top_layout.indexOf(window.focus_title_label)
    assert window.focus_top_layout.getItemPosition(title_index) == (1, 0, 1, 4)
    deadline_index = window.focus_top_layout.indexOf(window.focus_deadline_panel)
    assert window.focus_top_layout.getItemPosition(deadline_index) == (2, 0, 1, 4)

    window.resize(860, 620)
    qapp.processEvents()
    title_index = window.focus_top_layout.indexOf(window.focus_title_label)
    assert window.focus_top_layout.getItemPosition(title_index) == (1, 0, 1, 4)
    deadline_index = window.focus_top_layout.indexOf(window.focus_deadline_panel)
    assert window.focus_top_layout.getItemPosition(deadline_index) == (0, 4, 2, 1)

    row_labels = "\n".join(label.text() for label in window.task_rows_container.findChildren(QLabel))
    button_text = "\n".join(button.text() for button in window.task_rows_container.findChildren(QPushButton))
    button_tooltips = "\n".join(button.toolTip() for button in window.task_rows_container.findChildren(QPushButton))

    assert "截止" in row_labels
    assert "2026-" in row_labels
    assert "已超时" in row_labels
    assert "当前" in button_text
    assert "展开" in button_text
    assert isinstance(window.task_list_layout, QGridLayout)
    assert "border: none" in _card_style("normal")
    assert "border: 1px" not in _card_style("normal")
    assert window.task_rows_container.findChildren(NoWheelSlider) == []
    assert window.task_rows_container.findChildren(QLabel, "activeTaskProgressValue") == []
    assert window.task_rows_container.findChildren(QLabel, "taskProgressValue") == []
    assert "10%" not in row_labels
    assert "设为当前置顶任务" in button_tooltips
    assert window.focus_card.toolTip() == "把任务拖到这里设为进行中"
    assert window.focus_complete_button.text() == "完成"
    assert window.focus_pause_button.text() == "Ⅱ"
    assert window.focus_pause_button.toolTip() == "暂停工作计时，截止倒计时仍继续"
    assert window.focus_title_label.maximumHeight() <= 96
    assert window.focus_delete_button.text() == "删除"
    assert window.focus_pause_button.isEnabled()
    assert not window.focus_resume_button.isEnabled()
    assert window.focus_complete_button.isEnabled()
    assert window.focus_delete_button.isEnabled()
    assert _countdown_display("00:00:01", True) == "00:00:01"
    assert "font-size: 20px" in _countdown_label_style("normal", pulse=True)
    assert "#0A2740" in _countdown_label_style("normal", pulse=False)
    assert "#9A3B18" in _countdown_label_style("critical", pulse=False)
    assert "#5A2D12" in _priority_chip_style("P1")
    assert window.focus_priority_label.text() == "▲ 高"
    assert "font-size: 24px" in window.focus_title_label.styleSheet()
    assert ("focusCountdownLabel", 170) not in tick_animations
    qapp.processEvents()
    window.focus_countdown_label.setText("00:00:00")
    window.refresh()
    assert ("focusCountdownLabel", 170) in tick_animations
    assert not window.focus_notes_label.isHidden()
    assert "备注：先确认接口" in window.focus_notes_label.text()
    assert window.focus_deadline_label.text().startswith("截止 2026-")
    assert window.focus_countdown_label.text().startswith("超时 ")
    assert window.focus_work_timer_label.text().startswith("计时 ")
    assert " / " not in window.focus_work_timer_label.text()
    assert not hasattr(window, "focus_progress_label")
    current_buttons = [button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "当前"]
    assert current_buttons[0].objectName() == "currentTaskButton"
    task_titles = window.task_rows_container.findChildren(QLabel, "activeTaskTitle")
    assert task_titles
    assert task_titles[0].minimumHeight() >= 38
    assert task_titles[0].toolTip() == "临近任务"
    deadlines = window.task_rows_container.findChildren(QLabel, "activeTaskDeadline")
    assert deadlines
    assert deadlines[0].wordWrap()
    assert deadlines[0].minimumHeight() >= 28
    timers = window.task_rows_container.findChildren(QLabel, "activeTaskTimer")
    assert timers
    assert timers[0].text().startswith("计时 ")
    assert " / " not in timers[0].text()
    assert timers[0].geometry().top() >= deadlines[0].geometry().bottom()
    expand_button = next(button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "展开")
    expand_button.click()
    qapp.processEvents()

    assert window.task_rows_container.findChildren(NoWheelSlider) == []
    assert window.task_rows_container.findChildren(NoWheelSpinBox, "activeTaskProgressInput") == []
    assert any(button.text() == "收起" for button in window.task_rows_container.findChildren(QPushButton))
    assert any(button.text() == "Ⅱ" for button in window.task_rows_container.findChildren(QPushButton))
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


def test_paused_task_can_still_be_pinned_as_current(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [make_task("当前", "task-1"), make_task("暂停候选", "task-paused", status="paused")]
    store = MemoryStore(tasks)
    window = MainWindow(store, AppSettings(focus_task_id="task-1"), tmp_path / "settings.json")

    focus_button = next(button for button in window.task_rows_container.findChildren(QPushButton) if button.text() == "置顶")
    focus_button.click()

    assert window.settings.focus_task_id == "task-paused"
    assert window.focus_title_label.text() == "暂停候选"
    assert window.focus_meta_label.text() == "暂停中"

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
    assert window.minimumWidth() >= 960
    assert window.minimumHeight() >= 900
    assert window.width() >= 1080
    assert window.height() >= 920
    assert window.isSizeGripEnabled()
    assert window.history_resize_grip.toolTip() == "拖动调整历史窗口大小"
    assert window.fullscreen_button.objectName() == "historyFullscreenButton"
    assert window.fullscreen_button.toolTip() == "全屏历史窗口"
    assert window.priority_p1_label.text() == "▲ 高：1"
    assert window.priority_p2_label.text() == "◆ 中：1"
    assert window.priority_p3_label.text() == "▼ 低：0"
    assert window.review_metric_label.text() == "复盘 1/2"
    assert window.on_time_metric_label.text() == "准时率 100%"
    assert window.overdue_metric_label.text() == "超时 0/2"
    assert window.priority_donut_chart.priority_counts == {"P1": 1, "P2": 1, "P3": 0}
    assert window.deadline_outcome_chart.outcome_counts == {"on_time": 2, "overdue": 0, "no_deadline": 0}
    assert [value for _, value in window.completion_trend_chart.trend_points] == [1, 1]
    assert window.history_content_scroll.widgetResizable()
    assert window.stats_panel.height() >= 320
    assert window.priority_donut_chart.minimumHeight() >= 126
    assert window.deadline_outcome_chart.minimumHeight() >= 126
    assert window.priority_donut_chart.parentWidget().minimumHeight() >= 178
    assert window.history_scroll_area.minimumHeight() >= 160
    assert window.date_pager_widget.objectName() == "historyPagerPanel"
    assert window.history_records_panel.objectName() == "historyRecordsPanel"
    assert window.history_search_panel.objectName() == "historySearchPanel"
    assert window.history_analytics_panel.objectName() == "historyAnalyticsPanel"
    assert "historyPagerPanel" in window.styleSheet()
    assert "historyRecordsPanel" in window.styleSheet()
    assert "historySearchPanel" in window.styleSheet()
    assert "historyAnalyticsPanel" in window.styleSheet()
    assert "historyWorkTimerChip" in window.styleSheet()
    assert "#25135C" in window.styleSheet()
    window.show()
    qapp.processEvents()
    assert window.history_content_scroll.verticalScrollBar().maximum() == 0
    normal_geometry = window.geometry()
    window.fullscreen_button.click()
    qapp.processEvents()
    assert window.isFullScreen()
    assert window.fullscreen_button.text() == "▣"
    window.fullscreen_button.click()
    qapp.processEvents()
    assert not window.isFullScreen()
    assert window.geometry() == normal_geometry
    assert window.fullscreen_button.text() == "□"
    assert window.analytics_count_label.height() <= 32
    date_chips = (
        window.analytics_start_date_chip,
        window.analytics_end_date_chip,
        window.export_start_date_chip,
        window.export_end_date_chip,
    )
    date_edits = (
        window.analytics_start_date,
        window.analytics_end_date,
        window.export_start_date,
        window.export_end_date,
    )
    for chip, date_edit in zip(date_chips, date_edits):
        chip_label = chip.findChild(QLabel, "historyExportDateLabel")
        assert chip.height() == 36
        assert chip.minimumWidth() >= 214
        assert chip_label is not None
        assert chip_label.height() == 28
        assert chip_label.alignment() & Qt.AlignHCenter
        assert chip_label.alignment() & Qt.AlignVCenter
        assert date_edit.height() == 28
        assert date_edit.minimumWidth() >= 132
        assert date_edit.alignment() & Qt.AlignHCenter
        assert isinstance(date_edit, QDateEdit)
        assert abs(chip_label.geometry().center().y() - date_edit.geometry().center().y()) <= 1
        assert abs(chip.rect().center().y() - date_edit.geometry().center().y()) <= 1
    assert window.export_button.height() == 36
    metric_tops = {
        label.geometry().top()
        for label in (
            window.priority_p1_label,
            window.priority_p2_label,
            window.priority_p3_label,
            window.review_metric_label,
            window.on_time_metric_label,
            window.overdue_metric_label,
            window.average_metric_label,
            window.latest_metric_label,
        )
    }
    assert len(metric_tops) == 1
    toolbar = window.findChild(QFrame, "historyToolbar")
    toolbar_top = toolbar.mapTo(window, QPoint(0, 0)).y()
    for card in window.findChildren(QFrame, "historyChartCard"):
        assert card.geometry().bottom() <= window.stats_panel.contentsRect().bottom()
        assert card.mapTo(window, QPoint(0, card.height())).y() < toolbar_top
        assert (
            card.findChild(QWidget, "historyPriorityDonutChart")
            or card.findChild(QWidget, "historyCompletionTrendChart")
            or card.findChild(QWidget, "historyDeadlineOutcomeChart")
        )
    assert window.history_scroll_area.geometry().top() > window.stats_panel.geometry().bottom()
    assert window.priority_donut_chart.accessibleName() == "优先级完成结构图"
    assert window.completion_trend_chart.accessibleName() == "每日完成曲线图"
    assert window.deadline_outcome_chart.accessibleName() == "准时与超时分布图"
    assert window.analytics_start_date.accessibleName() == "统计起始日期"
    assert window.analytics_end_date.accessibleName() == "统计结束日期"
    assert window.analytics_count_label.text() == "2 条"
    assert window.analytics_all_button.text() == "全部"
    assert window.analytics_week_button.text() == "近7日"
    assert window.analytics_month_button.text() == "本月"
    assert window.analytics_start_date.calendarWidget().objectName() == "historyAnalyticsStartCalendar"
    assert window.search_input.placeholderText() == "按任务名称搜索"
    assert isinstance(window.list_layout, QGridLayout)
    assert window._history_grid_columns() >= 2
    assert window.priority_p1_label.height() >= 28
    window.analytics_start_date.setDate(window.analytics_end_date.date())
    qapp.processEvents()
    assert window.analytics_count_label.text() == "1 条"
    assert window.priority_donut_chart.priority_counts == {"P1": 1, "P2": 0, "P3": 0}
    assert [value for _, value in window.completion_trend_chart.trend_points] == [1]
    window.analytics_all_button.click()
    qapp.processEvents()
    assert window.analytics_count_label.text() == "2 条"
    assert window.priority_donut_chart.priority_counts == {"P1": 1, "P2": 1, "P3": 0}
    assert window.findChildren(QProgressBar, "historyInlineProgress")
    assert window.export_button.text() == "导出 CSV"
    assert window.export_start_date.accessibleName() == "导出起始日期"
    assert window.export_end_date.accessibleName() == "导出结束日期"
    assert window.export_count_label.text() == "2 条"
    assert window.export_all_button.text() == "全部"
    assert window.export_week_button.text() == "近7日"
    assert window.export_month_button.text() == "本月"
    assert window.export_start_date.calendarWidget().objectName() == "historyExportStartCalendar"
    assert window.export_start_date.calendarWidget().firstDayOfWeek() == Qt.Monday
    assert not window.export_start_date.calendarWidget().isGridVisible()
    assert "#070B12" in window.export_start_date.calendarWidget().styleSheet()
    window.export_start_date.setDate(window.export_end_date.date())
    qapp.processEvents()
    assert window.export_count_label.text() == "1 条"
    window.export_all_button.click()
    qapp.processEvents()
    assert window.export_count_label.text() == "2 条"

    labels = rendered_history_text()
    assert "已复盘" in labels
    assert window.date_selector.currentData() == "2026-05-12"
    assert "1-1/1 条 · 1/1 页" in window.date_page_label.text()
    assert "完成任务" in labels
    assert "任务备注：交付前确认了备注" in labels
    assert "完成体会：完成后觉得复盘有效" in labels
    assert "另一条记录" not in labels
    previews = window.findChildren(QLabel, "historyPreview")
    assert previews
    assert previews[0].minimumHeight() >= 44

    window.search_input.setText("交付")
    qapp.processEvents()

    assert window.count_label.text() == "0 条"
    window.search_input.clear()
    qapp.processEvents()

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "1-1/1 条 · 1/1 页" in window.date_page_label.text()
    assert "完成任务" in labels

    window.search_input.setText("另一条")
    qapp.processEvents()

    assert window.count_label.text() == "1 条"
    assert window.export_count_label.text() == "1 条"
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
    assert "▲ 高：1 条" in labels
    assert "◆ 中：1 条" in labels

    window.close()


def test_history_analytics_tracks_overdue_and_no_deadline(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    base = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    on_time = replace(
        make_task("准时完成", "done-on-time", status="done"),
        deadline=base + timedelta(hours=1),
        completed_at=base,
        updated_at=base,
        priority="P1",
    )
    overdue = replace(
        make_task("超时完成", "done-overdue", status="done"),
        deadline=base - timedelta(hours=1),
        completed_at=base,
        updated_at=base,
        priority="P2",
    )
    no_deadline = replace(
        make_task("无截止完成", "done-no-deadline", status="done"),
        deadline=None,
        completed_at=base - timedelta(days=1),
        updated_at=base - timedelta(days=1),
        priority="P3",
    )
    store = MemoryStore([on_time, overdue, no_deadline])
    window = HistoryWindow([on_time, overdue, no_deadline], store)

    assert window.priority_p1_label.text() == "▲ 高：1"
    assert window.priority_p2_label.text() == "◆ 中：1"
    assert window.priority_p3_label.text() == "▼ 低：1"
    assert window.on_time_metric_label.text() == "准时率 50%"
    assert window.overdue_metric_label.text() == "超时 1/2"
    assert window.deadline_outcome_chart.outcome_counts == {"on_time": 1, "overdue": 1, "no_deadline": 1}
    assert [value for _, value in window.completion_trend_chart.trend_points] == [1, 2]

    for chart in (window.priority_donut_chart, window.completion_trend_chart, window.deadline_outcome_chart):
        chart.resize(240, 132)
        pixmap = QPixmap(chart.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        chart.render(painter, QPoint(0, 0))
        painter.end()
        assert not pixmap.isNull()

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
    assert "done-1,完成任务,高" in exported
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
        for index in range(10)
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
    assert window.page_size_input.value() == 8
    assert not hasattr(window, "page_size_step_hint")
    assert "↑ 增加" in window.page_size_input.toolTip()
    assert "↓ 减少" in window.page_size_input.toolTip()
    assert window.date_selector.currentData() == "2026-05-12"
    assert "1-8/10 条 · 1/2 页" in window.date_page_label.text()
    assert "完成记录 0" in labels
    assert "完成记录 9" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "9-10/10 条 · 2/2 页" in window.date_page_label.text()
    assert "完成记录 9" in labels
    assert "完成记录 0" not in labels

    window.page_size_input.setValue(2)
    qapp.processEvents()

    assert "1-2/10 条 · 1/5 页" in window.date_page_label.text()

    window.group_mode.setCurrentText("按等级")
    qapp.processEvents()

    labels = rendered_history_text()
    assert "按等级 · 1-2/10 条 · 1/5 页" in window.date_page_label.text()
    assert "完成记录 0" in labels
    assert "完成记录 2" not in labels

    window.next_date_button.click()
    qapp.processEvents()

    labels = rendered_history_text()
    assert "按等级 · 3-4/10 条 · 2/5 页" in window.date_page_label.text()
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
