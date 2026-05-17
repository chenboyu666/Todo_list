from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import animate_content_swap, apply_soft_shadow, prepare_window_entrance


CSV_HEADERS = [
    "任务ID",
    "标题",
    "优先级",
    "预估工作量分钟",
    "截止时间",
    "进度",
    "状态",
    "创建时间",
    "更新时间",
    "完成时间",
    "任务备注",
    "完成体会",
]


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
        self._selected_page_index = 0
        self._syncing_date_selector = False
        self.setWindowTitle("历史任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumSize(520, 560)
        self.setStyleSheet(_history_window_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        root.addWidget(DialogTitleBar(self, self.windowTitle()))

        header_panel = QFrame()
        header_panel.setObjectName("historyHeaderPanel")
        header_layout = QHBoxLayout(header_panel)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(12)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(3)
        title = QLabel("历史任务")
        title.setObjectName("historyTitle")
        subtitle = QLabel("完成记录 · 复盘备注 · 进度归档")
        subtitle.setObjectName("historySubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header_layout.addLayout(title_stack, 1)
        self.count_label = QLabel("0 条")
        self.count_label.setObjectName("historyCountChip")
        self.count_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.count_label)
        root.addWidget(header_panel)

        stats_panel = QFrame()
        stats_panel.setObjectName("historyStatsPanel")
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(10, 8, 10, 8)
        stats_layout.setSpacing(7)
        priority_metrics = QHBoxLayout()
        priority_metrics.setContentsMargins(0, 0, 0, 0)
        priority_metrics.setSpacing(8)
        self.priority_p1_label = self._metric_label("P1 0", "historyPriorityMetricP1")
        self.priority_p2_label = self._metric_label("P2 0", "historyPriorityMetricP2")
        self.priority_p3_label = self._metric_label("P3 0", "historyPriorityMetricP3")
        self.priority_mix_label = self.priority_p1_label
        for metric in (self.priority_p1_label, self.priority_p2_label, self.priority_p3_label):
            priority_metrics.addWidget(metric, 1)
        stats_layout.addLayout(priority_metrics)

        summary_metrics = QHBoxLayout()
        summary_metrics.setContentsMargins(0, 0, 0, 0)
        summary_metrics.setSpacing(8)
        self.review_metric_label = self._metric_label("复盘 0/0")
        self.average_metric_label = self._metric_label("平均进度 --")
        self.latest_metric_label = self._metric_label("最近 --")
        for metric in (
            self.review_metric_label,
            self.average_metric_label,
            self.latest_metric_label,
        ):
            summary_metrics.addWidget(metric, 1)
        stats_layout.addLayout(summary_metrics)
        root.addWidget(stats_panel)

        toolbar_panel = QFrame()
        toolbar_panel.setObjectName("historyToolbar")
        toolbar_layout = QVBoxLayout(toolbar_panel)
        toolbar_layout.setContentsMargins(7, 7, 7, 7)
        toolbar_layout.setSpacing(8)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("historySearch")
        self.search_input.setPlaceholderText("搜索历史任务")
        self.search_input.textChanged.connect(self._render)
        search_row.addWidget(self.search_input, 1)
        self.group_mode = QComboBox()
        self.group_mode.setObjectName("historyMode")
        self.group_mode.addItems(["按日期", "按等级"])
        self.group_mode.currentTextChanged.connect(self._reset_page)
        search_row.addWidget(self.group_mode)
        page_size_label = QLabel("每页")
        page_size_label.setStyleSheet(f"color: {THEME_COLORS['muted']}; font-weight: 700;")
        search_row.addWidget(page_size_label)
        self.page_size_input = QSpinBox()
        self.page_size_input.setRange(1, 100)
        self.page_size_input.setValue(5)
        self.page_size_input.setSuffix(" 条")
        self.page_size_input.setToolTip("右侧 ↑ 增加每页条数，↓ 减少每页条数")
        self.page_size_input.valueChanged.connect(self._reset_page)
        search_row.addWidget(self.page_size_input)
        self.page_size_step_hint = QLabel("↑ 多 / ↓ 少")
        self.page_size_step_hint.setObjectName("historyStepHint")
        self.page_size_step_hint.setAlignment(Qt.AlignCenter)
        self.page_size_step_hint.setToolTip("说明每页条数右侧灰色箭头的含义")
        search_row.addWidget(self.page_size_step_hint)

        export_row = QHBoxLayout()
        export_row.setContentsMargins(0, 0, 0, 0)
        export_row.setSpacing(8)
        export_range_label = QLabel("导出日期")
        export_range_label.setObjectName("historyToolbarLabel")
        export_row.addWidget(export_range_label)
        self.export_start_date = QDateEdit()
        self.export_start_date.setObjectName("historyExportStartDate")
        self.export_start_date.setCalendarPopup(True)
        self.export_start_date.setDisplayFormat("yyyy-MM-dd")
        self.export_start_date.setToolTip("选择 CSV 导出的起始完成日期")
        self.export_start_date.setAccessibleName("导出起始日期")
        export_row.addWidget(self.export_start_date)
        export_to_label = QLabel("至")
        export_to_label.setObjectName("historyToolbarLabel")
        export_row.addWidget(export_to_label)
        self.export_end_date = QDateEdit()
        self.export_end_date.setObjectName("historyExportEndDate")
        self.export_end_date.setCalendarPopup(True)
        self.export_end_date.setDisplayFormat("yyyy-MM-dd")
        self.export_end_date.setToolTip("选择 CSV 导出的结束完成日期")
        self.export_end_date.setAccessibleName("导出结束日期")
        export_row.addWidget(self.export_end_date)
        export_row.addStretch(1)
        self.export_button = QPushButton("导出 CSV")
        self.export_button.setObjectName("historyExportButton")
        self.export_button.setToolTip("导出当前搜索结果中日期范围内的历史记录表格")
        self.export_button.clicked.connect(self.export_history)
        export_row.addWidget(self.export_button)
        toolbar_layout.addLayout(search_row)
        toolbar_layout.addLayout(export_row)
        root.addWidget(toolbar_panel)
        self._configure_export_date_range()

        self.date_pager_widget = QWidget()
        date_pager_layout = QHBoxLayout(self.date_pager_widget)
        date_pager_layout.setContentsMargins(0, 0, 0, 0)
        date_pager_layout.setSpacing(8)
        date_selector_label = QLabel("日期")
        date_selector_label.setObjectName("historyToolbarLabel")
        date_pager_layout.addWidget(date_selector_label)
        self.date_selector = QComboBox()
        self.date_selector.setObjectName("historyDateSelector")
        self.date_selector.setToolTip("选择要查看的完成日期")
        self.date_selector.currentIndexChanged.connect(self._select_date_from_combo)
        date_pager_layout.addWidget(self.date_selector, 1)
        self.date_page_label = QLabel("")
        self.date_page_label.setObjectName("historyPageLabel")
        date_pager_layout.addWidget(self.date_page_label, 1)
        self.prev_date_button = QPushButton("上一页")
        self.prev_date_button.setObjectName("historyPageButton")
        self.prev_date_button.clicked.connect(lambda checked=False: self._move_date_page(-1))
        date_pager_layout.addWidget(self.prev_date_button)
        self.next_date_button = QPushButton("下一页")
        self.next_date_button.setObjectName("historyPageButton")
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

    def _metric_label(self, text: str, object_name: str = "historyMetricChip") -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(32)
        label.setWordWrap(False)
        return label

    def _configure_export_date_range(self) -> None:
        dates = [_task_completed_date(task) for task in self.tasks if task.status == "done"]
        dates = [item for item in dates if item is not None]
        if dates:
            start = min(dates)
            end = max(dates)
        else:
            today = QDate.currentDate().toPython()
            start = today
            end = today
        start_qdate = QDate(start.year, start.month, start.day)
        end_qdate = QDate(end.year, end.month, end.day)
        for edit, value in ((self.export_start_date, start_qdate), (self.export_end_date, end_qdate)):
            edit.setDateRange(start_qdate, end_qdate)
            edit.setDate(value)

    def _render(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        completed = self._filtered_completed_tasks()
        self.count_label.setText(f"{len(completed)} 条")
        self._update_metrics(completed)
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
            self._clamp_selected_page(tasks)
            self._set_date_pager(groups, group_title)
            self.list_layout.addWidget(self._group_header(group_title, len(tasks)))
            for task in self._page_tasks(tasks):
                self.list_layout.addWidget(self._history_card(task))
        else:
            self._clamp_selected_page(completed)
            self._set_level_pager(completed)
            for group_title, tasks, total_count in self._paged_group_slices(groups):
                self.list_layout.addWidget(self._group_header(group_title, total_count))
                for task in tasks:
                    self.list_layout.addWidget(self._history_card(task))
        self.list_layout.addStretch(1)
        animate_content_swap(self.container)

    def _update_metrics(self, completed: list[Task]) -> None:
        total = len(completed)
        counts = {
            priority: sum(1 for task in completed if task.priority == priority)
            for priority in ("P1", "P2", "P3")
        }
        reviewed = sum(1 for task in completed if task.notes.strip() or task.reflection.strip())
        average = round(sum(task.progress for task in completed) / total) if total else None
        latest_task = max(completed, key=lambda task: task.completed_at or task.updated_at, default=None)
        latest = (
            (latest_task.completed_at or latest_task.updated_at).astimezone().strftime("%m-%d %H:%M")
            if latest_task
            else "--"
        )
        self.priority_p1_label.setText(f"P1 {counts['P1']}")
        self.priority_p2_label.setText(f"P2 {counts['P2']}")
        self.priority_p3_label.setText(f"P3 {counts['P3']}")
        self.review_metric_label.setText(f"复盘 {reviewed}/{total}")
        self.average_metric_label.setText(f"平均进度 {average}%" if average is not None else "平均进度 --")
        self.latest_metric_label.setText(f"最近 {latest}")

    def _reset_page(self, *args) -> None:
        self._selected_page_index = 0
        self._render()

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

    def _exportable_tasks(self) -> list[Task]:
        return self._tasks_in_export_date_range(self._filtered_completed_tasks())

    def _tasks_in_export_date_range(self, tasks: list[Task]) -> list[Task]:
        start = self.export_start_date.date().toPython()
        end = self.export_end_date.date().toPython()
        if start > end:
            start, end = end, start
        return [task for task in tasks if _date_in_range(_task_completed_date(task), start, end)]

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
            self._selected_page_index = 0
        for title, tasks in groups:
            if title == self._selected_date_key:
                return title, tasks
        return groups[0]

    def _page_size(self) -> int:
        return max(1, self.page_size_input.value())

    def _page_count(self, tasks: list[Task]) -> int:
        return max(1, (len(tasks) + self._page_size() - 1) // self._page_size())

    def _clamp_selected_page(self, tasks: list[Task]) -> None:
        self._selected_page_index = max(0, min(self._selected_page_index, self._page_count(tasks) - 1))

    def _page_tasks(self, tasks: list[Task]) -> list[Task]:
        page_size = self._page_size()
        start = self._selected_page_index * page_size
        return tasks[start : start + page_size]

    def _paged_group_slices(self, groups: list[tuple[str, list[Task]]]) -> list[tuple[str, list[Task], int]]:
        page_size = self._page_size()
        start = self._selected_page_index * page_size
        end = start + page_size
        cursor = 0
        paged: list[tuple[str, list[Task], int]] = []
        for group_title, tasks in groups:
            group_start = cursor
            group_end = cursor + len(tasks)
            cursor = group_end
            if group_end <= start or group_start >= end:
                continue
            slice_start = max(0, start - group_start)
            slice_end = min(len(tasks), end - group_start)
            paged.append((group_title, tasks[slice_start:slice_end], len(tasks)))
        return paged

    def _set_date_pager(self, groups: list[tuple[str, list[Task]]], selected_title: str | None) -> None:
        visible = self.group_mode.currentText() == "按日期" and bool(groups)
        self.date_pager_widget.setVisible(visible)
        if not visible or selected_title is None:
            self.date_page_label.setText("")
            self._sync_date_selector([], None)
            self.prev_date_button.setEnabled(False)
            self.next_date_button.setEnabled(False)
            return
        titles = [title for title, _ in groups]
        index = titles.index(selected_title)
        selected_tasks = groups[index][1]
        self._clamp_selected_page(selected_tasks)
        self._sync_date_selector(groups, selected_title)
        page_size = self._page_size()
        page_count = self._page_count(selected_tasks)
        start = self._selected_page_index * page_size + 1
        end = min(len(selected_tasks), start + page_size - 1)
        self.date_page_label.setText(
            f"{start}-{end}/{len(selected_tasks)} 条 · {self._selected_page_index + 1}/{page_count} 页"
        )
        self.prev_date_button.setEnabled(self._selected_page_index > 0)
        self.next_date_button.setEnabled(self._selected_page_index < page_count - 1)

    def _set_level_pager(self, tasks: list[Task]) -> None:
        self.date_pager_widget.setVisible(bool(tasks))
        if not tasks:
            self.date_page_label.setText("")
            self._sync_date_selector([], None)
            self.prev_date_button.setEnabled(False)
            self.next_date_button.setEnabled(False)
            return
        self._sync_date_selector([], None)
        self._clamp_selected_page(tasks)
        page_size = self._page_size()
        page_count = self._page_count(tasks)
        start = self._selected_page_index * page_size + 1
        end = min(len(tasks), start + page_size - 1)
        self.date_page_label.setText(
            f"按等级 · {start}-{end}/{len(tasks)} 条 · {self._selected_page_index + 1}/{page_count} 页"
        )
        self.prev_date_button.setEnabled(self._selected_page_index > 0)
        self.next_date_button.setEnabled(self._selected_page_index < page_count - 1)

    def _sync_date_selector(self, groups: list[tuple[str, list[Task]]], selected_title: str | None) -> None:
        self._syncing_date_selector = True
        try:
            self.date_selector.clear()
            for title, tasks in groups:
                self.date_selector.addItem(f"{title}  ·  {len(tasks)} 条", title)
            if selected_title is None:
                self.date_selector.addItem("全部等级", "")
                self.date_selector.setEnabled(False)
                return
            self.date_selector.setEnabled(True)
            index = self.date_selector.findData(selected_title)
            self.date_selector.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self._syncing_date_selector = False

    def _select_date_from_combo(self, index: int) -> None:
        if self._syncing_date_selector or index < 0:
            return
        selected = self.date_selector.itemData(index)
        if not selected or selected == self._selected_date_key:
            return
        self._selected_date_key = str(selected)
        self._selected_page_index = 0
        self._render()

    def _move_date_page(self, offset: int) -> None:
        if self.group_mode.currentText() != "按日期":
            completed = self._filtered_completed_tasks()
            if not completed:
                return
            self._clamp_selected_page(completed)
            next_page = self._selected_page_index + offset
            if 0 <= next_page < self._page_count(completed):
                self._selected_page_index = next_page
                self._render()
            return
        groups = self._group_completed_tasks(self._filtered_completed_tasks())
        if not groups:
            return
        titles = [title for title, _ in groups]
        current_index = titles.index(self._selected_date_key) if self._selected_date_key in titles else 0
        current_tasks = groups[current_index][1]
        self._clamp_selected_page(current_tasks)
        next_page = self._selected_page_index + offset
        if 0 <= next_page < self._page_count(current_tasks):
            self._selected_page_index = next_page
            self._render()

    def _group_header(self, title: str, count: int) -> QLabel:
        label = QLabel(f"{title} · {count} 条")
        label.setObjectName("historyGroupHeader")
        return label

    def _history_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setObjectName("historyCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        apply_soft_shadow(card, blur=28, y_offset=10, alpha=105)
        shell = QHBoxLayout(card)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        accent = QFrame()
        accent.setObjectName(f"historyAccent{task.priority}")
        accent.setFixedWidth(4)
        shell.addWidget(accent)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 10, 12, 11)
        layout.setSpacing(6)
        shell.addWidget(content, 1)

        header = QHBoxLayout()
        header.setSpacing(8)
        priority = QLabel(task.priority)
        priority.setObjectName(f"historyPriority{task.priority}")
        priority.setAlignment(Qt.AlignCenter)
        priority.setFixedHeight(24)
        priority.setFixedWidth(42)
        header.addWidget(priority)
        title = QLabel(task.title)
        title.setObjectName("historyTaskTitle")
        title.setWordWrap(False)
        header.addWidget(title, 1)
        progress = QLabel(f"{task.progress}%")
        progress.setObjectName("historyProgressChip")
        progress.setAlignment(Qt.AlignCenter)
        header.addWidget(progress)
        review_status = QLabel("已复盘" if task.notes.strip() or task.reflection.strip() else "待补记")
        review_status.setObjectName(
            "historyReviewChipDone" if task.notes.strip() or task.reflection.strip() else "historyReviewChipEmpty"
        )
        review_status.setAlignment(Qt.AlignCenter)
        header.addWidget(review_status)
        layout.addLayout(header)

        progress_bar = QProgressBar()
        progress_bar.setObjectName("historyInlineProgress")
        progress_bar.setRange(0, 100)
        progress_bar.setValue(task.progress)
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(6)
        layout.addWidget(progress_bar)

        completed_at = task.completed_at.astimezone().strftime("%Y-%m-%d %H:%M") if task.completed_at else "--"
        completed = QLabel(f"完成时间 {completed_at}")
        completed.setObjectName("historyCompletedAt")
        layout.addWidget(completed)
        for preview_text in self._note_previews(task):
            preview = QLabel(preview_text)
            preview.setWordWrap(True)
            preview.setObjectName("historyPreview")
            layout.addWidget(preview)
        note_button = QPushButton("查看/编辑备注")
        note_button.setObjectName("historyNoteButton")
        note_button.setFixedWidth(126)
        note_button.clicked.connect(lambda checked=False, task=task: self.open_note_editor(task))
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(note_button)
        layout.addLayout(actions)
        return card

    def _note_previews(self, task: Task) -> list[str]:
        previews: list[str] = []
        notes = self._compact_text(task.notes)
        reflection = self._compact_text(task.reflection)
        if notes:
            previews.append(f"任务备注：{notes}")
        if reflection:
            previews.append(f"完成体会：{reflection}")
        return previews or ["还没有记录备注或完成体会"]

    def _compact_text(self, text: str, limit: int = 54) -> str:
        compact = " ".join(str(text or "").split())
        return compact if len(compact) <= limit else f"{compact[:limit]}..."

    def export_history(self) -> None:
        tasks = self._exportable_tasks()
        if not tasks:
            QMessageBox.information(self, "导出历史记录", "没有可导出的历史记录。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出历史记录",
            "Todo list-历史记录.csv",
            "CSV 表格 (*.csv);;All Files (*)",
        )
        if not path:
            return
        export_path = Path(path)
        if export_path.suffix.lower() != ".csv":
            export_path = export_path.with_suffix(".csv")
        count = self.export_history_to_path(export_path, tasks)
        QMessageBox.information(self, "导出历史记录", f"已导出 {count} 条历史记录。")

    def export_history_to_path(self, path: str | Path, tasks: list[Task] | None = None) -> int:
        export_tasks = list(tasks if tasks is not None else self._exportable_tasks())
        export_history_csv(path, export_tasks)
        return len(export_tasks)

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


def export_history_csv(path: str | Path, tasks: list[Task]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "任务ID": task.id,
                    "标题": task.title,
                    "优先级": task.priority,
                    "预估工作量分钟": task.effort_minutes,
                    "截止时间": _export_datetime(task.deadline),
                    "进度": f"{task.progress}%",
                    "状态": task.status,
                    "创建时间": _export_datetime(task.created_at),
                    "更新时间": _export_datetime(task.updated_at),
                    "完成时间": _export_datetime(task.completed_at),
                    "任务备注": task.notes,
                    "完成体会": task.reflection,
                }
            )


def _export_datetime(value) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _task_completed_date(task: Task) -> date | None:
    value = task.completed_at or task.updated_at
    return value.astimezone().date() if value else None


def _date_in_range(value: date | None, start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def _history_window_style() -> str:
    return f"""
QFrame#historyHeaderPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E1A2A,
    stop:0.55 #10263A,
    stop:1 #12362D);
  border: none;
  border-radius: 8px;
}}
QLabel#historyTitle {{
  color: #F8FBFF;
  font-size: 22px;
  font-weight: 900;
}}
QLabel#historySubtitle {{
  color: #9EB5C8;
  font-weight: 700;
}}
QLabel#historyCountChip {{
  color: #DFFBFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #155E75,
    stop:1 #047857);
  border: none;
  border-radius: 8px;
  min-width: 72px;
  min-height: 34px;
  font-size: 16px;
  font-weight: 900;
}}
QFrame#historyStatsPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0A111B,
    stop:0.5 #0C1826,
    stop:1 #0E211F);
  border: none;
  border-radius: 8px;
}}
QLabel#historyMetricChip,
QLabel#historyPriorityMetricP1,
QLabel#historyPriorityMetricP2,
QLabel#historyPriorityMetricP3 {{
  color: #D4E3F2;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #111D2C,
    stop:1 #102A34);
  border: none;
  border-radius: 8px;
  font-weight: 900;
}}
QLabel#historyPriorityMetricP1 {{
  color: #FFE1A6;
  background: #4E2814;
}}
QLabel#historyPriorityMetricP2 {{
  color: #DCE7FF;
  background: #182B60;
}}
QLabel#historyPriorityMetricP3 {{
  color: #D9FBE8;
  background: #123A33;
}}
QFrame#historyToolbar {{
  background: #0C121D;
  border: none;
  border-radius: 8px;
  padding: 7px;
}}
QLabel#historyToolbarLabel {{
  color: #BFD0E2;
  font-weight: 900;
  padding: 0 4px;
}}
QLineEdit#historySearch, QComboBox#historyMode, QComboBox#historyDateSelector,
QDateEdit#historyExportStartDate, QDateEdit#historyExportEndDate {{
  background: #101827;
  font-weight: 700;
}}
QLabel#historyPageLabel {{
  color: #7DD3FC;
  background: #0C1724;
  border: none;
  border-radius: 8px;
  padding: 7px 12px;
  font-weight: 900;
}}
QLabel#historyStepHint {{
  color: #BAE6FD;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #102033,
    stop:1 #103A3D);
  border: none;
  border-radius: 8px;
  padding: 7px 9px;
  font-size: 12px;
  font-weight: 900;
}}
QPushButton#historyPageButton, QPushButton#historyNoteButton, QPushButton#historyExportButton {{
  background: #162033;
  color: #F6F8FC;
  font-weight: 800;
}}
QPushButton#historyPageButton:hover, QPushButton#historyNoteButton:hover, QPushButton#historyExportButton:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1E3A5F,
    stop:1 #155E75);
}}
QLabel#historyGroupHeader {{
  color: #7DD3FC;
  font-size: 15px;
  font-weight: 900;
  padding: 9px 4px 4px 4px;
}}
QFrame#historyCard {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #111827,
    stop:0.58 #121E2F,
    stop:1 #102B35);
  border: none;
  border-radius: 8px;
}}
QFrame#historyAccentP1 {{ background: #F6A44D; border-radius: 2px; }}
QFrame#historyAccentP2 {{ background: #8EA7FF; border-radius: 2px; }}
QFrame#historyAccentP3 {{ background: #A7F3D0; border-radius: 2px; }}
QLabel#historyPriorityP1, QLabel#historyPriorityP2, QLabel#historyPriorityP3 {{
  border: none;
  border-radius: 7px;
  font-weight: 900;
}}
QLabel#historyPriorityP1 {{ color: #FFE1A6; background: #5A2D12; }}
QLabel#historyPriorityP2 {{ color: #DCE7FF; background: #1B2F69; }}
QLabel#historyPriorityP3 {{ color: #D9FBE8; background: #123B34; }}
QLabel#historyTaskTitle {{
  color: #F8FBFF;
  font-size: 15px;
  font-weight: 900;
}}
QLabel#historyProgressChip {{
  color: #ECFEFF;
  background: #0E7490;
  border: none;
  border-radius: 8px;
  min-width: 58px;
  min-height: 24px;
  font-weight: 900;
}}
QLabel#historyReviewChipDone, QLabel#historyReviewChipEmpty {{
  border: none;
  border-radius: 8px;
  min-width: 62px;
  min-height: 24px;
  font-weight: 900;
}}
QLabel#historyReviewChipDone {{
  color: #DDFBE9;
  background: #145246;
}}
QLabel#historyReviewChipEmpty {{
  color: #F7DCA8;
  background: #4A3218;
}}
QProgressBar#historyInlineProgress {{
  background: #09111B;
  border: none;
  border-radius: 3px;
  height: 6px;
}}
QProgressBar#historyInlineProgress::chunk {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #A7F3D0,
    stop:0.52 #7DD3FC,
    stop:1 #F6C177);
  border-radius: 3px;
}}
QLabel#historyCompletedAt {{
  color: #AEC2D3;
  font-weight: 700;
}}
QLabel#historyPreview {{
  color: #C4D2E2;
  background: #0C1421;
  border: none;
  border-radius: 8px;
  padding: 6px 8px;
  font-weight: 600;
}}
"""
