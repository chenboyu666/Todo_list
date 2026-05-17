from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from floating_todo.theme import THEME_COLORS
from floating_todo.ui.effects import apply_soft_shadow


class FloatingToast(QFrame):
    def __init__(self, title: str, message: str, *, kind: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("floatingToast")
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedWidth(330)
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
        content.setContentsMargins(13, 11, 10, 12)
        content.setSpacing(5)
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

    def show_near(self, parent: QWidget | None = None, *, duration_ms: int = 7000, stack_index: int = 0) -> None:
        self.adjustSize()
        self._position_near(parent, stack_index=stack_index)
        self.show()
        self._auto_close_timer.start(duration_ms)

    def _position_near(self, parent: QWidget | None, *, stack_index: int) -> None:
        spacing = 10
        if parent is not None and parent.isVisible():
            top_right = parent.mapToGlobal(parent.rect().topRight())
            x = top_right.x() - self.width() - 18
            y = top_right.y() + 76 + stack_index * (self.height() + spacing)
            self.move(x, y)
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self.move(
            available.right() - self.width() - 18,
            available.bottom() - self.height() - 18 - stack_index * (self.height() + spacing),
        )


def _toast_style(kind: str) -> str:
    colors = {
        "success": {"accent": "#A7F3D0", "start": "#102B25", "end": "#0F4C5C", "title": "#ECFEFF"},
        "warning": {"accent": "#F6C177", "start": "#2D2414", "end": "#5A3217", "title": "#FFF0CC"},
        "danger": {"accent": "#FCA5A5", "start": "#301722", "end": "#5A1F2B", "title": "#FFE0E7"},
        "info": {"accent": THEME_COLORS["accent"], "start": "#0E1A2A", "end": "#123047", "title": "#ECFEFF"},
    }.get(kind, {"accent": THEME_COLORS["accent"], "start": "#0E1A2A", "end": "#123047", "title": "#ECFEFF"})
    return f"""
QFrame#floatingToast {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 {colors["start"]},
    stop:1 {colors["end"]});
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
  font-size: 15px;
  font-weight: 900;
}}
QLabel#toastMessage {{
  color: #CFE1EE;
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
