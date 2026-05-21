from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSizeGrip,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task, work_elapsed_seconds, work_target_seconds
from floating_todo.theme import THEME_COLORS
from floating_todo.ui.date_controls import apply_dark_calendar_popup
from floating_todo.ui.dialog_chrome import DialogTitleBar
from floating_todo.ui.effects import animate_content_swap, apply_soft_shadow, prepare_window_entrance
from floating_todo.view_models import (
    PRIORITY_ORDER,
    duration_clock_label,
    effort_short_label,
    priority_display_label,
    priority_text,
)


CSV_HEADERS = [
    "任务ID",
    "标题",
    "优先级",
    "预估工作量分钟",
    "实际工作时长",
    "实际工作秒数",
    "截止时间",
    "进度",
    "状态",
    "创建时间",
    "更新时间",
    "完成时间",
    "任务备注",
    "完成体会",
]

PRIORITY_CHART_COLORS = {
    "P1": "#F6A44D",
    "P2": "#8EA7FF",
    "P3": "#A7F3D0",
}


class PriorityDonutChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.priority_counts = {priority: 0 for priority in PRIORITY_ORDER}
        self.setObjectName("historyPriorityDonutChart")
        self.setAccessibleName("优先级完成结构图")
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_counts(self, counts: dict[str, int]) -> None:
        self.priority_counts = {priority: max(0, int(counts.get(priority, 0))) for priority in PRIORITY_ORDER}
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(6, 4, -6, -6)
        if rect.isEmpty():
            return
        total = sum(self.priority_counts.values())
        diameter = min(86.0, rect.height() - 16, rect.width() * 0.42)
        chart_rect = QRectF(rect.left() + 4, rect.center().y() - diameter / 2, diameter, diameter)
        center = chart_rect.center()
        ring_width = max(13.0, diameter * 0.18)

        painter.setPen(QPen(QColor("#162235"), ring_width, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(chart_rect.adjusted(ring_width / 2, ring_width / 2, -ring_width / 2, -ring_width / 2))

        if total:
            start_angle = 90 * 16
            arc_rect = chart_rect.adjusted(ring_width / 2, ring_width / 2, -ring_width / 2, -ring_width / 2)
            for priority in PRIORITY_ORDER:
                count = self.priority_counts[priority]
                if not count:
                    continue
                span_angle = int(-360 * 16 * count / total)
                painter.setPen(QPen(QColor(PRIORITY_CHART_COLORS[priority]), ring_width, Qt.SolidLine, Qt.RoundCap))
                painter.drawArc(arc_rect, start_angle, span_angle)
                start_angle += span_angle

        painter.setPen(QColor("#F8FBFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(13)
        painter.setFont(font)
        painter.drawText(chart_rect, Qt.AlignCenter, str(total))

        legend_x = chart_rect.right() + 18
        legend_y = rect.top() + 16
        font.setPointSize(8)
        painter.setFont(font)
        for index, priority in enumerate(PRIORITY_ORDER):
            y = legend_y + index * 25
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PRIORITY_CHART_COLORS[priority]))
            painter.drawRoundedRect(QRectF(legend_x, y + 4, 22, 8), 4, 4)
            painter.setPen(QColor("#D8E8F5"))
            count = self.priority_counts[priority]
            percent = round(count / total * 100) if total else 0
            painter.drawText(
                QRectF(legend_x + 30, y - 2, rect.right() - legend_x - 30, 22),
                Qt.AlignLeft,
                f"{priority_display_label(priority)}：{count} · {percent}%",
            )


class CompletionTrendChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.trend_points: list[tuple[date, int]] = []
        self.setObjectName("historyCompletionTrendChart")
        self.setAccessibleName("每日完成曲线图")
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_points(self, points: list[tuple[date, int]]) -> None:
        self.trend_points = list(points)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        plot = outer.adjusted(28, 12, -10, -28)
        if plot.width() <= 0 or plot.height() <= 0:
            return

        painter.setPen(QPen(QColor("#1F3146"), 1))
        for index in range(4):
            y = plot.top() + plot.height() * index / 3
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        if not self.trend_points:
            painter.setPen(QColor("#6F8093"))
            painter.drawText(outer, Qt.AlignCenter, "暂无趋势")
            return

        max_value = max(1, max(value for _, value in self.trend_points))
        coordinates: list[QPointF] = []
        span = max(1, len(self.trend_points) - 1)
        for index, (_, value) in enumerate(self.trend_points):
            x = plot.left() + plot.width() * index / span if len(self.trend_points) > 1 else plot.center().x()
            y = plot.bottom() - plot.height() * value / max_value
            coordinates.append(QPointF(x, y))

        if coordinates:
            area = QPainterPath(coordinates[0])
            for point in coordinates[1:]:
                area.lineTo(point)
            area.lineTo(QPointF(coordinates[-1].x(), plot.bottom()))
            area.lineTo(QPointF(coordinates[0].x(), plot.bottom()))
            area.closeSubpath()
            gradient = QLinearGradient(plot.topLeft(), plot.bottomLeft())
            top_fill = QColor("#7DD3FC")
            top_fill.setAlpha(72)
            bottom_fill = QColor("#A7F3D0")
            bottom_fill.setAlpha(8)
            gradient.setColorAt(0, top_fill)
            gradient.setColorAt(1, bottom_fill)
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(area)

            line = QPainterPath(coordinates[0])
            for point in coordinates[1:]:
                line.lineTo(point)
            painter.setPen(QPen(QColor("#7DD3FC"), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(line)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ECFEFF"))
            for point in coordinates:
                painter.drawEllipse(point, 3.2, 3.2)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#9EB5C8"))
        start_label = self.trend_points[0][0].strftime("%m-%d")
        end_label = self.trend_points[-1][0].strftime("%m-%d")
        painter.drawText(QRectF(plot.left(), plot.bottom() + 7, 72, 18), Qt.AlignLeft, start_label)
        painter.drawText(QRectF(plot.right() - 72, plot.bottom() + 7, 72, 18), Qt.AlignRight, end_label)
        painter.drawText(QRectF(outer.left(), outer.top(), 46, 18), Qt.AlignLeft, str(max_value))


class DeadlineOutcomeChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.outcome_counts = {"on_time": 0, "overdue": 0, "no_deadline": 0}
        self.setObjectName("historyDeadlineOutcomeChart")
        self.setAccessibleName("准时与超时分布图")
        self.setMinimumHeight(126)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_counts(self, *, on_time: int, overdue: int, no_deadline: int) -> None:
        self.outcome_counts = {
            "on_time": max(0, int(on_time)),
            "overdue": max(0, int(overdue)),
            "no_deadline": max(0, int(no_deadline)),
        }
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(10, 8, -10, -8)
        if rect.isEmpty():
            return
        total = sum(self.outcome_counts.values())
        deadline_total = self.outcome_counts["on_time"] + self.outcome_counts["overdue"]
        rate = round(self.outcome_counts["on_time"] / deadline_total * 100) if deadline_total else 0

        font = painter.font()
        font.setBold(True)
        font.setPointSize(18)
        painter.setFont(font)
        painter.setPen(QColor("#ECFEFF"))
        painter.drawText(QRectF(rect.left(), rect.top(), 78, 30), Qt.AlignLeft | Qt.AlignVCenter, f"{rate}%")
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#9EB5C8"))
        painter.drawText(QRectF(rect.left() + 80, rect.top() + 7, rect.width() - 80, 20), Qt.AlignLeft, "准时率")

        bar_rect = QRectF(rect.left(), rect.top() + 44, rect.width(), 14)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#111D2C"))
        painter.drawRoundedRect(bar_rect, 7, 7)
        if total:
            cursor = bar_rect.left()
            segments = (
                ("on_time", "#A7F3D0"),
                ("overdue", "#FCA5A5"),
                ("no_deadline", "#617086"),
            )
            for key, color in segments:
                value = self.outcome_counts[key]
                if not value:
                    continue
                width = bar_rect.width() * value / total
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(QRectF(cursor, bar_rect.top(), width, bar_rect.height()), 7, 7)
                cursor += width

        legend = (
            ("准时", self.outcome_counts["on_time"], "#A7F3D0"),
            ("超时", self.outcome_counts["overdue"], "#FCA5A5"),
            ("无截止", self.outcome_counts["no_deadline"], "#9AA4B8"),
        )
        legend_top = bar_rect.bottom() + 11
        for index, (label, value, color) in enumerate(legend):
            x = rect.left() + index * rect.width() / 3
            painter.setBrush(QColor(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(x, legend_top + 4, 18, 7), 3.5, 3.5)
            painter.setPen(QColor("#D8E8F5"))
            painter.drawText(QRectF(x + 24, legend_top - 2, rect.width() / 3 - 28, 22), Qt.AlignLeft, f"{label} {value}")


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

        title = QLabel(f"{priority_display_label(task.priority)} · {task.title}")
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
        self._history_column_count = 1
        self._normal_geometry_before_fullscreen: QRect | None = None
        self.setWindowTitle("历史任务")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setMinimumSize(960, 900)
        self.resize(1120, 920)
        self.setStyleSheet(_history_window_style())
        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self.title_bar = DialogTitleBar(self, self.windowTitle())
        self.title_bar.setObjectName("historyDragTitleBar")
        self.title_bar.setMinimumHeight(46)
        self.title_bar.setToolTip("按住此区域拖动历史窗口")
        self.title_bar.layout.setContentsMargins(10, 4, 6, 4)
        self.title_bar.layout.setSpacing(8)
        self.title_bar.setStyleSheet(_history_title_bar_style())
        self.fullscreen_button = self.title_bar.add_action_button("□", "全屏历史窗口", self.toggle_fullscreen)
        self.fullscreen_button.setObjectName("historyFullscreenButton")
        root.addWidget(self.title_bar)

        header_panel = QFrame()
        header_panel.setObjectName("historyHeaderPanel")
        header_layout = QHBoxLayout(header_panel)
        header_layout.setContentsMargins(12, 8, 12, 8)
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

        content_scroll = QScrollArea()
        content_scroll.setObjectName("historyContentScroll")
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.NoFrame)
        content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content_scroll.setStyleSheet("QScrollArea#historyContentScroll { background: transparent; border: none; }")
        content_scroll.viewport().setAutoFillBackground(False)
        content_scroll.viewport().setStyleSheet("background: transparent;")
        self.history_content_scroll = content_scroll
        self.history_content = QWidget()
        self.history_content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(self.history_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        self.history_content_layout = content_layout
        content_scroll.setWidget(self.history_content)
        root.addWidget(content_scroll, 1)

        stats_panel = QFrame()
        stats_panel.setObjectName("historyStatsPanel")
        stats_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        stats_panel.setFixedHeight(320)
        self.stats_panel = stats_panel
        stats_layout = QVBoxLayout(stats_panel)
        stats_layout.setContentsMargins(9, 6, 9, 7)
        stats_layout.setSpacing(6)
        metrics_panel = QFrame()
        metrics_panel.setObjectName("historyMetricsPanel")
        metrics_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_metrics_panel = metrics_panel
        metric_strip = QHBoxLayout(metrics_panel)
        metric_strip.setContentsMargins(8, 4, 8, 4)
        metric_strip.setSpacing(6)
        self.priority_p1_label = self._metric_label(f"{priority_display_label('P1')}：0", "historyPriorityMetricP1")
        self.priority_p2_label = self._metric_label(f"{priority_display_label('P2')}：0", "historyPriorityMetricP2")
        self.priority_p3_label = self._metric_label(f"{priority_display_label('P3')}：0", "historyPriorityMetricP3")
        self.priority_mix_label = self.priority_p1_label
        self.review_metric_label = self._metric_label("复盘 0/0")
        self.on_time_metric_label = self._metric_label("准时率 --")
        self.overdue_metric_label = self._metric_label("超时 0/0", "historyOverdueMetric")
        self.average_metric_label = self._metric_label("平均进度 --")
        self.latest_metric_label = self._metric_label("最近 --")
        for metric in (
            self.priority_p1_label,
            self.priority_p2_label,
            self.priority_p3_label,
            self.review_metric_label,
            self.on_time_metric_label,
            self.overdue_metric_label,
            self.average_metric_label,
            self.latest_metric_label,
        ):
            metric.setMinimumWidth(0)
            metric.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            metric_strip.addWidget(metric, 1)
        stats_layout.addWidget(metrics_panel)

        analytics_panel = QFrame()
        analytics_panel.setObjectName("historyAnalyticsPanel")
        analytics_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_analytics_panel = analytics_panel
        analytics_range = QHBoxLayout(analytics_panel)
        analytics_range.setContentsMargins(8, 4, 8, 4)
        analytics_range.setSpacing(7)
        analytics_title = QLabel("统计区间")
        analytics_title.setObjectName("historyAnalyticsTitle")
        analytics_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        analytics_title.setFixedHeight(32)
        analytics_range.addWidget(analytics_title)
        self.analytics_count_label = QLabel("0 条")
        self.analytics_count_label.setObjectName("historyAnalyticsCount")
        self.analytics_count_label.setAlignment(Qt.AlignCenter)
        self.analytics_count_label.setFixedHeight(32)
        self.analytics_count_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        analytics_range.addWidget(self.analytics_count_label)
        analytics_range.addStretch(1)
        self.analytics_all_button = self._range_preset_button(
            "全部",
            "统计全部完成记录",
            "historyAnalyticsPresetButton",
        )
        self.analytics_week_button = self._range_preset_button(
            "近7日",
            "只统计最近 7 天完成记录",
            "historyAnalyticsPresetButton",
        )
        self.analytics_month_button = self._range_preset_button(
            "本月",
            "只统计当前月份完成记录",
            "historyAnalyticsPresetButton",
        )
        self.analytics_all_button.clicked.connect(lambda checked=False: self._apply_analytics_preset("all"))
        self.analytics_week_button.clicked.connect(lambda checked=False: self._apply_analytics_preset("week"))
        self.analytics_month_button.clicked.connect(lambda checked=False: self._apply_analytics_preset("month"))
        for preset_button in (self.analytics_all_button, self.analytics_week_button, self.analytics_month_button):
            analytics_range.addWidget(preset_button)
        self.analytics_start_date = self._date_edit(
            "historyAnalyticsStartDate",
            "historyAnalyticsStartCalendar",
            "选择统计图表的起始完成日期",
            "统计起始日期",
        )
        self.analytics_start_date_chip = _date_chip("起始", self.analytics_start_date)
        analytics_range.addWidget(self.analytics_start_date_chip, 1)
        analytics_to_label = QLabel("→")
        analytics_to_label.setObjectName("historyAnalyticsArrow")
        analytics_to_label.setAlignment(Qt.AlignCenter)
        analytics_to_label.setFixedHeight(32)
        analytics_range.addWidget(analytics_to_label)
        self.analytics_end_date = self._date_edit(
            "historyAnalyticsEndDate",
            "historyAnalyticsEndCalendar",
            "选择统计图表的结束完成日期",
            "统计结束日期",
        )
        self.analytics_end_date_chip = _date_chip("结束", self.analytics_end_date)
        analytics_range.addWidget(self.analytics_end_date_chip, 1)
        stats_layout.addWidget(analytics_panel)

        charts_panel = QFrame()
        charts_panel.setObjectName("historyChartsPanel")
        charts_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_charts_panel = charts_panel
        chart_grid = QGridLayout(charts_panel)
        chart_grid.setContentsMargins(0, 0, 0, 0)
        chart_grid.setHorizontalSpacing(8)
        chart_grid.setVerticalSpacing(8)
        self.priority_donut_chart = PriorityDonutChart()
        self.completion_trend_chart = CompletionTrendChart()
        self.deadline_outcome_chart = DeadlineOutcomeChart()
        chart_grid.addWidget(
            self._chart_card("优先级结构", "高 / 中 / 低 完成占比", self.priority_donut_chart, "priority"),
            0,
            0,
        )
        chart_grid.addWidget(
            self._chart_card("完成曲线", "最近完成节奏", self.completion_trend_chart, "trend"),
            0,
            1,
        )
        chart_grid.addWidget(
            self._chart_card("超时分布", "准时、超时与无截止", self.deadline_outcome_chart, "deadline"),
            0,
            2,
        )
        chart_grid.setColumnStretch(0, 1)
        chart_grid.setColumnStretch(1, 1)
        chart_grid.setColumnStretch(2, 1)
        stats_layout.addWidget(charts_panel)
        content_layout.addWidget(stats_panel)

        toolbar_panel = QFrame()
        toolbar_panel.setObjectName("historyToolbar")
        toolbar_layout = QVBoxLayout(toolbar_panel)
        toolbar_layout.setContentsMargins(6, 6, 6, 6)
        toolbar_layout.setSpacing(6)

        search_panel = QFrame()
        search_panel.setObjectName("historySearchPanel")
        search_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.history_search_panel = search_panel
        search_row = QHBoxLayout(search_panel)
        search_row.setContentsMargins(8, 5, 8, 5)
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("historySearch")
        self.search_input.setPlaceholderText("按任务名称搜索")
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
        self.page_size_input.setValue(8)
        self.page_size_input.setSuffix(" 条")
        self.page_size_input.setToolTip("右侧 ↑ 增加每页条数，↓ 减少每页条数")
        self.page_size_input.valueChanged.connect(self._reset_page)
        search_row.addWidget(self.page_size_input)

        export_panel = QFrame()
        export_panel.setObjectName("historyExportPanel")
        export_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        export_panel_layout = QVBoxLayout(export_panel)
        export_panel_layout.setContentsMargins(8, 6, 8, 6)
        export_panel_layout.setSpacing(5)
        export_header = QHBoxLayout()
        export_header.setContentsMargins(0, 0, 0, 0)
        export_header.setSpacing(8)
        export_range_label = QLabel("导出区间")
        export_range_label.setObjectName("historyExportTitle")
        export_header.addWidget(export_range_label)
        self.export_count_label = QLabel("0 条")
        self.export_count_label.setObjectName("historyExportCount")
        self.export_count_label.setAlignment(Qt.AlignCenter)
        export_header.addWidget(self.export_count_label)
        export_header.addStretch(1)
        self.export_all_button = self._export_preset_button("全部", "导出全部完成记录")
        self.export_week_button = self._export_preset_button("近7日", "快速选择最近 7 天")
        self.export_month_button = self._export_preset_button("本月", "快速选择当前月份")
        self.export_all_button.clicked.connect(lambda checked=False: self._apply_export_preset("all"))
        self.export_week_button.clicked.connect(lambda checked=False: self._apply_export_preset("week"))
        self.export_month_button.clicked.connect(lambda checked=False: self._apply_export_preset("month"))
        for preset_button in (self.export_all_button, self.export_week_button, self.export_month_button):
            export_header.addWidget(preset_button)
        export_panel_layout.addLayout(export_header)

        export_row = QHBoxLayout()
        export_row.setContentsMargins(0, 0, 0, 0)
        export_row.setSpacing(8)
        self.export_start_date = QDateEdit()
        self.export_start_date.setObjectName("historyExportStartDate")
        self.export_start_date.setCalendarPopup(True)
        apply_dark_calendar_popup(self.export_start_date, "historyExportStartCalendar")
        self.export_start_date.setDisplayFormat("yyyy-MM-dd")
        self.export_start_date.setToolTip("选择 CSV 导出的起始完成日期")
        self.export_start_date.setAccessibleName("导出起始日期")
        export_row.addWidget(_export_date_chip("起始", self.export_start_date), 1)
        export_to_label = QLabel("→")
        export_to_label.setObjectName("historyExportArrow")
        export_to_label.setAlignment(Qt.AlignCenter)
        export_row.addWidget(export_to_label)
        self.export_end_date = QDateEdit()
        self.export_end_date.setObjectName("historyExportEndDate")
        self.export_end_date.setCalendarPopup(True)
        apply_dark_calendar_popup(self.export_end_date, "historyExportEndCalendar")
        self.export_end_date.setDisplayFormat("yyyy-MM-dd")
        self.export_end_date.setToolTip("选择 CSV 导出的结束完成日期")
        self.export_end_date.setAccessibleName("导出结束日期")
        export_row.addWidget(_export_date_chip("结束", self.export_end_date), 1)
        self.export_button = QPushButton("导出 CSV")
        self.export_button.setObjectName("historyExportButton")
        self.export_button.setToolTip("导出当前搜索结果中日期范围内的历史记录表格")
        self.export_button.clicked.connect(self.export_history)
        export_row.addWidget(self.export_button)
        export_panel_layout.addLayout(export_row)
        toolbar_layout.addWidget(search_panel)
        toolbar_layout.addWidget(export_panel)
        content_layout.addWidget(toolbar_panel)
        self._configure_analytics_date_range()
        self._configure_export_date_range()
        self.analytics_start_date.dateChanged.connect(self._render)
        self.analytics_end_date.dateChanged.connect(self._render)
        self.export_start_date.dateChanged.connect(self._update_export_count)
        self.export_end_date.dateChanged.connect(self._update_export_count)

        self.date_pager_widget = QFrame()
        self.date_pager_widget.setObjectName("historyPagerPanel")
        date_pager_layout = QHBoxLayout(self.date_pager_widget)
        date_pager_layout.setContentsMargins(8, 5, 8, 5)
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
        content_layout.addWidget(self.date_pager_widget)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.list_layout = QGridLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setHorizontalSpacing(10)
        self.list_layout.setVerticalSpacing(10)

        scroll = QScrollArea()
        scroll.setObjectName("historyRecordsPanel")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setViewportMargins(8, 8, 8, 8)
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            " stop:0 #111C3F, stop:0.34 #182252, stop:0.68 #073B4C, stop:1 #073B2D);"
        )
        scroll.setWidget(self.container)
        scroll.setMinimumHeight(160)
        self.history_scroll_area = scroll
        self.history_records_panel = scroll
        content_layout.addWidget(scroll, 1)

        resize_row = QHBoxLayout()
        resize_row.setContentsMargins(0, 0, 0, 0)
        resize_row.addStretch(1)
        self.history_resize_grip = QSizeGrip(self)
        self.history_resize_grip.setToolTip("拖动调整历史窗口大小")
        resize_row.addWidget(self.history_resize_grip)
        root.addLayout(resize_row)
        self._render()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "history_scroll_area") or not hasattr(self, "list_layout"):
            return
        next_columns = self._history_grid_columns()
        if next_columns != self._history_column_count:
            self._render()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            if self._normal_geometry_before_fullscreen is not None:
                self.setGeometry(self._normal_geometry_before_fullscreen)
            self.fullscreen_button.setText("□")
            self.fullscreen_button.setToolTip("全屏历史窗口")
            return
        self._normal_geometry_before_fullscreen = QRect(self.geometry())
        self.fullscreen_button.setText("▣")
        self.fullscreen_button.setToolTip("还原历史窗口")
        self.showFullScreen()

    def _metric_label(self, text: str, object_name: str = "historyMetricChip") -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignCenter)
        label.setFixedHeight(28)
        label.setWordWrap(False)
        label.setToolTip(text)
        return label

    def _chart_card(self, title: str, subtitle: str, chart: QWidget, tone: str = "neutral") -> QFrame:
        card = QFrame()
        card.setObjectName("historyChartCard")
        card.setProperty("historyTone", tone)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setFixedHeight(178)
        apply_soft_shadow(card, blur=22, y_offset=8, alpha=80)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(9, 6, 9, 6)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("historyChartTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("historyChartSubtitle")
        subtitle_label.setWordWrap(False)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(chart, 1)
        return card

    def _date_edit(self, object_name: str, calendar_name: str, tooltip: str, accessible_name: str) -> QDateEdit:
        edit = QDateEdit()
        edit.setObjectName(object_name)
        edit.setCalendarPopup(True)
        apply_dark_calendar_popup(edit, calendar_name)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setToolTip(tooltip)
        edit.setAccessibleName(accessible_name)
        edit.setFixedHeight(30)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return edit

    def _range_preset_button(self, text: str, tooltip: str, object_name: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(30)
        return button

    def _export_preset_button(self, text: str, tooltip: str) -> QPushButton:
        return self._range_preset_button(text, tooltip, "historyExportPresetButton")

    def _completed_date_bounds(self) -> tuple[date, date]:
        dates = [_task_completed_date(task) for task in self.tasks if task.status == "done"]
        dates = [item for item in dates if item is not None]
        if dates:
            return min(dates), max(dates)
        today = QDate.currentDate().toPython()
        return today, today

    def _configure_date_range(self, start_edit: QDateEdit, end_edit: QDateEdit) -> tuple[date, date]:
        start, end = self._completed_date_bounds()
        start_qdate = QDate(start.year, start.month, start.day)
        end_qdate = QDate(end.year, end.month, end.day)
        for edit, value in ((start_edit, start_qdate), (end_edit, end_qdate)):
            edit.setDateRange(start_qdate, end_qdate)
            edit.setDate(value)
        return start, end

    def _configure_export_date_range(self) -> None:
        start, end = self._configure_date_range(self.export_start_date, self.export_end_date)
        self._export_min_date = start
        self._export_max_date = end
        self._update_export_count()

    def _configure_analytics_date_range(self) -> None:
        start, end = self._configure_date_range(self.analytics_start_date, self.analytics_end_date)
        self._analytics_min_date = start
        self._analytics_max_date = end
        self._update_analytics_count()

    def _apply_date_preset(
        self,
        preset: str,
        *,
        start_edit: QDateEdit,
        end_edit: QDateEdit,
        min_date: date,
        max_date: date,
    ) -> None:
        end = max_date
        if preset == "week":
            start = max(min_date, end - timedelta(days=6))
        elif preset == "month":
            start = max(min_date, date(end.year, end.month, 1))
        else:
            start = min_date
        start_edit.setDate(QDate(start.year, start.month, start.day))
        end_edit.setDate(QDate(end.year, end.month, end.day))

    def _apply_analytics_preset(self, preset: str) -> None:
        min_date = getattr(self, "_analytics_min_date", QDate.currentDate().toPython())
        max_date = getattr(self, "_analytics_max_date", QDate.currentDate().toPython())
        self._apply_date_preset(
            preset,
            start_edit=self.analytics_start_date,
            end_edit=self.analytics_end_date,
            min_date=min_date,
            max_date=max_date,
        )
        self._render()

    def _apply_export_preset(self, preset: str) -> None:
        min_date = getattr(self, "_export_min_date", QDate.currentDate().toPython())
        max_date = getattr(self, "_export_max_date", QDate.currentDate().toPython())
        self._apply_date_preset(
            preset,
            start_edit=self.export_start_date,
            end_edit=self.export_end_date,
            min_date=min_date,
            max_date=max_date,
        )
        self._update_export_count()

    def _update_export_count(self, *args) -> None:
        if not hasattr(self, "export_count_label"):
            return
        self.export_count_label.setText(f"{len(self._exportable_tasks())} 条")

    def _update_analytics_count(self, tasks: list[Task] | None = None) -> None:
        if not hasattr(self, "analytics_count_label"):
            return
        analytics_tasks = tasks if tasks is not None else self._analytics_tasks()
        self.analytics_count_label.setText(f"{len(analytics_tasks)} 条")

    def _render(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row in range(self.list_layout.rowCount()):
            self.list_layout.setRowStretch(row, 0)
        completed = self._filtered_completed_tasks()
        self.count_label.setText(f"{len(completed)} 条")
        analytics_completed = self._analytics_tasks(completed)
        self._update_metrics(analytics_completed)
        self._update_analytics_count(analytics_completed)
        self._update_export_count()
        if not completed:
            self._set_date_pager([], None)
            query = self.search_input.text().strip()
            empty = QLabel("没有匹配的完成记录" if query else "还没有完成记录")
            empty.setStyleSheet(f"color: {THEME_COLORS['border']};")
            self.list_layout.addWidget(empty, 0, 0)
            animate_content_swap(self.container)
            return
        columns = self._history_grid_columns()
        self._history_column_count = columns
        for column in range(3):
            self.list_layout.setColumnStretch(column, 1 if column < columns else 0)
        row = 0
        groups = self._group_completed_tasks(completed)
        if self.group_mode.currentText() == "按日期":
            group_title, tasks = self._selected_date_group(groups)
            self._clamp_selected_page(tasks)
            self._set_date_pager(groups, group_title)
            row = self._add_history_group(row, group_title, self._page_tasks(tasks), len(tasks), columns)
        else:
            self._clamp_selected_page(completed)
            self._set_level_pager(completed)
            for group_title, tasks, total_count in self._paged_group_slices(groups):
                row = self._add_history_group(row, group_title, tasks, total_count, columns)
        self.list_layout.setRowStretch(row, 1)
        animate_content_swap(self.container)

    def _history_grid_columns(self) -> int:
        viewport_width = self.history_scroll_area.viewport().width() if hasattr(self, "history_scroll_area") else 0
        width = max(viewport_width, self.width() - 72)
        if width >= 1360:
            return 3
        if width >= 760:
            return 2
        return 1

    def _add_history_group(
        self, row: int, group_title: str, tasks: list[Task], total_count: int, columns: int
    ) -> int:
        self.list_layout.addWidget(self._group_header(group_title, total_count), row, 0, 1, columns)
        row += 1
        for index, task in enumerate(tasks):
            self.list_layout.addWidget(self._history_card(task), row + index // columns, index % columns)
        return row + max(1, (len(tasks) + columns - 1) // columns)

    def _update_metrics(self, completed: list[Task]) -> None:
        total = len(completed)
        counts = {
            priority: sum(1 for task in completed if task.priority == priority)
            for priority in PRIORITY_ORDER
        }
        overdue = sum(1 for task in completed if _task_completed_late(task))
        no_deadline = sum(1 for task in completed if task.deadline is None)
        deadline_total = total - no_deadline
        on_time = max(0, deadline_total - overdue)
        on_time_rate = round(on_time / deadline_total * 100) if deadline_total else None
        reviewed = sum(1 for task in completed if task.notes.strip() or task.reflection.strip())
        average = round(sum(task.progress for task in completed) / total) if total else None
        latest_task = max(completed, key=lambda task: task.completed_at or task.updated_at, default=None)
        latest = (
            (latest_task.completed_at or latest_task.updated_at).astimezone().strftime("%m-%d %H:%M")
            if latest_task
            else "--"
        )
        self.priority_p1_label.setText(f"{priority_display_label('P1')}：{counts['P1']}")
        self.priority_p2_label.setText(f"{priority_display_label('P2')}：{counts['P2']}")
        self.priority_p3_label.setText(f"{priority_display_label('P3')}：{counts['P3']}")
        self.review_metric_label.setText(f"复盘 {reviewed}/{total}")
        self.on_time_metric_label.setText(f"准时率 {on_time_rate}%" if on_time_rate is not None else "准时率 --")
        self.overdue_metric_label.setText(f"超时 {overdue}/{deadline_total}")
        self.average_metric_label.setText(f"平均进度 {average}%" if average is not None else "平均进度 --")
        self.latest_metric_label.setText(f"最近 {latest}")
        self.priority_donut_chart.set_counts(counts)
        self.completion_trend_chart.set_points(_completion_trend(completed))
        self.deadline_outcome_chart.set_counts(on_time=on_time, overdue=overdue, no_deadline=no_deadline)

    def _reset_page(self, *args) -> None:
        self._selected_page_index = 0
        self._render()

    def _filtered_completed_tasks(self) -> list[Task]:
        completed = [task for task in self.tasks if task.status == "done"]
        query = self.search_input.text().strip().lower()
        if not query:
            return completed
        return [task for task in completed if query in task.title.lower()]

    def _exportable_tasks(self) -> list[Task]:
        return self._tasks_in_export_date_range(self._filtered_completed_tasks())

    def _analytics_tasks(self, tasks: list[Task] | None = None) -> list[Task]:
        source_tasks = self._filtered_completed_tasks() if tasks is None else tasks
        return self._tasks_in_date_range(source_tasks, self.analytics_start_date, self.analytics_end_date)

    def _tasks_in_export_date_range(self, tasks: list[Task]) -> list[Task]:
        return self._tasks_in_date_range(tasks, self.export_start_date, self.export_end_date)

    def _tasks_in_date_range(self, tasks: list[Task], start_edit: QDateEdit, end_edit: QDateEdit) -> list[Task]:
        start = start_edit.date().toPython()
        end = end_edit.date().toPython()
        if start > end:
            start, end = end, start
        return [task for task in tasks if _date_in_range(_task_completed_date(task), start, end)]

    def _group_completed_tasks(self, tasks: list[Task]) -> list[tuple[str, list[Task]]]:
        sorted_tasks = sorted(tasks, key=lambda item: item.completed_at or item.updated_at, reverse=True)
        groups: dict[str, list[Task]] = {}
        if self.group_mode.currentText() == "按等级":
            for task in sorted_tasks:
                groups.setdefault(task.priority, []).append(task)
            return [(priority, groups[priority]) for priority in PRIORITY_ORDER if priority in groups]

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
        is_priority = title in PRIORITY_ORDER
        display_title = priority_display_label(title) if is_priority else title
        separator = "：" if is_priority else " · "
        label = QLabel(f"{display_title}{separator}{count} 条")
        label.setObjectName("historyGroupHeader")
        return label

    def _history_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setObjectName("historyCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(188)
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

        title = QLabel(task.title)
        title.setObjectName("historyTaskTitle")
        title.setWordWrap(True)
        title.setMinimumHeight(42)
        title.setMaximumHeight(58)
        title.setToolTip(task.title)
        layout.addWidget(title)

        header = QHBoxLayout()
        header.setSpacing(8)
        priority = QLabel(f"{priority_display_label(task.priority)}：")
        priority.setObjectName(f"historyPriority{task.priority}")
        priority.setAlignment(Qt.AlignCenter)
        priority.setFixedHeight(24)
        priority.setFixedWidth(62)
        header.addWidget(priority)
        progress = QLabel(f"{task.progress}%")
        progress.setObjectName("historyProgressChip")
        progress.setAlignment(Qt.AlignCenter)
        header.addWidget(progress)
        work_elapsed = work_elapsed_seconds(task, task.completed_at or task.updated_at)
        work_target = effort_short_label(max(0, work_target_seconds(task) // 60))
        work_timer = QLabel(f"计时 {duration_clock_label(work_elapsed)} / {work_target}")
        work_timer.setObjectName("historyWorkTimerChip")
        work_timer.setAlignment(Qt.AlignCenter)
        header.addWidget(work_timer)
        review_status = QLabel("已复盘" if task.notes.strip() or task.reflection.strip() else "待补记")
        review_status.setObjectName(
            "historyReviewChipDone" if task.notes.strip() or task.reflection.strip() else "historyReviewChipEmpty"
        )
        review_status.setAlignment(Qt.AlignCenter)
        header.addWidget(review_status)
        header.addStretch(1)
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
            preview.setMinimumHeight(44)
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

    def _compact_text(self, text: str, limit: int = 120) -> str:
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
                    "优先级": priority_text(task.priority),
                    "预估工作量分钟": task.effort_minutes,
                    "实际工作时长": duration_clock_label(work_elapsed_seconds(task, task.completed_at or task.updated_at)),
                    "实际工作秒数": work_elapsed_seconds(task, task.completed_at or task.updated_at),
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


def _date_chip(label_text: str, date_edit: QDateEdit) -> QFrame:
    chip = QFrame()
    chip.setObjectName("historyExportDateChip")
    chip.setFixedHeight(38)
    chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout = QHBoxLayout(chip)
    layout.setContentsMargins(7, 4, 6, 4)
    layout.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("historyExportDateLabel")
    label.setAlignment(Qt.AlignCenter)
    label.setFixedHeight(26)
    date_edit.setFixedHeight(30)
    date_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    layout.addWidget(label)
    layout.addWidget(date_edit, 1)
    return chip


def _export_date_chip(label_text: str, date_edit: QDateEdit) -> QFrame:
    return _date_chip(label_text, date_edit)


def _export_datetime(value) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _task_completed_date(task: Task) -> date | None:
    value = task.completed_at or task.updated_at
    return value.astimezone().date() if value else None


def _task_completed_late(task: Task) -> bool:
    completed_at = task.completed_at or task.updated_at
    return bool(task.deadline and completed_at and completed_at > task.deadline)


def _completion_trend(tasks: list[Task], *, max_days: int = 14) -> list[tuple[date, int]]:
    dates = [_task_completed_date(task) for task in tasks]
    dates = [item for item in dates if item is not None]
    if not dates:
        return []
    end = max(dates)
    start = max(min(dates), end - timedelta(days=max_days - 1))
    counts: dict[date, int] = {}
    for item in dates:
        if item >= start:
            counts[item] = counts.get(item, 0) + 1
    days = (end - start).days + 1
    return [(start + timedelta(days=offset), counts.get(start + timedelta(days=offset), 0)) for offset in range(days)]


def _date_in_range(value: date | None, start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def _history_title_bar_style() -> str:
    return """
QFrame#historyDragTitleBar {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #080D1A,
    stop:0.52 #0D1730,
    stop:1 #132033);
  border: none;
  border-radius: 8px;
}
QFrame#historyDragTitleBar QLabel {
  color: #F8FBFF;
  font-size: 16px;
  font-weight: 900;
}
QFrame#historyDragTitleBar QPushButton {
  color: #F6FBFF;
  background: #151D31;
  border: none;
  border-radius: 8px;
  min-height: 34px;
  font-weight: 900;
}
QFrame#historyDragTitleBar QPushButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1B2A44,
    stop:1 #16364C);
}
QFrame#historyDragTitleBar QPushButton:pressed {
  background: #0E1728;
}
"""


def _history_window_style() -> str:
    return f"""
QFrame#historyHeaderPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0B1A2C,
    stop:0.46 #102C3D,
    stop:1 #0D3A31);
  border: none;
  border-radius: 8px;
}}
QLabel#historyTitle {{
  color: #F8FBFF;
  font-size: 20px;
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
  min-height: 30px;
  font-size: 15px;
  font-weight: 900;
}}
QFrame#historyStatsPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #061226,
    stop:0.34 #101A3B,
    stop:0.68 #063442,
    stop:1 #0A3E32);
  border: none;
  border-radius: 8px;
}}
QFrame#historyMetricsPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #15102E,
    stop:0.36 #0D2D4E,
    stop:0.72 #0F3B3D,
    stop:1 #2A2B12);
  border: none;
  border-radius: 8px;
}}
QFrame#historyAnalyticsPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #052C55,
    stop:0.34 #073E63,
    stop:0.7 #075E59,
    stop:1 #134E2B);
  border: none;
  border-radius: 8px;
}}
QFrame#historyChartsPanel {{
  background: transparent;
  border: none;
}}
QLabel#historyMetricChip,
QLabel#historyPriorityMetricP1,
QLabel#historyPriorityMetricP2,
QLabel#historyPriorityMetricP3,
QLabel#historyOverdueMetric {{
  color: #D4E3F2;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #17203B,
    stop:0.55 #12334E,
    stop:1 #0F3C43);
  border: none;
  border-radius: 8px;
  font-weight: 900;
  font-size: 12px;
  padding: 0 6px;
}}
QLabel#historyPriorityMetricP1 {{
  color: #FFE1A6;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6B2E12, stop:1 #9A4C14);
}}
QLabel#historyPriorityMetricP2 {{
  color: #DCE7FF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #20367E, stop:1 #3657B7);
}}
QLabel#historyPriorityMetricP3 {{
  color: #D9FBE8;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0D4A3D, stop:1 #15805C);
}}
QLabel#historyOverdueMetric {{
  color: #FFD5DF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #51172A, stop:1 #8B1D35);
}}
QLabel#historyAnalyticsTitle {{
  color: #F8FBFF;
  font-size: 14px;
  font-weight: 900;
  padding: 0 2px;
}}
QLabel#historyAnalyticsCount {{
  color: #ECFEFF;
  background: #123047;
  border: none;
  border-radius: 8px;
  min-width: 54px;
  min-height: 24px;
  font-weight: 900;
  font-size: 13px;
}}
QPushButton#historyAnalyticsPresetButton {{
  color: #BDEAFE;
  background: #101827;
  border: none;
  border-radius: 8px;
  min-height: 26px;
  padding: 3px 9px;
  font-weight: 900;
}}
QPushButton#historyAnalyticsPresetButton:hover {{
  color: #ECFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #14304A,
    stop:1 #135E58);
}}
QLabel#historyAnalyticsArrow {{
  color: #A7F3D0;
  min-width: 22px;
  font-size: 17px;
  font-weight: 900;
}}
QFrame#historyChartCard {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #0D1624,
    stop:0.58 #0F1D2E,
    stop:1 #102A2D);
  border: none;
  border-radius: 8px;
}}
QFrame#historyChartCard[historyTone="priority"] {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #3A1608,
    stop:0.45 #71310F,
    stop:1 #5B1A2A);
}}
QFrame#historyChartCard[historyTone="trend"] {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #04235C,
    stop:0.52 #075985,
    stop:1 #0E7490);
}}
QFrame#historyChartCard[historyTone="deadline"] {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #3B0A38,
    stop:0.5 #831843,
    stop:1 #92400E);
}}
QLabel#historyChartTitle {{
  color: #F8FBFF;
  font-size: 14px;
  font-weight: 900;
}}
QLabel#historyChartSubtitle {{
  color: #8EA2B7;
  font-size: 12px;
  font-weight: 700;
}}
QFrame#historyToolbar {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0B1534,
    stop:0.34 #17204A,
    stop:0.66 #073B46,
    stop:1 #112F20);
  border: none;
  border-radius: 8px;
  padding: 7px;
}}
QFrame#historySearchPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #25135C,
    stop:0.42 #16408A,
    stop:1 #0E6C82);
  border: none;
  border-radius: 8px;
}}
QLabel#historyToolbarLabel {{
  color: #BFD0E2;
  font-weight: 900;
  padding: 0 4px;
}}
QFrame#historyExportPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0A4A55,
    stop:0.38 #0F766E,
    stop:0.72 #365314,
    stop:1 #713F12);
  border: none;
  border-radius: 8px;
}}
QLabel#historyExportTitle {{
  color: #F8FBFF;
  font-size: 15px;
  font-weight: 900;
}}
QLabel#historyExportCount {{
  color: #DFFBFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #155E75,
    stop:1 #047857);
  border: none;
  border-radius: 8px;
  min-width: 54px;
  min-height: 28px;
  font-weight: 900;
}}
QPushButton#historyExportPresetButton {{
  color: #BAE6FD;
  background: #101827;
  border: none;
  border-radius: 8px;
  min-height: 26px;
  padding: 3px 10px;
  font-weight: 900;
}}
QPushButton#historyExportPresetButton:hover {{
  color: #ECFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #123047,
    stop:1 #115E59);
}}
QFrame#historyExportDateChip {{
  background: #092433;
  border: none;
  border-radius: 8px;
}}
QLabel#historyExportDateLabel {{
  color: #B9F7E8;
  background: #104050;
  border: none;
  border-radius: 7px;
  min-width: 42px;
  min-height: 24px;
  font-weight: 900;
}}
QLabel#historyExportArrow {{
  color: #A7F3D0;
  min-width: 24px;
  font-size: 18px;
  font-weight: 900;
}}
QLineEdit#historySearch, QComboBox#historyMode, QComboBox#historyDateSelector,
QDateEdit#historyExportStartDate, QDateEdit#historyExportEndDate,
QDateEdit#historyAnalyticsStartDate, QDateEdit#historyAnalyticsEndDate {{
  background: #121A2B;
  color: #ECFEFF;
  font-weight: 700;
  font-size: 13px;
  min-width: 112px;
}}
QLabel#historyPageLabel {{
  color: #7DD3FC;
  background: #0C1724;
  border: none;
  border-radius: 8px;
  padding: 7px 12px;
  font-weight: 900;
}}
QFrame#historyPagerPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #38135F,
    stop:0.34 #1E3A8A,
    stop:0.68 #0E7490,
    stop:1 #047857);
  border: none;
  border-radius: 8px;
}}
QScrollArea#historyRecordsPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #111C3F,
    stop:0.34 #182252,
    stop:0.68 #073B4C,
    stop:1 #073B2D);
  border: none;
  border-radius: 8px;
}}
QPushButton#historyPageButton, QPushButton#historyNoteButton, QPushButton#historyExportButton {{
  background: #162033;
  color: #F6F8FC;
  font-weight: 800;
}}
QPushButton#historyExportButton {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #155E75,
    stop:1 #0F766E);
  color: #ECFEFF;
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
  font-size: 17px;
  font-weight: 900;
  background: #0A121E;
  border: none;
  border-radius: 8px;
  padding: 6px 8px;
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
QLabel#historyWorkTimerChip {{
  color: #E0F2FE;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1D4ED8,
    stop:0.55 #0E7490,
    stop:1 #047857);
  border: none;
  border-radius: 8px;
  min-width: 118px;
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
  font-size: 13px;
}}
QLabel#historyPreview {{
  color: #C4D2E2;
  background: #0C1421;
  border: none;
  border-radius: 8px;
  padding: 10px 10px;
  font-size: 14px;
  line-height: 20px;
  font-weight: 600;
}}
"""
