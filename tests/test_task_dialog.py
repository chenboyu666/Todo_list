from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QDate, QDateTime, QPoint, QPointF, Qt, QTimeZone
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox, QLabel, QMainWindow, QSpinBox, QToolButton

from floating_todo.domain import DEFAULT_NOTIFICATION_STATE, Task

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app


def _qdatetime(value: datetime) -> QDateTime:
    return QDateTime.fromMSecsSinceEpoch(int(value.timestamp() * 1000), QTimeZone.utc())


def make_task() -> Task:
    now = datetime(2026, 5, 10, 8, 0, tzinfo=timezone.utc)
    return Task(
        id="existing-id",
        title="旧任务",
        priority="P2",
        effort_minutes=30,
        deadline=now + timedelta(hours=4),
        progress=40,
        status="done",
        created_at=now,
        updated_at=now + timedelta(minutes=1),
        completed_at=now + timedelta(hours=2),
        notes="旧备注",
        notification_state={"deadline_warning_sent": True, "deadline_due_sent": False},
    )


def test_new_dialog_builds_active_task_from_fields(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    deadline = datetime(2026, 5, 12, 10, 30, tzinfo=timezone.utc)
    dialog.title_edit.setText("  写测试  ")
    dialog.priority_combo.setCurrentIndex(dialog.priority_combo.findData("P1"))
    dialog.effort_spin.setValue(90)
    dialog.deadline_edit.setDateTime(_qdatetime(deadline))
    dialog.notes_edit.setPlainText("用中文备注")

    task = dialog.build_task()

    assert task.id
    assert task.title == "写测试"
    assert task.priority == "P1"
    assert task.effort_minutes == 90
    assert task.deadline == deadline
    assert task.progress == 0
    assert task.status == "active"
    assert task.completed_at is None
    assert task.notes == "用中文备注"
    assert task.created_at.tzinfo == timezone.utc
    assert task.updated_at.tzinfo == timezone.utc
    assert dict(task.notification_state) == DEFAULT_NOTIFICATION_STATE

    dialog.close()


def test_dialog_defaults_for_new_task(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    before = datetime.now(timezone.utc)
    dialog = TaskDialog()
    after = datetime.now(timezone.utc)

    assert dialog.windowTitle() == "新增任务"
    assert dialog.priority_combo.currentText() == "中"
    assert dialog.priority_combo.currentData() == "P2"
    assert dialog.effort_spin.minimum() == 0
    assert dialog.effort_spin.maximum() == 1440
    assert dialog.effort_spin.singleStep() == 15
    assert dialog.effort_spin.value() == 60
    assert dialog.effort_hour_input.value() == 1
    assert dialog.effort_minute_input.value() == 0
    assert dialog.effort_hour_input.accessibleName() == "预计工作量小时"
    assert dialog.effort_minute_input.accessibleName() == "预计工作量分钟"
    assert not hasattr(dialog, "effort_hint_label")
    assert not hasattr(dialog, "effort_step_hint_label")
    assert "增减 15 分钟" in dialog.effort_spin.toolTip()
    assert not hasattr(dialog, "progress_slider")
    assert not hasattr(dialog, "progress_spin")
    assert not hasattr(dialog, "progress_input")
    assert not hasattr(dialog, "progress_hint_label")
    assert not hasattr(dialog, "progress_step_hint_label")
    assert dialog.deadline_edit.calendarPopup()
    assert not hasattr(dialog, "priority_hint_label")
    assert not hasattr(dialog, "deadline_hint_label")
    assert dialog.deadline_date_input.calendarWidget().objectName() == "taskDeadlineCalendar"
    assert "#06111C" in dialog.deadline_date_input.calendarWidget().styleSheet()
    assert dialog.deadline_date_input.buttonSymbols() == QAbstractSpinBox.NoButtons
    assert "QAbstractItemView::item:selected" in dialog.deadline_date_input.calendarWidget().styleSheet()
    assert "qt_calendar_prevmonth" in dialog.deadline_date_input.calendarWidget().styleSheet()
    assert dialog.scroll_area.widgetResizable()
    assert dialog.title_counter_label.text() == "0/100"
    assert dialog.notes_counter_label.text() == "0/500"
    visible_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "P1 最优先" not in visible_text
    assert "每次 15 分钟" not in visible_text
    assert "日期、小时和分钟" not in visible_text
    assert "键盘" not in visible_text
    assert "手动进度" not in visible_text
    assert "日期" in visible_text
    assert "小时" in visible_text
    assert "分钟" in visible_text
    assert dialog.deadline_date_input.accessibleName() == "截止日期"
    assert dialog.deadline_hour_input.accessibleName() == "截止小时"
    assert dialog.deadline_minute_input.accessibleName() == "截止分钟"

    default_deadline = dialog.deadline_edit.dateTime().toUTC().toPython()
    if default_deadline.tzinfo is None:
        default_deadline = default_deadline.replace(tzinfo=timezone.utc)
    assert before + timedelta(minutes=55) <= default_deadline <= after + timedelta(minutes=65)

    dialog.close()


def test_dialog_accepts_parent_as_first_argument_for_new_task(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    parent = QMainWindow()
    dialog = TaskDialog(parent)

    assert dialog.parent() is parent
    assert dialog.task is None
    assert dialog.windowTitle() == "新增任务"

    dialog.close()
    parent.close()


def test_edit_dialog_preserves_identity_and_lifecycle_fields(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    existing = make_task()
    new_deadline = datetime(2026, 5, 13, 9, 15, tzinfo=timezone.utc)
    parent = QMainWindow()
    dialog = TaskDialog(parent, existing)
    dialog.title_edit.setText("  更新任务  ")
    dialog.priority_combo.setCurrentIndex(dialog.priority_combo.findData("P3"))
    dialog.effort_spin.setValue(120)
    dialog.deadline_edit.setDateTime(_qdatetime(new_deadline))
    dialog.notes_edit.setPlainText("新备注")

    updated = dialog.build_task()

    assert updated.id == existing.id
    assert updated.status == existing.status
    assert updated.created_at == existing.created_at
    assert updated.completed_at == existing.completed_at
    assert dict(updated.notification_state) == DEFAULT_NOTIFICATION_STATE
    assert updated.title == "更新任务"
    assert updated.priority == "P3"
    assert updated.effort_minutes == 120
    assert updated.deadline == new_deadline
    assert updated.progress == existing.progress
    assert updated.notes == "新备注"
    assert updated.updated_at > existing.updated_at

    dialog.close()
    parent.close()


def test_edit_dialog_preserves_notification_state_when_deadline_is_unchanged(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    existing = make_task()
    parent = QMainWindow()
    dialog = TaskDialog(parent, existing)
    dialog.title_edit.setText("只改标题")

    updated = dialog.build_task()

    assert updated.deadline == existing.deadline
    assert updated.notification_state == existing.notification_state

    dialog.close()
    parent.close()


def test_edit_dialog_displays_stored_deadline_in_local_time(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.task_dialog as task_dialog

    monkeypatch.setattr(task_dialog, "local_timezone", lambda: timezone(timedelta(hours=8)))
    existing = replace(make_task(), deadline=datetime(2026, 5, 12, 16, 45, tzinfo=timezone.utc))

    dialog = task_dialog.TaskDialog(None, existing)

    assert dialog.deadline_date_input.date().toPython().isoformat() == "2026-05-13"
    assert dialog.deadline_hour_input.currentText() == "00"
    assert dialog.deadline_minute_input.currentText() == "45"
    assert dialog.build_task().deadline == existing.deadline

    dialog.close()


def test_dialog_saves_selected_local_deadline_as_utc(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.task_dialog as task_dialog

    monkeypatch.setattr(task_dialog, "local_timezone", lambda: timezone(timedelta(hours=8)))
    dialog = task_dialog.TaskDialog()
    dialog.deadline_date_input.setDate(QDate(2026, 5, 14))
    dialog.deadline_hour_input.setCurrentText("09")
    dialog.deadline_minute_input.setCurrentText("30")

    task = dialog.build_task()

    assert task.deadline == datetime(2026, 5, 14, 1, 30, tzinfo=timezone.utc)

    dialog.close()


def test_effort_change_updates_deadline_from_current_local_time(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.task_dialog as task_dialog

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 5, 14, 9, 0, tzinfo=tz)

    monkeypatch.setattr(task_dialog, "datetime", FrozenDateTime)
    monkeypatch.setattr(task_dialog, "local_timezone", lambda: timezone(timedelta(hours=8)))
    dialog = task_dialog.TaskDialog()

    dialog.effort_spin.setValue(90)

    assert dialog.deadline_date_input.date().toPython().isoformat() == "2026-05-14"
    assert dialog.deadline_hour_input.currentText() == "10"
    assert dialog.deadline_minute_input.currentText() == "30"
    assert dialog.build_task().deadline == datetime(2026, 5, 14, 2, 30, tzinfo=timezone.utc)

    dialog.close()


def test_dialog_keeps_deadline_row_visible_and_uses_svg_icons(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.show()
    qapp.processEvents()

    assert dialog.scroll_area.horizontalScrollBar().maximum() == 0
    assert dialog.deadline_date_input.minimumWidth() >= 180
    assert dialog.panel.maximumWidth() < dialog.scroll_area.viewport().width()

    hero_icon = dialog.findChild(QLabel, "taskDialogHeroIcon")
    assert hero_icon is not None
    assert hero_icon.pixmap() is not None
    assert not hero_icon.pixmap().isNull()

    section_icons = dialog.findChildren(QLabel, "taskSectionIcon")
    assert len(section_icons) == 5
    assert all(icon.pixmap() is not None and not icon.pixmap().isNull() for icon in section_icons)
    preview_icons = dialog.findChildren(QLabel, "taskPriorityPreviewIcon")
    assert len(preview_icons) == 3
    assert all(icon.pixmap() is not None and not icon.pixmap().isNull() for icon in preview_icons)
    assert not dialog.priority_combo.itemIcon(0).isNull()
    assert not dialog.priority_combo.itemIcon(1).isNull()
    assert not dialog.priority_combo.itemIcon(2).isNull()

    dialog.close()


def test_deadline_calendar_allows_direct_year_edit_and_updates_task(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.title_input.setText("year-edit")
    dialog.deadline_date_input.setDate(QDate(2026, 5, 24))
    dialog.deadline_hour_input.setCurrentText("09")
    dialog.deadline_minute_input.setCurrentText("30")
    calendar = dialog.deadline_date_input.calendarWidget()
    calendar.show()
    qapp.processEvents()

    year_button = calendar.findChild(QToolButton, "qt_calendar_yearbutton")
    year_edit = calendar.findChild(QSpinBox, "qt_calendar_yearedit")
    assert year_button is not None
    assert year_edit is not None

    QTest.mouseClick(year_button, Qt.LeftButton)
    qapp.processEvents()
    assert not year_edit.isHidden()
    year_line_edit = year_edit.lineEdit()
    assert year_line_edit is not None
    year_line_edit.setFocus(Qt.OtherFocusReason)
    year_line_edit.selectAll()
    QTest.keyClicks(year_line_edit, "2028")
    QTest.keyClick(year_line_edit, Qt.Key_Return)
    qapp.processEvents()

    assert calendar.yearShown() == 2028
    assert dialog.deadline_date_input.date().year() == 2028
    assert dialog.build_task().deadline.year == 2028

    QTest.mouseClick(year_button, Qt.LeftButton)
    qapp.processEvents()
    year_edit.setValue(2031)
    year_line_edit.setFocus(Qt.OtherFocusReason)
    QTest.keyClick(year_line_edit, Qt.Key_Escape)
    qapp.processEvents()
    assert year_edit.isHidden()
    assert calendar.yearShown() == 2028
    assert dialog.deadline_date_input.date().year() == 2028

    dialog.close()


def test_deadline_controls_ignore_mouse_wheel_changes(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.show()
    qapp.processEvents()

    original_date = dialog.deadline_date_input.date()
    original_hour = dialog.deadline_hour_input.currentText()
    original_minute = dialog.deadline_minute_input.currentText()

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

    wheel(dialog.deadline_date_input)
    wheel(dialog.deadline_hour_input)
    wheel(dialog.deadline_minute_input)

    assert dialog.deadline_date_input.date() == original_date
    assert dialog.deadline_hour_input.currentText() == original_hour
    assert dialog.deadline_minute_input.currentText() == original_minute

    dialog.close()


def test_single_line_controls_can_submit_with_enter(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.title_input.setText("回车保存任务")
    called: list[bool] = []
    dialog.accept = lambda: called.append(True)  # type: ignore[method-assign]

    dialog.title_input.setFocus()
    QTest.keyClick(dialog.title_input, Qt.Key_Return)

    assert called == [True]
    dialog.close()


def test_notes_editor_keeps_enter_for_newline(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.title_input.setText("备注换行")
    called: list[bool] = []
    dialog.accept = lambda: called.append(True)  # type: ignore[method-assign]

    dialog.notes_input.setFocus()
    dialog.notes_input.setPlainText("第一行")
    QTest.keyClick(dialog.notes_input, Qt.Key_Return)

    assert called == []
    assert "\n" in dialog.notes_input.toPlainText()
    dialog.close()


def test_effort_hour_and_minute_inputs_build_total_minutes(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    dialog = TaskDialog()
    dialog.effort_hour_input.setValue(2)
    dialog.effort_minute_input.setValue(30)

    task = dialog.build_task()

    assert dialog.effort_spin.value() == 150
    assert task.effort_minutes == 150

    dialog.effort_spin.setValue(24 * 60)

    assert dialog.effort_hour_input.value() == 24
    assert dialog.effort_minute_input.value() == 0
    assert dialog.effort_minute_input.maximum() == 0

    dialog.close()


def test_edit_dialog_preserves_empty_deadline_when_unchanged(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    existing = replace(make_task(), deadline=None)
    parent = QMainWindow()
    dialog = TaskDialog(parent, existing)

    updated = dialog.build_task()

    assert updated.deadline is None

    dialog.close()
    parent.close()
