from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QMimeData, QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task, select_focus_task
from floating_todo.platform_windows import current_startup_command, set_launch_on_startup
from floating_todo.reminders import mark_event_sent, reminder_events
from floating_todo.settings import AppSettings, settings_to_dict
from floating_todo.store import save_json_object
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.backdrop import AnimatedBackdrop
from floating_todo.ui.completion_dialog import CompletionDialog
from floating_todo.ui.confirmation_dialog import DeleteTaskDialog
from floating_todo.ui.controls import NoWheelSlider
from floating_todo.ui.effects import apply_soft_shadow
from floating_todo.ui.history_window import HistoryWindow
from floating_todo.ui.settings_window import SettingsWindow
from floating_todo.ui.task_dialog import TaskDialog
from floating_todo.view_models import (
    countdown_label,
    deadline_at_label,
    deadline_urgency,
    task_rows,
    today_completion_percent,
)


TASK_MIME_TYPE = "application/x-floating-todo-task-id"


class TaskStore(Protocol):
    def load_tasks(self) -> list[Task]:
        """Return persisted tasks."""

    def save_tasks(self, tasks: list[Task]) -> None:
        """Persist tasks."""


class NotificationSenderProtocol(Protocol):
    def send(self, title: str, message: str) -> None:
        """Send a user-visible notification."""


class TitleBar(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_start: QPoint | None = None
        self.setObjectName("titleBar")
        self.setCursor(Qt.SizeAllCursor)
        self.setMinimumHeight(46)
        self.setStyleSheet(
            "QFrame#titleBar {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #10263A,"
            " stop:0.48 #132F3C,"
            " stop:1 #142A33);"
            "border: 1px solid #2C5365;"
            "border-radius: 10px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)
        title = QLabel("FloatingTodo")
        title.setObjectName("windowTitleLabel")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        drag_hint = QLabel("拖动")
        drag_hint.setStyleSheet(f"color: {THEME_COLORS['accent_secondary']}; font-weight: 700;")
        layout.addWidget(drag_hint)
        layout.addStretch(1)
        layout.addWidget(window.clock_label)
        window.settings_button.setText("设置")
        window.settings_button.setToolTip("打开设置")
        layout.addWidget(window.settings_button)
        window.minimize_button = QPushButton("–")
        window.minimize_button.setToolTip("最小化")
        window.minimize_button.clicked.connect(window.showMinimized)
        layout.addWidget(window.minimize_button)
        window.close_button = QPushButton("×")
        window.close_button.setToolTip("关闭")
        window.close_button.clicked.connect(window.close)
        layout.addWidget(window.close_button)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None and event.buttons() & Qt.LeftButton and not self.window.settings.lock_position:
            self.window.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


class FocusDropCard(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(TASK_MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        task_id = bytes(event.mimeData().data(TASK_MIME_TYPE)).decode("utf-8")
        self.window.set_focus_task(task_id)
        event.acceptProposedAction()


class TaskRowCard(QFrame):
    def __init__(self, task_id: str, window: "MainWindow") -> None:
        super().__init__(window)
        self.task_id = task_id
        self.window = window
        self._drag_start: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None or not event.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 8:
            super().mouseMoveEvent(event)
            return
        self.start_drag()
        event.accept()

    def start_drag(self) -> None:
        if self.window.is_task_drag_active:
            return
        mime = QMimeData()
        mime.setData(TASK_MIME_TYPE, self.task_id.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        self.window.begin_task_drag()
        try:
            drag.exec(Qt.MoveAction)
        finally:
            self._drag_start = None
            self.window.end_task_drag()


class TaskDragHandle(QLabel):
    def __init__(self, card: TaskRowCard) -> None:
        super().__init__("↥", card)
        self.card = card
        self._drag_start: QPoint | None = None
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(24, 24)
        self.setToolTip("拖到上方设为进行中")
        self.setStyleSheet(
            f"background: {THEME_COLORS['surface_hover']}; "
            f"color: {THEME_COLORS['accent']}; "
            "font-weight: 900; border-radius: 7px;"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None or not event.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 8:
            super().mouseMoveEvent(event)
            return
        self.card.start_drag()
        self._drag_start = None
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is not None and event.button() == Qt.LeftButton:
            self.card.window.set_focus_task(self.card.task_id)
            event.accept()
            self._drag_start = None
            return
        self._drag_start = None
        super().mouseReleaseEvent(event)


class CornerResizeGrip(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_start: QPoint | None = None
        self._start_geometry: QRect | None = None
        self.setFixedSize(24, 24)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setToolTip("拖动调整窗口大小")
        self.setStyleSheet(
            "QFrame {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #1B3B4B,"
            " stop:1 #7DD3FC);"
            "border: none;"
            "border-radius: 8px;"
            "}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.window.settings.lock_position:
            self._drag_start = event.globalPosition().toPoint()
            self._start_geometry = QRect(self.window.geometry())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None or self._start_geometry is None or not event.buttons() & Qt.LeftButton:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._drag_start
        minimum = self.window.minimumSize()
        width = max(minimum.width(), self._start_geometry.width() + delta.x())
        height = max(minimum.height(), self._start_geometry.height() + delta.y())
        self.window.setGeometry(self._start_geometry.x(), self._start_geometry.y(), width, height)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        self._start_geometry = None
        super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: TaskStore,
        settings: AppSettings | None = None,
        settings_path: Path | None = None,
        notification_sender: NotificationSenderProtocol | None = None,
    ) -> None:
        super().__init__()
        self.store = store
        self.settings = settings or AppSettings()
        self.settings_path = Path(settings_path) if settings_path is not None else None
        self.notification_sender = notification_sender
        self.tray_controller = None
        self._geometry_initialized = False
        self._restoring_geometry = False
        self._task_drag_active = False
        self._task_drag_refresh_pending = False
        self.tasks = self.store.load_tasks()

        self.setWindowTitle("FloatingTodo")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.apply_window_behavior_settings()
        self.setMinimumSize(430, 420)
        self.apply_saved_geometry()

        self.clock_label = QLabel()
        self.today_completion_label = QLabel("0%")
        self.active_count_label = QLabel("0")
        self.focus_title_label = QLabel("没有进行中的任务")
        self.focus_meta_label = QLabel("工作量 --")
        self.focus_deadline_label = QLabel("截止 --:--:--")
        self.focus_urgency_label = QLabel("等待")
        self.focus_progress = NoWheelSlider(Qt.Horizontal)
        self.focus_progress.setRange(0, 100)
        self.focus_progress.valueChanged.connect(self.update_focus_progress)
        self.focus_progress.sliderReleased.connect(self.commit_focus_progress)
        self.empty_state_label = QLabel("没有进行中的任务")
        self.empty_state_hint_label = QLabel("点击新增任务开始")
        self.task_rows_container = QWidget()
        self.task_rows_container.setObjectName("taskRowsContainer")
        self.task_rows_container.setStyleSheet("QWidget#taskRowsContainer { background: transparent; }")
        self.task_list_layout = QVBoxLayout(self.task_rows_container)
        self.add_button = QPushButton("+")
        self.settings_button = QPushButton("设置")
        self.history_button = QPushButton("历史")
        self.minimize_button = QPushButton("–")
        self.close_button = QPushButton("×")

        self._build_ui()
        self.add_button.clicked.connect(self.add_task)
        self.settings_button.clicked.connect(self.open_settings)
        self.history_button.clicked.connect(self.open_history)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.refresh)
        self._clock_timer.start(1000)
        self.refresh()
        self._geometry_initialized = True

    def _build_ui(self) -> None:
        root = AnimatedBackdrop()
        root.setObjectName("mainRoot")
        self.root_widget = root
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 16)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        root_layout.addWidget(TitleBar(self))

        self.summary_widget = QWidget()
        summary_layout = QHBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(8)
        summary_layout.addWidget(self._summary_card("今日完成", self.today_completion_label))
        summary_layout.addWidget(self._summary_card("进行中", self.active_count_label))
        root_layout.addWidget(self.summary_widget)

        self.focus_card = FocusDropCard(self)
        self.focus_card.setObjectName("focusCard")
        self.focus_card.setToolTip("把任务拖到这里设为进行中")
        self.focus_card.setStyleSheet(_card_style("normal", selected=True))
        apply_soft_shadow(self.focus_card, blur=34, y_offset=12, alpha=120)
        focus_layout = QVBoxLayout(self.focus_card)
        focus_layout.setContentsMargins(12, 10, 12, 12)
        focus_layout.setSpacing(8)

        focus_top = QHBoxLayout()
        self.focus_title_prefix = QLabel("进行中")
        self.focus_title_prefix.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        focus_top.addWidget(self.focus_title_prefix)
        self.focus_urgency_label.setAlignment(Qt.AlignCenter)
        self.focus_urgency_label.setFixedHeight(24)
        focus_top.addWidget(self.focus_urgency_label)
        focus_top.addStretch(1)
        focus_top.addWidget(self.focus_deadline_label)
        focus_layout.addLayout(focus_top)

        self.focus_title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.focus_title_label.setWordWrap(True)
        focus_layout.addWidget(self.focus_title_label)
        focus_layout.addWidget(self.focus_meta_label)
        focus_layout.addWidget(self.focus_progress)
        root_layout.addWidget(self.focus_card)

        self.task_section_widget = QWidget()
        actions_layout = QHBoxLayout(self.task_section_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        section_label = QLabel("任务")
        section_label.setStyleSheet("font-weight: 700;")
        actions_layout.addWidget(section_label)
        actions_layout.addStretch(1)
        self.history_button.setToolTip("查看历史任务与完成体会")
        actions_layout.addWidget(self.history_button)
        self.add_button.setToolTip("新增任务")
        actions_layout.addWidget(self.add_button)
        root_layout.addWidget(self.task_section_widget)

        self.empty_state_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setContentsMargins(0, 12, 0, 12)
        empty_layout.setSpacing(4)
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setStyleSheet(f"color: {THEME_COLORS['border']};")
        empty_layout.addWidget(self.empty_state_label)
        empty_layout.addWidget(self.empty_state_hint_label)
        root_layout.addWidget(self.empty_state_widget)

        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(8)
        self.task_list_layout.setAlignment(Qt.AlignTop)
        self.task_scroll_area = QScrollArea()
        self.task_scroll_area.setWidgetResizable(True)
        self.task_scroll_area.setFrameShape(QFrame.NoFrame)
        self.task_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.task_scroll_area.viewport().setAutoFillBackground(False)
        self.task_scroll_area.viewport().setStyleSheet("background: transparent;")
        self.task_scroll_area.setWidget(self.task_rows_container)
        self.task_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout.addWidget(self.task_scroll_area, 1)

        resize_row = QHBoxLayout()
        resize_row.setContentsMargins(0, 0, 0, 0)
        resize_row.addStretch(1)
        self.resize_grip = CornerResizeGrip(self)
        resize_row.addWidget(self.resize_grip)
        root_layout.addLayout(resize_row)
        self.apply_background_settings()

    def _summary_card(self, caption: str, value_label: QLabel) -> QFrame:
        card = QFrame()
        card.setStyleSheet(_card_style())
        apply_soft_shadow(card, blur=24, y_offset=8, alpha=85)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        caption_label = QLabel(caption)
        caption_label.setStyleSheet(f"color: {THEME_COLORS['muted']};")
        value_label.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        return card

    def update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def focus_task(self) -> Task | None:
        if self.settings.focus_task_id:
            focused = next(
                (task for task in self.tasks if task.id == self.settings.focus_task_id and task.status == "active"),
                None,
            )
            if focused:
                return focused
            self.settings = replace(self.settings, focus_task_id=None)
            self._save_settings()
        return select_focus_task(self.tasks)

    def set_focus_task(self, task_id: str) -> None:
        if not any(task.id == task_id and task.status == "active" for task in self.tasks):
            return
        self.settings = replace(self.settings, focus_task_id=task_id)
        self._save_settings()
        self.refresh()

    @property
    def is_task_drag_active(self) -> bool:
        return self._task_drag_active

    def begin_task_drag(self) -> None:
        self._task_drag_active = True
        self._task_drag_refresh_pending = False

    def end_task_drag(self) -> None:
        if not self._task_drag_active:
            return
        needs_refresh = self._task_drag_refresh_pending
        self._task_drag_active = False
        self._task_drag_refresh_pending = False
        if needs_refresh:
            self.refresh()

    def update_focus_progress(self, value: int) -> None:
        if self.focus_progress.isSliderDown():
            return
        self._commit_focus_progress(value)

    def commit_focus_progress(self) -> None:
        self._commit_focus_progress(self.focus_progress.value())

    def _commit_focus_progress(self, value: int) -> None:
        focused = self.focus_task()
        if focused is None:
            return
        if focused.progress == value:
            return
        self.update_task_progress(focused.id, value)

    def update_task_progress(self, task_id: str, value: int) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        updated = replace(self.tasks[index], progress=max(0, min(100, int(value))), updated_at=datetime.now(timezone.utc))
        self.tasks = [*self.tasks[:index], updated, *self.tasks[index + 1 :]]
        self.store.save_tasks(self.tasks)
        self.refresh()

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

    def edit_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        dialog = TaskDialog(self, self.tasks[index])
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.build_task()
        if not updated.title.strip():
            return
        self.tasks = [*self.tasks[:index], updated, *self.tasks[index + 1 :]]
        self.store.save_tasks(self.tasks)
        self.refresh()

    def complete_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        if not self.confirm_complete_task(self.tasks[index]):
            return
        now = datetime.now(timezone.utc)
        completed = replace(self.tasks[index], status="done", progress=100, completed_at=now, updated_at=now)
        self.tasks = [*self.tasks[:index], completed, *self.tasks[index + 1 :]]
        if self.settings.focus_task_id == task_id:
            self.settings = replace(self.settings, focus_task_id=None)
            self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh()

    def confirm_complete_task(self, task: Task) -> bool:
        dialog = CompletionDialog(task, self)
        return dialog.exec() == QDialog.Accepted

    def delete_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        if not self.confirm_delete_task(self.tasks[index]):
            return
        self.tasks = [*self.tasks[:index], *self.tasks[index + 1 :]]
        if self.settings.focus_task_id == task_id:
            self.settings = replace(self.settings, focus_task_id=None)
            self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh()

    def confirm_delete_task(self, task: Task) -> bool:
        dialog = DeleteTaskDialog(task, self)
        return dialog.exec() == QDialog.Accepted

    def open_history(self) -> None:
        dialog = HistoryWindow(self.tasks, self.store, self)
        dialog.exec()
        self.tasks = self.store.load_tasks()
        self.refresh()

    def _task_index(self, task_id: str) -> int | None:
        for index, task in enumerate(self.tasks):
            if task.id == task_id:
                return index
        return None

    def apply_window_behavior_settings(self) -> None:
        self.setWindowOpacity(self.settings.opacity)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.always_on_top)

    def apply_background_settings(self) -> None:
        self.root_widget.set_background_settings(
            self.settings.background_enabled,
            self.settings.background_image_path,
            self.settings.background_overlay,
        )

    def preview_settings(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            settings.background_image_path,
            settings.background_overlay,
        )

    def restore_settings_preview(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            settings.background_image_path,
            settings.background_overlay,
        )

    def apply_low_distraction_settings(self) -> None:
        hidden = self.settings.low_distraction_mode
        self.summary_widget.setHidden(hidden)
        self.task_section_widget.setHidden(hidden)
        self.task_scroll_area.setHidden(hidden)
        self.empty_state_widget.setHidden(hidden or bool(self.focus_task()))
        self.focus_card.show()

    def apply_saved_geometry(self) -> None:
        geometry = self.settings.window_geometry
        self.setGeometry(int(geometry["x"]), int(geometry["y"]), int(geometry["width"]), int(geometry["height"]))

    def open_settings(self) -> None:
        previous_settings = self.settings
        dialog = SettingsWindow(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            self.restore_settings_preview(previous_settings)
            return
        updated_settings = dialog.build_settings()
        if updated_settings.launch_on_startup != self.settings.launch_on_startup:
            try:
                set_launch_on_startup("FloatingTodo", current_startup_command(), updated_settings.launch_on_startup)
            except OSError as exc:
                self.restore_settings_preview(previous_settings)
                QMessageBox.warning(self, "启动设置失败", f"无法更新开机启动设置：{exc}")
                return

        self.settings = updated_settings
        self._save_settings()
        self._restoring_geometry = True
        try:
            self.apply_window_behavior_settings()
            self.apply_background_settings()
            self.apply_low_distraction_settings()
            if self.settings.lock_position:
                self.apply_saved_geometry()
            self.show()
        finally:
            self._restoring_geometry = False

    def can_close_to_tray(self) -> bool:
        tray_controller = self.tray_controller
        return bool(self.settings.close_to_tray and tray_controller is not None and tray_controller.is_available())

    def closeEvent(self, event) -> None:
        if self.can_close_to_tray():
            event.ignore()
            self.hide()
            return
        self._clock_timer.stop()
        self.root_widget.stop_animation()
        event.accept()

    def setGeometry(self, *args) -> None:
        super().setGeometry(*args)
        self._handle_geometry_change()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._handle_geometry_change()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._handle_geometry_change()

    def _handle_geometry_change(self) -> None:
        if not self._geometry_initialized or self._restoring_geometry:
            return
        if self.settings.lock_position:
            self._restore_locked_geometry()
            return
        geometry = self._current_geometry()
        if geometry == dict(self.settings.window_geometry):
            return
        self.settings = replace(self.settings, window_geometry=geometry)
        self._save_settings()

    def _save_settings(self) -> None:
        if self.settings_path is None:
            return
        save_json_object(self.settings_path, settings_to_dict(self.settings))

    def _restore_locked_geometry(self) -> None:
        self._restoring_geometry = True
        try:
            self.apply_saved_geometry()
        finally:
            self._restoring_geometry = False

    def _current_geometry(self) -> dict[str, int]:
        geometry = self.geometry()
        return {"x": geometry.x(), "y": geometry.y(), "width": geometry.width(), "height": geometry.height()}

    def process_reminders(self, now: datetime) -> None:
        if self.notification_sender is None:
            return
        event_titles = {"deadline_warning": "任务临近截止", "deadline_due": "任务已超时"}
        updated_tasks: list[Task] = []
        changed = False
        for task in self.tasks:
            updated_task = task
            for event in reminder_events(
                updated_task,
                now,
                self.settings.notification_lead_minutes,
                self.settings.notification_repeat_minutes,
            ):
                self.notification_sender.send(event_titles[event], updated_task.title)
                updated_task = mark_event_sent(updated_task, event, now)
                changed = True
            updated_tasks.append(updated_task)
        if changed:
            self.tasks = updated_tasks
            self.store.save_tasks(self.tasks)

    def refresh(self) -> None:
        self.update_clock()
        if self._task_drag_active:
            self._task_drag_refresh_pending = True
            return
        self.tasks = self.store.load_tasks()
        now = datetime.now(timezone.utc)
        self.process_reminders(now)
        active_count = sum(1 for task in self.tasks if task.status == "active")
        self.active_count_label.setText(str(active_count))
        self.today_completion_label.setText(f"{today_completion_percent(self.tasks)}%")

        focus_task = self.focus_task()
        self.focus_progress.blockSignals(True)
        if focus_task is None:
            self.focus_title_label.setText("没有进行中的任务")
            self.focus_meta_label.setText("工作量 --")
            self.focus_deadline_label.setText("截止 --:--:--")
            self.focus_deadline_label.setStyleSheet(_deadline_label_style("none"))
            self.focus_urgency_label.setText("等待")
            self.focus_urgency_label.setStyleSheet(_urgency_chip_style("none"))
            self.focus_card.setStyleSheet(_card_style("normal", selected=True))
            self.focus_progress.setValue(0)
            self.empty_state_widget.show()
        else:
            urgency, urgency_label = deadline_urgency(focus_task.deadline, now)
            self.focus_title_label.setText(focus_task.title)
            self.focus_meta_label.setText(f"{focus_task.priority} · 工作量 {focus_task.effort_minutes} min")
            self.focus_deadline_label.setText(
                f"截止 {deadline_at_label(focus_task.deadline)} · {countdown_label(focus_task.deadline, now)}"
            )
            self.focus_deadline_label.setStyleSheet(_deadline_label_style(urgency))
            self.focus_urgency_label.setText(urgency_label)
            self.focus_urgency_label.setStyleSheet(_urgency_chip_style(urgency))
            self.focus_card.setStyleSheet(_card_style(urgency, selected=True))
            self.focus_progress.setValue(focus_task.progress)
            self.empty_state_widget.hide()
        self.focus_progress.blockSignals(False)

        self._render_task_rows(task_rows(self.tasks, now), focus_task.id if focus_task else None)
        self.apply_low_distraction_settings()

    def _render_task_rows(self, rows: list[dict[str, object]], focus_task_id: str | None = None) -> None:
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in rows:
            self.task_list_layout.addWidget(self._task_row(row, focus_task_id))

    def _task_row(self, row: dict[str, object], focus_task_id: str | None = None) -> QFrame:
        task_id = str(row["id"])
        urgency = str(row["urgency"])
        card = TaskRowCard(task_id, self)
        card.setObjectName(f"taskRow-{task_id}")
        card.setStyleSheet(_card_style(urgency, selected=task_id == focus_task_id))
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_soft_shadow(card, blur=22, y_offset=8, alpha=80)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        drag_handle = TaskDragHandle(card)
        top.addWidget(drag_handle)
        priority = QLabel(str(row["priority"]))
        priority.setAlignment(Qt.AlignCenter)
        priority.setFixedHeight(24)
        priority.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        priority.setStyleSheet(
            "font-weight: 700; padding: 2px 8px; border-radius: 7px; "
            f"background: {_priority_chip_background(str(row['priority']))}; "
            f"color: {_priority_chip_text(str(row['priority']))};"
        )
        top.addWidget(priority)
        urgency_chip = QLabel(str(row["urgency_label"]))
        urgency_chip.setAlignment(Qt.AlignCenter)
        urgency_chip.setFixedHeight(24)
        urgency_chip.setStyleSheet(_urgency_chip_style(urgency))
        top.addWidget(urgency_chip)
        title = QLabel(str(row["title"]))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700;")
        top.addWidget(title, 1)
        progress_label = QLabel(str(row["progress_label"]))
        top.addWidget(progress_label)
        layout.addLayout(top)

        progress = NoWheelSlider(Qt.Horizontal)
        progress.setRange(0, 100)
        progress.setValue(int(row["progress"]))
        progress.valueChanged.connect(
            lambda value, task_id=task_id, slider=progress, label=progress_label: self._handle_row_progress_value(
                task_id, slider, label, value
            )
        )
        progress.sliderReleased.connect(lambda task_id=task_id, slider=progress: self.update_task_progress(task_id, slider.value()))
        layout.addWidget(progress)

        actions = QHBoxLayout()
        actions.addStretch(1)
        focus_button = QPushButton("进行中" if task_id == focus_task_id else "置顶")
        focus_button.setToolTip("设为当前置顶任务")
        focus_button.setEnabled(task_id != focus_task_id)
        focus_button.clicked.connect(lambda checked=False, task_id=task_id: self.set_focus_task(task_id))
        actions.addWidget(focus_button)
        edit_button = QPushButton("编辑")
        edit_button.setToolTip("编辑任务")
        edit_button.clicked.connect(lambda checked=False, task_id=task_id: self.edit_task(task_id))
        actions.addWidget(edit_button)
        complete_button = QPushButton("完成")
        complete_button.setToolTip("标记任务完成")
        complete_button.clicked.connect(lambda checked=False, task_id=task_id: self.complete_task(task_id))
        actions.addWidget(complete_button)
        delete_button = QPushButton("删除")
        delete_button.setToolTip("删除任务")
        delete_button.clicked.connect(lambda checked=False, task_id=task_id: self.delete_task(task_id))
        actions.addWidget(delete_button)
        layout.addLayout(actions)

        meta = QHBoxLayout()
        meta.addWidget(QLabel(f"工作量 {row['effort_label']}"))
        meta.addStretch(1)
        deadline = QLabel(f"截止 {row['deadline_at_label']} · {row['deadline_label']}")
        deadline.setStyleSheet(_deadline_label_style(urgency))
        meta.addWidget(deadline)
        layout.addLayout(meta)
        return card

    def _handle_row_progress_value(self, task_id: str, slider: NoWheelSlider, label: QLabel, value: int) -> None:
        label.setText(f"{value}%")
        if slider.isSliderDown():
            return
        self.update_task_progress(task_id, value)


URGENCY_STYLES = {
    "none": {
        "surface": "#111722",
        "surface_alt": "#151B27",
        "selected": "#1A2230",
        "accent": THEME_COLORS["muted"],
        "chip_bg": "#202838",
        "chip_text": "#C9D2E4",
    },
    "normal": {
        "surface": "#111722",
        "surface_alt": "#142031",
        "selected": "#1A2E3C",
        "accent": THEME_COLORS["accent"],
        "chip_bg": "#123047",
        "chip_text": "#BAE6FD",
    },
    "soon": {
        "surface": "#101B1E",
        "surface_alt": "#132822",
        "selected": "#18352D",
        "accent": THEME_COLORS["accent_secondary"],
        "chip_bg": "#12362D",
        "chip_text": "#C8FFE8",
    },
    "urgent": {
        "surface": "#1F1A13",
        "surface_alt": "#2A2214",
        "selected": "#3A2A16",
        "accent": THEME_COLORS["warning"],
        "chip_bg": "#4A3218",
        "chip_text": "#FFE2A8",
    },
    "critical": {
        "surface": "#251714",
        "surface_alt": "#321D17",
        "selected": "#422117",
        "accent": "#FDBA74",
        "chip_bg": "#5A2719",
        "chip_text": "#FFD5BA",
    },
    "overdue": {
        "surface": "#28151B",
        "surface_alt": "#351722",
        "selected": "#421927",
        "accent": THEME_COLORS["danger"],
        "chip_bg": "#5A1F2B",
        "chip_text": "#FFD5DF",
    },
}


def _urgency_style(urgency: str) -> dict[str, str]:
    return URGENCY_STYLES.get(urgency, URGENCY_STYLES["normal"])


def _card_style(urgency: str = "normal", *, selected: bool = False) -> str:
    style = _urgency_style(urgency)
    selected_stop = style["selected"] if selected else style["surface_alt"]
    return (
        "QFrame {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        f" stop:0 {style['surface']},"
        f" stop:0.68 {THEME_COLORS['surface']},"
        f" stop:1 {selected_stop});"
        "border: 1px solid #26364A;"
        "border-radius: 8px;"
        "}"
    )


def _urgency_chip_style(urgency: str) -> str:
    style = _urgency_style(urgency)
    return (
        "font-weight: 700; padding: 2px 8px; border-radius: 7px; "
        f"background: {style['chip_bg']}; color: {style['chip_text']};"
    )


def _deadline_label_style(urgency: str) -> str:
    return f"color: {_urgency_style(urgency)['accent']}; font-weight: 700;"


def _priority_chip_background(priority: str) -> str:
    return {
        "P1": "#4A2B16",
        "P2": "#123047",
        "P3": "#12362D",
    }.get(priority, "#1A1F2B")


def _priority_chip_text(priority: str) -> str:
    return {
        "P1": THEME_COLORS["warning"],
        "P2": THEME_COLORS["accent"],
        "P3": THEME_COLORS["accent_secondary"],
    }.get(priority, THEME_COLORS["text"])
