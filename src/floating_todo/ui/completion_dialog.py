from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from floating_todo.domain import Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import apply_soft_shadow


class CompletionDialog(QDialog):
    def __init__(self, task: Task, parent=None) -> None:
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("确认完成")
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

        title = QLabel("准备把这个任务收束归档吗？")
        title.setStyleSheet("font-size: 18px; font-weight: 900;")
        layout.addWidget(title)

        task_title = QLabel(task.title)
        task_title.setWordWrap(True)
        task_title.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        layout.addWidget(task_title)

        body = QLabel("确认后任务会进入历史记录。做完这一项，今天的秩序感会更清楚一点。")
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {THEME_COLORS['muted']};")
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel_button = QPushButton("先不完成")
        cancel_button.clicked.connect(self.reject)
        actions.addWidget(cancel_button)
        confirm_button = QPushButton("确认完成")
        confirm_button.setDefault(True)
        confirm_button.clicked.connect(self.accept)
        actions.addWidget(confirm_button)
        layout.addLayout(actions)
        root.addWidget(panel)
