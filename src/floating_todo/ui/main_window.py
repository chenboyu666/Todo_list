from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QDrag, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
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

from floating_todo.app_identity import APP_DISPLAY_NAME, APP_STARTUP_NAME, resolved_icon_path
from floating_todo.domain import Task, select_focus_task
from floating_todo.platform_windows import current_startup_command, set_launch_on_startup
from floating_todo.reminders import mark_event_sent, reminder_events
from floating_todo.settings import (
    AppSettings,
    DEFAULT_BACKGROUND_OVERLAY,
    DEFAULT_NOTIFICATION_REPEAT_MINUTES,
    remove_deprecated_setting_features,
    settings_to_dict,
)
from floating_todo.store import save_json_object
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.backdrop import AnimatedBackdrop
from floating_todo.ui.completion_dialog import CompletionDialog
from floating_todo.ui.confirmation_dialog import DeleteTaskDialog
from floating_todo.ui.controls import NoWheelSlider, NoWheelSpinBox
from floating_todo.ui.effects import (
    animate_value_tick,
    apply_soft_shadow,
    install_global_interaction_effects,
    prepare_window_entrance,
)
from floating_todo.ui.history_window import HistoryWindow
from floating_todo.ui.settings_window import SettingsWindow
from floating_todo.ui.task_dialog import TaskDialog
from floating_todo.ui.toast import FloatingToast
from floating_todo.view_models import (
    countdown_label,
    deadline_at_label,
    deadline_urgency,
    task_rows,
    today_completion_percent,
)


TASK_MIME_TYPE = "application/x-floating-todo-task-id"
MAIN_WINDOW_MINIMUM_WIDTH = 520
MAIN_WINDOW_MINIMUM_HEIGHT = 760
FOCUS_CARD_MINIMUM_HEIGHT = 350
FOCUS_DEADLINE_PANEL_MINIMUM_HEIGHT = 92
TASK_SECTION_MINIMUM_HEIGHT = 54


class TaskStore(Protocol):
    def load_tasks(self) -> list[Task]:
        """Return persisted tasks."""

    def save_tasks(self, tasks: list[Task]) -> None:
        """Persist tasks."""


class NotificationSenderProtocol(Protocol):
    def send(self, title: str, message: str) -> None:
        """Send a user-visible notification."""


class ClockDisplay(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._phase = 0
        self.setObjectName("clockLabel")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(92, 38)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setStyleSheet(
            "QLabel#clockLabel {"
            "color: #F8FBFF;"
            "background: transparent;"
            "font-size: 15px;"
            "font-weight: 900;"
            'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
            "padding: 0 12px;"
            "}"
        )

    def setText(self, text: str) -> None:
        self._phase = (self._phase + 1) % 360
        super().setText(text)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
        fill.setColorAt(0, QColor(9, 20, 33, 228))
        fill.setColorAt(0.52, QColor(13, 48, 66, 232))
        fill.setColorAt(1, QColor(22, 78, 73, 226))
        painter.fillPath(path, fill)
        painter.setClipPath(path)
        self._draw_clock_sweep(painter, rect)
        painter.setClipping(False)
        painter.setPen(QPen(QColor(125, 211, 252, 90), 1.1))
        painter.drawPath(path)
        painter.end()
        super().paintEvent(event)

    def _draw_clock_sweep(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(Qt.NoPen)
        baseline = QRectF(rect.left() + 14, rect.bottom() - 5, max(0, rect.width() - 28), 2)
        painter.fillRect(baseline, QColor(125, 211, 252, 42))
        sweep_width = min(44, max(24, int(rect.width() * 0.34)))
        travel = max(1, int(baseline.width() + sweep_width))
        x = baseline.left() - sweep_width + ((self._phase * 1.3) % travel)
        sweep_rect = QRectF(x, baseline.top(), sweep_width, baseline.height())
        sweep = QLinearGradient(sweep_rect.topLeft(), sweep_rect.topRight())
        sweep.setColorAt(0, QColor(125, 211, 252, 0))
        sweep.setColorAt(0.5, QColor(186, 230, 253, 150))
        sweep.setColorAt(1, QColor(167, 243, 208, 0))
        painter.fillRect(sweep_rect, sweep)


class TitleBar(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_start: QPoint | None = None
        self.setObjectName("titleBar")
        self.setCursor(Qt.OpenHandCursor)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            "QFrame#titleBar {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #10263A,"
            " stop:0.48 #132F3C,"
            " stop:1 #142A33);"
            "border: none;"
            "border-radius: 10px;"
            "}"
            "QFrame#titleActionDock {"
            "background: rgba(7, 13, 23, 118);"
            "border: none;"
            "border-radius: 10px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 8, 7)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignVCenter)
        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("windowTitleLabel")
        title.setStyleSheet("font-size: 21px; font-weight: 900;")
        layout.addWidget(title)
        drag_hint = QLabel("拖动")
        drag_hint.setStyleSheet(f"color: {THEME_COLORS['accent_secondary']}; font-weight: 700;")
        layout.addWidget(drag_hint)
        window.passthrough_hint_label = QLabel("穿透中 · 右键托盘恢复")
        window.passthrough_hint_label.setObjectName("passthroughHint")
        window.passthrough_hint_label.setStyleSheet(
            "color: #ECFEFF; background: #155E75; border-radius: 8px; padding: 3px 8px; font-weight: 800;"
        )
        layout.addWidget(window.passthrough_hint_label)
        layout.addStretch(1)
        action_dock = QFrame()
        action_dock.setObjectName("titleActionDock")
        action_dock.setFixedHeight(46)
        action_layout = QHBoxLayout(action_dock)
        action_layout.setContentsMargins(7, 4, 7, 4)
        action_layout.setSpacing(8)
        action_layout.setAlignment(Qt.AlignVCenter)
        action_layout.addWidget(window.clock_label, 0, Qt.AlignVCenter)
        window.settings_button.setText("设置")
        window.settings_button.setToolTip("打开设置")
        window.settings_button.setCursor(Qt.PointingHandCursor)
        window.settings_button.setFixedHeight(38)
        window.settings_button.setMinimumWidth(62)
        action_layout.addWidget(window.settings_button, 0, Qt.AlignVCenter)
        window.minimize_button = QPushButton("–")
        window.minimize_button.setToolTip("最小化")
        window.minimize_button.setCursor(Qt.PointingHandCursor)
        window.minimize_button.setFixedSize(42, 38)
        window.minimize_button.clicked.connect(window.showMinimized)
        action_layout.addWidget(window.minimize_button, 0, Qt.AlignVCenter)
        window.close_button = QPushButton("×")
        window.close_button.setToolTip("关闭")
        window.close_button.setCursor(Qt.PointingHandCursor)
        window.close_button.setFixedSize(42, 38)
        window.close_button.clicked.connect(window.close)
        action_layout.addWidget(window.close_button, 0, Qt.AlignVCenter)
        window.title_action_dock = action_dock
        layout.addWidget(action_dock, 0, Qt.AlignRight | Qt.AlignVCenter)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
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
        self.setCursor(Qt.OpenHandCursor)
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
        install_global_interaction_effects()
        self.store = store
        self.settings = remove_deprecated_setting_features(settings or AppSettings())
        self.settings_path = Path(settings_path) if settings_path is not None else None
        self.notification_sender = notification_sender
        self.tray_controller = None
        self._geometry_initialized = False
        self._restoring_geometry = False
        self._task_drag_active = False
        self._task_drag_refresh_pending = False
        self._toast_popups: list[FloatingToast] = []
        self.expanded_task_ids: set[str] = set()
        self.tasks = self.store.load_tasks()

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.apply_window_behavior_settings()
        self.apply_icon_settings()
        self.setMinimumSize(MAIN_WINDOW_MINIMUM_WIDTH, MAIN_WINDOW_MINIMUM_HEIGHT)
        self.apply_saved_geometry()

        self.clock_label = ClockDisplay()
        self.today_completion_label = QLabel("0%")
        self.active_count_label = QLabel("0")
        self.focus_title_label = QLabel("没有进行中的任务")
        self.focus_meta_label = QLabel("工作量 --")
        self.focus_deadline_label = QLabel("截止 --:--:--")
        self.focus_countdown_label = QLabel("--:--:--")
        self.focus_countdown_label.setObjectName("focusCountdownLabel")
        self.focus_countdown_label.setAlignment(Qt.AlignCenter)
        self.focus_countdown_label.setMinimumWidth(220)
        self.focus_priority_label = QLabel("--")
        self.focus_priority_label.setObjectName("focusPriorityLabel")
        self.focus_priority_label.setAlignment(Qt.AlignCenter)
        self.focus_priority_label.setMinimumHeight(34)
        self.focus_urgency_label = QLabel("等待")
        self.focus_progress = NoWheelSlider(Qt.Horizontal)
        self.focus_progress.setObjectName("focusProgress")
        self.focus_progress.setRange(0, 100)
        self.focus_progress.valueChanged.connect(self.update_focus_progress)
        self.focus_progress.sliderReleased.connect(self.commit_focus_progress)
        self.focus_progress_label = NoWheelSpinBox()
        self.focus_progress_label.setObjectName("focusProgressValue")
        self.focus_progress_label.setRange(0, 100)
        self.focus_progress_label.setSuffix("%")
        self.focus_progress_label.setAlignment(Qt.AlignCenter)
        self.focus_progress_label.setFixedWidth(62)
        self.focus_progress_label.setFixedHeight(26)
        self.focus_progress_label.setStyleSheet(_progress_input_style(selected=True))
        self.focus_progress_label.valueChanged.connect(self.update_focus_progress_from_input)
        self.empty_state_label = QLabel("没有进行中的任务")
        self.empty_state_hint_label = QLabel("点击新增任务开始")
        self.task_rows_container = QWidget()
        self.task_rows_container.setObjectName("taskRowsContainer")
        self.task_rows_container.setStyleSheet("QWidget#taskRowsContainer { background: transparent; }")
        self.task_list_layout = QGridLayout(self.task_rows_container)
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
        self.focus_card.setMinimumHeight(FOCUS_CARD_MINIMUM_HEIGHT)
        self.focus_card.setStyleSheet(_card_style("normal", selected=True))
        apply_soft_shadow(self.focus_card, blur=34, y_offset=12, alpha=120)
        focus_layout = QVBoxLayout(self.focus_card)
        focus_layout.setContentsMargins(14, 12, 14, 12)
        focus_layout.setSpacing(10)

        focus_top = QGridLayout()
        focus_top.setContentsMargins(0, 0, 0, 0)
        focus_top.setHorizontalSpacing(10)
        focus_top.setVerticalSpacing(8)
        self.focus_top_layout = focus_top
        self.focus_title_prefix = QLabel("进行中")
        self.focus_title_prefix.setAlignment(Qt.AlignCenter)
        self.focus_title_prefix.setMinimumHeight(34)
        self.focus_title_prefix.setStyleSheet(_focus_status_style())
        self.focus_meta_label.setAlignment(Qt.AlignCenter)
        self.focus_meta_label.setMinimumHeight(34)
        self.focus_meta_label.setStyleSheet(_focus_meta_style())
        self.focus_urgency_label.setAlignment(Qt.AlignCenter)
        self.focus_urgency_label.setMinimumHeight(34)
        for index, widget in enumerate(
            (self.focus_title_prefix, self.focus_priority_label, self.focus_urgency_label, self.focus_meta_label)
        ):
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            focus_top.addWidget(widget, 0, index)
            focus_top.setColumnStretch(index, 1)

        deadline_panel = QFrame()
        deadline_panel.setObjectName("focusDeadlinePanel")
        deadline_panel.setStyleSheet(_focus_deadline_panel_style())
        deadline_panel.setMinimumHeight(FOCUS_DEADLINE_PANEL_MINIMUM_HEIGHT)
        deadline_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.focus_deadline_panel = deadline_panel
        deadline_layout = QVBoxLayout(deadline_panel)
        deadline_layout.setContentsMargins(12, 7, 12, 9)
        deadline_layout.setSpacing(4)
        self.focus_deadline_label.setAlignment(Qt.AlignCenter)
        self.focus_deadline_label.setMinimumWidth(220)
        deadline_layout.addWidget(self.focus_deadline_label)
        deadline_layout.addWidget(self.focus_countdown_label)
        focus_top.addWidget(deadline_panel, 0, 4, 2, 1)
        focus_top.setColumnMinimumWidth(4, 244)
        focus_top.setColumnStretch(4, 2)
        focus_layout.addLayout(focus_top)

        self.focus_title_label.setStyleSheet(_focus_title_style())
        self.focus_title_label.setWordWrap(True)
        self.focus_title_label.setMinimumHeight(46)
        self.focus_title_label.setMaximumHeight(96)
        self.focus_title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.focus_title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        focus_layout.addWidget(self.focus_title_label)
        self.focus_notes_label = QLabel()
        self.focus_notes_label.setWordWrap(True)
        self.focus_notes_label.setObjectName("focusNotesLabel")
        self.focus_notes_label.setStyleSheet(_notes_style(selected=True))
        self.focus_notes_label.setMaximumHeight(62)
        self.focus_notes_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        focus_layout.addWidget(self.focus_notes_label)
        focus_progress_row = QHBoxLayout()
        focus_progress_row.setSpacing(10)
        progress_caption = QLabel("进度")
        progress_caption.setObjectName("focusProgressCaption")
        progress_caption.setAlignment(Qt.AlignCenter)
        progress_caption.setStyleSheet(_focus_status_style(compact=True))
        focus_progress_row.addWidget(progress_caption)
        focus_progress_row.addWidget(self.focus_progress, 1)
        focus_progress_row.addWidget(self.focus_progress_label)
        focus_layout.addLayout(focus_progress_row)
        focus_actions = QHBoxLayout()
        focus_actions.addStretch(1)
        self.focus_edit_button = QPushButton("编辑")
        self.focus_edit_button.setToolTip("编辑当前进行中的任务")
        self.focus_edit_button.clicked.connect(self.edit_focus_task)
        focus_actions.addWidget(self.focus_edit_button)
        self.focus_pause_button = QPushButton("Ⅱ")
        self.focus_pause_button.setObjectName("focusPauseButton")
        self.focus_pause_button.setToolTip("暂停当前任务，暂时移出进行中和提醒")
        self.focus_pause_button.setAccessibleName("暂停或继续当前任务")
        self.focus_pause_button.setFixedSize(44, 36)
        self.focus_pause_button.clicked.connect(self.toggle_focus_pause_task)
        focus_actions.addWidget(self.focus_pause_button)
        self.focus_resume_button = QPushButton()
        self.focus_resume_button.hide()
        self.focus_resume_button.clicked.connect(self.resume_focus_task)
        self.focus_complete_button = QPushButton("完成")
        self.focus_complete_button.setObjectName("focusCompleteButton")
        self.focus_complete_button.setToolTip("完成当前进行中的任务")
        self.focus_complete_button.clicked.connect(self.complete_focus_task)
        focus_actions.addWidget(self.focus_complete_button)
        self.focus_delete_button = QPushButton("删除")
        self.focus_delete_button.setObjectName("dangerButton")
        self.focus_delete_button.setToolTip("删除当前进行中的任务")
        self.focus_delete_button.clicked.connect(self.delete_focus_task)
        focus_actions.addWidget(self.focus_delete_button)
        focus_layout.addLayout(focus_actions)
        root_layout.addWidget(self.focus_card)
        self._sync_focus_header_layout()

        self.task_section_widget = QWidget()
        self.task_section_widget.setMinimumHeight(TASK_SECTION_MINIMUM_HEIGHT)
        self.task_section_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_layout = QHBoxLayout(self.task_section_widget)
        actions_layout.setContentsMargins(0, 6, 0, 6)
        actions_layout.setAlignment(Qt.AlignVCenter)
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
        self.task_list_layout.setHorizontalSpacing(10)
        self.task_list_layout.setVerticalSpacing(10)
        self.task_list_layout.setAlignment(Qt.AlignTop)
        self.task_scroll_area = QScrollArea()
        self.task_scroll_area.setWidgetResizable(True)
        self.task_scroll_area.setFrameShape(QFrame.NoFrame)
        self.task_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_scroll_area.verticalScrollBar().setSingleStep(32)
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
                (
                    task
                    for task in self.tasks
                    if task.id == self.settings.focus_task_id and task.status in {"active", "paused"}
                ),
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
        self._pulse_widget(self.focus_card)

    def edit_focus_task(self) -> None:
        focused = self.focus_task()
        if focused is None:
            return
        self.edit_task(focused.id)

    def complete_focus_task(self) -> None:
        focused = self.focus_task()
        if focused is None:
            return
        self.complete_task(focused.id)

    def pause_focus_task(self) -> None:
        focused = self.focus_task()
        if focused is None or focused.status != "active":
            return
        self.pause_task(focused.id)

    def resume_focus_task(self) -> None:
        focused = self.focus_task()
        if focused is None or focused.status != "paused":
            return
        self.resume_task(focused.id, make_focus=True)

    def toggle_focus_pause_task(self) -> None:
        focused = self.focus_task()
        if focused is None:
            return
        if focused.status == "paused":
            self.resume_task(focused.id, make_focus=True)
            return
        if focused.status == "active":
            self.pause_task(focused.id)

    def delete_focus_task(self) -> None:
        focused = self.focus_task()
        if focused is None:
            return
        self.delete_task(focused.id)

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
        self._set_focus_progress_input(value)
        if self.focus_progress.isSliderDown():
            return
        self._commit_focus_progress(value)

    def update_focus_progress_from_input(self, value: int) -> None:
        self.focus_progress.blockSignals(True)
        try:
            self.focus_progress.setValue(value)
        finally:
            self.focus_progress.blockSignals(False)
        self._commit_focus_progress(value)

    def commit_focus_progress(self) -> None:
        self._commit_focus_progress(self.focus_progress.value())

    def _set_focus_progress_input(self, value: int) -> None:
        self.focus_progress_label.blockSignals(True)
        try:
            self.focus_progress_label.setValue(value)
        finally:
            self.focus_progress_label.blockSignals(False)

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
        prepare_window_entrance(dialog)
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
        prepare_window_entrance(dialog)
        if dialog.exec() != QDialog.Accepted:
            return
        updated = dialog.build_task()
        if not updated.title.strip():
            return
        self.tasks = [*self.tasks[:index], updated, *self.tasks[index + 1 :]]
        self.store.save_tasks(self.tasks)
        self.refresh()

    def pause_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None or self.tasks[index].status != "active":
            return
        now = datetime.now(timezone.utc)
        paused = replace(self.tasks[index], status="paused", updated_at=now)
        self.tasks = [*self.tasks[:index], paused, *self.tasks[index + 1 :]]
        self.settings = replace(self.settings, focus_task_id=task_id)
        self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh()
        self.show_toast("已暂停", f"{paused.title}\n暂时移出进行中与提醒，需要时点继续恢复。", kind="info", duration_ms=4200)

    def resume_task(self, task_id: str, *, make_focus: bool = False) -> None:
        index = self._task_index(task_id)
        if index is None or self.tasks[index].status != "paused":
            return
        now = datetime.now(timezone.utc)
        resumed = replace(self.tasks[index], status="active", updated_at=now)
        self.tasks = [*self.tasks[:index], resumed, *self.tasks[index + 1 :]]
        if make_focus:
            self.settings = replace(self.settings, focus_task_id=task_id)
            self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh()
        self.show_toast("已继续", f"{resumed.title}\n已恢复到进行中任务。", kind="success", duration_ms=3800)
        if make_focus:
            self._pulse_widget(self.focus_card)

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
        self.show_completion_encouragement(completed)

    def confirm_complete_task(self, task: Task) -> bool:
        dialog = CompletionDialog(task, self)
        prepare_window_entrance(dialog)
        return dialog.exec() == QDialog.Accepted

    def show_completion_encouragement(self, task: Task) -> None:
        title, body = completion_toast_copy(task)
        message = f"{task.title}\n{body}"
        self.show_toast(title, message, kind="success", duration_ms=5600)

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
        prepare_window_entrance(dialog)
        return dialog.exec() == QDialog.Accepted

    def open_history(self) -> None:
        dialog = HistoryWindow(self.tasks, self.store, self)
        prepare_window_entrance(dialog)
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
        self.setWindowFlag(Qt.WindowTransparentForInput, self.mouse_passthrough_active())
        self.setWindowTitle(f"{APP_DISPLAY_NAME} · 穿透模式" if self.mouse_passthrough_active() else APP_DISPLAY_NAME)
        self._update_passthrough_hint()
        self._sync_tray_actions()

    def apply_icon_settings(self) -> None:
        self._apply_icon_for_settings(self.settings)

    def _apply_icon_for_settings(self, settings: AppSettings) -> None:
        icon = QIcon(str(resolved_icon_path(settings.icon_path)))
        self.setWindowIcon(icon)
        tray_controller = self.tray_controller
        sync_icon = getattr(tray_controller, "sync_icon", None)
        if callable(sync_icon):
            sync_icon(icon)

    def mouse_passthrough_active(self) -> bool:
        return bool(
            self.settings.always_on_top and self.settings.mouse_passthrough and self._mouse_passthrough_can_be_restored()
        )

    def _mouse_passthrough_can_be_restored(self) -> bool:
        tray_controller = self.tray_controller
        if tray_controller is None:
            return False
        is_available = getattr(tray_controller, "is_available", None)
        return not callable(is_available) or bool(is_available())

    def set_mouse_passthrough(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled:
            self.settings = replace(self.settings, always_on_top=True, mouse_passthrough=True)
        else:
            self.settings = replace(self.settings, mouse_passthrough=False)
        self._save_settings()
        self.apply_window_behavior_settings()
        self.show()

    def toggle_mouse_passthrough(self) -> None:
        self.set_mouse_passthrough(not self.mouse_passthrough_active())

    def _update_passthrough_hint(self) -> None:
        hint = getattr(self, "passthrough_hint_label", None)
        if hint is not None:
            hint.setVisible(self.mouse_passthrough_active())

    def _sync_tray_actions(self) -> None:
        tray_controller = self.tray_controller
        sync_actions = getattr(tray_controller, "sync_actions", None)
        if callable(sync_actions):
            sync_actions()

    def apply_background_settings(self) -> None:
        self.root_widget.set_background_settings(
            self.settings.background_enabled,
            self.settings.background_image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )

    def preview_settings(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self._apply_icon_for_settings(settings)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            settings.background_image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )

    def restore_settings_preview(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self._apply_icon_for_settings(settings)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            settings.background_image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )

    def apply_low_distraction_settings(self) -> None:
        self.summary_widget.show()
        self.task_section_widget.show()
        self.task_scroll_area.show()
        self.empty_state_widget.setHidden(bool(self.focus_task()))
        self.focus_card.show()

    def apply_saved_geometry(self) -> None:
        geometry = self.settings.window_geometry
        self.setGeometry(int(geometry["x"]), int(geometry["y"]), int(geometry["width"]), int(geometry["height"]))

    def open_settings(self) -> None:
        previous_settings = self.settings
        dialog = SettingsWindow(self.settings, self)
        prepare_window_entrance(dialog)
        if dialog.exec() != QDialog.Accepted:
            self.restore_settings_preview(previous_settings)
            return
        updated_settings = remove_deprecated_setting_features(dialog.build_settings())
        if updated_settings.mouse_passthrough and not updated_settings.always_on_top:
            updated_settings = replace(updated_settings, mouse_passthrough=False)
        if updated_settings.launch_on_startup != self.settings.launch_on_startup:
            try:
                set_launch_on_startup(APP_STARTUP_NAME, current_startup_command(), updated_settings.launch_on_startup)
            except OSError as exc:
                self.restore_settings_preview(previous_settings)
                QMessageBox.warning(self, "启动设置失败", f"无法更新开机启动设置：{exc}")
                return

        if updated_settings.mouse_passthrough and not previous_settings.mouse_passthrough:
            self.show_mouse_passthrough_notice()
        self.settings = updated_settings
        self._save_settings()
        self._restoring_geometry = True
        try:
            self.apply_window_behavior_settings()
            self.apply_icon_settings()
            self.apply_background_settings()
            self.apply_low_distraction_settings()
            if self.settings.lock_position:
                self.apply_saved_geometry()
            self.show()
        finally:
            self._restoring_geometry = False

    def show_mouse_passthrough_notice(self) -> None:
        QMessageBox.information(
            self,
            "鼠标穿透已开启",
            "浮窗会继续置顶显示，但鼠标点击会落到后方窗口。\n\n需要恢复时，请右键托盘图标，选择“退出鼠标穿透”。",
        )

    def can_close_to_tray(self) -> bool:
        tray_controller = self.tray_controller
        return bool(self.settings.close_to_tray and tray_controller is not None and tray_controller.is_available())

    def closeEvent(self, event) -> None:
        if self.can_close_to_tray():
            event.ignore()
            self.hide()
            return
        self._clock_timer.stop()
        self.close_toasts()
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
        self._sync_focus_header_layout()
        self._handle_geometry_change()

    def _sync_focus_header_layout(self) -> None:
        layout = getattr(self, "focus_top_layout", None)
        deadline_panel = getattr(self, "focus_deadline_panel", None)
        if layout is None or deadline_panel is None:
            return
        layout.removeWidget(deadline_panel)
        narrow = self.width() < 720
        if narrow:
            layout.addWidget(deadline_panel, 1, 0, 1, 4)
            layout.setColumnMinimumWidth(4, 0)
            layout.setColumnStretch(4, 0)
            self.focus_deadline_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.focus_countdown_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return
        layout.addWidget(deadline_panel, 0, 4, 2, 1)
        layout.setColumnMinimumWidth(4, 244)
        layout.setColumnStretch(4, 2)
        self.focus_deadline_label.setAlignment(Qt.AlignCenter)
        self.focus_countdown_label.setAlignment(Qt.AlignCenter)

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

    def _pulse_widget(self, widget: QWidget) -> None:
        add_click_pulse = getattr(self.root_widget, "add_click_pulse", None)
        if not callable(add_click_pulse):
            return
        add_click_pulse(self.root_widget.mapFromGlobal(widget.mapToGlobal(widget.rect().center())))

    def show_toast(self, title: str, message: str, *, kind: str = "info", duration_ms: int = 7000) -> FloatingToast:
        popup = FloatingToast(title, message, kind=kind)
        self._toast_popups = [toast for toast in self._toast_popups if toast.isVisible()]
        self._toast_popups.append(popup)
        popup.destroyed.connect(lambda *args, popup=popup: self._forget_toast(popup))
        popup.show_near(self, duration_ms=duration_ms, stack_index=len(self._toast_popups) - 1)
        return popup

    def _forget_toast(self, popup: FloatingToast) -> None:
        self._toast_popups = [toast for toast in self._toast_popups if toast is not popup and toast.isVisible()]

    def close_toasts(self) -> None:
        for popup in list(self._toast_popups):
            popup.close()
        self._toast_popups = []

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
                DEFAULT_NOTIFICATION_REPEAT_MINUTES,
            ):
                self.notification_sender.send(event_titles[event], updated_task.title)
                self.show_reminder_popup(event, updated_task)
                updated_task = mark_event_sent(updated_task, event, now)
                changed = True
            updated_tasks.append(updated_task)
        if changed:
            self.tasks = updated_tasks
            self.store.save_tasks(self.tasks)

    def show_reminder_popup(self, event: str, task: Task) -> None:
        title = "临近截止" if event == "deadline_warning" else "已经超时"
        if event == "deadline_warning":
            message = f"{task.title}\n先推进最关键的一步，别让它滑到最后一刻。"
            kind = "warning"
        else:
            message = f"{task.title}\n建议现在重新确认优先级，先把下一步落下来。"
            kind = "danger"
        self.show_toast(title, message, kind=kind, duration_ms=7200)

    def refresh(self) -> None:
        self.update_clock()
        if self._task_drag_active:
            self._task_drag_refresh_pending = True
            return
        self.tasks = self.store.load_tasks()
        now = datetime.now(timezone.utc)
        self.process_reminders(now)
        active_count = sum(1 for task in self.tasks if task.status == "active")
        paused_count = sum(1 for task in self.tasks if task.status == "paused")
        self.active_count_label.setText(str(active_count))
        self.today_completion_label.setText(f"{today_completion_percent(self.tasks)}%")

        focus_task = self.focus_task()
        self.focus_progress.blockSignals(True)
        self.focus_progress_label.blockSignals(True)
        if focus_task is None:
            self.focus_title_label.setText("没有进行中的任务")
            self.focus_title_label.setToolTip("")
            self.focus_meta_label.setText("工作量 --")
            self.focus_notes_label.clear()
            self.focus_notes_label.hide()
            self.focus_deadline_label.setText("截止 --:--:--")
            self.focus_deadline_label.setStyleSheet(_deadline_label_style("none"))
            self.focus_countdown_label.setText("--:--:--")
            self.focus_countdown_label.setStyleSheet(_countdown_label_style("none", pulse=False))
            self.focus_priority_label.setText("--")
            self.focus_priority_label.setStyleSheet(_priority_chip_style("none"))
            self.focus_urgency_label.setText("等待")
            self.focus_urgency_label.setStyleSheet(_urgency_chip_style("none"))
            self.focus_card.setStyleSheet(_card_style("normal", selected=True))
            self.focus_progress.setValue(0)
            self.focus_progress_label.setValue(0)
            self._set_focus_action_state(None)
            self.empty_state_hint_label.setText("可继续暂停任务，或点击新增任务" if paused_count else "点击新增任务开始")
            self.empty_state_widget.show()
        else:
            is_paused_focus = focus_task.status == "paused"
            urgency, urgency_label = ("paused", "已暂停") if is_paused_focus else deadline_urgency(focus_task.deadline, now)
            self.focus_title_label.setText(focus_task.title)
            self.focus_title_label.setToolTip(focus_task.title)
            self.focus_meta_label.setText(f"工作量 {focus_task.effort_minutes} min")
            self._set_focus_notes(focus_task.notes)
            self.focus_priority_label.setText(focus_task.priority)
            self.focus_priority_label.setStyleSheet(_priority_chip_style(focus_task.priority))
            self.focus_deadline_label.setText(f"截止 {deadline_at_label(focus_task.deadline)}")
            self.focus_deadline_label.setStyleSheet(_deadline_label_style(urgency))
            countdown_pulse = False
            countdown_text = _countdown_display(countdown_label(focus_task.deadline, now), countdown_pulse)
            if self.focus_countdown_label.text() != countdown_text:
                self.focus_countdown_label.setText(countdown_text)
                if self.isVisible():
                    animate_value_tick(self.focus_countdown_label, duration=170)
            self.focus_countdown_label.setStyleSheet(_countdown_label_style(urgency, pulse=countdown_pulse))
            self.focus_urgency_label.setText(urgency_label)
            self.focus_urgency_label.setStyleSheet(_urgency_chip_style(urgency))
            self.focus_card.setStyleSheet(_card_style(urgency, selected=True))
            self.focus_progress.setValue(focus_task.progress)
            self.focus_progress_label.setValue(focus_task.progress)
            self._set_focus_action_state(focus_task.status)
            self.empty_state_widget.hide()
        self.focus_progress.blockSignals(False)
        self.focus_progress_label.blockSignals(False)

        self._render_task_rows(task_rows(self.tasks, now), focus_task.id if focus_task else None)
        self.apply_low_distraction_settings()

    def _render_task_rows(self, rows: list[dict[str, object]], focus_task_id: str | None = None) -> None:
        active_ids = {str(row["id"]) for row in rows}
        self.expanded_task_ids.intersection_update(active_ids)
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        columns = self._task_grid_columns()
        for column in range(5):
            self.task_list_layout.setColumnStretch(column, 1 if column < columns else 0)
        for index, row in enumerate(rows):
            self.task_list_layout.addWidget(self._task_row(row, focus_task_id), index // columns, index % columns)

    def _task_grid_columns(self) -> int:
        width = self.task_scroll_area.viewport().width() if hasattr(self, "task_scroll_area") else self.width()
        if width >= 900:
            return 4
        if width >= 680:
            return 3
        if width >= 460:
            return 2
        return 1

    def toggle_task_details(self, task_id: str) -> None:
        if task_id in self.expanded_task_ids:
            self.expanded_task_ids.remove(task_id)
        else:
            self.expanded_task_ids.add(task_id)
        self.refresh()

    def _task_row(self, row: dict[str, object], focus_task_id: str | None = None) -> QFrame:
        task_id = str(row["id"])
        urgency = str(row["urgency"])
        is_paused = bool(row.get("is_paused"))
        is_focused = task_id == focus_task_id
        is_expanded = task_id in self.expanded_task_ids
        card = TaskRowCard(task_id, self)
        card.setObjectName(f"taskRow-{task_id}")
        card.setStyleSheet(_card_style(urgency, selected=is_focused))
        card.setMinimumHeight(218 if is_expanded else 154)
        card.setMinimumWidth(168)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_soft_shadow(card, blur=32 if is_focused else 22, y_offset=9, alpha=130 if is_focused else 80)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.setSpacing(6)

        top = QHBoxLayout()
        priority = QLabel(str(row["priority"]))
        priority.setAlignment(Qt.AlignCenter)
        priority.setFixedHeight(30)
        priority.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        priority.setStyleSheet(_priority_chip_style(str(row["priority"])))
        top.addWidget(priority)
        urgency_chip = QLabel(str(row["urgency_label"]))
        urgency_chip.setAlignment(Qt.AlignCenter)
        urgency_chip.setFixedHeight(30)
        urgency_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        urgency_chip.setStyleSheet(_urgency_chip_style(urgency))
        top.addWidget(urgency_chip)
        top.addStretch(1)
        progress_label = QLabel(str(row["progress_label"]))
        progress_label.setObjectName("activeTaskProgressValue" if is_focused else "taskProgressValue")
        progress_label.setAlignment(Qt.AlignCenter)
        progress_label.setFixedHeight(30)
        progress_label.setStyleSheet(_progress_value_style(selected=is_focused))
        top.addWidget(progress_label)
        layout.addLayout(top)

        title = QLabel(str(row["title"]))
        title.setObjectName("activeTaskTitle" if is_focused else "taskTitle")
        title.setToolTip(str(row["title"]))
        title.setWordWrap(True)
        title.setMinimumHeight(38)
        title.setMaximumHeight(44)
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title.setStyleSheet(_task_title_style(selected=is_focused))
        layout.addWidget(title)

        deadline = QLabel(f"截止 {row['deadline_at_label']} · {row['deadline_label']}")
        deadline.setObjectName("activeTaskDeadline" if is_focused else "taskDeadline")
        deadline.setWordWrap(True)
        deadline.setMinimumHeight(28)
        deadline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        deadline.setStyleSheet(_deadline_label_style(urgency))
        layout.addWidget(deadline)

        compact_row = QHBoxLayout()
        compact_row.setSpacing(6)
        compact_row.addStretch(1)
        if is_paused:
            resume_button = QPushButton()
            self._configure_pause_resume_button(resume_button, paused=True)
            resume_button.setToolTip("恢复任务，并设为当前进行中")
            resume_button.clicked.connect(lambda checked=False, task_id=task_id: self.resume_task(task_id, make_focus=True))
            compact_row.addWidget(resume_button)
        else:
            focus_button = QPushButton("进行中" if is_focused else "置顶")
            focus_button.setToolTip("设为当前置顶任务；之后点击其它任务的置顶即可替换")
            if is_focused:
                focus_button.setObjectName("currentTaskButton")
            focus_button.clicked.connect(lambda checked=False, task_id=task_id: self.set_focus_task(task_id))
            compact_row.addWidget(focus_button)
        expand_button = QPushButton("收起" if is_expanded else "展开")
        expand_button.setObjectName("taskCollapseButton" if is_expanded else "taskExpandButton")
        expand_button.setToolTip("显示或收起详细操作")
        expand_button.clicked.connect(lambda checked=False, task_id=task_id: self.toggle_task_details(task_id))
        compact_row.addWidget(expand_button)
        layout.addLayout(compact_row)

        if not is_expanded:
            return card

        notes_text = _note_preview(str(row.get("notes", "")), limit=78)
        if notes_text:
            notes_label = QLabel(f"备注：{notes_text}")
            notes_label.setWordWrap(True)
            notes_label.setObjectName("taskNotesPreview")
            notes_label.setStyleSheet(_notes_style(selected=is_focused))
            layout.addWidget(notes_label)

        progress = NoWheelSlider(Qt.Horizontal)
        progress.setObjectName("activeTaskProgress" if is_focused else "taskProgress")
        progress.setRange(0, 100)
        progress.setValue(int(row["progress"]))
        progress_input = NoWheelSpinBox()
        progress_input.setObjectName("activeTaskProgressInput" if is_focused else "taskProgressInput")
        progress_input.setRange(0, 100)
        progress_input.setSuffix("%")
        progress_input.setAlignment(Qt.AlignCenter)
        progress_input.setFixedWidth(58)
        progress_input.setFixedHeight(24)
        progress_input.setValue(int(row["progress"]))
        progress_input.setStyleSheet(_progress_input_style(selected=is_focused))
        progress.valueChanged.connect(
            lambda value, task_id=task_id, slider=progress, label=progress_label, value_input=progress_input: self._handle_row_progress_value(
                task_id, slider, label, value_input, value
            )
        )
        progress.sliderReleased.connect(lambda task_id=task_id, slider=progress: self.update_task_progress(task_id, slider.value()))
        progress_input.valueChanged.connect(
            lambda value, task_id=task_id, slider=progress, label=progress_label: self._handle_row_progress_input(
                task_id, slider, label, value
            )
        )
        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        progress_row.addWidget(progress, 1)
        progress_row.addWidget(progress_input)
        layout.addLayout(progress_row)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(6)
        detail_row.addWidget(QLabel(f"工作量 {row['effort_label']}"))
        detail_row.addStretch(1)
        pause_button = QPushButton()
        self._configure_pause_resume_button(pause_button, paused=is_paused)
        if is_paused:
            pause_button.setToolTip("恢复任务，并设为当前进行中")
            pause_button.clicked.connect(lambda checked=False, task_id=task_id: self.resume_task(task_id, make_focus=True))
        else:
            pause_button.clicked.connect(lambda checked=False, task_id=task_id: self.pause_task(task_id))
        detail_row.addWidget(pause_button)
        edit_button = QPushButton("编辑")
        edit_button.setToolTip("编辑任务")
        edit_button.clicked.connect(lambda checked=False, task_id=task_id: self.edit_task(task_id))
        detail_row.addWidget(edit_button)
        complete_button = QPushButton("完成")
        complete_button.setToolTip("标记任务完成")
        complete_button.clicked.connect(lambda checked=False, task_id=task_id: self.complete_task(task_id))
        detail_row.addWidget(complete_button)
        delete_button = QPushButton("删除")
        delete_button.setToolTip("删除任务")
        delete_button.clicked.connect(lambda checked=False, task_id=task_id: self.delete_task(task_id))
        detail_row.addWidget(delete_button)
        layout.addLayout(detail_row)
        return card

    def _handle_row_progress_value(
        self, task_id: str, slider: NoWheelSlider, label: QLabel, value_input: NoWheelSpinBox, value: int
    ) -> None:
        label.setText(f"{value}%")
        value_input.blockSignals(True)
        try:
            value_input.setValue(value)
        finally:
            value_input.blockSignals(False)
        if slider.isSliderDown():
            return
        self.update_task_progress(task_id, value)

    def _handle_row_progress_input(self, task_id: str, slider: NoWheelSlider, label: QLabel, value: int) -> None:
        label.setText(f"{value}%")
        slider.blockSignals(True)
        try:
            slider.setValue(value)
        finally:
            slider.blockSignals(False)
        self.update_task_progress(task_id, value)

    def _set_focus_action_enabled(self, enabled: bool) -> None:
        self._set_focus_action_state("active" if enabled else None)

    def _set_focus_action_state(self, status: str | None) -> None:
        has_task = status in {"active", "paused"}
        self.focus_edit_button.setEnabled(has_task)
        self._configure_pause_resume_button(self.focus_pause_button, paused=status == "paused", focus=True)
        self.focus_pause_button.setEnabled(has_task)
        self.focus_resume_button.setEnabled(status == "paused")
        self.focus_complete_button.setEnabled(has_task)
        self.focus_delete_button.setEnabled(has_task)
        self.focus_progress.setEnabled(has_task)
        self.focus_progress_label.setEnabled(has_task)

    def _configure_pause_resume_button(self, button: QPushButton, *, paused: bool, focus: bool = False) -> None:
        if paused:
            button.setText("▶")
            button.setObjectName("resumeTaskButton")
            button.setToolTip("继续暂停中的当前任务")
            button.setAccessibleName("继续任务")
        else:
            button.setText("Ⅱ")
            button.setObjectName("focusPauseButton" if focus else "pauseTaskButton")
            button.setToolTip("暂停任务，暂时移出进行中和提醒")
            button.setAccessibleName("暂停任务")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(44, 36)
        button.style().unpolish(button)
        button.style().polish(button)

    def _set_focus_notes(self, notes: str) -> None:
        preview = _note_preview(notes, limit=92)
        if not preview:
            self.focus_notes_label.clear()
            self.focus_notes_label.hide()
            return
        self.focus_notes_label.setText(f"备注：{preview}")
        self.focus_notes_label.show()


URGENCY_STYLES = {
    "none": {
        "surface": "#111722",
        "surface_alt": "#151B27",
        "selected": "#1A2230",
        "accent": THEME_COLORS["muted"],
        "chip_bg": "#202838",
        "chip_text": "#C9D2E4",
    },
    "paused": {
        "surface": "#10141F",
        "surface_alt": "#151C2A",
        "selected": "#1D2738",
        "accent": "#93A4B8",
        "chip_bg": "#263142",
        "chip_text": "#D6E1F0",
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
    glow_stop = "#24465A" if selected else selected_stop
    mid_stop = "#132536" if selected else THEME_COLORS["surface"]
    return (
        "QFrame {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        f" stop:0 {style['surface']},"
        f" stop:0.46 {mid_stop},"
        f" stop:1 {glow_stop});"
        "border: none;"
        "border-radius: 8px;"
        "}"
    )


def _urgency_chip_style(urgency: str) -> str:
    style = _urgency_style(urgency)
    return (
        "font-size: 14px; font-weight: 900; padding: 5px 10px; border-radius: 8px; min-width: 72px; "
        f"background: {style['chip_bg']}; color: {style['chip_text']};"
    )


def _deadline_label_style(urgency: str) -> str:
    return f"color: {_countdown_style(urgency)['accent']}; font-weight: 800; font-size: 13px;"


def _countdown_label_style(urgency: str, *, pulse: bool) -> str:
    style = _countdown_style(urgency)
    start = style["start_pulse"] if pulse else style["start"]
    end = style["end_pulse"] if pulse else style["end"]
    return (
        f"color: {style['text']};"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        f" stop:0 {start},"
        f" stop:1 {end});"
        "border: none;"
        "border-radius: 8px;"
        "padding: 5px 14px;"
        "min-height: 42px;"
        "min-width: 154px;"
        "font-size: 30px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Segoe UI Variable", "Microsoft YaHei UI";'
        f"selection-background-color: {style['accent']};"
    )


def _countdown_display(text: str, pulse: bool) -> str:
    return text


def _focus_title_style() -> str:
    return (
        "font-size: 24px;"
        "font-weight: 900;"
        "color: #F8FBFF;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #143044,"
        " stop:0.58 #10263A,"
        " stop:1 #0F1A2A);"
        "border: none;"
        "border-radius: 8px;"
        "padding: 8px 12px;"
    )


def _focus_status_style(*, compact: bool = False) -> str:
    min_width = "56px" if compact else "72px"
    return (
        "color: #BAE6FD;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #10263A,"
        " stop:1 #0F4C5C);"
        "border: none;"
        "border-radius: 8px;"
        "font-size: 14px;"
        "font-weight: 900;"
        "padding: 5px 10px;"
        f"min-width: {min_width};"
    )


def _focus_deadline_panel_style() -> str:
    return (
        "QFrame#focusDeadlinePanel {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        " stop:0 #0A1421,"
        " stop:0.45 #10263A,"
        " stop:1 #143A3E);"
        "border: none;"
        "border-radius: 8px;"
        "}"
    )


def _focus_meta_style() -> str:
    return (
        "font-size: 14px;"
        "font-weight: 900;"
        "color: #D9FBE8;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #123B34,"
        " stop:1 #0F4C5C);"
        "border: none;"
        "border-radius: 8px;"
        "padding: 5px 9px;"
    )


def _task_title_style(*, selected: bool = False) -> str:
    if selected:
        background = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #143B56, stop:1 #143D48)"
        color = "#F8FBFF"
    else:
        background = "#0A121E"
        color = "#F3F7FC"
    return (
        f"color: {color};"
        f"background: {background};"
        "border: none;"
        "border-radius: 8px;"
        "padding: 4px 8px;"
        "font-size: 15px;"
        "font-weight: 900;"
        "line-height: 18px;"
    )


def _progress_value_style(*, selected: bool = False) -> str:
    if selected:
        return (
            "font-weight: 800; min-width: 48px; padding: 1px 8px; border-radius: 8px; "
            "color: #ECFEFF; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #155E75, stop:0.55 #0E7490, stop:1 #047857);"
        )
    return (
        f"font-weight: 700; min-width: 48px; padding: 1px 8px; border-radius: 8px; "
        f"color: {THEME_COLORS['accent']}; background: #102033;"
    )


def _progress_input_style(*, selected: bool = False) -> str:
    if selected:
        background = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #155E75, stop:0.55 #0E7490, stop:1 #047857)"
        color = "#ECFEFF"
    else:
        background = "#102033"
        color = THEME_COLORS["accent"]
    return (
        "QSpinBox {"
        f"background: {background};"
        f"color: {color};"
        "border: none;"
        "border-radius: 8px;"
        "font-weight: 800;"
        "padding: 1px 8px;"
        "selection-background-color: #1D4ED8;"
        "}"
        "QSpinBox:focus {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0E7490, stop:1 #16A34A);"
        "}"
        "QSpinBox:disabled {"
        "color: #5F6E7E;"
        "background: #111827;"
        "}"
        "QSpinBox::up-button, QSpinBox::down-button {"
        "width: 0px;"
        "border: none;"
        "}"
    )


def _notes_style(*, selected: bool = False) -> str:
    if selected:
        return (
            "color: #D7F8FF; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #14485C, stop:1 #166552);"
            "border: none; border-radius: 8px; padding: 6px 8px; font-weight: 600;"
        )
    return (
        f"color: {THEME_COLORS['muted']}; background: #101A27; "
        "border: none; border-radius: 8px; padding: 5px 8px;"
    )


def _note_preview(notes: str, *, limit: int = 72) -> str:
    text = " ".join(str(notes or "").split())
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


COMPLETION_TOAST_TITLES = (
    "完成得漂亮",
    "推进完成",
    "收尾成功",
    "又清掉一项",
    "节奏很好",
)

COMPLETION_ENCOURAGEMENTS = {
    "priority": (
        "关键任务已经落地，今天的主线更稳了。",
        "优先级最高的事项拿下了，后面的推进会轻很多。",
        "这一步很关键，你把它推进到闭环了。",
        "重要事项已经收住，接下来可以更从容。",
    ),
    "large": (
        "这是一块不小的工作量，完成它很值得记一笔。",
        "大块任务收尾了，给后面的时间腾出了空间。",
        "耐心推进到这里，很扎实。",
        "这类任务最消耗心力，你已经把它稳稳落地。",
    ),
    "progress": (
        "从推进到收尾已经闭环，继续保持这个节奏。",
        "最后一段也补上了，这个任务现在完整落地。",
        "把未完成的部分收住了，很稳。",
        "进度条走到终点，今天又多了一个确定结果。",
    ),
    "default": (
        "又完成一项，清单正在变轻。",
        "这一项已经归档，继续往前走。",
        "小闭环也很重要，今天又往前推进了一步。",
        "完成感正在积累，节奏保持得不错。",
    ),
}


def completion_toast_copy(task: Task) -> tuple[str, str]:
    body_options = COMPLETION_ENCOURAGEMENTS[_completion_encouragement_category(task)]
    return (
        _stable_pick(COMPLETION_TOAST_TITLES, task, salt="title"),
        _stable_pick(body_options, task, salt="body"),
    )


def completion_encouragement(task: Task) -> str:
    return completion_toast_copy(task)[1]


def _completion_encouragement_category(task: Task) -> str:
    if task.priority == "P1":
        return "priority"
    if task.effort_minutes >= 90:
        return "large"
    if task.progress < 100:
        return "progress"
    return "default"


def _stable_pick(options: tuple[str, ...], task: Task, *, salt: str) -> str:
    seed = f"{salt}|{task.id}|{task.title}|{task.priority}|{task.effort_minutes}|{task.created_at.isoformat()}"
    return options[sum(ord(character) for character in seed) % len(options)]


PRIORITY_STYLES = {
    "P1": {"background": "#5A2D12", "text": "#FFE1A6"},
    "P2": {"background": "#1B2F69", "text": "#DCE7FF"},
    "P3": {"background": "#123B34", "text": "#D9FBE8"},
    "none": {"background": "#202838", "text": "#C9D2E4"},
}


COUNTDOWN_STYLES = {
    "none": {
        "start": "#151C28",
        "end": "#1B2432",
        "start_pulse": "#1A2331",
        "end_pulse": "#222D3F",
        "accent": THEME_COLORS["muted"],
        "text": "#C9D2E4",
    },
    "paused": {
        "start": "#151C28",
        "end": "#263142",
        "start_pulse": "#1B2432",
        "end_pulse": "#334155",
        "accent": "#93A4B8",
        "text": "#D6E1F0",
    },
    "normal": {
        "start": "#0A2740",
        "end": "#0B4A60",
        "start_pulse": "#0D3454",
        "end_pulse": "#0E6074",
        "accent": "#7DD3FC",
        "text": "#DFF7FF",
    },
    "soon": {
        "start": "#0B3D47",
        "end": "#145B4D",
        "start_pulse": "#0E4D59",
        "end_pulse": "#18705C",
        "accent": "#A7F3D0",
        "text": "#E7FFF7",
    },
    "urgent": {
        "start": "#4A3114",
        "end": "#7A4515",
        "start_pulse": "#654019",
        "end_pulse": "#985C1C",
        "accent": "#F6C177",
        "text": "#FFF0CC",
    },
    "critical": {
        "start": "#5A2417",
        "end": "#9A3B18",
        "start_pulse": "#74301B",
        "end_pulse": "#BA4A1C",
        "accent": "#FDBA74",
        "text": "#FFE5D0",
    },
    "overdue": {
        "start": "#4B1422",
        "end": "#8B1D35",
        "start_pulse": "#64192D",
        "end_pulse": "#A52542",
        "accent": "#FCA5A5",
        "text": "#FFE0E7",
    },
}


def _priority_style(priority: str) -> dict[str, str]:
    return PRIORITY_STYLES.get(priority, PRIORITY_STYLES["none"])


def _priority_chip_style(priority: str) -> str:
    style = _priority_style(priority)
    return (
        "font-size: 14px; font-weight: 900; padding: 5px 10px; border-radius: 8px; min-width: 72px; "
        f"background: {style['background']}; color: {style['text']};"
    )


def _countdown_style(urgency: str) -> dict[str, str]:
    return COUNTDOWN_STYLES.get(urgency, COUNTDOWN_STYLES["normal"])
