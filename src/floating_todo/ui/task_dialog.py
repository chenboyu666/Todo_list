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
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from floating_todo.domain import DEFAULT_NOTIFICATION_STATE, Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.controls import NoWheelSlider, NoWheelSpinBox
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
        self.priority_input.setToolTip("选择任务优先级：P1 最高，P3 较低")
        self.priority_input.setAccessibleName("任务优先级")
        self.priority_combo = self.priority_input
        self.effort_input = QSpinBox()
        self.effort_input.setRange(0, 24 * 60)
        self.effort_input.setSingleStep(15)
        self.effort_input.setSuffix(" min")
        self.effort_input.setToolTip("右侧箭头每次增减 15 分钟；修改后会按当前时间同步截止时间")
        self.effort_input.setAccessibleName("预计工作量分钟")
        self.effort_spin = self.effort_input

        self.deadline_date_input = QDateEdit()
        self.deadline_date_input.setCalendarPopup(True)
        self.deadline_date_input.setToolTip("选择截止日期")
        self.deadline_date_input.setAccessibleName("截止日期")
        self.deadline_hour_input = QComboBox()
        self.deadline_hour_input.addItems([f"{hour:02d}" for hour in range(24)])
        self.deadline_hour_input.setToolTip("选择截止小时")
        self.deadline_hour_input.setAccessibleName("截止小时")
        self.deadline_minute_input = QComboBox()
        self.deadline_minute_input.addItems([f"{minute:02d}" for minute in range(60)])
        self.deadline_minute_input.setToolTip("选择截止分钟")
        self.deadline_minute_input.setAccessibleName("截止分钟")

        self.progress_slider = NoWheelSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setToolTip("拖动调整任务完成进度")
        self.progress_slider.setAccessibleName("手动进度滑条")
        self.progress_value_input = NoWheelSpinBox()
        self.progress_value_input.setRange(0, 100)
        self.progress_value_input.setSuffix("%")
        self.progress_value_input.setAlignment(Qt.AlignCenter)
        self.progress_value_input.setFixedWidth(62)
        self.progress_value_input.setFixedHeight(26)
        self.progress_value_input.setToolTip("输入百分比，或用右侧箭头微调 1%")
        self.progress_value_input.setAccessibleName("手动进度百分比")
        self.progress_input = self.progress_value_input
        self.progress_spin = self.progress_value_input
        self.deadline_input = DeadlineInputAdapter(self)
        self.deadline_edit = self.deadline_input
        self.progress_label = self.progress_value_input
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("备注")
        self.notes_edit = self.notes_input

        self._build_ui()
        self._populate_fields(task)
        self.deadline_date_input.dateChanged.connect(self._mark_deadline_changed)
        self.deadline_hour_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.deadline_minute_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.effort_input.valueChanged.connect(self._sync_deadline_from_effort)
        self.progress_slider.valueChanged.connect(self._sync_progress_input_from_slider)
        self.progress_value_input.valueChanged.connect(self._sync_progress_slider_from_input)

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
        self.priority_hint_label = _hint_label("P1 最优先，P2 普通，P3 较低；只影响排序和优先级颜色。")
        form.addRow("", self.priority_hint_label)
        form.addRow("预计工作量", self.effort_input)
        self.effort_hint_label = _hint_label("右侧箭头可增减时间；每次 15 分钟。修改后会同步推算截止时间。")
        form.addRow("", self.effort_hint_label)

        deadline_layout = QVBoxLayout()
        deadline_layout.setSpacing(6)
        deadline_fields = QHBoxLayout()
        deadline_fields.setSpacing(8)
        deadline_fields.addWidget(_inline_label("日期"))
        deadline_fields.addWidget(self.deadline_date_input, 1)
        deadline_fields.addWidget(_inline_label("小时"))
        deadline_fields.addWidget(self.deadline_hour_input)
        deadline_fields.addWidget(_inline_label("分钟"))
        deadline_fields.addWidget(self.deadline_minute_input)
        self.deadline_hint_label = _hint_label("选择日期、小时和分钟；工作量变化时会自动带动这里更新。")
        deadline_layout.addLayout(deadline_fields)
        deadline_layout.addWidget(self.deadline_hint_label)
        form.addRow("截止时间", deadline_layout)

        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)
        progress_layout.addWidget(self.progress_slider, 1)
        self.progress_value_input.setStyleSheet(_progress_input_style())
        progress_layout.addWidget(self.progress_value_input)
        form.addRow("手动进度", progress_layout)
        self.progress_hint_label = _hint_label("可拖动滑条，也可以直接输入百分比；进度输入框右侧箭头每次增减 1%。")
        form.addRow("", self.progress_hint_label)
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
        self.progress_value_input.setValue(self.progress_slider.value())
        self.notes_input.setPlainText(task.notes if task else "")

    def _sync_progress_input_from_slider(self, value: int) -> None:
        self.progress_value_input.blockSignals(True)
        try:
            self.progress_value_input.setValue(value)
        finally:
            self.progress_value_input.blockSignals(False)

    def _sync_progress_slider_from_input(self, value: int) -> None:
        self.progress_slider.blockSignals(True)
        try:
            self.progress_slider.setValue(value)
        finally:
            self.progress_slider.blockSignals(False)

    def _progress_value(self) -> int:
        self.progress_value_input.interpretText()
        return self.progress_value_input.value()

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
                progress=self._progress_value(),
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
            progress=self._progress_value(),
            status="active",
            created_at=now,
            updated_at=now,
            completed_at=None,
            notes=self.notes_input.toPlainText(),
            notification_state=dict(DEFAULT_NOTIFICATION_STATE),
        )


def _progress_input_style() -> str:
    return (
        "QSpinBox {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #155E75, stop:0.55 #0E7490, stop:1 #047857);"
        "color: #ECFEFF;"
        "border: none;"
        "border-radius: 8px;"
        "font-weight: 800;"
        "padding: 1px 8px;"
        "selection-background-color: #1D4ED8;"
        "}"
        "QSpinBox:focus {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0E7490, stop:1 #16A34A);"
        "}"
        "QSpinBox::up-button, QSpinBox::down-button {"
        "width: 0px;"
        "border: none;"
        "}"
    )


def _hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName("taskDialogHint")
    label.setStyleSheet(
        "color: #8FA7B8;"
        "background: transparent;"
        "font-size: 12px;"
        "font-weight: 600;"
        "padding: 0 4px;"
    )
    return label


def _inline_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("taskDialogInlineLabel")
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        "color: #CDE5F6;"
        "background: #101A27;"
        "border: none;"
        "border-radius: 8px;"
        "padding: 6px 8px;"
        "font-weight: 800;"
    )
    return label
