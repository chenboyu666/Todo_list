from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task, select_focus_task
from floating_todo.settings import AppSettings, settings_to_dict
from floating_todo.store import save_json_object
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.settings_window import SettingsWindow
from floating_todo.ui.task_dialog import TaskDialog
from floating_todo.view_models import countdown_label, task_rows, today_completion_percent


class TaskStore(Protocol):
    def load_tasks(self) -> list[Task]:
        """Return persisted tasks."""

    def save_tasks(self, tasks: list[Task]) -> None:
        """Persist tasks."""


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: TaskStore,
        settings: AppSettings | None = None,
        settings_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.settings = settings or AppSettings()
        self.settings_path = Path(settings_path) if settings_path is not None else Path("settings.json")
        self.tasks = self.store.load_tasks()

        self.setWindowTitle("FloatingTodo")
        self.apply_window_behavior_settings()
        self.setMinimumWidth(410)

        self.clock_label = QLabel()
        self.today_completion_label = QLabel("0%")
        self.active_count_label = QLabel("0")
        self.focus_title_label = QLabel("没有进行中的任务")
        self.focus_meta_label = QLabel("工作量 --")
        self.focus_deadline_label = QLabel("截止 --:--:--")
        self.focus_progress = QProgressBar()
        self.empty_state_label = QLabel("没有进行中的任务")
        self.empty_state_hint_label = QLabel("点击新增任务开始")
        self.task_rows_container = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_rows_container)
        self.add_button = QPushButton("+")
        self.settings_button = QPushButton("设置")

        self._build_ui()
        self.add_button.clicked.connect(self.add_task)
        self.settings_button.clicked.connect(self.open_settings)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.refresh)
        self._clock_timer.start(1000)
        self.refresh()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        header_layout = QHBoxLayout()
        title_label = QLabel("FloatingTodo")
        title_label.setObjectName("windowTitleLabel")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        header_layout.addWidget(title_label)
        header_layout.addStretch(1)
        self.clock_label.setObjectName("clockLabel")
        header_layout.addWidget(self.clock_label)
        self.settings_button.setToolTip("打开设置")
        header_layout.addWidget(self.settings_button)
        root_layout.addLayout(header_layout)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(8)
        summary_layout.addWidget(self._summary_card("今日完成", self.today_completion_label))
        summary_layout.addWidget(self._summary_card("进行中", self.active_count_label))
        root_layout.addLayout(summary_layout)

        focus_card = QFrame()
        focus_card.setObjectName("focusCard")
        focus_card.setStyleSheet(_card_style())
        focus_layout = QVBoxLayout(focus_card)
        focus_layout.setContentsMargins(12, 10, 12, 12)
        focus_layout.setSpacing(8)

        focus_top = QHBoxLayout()
        focus_title_prefix = QLabel("进行中")
        focus_title_prefix.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        focus_top.addWidget(focus_title_prefix)
        focus_top.addStretch(1)
        focus_top.addWidget(self.focus_deadline_label)
        focus_layout.addLayout(focus_top)

        self.focus_title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.focus_title_label.setWordWrap(True)
        focus_layout.addWidget(self.focus_title_label)
        focus_layout.addWidget(self.focus_meta_label)
        self.focus_progress.setRange(0, 100)
        focus_layout.addWidget(self.focus_progress)
        root_layout.addWidget(focus_card)

        actions_layout = QHBoxLayout()
        section_label = QLabel("任务")
        section_label.setStyleSheet("font-weight: 700;")
        actions_layout.addWidget(section_label)
        actions_layout.addStretch(1)
        self.add_button.setToolTip("新增任务")
        actions_layout.addWidget(self.add_button)
        root_layout.addLayout(actions_layout)

        empty_box = QWidget()
        empty_layout = QVBoxLayout(empty_box)
        empty_layout.setContentsMargins(0, 12, 0, 12)
        empty_layout.setSpacing(4)
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setStyleSheet(f"color: {THEME_COLORS['border']};")
        empty_layout.addWidget(self.empty_state_label)
        empty_layout.addWidget(self.empty_state_hint_label)
        root_layout.addWidget(empty_box)
        self.empty_state_widget = empty_box

        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(8)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.task_rows_container)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout.addWidget(scroll_area, 1)

    def _summary_card(self, caption: str, value_label: QLabel) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        caption_label = QLabel(caption)
        caption_label.setStyleSheet(f"color: {THEME_COLORS['accent']};")
        value_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        return card

    def update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def add_task(self) -> None:
        dialog = TaskDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        task = dialog.build_task()
        if not task.title.strip():
            return

        self.tasks = [*self.tasks, task]
        self.store.save_tasks(self.tasks)
        self.refresh()

    def apply_window_behavior_settings(self) -> None:
        self.setWindowOpacity(self.settings.opacity)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.always_on_top)

    def open_settings(self) -> None:
        dialog = SettingsWindow(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return

        self.settings = dialog.build_settings()
        save_json_object(self.settings_path, settings_to_dict(self.settings))
        self.apply_window_behavior_settings()
        self.show()

    def closeEvent(self, event) -> None:
        if self.settings.close_to_tray:
            event.ignore()
            self.hide()
            return

        event.accept()

    def refresh(self) -> None:
        self.update_clock()
        self.tasks = self.store.load_tasks()
        now = datetime.now(timezone.utc)
        active_count = sum(1 for task in self.tasks if task.status == "active")
        self.active_count_label.setText(str(active_count))
        self.today_completion_label.setText(f"{today_completion_percent(self.tasks)}%")

        focus_task = select_focus_task(self.tasks)
        if focus_task is None:
            self.focus_title_label.setText("没有进行中的任务")
            self.focus_meta_label.setText("工作量 --")
            self.focus_deadline_label.setText("截止 --:--:--")
            self.focus_progress.setValue(0)
            self.empty_state_widget.show()
        else:
            self.focus_title_label.setText(focus_task.title)
            self.focus_meta_label.setText(f"{focus_task.priority} · 工作量 {focus_task.effort_minutes} min")
            self.focus_deadline_label.setText(f"截止 {countdown_label(focus_task.deadline, now)}")
            self.focus_progress.setValue(focus_task.progress)
            self.empty_state_widget.hide()

        self._render_task_rows(task_rows(self.tasks, now))

    def _render_task_rows(self, rows: list[dict[str, object]]) -> None:
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for row in rows:
            self.task_list_layout.addWidget(self._task_row(row))

    def _task_row(self, row: dict[str, object]) -> QFrame:
        card = QFrame()
        card.setObjectName(f"taskRow-{row['id']}")
        card.setStyleSheet(_card_style())
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        priority = QLabel(str(row["priority"]))
        priority.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        top.addWidget(priority)
        title = QLabel(str(row["title"]))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700;")
        top.addWidget(title, 1)
        progress_label = QLabel(str(row["progress_label"]))
        top.addWidget(progress_label)
        layout.addLayout(top)

        meta = QHBoxLayout()
        meta.addWidget(QLabel(f"工作量 {row['effort_label']}"))
        meta.addStretch(1)
        deadline = QLabel(f"截止 {row['deadline_label']}")
        if row["is_overdue"]:
            deadline.setStyleSheet("color: #FCA5A5;")
        meta.addWidget(deadline)
        layout.addLayout(meta)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(int(row["progress"]))
        layout.addWidget(progress)
        return card


def _card_style() -> str:
    return (
        f"QFrame {{ background: {THEME_COLORS['surface']}; "
        f"border: 1px solid {THEME_COLORS['border']}; border-radius: 8px; }}"
    )
