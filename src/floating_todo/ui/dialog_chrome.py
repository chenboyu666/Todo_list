from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton


class DialogTitleBar(QFrame):
    def __init__(self, dialog: QDialog, title: str) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self._drag_start: QPoint | None = None
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        layout = QHBoxLayout(self)
        self.layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title_label)
        layout.addStretch(1)
        close_button = QPushButton("×")
        self.close_button = close_button
        close_button.setFixedWidth(38)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setToolTip("关闭")
        close_button.clicked.connect(dialog.reject)
        layout.addWidget(close_button)

    def add_action_button(self, text: str, tooltip: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setFixedWidth(38)
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
