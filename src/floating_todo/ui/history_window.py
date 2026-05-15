from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import apply_soft_shadow


class HistoryWindow(QDialog):
    def __init__(self, tasks: list[Task], store, parent=None) -> None:
        super().__init__(parent)
        self.tasks = list(tasks)
        self.store = store
        self.setWindowTitle("历史任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumSize(520, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(DialogTitleBar(self, self.windowTitle()))
        title = QLabel("历史任务与完成体会")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索历史任务")
        self.search_input.textChanged.connect(self._render)
        search_row.addWidget(self.search_input, 1)
        self.count_label = QLabel("0 条")
        self.count_label.setStyleSheet(f"color: {THEME_COLORS['muted']}; font-weight: 700;")
        search_row.addWidget(self.count_label)
        root.addLayout(search_row)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)
        self._render()

    def _render(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        completed = [task for task in self.tasks if task.status == "done"]
        query = self.search_input.text().strip().lower()
        if query:
            completed = [
                task
                for task in completed
                if query in task.title.lower()
                or query in task.priority.lower()
                or query in task.reflection.lower()
                or query in task.notes.lower()
            ]
        self.count_label.setText(f"{len(completed)} 条")
        if not completed:
            empty = QLabel("没有匹配的完成记录" if query else "还没有完成记录")
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
            "border: none; border-radius: 8px; }}"
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_soft_shadow(card, blur=22, y_offset=8, alpha=85)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(f"{task.priority} · {task.title}")
        title.setStyleSheet("font-weight: 700;")
        title.setWordWrap(False)
        header.addWidget(title, 1)
        progress = QLabel(f"{task.progress}%")
        progress.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        header.addWidget(progress)
        layout.addLayout(header)

        completed_at = task.completed_at.astimezone().strftime("%Y-%m-%d %H:%M") if task.completed_at else "--"
        completed = QLabel(f"完成时间 {completed_at}")
        completed.setStyleSheet(f"color: {THEME_COLORS['muted']};")
        layout.addWidget(completed)
        reflection = QTextEdit(task.reflection)
        reflection.setPlaceholderText("记录这次完成后的体会、复盘或下次改进")
        reflection.setFixedHeight(58)
        reflection.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(reflection)
        save_button = QPushButton("保存体会")
        save_button.setFixedWidth(96)
        save_button.clicked.connect(lambda checked=False, task_id=task.id, editor=reflection: self.save_reflection(task_id, editor.toPlainText()))
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        return card

    def save_reflection(self, task_id: str, reflection: str) -> None:
        updated_tasks: list[Task] = []
        for task in self.tasks:
            updated_tasks.append(replace(task, reflection=reflection) if task.id == task_id else task)
        self.tasks = updated_tasks
        self.store.save_tasks(self.tasks)
