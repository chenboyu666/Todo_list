from __future__ import annotations

from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QDate, QDateTime, QEvent, QSize, QTimeZone, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import DEFAULT_NOTIFICATION_STATE, DEFAULT_TASK_TAG, TASK_TAG_PRESETS, Task, normalize_task_tag
from floating_todo.ui.date_controls import NoWheelComboBox, NoWheelDateEdit, NoWheelSpinBox, apply_dark_calendar_popup
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import apply_soft_shadow
from floating_todo.view_models import PRIORITY_ORDER, priority_from_display, priority_text

UI_ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "ui"
MAX_EFFORT_HOURS = 999
MAX_EFFORT_MINUTES = MAX_EFFORT_HOURS * 60 + 59
CUSTOM_TASK_TAG_LABEL = "自定义"
DEFAULT_NEW_TASK_TAG = "工作"


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


class EffortInputAdapter:
    def __init__(self, dialog: "TaskDialog") -> None:
        self.dialog = dialog

    def setValue(self, minutes: int) -> None:
        self.dialog._set_effort_fields(minutes)
        self.dialog._sync_deadline_from_effort()

    def value(self) -> int:
        return self.dialog._effort_minutes()

    def minimum(self) -> int:
        return 0

    def maximum(self) -> int:
        return MAX_EFFORT_MINUTES

    def singleStep(self) -> int:
        return self.dialog.effort_minute_input.singleStep()

    def toolTip(self) -> str:
        return self.dialog.effort_minute_input.toolTip()


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task | None = None) -> None:
        super().__init__(parent)
        self.task = task
        self._deadline_changed = False
        self.setWindowTitle("编辑任务" if task else "新增任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(900, 860)
        self.resize(980, 1040)

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("请输入任务名称")
        self.title_input.setMaxLength(100)
        self.title_edit = self.title_input

        self.tag_input = NoWheelComboBox()
        self.tag_input.setObjectName("taskTagCombo")
        for tag in TASK_TAG_PRESETS:
            self.tag_input.addItem(tag, tag)
        self.tag_input.addItem(CUSTOM_TASK_TAG_LABEL, CUSTOM_TASK_TAG_LABEL)
        self.tag_input.setToolTip("给任务选择一个标签，便于历史统计按类型观察耗时")
        self.tag_input.setAccessibleName("任务标签")
        self.tag_combo = self.tag_input

        self.custom_tag_input = QLineEdit()
        self.custom_tag_input.setObjectName("taskCustomTagInput")
        self.custom_tag_input.setPlaceholderText("输入自定义标签")
        self.custom_tag_input.setMaxLength(24)
        self.custom_tag_input.setToolTip("输入自定义任务标签")
        self.custom_tag_input.setAccessibleName("自定义任务标签")

        self.priority_input = NoWheelComboBox()
        self.priority_input.setIconSize(QSize(16, 16))
        for priority in PRIORITY_ORDER:
            self.priority_input.addItem(
                QIcon(str(UI_ICON_DIR / _priority_icon_name(priority))),
                priority_text(priority),
                priority,
            )
        self.priority_input.setToolTip("选择任务优先级，高优先级会以更醒目的颜色显示")
        self.priority_input.setAccessibleName("任务优先级")
        self.priority_combo = self.priority_input

        self.effort_hour_input = NoWheelSpinBox()
        self.effort_hour_input.setRange(0, MAX_EFFORT_HOURS)
        self.effort_hour_input.setSuffix(" 小时")
        self.effort_hour_input.setToolTip("右侧按钮每次增减 1 小时，最多可设置 999 小时")
        self.effort_hour_input.setAccessibleName("预计工作量小时")

        self.effort_minute_input = NoWheelSpinBox()
        self.effort_minute_input.setRange(0, 59)
        self.effort_minute_input.setSingleStep(15)
        self.effort_minute_input.setSuffix(" 分钟")
        self.effort_minute_input.setToolTip("右侧按钮每次增减 15 分钟，修改后会按当前时间同步截止时间")
        self.effort_minute_input.setAccessibleName("预计工作量分钟")
        self.effort_input = EffortInputAdapter(self)
        self.effort_spin = self.effort_input

        self.deadline_date_input = NoWheelDateEdit()
        self.deadline_date_input.setCalendarPopup(True)
        self.deadline_date_input.setDisplayFormat("yyyy-MM-dd")
        self.deadline_date_input.setMinimumWidth(206)
        self.deadline_date_input.setMaximumWidth(236)
        self.deadline_date_input.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        apply_dark_calendar_popup(self.deadline_date_input, "taskDeadlineCalendar")
        self.deadline_date_input.setToolTip("选择截止日期")
        self.deadline_date_input.setAccessibleName("截止日期")

        self.deadline_hour_input = NoWheelComboBox()
        self.deadline_hour_input.addItems([f"{hour:02d}" for hour in range(24)])
        self.deadline_hour_input.setMinimumWidth(86)
        self.deadline_hour_input.setToolTip("选择截止小时")
        self.deadline_hour_input.setAccessibleName("截止小时")

        self.deadline_minute_input = NoWheelComboBox()
        self.deadline_minute_input.addItems([f"{minute:02d}" for minute in range(60)])
        self.deadline_minute_input.setMinimumWidth(86)
        self.deadline_minute_input.setToolTip("选择截止分钟")
        self.deadline_minute_input.setAccessibleName("截止分钟")

        self.deadline_input = DeadlineInputAdapter(self)
        self.deadline_edit = self.deadline_input

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("添加备注信息（可选）")
        self.notes_edit = self.notes_input

        self.save_button = QPushButton("保存任务" if task is None else "保存修改")
        self.save_button.setObjectName("taskDialogSaveButton")
        self.save_button.setProperty("effectVariant", "primary")
        self.save_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("taskDialogCancelButton")
        self.cancel_button.setProperty("effectVariant", "secondary")
        self.cancel_button.clicked.connect(self.reject)

        self._build_ui()
        self._populate_fields(task)
        self._sync_counters()

        self.deadline_date_input.dateChanged.connect(self._mark_deadline_changed)
        self.deadline_hour_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.deadline_minute_input.currentTextChanged.connect(self._mark_deadline_changed)
        self.tag_input.currentIndexChanged.connect(self._sync_custom_tag_visibility)
        self.effort_hour_input.valueChanged.connect(self._sync_effort_from_fields)
        self.effort_minute_input.valueChanged.connect(self._sync_effort_from_fields)
        self.title_input.textChanged.connect(self._sync_counters)
        self.notes_input.textChanged.connect(self._sync_counters)
        self._install_submit_shortcuts()

    def accept(self) -> None:
        if not self.title_input.text().strip():
            self.title_input.setFocus(Qt.OtherFocusReason)
            return
        super().accept()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if watched is self.notes_input or self.notes_input.isAncestorOf(watched):
                return False
            popup_visible = False
            if watched in {self.priority_input, self.tag_input, self.deadline_hour_input, self.deadline_minute_input}:
                popup_visible = watched.view().isVisible()
            if watched is self.deadline_date_input:
                calendar = self.deadline_date_input.calendarWidget()
                popup_visible = calendar is not None and calendar.isVisible()
            if popup_visible:
                return False
            self.accept()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _build_ui(self) -> None:
        self.setStyleSheet(_task_dialog_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.title_bar = DialogTitleBar(self, self.windowTitle())
        self.title_bar.setObjectName("taskDialogTitleBar")
        root.addWidget(self.title_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("taskDialogScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.verticalScrollBar().setSingleStep(32)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(lambda *_: self._sync_panel_width())

        scroll_content = QWidget()
        self.scroll_content = scroll_content
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        panel = QFrame()
        self.panel = panel
        panel.setObjectName("taskDialogPanel")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        apply_soft_shadow(panel, blur=34, y_offset=12, alpha=120)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(12)

        hero = QHBoxLayout()
        hero.setContentsMargins(0, 0, 0, 4)
        hero.setSpacing(14)

        accent = QFrame()
        accent.setObjectName("taskDialogAccent")
        accent.setFixedSize(5, 54)
        hero.addWidget(accent, 0, Qt.AlignTop)

        hero_icon = QLabel("")
        hero_icon.setObjectName("taskDialogHeroIcon")
        hero_icon.setAlignment(Qt.AlignCenter)
        hero_icon.setFixedSize(48, 48)
        hero_icon.setPixmap(
            QIcon(str(UI_ICON_DIR / ("task-add.svg" if self.task is None else "task-edit.svg"))).pixmap(QSize(22, 22))
        )
        hero.addWidget(hero_icon, 0, Qt.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setContentsMargins(0, 0, 0, 0)
        hero_text.setSpacing(3)
        hero_title = QLabel(self.windowTitle())
        hero_title.setObjectName("taskDialogHeroTitle")
        hero_subtitle = QLabel("创建并规划您的任务，让工作井井有条")
        hero_subtitle.setObjectName("taskDialogHeroSubtitle")
        hero_subtitle.setWordWrap(True)
        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_subtitle)
        hero.addLayout(hero_text, 1)
        panel_layout.addLayout(hero)

        divider = QFrame()
        divider.setObjectName("taskDialogDivider")
        divider.setFixedHeight(1)
        panel_layout.addWidget(divider)

        title_section = _section_card("任务名称", "task-title.svg", "taskSectionTitle")
        title_section.layout().addWidget(self.title_input)
        self.title_counter_label = QLabel("0/100")
        self.title_counter_label.setObjectName("taskDialogCounter")
        title_section.layout().addWidget(self.title_counter_label, 0, Qt.AlignRight)
        title_hint = QLabel("简洁明确的任务名称有助于更好地管理和跟踪任务")
        title_hint.setObjectName("taskDialogHint")
        title_hint.setWordWrap(True)
        title_section.layout().addWidget(title_hint)
        panel_layout.addWidget(title_section)

        tag_section = _section_card("任务标签", "record-note.svg", "taskSectionTag")
        tag_layout = QHBoxLayout()
        tag_layout.setContentsMargins(0, 0, 0, 0)
        tag_layout.setSpacing(10)
        tag_layout.addWidget(self.tag_input, 1)
        tag_layout.addWidget(self.custom_tag_input, 1)
        tag_section.layout().addLayout(tag_layout)
        tag_hint = QLabel("标签会进入历史统计，用来观察不同类型任务的数量和耗时占比")
        tag_hint.setObjectName("taskDialogHint")
        tag_hint.setWordWrap(True)
        tag_section.layout().addWidget(tag_hint)
        panel_layout.addWidget(tag_section)

        priority_section = _section_card("优先级", "task-priority.svg", "taskSectionPriority")
        priority_grid = QGridLayout()
        priority_grid.setContentsMargins(0, 0, 0, 0)
        priority_grid.setHorizontalSpacing(8)
        priority_grid.setVerticalSpacing(8)
        priority_grid.addWidget(_priority_preview("高", "紧急且重要", "P1"), 0, 0)
        priority_grid.addWidget(_priority_preview("中", "重要但不紧急", "P2"), 0, 1)
        priority_grid.addWidget(_priority_preview("低", "可延后处理", "P3"), 0, 2)
        priority_grid.addWidget(self.priority_input, 1, 0, 1, 3)
        priority_section.layout().addLayout(priority_grid)
        priority_hint = QLabel("设置优先级有助于合理安排任务顺序")
        priority_hint.setObjectName("taskDialogHint")
        priority_hint.setWordWrap(True)
        priority_section.layout().addWidget(priority_hint)
        panel_layout.addWidget(priority_section)

        effort_section = _section_card("预计工作量", "task-effort.svg", "taskSectionEffort")
        effort_layout = QHBoxLayout()
        effort_layout.setContentsMargins(0, 0, 0, 0)
        effort_layout.setSpacing(12)
        effort_layout.addWidget(_field_group("小时", self.effort_hour_input), 1)
        effort_layout.addWidget(_field_group("分钟", self.effort_minute_input), 1)
        effort_section.layout().addLayout(effort_layout)
        effort_hint = QLabel("预计完成该任务所需的时间，便于合理规划")
        effort_hint.setObjectName("taskDialogHint")
        effort_hint.setWordWrap(True)
        effort_section.layout().addWidget(effort_hint)

        deadline_section = _section_card("截止时间", "task-deadline.svg", "taskSectionDeadline")
        deadline_layout = QVBoxLayout()
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_layout.setSpacing(8)
        deadline_layout.addWidget(_field_group("日期", self.deadline_date_input, compact=True))
        deadline_layout.addWidget(_field_group("时间", _time_pair(self.deadline_hour_input, self.deadline_minute_input)))
        deadline_section.layout().addLayout(deadline_layout)
        deadline_hint = QLabel("设置截止时间有助于按时完成任务")
        deadline_hint.setObjectName("taskDialogHint")
        deadline_hint.setWordWrap(True)
        deadline_section.layout().addWidget(deadline_hint)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(12)
        meta_row.addWidget(effort_section, 5)
        meta_row.addWidget(deadline_section, 7)
        panel_layout.addLayout(meta_row)

        notes_section = _section_card("备注", "task-note.svg", "taskSectionNotes")
        self.notes_input.setMinimumHeight(96)
        self.notes_input.setMaximumHeight(120)
        notes_section.layout().addWidget(self.notes_input)
        self.notes_counter_label = QLabel("0/500")
        self.notes_counter_label.setObjectName("taskDialogCounter")
        notes_section.layout().addWidget(self.notes_counter_label, 0, Qt.AlignRight)
        notes_hint = QLabel("补充说明、相关信息或注意事项")
        notes_hint.setObjectName("taskDialogHint")
        notes_hint.setWordWrap(True)
        notes_section.layout().addWidget(notes_hint)
        panel_layout.addWidget(notes_section)

        scroll_layout.addWidget(panel)
        self.scroll_area.setWidget(scroll_content)
        root.addWidget(self.scroll_area, 1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(12)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        root.addLayout(buttons)
        self._sync_panel_width()

    def _install_submit_shortcuts(self) -> None:
        watched = [
            self.title_input,
            self.tag_input,
            self.custom_tag_input,
            self.priority_input,
            self.effort_hour_input,
            self.effort_minute_input,
            self.deadline_date_input,
            self.deadline_hour_input,
            self.deadline_minute_input,
        ]
        for widget in watched:
            widget.installEventFilter(self)
            line_edit = getattr(widget, "lineEdit", lambda: None)()
            if line_edit is not None:
                line_edit.installEventFilter(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_panel_width()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_panel_width()

    def _sync_panel_width(self) -> None:
        panel = getattr(self, "panel", None)
        scroll_area = getattr(self, "scroll_area", None)
        if panel is None or scroll_area is None:
            return
        viewport_width = max(0, scroll_area.viewport().width())
        if viewport_width:
            scrollbar = scroll_area.verticalScrollBar()
            reserve = scrollbar.sizeHint().width() + 8 if scrollbar.maximum() > 0 else 4
            panel.setMaximumWidth(max(0, viewport_width - reserve))

    def _populate_fields(self, task: Task | None) -> None:
        default_deadline = datetime.now(local_timezone()).replace(second=0, microsecond=0) + timedelta(hours=1)
        deadline = task.deadline if task and task.deadline else default_deadline
        deadline = to_local_datetime(deadline)

        self.title_input.setText(task.title if task else "")
        self._set_tag_value(task.tag if task else DEFAULT_NEW_TASK_TAG)
        self._set_priority_value(task.priority if task else "P2")
        self._set_effort_fields(task.effort_minutes if task else 60)
        self.deadline_date_input.setDate(QDate(deadline.year, deadline.month, deadline.day))
        self.deadline_hour_input.setCurrentText(f"{deadline.hour:02d}")
        self.deadline_minute_input.setCurrentText(f"{deadline.minute:02d}")
        self.notes_input.setPlainText(task.notes if task else "")

    def _sync_counters(self) -> None:
        self.title_counter_label.setText(f"{len(self.title_input.text().strip())}/100")
        self.notes_counter_label.setText(f"{len(self.notes_input.toPlainText().strip())}/500")

    def _selected_priority(self) -> str:
        data = self.priority_input.currentData()
        return priority_from_display(str(data if data is not None else self.priority_input.currentText()))

    def _selected_tag(self) -> str:
        data = str(self.tag_input.currentData() or self.tag_input.currentText())
        if data == CUSTOM_TASK_TAG_LABEL:
            return normalize_task_tag(self.custom_tag_input.text() or DEFAULT_TASK_TAG)
        return normalize_task_tag(data)

    def _set_tag_value(self, tag: str) -> None:
        normalized = normalize_task_tag(tag)
        index = self.tag_input.findData(normalized)
        if index >= 0:
            self.tag_input.setCurrentIndex(index)
            self.custom_tag_input.clear()
        else:
            custom_index = self.tag_input.findData(CUSTOM_TASK_TAG_LABEL)
            self.tag_input.setCurrentIndex(custom_index if custom_index >= 0 else self.tag_input.count() - 1)
            self.custom_tag_input.setText(normalized)
        self._sync_custom_tag_visibility()

    def _sync_custom_tag_visibility(self, *args) -> None:
        is_custom = self.tag_input.currentData() == CUSTOM_TASK_TAG_LABEL
        self.custom_tag_input.setVisible(is_custom)
        self.custom_tag_input.setEnabled(is_custom)

    def _set_priority_value(self, priority: str) -> None:
        index = self.priority_input.findData(priority_from_display(priority))
        fallback = self.priority_input.findData("P2")
        self.priority_input.setCurrentIndex(index if index >= 0 else max(0, fallback))

    def _progress_value(self) -> int:
        return self.task.progress if self.task else 0

    def _effort_minutes(self) -> int:
        self.effort_hour_input.interpretText()
        self.effort_minute_input.interpretText()
        return min(MAX_EFFORT_MINUTES, max(0, self.effort_hour_input.value() * 60 + self.effort_minute_input.value()))

    def _set_effort_fields(self, minutes: int) -> None:
        total_minutes = min(MAX_EFFORT_MINUTES, max(0, int(minutes)))
        hours, remainder = divmod(total_minutes, 60)
        self.effort_hour_input.blockSignals(True)
        self.effort_minute_input.blockSignals(True)
        try:
            self.effort_hour_input.setValue(hours)
            self._apply_effort_minute_bounds()
            self.effort_minute_input.setValue(remainder)
        finally:
            self.effort_hour_input.blockSignals(False)
            self.effort_minute_input.blockSignals(False)

    def _apply_effort_minute_bounds(self) -> None:
        maximum = 59
        if self.effort_minute_input.maximum() != maximum:
            self.effort_minute_input.setMaximum(maximum)

    def _sync_effort_from_fields(self, *args) -> None:
        self._apply_effort_minute_bounds()
        self._sync_deadline_from_effort()

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

    def _sync_deadline_from_effort(self, *args) -> None:
        base = datetime.now(local_timezone()).replace(second=0, microsecond=0)
        self._set_deadline_fields(base + timedelta(minutes=self._effort_minutes()))
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
                dict(DEFAULT_NOTIFICATION_STATE) if deadline != self.task.deadline else self.task.notification_state
            )
            return replace(
                self.task,
                title=title,
                tag=self._selected_tag(),
                priority=self._selected_priority(),
                effort_minutes=self._effort_minutes(),
                deadline=deadline,
                progress=self._progress_value(),
                updated_at=now,
                notes=self.notes_input.toPlainText(),
                notification_state=notification_state,
            )
        return Task(
            id=str(uuid4()),
            title=title,
            tag=self._selected_tag(),
            priority=self._selected_priority(),
            effort_minutes=self._effort_minutes(),
            deadline=self._deadline(),
            progress=self._progress_value(),
            status="active",
            created_at=now,
            updated_at=now,
            completed_at=None,
            work_started_at=now,
            notes=self.notes_input.toPlainText(),
            notification_state=dict(DEFAULT_NOTIFICATION_STATE),
        )


def _section_card(title: str, icon_name: str, object_name: str) -> QFrame:
    section = QFrame()
    section.setObjectName(object_name)
    section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    layout = QVBoxLayout(section)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(10)

    badge = QLabel("")
    badge.setObjectName("taskSectionIcon")
    badge.setAlignment(Qt.AlignCenter)
    badge.setFixedSize(34, 34)
    badge.setPixmap(QIcon(str(UI_ICON_DIR / icon_name)).pixmap(QSize(16, 16)))
    header.addWidget(badge, 0, Qt.AlignTop)

    title_label = QLabel(title)
    title_label.setObjectName("taskSectionLabel")
    header.addWidget(title_label)
    header.addStretch(1)
    layout.addLayout(header)
    return section


def _field_group(label_text: str, control: QWidget, *, compact: bool = False) -> QFrame:
    frame = QFrame()
    frame.setObjectName("taskFieldGroup")
    if compact:
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        frame.setMinimumWidth(314)
        frame.setMaximumWidth(346)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(10, 9, 10, 9)
    layout.setSpacing(10)

    label = QLabel(label_text)
    label.setObjectName("taskFieldGroupLabel")
    label.setAlignment(Qt.AlignCenter)
    label.setFixedWidth(56)
    layout.addWidget(label)
    layout.addWidget(control, 0 if compact else 1)
    if compact:
        layout.addStretch(1)
    return frame


def _time_pair(hour_input: NoWheelComboBox, minute_input: NoWheelComboBox) -> QWidget:
    container = QWidget()
    container.setObjectName("taskDialogTimePair")
    container.setMinimumWidth(210)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    hour_input.setMinimumWidth(72)
    minute_input.setMinimumWidth(72)
    layout.addWidget(hour_input, 1)
    hour_unit = _time_unit_label("时")
    layout.addWidget(hour_unit)
    layout.addWidget(minute_input, 1)
    minute_unit = _time_unit_label("分")
    layout.addWidget(minute_unit)
    return container


def _time_unit_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("taskDialogTimeUnit")
    label.setAlignment(Qt.AlignCenter)
    label.setFixedWidth(22)
    return label


def _priority_icon_name(priority: str) -> str:
    return {
        "P1": "priority-high.svg",
        "P2": "priority-medium.svg",
        "P3": "priority-low.svg",
    }.get(priority, "priority-medium.svg")


def _priority_preview(title: str, subtitle: str, priority: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName(f"taskPriorityPreview{priority}")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setFixedHeight(72)

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(5)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(8)

    icon = QLabel("")
    icon.setObjectName("taskPriorityPreviewIcon")
    icon.setAlignment(Qt.AlignCenter)
    icon.setFixedSize(26, 26)
    icon.setPixmap(QIcon(str(UI_ICON_DIR / _priority_icon_name(priority))).pixmap(QSize(14, 14)))
    header.addWidget(icon, 0, Qt.AlignLeft | Qt.AlignVCenter)

    title_label = QLabel(title)
    title_label.setObjectName("taskPriorityPreviewTitle")
    title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.addWidget(title_label, 1)
    layout.addLayout(header)

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("taskPriorityPreviewSubtitle")
    subtitle_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    layout.addWidget(subtitle_label)
    return frame


def _task_dialog_style() -> str:
    return f"""
QDialog {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #020A13,
    stop:0.52 #041323,
    stop:1 #06202B);
}}
QScrollArea#taskDialogScrollArea {{
  background: transparent;
  border: none;
}}
QFrame#taskDialogPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #061321,
    stop:0.48 #08243A,
    stop:1 #06313B);
  border: 1px solid rgba(112, 171, 196, 40);
  border-radius: 20px;
}}
QFrame#taskDialogTitleBar {{
  background: transparent;
  border: none;
}}
QFrame#taskDialogAccent {{
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #22D3EE,
    stop:1 #0F766E);
  border: none;
  border-radius: 2px;
}}
QFrame#taskDialogDivider {{
  background: rgba(111, 162, 189, 34);
  border: none;
}}
QLabel#taskDialogHeroIcon {{
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.7,
    fx:0.5, fy:0.5,
    stop:0 #0E7490,
    stop:1 #0A2540);
  border: 1px solid rgba(125, 211, 252, 32);
  border-radius: 14px;
}}
QLabel#taskDialogHeroTitle {{
  color: #F8FBFF;
  font-size: 22px;
  font-weight: 900;
}}
QLabel#taskDialogHeroSubtitle {{
  color: #91A8BD;
  font-size: 14px;
  font-weight: 700;
}}
QFrame#taskSectionTitle,
QFrame#taskSectionTag,
QFrame#taskSectionPriority,
QFrame#taskSectionEffort,
QFrame#taskSectionDeadline,
QFrame#taskSectionNotes,
QFrame#taskFieldGroup {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 rgba(10, 28, 46, 214),
    stop:1 rgba(11, 38, 56, 186));
  border: 1px solid rgba(111, 162, 189, 26);
  border-radius: 16px;
}}
QLabel#taskSectionIcon {{
  background: rgba(11, 50, 74, 174);
  border: 1px solid rgba(125, 211, 252, 22);
  border-radius: 17px;
}}
QLabel#taskSectionLabel {{
  color: #EAF7FF;
  font-size: 19px;
  font-weight: 900;
}}
QLabel#taskFieldGroupLabel {{
  color: #CDE5F6;
  background: #10263A;
  border: none;
  border-radius: 10px;
  padding: 7px 10px;
  font-size: 14px;
  font-weight: 900;
}}
QLabel#taskDialogCounter {{
  color: #88A4BA;
  font-size: 14px;
  font-weight: 700;
}}
QLabel#taskDialogHint,
QLabel#taskDialogTimeUnit {{
  color: #7F97AC;
  font-size: 14px;
}}
QLabel#taskDialogTimeUnit {{
  color: #D6EAFE;
  background: rgba(13, 38, 57, 0.78);
  border: none;
  border-radius: 8px;
  font-weight: 900;
  min-height: 30px;
}}
QFrame#taskPriorityPreviewP1 {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4A1824, stop:1 #6B2E12);
  border: none;
  border-radius: 14px;
}}
QFrame#taskPriorityPreviewP2 {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #12335F, stop:1 #164E63);
  border: 1px solid rgba(56, 189, 248, 0.55);
  border-radius: 14px;
}}
QFrame#taskPriorityPreviewP3 {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0F3C43, stop:1 #145246);
  border: none;
  border-radius: 14px;
}}
QLabel#taskPriorityPreviewIcon {{
  background: rgba(6, 18, 30, 0.24);
  border: 1px solid rgba(236, 253, 245, 0.18);
  border-radius: 13px;
}}
QLabel#taskPriorityPreviewTitle {{
  color: #F8FBFF;
  font-size: 16px;
  font-weight: 900;
}}
QLabel#taskPriorityPreviewSubtitle {{
  color: #AFC3D8;
  font-size: 12px;
  font-weight: 700;
}}
QLineEdit {{
  min-height: 38px;
}}
QLineEdit#taskCustomTagInput {{
  color: #ECFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #071321,
    stop:1 #0B1C2E);
  border: none;
  border-radius: 12px;
  padding: 0 12px;
  selection-background-color: #22D3EE;
  selection-color: #03111B;
}}
QDateEdit,
QComboBox {{
  min-height: 36px;
  color: #ECFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #071321,
    stop:1 #0B1C2E);
  border: none;
  border-radius: 12px;
  padding: 0 30px 0 12px;
  selection-background-color: #22D3EE;
  selection-color: #03111B;
}}
QDateEdit::drop-down,
QComboBox::drop-down {{
  width: 24px;
  subcontrol-origin: padding;
  subcontrol-position: top right;
  border: none;
  background: rgba(16, 38, 58, 0.96);
  border-top-right-radius: 12px;
  border-bottom-right-radius: 12px;
}}
QDateEdit::down-arrow,
QComboBox::down-arrow {{
  image: url("{(UI_ICON_DIR / "chevron-down.svg").as_posix()}");
  width: 12px;
  height: 12px;
}}
QDateEdit:focus,
QComboBox:focus {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0A1F34,
    stop:1 #0D3341);
}}
QDateEdit::up-button,
QDateEdit::down-button,
QDateEdit::up-arrow,
QDateEdit::down-arrow {{
  width: 0;
  height: 0;
  border: none;
  image: none;
}}
QWidget#taskDialogTimePair {{
  background: transparent;
}}
QTextEdit {{
  min-height: 96px;
}}
QPushButton#taskDialogSaveButton,
QPushButton#taskDialogCancelButton {{
  min-width: 140px;
  min-height: 44px;
  border-radius: 14px;
  font-size: 16px;
}}
QPushButton#taskDialogSaveButton {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0891B2,
    stop:1 #0F766E);
}}
QPushButton#taskDialogSaveButton:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0EA5C6,
    stop:1 #059669);
}}
QPushButton#taskDialogCancelButton {{
  background: rgba(14, 33, 53, 214);
}}
"""
