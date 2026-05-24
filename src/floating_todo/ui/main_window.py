from __future__ import annotations

import random
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QDrag, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from floating_todo.app_resources import background_image_candidates, materialize_custom_resource
from floating_todo.app_identity import APP_DISPLAY_NAME, APP_STARTUP_NAME, resolved_icon_path
from floating_todo.domain import Task, freeze_work_timer, pause_work_timer, resume_work_timer, select_focus_task
from floating_todo.platform_windows import current_startup_command, set_launch_on_startup
from floating_todo.reminders import mark_event_sent, reminder_events
from floating_todo.settings import (
    AppSettings,
    DEFAULT_BACKGROUND_OVERLAY,
    DEFAULT_UI_SCALE,
    MAX_UI_SCALE,
    MIN_UI_SCALE,
    DEFAULT_NOTIFICATION_REPEAT_MINUTES,
    remove_deprecated_setting_features,
    settings_to_dict,
)
from floating_todo.store import save_json_object
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.backdrop import AnimatedBackdrop
from floating_todo.ui.completion_dialog import CompletionDialog
from floating_todo.ui.confirmation_dialog import DeleteTaskDialog
from floating_todo.ui.effects import (
    animate_content_swap,
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
    priority_text,
    task_rows,
    today_completion_percent,
    work_timer_label,
)


TASK_MIME_TYPE = "application/x-floating-todo-task-id"
UI_ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "ui"
MAIN_WINDOW_MINIMUM_WIDTH = 720
MAIN_WINDOW_MINIMUM_HEIGHT = 900
FOCUS_CARD_MINIMUM_HEIGHT = 390
FOCUS_DEADLINE_PANEL_MINIMUM_HEIGHT = 124
TASK_SECTION_MINIMUM_HEIGHT = 54
BACKGROUND_RANDOM_INTERVAL_MS = 3 * 60 * 1000
_CURRENT_UI_SCALE = DEFAULT_UI_SCALE
TASK_SCOPE_LABELS = {
    "all": "全部",
    "active": "进行中",
    "paused": "已暂停",
    "soon": "临近",
    "overdue": "超时",
}
TASK_SORT_LABELS = {
    "priority": "按优先级",
    "deadline": "按截止时间",
    "created": "按创建时间",
}


def _clamp_ui_scale(scale: float) -> float:
    return round(max(MIN_UI_SCALE, min(MAX_UI_SCALE, float(scale))), 2)


def _set_current_ui_scale(scale: float) -> None:
    global _CURRENT_UI_SCALE
    _CURRENT_UI_SCALE = _clamp_ui_scale(scale)


def _scale_px(value: int | float, *, minimum: int = 1) -> int:
    return max(minimum, int(round(float(value) * _CURRENT_UI_SCALE)))


def _apply_svg_icon(label: QLabel, icon_name: str, size: int) -> None:
    label.setPixmap(QIcon(str(UI_ICON_DIR / icon_name)).pixmap(QSize(size, size)))


def _priority_icon_name(priority: str) -> str:
    return {
        "P1": "priority-high.svg",
        "P2": "priority-medium.svg",
        "P3": "priority-low.svg",
    }.get(priority, "priority-medium.svg")


def _priority_inline_markup(priority: str, *, size: int = 14, text: str | None = None) -> str:
    icon_path = (UI_ICON_DIR / _priority_icon_name(priority)).as_posix()
    label_text = text if text is not None else priority_text(priority)
    return (
        f"<span style=\"white-space: nowrap;\">"
        f"<img src=\"{icon_path}\" width=\"{size}\" height=\"{size}\" "
        f"style=\"vertical-align: middle; margin-right: 6px;\"/>"
        f"{label_text}</span>"
    )


def _focus_info_card(object_name: str, icon_name: str, text_label: QLabel) -> QFrame:
    card = QFrame()
    card.setObjectName(object_name)
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    card.setMinimumHeight(_scale_px(52))

    layout = QHBoxLayout(card)
    layout.setContentsMargins(_scale_px(14), _scale_px(11), _scale_px(16), _scale_px(11))
    layout.setSpacing(_scale_px(10))

    icon = QLabel("")
    icon.setObjectName("focusInfoIcon")
    icon.setProperty("iconName", icon_name)
    icon.setAlignment(Qt.AlignCenter)
    icon.setFixedSize(_scale_px(28), _scale_px(28))
    _apply_svg_icon(icon, icon_name, _scale_px(15))
    layout.addWidget(icon, 0, Qt.AlignVCenter)

    text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout.addWidget(text_label, 1)
    return card


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
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.apply_scale()

    def apply_scale(self) -> None:
        self.setMinimumSize(_scale_px(150), _scale_px(42))
        self.setStyleSheet(
            "QLabel#clockLabel {"
            "color: #7DF9FF;"
            "background: transparent;"
            f"font-size: {_scale_px(26)}px;"
            "font-weight: 900;"
            'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
            f"padding: 0 {_scale_px(4)}px;"
            "}"
        )

    def setText(self, text: str) -> None:
        super().setText(text)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(self.font())
        rect = self.rect()
        for offset, alpha in ((2, 34), (1, 62)):
            painter.setPen(QColor(34, 211, 238, alpha))
            painter.drawText(rect.adjusted(-offset, 0, offset, 0), Qt.AlignCenter, self.text())
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


class TitleLogoBadge(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("titleLogoBadge")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.apply_scale()

    def apply_scale(self) -> None:
        self.setFixedSize(_scale_px(34), _scale_px(34))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        glow = QLinearGradient(rect.topLeft(), rect.bottomRight())
        glow.setColorAt(0, QColor(34, 211, 238, 76))
        glow.setColorAt(1, QColor(15, 118, 110, 42))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#22D3EE"), max(1.6, _scale_px(2)), Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(rect.adjusted(4, 4, -4, -4), 42 * 16, 288 * 16)
        check = QPainterPath()
        check.moveTo(rect.left() + rect.width() * 0.34, rect.top() + rect.height() * 0.52)
        check.lineTo(rect.left() + rect.width() * 0.46, rect.top() + rect.height() * 0.64)
        check.lineTo(rect.left() + rect.width() * 0.68, rect.top() + rect.height() * 0.38)
        painter.setPen(QPen(QColor("#B9F8FF"), max(1.8, _scale_px(2.2)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(check)
        dot = QRectF(rect.left() + rect.width() * 0.68, rect.top() + rect.height() * 0.13, _scale_px(4), _scale_px(4))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#5EEAD4"))
        painter.drawEllipse(dot)


class TitleBar(QFrame):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._drag_start: QPoint | None = None
        self.setObjectName("titleBar")
        self.setCursor(Qt.OpenHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            "QFrame#titleBar {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #061321,"
            " stop:0.45 #0B2035,"
            " stop:1 #082B34);"
            "border: none;"
            "border-radius: 14px;"
            "}"
            "QFrame#titleActionDock {"
            "background: transparent;"
            "border: none;"
            "}"
        )

        layout = QHBoxLayout(self)
        self.title_layout = layout
        layout.setAlignment(Qt.AlignVCenter)
        self.logo_badge = TitleLogoBadge(self)
        layout.addWidget(self.logo_badge)
        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("windowTitleLabel")
        self.title_label = title
        layout.addWidget(title)
        drag_hint = QLabel("拖动")
        drag_hint.setFixedWidth(4)
        self.drag_hint_label = drag_hint
        layout.addWidget(drag_hint)
        window.passthrough_hint_label = QLabel("穿透中 · 右键托盘恢复")
        window.passthrough_hint_label.setObjectName("passthroughHint")
        window.passthrough_hint_label.setStyleSheet(
            "color: #ECFEFF; background: #155E75; border-radius: 8px; padding: 3px 8px; font-weight: 800;"
        )
        window.passthrough_hint_label.setVisible(False)
        layout.addWidget(window.passthrough_hint_label)
        layout.addStretch(1)
        action_dock = QFrame()
        action_dock.setObjectName("titleActionDock")
        self.action_dock = action_dock
        action_layout = QHBoxLayout(action_dock)
        self.action_layout = action_layout
        action_layout.setAlignment(Qt.AlignVCenter)
        action_layout.addWidget(window.clock_label, 0, Qt.AlignVCenter)
        window.settings_button.setText("")
        window.settings_button.setObjectName("titleIconButton")
        window.settings_button.setToolTip("打开设置")
        window.settings_button.setAccessibleName("打开设置")
        window.settings_button.setIcon(QIcon(str(UI_ICON_DIR / "nav-settings.svg")))
        window.settings_button.setCursor(Qt.PointingHandCursor)
        action_layout.addWidget(window.settings_button, 0, Qt.AlignVCenter)
        window.minimize_button = QPushButton("")
        window.minimize_button.setObjectName("titleIconButton")
        window.minimize_button.setToolTip("最小化")
        window.minimize_button.setAccessibleName("最小化")
        window.minimize_button.setIcon(QIcon(str(UI_ICON_DIR / "window-minimize.svg")))
        window.minimize_button.setCursor(Qt.PointingHandCursor)
        window.minimize_button.clicked.connect(window.showMinimized)
        action_layout.addWidget(window.minimize_button, 0, Qt.AlignVCenter)
        window.close_button = QPushButton("")
        window.close_button.setObjectName("titleIconButton")
        window.close_button.setToolTip("关闭")
        window.close_button.setAccessibleName("关闭")
        window.close_button.setIcon(QIcon(str(UI_ICON_DIR / "window-close.svg")))
        window.close_button.setCursor(Qt.PointingHandCursor)
        window.close_button.clicked.connect(window.close)
        action_layout.addWidget(window.close_button, 0, Qt.AlignVCenter)
        window.title_action_dock = action_dock
        layout.addWidget(action_dock, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.apply_scale()

    def apply_scale(self) -> None:
        self.setMinimumHeight(_scale_px(58))
        self.title_layout.setContentsMargins(_scale_px(12), _scale_px(7), _scale_px(8), _scale_px(7))
        self.title_layout.setSpacing(_scale_px(8))
        self.logo_badge.apply_scale()
        self.title_label.setStyleSheet(f"font-size: {_scale_px(22)}px; font-weight: 900; color: #F8FBFF;")
        self.drag_hint_label.setStyleSheet(
            "color: transparent; "
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #22D3EE, stop:1 #0F766E); "
            f"border-radius: {_scale_px(2)}px;"
        )
        self.action_dock.setFixedHeight(_scale_px(46))
        self.action_layout.setContentsMargins(_scale_px(7), _scale_px(4), _scale_px(7), _scale_px(4))
        self.action_layout.setSpacing(_scale_px(8))
        self.window.clock_label.apply_scale()
        self.window.settings_button.setFixedSize(_scale_px(42), _scale_px(38))
        self.window.settings_button.setIconSize(QSize(_scale_px(18), _scale_px(18)))
        self.window.minimize_button.setFixedSize(_scale_px(42), _scale_px(38))
        self.window.minimize_button.setIconSize(QSize(_scale_px(18), _scale_px(18)))
        self.window.close_button.setFixedSize(_scale_px(42), _scale_px(38))
        self.window.close_button.setIconSize(QSize(_scale_px(18), _scale_px(18)))

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
        self.apply_scale()

    def apply_scale(self) -> None:
        self.setFixedSize(_scale_px(24), _scale_px(24))
        self._style_handle()

    def _style_handle(self) -> None:
        self.setToolTip("拖到上方设为进行中")
        self.setStyleSheet(
            f"background: {THEME_COLORS['surface_hover']}; "
            f"color: {THEME_COLORS['accent']}; "
            f"font-weight: 900; border-radius: {_scale_px(7)}px; font-size: {_scale_px(13)}px;"
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
        self.setCursor(Qt.SizeFDiagCursor)
        self.apply_scale()

    def apply_scale(self) -> None:
        self.setFixedSize(_scale_px(24), _scale_px(24))
        self.setToolTip("拖动调整窗口大小")
        self.setStyleSheet(
            "QFrame {"
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #1B3B4B,"
            " stop:1 #7DD3FC);"
            "border: none;"
            f"border-radius: {_scale_px(8)}px;"
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
        _set_current_ui_scale(self.settings.ui_scale)
        self.settings_path = Path(settings_path) if settings_path is not None else None
        self.notification_sender = notification_sender
        self.tray_controller = None
        self._geometry_initialized = False
        self._restoring_geometry = False
        self._task_drag_active = False
        self._task_drag_refresh_pending = False
        self._current_random_background_path = ""
        self._current_random_background_folder = ""
        self._background_random_timer = QTimer(self)
        self._background_random_timer.timeout.connect(self.rotate_random_background)
        self._toast_popups: list[FloatingToast] = []
        self.expanded_task_ids: set[str] = set()
        self.task_scope_mode = "all"
        self.task_sort_mode = "priority"
        self._last_task_grid_columns = 0
        self.tasks = self.store.load_tasks()

        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.apply_window_behavior_settings()
        self.apply_icon_settings()
        self.setMinimumSize(_scale_px(MAIN_WINDOW_MINIMUM_WIDTH), _scale_px(MAIN_WINDOW_MINIMUM_HEIGHT))
        self.apply_saved_geometry()

        self.clock_label = ClockDisplay()
        self.today_completion_label = QLabel("0%")
        self.active_count_label = QLabel("0")
        self.soon_count_label = QLabel("0")
        self.overdue_count_label = QLabel("0")
        self.focus_title_label = QLabel("没有进行中的任务")
        self.focus_meta_label = QLabel("等待任务")
        self.focus_deadline_label = QLabel("截止 --:--:--")
        self.focus_countdown_label = QLabel("倒计时 --:--:--")
        self.focus_countdown_label.setObjectName("focusCountdownLabel")
        self.focus_countdown_label.setAlignment(Qt.AlignCenter)
        self.focus_countdown_label.setMinimumWidth(_scale_px(196))
        self.focus_countdown_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.focus_work_timer_label = QLabel("计时 --:--:--")
        self.focus_work_timer_label.setObjectName("focusWorkTimerLabel")
        self.focus_work_timer_label.setAlignment(Qt.AlignCenter)
        self.focus_work_timer_label.setMinimumWidth(_scale_px(188))
        self.focus_work_timer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.focus_priority_label = QLabel("--")
        self.focus_priority_label.setObjectName("focusPriorityLabel")
        self.focus_priority_label.setAlignment(Qt.AlignCenter)
        self.focus_priority_label.setTextFormat(Qt.RichText)
        self.focus_priority_label.setMinimumHeight(_scale_px(40))
        self.focus_urgency_label = QLabel("等待")
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
        self._configure_task_controls()
        self.apply_ui_scale(self.settings.ui_scale, persist=False, refresh=False)
        self.add_button.clicked.connect(self.add_task)
        self.settings_button.clicked.connect(self.open_settings)
        self.history_button.clicked.connect(self.open_history)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.refresh_live_state)
        self._clock_timer.start(1000)
        self.refresh()
        self._geometry_initialized = True

    def _build_ui(self) -> None:
        root = AnimatedBackdrop()
        root.setObjectName("mainRoot")
        root.setStyleSheet(_main_window_style())
        self.root_widget = root
        root_layout = QVBoxLayout(root)
        self.root_layout = root_layout
        root_layout.setContentsMargins(_scale_px(16), _scale_px(14), _scale_px(16), _scale_px(16))
        root_layout.setSpacing(_scale_px(12))
        self.setCentralWidget(root)

        self.title_bar = TitleBar(self)
        root_layout.addWidget(self.title_bar)

        self.summary_widget = QWidget()
        summary_layout = QHBoxLayout(self.summary_widget)
        self.summary_layout = summary_layout
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(_scale_px(8))
        summary_layout.addWidget(self._summary_card("今日完成", self.today_completion_label, "done"))
        summary_layout.addWidget(self._summary_card("进行中", self.active_count_label, "active"))
        summary_layout.addWidget(self._summary_card("临近", self.soon_count_label, "soon"))
        summary_layout.addWidget(self._summary_card("超时", self.overdue_count_label, "overdue"))
        root_layout.addWidget(self.summary_widget)

        self.focus_card = FocusDropCard(self)
        self.focus_card.setObjectName("focusCard")
        self.focus_card.setToolTip("把任务拖到这里设为进行中")
        self.focus_card.setMinimumHeight(_scale_px(FOCUS_CARD_MINIMUM_HEIGHT))
        self.focus_card.setStyleSheet(_card_style("normal", selected=True))
        apply_soft_shadow(self.focus_card, blur=34, y_offset=12, alpha=120)
        focus_layout = QVBoxLayout(self.focus_card)
        self.focus_layout = focus_layout
        focus_layout.setContentsMargins(_scale_px(14), _scale_px(12), _scale_px(14), _scale_px(12))
        focus_layout.setSpacing(_scale_px(10))

        focus_header = QHBoxLayout()
        focus_header.setContentsMargins(0, 0, 0, 0)
        focus_header.setSpacing(_scale_px(8))
        focus_header_accent = QFrame()
        focus_header_accent.setObjectName("focusSectionAccent")
        focus_header_accent.setFixedSize(_scale_px(5), _scale_px(28))
        focus_header.addWidget(focus_header_accent)
        focus_header_label = QLabel("当前任务")
        focus_header_label.setObjectName("focusSectionTitle")
        focus_header.addWidget(focus_header_label)
        focus_header.addStretch(1)
        focus_star = QLabel("")
        focus_star.setObjectName("focusStar")
        focus_star.setAlignment(Qt.AlignCenter)
        focus_star.setFixedSize(_scale_px(34), _scale_px(34))
        _apply_svg_icon(focus_star, "focus-star.svg", _scale_px(18))
        self.focus_star_label = focus_star
        focus_header.addWidget(focus_star)
        focus_layout.addLayout(focus_header)

        focus_top = QGridLayout()
        focus_top.setContentsMargins(0, 0, 0, 0)
        focus_top.setHorizontalSpacing(_scale_px(10))
        focus_top.setVerticalSpacing(_scale_px(8))
        self.focus_top_layout = focus_top
        self.focus_title_prefix = QLabel("进行中")
        self.focus_title_prefix.setAlignment(Qt.AlignCenter)
        self.focus_title_prefix.setMinimumHeight(_scale_px(40))
        self.focus_title_prefix.setStyleSheet(_focus_status_style())
        self.focus_meta_label.setAlignment(Qt.AlignCenter)
        self.focus_meta_label.setMinimumHeight(_scale_px(40))
        self.focus_meta_label.setStyleSheet(_focus_meta_style())
        self.focus_urgency_label.setAlignment(Qt.AlignCenter)
        self.focus_urgency_label.setMinimumHeight(_scale_px(40))
        self.focus_status_strip = QFrame()
        self.focus_status_strip.setObjectName("focusStatusStrip")
        self.focus_status_strip.setStyleSheet(_focus_status_strip_style())
        self.focus_status_strip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.focus_status_layout = QHBoxLayout(self.focus_status_strip)
        self.focus_status_layout.setContentsMargins(_scale_px(8), _scale_px(6), _scale_px(8), _scale_px(6))
        self.focus_status_layout.setSpacing(_scale_px(10))
        for widget in (self.focus_title_prefix, self.focus_priority_label, self.focus_urgency_label, self.focus_meta_label):
            widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            widget.setMinimumWidth(_scale_px(128))
            self.focus_status_layout.addWidget(widget)
        focus_top.addWidget(self.focus_status_strip, 0, 0, 1, 4, Qt.AlignLeft | Qt.AlignVCenter)
        for index in range(4):
            focus_top.setColumnStretch(index, 0)

        deadline_panel = QFrame()
        deadline_panel.setObjectName("focusDeadlinePanel")
        deadline_panel.setStyleSheet(_focus_deadline_panel_style())
        deadline_panel.setMinimumHeight(_scale_px(FOCUS_DEADLINE_PANEL_MINIMUM_HEIGHT))
        deadline_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.focus_deadline_panel = deadline_panel
        deadline_layout = QVBoxLayout(deadline_panel)
        self.deadline_layout = deadline_layout
        deadline_layout.setContentsMargins(_scale_px(16), _scale_px(10), _scale_px(16), _scale_px(12))
        deadline_layout.setSpacing(_scale_px(7))
        self.focus_deadline_card = _focus_info_card("focusDeadlineInfoCard", "record-calendar.svg", self.focus_deadline_label)
        self.focus_deadline_label.setMinimumWidth(_scale_px(336))
        deadline_layout.addWidget(self.focus_deadline_card)
        focus_time_row = QHBoxLayout()
        self.focus_time_row = focus_time_row
        focus_time_row.setContentsMargins(0, 0, 0, 0)
        focus_time_row.setSpacing(_scale_px(12))
        self.focus_countdown_card = _focus_info_card("focusCountdownCard", "task-deadline.svg", self.focus_countdown_label)
        self.focus_work_timer_card = _focus_info_card("focusWorkTimerCard", "record-clock.svg", self.focus_work_timer_label)
        focus_time_row.addWidget(self.focus_countdown_card, 1)
        focus_time_row.addWidget(self.focus_work_timer_card, 1)
        deadline_layout.addLayout(focus_time_row)

        self.focus_title_label.setStyleSheet(_focus_title_style())
        self.focus_title_label.setWordWrap(True)
        self.focus_title_label.setMinimumHeight(_scale_px(46))
        self.focus_title_label.setMaximumHeight(_scale_px(96))
        self.focus_title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.focus_title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        focus_top.addWidget(self.focus_title_label, 1, 0, 1, 4)
        focus_top.addWidget(deadline_panel, 0, 4, 2, 1)
        focus_top.setColumnMinimumWidth(4, _scale_px(436))
        focus_top.setColumnStretch(4, 2)
        focus_layout.addLayout(focus_top)
        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(_scale_px(10))
        focus_progress_caption = QLabel("进度")
        focus_progress_caption.setObjectName("focusProgressCaption")
        focus_progress_caption.setFixedWidth(_scale_px(48))
        progress_row.addWidget(focus_progress_caption)
        self.focus_progress_bar = QProgressBar()
        self.focus_progress_bar.setObjectName("focusProgressDisplay")
        self.focus_progress_bar.setRange(0, 100)
        self.focus_progress_bar.setTextVisible(False)
        self.focus_progress_bar.setFixedHeight(_scale_px(8))
        progress_row.addWidget(self.focus_progress_bar, 1)
        self.focus_progress_value_label = QLabel("")
        self.focus_progress_value_label.setObjectName("focusProgressValue")
        self.focus_progress_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.focus_progress_value_label.setFixedWidth(_scale_px(52))
        self.focus_progress_value_label.setStyleSheet(_progress_value_style(selected=True))
        progress_row.addWidget(self.focus_progress_value_label)
        focus_layout.addLayout(progress_row)
        focus_progress_caption.hide()
        self.focus_progress_bar.hide()
        self.focus_progress_value_label.hide()
        self.focus_notes_label = QLabel()
        self.focus_notes_label.setWordWrap(True)
        self.focus_notes_label.setObjectName("focusNotesLabel")
        self.focus_notes_label.setStyleSheet(_notes_style(selected=True))
        self.focus_notes_label.setMaximumHeight(_scale_px(62))
        self.focus_notes_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        focus_layout.addWidget(self.focus_notes_label)
        focus_actions = QHBoxLayout()
        focus_actions.setSpacing(_scale_px(8))
        self.focus_actions = focus_actions
        self.focus_pause_button = QPushButton("Ⅱ")
        self.focus_pause_button.setObjectName("focusPauseButton")
        self.focus_pause_button.setToolTip("暂停工作计时，截止倒计时仍继续")
        self.focus_pause_button.setAccessibleName("暂停或继续工作计时")
        self.focus_pause_button.setFixedSize(_scale_px(44), _scale_px(36))
        self.focus_pause_button.clicked.connect(self.toggle_focus_pause_task)
        focus_actions.addWidget(self.focus_pause_button, 1)
        self.focus_resume_button = QPushButton()
        self.focus_resume_button.hide()
        self.focus_resume_button.clicked.connect(self.resume_focus_task)
        self.focus_complete_button = QPushButton("完成")
        self.focus_complete_button.setObjectName("focusCompleteButton")
        self.focus_complete_button.setToolTip("完成当前进行中的任务")
        self.focus_complete_button.clicked.connect(self.complete_focus_task)
        focus_actions.addWidget(self.focus_complete_button, 1)
        self.focus_edit_button = QPushButton("编辑")
        self.focus_edit_button.setToolTip("编辑当前进行中的任务")
        self.focus_edit_button.clicked.connect(self.edit_focus_task)
        focus_actions.addWidget(self.focus_edit_button, 1)
        self.focus_delete_button = QPushButton("删除")
        self.focus_delete_button.setObjectName("dangerButton")
        self.focus_delete_button.setToolTip("删除当前进行中的任务")
        self.focus_delete_button.clicked.connect(self.delete_focus_task)
        focus_actions.addWidget(self.focus_delete_button, 1)
        focus_layout.addLayout(focus_actions)
        root_layout.addWidget(self.focus_card)
        self._sync_focus_header_layout()

        self.task_section_widget = QWidget()
        self.task_section_widget.setMinimumHeight(_scale_px(TASK_SECTION_MINIMUM_HEIGHT))
        self.task_section_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        actions_layout = QHBoxLayout(self.task_section_widget)
        self.actions_layout = actions_layout
        actions_layout.setContentsMargins(0, _scale_px(6), 0, _scale_px(6))
        actions_layout.setAlignment(Qt.AlignVCenter)
        task_section_accent = QFrame()
        task_section_accent.setObjectName("taskSectionAccent")
        task_section_accent.setFixedSize(_scale_px(5), _scale_px(26))
        actions_layout.addWidget(task_section_accent)
        section_label = QLabel("任务列表")
        section_label.setObjectName("taskSectionTitle")
        actions_layout.addWidget(section_label)
        actions_layout.addStretch(1)
        self.task_scope_button = QPushButton("全部 v")
        self.task_scope_button.setObjectName("taskFilterButton")
        self.task_scope_button.setProperty("effectVariant", "utility")
        self.task_scope_button.setToolTip("显示全部任务")
        actions_layout.addWidget(self.task_scope_button)
        self.task_sort_button = QPushButton("按优先级 v")
        self.task_sort_button.setObjectName("taskFilterButton")
        self.task_sort_button.setProperty("effectVariant", "utility")
        self.task_sort_button.setToolTip("当前按优先级和时间排序")
        actions_layout.addWidget(self.task_sort_button)
        self.task_grid_button = QPushButton("卡片")
        self.task_grid_button.setObjectName("taskViewButton")
        self.task_grid_button.setToolTip("矩形卡片视图")
        actions_layout.addWidget(self.task_grid_button)
        self.history_button.setToolTip("查看历史任务与完成体会")
        self.history_button.setProperty("effectVariant", "utility")
        actions_layout.addWidget(self.history_button)
        self.add_button.setToolTip("新增任务")
        self.add_button.setProperty("effectVariant", "primary")
        actions_layout.addWidget(self.add_button)
        root_layout.addWidget(self.task_section_widget)

        self.empty_state_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_state_widget)
        self.empty_layout = empty_layout
        empty_layout.setContentsMargins(0, _scale_px(12), 0, _scale_px(12))
        empty_layout.setSpacing(_scale_px(4))
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setAlignment(Qt.AlignCenter)
        self.empty_state_hint_label.setStyleSheet(f"color: {THEME_COLORS['border']};")
        empty_layout.addWidget(self.empty_state_label)
        empty_layout.addWidget(self.empty_state_hint_label)
        root_layout.addWidget(self.empty_state_widget)

        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setHorizontalSpacing(_scale_px(10))
        self.task_list_layout.setVerticalSpacing(_scale_px(10))
        self.task_list_layout.setAlignment(Qt.AlignTop)
        self.task_scroll_area = QScrollArea()
        self.task_scroll_area.setWidgetResizable(True)
        self.task_scroll_area.setFrameShape(QFrame.NoFrame)
        self.task_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.task_scroll_area.verticalScrollBar().setSingleStep(_scale_px(32))
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

    def _summary_card(self, caption: str, value_label: QLabel, tone: str = "active") -> QFrame:
        card = QFrame()
        card.setObjectName(f"summaryCard-{tone}")
        card.setStyleSheet(_summary_card_style(tone))
        apply_soft_shadow(card, blur=_scale_px(24), y_offset=_scale_px(8), alpha=85)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(_scale_px(14), _scale_px(12), _scale_px(14), _scale_px(12))
        layout.setSpacing(_scale_px(12))
        icon = QLabel("")
        icon.setObjectName("summaryIcon")
        icon.setProperty("summaryTone", tone)
        icon.setProperty("iconName", _summary_icon_name(tone))
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(_scale_px(34), _scale_px(34))
        icon.setStyleSheet(_summary_icon_style(tone))
        _apply_svg_icon(icon, _summary_icon_name(tone), _scale_px(18))
        layout.addWidget(icon)
        text_stack = QVBoxLayout()
        text_stack.setContentsMargins(0, 0, 0, 0)
        text_stack.setSpacing(_scale_px(3))
        caption_label = QLabel(caption)
        caption_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        caption_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        caption_label.setStyleSheet(f"color: #AFC3D8; font-size: {_scale_px(12)}px; font-weight: 800;")
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        value_label.setStyleSheet(f"font-size: {_scale_px(24)}px; font-weight: 900; color: #F8FBFF;")
        footer_label = QLabel(_summary_footer(tone))
        footer_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        footer_label.setStyleSheet(f"color: #8EA2B7; font-size: {_scale_px(11)}px; font-weight: 800;")
        text_stack.addWidget(caption_label)
        text_stack.addWidget(value_label)
        text_stack.addWidget(footer_label)
        layout.addLayout(text_stack, 1)
        return card

    def _configure_task_controls(self) -> None:
        scope_menu = QMenu(self.task_scope_button)
        for mode in ("all", "active", "paused", "soon", "overdue"):
            action = scope_menu.addAction(TASK_SCOPE_LABELS[mode])
            action.triggered.connect(lambda checked=False, scope=mode: self._set_task_scope_mode(scope))
        self.task_scope_button.setMenu(scope_menu)

        sort_menu = QMenu(self.task_sort_button)
        for mode in ("priority", "deadline", "created"):
            action = sort_menu.addAction(TASK_SORT_LABELS[mode])
            action.triggered.connect(lambda checked=False, sort_mode=mode: self._set_task_sort_mode(sort_mode))
        self.task_sort_button.setMenu(sort_menu)

        self.task_grid_button.hide()
        self.task_grid_button.setEnabled(False)
        self.task_grid_button.deleteLater()
        del self.task_grid_button
        self._update_task_control_labels()

    def _set_task_scope_mode(self, mode: str) -> None:
        if mode == self.task_scope_mode:
            return
        self.task_scope_mode = mode
        self.refresh_data_view()

    def _set_task_sort_mode(self, mode: str) -> None:
        if mode == self.task_sort_mode:
            return
        self.task_sort_mode = mode
        self.refresh_data_view()

    def _update_task_control_labels(self) -> None:
        scope_text = TASK_SCOPE_LABELS.get(self.task_scope_mode, TASK_SCOPE_LABELS["all"])
        sort_text = TASK_SORT_LABELS.get(self.task_sort_mode, TASK_SORT_LABELS["priority"])
        self.task_scope_button.setText(f"{scope_text} v")
        self.task_scope_button.setToolTip(f"当前筛选：{scope_text}")
        self.task_sort_button.setText(f"{sort_text} v")
        self.task_sort_button.setToolTip(f"当前排序：{sort_text}")

    def _task_rows_for_view(self, now: datetime) -> list[dict[str, object]]:
        rows = list(task_rows(self.tasks, now))
        tasks_by_id = {task.id: task for task in self.tasks}
        if self.task_scope_mode == "active":
            rows = [row for row in rows if not bool(row.get("is_paused"))]
        elif self.task_scope_mode == "paused":
            rows = [row for row in rows if bool(row.get("is_paused"))]
        elif self.task_scope_mode == "soon":
            rows = [
                row
                for row in rows
                if not bool(row.get("is_paused")) and str(row.get("urgency")) in {"soon", "urgent", "critical"}
            ]
        elif self.task_scope_mode == "overdue":
            rows = [row for row in rows if str(row.get("urgency")) == "overdue"]

        if self.task_sort_mode == "deadline":
            rows.sort(
                key=lambda row: (
                    tasks_by_id[str(row["id"])].deadline is None,
                    tasks_by_id[str(row["id"])].deadline or datetime.max.replace(tzinfo=timezone.utc),
                    str(row.get("priority") or ""),
                )
            )
        elif self.task_sort_mode == "created":
            rows.sort(
                key=lambda row: (
                    tasks_by_id[str(row["id"])].created_at,
                    row.get("title") or "",
                ),
                reverse=True,
            )
        return rows

    def update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%H:%M:%S"))

    def _reactivate_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

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
        if not any(task.id == task_id and task.status in {"active", "paused"} for task in self.tasks):
            return
        self.settings = replace(self.settings, focus_task_id=task_id)
        self._save_settings()
        self.refresh_data_view()
        animate_value_tick(self.focus_title_label, duration=190)
        animate_content_swap(self.task_rows_container, duration=150)
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

    def update_task_progress(self, task_id: str, value: int) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        updated = replace(self.tasks[index], progress=max(0, min(100, int(value))), updated_at=datetime.now(timezone.utc))
        self.tasks = [*self.tasks[:index], updated, *self.tasks[index + 1 :]]
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()

    def add_task(self) -> None:
        dialog = TaskDialog(self)
        prepare_window_entrance(dialog)
        accepted = dialog.exec() == QDialog.Accepted
        self._reactivate_window()
        if not accepted:
            return
        task = dialog.build_task()
        if not task.title.strip():
            return
        self.tasks = [*self.tasks, task]
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()

    def edit_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        dialog = TaskDialog(self, self.tasks[index])
        prepare_window_entrance(dialog)
        accepted = dialog.exec() == QDialog.Accepted
        self._reactivate_window()
        if not accepted:
            return
        updated = dialog.build_task()
        if not updated.title.strip():
            return
        self.tasks = [*self.tasks[:index], updated, *self.tasks[index + 1 :]]
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()

    def pause_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None or self.tasks[index].status != "active":
            return
        now = datetime.now(timezone.utc)
        paused = pause_work_timer(self.tasks[index], now)
        self.tasks = [*self.tasks[:index], paused, *self.tasks[index + 1 :]]
        self.settings = replace(self.settings, focus_task_id=task_id)
        self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()
        self.show_toast("工作计时已暂停", f"{paused.title}\n截止倒计时仍会继续，提醒也会按截止时间触发。", kind="info", duration_ms=4200)

    def resume_task(self, task_id: str, *, make_focus: bool = False) -> None:
        index = self._task_index(task_id)
        if index is None or self.tasks[index].status != "paused":
            return
        now = datetime.now(timezone.utc)
        resumed = resume_work_timer(self.tasks[index], now)
        self.tasks = [*self.tasks[:index], resumed, *self.tasks[index + 1 :]]
        if make_focus:
            self.settings = replace(self.settings, focus_task_id=task_id)
            self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()
        self.show_toast("工作计时已继续", f"{resumed.title}\n已恢复工作计时，并设为进行中任务。", kind="success", duration_ms=3800)
        if make_focus:
            self._pulse_widget(self.focus_card)

    def complete_task(self, task_id: str) -> None:
        index = self._task_index(task_id)
        if index is None:
            return
        if not self.confirm_complete_task(self.tasks[index]):
            return
        now = datetime.now(timezone.utc)
        frozen = freeze_work_timer(self.tasks[index], now)
        completed = replace(frozen, status="done", progress=100, completed_at=now, updated_at=now)
        self.tasks = [*self.tasks[:index], completed, *self.tasks[index + 1 :]]
        if self.settings.focus_task_id == task_id:
            self.settings = replace(self.settings, focus_task_id=None)
            self._save_settings()
        self.store.save_tasks(self.tasks)
        self.refresh_data_view()
        self.show_completion_encouragement(completed)

    def confirm_complete_task(self, task: Task) -> bool:
        dialog = CompletionDialog(task, self)
        prepare_window_entrance(dialog)
        accepted = dialog.exec() == QDialog.Accepted
        self._reactivate_window()
        return accepted

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
        self.refresh_data_view()

    def confirm_delete_task(self, task: Task) -> bool:
        dialog = DeleteTaskDialog(task, self)
        prepare_window_entrance(dialog)
        accepted = dialog.exec() == QDialog.Accepted
        self._reactivate_window()
        return accepted

    def open_history(self) -> None:
        dialog = HistoryWindow(self.tasks, self.store, self)
        prepare_window_entrance(dialog)
        dialog.exec()
        self._reactivate_window()
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
        image_path = self._select_background_image_path(self.settings, rotate=True)
        self.root_widget.set_background_settings(
            self.settings.background_enabled,
            image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )
        self._sync_background_random_timer()

    def preview_settings(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self._apply_icon_for_settings(settings)
        image_path = self._select_background_image_path(settings, rotate=True)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )

    def restore_settings_preview(self, settings: AppSettings) -> None:
        self.setWindowOpacity(settings.opacity)
        self._apply_icon_for_settings(settings)
        image_path = self._select_background_image_path(settings, rotate=True)
        self.root_widget.set_background_settings(
            settings.background_enabled,
            image_path,
            DEFAULT_BACKGROUND_OVERLAY,
        )
        self._sync_background_random_timer()

    def _select_background_image_path(self, settings: AppSettings, *, rotate: bool = False) -> str:
        if not settings.background_enabled:
            return settings.background_image_path
        if not settings.background_random_enabled or not settings.background_folder_path:
            return settings.background_image_path
        folder = str(settings.background_folder_path)
        candidates = background_image_candidates(folder)
        if not candidates:
            return settings.background_image_path
        if folder != self._current_random_background_folder:
            self._current_random_background_folder = folder
            self._current_random_background_path = ""
        if not rotate and self._current_random_background_path:
            return self._current_random_background_path
        pool = [path for path in candidates if str(path) != self._current_random_background_path] or candidates
        selected = random.choice(pool)
        self._current_random_background_path = str(selected)
        return self._current_random_background_path

    def _sync_background_random_timer(self) -> None:
        should_run = bool(
            self.settings.background_enabled
            and self.settings.background_random_enabled
            and len(background_image_candidates(self.settings.background_folder_path)) > 1
        )
        if should_run:
            if not self._background_random_timer.isActive():
                self._background_random_timer.start(BACKGROUND_RANDOM_INTERVAL_MS)
        else:
            self._background_random_timer.stop()

    def rotate_random_background(self) -> None:
        if not (
            self.settings.background_enabled
            and self.settings.background_random_enabled
            and self.settings.background_folder_path
        ):
            self._background_random_timer.stop()
            return
        image_path = self._select_background_image_path(self.settings, rotate=True)
        self.root_widget.set_background_settings(True, image_path, DEFAULT_BACKGROUND_OVERLAY)

    def _materialize_settings_resources(self, settings: AppSettings) -> AppSettings:
        if self.settings_path is None:
            return settings
        data_dir = self.settings_path.parent
        return replace(
            settings,
            background_image_path=materialize_custom_resource(settings.background_image_path, data_dir, "background"),
            icon_path=materialize_custom_resource(settings.icon_path, data_dir, "icon"),
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

    def apply_ui_scale(
        self,
        scale: float,
        *,
        persist: bool = True,
        refresh: bool = True,
    ) -> None:
        scale = _clamp_ui_scale(scale)
        _set_current_ui_scale(scale)
        if self.settings.ui_scale != scale:
            self.settings = replace(self.settings, ui_scale=scale)
            if persist:
                self._save_settings()
        self.setMinimumSize(_scale_px(MAIN_WINDOW_MINIMUM_WIDTH), _scale_px(MAIN_WINDOW_MINIMUM_HEIGHT))
        if self.width() < self.minimumWidth() or self.height() < self.minimumHeight():
            self.resize(max(self.width(), self.minimumWidth()), max(self.height(), self.minimumHeight()))

        if hasattr(self, "root_layout"):
            self.root_layout.setContentsMargins(_scale_px(16), _scale_px(14), _scale_px(16), _scale_px(16))
            self.root_layout.setSpacing(_scale_px(12))
            self.root_widget.setStyleSheet(_main_window_style())
        if hasattr(self, "title_bar"):
            self.title_bar.apply_scale()
        if hasattr(self, "summary_layout"):
            self.summary_layout.setSpacing(_scale_px(8))
            for label in self.summary_widget.findChildren(QLabel):
                if label.objectName() == "summaryIcon":
                    icon_name = str(label.property("iconName") or _summary_icon_name(str(label.property("summaryTone") or "active")))
                    label.setFixedSize(_scale_px(34), _scale_px(34))
                    label.setStyleSheet(_summary_icon_style(str(label.property("summaryTone") or "active")))
                    _apply_svg_icon(label, icon_name, _scale_px(18))
                    continue
                if label in (
                    self.today_completion_label,
                    self.active_count_label,
                    self.soon_count_label,
                    self.overdue_count_label,
                ):
                    label.setStyleSheet(f"font-size: {_scale_px(21)}px; font-weight: 900; color: #F8FBFF;")
                else:
                    label.setStyleSheet(f"color: #AFC3D8; font-size: {_scale_px(12)}px; font-weight: 800;")
        if hasattr(self, "focus_card"):
            self.focus_card.setMinimumHeight(_scale_px(FOCUS_CARD_MINIMUM_HEIGHT))
        if hasattr(self, "focus_layout"):
            self.focus_layout.setContentsMargins(_scale_px(14), _scale_px(12), _scale_px(14), _scale_px(12))
            self.focus_layout.setSpacing(_scale_px(10))
        if hasattr(self, "focus_top_layout"):
            self.focus_top_layout.setHorizontalSpacing(_scale_px(12))
            self.focus_top_layout.setVerticalSpacing(_scale_px(10))
            self.focus_status_strip.setStyleSheet(_focus_status_strip_style())
            self.focus_status_layout.setContentsMargins(_scale_px(8), _scale_px(6), _scale_px(8), _scale_px(6))
            self.focus_status_layout.setSpacing(_scale_px(10))
            self.focus_title_prefix.setMinimumHeight(_scale_px(40))
            self.focus_priority_label.setMinimumHeight(_scale_px(40))
            self.focus_urgency_label.setMinimumHeight(_scale_px(40))
            self.focus_meta_label.setMinimumHeight(_scale_px(40))
            for widget in (self.focus_title_prefix, self.focus_priority_label, self.focus_urgency_label, self.focus_meta_label):
                widget.setMinimumWidth(_scale_px(128))
            self.focus_top_layout.setColumnMinimumWidth(4, _scale_px(436))
        if hasattr(self, "focus_deadline_panel"):
            self.focus_deadline_panel.setMinimumHeight(_scale_px(FOCUS_DEADLINE_PANEL_MINIMUM_HEIGHT))
            self.focus_deadline_label.setMinimumWidth(_scale_px(336))
            self.focus_countdown_label.setMinimumWidth(_scale_px(196))
            self.focus_work_timer_label.setMinimumWidth(_scale_px(188))
            self.focus_deadline_label.setStyleSheet(_focus_deadline_text_style("none"))
            self.focus_countdown_label.setStyleSheet(_focus_time_text_style("countdown", "none"))
            self.focus_work_timer_label.setStyleSheet(_focus_time_text_style("timer", "none"))
        if hasattr(self, "focus_progress_bar"):
            self.focus_progress_bar.setFixedHeight(_scale_px(8))
            self.focus_progress_value_label.setFixedWidth(_scale_px(52))
            self.focus_progress_value_label.setStyleSheet(_progress_value_style(selected=True))
        if hasattr(self, "deadline_layout"):
            self.deadline_layout.setContentsMargins(_scale_px(16), _scale_px(10), _scale_px(16), _scale_px(12))
            self.deadline_layout.setSpacing(_scale_px(7))
        for attr in ("focus_deadline_card", "focus_countdown_card", "focus_work_timer_card"):
            card = getattr(self, attr, None)
            if card is None:
                continue
            card.setMinimumHeight(_scale_px(52))
            layout = card.layout()
            if isinstance(layout, QHBoxLayout):
                layout.setContentsMargins(_scale_px(14), _scale_px(11), _scale_px(16), _scale_px(11))
                layout.setSpacing(_scale_px(10))
        if hasattr(self, "focus_deadline_panel"):
            for icon in self.focus_deadline_panel.findChildren(QLabel, "focusInfoIcon"):
                icon_name = str(icon.property("iconName") or "")
                icon.setFixedSize(_scale_px(28), _scale_px(28))
                if icon_name:
                    _apply_svg_icon(icon, icon_name, _scale_px(15))
        if hasattr(self, "focus_time_row"):
            self.focus_time_row.setSpacing(_scale_px(12))
        if hasattr(self, "focus_title_label"):
            self.focus_title_label.setMinimumHeight(_scale_px(46))
            self.focus_title_label.setMaximumHeight(_scale_px(96))
            self.focus_title_label.setStyleSheet(_focus_title_style())
        if hasattr(self, "focus_notes_label"):
            self.focus_notes_label.setMaximumHeight(_scale_px(62))
        if hasattr(self, "focus_actions"):
            self.focus_actions.setSpacing(_scale_px(8))
        if hasattr(self, "task_section_widget"):
            self.task_section_widget.setMinimumHeight(_scale_px(TASK_SECTION_MINIMUM_HEIGHT))
        if hasattr(self, "actions_layout"):
            self.actions_layout.setContentsMargins(0, _scale_px(6), 0, _scale_px(6))
        if hasattr(self, "empty_layout"):
            self.empty_layout.setContentsMargins(0, _scale_px(12), 0, _scale_px(12))
            self.empty_layout.setSpacing(_scale_px(4))
        if hasattr(self, "task_list_layout"):
            self.task_list_layout.setHorizontalSpacing(_scale_px(10))
            self.task_list_layout.setVerticalSpacing(_scale_px(10))
        if hasattr(self, "task_scroll_area"):
            self.task_scroll_area.verticalScrollBar().setSingleStep(_scale_px(32))
        if hasattr(self, "resize_grip"):
            self.resize_grip.apply_scale()
        focus_star = getattr(self, "focus_star_label", None)
        if focus_star is not None:
            focus_star.setFixedSize(_scale_px(34), _scale_px(34))
            _apply_svg_icon(focus_star, "focus-star.svg", _scale_px(18))
        if refresh:
            self.refresh()
            self.updateGeometry()

    def open_settings(self) -> None:
        previous_settings = self.settings
        previous_geometry = self.geometry()
        dialog = SettingsWindow(self.settings, self)
        prepare_window_entrance(dialog)
        accepted = dialog.exec() == QDialog.Accepted
        self._reactivate_window()
        if not accepted:
            self.restore_settings_preview(previous_settings)
            self.apply_ui_scale(previous_settings.ui_scale, persist=False, refresh=True)
            self.apply_low_distraction_settings()
            self._sync_focus_header_layout()
            return
        updated_settings = remove_deprecated_setting_features(dialog.build_settings())
        updated_settings = self._materialize_settings_resources(updated_settings)
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
            self.apply_ui_scale(self.settings.ui_scale, persist=False, refresh=True)
            self.apply_low_distraction_settings()
            if self.settings.lock_position:
                self.apply_saved_geometry()
            else:
                self.setGeometry(previous_geometry)
            self.show()
            self.centralWidget().layout().activate()
            self._sync_focus_header_layout()
            self.refresh()
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
        columns = self._task_grid_columns()
        if columns != self._last_task_grid_columns:
            self.refresh_data_view()

    def _sync_focus_header_layout(self) -> None:
        layout = getattr(self, "focus_top_layout", None)
        status_strip = getattr(self, "focus_status_strip", None)
        deadline_panel = getattr(self, "focus_deadline_panel", None)
        title_label = getattr(self, "focus_title_label", None)
        if layout is None or deadline_panel is None or title_label is None:
            return
        if status_strip is not None:
            layout.removeWidget(status_strip)
            layout.addWidget(status_strip, 0, 0, 1, 4, Qt.AlignLeft | Qt.AlignVCenter)
        layout.removeWidget(deadline_panel)
        layout.removeWidget(title_label)
        layout.addWidget(title_label, 1, 0, 1, 4)
        layout.addWidget(deadline_panel, 2, 0, 1, 4)
        layout.setColumnMinimumWidth(4, 0)
        layout.setColumnStretch(4, 0)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.focus_deadline_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.focus_countdown_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.focus_work_timer_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

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

    def show_toast(
        self,
        title: str,
        message: str,
        *,
        kind: str = "info",
        duration_ms: int = 7000,
        use_background: bool = False,
    ) -> FloatingToast:
        popup = FloatingToast(
            title,
            message,
            kind=kind,
            background_enabled=use_background and self.settings.background_enabled,
            background_image_path=self.root_widget.background_image_path if use_background else "",
            background_overlay=self.settings.background_overlay,
        )
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
        self.show_toast(title, message, kind=kind, duration_ms=7200, use_background=True)

    def refresh(self) -> None:
        self.refresh_data_view(reload=True)

    def refresh_data_view(self, *, reload: bool = False) -> None:
        self.update_clock()
        if self._task_drag_active:
            self._task_drag_refresh_pending = True
            return
        if reload:
            self.tasks = self.store.load_tasks()
        now = datetime.now(timezone.utc)
        self.process_reminders(now)
        rows = self._task_rows_for_view(now)
        self._update_task_control_labels()
        focus_task = self._render_summary_and_focus(now, rows)
        self._render_task_rows(rows, focus_task.id if focus_task else None)
        self.apply_low_distraction_settings()

    def refresh_live_state(self) -> None:
        self.update_clock()
        if self._task_drag_active:
            return
        now = datetime.now(timezone.utc)
        self.process_reminders(now)
        rows = self._task_rows_for_view(now)
        focus_task = self._render_summary_and_focus(now, rows)
        self._sync_task_row_live_labels(rows, focus_task.id if focus_task else None)
        self.apply_low_distraction_settings()

    def _render_summary_and_focus(self, now: datetime, rows: list[dict[str, object]]) -> Task | None:
        all_rows = task_rows(self.tasks, now)
        active_count = sum(1 for task in self.tasks if task.status == "active")
        paused_count = sum(1 for task in self.tasks if task.status == "paused")
        soon_count = sum(1 for row in all_rows if str(row.get("urgency")) in {"soon", "urgent", "critical"})
        overdue_count = sum(1 for row in all_rows if str(row.get("urgency")) == "overdue")
        self.active_count_label.setText(str(active_count))
        self.soon_count_label.setText(str(soon_count))
        self.overdue_count_label.setText(str(overdue_count))
        self.today_completion_label.setText(f"{today_completion_percent(self.tasks)}%")

        focus_task = self.focus_task()
        if focus_task is None:
            self.focus_title_label.setText("没有进行中的任务")
            self.focus_title_label.setToolTip("")
            self.focus_title_prefix.setText("进行中")
            self.focus_meta_label.setText("等待任务")
            self.focus_meta_label.show()
            self.focus_notes_label.clear()
            self.focus_notes_label.hide()
            self.focus_deadline_label.setText("截止 --:--:--")
            self.focus_deadline_card.setStyleSheet(_focus_info_card_style("deadline", "none"))
            self.focus_deadline_label.setStyleSheet(_focus_deadline_text_style("none"))
            self.focus_countdown_label.setText("倒计时 --:--:--")
            self.focus_countdown_card.setStyleSheet(_focus_info_card_style("countdown", "none"))
            self.focus_countdown_label.setStyleSheet(_focus_time_text_style("countdown", "none"))
            self.focus_work_timer_label.setText("计时 --:--:--")
            self.focus_work_timer_card.setStyleSheet(_focus_info_card_style("timer", "none", paused=False))
            self.focus_work_timer_label.setStyleSheet(_focus_time_text_style("timer", "none"))
            self.focus_progress_bar.setValue(0)
            self.focus_progress_value_label.clear()
            self.focus_priority_label.setText("--")
            self.focus_priority_label.setStyleSheet(_priority_chip_style("none"))
            self.focus_urgency_label.setText("等待")
            self.focus_urgency_label.setStyleSheet(_urgency_chip_style("none"))
            self.focus_card.setStyleSheet(_card_style("normal", selected=True))
            self._set_focus_action_state(None)
            self.empty_state_hint_label.setText("可继续暂停任务，或点击新增任务" if paused_count else "点击新增任务开始")
            self.empty_state_widget.show()
            return None

        is_paused_focus = focus_task.status == "paused"
        urgency, urgency_label = deadline_urgency(focus_task.deadline, now)
        if is_paused_focus:
            urgency_label = f"已暂停 · {urgency_label}"
        self.focus_title_label.setText(_task_name_display(focus_task.title))
        self.focus_title_label.setToolTip(focus_task.title)
        self.focus_title_prefix.setText("已暂停" if is_paused_focus else "进行中")
        self.focus_meta_label.setText("暂停中" if is_paused_focus else "计时中")
        self.focus_meta_label.setVisible(is_paused_focus)
        self._set_focus_notes(focus_task.notes)
        self.focus_priority_label.setText(_priority_inline_markup(focus_task.priority, size=_scale_px(13)))
        self.focus_priority_label.setStyleSheet(_priority_chip_style(focus_task.priority))
        self.focus_deadline_label.setText(f"截止 {deadline_at_label(focus_task.deadline)}")
        self.focus_deadline_card.setStyleSheet(_focus_info_card_style("deadline", urgency))
        self.focus_deadline_label.setStyleSheet(_focus_deadline_text_style(urgency))
        countdown_pulse = False
        raw_countdown_text = countdown_label(focus_task.deadline, now)
        countdown_text = _countdown_display(_focus_countdown_text(raw_countdown_text), countdown_pulse)
        if self.focus_countdown_label.text() != countdown_text:
            self.focus_countdown_label.setText(countdown_text)
        self.focus_countdown_card.setStyleSheet(_focus_info_card_style("countdown", urgency, pulse=countdown_pulse))
        self.focus_countdown_label.setStyleSheet(_focus_time_text_style("countdown", urgency))
        work_timer_text = f"计时 {_elapsed_work_timer_text(work_timer_label(focus_task, now))}"
        if self.focus_work_timer_label.text() != work_timer_text:
            self.focus_work_timer_label.setText(work_timer_text)
            if self.isVisible():
                animate_value_tick(self.focus_work_timer_label, duration=170)
        self.focus_work_timer_card.setStyleSheet(_focus_info_card_style("timer", urgency, paused=is_paused_focus))
        self.focus_work_timer_label.setStyleSheet(_focus_time_text_style("timer", urgency))
        self.focus_progress_bar.setValue(focus_task.progress)
        self.focus_progress_value_label.clear()
        self.focus_urgency_label.setText(urgency_label)
        self.focus_urgency_label.setStyleSheet(_urgency_chip_style(urgency))
        self.focus_card.setStyleSheet(_card_style(urgency, selected=True))
        self._set_focus_action_state(focus_task.status)
        self.empty_state_widget.hide()
        return focus_task

    def _render_task_rows(self, rows: list[dict[str, object]], focus_task_id: str | None = None) -> None:
        active_ids = {str(row["id"]) for row in rows}
        self.expanded_task_ids.intersection_update(active_ids)
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        columns = self._task_grid_columns()
        self._last_task_grid_columns = columns
        for column in range(5):
            self.task_list_layout.setColumnStretch(column, 1 if column < columns else 0)
        for index, row in enumerate(rows):
            self.task_list_layout.addWidget(self._task_row(row, focus_task_id), index // columns, index % columns)
        if rows:
            add_index = len(rows)
            self.task_list_layout.addWidget(self._add_task_tile(), add_index // columns, add_index % columns)

    def _sync_task_row_live_labels(self, rows: list[dict[str, object]], focus_task_id: str | None) -> None:
        displayed_cards = self.task_rows_container.findChildren(TaskRowCard)
        displayed_ids = [card.task_id for card in displayed_cards]
        row_ids = [str(row["id"]) for row in rows]
        if displayed_ids != row_ids:
            self._render_task_rows(rows, focus_task_id)
            return

        for row in rows:
            task_id = str(row["id"])
            urgency = str(row["urgency"])
            is_paused = bool(row.get("is_paused"))
            is_focused = task_id == focus_task_id
            card = self.task_rows_container.findChild(TaskRowCard, f"taskRow-{task_id}")
            if card is None:
                self._render_task_rows(rows, focus_task_id)
                return

            card.setStyleSheet(_card_style(urgency, selected=is_focused))
            urgency_chip = card.findChild(QLabel, "activeTaskUrgency" if is_focused else "taskUrgency")
            if urgency_chip is not None:
                urgency_chip.setText(str(row["urgency_label"]))
                urgency_chip.setStyleSheet(_urgency_chip_style(urgency))

            deadline = card.findChild(QLabel, "activeTaskDeadline" if is_focused else "taskDeadline")
            if deadline is not None:
                deadline.setText(f"截止 {row['deadline_at_label']} · {row['deadline_label']}")
                deadline.setStyleSheet(_deadline_label_style(urgency))

            work_timer = card.findChild(QLabel, "activeTaskTimer" if is_focused else "taskTimer")
            if work_timer is not None:
                work_timer.setText(f"计时 {_elapsed_work_timer_text(str(row['work_timer_label']))}")
                work_timer.setStyleSheet(_task_timer_style(urgency, selected=is_focused, paused=is_paused))

    def _task_grid_columns(self) -> int:
        width = self.task_scroll_area.viewport().width() if hasattr(self, "task_scroll_area") else self.width()
        if width >= 900:
            return 4
        if width >= 680:
            return 3
        if width >= 460:
            return 2
        return 1

    def _add_task_tile(self) -> QPushButton:
        tile = QPushButton("+\n新增任务")
        tile.setObjectName("addTaskTile")
        tile.setToolTip("新增任务")
        tile.setCursor(Qt.PointingHandCursor)
        tile.setMinimumHeight(_scale_px(214))
        tile.setMinimumWidth(_scale_px(190))
        tile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tile.setStyleSheet(_add_task_tile_style())
        tile.clicked.connect(self.add_task)
        return tile

    def toggle_task_details(self, task_id: str) -> None:
        if task_id in self.expanded_task_ids:
            self.expanded_task_ids.remove(task_id)
        else:
            self.expanded_task_ids.add(task_id)
        self.refresh_data_view()
        animate_content_swap(self.task_rows_container, duration=150)

    def _task_row(self, row: dict[str, object], focus_task_id: str | None = None) -> QFrame:
        task_id = str(row["id"])
        urgency = str(row["urgency"])
        is_paused = bool(row.get("is_paused"))
        is_focused = task_id == focus_task_id
        is_expanded = task_id in self.expanded_task_ids
        card = TaskRowCard(task_id, self)
        card.setObjectName(f"taskRow-{task_id}")
        card.setStyleSheet(_card_style(urgency, selected=is_focused))
        card.setMinimumHeight(_scale_px(244 if is_expanded else 214))
        card.setMinimumWidth(_scale_px(190))
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_soft_shadow(card, blur=32 if is_focused else 22, y_offset=9, alpha=130 if is_focused else 80)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(_scale_px(10), _scale_px(8), _scale_px(10), _scale_px(9))
        layout.setSpacing(_scale_px(6))

        top = QHBoxLayout()
        priority = QLabel(_priority_inline_markup(str(row["priority"]), size=_scale_px(11)))
        priority.setAlignment(Qt.AlignCenter)
        priority.setTextFormat(Qt.RichText)
        priority.setFixedHeight(_scale_px(30))
        priority.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        priority.setStyleSheet(_priority_chip_style(str(row["priority"])))
        top.addWidget(priority)
        tag_name = str(row.get("tag", "未分类"))
        tag_chip = QLabel(f"#{tag_name if len(tag_name) <= 6 else tag_name[:6] + '...'}")
        tag_chip.setObjectName("activeTaskTag" if is_focused else "taskTag")
        tag_chip.setAlignment(Qt.AlignCenter)
        tag_chip.setFixedHeight(_scale_px(30))
        tag_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        tag_chip.setStyleSheet(_task_tag_chip_style(selected=is_focused))
        tag_chip.setToolTip(f"任务标签：{tag_name}")
        top.addWidget(tag_chip)
        urgency_chip = QLabel(str(row["urgency_label"]))
        urgency_chip.setObjectName("activeTaskUrgency" if is_focused else "taskUrgency")
        urgency_chip.setAlignment(Qt.AlignCenter)
        urgency_chip.setFixedHeight(_scale_px(30))
        urgency_chip.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        urgency_chip.setStyleSheet(_urgency_chip_style(urgency))
        top.addWidget(urgency_chip)
        top.addStretch(1)
        layout.addLayout(top)

        title = QLabel(_task_name_display(str(row["title"])))
        title.setObjectName("activeTaskTitle" if is_focused else "taskTitle")
        title.setToolTip(str(row["title"]))
        title.setWordWrap(True)
        title.setMinimumHeight(_scale_px(38))
        title.setMaximumHeight(_scale_px(44))
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title.setStyleSheet(_task_title_style(selected=is_focused))
        layout.addWidget(title)

        deadline = QLabel(f"截止 {row['deadline_at_label']} · {row['deadline_label']}")
        deadline.setObjectName("activeTaskDeadline" if is_focused else "taskDeadline")
        deadline.setWordWrap(True)
        deadline.setMinimumHeight(_scale_px(28))
        deadline.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        deadline.setStyleSheet(_deadline_label_style(urgency))
        layout.addWidget(deadline)

        work_timer = QLabel(f"计时 {_elapsed_work_timer_text(str(row['work_timer_label']))}")
        work_timer.setObjectName("activeTaskTimer" if is_focused else "taskTimer")
        work_timer.setAlignment(Qt.AlignCenter)
        work_timer.setMinimumHeight(_scale_px(28))
        work_timer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        work_timer.setStyleSheet(_task_timer_style(urgency, selected=is_focused, paused=is_paused))
        layout.addWidget(work_timer)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(_scale_px(7))
        progress_bar = QProgressBar()
        progress_bar.setObjectName("activeTaskProgressDisplay" if is_focused else "taskProgressDisplay")
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(row.get("progress", 0)))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(_scale_px(7))
        progress_bar.setStyleSheet(_task_progress_style(selected=is_focused))
        progress_row.addWidget(progress_bar, 1)
        progress_value = QLabel("")
        progress_value.setObjectName("activeTaskProgressValue" if is_focused else "taskProgressValue")
        progress_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_value.setFixedWidth(_scale_px(40))
        progress_value.setStyleSheet(_progress_value_style(selected=is_focused))
        progress_row.addWidget(progress_value)
        layout.addLayout(progress_row)
        progress_bar.hide()
        progress_value.hide()

        compact_row = QHBoxLayout()
        compact_row.setSpacing(_scale_px(6))
        compact_row.addStretch(1)
        focus_button = QPushButton("当前" if is_focused else "置顶")
        focus_button.setToolTip("设为当前置顶任务；之后点击其它任务的置顶即可替换")
        if is_focused:
            focus_button.setObjectName("currentTaskButton")
        focus_button.clicked.connect(lambda checked=False, task_id=task_id: self.set_focus_task(task_id))
        compact_row.addWidget(focus_button)
        if is_paused:
            resume_button = QPushButton()
            self._configure_pause_resume_button(resume_button, paused=True)
            resume_button.setToolTip("继续工作计时，并设为当前进行中")
            resume_button.clicked.connect(lambda checked=False, task_id=task_id: self.resume_task(task_id, make_focus=True))
            compact_row.addWidget(resume_button)
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

        detail_row = QHBoxLayout()
        detail_row.setSpacing(_scale_px(6))
        detail_row.addStretch(1)
        pause_button = QPushButton()
        self._configure_pause_resume_button(pause_button, paused=is_paused)
        if is_paused:
            pause_button.setToolTip("继续工作计时，并设为当前进行中")
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

    def _configure_pause_resume_button(self, button: QPushButton, *, paused: bool, focus: bool = False) -> None:
        if paused:
            button.setText("▶")
            button.setObjectName("resumeTaskButton")
            button.setToolTip("继续工作计时")
            button.setAccessibleName("继续工作计时")
        else:
            button.setText("Ⅱ")
            button.setObjectName("focusPauseButton" if focus else "pauseTaskButton")
            button.setToolTip("暂停工作计时，截止倒计时仍继续")
            button.setAccessibleName("暂停工作计时")
        button.setCursor(Qt.PointingHandCursor)
        if focus:
            button.setFixedHeight(_scale_px(40))
            button.setMinimumWidth(_scale_px(96))
            button.setMaximumWidth(16777215)
        else:
            button.setFixedSize(_scale_px(44), _scale_px(36))
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
    glow_stop = "#0E7490" if selected else selected_stop
    mid_stop = "#0B2235" if selected else "#081725"
    return (
        "QFrame {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        f" stop:0 {style['surface_alt']},"
        f" stop:0.46 {mid_stop},"
        f" stop:1 {glow_stop});"
        "border: none;"
        "border-radius: 8px;"
        "}"
    )


def _summary_card_style(tone: str = "active") -> str:
    stops = {
        "done": ("#0A302B", "#0F4B45", "#0D382D"),
        "active": ("#092949", "#0C4A7C", "#0A2E52"),
        "soon": ("#3B2606", "#7A5310", "#4E3213"),
        "overdue": ("#3B1020", "#7A1E3D", "#481525"),
    }.get(tone, ("#0A1B2B", "#102A3E", "#0B2132"))
    return (
        "QFrame {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        f" stop:0 {stops[0]},"
        f" stop:0.54 {stops[1]},"
        f" stop:1 {stops[2]});"
        "border: 1px solid rgba(125, 211, 252, 0.16);"
        f"border-radius: {_scale_px(8)}px;"
        "}"
    )


def _summary_icon_name(tone: str = "active") -> str:
    return {
        "done": "record-status.svg",
        "active": "nav-task.svg",
        "soon": "task-deadline.svg",
        "overdue": "priority-high.svg",
    }.get(tone, "record-status.svg")


def _summary_footer(tone: str = "active") -> str:
    return {
        "done": "完成率",
        "active": "任务",
        "soon": "即将到期",
        "overdue": "已超时",
    }.get(tone, "")


def _summary_icon_style(tone: str = "active") -> str:
    colors = {
        "done": ("rgba(22, 101, 74, 0.72)", "#5EEAD4"),
        "active": ("rgba(30, 64, 175, 0.62)", "#7DD3FC"),
        "soon": ("rgba(146, 94, 15, 0.68)", "#F6C177"),
        "overdue": ("rgba(127, 29, 29, 0.72)", "#FCA5A5"),
    }.get(tone, ("#10263A", "#22D3EE"))
    return (
        f"background: {colors[0]};"
        f"color: {colors[1]};"
        "border: 1px solid rgba(255, 255, 255, 0.12);"
        f"border-radius: {_scale_px(17)}px;"
        f"font-size: {_scale_px(16)}px;"
        "font-weight: 900;"
    )


def _main_window_style() -> str:
    return """
QFrame#focusSectionAccent, QFrame#taskSectionAccent {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #22D3EE,
    stop:1 #0F766E);
  border: none;
  border-radius: 2px;
}
QLabel#focusSectionTitle, QLabel#taskSectionTitle {
  color: #F8FBFF;
  font-size: 18px;
  font-weight: 900;
}
QLabel#focusStar {
  background: rgba(14, 52, 74, 0.58);
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 17px;
}
QLabel#focusInfoIcon {
  background: rgba(6, 18, 31, 0.34);
  border: 1px solid rgba(186, 230, 253, 0.2);
  border-radius: 14px;
}
QLabel#focusProgressCaption {
  color: #C4D8EA;
  font-weight: 900;
  font-size: 14px;
}
QProgressBar#focusProgressDisplay {
  background: #0A2032;
  border: none;
  border-radius: 4px;
}
QProgressBar#focusProgressDisplay::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #5EEAD4,
    stop:0.58 #22D3EE,
    stop:1 #60A5FA);
  border-radius: 4px;
}
QProgressBar#activeTaskProgressDisplay, QProgressBar#taskProgressDisplay {
  background: #0A2032;
  border: none;
  border-radius: 4px;
}
QProgressBar#activeTaskProgressDisplay::chunk, QProgressBar#taskProgressDisplay::chunk {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #5EEAD4,
    stop:0.58 #22D3EE,
    stop:1 #60A5FA);
  border-radius: 4px;
}
QPushButton#focusCompleteButton {
  color: #DDFBE9;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0F766E,
    stop:1 #047857);
  font-weight: 900;
}
QPushButton#focusCompleteButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:1 #059669);
}
QPushButton#taskFilterButton {
  color: #D7E8F8;
  background: rgba(10, 28, 45, 170);
  border: none;
  border-radius: 8px;
  padding: 7px 13px;
  font-weight: 800;
}
QPushButton#taskFilterButton:hover {
  background: rgba(14, 116, 144, 96);
}
QPushButton#taskViewButton {
  color: #D7E8F8;
  background: rgba(24, 52, 82, 190);
  border: none;
  border-radius: 8px;
  padding: 7px 10px;
  font-weight: 900;
}
QPushButton#taskViewButton:hover {
  background: rgba(34, 211, 238, 80);
}
QPushButton#titleIconButton {
  color: #B8CBE0;
  background: transparent;
  border: none;
  border-radius: 9px;
  padding: 0;
}
QPushButton#titleIconButton:hover {
  background: rgba(125, 211, 252, 0.12);
}
"""


def _task_progress_style(*, selected: bool = False) -> str:
    chunk_end = "#5EEAD4" if selected else "#60A5FA"
    return (
        "QProgressBar {"
        "background: #0A2032;"
        "border: none;"
        f"border-radius: {_scale_px(4)}px;"
        "}"
        "QProgressBar::chunk {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #5EEAD4,"
        " stop:0.58 #22D3EE,"
        f" stop:1 {chunk_end});"
        f"border-radius: {_scale_px(4)}px;"
        "}"
    )


def _add_task_tile_style() -> str:
    return (
        "QPushButton#addTaskTile {"
        "color: #93A9BD;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        " stop:0 rgba(7, 20, 33, 168),"
        " stop:1 rgba(9, 31, 49, 132));"
        "border: 1px dashed rgba(172, 198, 220, 92);"
        f"border-radius: {_scale_px(10)}px;"
        f"font-size: {_scale_px(18)}px;"
        "font-weight: 900;"
        f"padding: {_scale_px(18)}px;"
        "}"
        "QPushButton#addTaskTile:hover {"
        "color: #D7F8FF;"
        "background: rgba(14, 116, 144, 92);"
        "border: 1px dashed rgba(94, 234, 212, 170);"
        "}"
    )


def _progress_value_style(*, selected: bool = False) -> str:
    return (
        f"color: {'#ECFEFF' if selected else '#BFD0E2'};"
        f"font-size: {_scale_px(13)}px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
    )


def _urgency_chip_style(urgency: str) -> str:
    style = _urgency_style(urgency)
    return (
        f"font-size: {_scale_px(14)}px; font-weight: 900; "
        f"padding: {_scale_px(5)}px {_scale_px(10)}px; border-radius: {_scale_px(8)}px; "
        f"min-width: {_scale_px(72)}px; "
        f"background: {style['chip_bg']}; color: {style['chip_text']};"
    )


def _deadline_label_style(urgency: str) -> str:
    return f"color: {_countdown_style(urgency)['accent']}; font-weight: 800; font-size: {_scale_px(13)}px;"


def _focus_deadline_text_style(urgency: str) -> str:
    accent = _countdown_style(urgency)["accent"]
    return (
        f"color: {accent};"
        f"font-size: {_scale_px(16)}px;"
        "font-weight: 900;"
        'font-family: "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI", "Segoe UI Variable";'
        "background: transparent;"
        "border: none;"
    )


def _focus_time_text_style(kind: str, urgency: str) -> str:
    style = _countdown_style(urgency)
    size = _scale_px(19)
    color = "#DDF8F3"
    if urgency == "none":
        color = "#B5CBD9"
    return (
        f"color: {color};"
        f"font-size: {size}px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
        "background: transparent;"
        "border: none;"
    )


def _focus_info_card_style(kind: str, urgency: str, *, pulse: bool = False, paused: bool = False) -> str:
    style = _countdown_style("paused" if paused and kind == "timer" else urgency)
    if kind == "deadline":
        start = "#0A2438" if urgency != "none" else "#091521"
        end = "#0D3A4A" if urgency not in {"none", "overdue"} else ("#122033" if urgency == "none" else "#4A1824")
        border = style["accent"]
    else:
        start = "#1D2B3B" if paused else "#0E3C43"
        end = "#243447" if paused else "#155E75"
        border = "#94A3B8" if paused else "#37D7C2"
    return (
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        f" stop:0 {start},"
        f" stop:1 {end});"
        f"border: 1px solid {border};"
        f"border-radius: {_scale_px(14)}px;"
    )


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
        f"border-radius: {_scale_px(8)}px;"
        f"padding: {_scale_px(5)}px {_scale_px(14)}px;"
        f"min-height: {_scale_px(42)}px;"
        f"min-width: {_scale_px(154)}px;"
        f"font-size: {_scale_px(20)}px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Segoe UI Variable", "Microsoft YaHei UI";'
        f"selection-background-color: {style['accent']};"
    )


def _focus_work_timer_style(urgency: str, *, paused: bool) -> str:
    style = _countdown_style("paused" if paused else urgency)
    start = "#263142" if paused else "#0F3C43"
    end = "#111D2C" if paused else "#155E75"
    return (
        f"color: {style['text']};"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        f" stop:0 {start},"
        f" stop:1 {end});"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        f"padding: {_scale_px(5)}px {_scale_px(10)}px;"
        f"min-height: {_scale_px(42)}px;"
        f"font-size: {_scale_px(18)}px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
    )


def _countdown_display(text: str, pulse: bool) -> str:
    return text


def _task_name_display(title: str) -> str:
    title = str(title).strip()
    if not title:
        return "任务名称：--"
    if title.startswith("任务名称："):
        return title
    return f"任务名称：{title}"


def _focus_countdown_text(text: str) -> str:
    if text.startswith("超时 "):
        return text
    if text == "--:--:--":
        return "倒计时 --:--:--"
    return f"倒计时 {text}"


def _elapsed_work_timer_text(text: str) -> str:
    return text.split(" / ", 1)[0]


def _focus_title_style() -> str:
    return (
        f"font-size: {_scale_px(25)}px;"
        "font-weight: 900;"
        "color: #F8FBFF;"
        "background: transparent;"
        "border: none;"
        f"padding: {_scale_px(8)}px 0;"
    )


def _focus_status_style(*, compact: bool = False) -> str:
    min_width = "56px" if compact else "72px"
    return (
        "color: #BAE6FD;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #10263A,"
        " stop:1 #0F4C5C);"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        f"font-size: {_scale_px(14)}px;"
        "font-weight: 900;"
        f"padding: {_scale_px(5)}px {_scale_px(10)}px;"
        f"min-width: {_scale_px(56 if compact else 72)}px;"
    )


def _focus_status_strip_style() -> str:
    return (
        "QFrame#focusStatusStrip {"
        "background: rgba(3, 18, 30, 0.28);"
        "border: none;"
        f"border-radius: {_scale_px(12)}px;"
        "}"
    )


def _focus_deadline_panel_style() -> str:
    return (
        "QFrame#focusDeadlinePanel {"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
        " stop:0 #071A2B,"
        " stop:0.44 #0B2C45,"
        " stop:1 #0D3A4A);"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        "}"
    )


def _focus_meta_style() -> str:
    return (
        f"font-size: {_scale_px(14)}px;"
        "font-weight: 900;"
        "color: #D9FBE8;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        " stop:0 #123B34,"
        " stop:1 #0F4C5C);"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        f"padding: {_scale_px(5)}px {_scale_px(9)}px;"
    )


def _task_title_style(*, selected: bool = False) -> str:
    if selected:
        background = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0D4960, stop:1 #0B3F49)"
        color = "#F8FBFF"
    else:
        background = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #071421, stop:1 #0A1D2E)"
        color = "#F3F7FC"
    return (
        f"color: {color};"
        f"background: {background};"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        f"padding: {_scale_px(4)}px {_scale_px(8)}px;"
        f"font-size: {_scale_px(15)}px;"
        "font-weight: 900;"
        f"line-height: {_scale_px(18)}px;"
    )


def _task_timer_style(urgency: str, *, selected: bool = False, paused: bool = False) -> str:
    style = _urgency_style("paused" if paused else urgency)
    if selected:
        background = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #125D6E, stop:0.55 #0E7490, stop:1 #0F766E)"
        color = "#ECFEFF"
    elif paused:
        background = "#202838"
        color = "#D6E1F0"
    else:
        background = (
            "qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {style['chip_bg']},"
            " stop:1 #0C1724)"
        )
        color = style["chip_text"]
    return (
        f"color: {color};"
        f"background: {background};"
        "border: none;"
        f"border-radius: {_scale_px(8)}px;"
        f"padding: {_scale_px(4)}px {_scale_px(8)}px;"
        f"font-size: {_scale_px(13)}px;"
        "font-weight: 900;"
        'font-family: "Cascadia Mono", "JetBrains Mono", "Alibaba PuHuiTi 3.0", "Microsoft YaHei UI";'
    )


def _notes_style(*, selected: bool = False) -> str:
    if selected:
        return (
            "color: #D7F8FF; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            " stop:0 #14485C, stop:1 #166552);"
        f"border: none; border-radius: {_scale_px(8)}px; "
        f"padding: {_scale_px(6)}px {_scale_px(8)}px; font-weight: 600; font-size: {_scale_px(13)}px;"
        )
    return (
        f"color: {THEME_COLORS['muted']}; background: #101A27; "
        f"border: none; border-radius: {_scale_px(8)}px; "
        f"padding: {_scale_px(5)}px {_scale_px(8)}px; font-size: {_scale_px(13)}px;"
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
        f"font-size: {_scale_px(14)}px; font-weight: 900; "
        f"padding: {_scale_px(5)}px {_scale_px(10)}px; border-radius: {_scale_px(8)}px; "
        f"min-width: {_scale_px(72)}px; "
        f"background: {style['background']}; color: {style['text']};"
    )


def _task_tag_chip_style(*, selected: bool = False) -> str:
    return (
        f"font-size: {_scale_px(13)}px; font-weight: 900; "
        f"padding: {_scale_px(5)}px {_scale_px(9)}px; border-radius: {_scale_px(8)}px; "
        f"min-width: {_scale_px(54)}px; "
        f"background: {'#155E75' if selected else '#10263A'}; "
        f"color: {'#DDFBFF' if selected else '#BDE7F4'};"
    )


def _countdown_style(urgency: str) -> dict[str, str]:
    return COUNTDOWN_STYLES.get(urgency, COUNTDOWN_STYLES["normal"])
