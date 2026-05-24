from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton


class DialogTitleBar(QFrame):
    def __init__(self, dialog: QDialog, title: str) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self._drag_start: QPoint | None = None
        self.setObjectName("dialogTitleBar")
        self.setFixedHeight(48)
        self.setStyleSheet(
            """
QFrame#dialogTitleBar {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 rgba(7, 18, 31, 236),
    stop:0.54 rgba(11, 32, 53, 244),
    stop:1 rgba(10, 43, 52, 238));
  border: 1px solid rgba(103, 163, 184, 56);
  border-radius: 14px;
}
QLabel#dialogTitleText {
  color: #F8FBFF;
  font-size: 17px;
  font-weight: 900;
}
QPushButton#dialogTitleAction,
QPushButton#dialogTitleCloseButton {
  color: #EAF7FF;
  background: rgba(14, 33, 53, 214);
  border: 1px solid rgba(120, 168, 197, 42);
  border-radius: 9px;
  min-width: 34px;
  max-width: 34px;
  min-height: 34px;
  max-height: 34px;
  padding: 0;
  font-size: 14px;
  font-weight: 900;
}
QPushButton#dialogTitleAction:hover,
QPushButton#dialogTitleCloseButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 rgba(24, 79, 110, 220),
    stop:1 rgba(18, 113, 104, 220));
}
QPushButton#dialogTitleCloseButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 rgba(82, 33, 49, 228),
    stop:1 rgba(129, 39, 57, 228));
}
"""
        )

        layout = QHBoxLayout(self)
        self.layout = layout
        layout.setContentsMargins(14, 7, 7, 7)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitleText")
        layout.addWidget(title_label)
        layout.addStretch(1)

        close_button = QPushButton("")
        close_button.setObjectName("dialogTitleCloseButton")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setToolTip("关闭")
        close_button.setAccessibleName("关闭")
        close_button.setIcon(QIcon(str(_dialog_ui_icon_path("window-close.svg"))))
        close_button.setIconSize(QSize(14, 14))
        close_button.clicked.connect(dialog.reject)
        self.close_button = close_button
        layout.addWidget(close_button)

    def add_action_button(self, text: str, tooltip: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("dialogTitleAction")
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        self.layout.insertWidget(max(0, self.layout.count() - 1), button)
        return button

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.dialog.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None and event.buttons() & Qt.LeftButton:
            self.dialog.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


def _dialog_ui_icon_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "ui" / name
