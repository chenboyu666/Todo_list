from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from floating_todo.domain import Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import apply_soft_shadow


class DeleteTaskDialog(QDialog):
    def __init__(self, task: Task, parent=None) -> None:
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("删除任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)
        root.addWidget(DialogTitleBar(self, self.windowTitle()))

        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {THEME_COLORS['surface']}; border: none; border-radius: 8px; }}"
        )
        apply_soft_shadow(panel, blur=32, y_offset=12, alpha=120)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("确认删除这个任务吗？")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        task_title = QLabel(task.title)
        task_title.setWordWrap(True)
        task_title.setStyleSheet(f"color: {THEME_COLORS['danger']}; font-weight: 700;")
        layout.addWidget(task_title)

        body = QLabel("删除后不会进入历史记录，也不会保留体会记录。")
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {THEME_COLORS['muted']};")
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("保留")
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(cancel_button)
        delete_button = QPushButton("确认删除")
        delete_button.setObjectName("dangerButton")
        delete_button.setDefault(True)
        delete_button.clicked.connect(self.accept)
        actions.addWidget(delete_button)
        layout.addLayout(actions)
        root.addWidget(panel)
