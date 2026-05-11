from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from floating_todo.domain import DEFAULT_NOTIFICATION_STATE, Task


class TaskDialog(QDialog):
    def __init__(self, task: Task | None = None, parent: object | None = None) -> None:
        super().__init__(parent)
        self.task = task

        self.title_edit = QLineEdit()
        self.priority_combo = QComboBox()
        self.effort_spin = QSpinBox()
        self.deadline_edit = QDateTimeEdit()
        self.progress_spin = QSpinBox()
        self.notes_edit = QTextEdit()

        self._build_ui()
        self._populate_fields()

    def _build_ui(self) -> None:
        self.setWindowTitle("编辑任务" if self.task is not None else "新增任务")

        self.title_edit.setPlaceholderText("任务名称")
        self.title_edit.setToolTip("任务名称")

        self.priority_combo.addItems(["P1", "P2", "P3"])
        self.priority_combo.setToolTip("优先级")

        self.effort_spin.setRange(0, 1440)
        self.effort_spin.setSingleStep(15)
        self.effort_spin.setSuffix(" min")
        self.effort_spin.setToolTip("预计工作量")

        self.deadline_edit.setCalendarPopup(True)
        self.deadline_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.deadline_edit.setToolTip("截止时间")

        self.progress_spin.setRange(0, 100)
        self.progress_spin.setSuffix("%")
        self.progress_spin.setToolTip("手动进度")

        self.notes_edit.setPlaceholderText("备注")
        self.notes_edit.setToolTip("备注")

        form = QFormLayout()
        form.addRow("任务名称", self.title_edit)
        form.addRow("优先级", self.priority_combo)
        form.addRow("预计工作量", self.effort_spin)
        form.addRow("截止时间", self.deadline_edit)
        form.addRow("手动进度", self.progress_spin)
        form.addRow("备注", self.notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText("新增" if self.task is None else "保存")
        if cancel_button is not None:
            cancel_button.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _populate_fields(self) -> None:
        task = self.task
        if task is None:
            self.priority_combo.setCurrentText("P2")
            self.effort_spin.setValue(60)
            self.deadline_edit.setDateTime(_qdatetime_from_utc(datetime.now(timezone.utc) + timedelta(hours=1)))
            self.progress_spin.setValue(0)
            return

        self.title_edit.setText(task.title)
        self.priority_combo.setCurrentText(task.priority)
        self.effort_spin.setValue(task.effort_minutes)
        deadline = task.deadline or datetime.now(timezone.utc) + timedelta(hours=1)
        self.deadline_edit.setDateTime(_qdatetime_from_utc(deadline))
        self.progress_spin.setValue(task.progress)
        self.notes_edit.setPlainText(task.notes)

    def build_task(self) -> Task:
        now = datetime.now(timezone.utc)
        title = self.title_edit.text().strip()
        priority = self.priority_combo.currentText()
        effort = self.effort_spin.value()
        deadline = _datetime_from_qdatetime(self.deadline_edit.dateTime())
        progress = self.progress_spin.value()
        notes = self.notes_edit.toPlainText()

        if self.task is not None:
            return replace(
                self.task,
                title=title,
                priority=priority,  # type: ignore[arg-type]
                effort_minutes=effort,
                deadline=deadline,
                progress=progress,
                updated_at=now,
                notes=notes,
            )

        return Task(
            id=str(uuid4()),
            title=title,
            priority=priority,  # type: ignore[arg-type]
            effort_minutes=effort,
            deadline=deadline,
            progress=progress,
            status="active",
            created_at=now,
            updated_at=now,
            completed_at=None,
            notes=notes,
            notification_state=dict(DEFAULT_NOTIFICATION_STATE),
        )


def _qdatetime_from_utc(value: datetime) -> QDateTime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    timestamp_ms = int(value.astimezone(timezone.utc).timestamp() * 1000)
    return QDateTime.fromMSecsSinceEpoch(timestamp_ms, QTimeZone.utc())


def _datetime_from_qdatetime(value: QDateTime) -> datetime:
    result = value.toUTC().toPython()
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)
