from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import QDate, QDateTime, QTimeZone
from PySide6.QtWidgets import QApplication, QMainWindow

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
    dialog.priority_combo.setCurrentText("P1")
    dialog.effort_spin.setValue(90)
    dialog.deadline_edit.setDateTime(_qdatetime(deadline))
    dialog.progress_spin.setValue(25)
    dialog.notes_edit.setPlainText("用中文备注")

    task = dialog.build_task()

    assert task.id
    assert task.title == "写测试"
    assert task.priority == "P1"
    assert task.effort_minutes == 90
    assert task.deadline == deadline
    assert task.progress == 25
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
    assert dialog.priority_combo.currentText() == "P2"
    assert dialog.effort_spin.minimum() == 0
    assert dialog.effort_spin.maximum() == 1440
    assert dialog.effort_spin.singleStep() == 15
    assert dialog.effort_spin.value() == 60
    assert "每次 15 分钟" in dialog.effort_hint_label.text()
    assert "↑ 增加 15 分钟" in dialog.effort_step_hint_label.text()
    assert "↓ 减少 15 分钟" in dialog.effort_step_hint_label.text()
    assert "增减 15 分钟" in dialog.effort_spin.toolTip()
    assert dialog.progress_spin.minimum() == 0
    assert dialog.progress_spin.maximum() == 100
    assert "每次增减 1%" in dialog.progress_hint_label.text()
    assert "↑ +1%" in dialog.progress_step_hint_label.text()
    assert "↓ -1%" in dialog.progress_step_hint_label.text()
    assert dialog.deadline_edit.calendarPopup()
    assert "日期、小时和分钟" in dialog.deadline_hint_label.text()
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
    dialog.priority_combo.setCurrentText("P3")
    dialog.effort_spin.setValue(120)
    dialog.deadline_edit.setDateTime(_qdatetime(new_deadline))
    dialog.progress_spin.setValue(70)
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
    assert updated.progress == 70
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


def test_edit_dialog_preserves_empty_deadline_when_unchanged(qapp: QApplication) -> None:
    from floating_todo.ui.task_dialog import TaskDialog

    existing = replace(make_task(), deadline=None)
    parent = QMainWindow()
    dialog = TaskDialog(parent, existing)

    updated = dialog.build_task()

    assert updated.deadline is None

    dialog.close()
    parent.close()
