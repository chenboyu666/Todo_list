from __future__ import annotations

from dataclasses import replace
from datetime import timezone

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task
from floating_todo.theme import THEME_COLORS


class HistoryWindow(QDialog):
    def __init__(self, tasks: list[Task], store, parent=None) -> None:
        super().__init__(parent)
        self.tasks = list(tasks)
        self.store = store
        self.setWindowTitle("历史任务")
        self.setMinimumSize(520, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        title = QLabel("历史任务与完成体会")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        self.container = QWidget()
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)
        self._render()

    def _render(self) -> None:
        completed = [task for task in self.tasks if task.status == "done"]
        if not completed:
            empty = QLabel("还没有完成记录")
            empty.setStyleSheet(f"color: {THEME_COLORS['border']};")
            self.list_layout.addWidget(empty)
            return
        for task in sorted(completed, key=lambda item: item.completed_at or item.updated_at, reverse=True):
            self.list_layout.addWidget(self._history_card(task))
        self.list_layout.addStretch(1)

    def _history_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {THEME_COLORS['surface']}; "
            f"border: 1px solid {THEME_COLORS['border']}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        title = QLabel(f"{task.priority} · {task.title} · {task.progress}%")
        title.setStyleSheet("font-weight: 700;")
        layout.addWidget(title)
        completed_at = task.completed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") if task.completed_at else "--"
        layout.addWidget(QLabel(f"完成时间 {completed_at}"))
        reflection = QTextEdit(task.reflection)
        reflection.setPlaceholderText("记录这次完成后的体会、复盘或下次改进")
        layout.addWidget(reflection)
        save_button = QPushButton("保存体会")
        save_button.clicked.connect(lambda checked=False, task_id=task.id, editor=reflection: self.save_reflection(task_id, editor.toPlainText()))
        layout.addWidget(save_button)
        return card

    def save_reflection(self, task_id: str, reflection: str) -> None:
        updated_tasks: list[Task] = []
        for task in self.tasks:
            updated_tasks.append(replace(task, reflection=reflection) if task.id == task_id else task)
        self.tasks = updated_tasks
        self.store.save_tasks(self.tasks)
