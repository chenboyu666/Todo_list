from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
from floating_todo.ui.effects import animate_content_swap, apply_soft_shadow, prepare_window_entrance


class HistoryNoteDialog(QDialog):
    def __init__(self, task: Task, parent=None) -> None:
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("查看与编辑备注")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumSize(500, 430)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(DialogTitleBar(self, self.windowTitle()))

        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {THEME_COLORS['surface']}; border: none; border-radius: 8px; }}"
        )
        apply_soft_shadow(panel, blur=30, y_offset=10, alpha=110)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        title = QLabel(f"{task.priority} · {task.title}")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(title)

        notes_label = QLabel("任务备注")
        notes_label.setStyleSheet(f"color: {THEME_COLORS['muted']}; font-weight: 700;")
        layout.addWidget(notes_label)
        self.notes_edit = QTextEdit(task.notes)
        self.notes_edit.setPlaceholderText("记录任务背景、上下文或补充说明")
        self.notes_edit.setMinimumHeight(90)
        layout.addWidget(self.notes_edit)

        reflection_label = QLabel("完成体会")
        reflection_label.setStyleSheet(f"color: {THEME_COLORS['muted']}; font-weight: 700;")
        layout.addWidget(reflection_label)
        self.reflection_edit = QTextEdit(task.reflection)
        self.reflection_edit.setPlaceholderText("记录这次完成后的体会、复盘或下次改进")
        self.reflection_edit.setMinimumHeight(120)
        layout.addWidget(self.reflection_edit)

        root.addWidget(panel, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        if buttons.button(QDialogButtonBox.Save):
            buttons.button(QDialogButtonBox.Save).setText("保存")
        if buttons.button(QDialogButtonBox.Cancel):
            buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def notes(self) -> str:
        return self.notes_edit.toPlainText()

    def reflection(self) -> str:
        return self.reflection_edit.toPlainText()


class HistoryWindow(QDialog):
    def __init__(self, tasks: list[Task], store, parent=None) -> None:
        super().__init__(parent)
        self.tasks = list(tasks)
        self.store = store
        self._selected_date_key: str | None = None
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
        self.group_mode = QComboBox()
        self.group_mode.addItems(["按日期", "按等级"])
        self.group_mode.currentTextChanged.connect(self._render)
        search_row.addWidget(self.group_mode)
        self.count_label = QLabel("0 条")
        self.count_label.setStyleSheet(f"color: {THEME_COLORS['muted']}; font-weight: 700;")
        search_row.addWidget(self.count_label)
        root.addLayout(search_row)

        self.date_pager_widget = QWidget()
        date_pager_layout = QHBoxLayout(self.date_pager_widget)
        date_pager_layout.setContentsMargins(0, 0, 0, 0)
        date_pager_layout.setSpacing(8)
        self.prev_date_button = QPushButton("上一页")
        self.prev_date_button.clicked.connect(lambda checked=False: self._move_date_page(-1))
        date_pager_layout.addWidget(self.prev_date_button)
        self.date_page_label = QLabel("")
        self.date_page_label.setStyleSheet(f"color: {THEME_COLORS['accent']}; font-weight: 700;")
        date_pager_layout.addWidget(self.date_page_label, 1)
        self.next_date_button = QPushButton("下一页")
        self.next_date_button.clicked.connect(lambda checked=False: self._move_date_page(1))
        date_pager_layout.addWidget(self.next_date_button)
        root.addWidget(self.date_pager_widget)

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
        completed = self._filtered_completed_tasks()
        self.count_label.setText(f"{len(completed)} 条")
        if not completed:
            self._set_date_pager([], None)
            query = self.search_input.text().strip()
            empty = QLabel("没有匹配的完成记录" if query else "还没有完成记录")
            empty.setStyleSheet(f"color: {THEME_COLORS['border']};")
            self.list_layout.addWidget(empty)
            animate_content_swap(self.container)
            return
        groups = self._group_completed_tasks(completed)
        if self.group_mode.currentText() == "按日期":
            group_title, tasks = self._selected_date_group(groups)
            self._set_date_pager(groups, group_title)
            self.list_layout.addWidget(self._group_header(group_title, len(tasks)))
            for task in tasks:
                self.list_layout.addWidget(self._history_card(task))
        else:
            self._set_date_pager([], None)
            for group_title, tasks in groups:
                self.list_layout.addWidget(self._group_header(group_title, len(tasks)))
                for task in tasks:
                    self.list_layout.addWidget(self._history_card(task))
        self.list_layout.addStretch(1)
        animate_content_swap(self.container)

    def _filtered_completed_tasks(self) -> list[Task]:
        completed = [task for task in self.tasks if task.status == "done"]
        query = self.search_input.text().strip().lower()
        if not query:
            return completed
        return [
            task
            for task in completed
            if query in task.title.lower()
            or query in task.priority.lower()
            or query in task.reflection.lower()
            or query in task.notes.lower()
        ]

    def _group_completed_tasks(self, tasks: list[Task]) -> list[tuple[str, list[Task]]]:
        sorted_tasks = sorted(tasks, key=lambda item: item.completed_at or item.updated_at, reverse=True)
        groups: dict[str, list[Task]] = {}
        if self.group_mode.currentText() == "按等级":
            order = ["P1", "P2", "P3"]
            for task in sorted_tasks:
                groups.setdefault(task.priority, []).append(task)
            return [(priority, groups[priority]) for priority in order if priority in groups]

        for task in sorted_tasks:
            completed_at = task.completed_at or task.updated_at
            title = completed_at.astimezone().strftime("%Y-%m-%d") if completed_at else "未记录日期"
            groups.setdefault(title, []).append(task)
        return list(groups.items())

    def _selected_date_group(self, groups: list[tuple[str, list[Task]]]) -> tuple[str, list[Task]]:
        if not groups:
            return "", []
        titles = [title for title, _ in groups]
        if self._selected_date_key not in titles:
            self._selected_date_key = titles[0]
        for title, tasks in groups:
            if title == self._selected_date_key:
                return title, tasks
        return groups[0]

    def _set_date_pager(self, groups: list[tuple[str, list[Task]]], selected_title: str | None) -> None:
        visible = self.group_mode.currentText() == "按日期" and bool(groups)
        self.date_pager_widget.setVisible(visible)
        if not visible or selected_title is None:
            self.date_page_label.setText("")
            self.prev_date_button.setEnabled(False)
            self.next_date_button.setEnabled(False)
            return
        titles = [title for title, _ in groups]
        index = titles.index(selected_title)
        selected_tasks = groups[index][1]
        self.date_page_label.setText(f"{selected_title} · {len(selected_tasks)} 条 · {index + 1}/{len(groups)}")
        self.prev_date_button.setEnabled(index > 0)
        self.next_date_button.setEnabled(index < len(groups) - 1)

    def _move_date_page(self, offset: int) -> None:
        groups = self._group_completed_tasks(self._filtered_completed_tasks())
        if not groups:
            return
        titles = [title for title, _ in groups]
        current_index = titles.index(self._selected_date_key) if self._selected_date_key in titles else 0
        next_index = max(0, min(len(groups) - 1, current_index + offset))
        self._selected_date_key = titles[next_index]
        self._render()

    def _group_header(self, title: str, count: int) -> QLabel:
        label = QLabel(f"{title} · {count} 条")
        label.setStyleSheet(
            f"color: {THEME_COLORS['accent']}; "
            "font-size: 14px; font-weight: 700; padding: 6px 2px 2px 2px;"
        )
        return label

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
        preview = QLabel(self._note_preview(task))
        preview.setWordWrap(True)
        preview.setStyleSheet(f"color: {THEME_COLORS['muted']};")
        layout.addWidget(preview)
        note_button = QPushButton("查看/编辑备注")
        note_button.setFixedWidth(126)
        note_button.clicked.connect(lambda checked=False, task=task: self.open_note_editor(task))
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(note_button)
        layout.addLayout(actions)
        return card

    def _note_preview(self, task: Task) -> str:
        text = (task.reflection or task.notes or "还没有记录备注或完成体会").strip()
        return text if len(text) <= 54 else f"{text[:54]}..."

    def open_note_editor(self, task: Task) -> None:
        dialog = HistoryNoteDialog(task, self)
        prepare_window_entrance(dialog)
        if dialog.exec() != QDialog.Accepted:
            return
        self.save_history_notes(task.id, dialog.notes(), dialog.reflection())
        self._render()

    def save_history_notes(self, task_id: str, notes: str, reflection: str) -> None:
        updated_tasks: list[Task] = []
        for task in self.tasks:
            if task.id == task_id:
                updated_tasks.append(replace(task, notes=notes, reflection=reflection))
            else:
                updated_tasks.append(task)
        self.tasks = updated_tasks
        self.store.save_tasks(self.tasks)

    def save_reflection(self, task_id: str, reflection: str) -> None:
        task = next((item for item in self.tasks if item.id == task_id), None)
        self.save_history_notes(task_id, task.notes if task else "", reflection)
