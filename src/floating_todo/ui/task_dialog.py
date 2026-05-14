from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, time, timezone
from uuid import uuid4

from PySide6.QtCore import QDate, QDateTime, QTimeZone, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from floating_todo.domain import DEFAULT_NOTIFICATION_STATE, Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import apply_soft_shadow


def local_timezone():
    return datetime.now().astimezone().tzinfo or timezone.utc


def to_local_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(local_timezone())


class DeadlineInputAdapter:
    def __init__(self, dialog: "TaskDialog") -> None:
        self.dialog = dialog

    def setDateTime(self, value: QDateTime) -> None:
        self.dialog._set_deadline_fields(value.toPython())
        self.dialog._deadline_changed = True

    def dateTime(self) -> QDateTime:
        deadline = self.dialog._deadline()
        if deadline is None:
            return QDateTime.currentDateTime()
        return QDateTime.fromSecsSinceEpoch(int(deadline.timestamp()), QTimeZone.utc())

    def calendarPopup(self) -> bool:
        return self.dialog.deadline_date_input.calendarPopup()


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self._deadline_changed = False
        self.setWindowTitle("编辑任务" if task else "新增任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumWidth(460)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("任务名称")
        self.title_edit = self.title_input
        self.priority_input = QComboBox()
        self.priority_input.addItems(["P1", "P2", "P3"])
        self.priority_combo = self.priority_input
        self.effort_input = QSpinBox()
        self.effort_input.setRange(0, 24 * 60)
        self.effort_input.setSingleStep(15)
        self.effort_input.setSuffix(" min")
        self.effort_spin = self.effort_input

        self.deadline_date_input = QDateEdit()
        self.deadline_date_input.setCalendarPopup(True)
        self.deadline_hour_input = QComboBox()
        self.deadline_hour_input.addItems([f"{hour:02d}" for hour in range(24)])
        self.deadline_minute_input = QComboBox()
        self.deadline_minute_input.addItems([f"{minute:02d}" for minute in range(60)])

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_input = self.progress_slider
        self.progress_spin = self.progress_slider
        self.deadline_input = DeadlineInputAdapter(self)
        self.deadline_edit = self.deadline_input
        self.progress_label = QLabel("0%")
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("备注")
        self.notes_edit = self.notes_input

        self._build_ui()
        self._populate_fields(task)
        self.deadline_date_input.dateChanged.connect(self._mark_deadline_changed)
        self.deadline_hour_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.deadline_minute_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.effort_input.valueChanged.connect(self._sync_deadline_from_effort)
        self.progress_slider.valueChanged.connect(lambda value: self.progress_label.setText(f"{value}%"))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogTitleBar(self, self.windowTitle()))

        panel = QFrame()
        panel.setObjectName("taskDialogPanel")
        panel.setStyleSheet(
            "QFrame#taskDialogPanel {"
            f"background: {THEME_COLORS['surface']};"
            "border: none;"
            "border-radius: 8px;"
            "}"
        )
        apply_soft_shadow(panel, blur=34, y_offset=12, alpha=120)
        form = QFormLayout(panel)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(12)
        form.addRow("任务名称", self.title_input)
        form.addRow("优先级", self.priority_input)
        form.addRow("预计工作量", self.effort_input)

        deadline_layout = QHBoxLayout()
        deadline_layout.setSpacing(8)
        deadline_layout.addWidget(self.deadline_date_input, 1)
        deadline_layout.addWidget(self.deadline_hour_input)
        deadline_layout.addWidget(QLabel("时"))
        deadline_layout.addWidget(self.deadline_minute_input)
        deadline_layout.addWidget(QLabel("分"))
        form.addRow("截止时间", deadline_layout)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)
        progress_layout.addWidget(self.progress_slider, 1)
        self.progress_label.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        progress_layout.addWidget(self.progress_label)
        form.addRow("手动进度", progress_layout)
        form.addRow("备注", self.notes_input)
        layout.addWidget(panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        if buttons.button(QDialogButtonBox.Save):
            buttons.button(QDialogButtonBox.Save).setText("保存")
        if buttons.button(QDialogButtonBox.Cancel):
            buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate_fields(self, task: Task | None) -> None:
        default_deadline = datetime.now(local_timezone()).replace(second=0, microsecond=0) + timedelta(hours=1)
        deadline = task.deadline if task and task.deadline else default_deadline
        deadline = to_local_datetime(deadline)

        self.title_input.setText(task.title if task else "")
        self.priority_input.setCurrentText(task.priority if task else "P2")
        self.effort_input.setValue(task.effort_minutes if task else 60)
        self.deadline_date_input.setDate(QDate(deadline.year, deadline.month, deadline.day))
        self.deadline_hour_input.setCurrentText(f"{deadline.hour:02d}")
        self.deadline_minute_input.setCurrentText(f"{deadline.minute:02d}")
        self.progress_slider.setValue(task.progress if task else 0)
        self.progress_label.setText(f"{self.progress_slider.value()}%")
        self.notes_input.setPlainText(task.notes if task else "")

    def _mark_deadline_changed(self, *args) -> None:
        self._deadline_changed = True

    def _set_deadline_fields(self, deadline: datetime) -> None:
        deadline = to_local_datetime(deadline)
        self.deadline_date_input.blockSignals(True)
        self.deadline_hour_input.blockSignals(True)
        self.deadline_minute_input.blockSignals(True)
        try:
            self.deadline_date_input.setDate(QDate(deadline.year, deadline.month, deadline.day))
            self.deadline_hour_input.setCurrentText(f"{deadline.hour:02d}")
            self.deadline_minute_input.setCurrentText(f"{deadline.minute:02d}")
        finally:
            self.deadline_date_input.blockSignals(False)
            self.deadline_hour_input.blockSignals(False)
            self.deadline_minute_input.blockSignals(False)

    def _sync_deadline_from_effort(self, minutes: int) -> None:
        base = datetime.now(local_timezone()).replace(second=0, microsecond=0)
        self._set_deadline_fields(base + timedelta(minutes=max(0, int(minutes))))
        self._deadline_changed = True

    def _deadline(self) -> datetime | None:
        if self.task and self.task.deadline is None and not self._deadline_changed:
            return None
        selected_date = self.deadline_date_input.date().toPython()
        selected_time = time(
            hour=int(self.deadline_hour_input.currentText()),
            minute=int(self.deadline_minute_input.currentText()),
            tzinfo=local_timezone(),
        )
        return datetime.combine(selected_date, selected_time).astimezone(timezone.utc)

    def build_task(self) -> Task:
        now = datetime.now(timezone.utc)
        title = self.title_input.text().strip()
        if self.task:
            deadline = self._deadline()
            notification_state = (
                dict(DEFAULT_NOTIFICATION_STATE)
                if deadline != self.task.deadline
                else self.task.notification_state
            )
            return replace(
                self.task,
                title=title,
                priority=self.priority_input.currentText(),
                effort_minutes=self.effort_input.value(),
                deadline=deadline,
                progress=self.progress_slider.value(),
                updated_at=now,
                notes=self.notes_input.toPlainText(),
                notification_state=notification_state,
            )
        return Task(
            id=str(uuid4()),
            title=title,
            priority=self.priority_input.currentText(),
            effort_minutes=self.effort_input.value(),
            deadline=self._deadline(),
            progress=self.progress_slider.value(),
            status="active",
            created_at=now,
            updated_at=now,
            completed_at=None,
            notes=self.notes_input.toPlainText(),
            notification_state=dict(DEFAULT_NOTIFICATION_STATE),
        )
