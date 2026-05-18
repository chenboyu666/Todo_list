from __future__ import annotations

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QMovie, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from floating_todo.app_resources import resolve_resource_path
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.effects import apply_soft_shadow


class FloatingToast(QFrame):
    def __init__(
        self,
        title: str,
        message: str,
        *,
        kind: str = "info",
        parent: QWidget | None = None,
        background_enabled: bool = False,
        background_image_path: str = "",
        background_overlay: float = 0.68,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("floatingToast")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(360)
        self.kind = kind
        self.background_enabled = bool(background_enabled)
        self.background_image_path = str(background_image_path or "")
        self.background_overlay = max(0.35, min(0.9, float(background_overlay)))
        self._colors = _toast_colors(kind)
        self._pixmap = QPixmap()
        self._movie: QMovie | None = None
        self._load_background()
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.close)
        self.setStyleSheet(_toast_style(kind))
        apply_soft_shadow(self, blur=30, y_offset=10, alpha=135)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        accent = QFrame()
        accent.setObjectName("toastAccent")
        accent.setFixedWidth(5)
        layout.addWidget(accent)

        content = QVBoxLayout()
        content.setContentsMargins(14, 12, 12, 13)
        content.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("toastTitle")
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)
        close_button = QPushButton("×")
        close_button.setObjectName("toastCloseButton")
        close_button.setFixedSize(26, 24)
        close_button.setToolTip("关闭提示")
        close_button.clicked.connect(self.close)
        header.addWidget(close_button)
        content.addLayout(header)

        message_label = QLabel(message)
        message_label.setObjectName("toastMessage")
        message_label.setWordWrap(True)
        content.addWidget(message_label)
        layout.addLayout(content, 1)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if rect.isEmpty():
            return

        shape = QPainterPath()
        shape.addRoundedRect(rect, 8, 8)
        painter.setClipPath(shape)

        background = self._current_background_pixmap()
        if self.background_enabled and not background.isNull():
            scaled = background.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(self.rect(), QColor(7, 10, 18, int(self.background_overlay * 255)))
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(self._colors["start"]))
            gradient.setColorAt(1, QColor(self._colors["end"]))
            painter.fillPath(shape, gradient)
        painter.end()

    def show_near(self, parent: QWidget | None = None, *, duration_ms: int = 7000, stack_index: int = 0) -> None:
        self.adjustSize()
        self._position_near(parent, stack_index=stack_index)
        self.show()
        self._auto_close_timer.start(duration_ms)

    def _load_background(self) -> None:
        if not self.background_enabled:
            return
        path = resolve_resource_path(self.background_image_path)
        if not path.exists():
            return
        if path.suffix.lower() == ".gif":
            self._movie = QMovie(str(path))
            self._movie.setCacheMode(QMovie.CacheAll)
            self._movie.frameChanged.connect(lambda frame_number: self.update())
            self._movie.start()
            return
        self._pixmap = QPixmap(str(path))

    def _current_background_pixmap(self) -> QPixmap:
        if self._movie is not None:
            return self._movie.currentPixmap()
        return self._pixmap

    def closeEvent(self, event) -> None:
        if self._movie is not None:
            self._movie.stop()
        super().closeEvent(event)

    def _position_near(self, parent: QWidget | None, *, stack_index: int) -> None:
        spacing = 10
        if parent is not None and parent.isVisible():
            top_right = parent.mapToGlobal(parent.rect().topRight())
            x = top_right.x() - self.width() - 20
            y = top_right.y() + 70 + stack_index * (self.height() + spacing)
            self.move(x, y)
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.right() - self.width() - 20,
            available.bottom() - self.height() - 20 - stack_index * (self.height() + spacing),
        )


def _toast_colors(kind: str) -> dict[str, str]:
    return {
        "success": {"accent": "#A7F3D0", "start": "#102B25", "end": "#0F4C5C", "title": "#ECFEFF"},
        "warning": {"accent": "#F6C177", "start": "#2D2414", "end": "#5A3217", "title": "#FFF0CC"},
        "danger": {"accent": "#FCA5A5", "start": "#301722", "end": "#5A1F2B", "title": "#FFE0E7"},
        "info": {"accent": THEME_COLORS["accent"], "start": "#0E1A2A", "end": "#123047", "title": "#ECFEFF"},
    }.get(kind, {"accent": THEME_COLORS["accent"], "start": "#0E1A2A", "end": "#123047", "title": "#ECFEFF"})


def _toast_style(kind: str) -> str:
    colors = _toast_colors(kind)
    return f"""
QFrame#floatingToast {{
  background: transparent;
  border: none;
  border-radius: 8px;
}}
QFrame#toastAccent {{
  background: {colors["accent"]};
  border: none;
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
}}
QLabel#toastTitle {{
  color: {colors["title"]};
  font-size: 16px;
  font-weight: 900;
}}
QLabel#toastMessage {{
  color: #DAEAF3;
  font-weight: 700;
  line-height: 18px;
}}
QPushButton#toastCloseButton {{
  color: #DFF7FF;
  background: rgba(255, 255, 255, 24);
  border: none;
  border-radius: 8px;
  padding: 0;
  min-height: 0;
}}
QPushButton#toastCloseButton:hover {{
  background: rgba(255, 255, 255, 44);
}}
"""
