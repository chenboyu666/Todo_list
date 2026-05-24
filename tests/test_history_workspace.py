from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os

import pytest
from PySide6.QtCore import QDate, QPoint, QPointF, Qt
from PySide6.QtGui import QPainter, QPixmap, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QLabel, QProgressBar, QWidget

from floating_todo.domain import Task

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


def test_history_window_saves_reflection(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = make_task("完成任务", "done-1", status="done")
    store = MemoryStore([task])
    window = HistoryWindow([task], store)

    assert window.windowFlags() & Qt.FramelessWindowHint
    window.save_reflection("done-1", "这次要提前拆小任务")
    assert store.saved_tasks == [replace(task, reflection="这次要提前拆小任务")]

    window.close()


def test_history_workspace_navigation_and_actions(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    class ParentWindow(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.settings_opened = 0
            self.main_activated = 0

        def open_settings(self) -> None:
            self.settings_opened += 1

        def showNormal(self) -> None:
            self.main_activated += 1

        def raise_(self) -> None:
            self.main_activated += 1

        def activateWindow(self) -> None:
            self.main_activated += 1

    first = replace(
        make_task("完成任务", "done-1", status="done", notes="交付前确认了备注"),
        reflection="复盘后决定提前拆分任务",
    )
    second = replace(
        make_task("另一条记录", "done-2", status="done"),
        priority="P2",
        completed_at=first.completed_at - timedelta(days=1),
        updated_at=first.updated_at - timedelta(days=1),
    )
    parent = ParentWindow()
    store = MemoryStore([first, second])
    window = HistoryWindow([first, second], store, parent)

    assert window.minimumWidth() >= 1180
    assert window.minimumHeight() >= 900
    assert window.isSizeGripEnabled()
    assert window.history_resize_grip.toolTip() == "拖动调整历史窗口大小"
    assert window.history_section_stack.currentWidget() is window.history_tasks_scroll
    assert window.history_sidebar_buttons["history"].isChecked()
    assert not window.history_sidebar_buttons["analysis"].isChecked()
    assert window.top_settings_button.toolTip() == "打开设置"
    assert window.minimize_button.toolTip() == "最小化"
    assert window.fullscreen_button.objectName() == "historyFullscreenButton"
    assert window.fullscreen_button.toolTip() == "最大化历史窗口"
    assert not window.top_settings_button.icon().isNull()
    assert not window.minimize_button.icon().isNull()
    assert not window.fullscreen_button.icon().isNull()
    assert window.count_label.text() == "2 条"
    assert window.records_count_label.text() == "2 条"
    assert window.priority_p1_label.text() == "高：1"
    assert window.priority_p2_label.text() == "中：1"
    assert window.priority_p3_label.text() == "低：0"
    assert window.review_metric_label.text() == "复盘 1/2"
    assert window.on_time_metric_label.text() == "准时率 100%"
    assert window.overdue_metric_label.text() == "超时 0/2"
    assert window.priority_donut_chart.priority_counts == {"P1": 1, "P2": 1, "P3": 0}
    assert window.deadline_outcome_chart.outcome_counts == {"on_time": 2, "overdue": 0, "no_deadline": 0}
    assert [value for _, value in window.completion_trend_chart.trend_points] == [1, 1]
    assert window.history_tasks_scroll.horizontalScrollBar().maximum() == 0
    assert window.history_analysis_scroll.horizontalScrollBar().maximum() == 0
    assert window.history_records_panel.objectName() == "historyRecordsPanel"
    assert "historyRecordsPanel" in window.styleSheet()
    assert "historyAnalysisSummaryPanel" in window.styleSheet()
    assert "historyChartCard" in window.styleSheet()
    metric_icons = window.findChildren(QLabel, "historyMetricIcon")
    assert len(metric_icons) >= 8
    assert all(icon.pixmap() is not None and not icon.pixmap().isNull() for icon in metric_icons)

    window.show()
    qapp.processEvents()

    window.history_sidebar_buttons["analysis"].click()
    qapp.processEvents()
    assert window.history_section_stack.currentWidget() is window.history_analysis_scroll
    assert window.history_sidebar_buttons["analysis"].isChecked()
    assert window.analysis_range_label.text().startswith("统计区间")
    assert window.analysis_count_label.text() == "2 条"
    assert "完成节奏 = 最近一段时间每天完成任务数量的趋势" in window.analysis_rhythm_hint_label.text()
    assert window.analysis_total_value_label.text() == "2 条"
    assert "<img" in window.analysis_priority_value_label.text()
    assert any(label in window.analysis_priority_value_label.text() for label in ("高", "中", "低"))
    assert window.analysis_needs_notes_button.text() == "查看待补记"
    window.analysis_reviewed_button.click()
    qapp.processEvents()
    assert window.history_section_stack.currentWidget() is window.history_tasks_scroll
    assert window.status_filter.currentData() == "reviewed"
    window.history_sidebar_buttons["analysis"].click()
    qapp.processEvents()

    window.fullscreen_button.click()
    qapp.processEvents()
    assert window.isMaximized()
    assert window.fullscreen_button.text() == ""
    assert not window.fullscreen_button.icon().isNull()
    window.fullscreen_button.click()
    qapp.processEvents()
    assert not window.isMaximized()

    window.history_top_button.click()
    qapp.processEvents()
    assert window.history_content_scroll.verticalScrollBar().value() == 0
    assert window.top_settings_button.accessibleName() == "打开设置"
    window.top_settings_button.click()
    assert parent.settings_opened == 1
    window.history_sidebar_buttons["settings"].click()
    assert parent.settings_opened == 2

    task_window = HistoryWindow([first, second], store, parent)
    task_window.history_sidebar_buttons["tasks"].click()
    qapp.processEvents()
    assert parent.main_activated >= 3
    assert not task_window.isVisible()

    window.close()
    parent.close()


def test_history_workspace_filters_export_and_no_progress(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    base = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    first = replace(
        make_task("完成任务", "done-1", status="done", notes="交付前确认备注"),
        reflection="下次提前拆分",
        priority="P1",
        completed_at=base,
        updated_at=base,
        deadline=base + timedelta(hours=1),
    )
    second = replace(
        make_task("超时记录", "done-2", status="done"),
        priority="P2",
        completed_at=base - timedelta(days=1),
        updated_at=base - timedelta(days=1),
        deadline=base - timedelta(days=1, hours=1),
    )
    third = replace(
        make_task("无截止记录", "done-3", status="done"),
        priority="P3",
        completed_at=base - timedelta(days=2),
        updated_at=base - timedelta(days=2),
        deadline=None,
    )
    store = MemoryStore([first, second, third])
    window = HistoryWindow([first, second, third], store)

    assert window.findChildren(QProgressBar, "historyInlineProgress") == []
    assert window.deadline_outcome_chart.outcome_counts == {"on_time": 1, "overdue": 1, "no_deadline": 1}
    assert "#0F766E" in window.styleSheet()
    assert window.priority_p1_label.text() == "高：1"
    assert window.priority_p2_label.text() == "中：1"
    assert window.priority_p3_label.text() == "低：1"
    assert window.on_time_metric_label.text() == "准时率 50%"
    assert window.overdue_metric_label.text() == "超时 1/2"

    window.search_input.setText("完成")
    qapp.processEvents()
    assert window.count_label.text() == "1 条"
    titles = [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")]
    assert "完成任务" in titles
    assert "超时记录" not in titles

    window.search_input.clear()
    window.status_filter.setCurrentIndex(window.status_filter.findData("overdue"))
    qapp.processEvents()
    assert window.records_count_label.text() == "1 条"
    assert [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")] == ["超时记录"]

    window.status_filter.setCurrentIndex(window.status_filter.findData("reviewed"))
    qapp.processEvents()
    assert window.records_count_label.text() == "1 条"
    assert [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")] == ["完成任务"]

    window.status_filter.setCurrentIndex(window.status_filter.findData("all"))
    window.priority_filter.setCurrentIndex(window.priority_filter.findData("P2"))
    qapp.processEvents()
    assert [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")] == ["超时记录"]

    window.priority_filter.setCurrentIndex(window.priority_filter.findData("all"))
    window.export_start_date.setDate(window.export_end_date.date())
    qapp.processEvents()

    export_path = tmp_path / "history.csv"
    count = window.export_history_to_path(export_path)
    assert count == 1
    exported = export_path.read_text(encoding="utf-8-sig")
    assert "任务ID,标题,优先级" in exported
    assert "done-1,完成任务,高" in exported
    assert "交付前确认备注" in exported
    assert "下次提前拆分" in exported
    assert "done-2" not in exported
    assert "done-3" not in exported

    window.export_start_date.setDate(QDate(2026, 5, 10))
    window.export_end_date.setDate(QDate(2026, 5, 12))
    qapp.processEvents()
    count = window.export_history_to_path(tmp_path / "history-all.csv")
    assert count == 3

    window.close()


def test_history_workspace_filters_ignore_mouse_wheel_changes(qapp: QApplication) -> None:
    from floating_todo.ui.history_window import HistoryWindow

    task = replace(
        make_task("完成任务", "done-1", status="done"),
        completed_at=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
    )
    window = HistoryWindow([task], MemoryStore([task]))
    window.show()
    qapp.processEvents()

    original_status = window.status_filter.currentIndex()
    original_priority = window.priority_filter.currentIndex()
    original_page_size = window.page_size_combo.currentIndex()
    original_sort = window.sort_mode.currentIndex()
    original_date = window.analytics_start_date.date()
    original_page = window.page_jump_input.value()

    def wheel(widget) -> None:
        event = QWheelEvent(
            QPointF(10, 10),
            QPointF(10, 10),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.NoButton,
            Qt.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(widget, event)

    for widget in (
        window.status_filter,
        window.priority_filter,
        window.page_size_combo,
        window.sort_mode,
        window.analytics_start_date,
        window.export_start_date,
        window.page_jump_input,
    ):
        wheel(widget)

    assert window.status_filter.currentIndex() == original_status
    assert window.priority_filter.currentIndex() == original_priority
    assert window.page_size_combo.currentIndex() == original_page_size
    assert window.sort_mode.currentIndex() == original_sort
    assert window.analytics_start_date.date() == original_date
    assert window.page_jump_input.value() == original_page

    window.close()


def test_history_workspace_calendar_allows_direct_year_edit(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QAbstractSpinBox, QSpinBox, QToolButton
    from floating_todo.ui.history_window import HistoryWindow

    task = replace(
        make_task("完成任务", "done-1", status="done"),
        completed_at=datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc),
    )
    window = HistoryWindow([task], MemoryStore([task]))
    date_edits = (
        window.analytics_start_date,
        window.analytics_end_date,
        window.export_start_date,
        window.export_end_date,
    )

    for offset, date_edit in enumerate(date_edits):
        target_year = 2028 + offset
        assert date_edit.buttonSymbols() == QAbstractSpinBox.NoButtons
        calendar = date_edit.calendarWidget()
        calendar.show()
        qapp.processEvents()

        year_button = calendar.findChild(QToolButton, "qt_calendar_yearbutton")
        month_button = calendar.findChild(QToolButton, "qt_calendar_monthbutton")
        year_edit = calendar.findChild(QSpinBox, "qt_calendar_yearedit")

        assert year_button is not None
        assert month_button is not None
        assert month_button.menu() is not None
        assert year_edit is not None
        assert year_edit.isHidden()

        QTest.mouseClick(year_button, Qt.LeftButton)
        qapp.processEvents()
        assert not year_edit.isHidden()

        year_line_edit = year_edit.lineEdit()
        assert year_line_edit is not None
        year_line_edit.setFocus(Qt.OtherFocusReason)
        year_line_edit.selectAll()
        QTest.keyClicks(year_line_edit, str(target_year))
        QTest.keyClick(year_line_edit, Qt.Key_Return)
        qapp.processEvents()
        assert calendar.yearShown() == target_year
        assert date_edit.date().year() == target_year

    window.close()


def test_history_workspace_pagination_record_menu_and_chart_render(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.history_window import HistoryWindow
    import floating_todo.ui.history_window as history_window

    base = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    tasks = [
        replace(
            make_task(f"完成记录 {index}", f"done-{index}", status="done"),
            priority="P1" if index % 3 == 0 else "P2" if index % 3 == 1 else "P3",
            notes="需要沉淀要点" if index == 0 else "",
            reflection="形成复盘" if index == 0 else "",
            completed_at=base - timedelta(minutes=index),
            updated_at=base - timedelta(minutes=index),
        )
        for index in range(10)
    ]
    store = MemoryStore(tasks)
    window = HistoryWindow(tasks, store)

    assert window.page_summary_label.text().startswith("1-8 / 10 条")
    assert [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")][:2] == ["完成记录 0", "完成记录 1"]

    window.page_size_combo.setCurrentIndex(window.page_size_combo.findData(12))
    qapp.processEvents()
    assert window.page_summary_label.text().startswith("1-10 / 10 条")

    window.page_size_combo.setCurrentIndex(window.page_size_combo.findData(8))
    qapp.processEvents()
    window.next_page_button.click()
    qapp.processEvents()
    assert window.page_summary_label.text().startswith("9-10 / 10 条")
    assert [label.text() for label in window.findChildren(QLabel, "historyRecordTitle")] == ["完成记录 8", "完成记录 9"]

    window.prev_page_button.click()
    qapp.processEvents()
    card = window.findChildren(QFrame, "historyCard")[0]
    menu_button = card.findChild(QWidget, "historyMoreButton")
    priority_icon = card.findChild(QLabel, "historyPriorityIcon")
    assert priority_icon is not None
    assert priority_icon.pixmap() is not None
    assert not priority_icon.pixmap().isNull()
    assert menu_button is not None
    assert not menu_button.icon().isNull()
    menu = menu_button.menu()
    assert menu is not None
    assert [action.text() for action in menu.actions()] == ["查看/编辑备注", "复制记录摘要", "导出当前记录"]

    window._copy_record_summary(tasks[0])
    assert "完成记录 0" in QApplication.clipboard().text()

    export_path = tmp_path / "single-record.csv"
    monkeypatch.setattr(history_window.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(export_path), "CSV"))
    window._export_single_record(tasks[0])
    exported = export_path.read_text(encoding="utf-8-sig")
    assert "done-0" in exported
    assert "done-1" not in exported

    for chart in (
        window.priority_donut_chart,
        window.completion_trend_chart,
        window.deadline_outcome_chart,
        window.analysis_priority_donut_chart,
    ):
        chart.resize(240, 160)
        pixmap = QPixmap(chart.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        chart.render(painter, QPoint(0, 0))
        painter.end()
        assert not pixmap.isNull()

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
