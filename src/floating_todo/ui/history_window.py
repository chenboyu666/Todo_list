from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, QDate, QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import DEFAULT_TASK_TAG, Task, normalize_task_tag, work_elapsed_seconds, work_target_seconds
from floating_todo.ui.history_graph import build_history_graph_payload, render_history_graph_html
from floating_todo.ui.date_controls import NoWheelComboBox, NoWheelDateEdit, NoWheelSpinBox, apply_dark_calendar_popup
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
    "标签",
    "优先级",
    "预计工作量分钟",
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

PRIORITY_ICON_NAMES = {
    "P1": "priority-high.svg",
    "P2": "priority-medium.svg",
    "P3": "priority-low.svg",
}

TAG_CHART_COLORS = [
    "#22D3EE",
    "#A78BFA",
    "#F6A44D",
    "#34D399",
    "#F472B6",
    "#60A5FA",
    "#FACC15",
]

STATUS_FILTERS = [
    ("全部状态", "all"),
    ("准时完成", "on_time"),
    ("超时完成", "overdue"),
    ("无截止", "no_deadline"),
    ("已复盘", "reviewed"),
    ("待补记", "needs_notes"),
]

PRIORITY_FILTERS = [
    ("全部优先级", "all"),
    ("高", "P1"),
    ("中", "P2"),
    ("低", "P3"),
]

SORT_FILTERS = [
    ("按完成时间", "completed"),
    ("按优先级", "priority"),
    ("按实际耗时", "effort"),
    ("按标题", "title"),
]

PAGE_SIZES = [8, 12, 16, 24]
UI_ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "ui"


class PriorityDonutChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.priority_counts = {priority: 0 for priority in PRIORITY_ORDER}
        self.setObjectName("historyPriorityDonutChart")
        self.setAccessibleName("优先级完成结构图")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_counts(self, counts: dict[str, int]) -> None:
        self.priority_counts = {priority: max(0, int(counts.get(priority, 0))) for priority in PRIORITY_ORDER}
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        if rect.isEmpty():
            return
        total = sum(self.priority_counts.values())
        diameter = min(96.0, rect.height() - 24, rect.width() * 0.42)
        chart_rect = QRectF(rect.left() + 6, rect.center().y() - diameter / 2, diameter, diameter)
        ring_width = max(13.0, diameter * 0.18)

        painter.setPen(QPen(QColor("#14253A"), ring_width, Qt.SolidLine, Qt.RoundCap))
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
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(chart_rect, Qt.AlignCenter, str(total))

        legend_x = chart_rect.right() + 18
        legend_y = rect.top() + 18
        font.setPointSize(10)
        painter.setFont(font)
        for index, priority in enumerate(PRIORITY_ORDER):
            chip_rect = QRectF(legend_x, legend_y + index * 28, 28, 10)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PRIORITY_CHART_COLORS[priority]))
            painter.drawRoundedRect(chip_rect, 4, 4)
            painter.setPen(QColor("#D7E5F4"))
            painter.drawText(
                QRectF(chip_rect.right() + 10, chip_rect.top() - 8, rect.right() - chip_rect.right() - 10, 26),
                Qt.AlignLeft | Qt.AlignVCenter,
                f"{priority_display_label(priority)}：{self.priority_counts[priority]} · {_ratio_text(self.priority_counts[priority], total)}",
            )


class CompletionTrendChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.trend_points: list[tuple[date, int]] = []
        self.setObjectName("historyCompletionTrendChart")
        self.setAccessibleName("每日完成曲线图")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_points(self, points: list[tuple[date, int]]) -> None:
        self.trend_points = list(points)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(10, 10, -10, -12)
        if rect.isEmpty():
            return

        painter.setPen(QPen(QColor("#16314B"), 1))
        for offset in range(4):
            y = rect.top() + rect.height() * offset / 3
            painter.drawLine(rect.left(), y, rect.right(), y)

        if not self.trend_points:
            painter.setPen(QColor("#86A3BD"))
            painter.drawText(rect, Qt.AlignCenter, "暂无趋势")
            return

        values = [value for _, value in self.trend_points]
        max_value = max(1, max(values))
        step_x = rect.width() / max(1, len(self.trend_points) - 1)
        path = QPainterPath()
        fill_path = QPainterPath()
        baseline = rect.bottom()
        for index, (_, value) in enumerate(self.trend_points):
            x = rect.left() + step_x * index
            y = baseline - (value / max_value) * max(28.0, rect.height() - 22)
            point = QPointF(x, y)
            if index == 0:
                path.moveTo(point)
                fill_path.moveTo(x, baseline)
                fill_path.lineTo(point)
            else:
                path.lineTo(point)
                fill_path.lineTo(point)
        fill_path.lineTo(rect.right(), baseline)
        fill_path.closeSubpath()

        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(34, 211, 238, 110))
        gradient.setColorAt(1.0, QColor(34, 211, 238, 10))
        painter.fillPath(fill_path, gradient)
        painter.setPen(QPen(QColor("#38BDF8"), 2.5))
        painter.drawPath(path)
        painter.setBrush(QColor("#BFF7FF"))
        painter.setPen(Qt.NoPen)
        for index, (_, value) in enumerate(self.trend_points):
            x = rect.left() + step_x * index
            y = baseline - (value / max_value) * max(28.0, rect.height() - 22)
            painter.drawEllipse(QPointF(x, y), 3.6, 3.6)


class DeadlineOutcomeChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.outcome_counts = {"on_time": 0, "overdue": 0, "no_deadline": 0}
        self.setObjectName("historyDeadlineOutcomeChart")
        self.setAccessibleName("准时与超时分布图")
        self.setMinimumHeight(140)
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
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -14)
        if rect.isEmpty():
            return
        total = max(1, sum(self.outcome_counts.values()))
        bar_rect = QRectF(rect.left(), rect.top() + 46, rect.width(), 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#14332F"))
        painter.drawRoundedRect(bar_rect, 9, 9)

        cursor = bar_rect.left()
        segments = [
            ("on_time", QColor("#A7F3D0"), "准时"),
            ("overdue", QColor("#FCA5A5"), "超时"),
            ("no_deadline", QColor("#CBD5E1"), "无截止"),
        ]
        for key, color, _ in segments:
            width = bar_rect.width() * self.outcome_counts[key] / total
            if width <= 0:
                continue
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(cursor, bar_rect.top(), width, bar_rect.height()), 9, 9)
            cursor += width

        painter.setPen(QColor("#F8FBFF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(24)
        painter.setFont(font)
        on_time_rate = round(self.outcome_counts["on_time"] / total * 100)
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width() * 0.4, 34), Qt.AlignLeft | Qt.AlignVCenter, f"{on_time_rate}%")
        font.setPointSize(11)
        painter.setFont(font)
        painter.setPen(QColor("#A6BCD0"))
        painter.drawText(QRectF(rect.left() + 96, rect.top() + 4, rect.width() - 96, 24), Qt.AlignLeft | Qt.AlignVCenter, "准时率")

        legend_y = rect.bottom() - 18
        for index, (key, color, label) in enumerate(segments):
            x = rect.left() + index * max(92, int(rect.width() / 3.2))
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, legend_y - 8, 22, 10), 5, 5)
            painter.setPen(QColor("#D7E5F4"))
            painter.drawText(QRectF(x + 30, legend_y - 13, 90, 20), Qt.AlignLeft | Qt.AlignVCenter, f"{label} {self.outcome_counts[key]}")


class TagDurationChart(QWidget):
    tag_clicked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.tag_stats: list[dict[str, object]] = []
        self._node_rects: dict[str, QRectF] = {}
        self.setObjectName("historyTagDurationChart")
        self.setAccessibleName("标签时长占比数据库图")
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    def set_stats(self, stats: list[dict[str, object]]) -> None:
        self.tag_stats = [
            {
                "tag": normalize_task_tag(stat.get("tag", DEFAULT_TASK_TAG)),
                "count": max(0, int(stat.get("count", 0))),
                "seconds": max(0, int(stat.get("seconds", 0))),
            }
            for stat in stats
        ]
        self.update()

    def node_rect_for_tag(self, tag: str) -> QRectF | None:
        return self._node_rects.get(normalize_task_tag(tag))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            position = QPointF(event.position()) if hasattr(event, "position") else QPointF(event.pos())
            for tag, node_rect in self._node_rects.items():
                if node_rect.contains(position):
                    self.tag_clicked.emit(tag)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(12, 12, -12, -12)
        self._node_rects = {}
        if rect.isEmpty():
            return

        if not self.tag_stats:
            painter.setPen(QColor("#86A3BD"))
            painter.drawText(rect, Qt.AlignCenter, "暂无标签数据")
            return

        total_seconds = max(1, sum(int(stat["seconds"]) for stat in self.tag_stats))
        total_count = sum(int(stat["count"]) for stat in self.tag_stats)

        core_rect = QRectF(rect.left(), rect.top() + 42, min(182.0, rect.width() * 0.22), rect.height() - 54)
        core_gradient = QLinearGradient(core_rect.topLeft(), core_rect.bottomRight())
        core_gradient.setColorAt(0.0, QColor("#0E7490"))
        core_gradient.setColorAt(0.55, QColor("#12335F"))
        core_gradient.setColorAt(1.0, QColor("#0B1728"))
        painter.setPen(QPen(QColor(103, 232, 249, 88), 1.4))
        painter.setBrush(QBrush(core_gradient))
        painter.drawRoundedRect(core_rect, 18, 18)

        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(QColor("#ECFEFF"))
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 24), Qt.AlignLeft | Qt.AlignVCenter, "标签关系数据库")
        font.setPointSize(18)
        painter.setFont(font)
        painter.drawText(QRectF(core_rect.left() + 16, core_rect.top() + 18, core_rect.width() - 32, 34), Qt.AlignLeft | Qt.AlignVCenter, f"{len(self.tag_stats)} 类")
        font.setPointSize(10)
        painter.setFont(font)
        painter.setPen(QColor("#BDE7F4"))
        painter.drawText(QRectF(core_rect.left() + 16, core_rect.top() + 54, core_rect.width() - 32, 22), Qt.AlignLeft | Qt.AlignVCenter, f"{total_count} 条完成记录")
        painter.drawText(QRectF(core_rect.left() + 16, core_rect.top() + 78, core_rect.width() - 32, 22), Qt.AlignLeft | Qt.AlignVCenter, "点击节点查看任务")

        anchor = QPointF(core_rect.right(), core_rect.center().y())
        nodes = self._node_layout(rect, core_rect)
        for index, (stat, node_rect) in enumerate(nodes):
            tag = str(stat["tag"])
            seconds = int(stat["seconds"])
            ratio = _ratio_text(seconds, total_seconds)
            color = QColor(_tag_chart_color(index))
            control_x = anchor.x() + (node_rect.left() - anchor.x()) * 0.48
            path = QPainterPath(anchor)
            path.cubicTo(
                QPointF(control_x, anchor.y()),
                QPointF(control_x, node_rect.center().y()),
                QPointF(node_rect.left(), node_rect.center().y()),
            )
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 138), 2.0, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

        for index, (stat, node_rect) in enumerate(nodes):
            tag = str(stat["tag"])
            seconds = int(stat["seconds"])
            count = int(stat["count"])
            ratio = _ratio_text(seconds, total_seconds)
            duration = duration_clock_label(seconds)
            color = QColor(_tag_chart_color(index))
            node_gradient = QLinearGradient(node_rect.topLeft(), node_rect.bottomRight())
            node_gradient.setColorAt(0.0, QColor(8, 21, 34, 232))
            node_gradient.setColorAt(0.58, QColor(color.red(), color.green(), color.blue(), 88))
            node_gradient.setColorAt(1.0, QColor(8, 21, 34, 218))
            painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 164), 1.6))
            painter.setBrush(QBrush(node_gradient))
            painter.drawRoundedRect(node_rect, 16, 16)
            self._node_rects[tag] = QRectF(node_rect)

            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(node_rect.left() + 18, node_rect.top() + 18), 6, 6)

            painter.setPen(QColor("#F8FBFF"))
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(QRectF(node_rect.left() + 34, node_rect.top() + 7, node_rect.width() - 44, 22), Qt.AlignLeft | Qt.AlignVCenter, tag)
            painter.setPen(QColor("#B9CCE0"))
            font.setBold(False)
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(QRectF(node_rect.left() + 16, node_rect.top() + 34, node_rect.width() - 32, 18), Qt.AlignLeft | Qt.AlignVCenter, f"{count} 条 · {duration}")
            painter.setPen(QColor("#DDFBFF"))
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(QRectF(node_rect.right() - 56, node_rect.top() + 8, 42, 22), Qt.AlignRight | Qt.AlignVCenter, ratio)

    def _node_layout(self, rect: QRectF, core_rect: QRectF) -> list[tuple[dict[str, object], QRectF]]:
        stats = self.tag_stats[:6]
        available_left = core_rect.right() + 38
        available_width = max(180.0, rect.right() - available_left)
        node_width = max(150.0, min(220.0, available_width / 2 - 10))
        node_height = 62.0
        row_gap = 14.0
        col_gap = 18.0
        rows = 2 if len(stats) > 3 else 1
        top = rect.top() + 48 if rows == 1 else rect.top() + 42
        nodes: list[tuple[dict[str, object], QRectF]] = []
        for index, stat in enumerate(stats):
            row = index % rows
            col = index // rows
            x = available_left + col * (node_width + col_gap)
            y = top + row * (node_height + row_gap)
            if x + node_width > rect.right():
                x = rect.right() - node_width
            nodes.append((stat, QRectF(x, y, node_width, node_height)))
        return nodes


class HistoryNoteDialog(QDialog):
    def __init__(self, task: Task, parent=None) -> None:
        super().__init__(parent)
        self.task = task
        self.setWindowTitle("编辑历史备注")
        self.setMinimumSize(540, 420)
        self.setStyleSheet(
            """
QDialog {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #04111E,
    stop:1 #0A2335);
}
QFrame#historyNotePanel {
  background: rgba(8, 26, 43, 0.92);
  border: 1px solid rgba(98, 144, 176, 42);
  border-radius: 16px;
}
QLabel {
  color: #F8FBFF;
  font-weight: 800;
}
QTextEdit {
  background: #091422;
  color: #ECFEFF;
  border: 1px solid rgba(110, 156, 184, 40);
  border-radius: 12px;
  padding: 10px;
}
QDialogButtonBox QPushButton {
  min-width: 108px;
  min-height: 38px;
  border-radius: 12px;
  font-weight: 900;
}
"""
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        panel = QFrame()
        panel.setObjectName("historyNotePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(task.title)
        title.setStyleSheet("font-size: 18px; font-weight: 900;")
        title.setWordWrap(True)
        layout.addWidget(title)

        notes_label = QLabel("任务备注")
        layout.addWidget(notes_label)
        self.notes_edit = QTextEdit(task.notes)
        self.notes_edit.setPlaceholderText("记录任务背景、上下文或补充说明")
        self.notes_edit.setMinimumHeight(100)
        layout.addWidget(self.notes_edit)

        reflection_label = QLabel("完成体会")
        layout.addWidget(reflection_label)
        self.reflection_edit = QTextEdit(task.reflection)
        self.reflection_edit.setPlaceholderText("记录完成后的复盘、体会或下次改进")
        self.reflection_edit.setMinimumHeight(140)
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


class HistoryGraphBridge(QObject):
    def __init__(self, window: "HistoryWindow") -> None:
        super().__init__(window)
        self._window = window

    @Slot(str)
    def openNotes(self, task_id: str) -> None:
        self._window.open_history_graph_notes(task_id)

    @Slot(str)
    def editTag(self, task_id: str) -> None:
        self._window.edit_history_graph_tag(task_id)

    @Slot(str)
    def filterKeyword(self, keyword: str) -> None:
        self._window._jump_to_history_records(search=keyword)

    @Slot()
    def exportHistory(self) -> None:
        self._window.export_history()


class HistoryWindow(QDialog):
    def __init__(self, tasks: list[Task], store, parent=None) -> None:
        super().__init__(parent)
        self.tasks = list(tasks)
        self.store = store
        self._selected_page_index = 0
        self._current_history_section = "history"
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(150)
        self._search_debounce.timeout.connect(self._reset_page)

        self.setWindowTitle("历史任务")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModal)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(1180, 900)
        self.resize(1320, 960)
        self.setStyleSheet(_history_window_style())
        self.setSizeGripEnabled(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)

        content_shell = QFrame()
        content_shell.setObjectName("historyContentShell")
        content_root = QVBoxLayout(content_shell)
        content_root.setContentsMargins(0, 0, 0, 0)
        content_root.setSpacing(10)
        root.addWidget(content_shell, 1)

        self.title_bar = DialogTitleBar(self, "历史任务")
        self.title_bar.setObjectName("historyDragTitleBar")
        self.title_bar.setStyleSheet(_history_title_bar_style())
        self.top_settings_button = self.title_bar.add_action_button("", "打开设置", self._open_settings_workspace)
        self.top_settings_button.setAccessibleName("打开设置")
        self._set_button_icon(self.top_settings_button, "nav-settings.svg", size=15, icon_only=True)
        self.minimize_button = self.title_bar.add_action_button("", "最小化", self.showMinimized)
        self.minimize_button.setAccessibleName("最小化")
        self._set_button_icon(self.minimize_button, "window-minimize.svg", size=15, icon_only=True)
        self.fullscreen_button = self.title_bar.add_action_button("", "最大化历史窗口", self._toggle_maximize)
        self.fullscreen_button.setObjectName("historyFullscreenButton")
        self.fullscreen_button.setAccessibleName("最大化或还原")
        self._set_button_icon(self.fullscreen_button, "window-maximize.svg", size=14, icon_only=True)
        content_root.addWidget(self.title_bar)

        self.history_section_stack = QStackedWidget()
        self.history_section_stack.setObjectName("historySectionStack")
        content_root.addWidget(self.history_section_stack, 1)

        self.history_overview_scroll, self.history_overview_page, overview_layout = self._create_section_page("historyOverviewPage")
        self.history_records_list_scroll, self.history_records_list_page, records_layout = self._create_section_page("historyRecordsPage")
        self.history_analysis_scroll, self.history_analysis_page, analysis_layout = self._create_section_page("historyAnalysisPage")
        self.history_section_stack.addWidget(self.history_overview_scroll)
        self.history_section_stack.addWidget(self.history_records_list_scroll)
        self.history_section_stack.addWidget(self.history_analysis_scroll)
        self.history_content_scroll = self.history_overview_scroll

        self.header_panel = self._build_header_panel()
        overview_layout.addWidget(self.header_panel)
        self.metrics_panel = self._build_metrics_panel()
        overview_layout.addWidget(self.metrics_panel)
        self.analytics_panel = self._build_analytics_panel()
        overview_layout.addWidget(self.analytics_panel)
        self.charts_panel = self._build_history_charts_panel()
        overview_layout.addWidget(self.charts_panel)
        self.records_tools_panel = self._build_records_tools_panel()
        records_layout.addWidget(self.records_tools_panel)
        self.history_records_panel, self.history_list_container, self.list_layout = self._build_records_panel()
        records_layout.addWidget(self.history_records_panel, 1)
        self.pagination_panel = self._build_pagination_panel()
        records_layout.addWidget(self.pagination_panel)

        self.history_graph_panel = self._build_history_graph_panel()
        analysis_layout.addWidget(self.history_graph_panel, 1)

        resize_row = QHBoxLayout()
        resize_row.setContentsMargins(0, 0, 0, 0)
        resize_row.addStretch(1)
        self.history_resize_grip = QSizeGrip(self)
        self.history_resize_grip.setToolTip("拖动调整历史窗口大小")
        resize_row.addWidget(self.history_resize_grip)
        content_root.addLayout(resize_row)

        self._configure_date_range()
        self._set_history_section("history")
        self._render()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("historySidebar")
        sidebar.setFixedWidth(160)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        brand = QFrame()
        brand.setObjectName("historySidebarBrand")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(12, 14, 12, 14)
        brand_layout.setSpacing(10)
        logo = QLabel("")
        logo.setObjectName("historySidebarLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(50, 50)
        logo.setPixmap(QIcon(str(UI_ICON_DIR / "history-logo.svg")).pixmap(QSize(28, 28)))
        brand_layout.addWidget(logo, 0, Qt.AlignCenter)
        title = QLabel("Todo List")
        title.setObjectName("historySidebarTitle")
        title.setAlignment(Qt.AlignCenter)
        brand_layout.addWidget(title)
        layout.addWidget(brand)

        self.history_sidebar_buttons: dict[str, QPushButton] = {}
        definitions = [
            ("tasks", "任务", "nav-task.svg", "返回主任务窗口", self._open_main_workspace),
            ("history", "概览", "nav-history.svg", "查看历史任务概览", lambda: self._set_history_section("history")),
            ("records", "历史记录", "record-note.svg", "查看历史记录列表", lambda: self._set_history_section("records")),
            ("analysis", "洞察", "nav-analysis.svg", "查看任务星图洞察", lambda: self._set_history_section("analysis")),
            ("settings", "设置", "nav-settings.svg", "打开设置窗口", self._open_settings_workspace),
        ]
        for key, text, icon_name, tooltip, callback in definitions:
            button = QPushButton(text)
            button.setObjectName("historySidebarButton")
            button.setProperty("effectVariant", "nav")
            button.setCheckable(key in {"history", "records", "analysis"})
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setAccessibleName(text)
            button.clicked.connect(callback)
            self._set_button_icon(button, icon_name, size=18)
            layout.addWidget(button)
            self.history_sidebar_buttons[key] = button

        layout.addStretch(1)

        self.history_top_button = QPushButton("回到顶部")
        self.history_top_button.setObjectName("historySidebarUtility")
        self.history_top_button.setProperty("effectVariant", "utility")
        self.history_top_button.setCursor(Qt.PointingHandCursor)
        self.history_top_button.setToolTip("将当前页面滚动到顶部")
        self.history_top_button.clicked.connect(self._scroll_current_section_to_top)
        self._set_button_icon(self.history_top_button, "step-up.svg", size=16)
        layout.addWidget(self.history_top_button)
        return sidebar

    def _build_header_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyHeaderPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(4)
        title = QLabel("历史任务概览")
        title.setObjectName("historyTitle")
        subtitle = QLabel("复盘记录 · 数据洞察 · 持续优化")
        subtitle.setObjectName("historySubtitle")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        layout.addLayout(title_stack, 1)

        self.count_label = QLabel("0 条")
        self.count_label.setObjectName("historyCountChip")
        self.count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.count_label)
        return panel

    def _build_metrics_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyStatsPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        chips = [
            self._metric_chip("高：0", "historyPriorityMetricP1", "priority-high.svg", "historyMetricShellP1"),
            self._metric_chip("中：0", "historyPriorityMetricP2", "priority-medium.svg", "historyMetricShellP2"),
            self._metric_chip("低：0", "historyPriorityMetricP3", "priority-low.svg", "historyMetricShellP3"),
            self._metric_chip("复盘 0/0", "historyMetricChip", "record-note.svg", "historyMetricShell"),
            self._metric_chip("准时率 --", "historyMetricChip", "record-status.svg", "historyMetricShell"),
            self._metric_chip("超时 0/0", "historyOverdueMetric", "window-close.svg", "historyMetricShellOverdue"),
            self._metric_chip("无截止 0", "historyMetricChip", "record-calendar.svg", "historyMetricShell"),
            self._metric_chip("最近 --", "historyMetricChip", "record-clock.svg", "historyMetricShell"),
        ]
        (
            (_, self.priority_p1_label),
            (_, self.priority_p2_label),
            (_, self.priority_p3_label),
            (_, self.review_metric_label),
            (_, self.on_time_metric_label),
            (_, self.overdue_metric_label),
            (_, self.average_metric_label),
            (_, self.latest_metric_label),
        ) = chips
        for index, (chip, _) in enumerate(chips):
            layout.addWidget(chip, index // 4, index % 4)
            layout.setColumnStretch(index % 4, 1)
        return panel

    def _build_analytics_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyAnalyticsPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        title = QLabel("统计范围")
        title.setObjectName("historyAnalyticsTitle")
        layout.addWidget(title, 0, 0)

        self.analytics_count_label = QLabel("0 条")
        self.analytics_count_label.setObjectName("historyAnalyticsCount")
        self.analytics_count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.analytics_count_label, 0, 1)

        self.analytics_all_button = self._range_preset_button("全部", lambda: self._apply_range_preset("all"))
        self.analytics_week_button = self._range_preset_button("近7日", lambda: self._apply_range_preset("week"))
        self.analytics_month_button = self._range_preset_button("本月", lambda: self._apply_range_preset("month"))
        for column, button in enumerate((self.analytics_all_button, self.analytics_week_button, self.analytics_month_button), start=2):
            layout.addWidget(button, 0, column)

        self.analytics_start_date = self._date_edit(
            "historyAnalyticsStartDate",
            "historyAnalyticsStartCalendar",
            "统计起始日期",
            "选择统计区间的开始日期",
        )
        self.analytics_end_date = self._date_edit(
            "historyAnalyticsEndDate",
            "historyAnalyticsEndCalendar",
            "统计结束日期",
            "选择统计区间的结束日期",
        )
        self.analytics_start_date_chip = _date_chip("开始", self.analytics_start_date)
        self.analytics_end_date_chip = _date_chip("结束", self.analytics_end_date)
        self.analytics_start_date_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.analytics_end_date_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        date_row_widget = QWidget()
        date_row_layout = QHBoxLayout(date_row_widget)
        date_row_layout.setContentsMargins(0, 0, 0, 0)
        date_row_layout.setSpacing(10)
        arrow = QLabel("→")
        arrow.setObjectName("historyAnalyticsArrow")
        arrow.setAlignment(Qt.AlignCenter)
        date_row_layout.addWidget(self.analytics_start_date_chip, 1)
        date_row_layout.addWidget(arrow)
        date_row_layout.addWidget(self.analytics_end_date_chip, 1)
        layout.addWidget(date_row_widget, 1, 0, 1, 7)

        self.sort_mode = NoWheelComboBox()
        self.sort_mode.setObjectName("historySortMode")
        for label, key in SORT_FILTERS:
            self.sort_mode.addItem(label, key)
        self.sort_mode.currentIndexChanged.connect(self._reset_page)
        layout.addWidget(self.sort_mode, 0, 5)

        self.apply_filter_button = QPushButton("重置筛选")
        self.apply_filter_button.setObjectName("historyActionButton")
        self.apply_filter_button.setCursor(Qt.PointingHandCursor)
        self.apply_filter_button.clicked.connect(self._reset_filters)
        layout.addWidget(self.apply_filter_button, 0, 6)
        layout.setColumnStretch(4, 1)
        layout.setColumnStretch(7, 1)
        return panel

    def _build_history_charts_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyChartsPanel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.priority_donut_chart = PriorityDonutChart()
        self.completion_trend_chart = CompletionTrendChart()
        self.deadline_outcome_chart = DeadlineOutcomeChart()
        self.tag_duration_chart = TagDurationChart()
        self.tag_duration_chart.tag_clicked.connect(self._jump_to_tag_records)

        layout.addWidget(self._chart_card("优先级结构", "高 / 中 / 低完成占比", self.priority_donut_chart, "priority"), 0, 0)
        layout.addWidget(self._chart_card("完成节奏", "最近每天完成任务数量趋势", self.completion_trend_chart, "trend"), 0, 1)
        layout.addWidget(self._chart_card("准时率与超时分布", "准时、超时与无截止", self.deadline_outcome_chart, "deadline"), 0, 2)
        layout.addWidget(self._chart_card("标签数据库", "按任务标签聚合数量、实际耗时与时长占比", self.tag_duration_chart, "tag"), 1, 0, 1, 3)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        return panel

    def _build_history_graph_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyGraphPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(4)
        title = QLabel("3D 任务关系图")
        title.setObjectName("historySectionTitle")
        subtitle = QLabel("根据已完成任务的标题、标签、备注和体会抽取关键词，形成 Obsidian 风格关系网络")
        subtitle.setObjectName("historySubtitle")
        subtitle.setWordWrap(True)
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack, 1)
        self.history_graph_count_label = QLabel("0 条")
        self.history_graph_count_label.setObjectName("historyGraphCountChip")
        self.history_graph_count_label.setAlignment(Qt.AlignCenter)
        header.addWidget(self.history_graph_count_label)
        layout.addLayout(header)

        self.history_graph_webview = QWebEngineView()
        self.history_graph_webview.setObjectName("historyGraphWebView")
        self.history_graph_webview.setMinimumHeight(520)
        self.history_graph_webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._history_graph_channel = QWebChannel(self.history_graph_webview.page())
        self._history_graph_bridge = HistoryGraphBridge(self)
        self._history_graph_channel.registerObject("historyBridge", self._history_graph_bridge)
        self.history_graph_webview.page().setWebChannel(self._history_graph_channel)

        self.history_graph_stack = QStackedWidget()
        self.history_graph_stack.setMinimumHeight(520)
        self.history_graph_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.history_graph_placeholder = QLabel("正在准备 3D 关系图…")
        self.history_graph_placeholder.setObjectName("historyGraphPlaceholder")
        self.history_graph_placeholder.setAlignment(Qt.AlignCenter)
        self.history_graph_placeholder.setStyleSheet(
            "QLabel#historyGraphPlaceholder {"
            "color: #9CB3C6; font-size: 14px; font-weight: 800;"
            "background: rgba(4, 16, 29, 0.62);"
            "border: 1px dashed rgba(110, 156, 184, 36);"
            "border-radius: 14px;"
            "}"
        )
        self.history_graph_stack.addWidget(self.history_graph_placeholder)
        self.history_graph_stack.addWidget(self.history_graph_webview)
        self.history_graph_webview.loadFinished.connect(
            lambda _ok: self.history_graph_stack.setCurrentWidget(self.history_graph_webview)
        )
        layout.addWidget(self.history_graph_stack, 1)
        self._analysis_graph_html = ""
        return panel

    def _build_records_tools_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyToolbar")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        title = QLabel("历史记录列表")
        title.setObjectName("historySectionTitle")
        header_row.addWidget(title)
        self.records_count_label = QLabel("0 条")
        self.records_count_label.setObjectName("historySectionCount")
        self.records_count_label.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.records_count_label)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("historySearch")
        self.search_input.setPlaceholderText("搜索任务名称、备注或复盘")
        self.search_input.textChanged.connect(lambda _text: self._search_debounce.start())
        filters_row.addWidget(self.search_input, 2)

        self.status_filter = NoWheelComboBox()
        self.status_filter.setObjectName("historyStatusFilter")
        for label, key in STATUS_FILTERS:
            self.status_filter.addItem(label, key)
        self.status_filter.currentIndexChanged.connect(self._reset_page)
        filters_row.addWidget(self.status_filter)

        self.priority_filter = NoWheelComboBox()
        self.priority_filter.setObjectName("historyPriorityFilter")
        for label, key in PRIORITY_FILTERS:
            self.priority_filter.addItem(label, key)
        self.priority_filter.currentIndexChanged.connect(self._reset_page)
        filters_row.addWidget(self.priority_filter)

        self.tag_filter = NoWheelComboBox()
        self.tag_filter.setObjectName("historyTagFilter")
        self.tag_filter.addItem("全部标签", "all")
        for tag in _task_tags(self.tasks):
            self.tag_filter.addItem(tag, tag)
        self.tag_filter.currentIndexChanged.connect(self._reset_page)
        filters_row.addWidget(self.tag_filter)

        self.page_size_combo = NoWheelComboBox()
        self.page_size_combo.setObjectName("historyPageSize")
        for size in PAGE_SIZES:
            self.page_size_combo.addItem(f"每页 {size} 条", size)
        self.page_size_combo.setCurrentIndex(0)
        self.page_size_combo.currentIndexChanged.connect(self._reset_page)
        filters_row.addWidget(self.page_size_combo)
        layout.addLayout(filters_row)

        export_row = QHBoxLayout()
        export_row.setSpacing(10)
        export_label = QLabel("导出范围")
        export_label.setObjectName("historyToolbarLabel")
        export_row.addWidget(export_label)

        self.export_count_label = QLabel("0 条")
        self.export_count_label.setObjectName("historyExportCount")
        self.export_count_label.setAlignment(Qt.AlignCenter)
        export_row.addWidget(self.export_count_label)

        self.export_start_date = self._date_edit(
            "historyExportStartDate",
            "historyExportStartCalendar",
            "导出起始日期",
            "选择导出记录的开始日期",
        )
        self.export_end_date = self._date_edit(
            "historyExportEndDate",
            "historyExportEndCalendar",
            "导出结束日期",
            "选择导出记录的结束日期",
        )
        self.export_start_date_chip = _date_chip("开始", self.export_start_date)
        self.export_end_date_chip = _date_chip("结束", self.export_end_date)
        self.export_start_date_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.export_end_date_chip.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        export_row.addWidget(self.export_start_date_chip, 1)
        export_arrow = QLabel("→")
        export_arrow.setObjectName("historyExportArrow")
        export_arrow.setAlignment(Qt.AlignCenter)
        export_row.addWidget(export_arrow)
        export_row.addWidget(self.export_end_date_chip, 1)

        self.export_button = QPushButton("导出 CSV")
        self.export_button.setObjectName("historyExportButton")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setToolTip("按当前筛选结果和导出日期导出记录")
        self._set_button_icon(self.export_button, "record-status.svg", size=16)
        self.export_button.clicked.connect(self.export_history)
        export_row.addWidget(self.export_button)
        layout.addLayout(export_row)
        return panel

    def _build_records_panel(self) -> tuple[QScrollArea, QWidget, QGridLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("historyRecordsPanel")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        container = QWidget()
        container.setObjectName("historyRecordsViewport")
        layout = QGridLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)
        scroll.setWidget(container)
        return scroll, container, layout

    def _build_pagination_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("historyPagerPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.page_summary_label = QLabel("第 1 / 1 页")
        self.page_summary_label.setObjectName("historyPageLabel")
        layout.addWidget(self.page_summary_label)
        layout.addStretch(1)

        self.prev_page_button = QPushButton("上一页")
        self.prev_page_button.setObjectName("historyPageButton")
        self.prev_page_button.setCursor(Qt.PointingHandCursor)
        self._set_button_icon(self.prev_page_button, "step-down.svg", size=14)
        self.prev_page_button.clicked.connect(lambda checked=False: self._move_page(-1))
        layout.addWidget(self.prev_page_button)

        self.page_jump_input = NoWheelSpinBox()
        self.page_jump_input.setObjectName("historyPageJump")
        self.page_jump_input.setRange(1, 1)
        self.page_jump_input.setButtonSymbols(QSpinBox.NoButtons)
        self.page_jump_input.editingFinished.connect(self._jump_to_page)
        layout.addWidget(self.page_jump_input)

        self.next_page_button = QPushButton("下一页")
        self.next_page_button.setObjectName("historyPageButton")
        self.next_page_button.setCursor(Qt.PointingHandCursor)
        self._set_button_icon(self.next_page_button, "step-up.svg", size=14)
        self.next_page_button.clicked.connect(lambda checked=False: self._move_page(1))
        layout.addWidget(self.next_page_button)
        return panel

    def _create_section_page(self, object_name: str) -> tuple[QScrollArea, QFrame, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setObjectName(f"{object_name}Scroll")

        page = QFrame()
        page.setObjectName(object_name)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        scroll.setWidget(page)
        return scroll, page, layout

    def _metric_chip(self, text: str, object_name: str, icon_name: str, shell_name: str) -> tuple[QFrame, QLabel]:
        shell = QFrame()
        shell.setObjectName(shell_name)
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(8)
        layout.addWidget(self._icon_chip(icon_name, size=16, object_name="historyMetricIcon"))
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setWordWrap(True)
        layout.addWidget(label, 1)
        return shell, label

    def _priority_badge(self, priority: str) -> QFrame:
        shell = QFrame()
        shell.setObjectName(f"historyPriorityBadge{priority}")
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(8, 0, 10, 0)
        layout.setSpacing(6)
        layout.addWidget(self._icon_chip(PRIORITY_ICON_NAMES[priority], size=12, object_name="historyPriorityIcon"))
        label = QLabel(priority_text(priority))
        label.setObjectName(f"historyPriority{priority}")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        return shell

    def _set_button_icon(self, button: QPushButton | QToolButton, icon_name: str, *, size: int = 18, icon_only: bool = False) -> None:
        button.setIcon(QIcon(str(UI_ICON_DIR / icon_name)))
        button.setIconSize(QSize(size, size))
        if icon_only and hasattr(button, "setText"):
            button.setText("")

    def _icon_chip(self, icon_name: str, *, size: int = 16, object_name: str = "historyInlineIcon") -> QLabel:
        chip = QLabel("")
        chip.setObjectName(object_name)
        chip.setFixedSize(size + 14, size + 14)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(QIcon(str(UI_ICON_DIR / icon_name)).pixmap(QSize(size, size)))
        return chip

    def _range_preset_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("historyAnalyticsPresetButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _history_action_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("historyActionButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def _priority_markup(self, priority: str, *, size: int = 13, suffix: str = "") -> str:
        icon_path = (UI_ICON_DIR / PRIORITY_ICON_NAMES.get(priority, "priority-medium.svg")).as_posix()
        label = priority_text(priority)
        trailing = f" {suffix}" if suffix else ""
        return (
            f"<span style=\"white-space: nowrap;\">"
            f"<img src=\"{icon_path}\" width=\"{size}\" height=\"{size}\" "
            f"style=\"vertical-align: middle; margin-right: 6px;\"/>"
            f"{label}{trailing}</span>"
        )

    def _date_edit(self, object_name: str, calendar_name: str, accessible_name: str, tooltip: str) -> QDateEdit:
        edit = NoWheelDateEdit()
        edit.setObjectName(object_name)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setAccessibleName(accessible_name)
        edit.setToolTip(tooltip)
        edit.setAlignment(Qt.AlignCenter)
        apply_dark_calendar_popup(edit, calendar_name)
        edit.dateChanged.connect(self._render)
        return edit

    def _chart_card(self, title: str, subtitle: str, widget: QWidget, tone: str) -> QFrame:
        card = QFrame()
        card.setObjectName("historyChartCard")
        card.setProperty("historyTone", tone)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("historyChartTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("historyChartSubtitle")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addWidget(widget)
        apply_soft_shadow(card, blur=28, y_offset=10, alpha=92)
        return card

    def _set_history_section(self, section: str, *, scroll_to_top: bool = True) -> None:
        self._current_history_section = section
        if section == "analysis":
            self.history_section_stack.setCurrentWidget(self.history_analysis_scroll)
            self.history_content_scroll = self.history_analysis_scroll
            animate_content_swap(self.history_analysis_page)
        elif section == "records":
            self.history_section_stack.setCurrentWidget(self.history_records_list_scroll)
            self.history_content_scroll = self.history_records_list_scroll
            animate_content_swap(self.history_records_list_page)
        else:
            self.history_section_stack.setCurrentWidget(self.history_overview_scroll)
            self.history_content_scroll = self.history_overview_scroll
            animate_content_swap(self.history_overview_page)

        self.history_sidebar_buttons["history"].setChecked(section == "history")
        self.history_sidebar_buttons["records"].setChecked(section == "records")
        self.history_sidebar_buttons["analysis"].setChecked(section == "analysis")
        if scroll_to_top:
            self._scroll_current_section_to_top()

    def _scroll_current_section_to_top(self) -> None:
        self._scroll_current_section_to_value(0, animated=False)

    def _scroll_current_section_to_value(self, value: int, *, animated: bool) -> None:
        scroll_bar = self.history_content_scroll.verticalScrollBar()
        target = max(scroll_bar.minimum(), min(int(value), scroll_bar.maximum()))
        old_animation = getattr(self, "_history_scroll_animation", None)
        if old_animation is not None:
            old_animation.stop()
            self._history_scroll_animation = None

        if not animated or abs(scroll_bar.value() - target) <= 2:
            scroll_bar.setValue(target)
            return

        animation = QPropertyAnimation(scroll_bar, b"value", self)
        animation.setDuration(320)
        animation.setStartValue(scroll_bar.value())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        self._history_scroll_animation = animation

        def finish() -> None:
            if getattr(self, "_history_scroll_animation", None) is animation:
                self._history_scroll_animation = None

        animation.finished.connect(finish)
        animation.start()

    def _scroll_records_list_into_view(self, *, animated: bool = True) -> None:
        self._set_history_section("records")
        animate_content_swap(self.history_list_container, duration=220)

    def _open_main_workspace(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            QMessageBox.information(self, "返回任务窗口", "当前历史工作台没有绑定主任务窗口。")
            return
        if hasattr(parent, "showNormal"):
            parent.showNormal()
        if hasattr(parent, "raise_"):
            parent.raise_()
        if hasattr(parent, "activateWindow"):
            parent.activateWindow()
        self.accept()

    def _open_settings_workspace(self) -> None:
        parent = self.parentWidget()
        if parent is None or not hasattr(parent, "open_settings"):
            QMessageBox.information(self, "打开设置", "当前历史工作台没有可复用的设置窗口入口。")
            return
        parent.open_settings()

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self._set_button_icon(self.fullscreen_button, "window-maximize.svg", size=14, icon_only=True)
            self.fullscreen_button.setToolTip("最大化历史窗口")
            return
        self.showMaximized()
        self._set_button_icon(self.fullscreen_button, "window-restore.svg", size=14, icon_only=True)
        self.fullscreen_button.setToolTip("还原历史窗口")

    def _configure_date_range(self) -> None:
        completed = self._completed_tasks()
        if completed:
            dates = [item for item in (_task_completed_date(task) for task in completed) if item is not None]
            start = min(dates) if dates else date.today()
            end = max(dates) if dates else date.today()
        else:
            start = end = date.today()

        start_qdate = QDate(start.year, start.month, start.day)
        end_qdate = QDate(end.year, end.month, end.day)
        for edit in (self.analytics_start_date, self.export_start_date):
            edit.blockSignals(True)
            edit.setDate(start_qdate)
            edit.blockSignals(False)
        for edit in (self.analytics_end_date, self.export_end_date):
            edit.blockSignals(True)
            edit.setDate(end_qdate)
            edit.blockSignals(False)

    def _apply_range_preset(self, preset: str) -> None:
        completed = self._completed_tasks()
        today = max((_task_completed_date(task) or date.today()) for task in completed) if completed else date.today()
        if preset == "week":
            start = today - timedelta(days=6)
            end = today
        elif preset == "month":
            start = today.replace(day=1)
            end = today
        else:
            dates = [item for item in (_task_completed_date(task) for task in completed) if item is not None]
            start = min(dates) if dates else today
            end = max(dates) if dates else today
        self.analytics_start_date.setDate(QDate(start.year, start.month, start.day))
        self.analytics_end_date.setDate(QDate(end.year, end.month, end.day))

    def _reset_filters(self) -> None:
        self.search_input.clear()
        self.status_filter.setCurrentIndex(0)
        self.priority_filter.setCurrentIndex(0)
        self.tag_filter.setCurrentIndex(0)
        self.sort_mode.setCurrentIndex(0)
        self.page_size_combo.setCurrentIndex(0)
        self._selected_page_index = 0
        self._render()

    def _completed_tasks(self) -> list[Task]:
        return [task for task in self.tasks if task.status == "done"]

    def _analytics_tasks(self) -> list[Task]:
        start = self.analytics_start_date.date().toPython()
        end = self.analytics_end_date.date().toPython()
        return [task for task in self._completed_tasks() if _date_in_range(_task_completed_date(task), start, end)]

    def _status_matches(self, task: Task) -> bool:
        selected = str(self.status_filter.currentData() or "all")
        reviewed = bool(task.notes.strip() or task.reflection.strip())
        if selected == "all":
            return True
        if selected == "on_time":
            return task.deadline is not None and not _task_completed_late(task)
        if selected == "overdue":
            return _task_completed_late(task)
        if selected == "no_deadline":
            return task.deadline is None
        if selected == "reviewed":
            return reviewed
        if selected == "needs_notes":
            return not reviewed
        return True

    def _filtered_completed_tasks(self) -> list[Task]:
        search = self.search_input.text().strip().lower()
        selected_priority = str(self.priority_filter.currentData() or "all")
        selected_tag = str(self.tag_filter.currentData() or "all")
        tasks: list[Task] = []
        for task in self._analytics_tasks():
            if selected_priority != "all" and task.priority != selected_priority:
                continue
            if selected_tag != "all" and _task_tag(task) != selected_tag:
                continue
            if not self._status_matches(task):
                continue
            searchable = " ".join([task.title, _task_tag(task), task.notes, task.reflection]).lower()
            if search and search not in searchable:
                continue
            tasks.append(task)
        return self._sorted_completed_tasks(tasks)

    def _sorted_completed_tasks(self, tasks: list[Task]) -> list[Task]:
        mode = str(self.sort_mode.currentData() or "completed")
        if mode == "priority":
            priority_rank = {priority: index for index, priority in enumerate(PRIORITY_ORDER)}
            return sorted(tasks, key=lambda task: (priority_rank.get(task.priority, 99), -(task.completed_at or task.updated_at).timestamp()))
        if mode == "effort":
            return sorted(tasks, key=lambda task: (-work_elapsed_seconds(task, task.completed_at or task.updated_at), task.title.lower()))
        if mode == "title":
            return sorted(tasks, key=lambda task: (task.title.lower(), -(task.completed_at or task.updated_at).timestamp()))
        return sorted(tasks, key=lambda task: (task.completed_at or task.updated_at), reverse=True)

    def _exportable_tasks(self) -> list[Task]:
        start = self.export_start_date.date().toPython()
        end = self.export_end_date.date().toPython()
        return [task for task in self._filtered_completed_tasks() if _date_in_range(_task_completed_date(task), start, end)]

    def _page_size(self) -> int:
        return int(self.page_size_combo.currentData() or PAGE_SIZES[0])

    def _page_count(self, tasks: list[Task]) -> int:
        size = self._page_size()
        return max(1, (len(tasks) + size - 1) // size)

    def _paged_tasks(self, tasks: list[Task]) -> list[Task]:
        size = self._page_size()
        start = self._selected_page_index * size
        end = start + size
        return tasks[start:end]

    def _move_page(self, offset: int) -> None:
        tasks = self._filtered_completed_tasks()
        if not tasks:
            return
        self._selected_page_index = max(0, min(self._selected_page_index + offset, self._page_count(tasks) - 1))
        self._render()

    def _jump_to_page(self) -> None:
        tasks = self._filtered_completed_tasks()
        if not tasks:
            return
        self._selected_page_index = max(0, min(self.page_jump_input.value() - 1, self._page_count(tasks) - 1))
        self._render()

    def _reset_page(self, *args) -> None:
        self._selected_page_index = 0
        self._render()

    def _record_status(self, task: Task) -> tuple[str, str, str]:
        if task.deadline is None:
            return "无截止", "完成时未设置截止时间", "historyStatusNeutral"
        if _task_completed_late(task):
            return "超时完成", "完成时间晚于截止时间", "historyStatusOverdue"
        return "准时完成", "在截止时间前完成", "historyStatusOnTime"

    def _record_summary(self, task: Task) -> str:
        completed_text = _export_datetime(task.completed_at or task.updated_at)
        status_text, detail_text, _ = self._record_status(task)
        parts = [
            f"标题：{task.title}",
            f"标签：{_task_tag(task)}",
            f"优先级：{priority_text(task.priority)}",
            f"完成时间：{completed_text}",
            f"状态：{status_text}",
            f"说明：{detail_text}",
        ]
        if task.notes.strip():
            parts.append(f"任务备注：{task.notes.strip()}")
        if task.reflection.strip():
            parts.append(f"完成体会：{task.reflection.strip()}")
        return "\n".join(parts)

    def _copy_record_summary(self, task: Task) -> None:
        QApplication.clipboard().setText(self._record_summary(task))

    def _export_single_record(self, task: Task) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "导出单条历史记录", f"{task.title}-历史记录.csv", "CSV 表格 (*.csv);;All Files (*)")
        if not path:
            return
        export_path = Path(path)
        if export_path.suffix.lower() != ".csv":
            export_path = export_path.with_suffix(".csv")
        self.export_history_to_path(export_path, [task])

    def _meta_line(self, icon_name: str, text: str, *, strong: bool = False) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._icon_chip(icon_name, size=14))
        label = QLabel(text)
        label.setObjectName("historyRecordMetaStrong" if strong else "historyRecordMeta")
        layout.addWidget(label)
        layout.addStretch(1)
        return layout

    def _preview_line(self, icon_name: str, text: str) -> QFrame:
        shell = QFrame()
        shell.setObjectName("historyPreview")
        layout = QHBoxLayout(shell)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        layout.addWidget(self._icon_chip(icon_name, size=14))
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("historyPreviewText")
        layout.addWidget(label, 1)
        return shell

    def _build_record_card(self, task: Task) -> QFrame:
        card = QFrame()
        card.setObjectName("historyCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        card.setMinimumHeight(160)
        apply_soft_shadow(card, blur=24, y_offset=8, alpha=96)

        shell = QHBoxLayout(card)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        accent = QFrame()
        accent.setObjectName(f"historyAccent{task.priority}")
        accent.setFixedWidth(5)
        shell.addWidget(accent)

        content = QWidget()
        shell.addWidget(content, 1)
        layout = QHBoxLayout(content)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel(task.title)
        title.setObjectName("historyRecordTitle")
        title.setWordWrap(True)
        title.setToolTip(task.title)
        left.addWidget(title)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_row.addWidget(self._priority_badge(task.priority))
        tag_label = QLabel(f"#{_task_tag(task)}")
        tag_label.setObjectName("historyTagChip")
        tag_label.setAlignment(Qt.AlignCenter)
        tag_label.setToolTip(f"任务标签：{_task_tag(task)}")
        meta_row.addWidget(tag_label)
        review_label = QLabel("已复盘" if task.notes.strip() or task.reflection.strip() else "待补记")
        review_label.setObjectName("historyReviewChipDone" if task.notes.strip() or task.reflection.strip() else "historyReviewChipEmpty")
        review_label.setAlignment(Qt.AlignCenter)
        meta_row.addWidget(review_label)
        meta_row.addStretch(1)
        left.addLayout(meta_row)

        completed_text = _export_datetime(task.completed_at or task.updated_at)[:-3]
        left.addLayout(self._meta_line("record-calendar.svg", f"完成时间  {completed_text}"))
        deadline_text = _export_datetime(task.deadline)[:-3] if task.deadline is not None else "无"
        left.addLayout(self._meta_line("record-calendar.svg", f"截止时间  {deadline_text}"))
        layout.addLayout(left, 2)

        middle = QVBoxLayout()
        middle.setSpacing(8)
        elapsed = work_elapsed_seconds(task, task.completed_at or task.updated_at)
        target = work_target_seconds(task)
        middle.addLayout(
            self._meta_line(
                "record-clock.svg",
                f"实际耗时  {duration_clock_label(elapsed)}  /  预计  {effort_short_label(max(0, target // 60))}",
                strong=True,
            )
        )
        has_notes = bool(task.notes.strip())
        has_reflection = bool(task.reflection.strip())
        if has_notes:
            middle.addWidget(self._preview_line("record-note.svg", self._compact_text(task.notes)))
        if has_reflection:
            middle.addWidget(self._preview_line("record-note.svg", self._compact_text(task.reflection)))
        if not has_notes and not has_reflection:
            middle.addWidget(self._preview_line("record-note.svg", "任务备注与完成体会：暂无"))
        middle.addStretch(1)
        layout.addLayout(middle, 2)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.setAlignment(Qt.AlignTop)
        status_text, detail_text, status_name = self._record_status(task)
        status_header = QHBoxLayout()
        status_header.setSpacing(8)
        status_header.addWidget(self._icon_chip("record-status.svg", size=14))
        status_label = QLabel(status_text)
        status_label.setObjectName(status_name)
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setMinimumHeight(30)
        status_header.addWidget(status_label)
        status_header.addStretch(1)
        right.addLayout(status_header)

        detail_label = QLabel(detail_text)
        detail_label.setObjectName("historyRecordDetail")
        detail_label.setWordWrap(True)
        right.addWidget(detail_label)

        menu_button = QToolButton()
        menu_button.setObjectName("historyMoreButton")
        menu_button.setCursor(Qt.PointingHandCursor)
        menu_button.setPopupMode(QToolButton.InstantPopup)
        menu_button.setToolTip("更多操作")
        self._set_button_icon(menu_button, "more-vertical.svg", size=16, icon_only=True)
        menu = QMenu(menu_button)
        menu.addAction("查看/编辑备注", lambda: self.open_note_editor(task))
        menu.addAction("复制记录摘要", lambda: self._copy_record_summary(task))
        menu.addAction("导出当前记录", lambda: self._export_single_record(task))
        menu_button.setMenu(menu)
        right.addStretch(1)
        right.addWidget(menu_button, 0, Qt.AlignRight)
        layout.addLayout(right, 1)
        return card

    def _clear_list_layout(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _render_records(self, tasks: list[Task]) -> None:
        self._clear_list_layout()
        if not tasks:
            empty = QFrame()
            empty.setObjectName("historyEmptyState")
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(18, 40, 18, 40)
            empty_layout.setSpacing(6)
            title = QLabel("还没有符合条件的历史记录")
            title.setObjectName("historyEmptyTitle")
            hint = QLabel("调整日期范围或筛选条件后再试。")
            hint.setObjectName("historyEmptyHint")
            empty_layout.addWidget(title, 0, Qt.AlignCenter)
            empty_layout.addWidget(hint, 0, Qt.AlignCenter)
            self.list_layout.addWidget(empty, 0, 0)
            return
        for index, task in enumerate(tasks):
            self.list_layout.addWidget(self._build_record_card(task), index, 0)
        self.list_layout.setRowStretch(len(tasks), 1)
        self.list_layout.setColumnStretch(0, 1)

    def _update_metrics(self, completed: list[Task]) -> None:
        total = len(completed)
        counts = {priority: sum(1 for task in completed if task.priority == priority) for priority in PRIORITY_ORDER}
        overdue = sum(1 for task in completed if _task_completed_late(task))
        no_deadline = sum(1 for task in completed if task.deadline is None)
        deadline_total = max(0, total - no_deadline)
        on_time = max(0, deadline_total - overdue)
        on_time_rate = f"{round(on_time / deadline_total * 100)}%" if deadline_total else "--"
        reviewed = sum(1 for task in completed if task.notes.strip() or task.reflection.strip())
        latest_task = max(completed, key=lambda task: task.completed_at or task.updated_at, default=None)
        latest = (latest_task.completed_at or latest_task.updated_at).astimezone().strftime("%m-%d %H:%M") if latest_task else "--"
        tag_stats = _tag_duration_stats(completed)

        self.priority_p1_label.setText(f"高：{counts['P1']}")
        self.priority_p2_label.setText(f"中：{counts['P2']}")
        self.priority_p3_label.setText(f"低：{counts['P3']}")
        self.review_metric_label.setText(f"复盘 {reviewed}/{total}")
        self.on_time_metric_label.setText(f"准时率 {on_time_rate}")
        self.overdue_metric_label.setText(f"超时 {overdue}/{deadline_total}")
        self.average_metric_label.setText(f"无截止 {no_deadline}")
        self.latest_metric_label.setText(f"最近 {latest}")

        self.priority_donut_chart.set_counts(counts)
        self.completion_trend_chart.set_points(_completion_trend(completed))
        self.deadline_outcome_chart.set_counts(on_time=on_time, overdue=overdue, no_deadline=no_deadline)
        self.tag_duration_chart.set_stats(tag_stats)
    def _sync_pagination(self, total_tasks: list[Task]) -> None:
        page_count = self._page_count(total_tasks)
        if self._selected_page_index >= page_count:
            self._selected_page_index = max(0, page_count - 1)
        current_page = self._selected_page_index + 1
        total = len(total_tasks)
        if total:
            start = self._selected_page_index * self._page_size() + 1
            end = min(total, start + self._page_size() - 1)
            self.page_summary_label.setText(f"{start}-{end} / {total} 条 · 第 {current_page}/{page_count} 页")
        else:
            self.page_summary_label.setText("0 / 0 条 · 第 1/1 页")
        self.page_jump_input.blockSignals(True)
        self.page_jump_input.setRange(1, page_count)
        self.page_jump_input.setValue(current_page if total else 1)
        self.page_jump_input.blockSignals(False)
        self.prev_page_button.setEnabled(self._selected_page_index > 0)
        self.next_page_button.setEnabled(self._selected_page_index < page_count - 1)

    def _update_history_graph(self, completed: list[Task]) -> None:
        payload = build_history_graph_payload(completed)
        self.history_graph_count_label.setText(f"{len(payload['tasks'])} 条")
        html = render_history_graph_html(payload)
        if html == self._analysis_graph_html:
            return
        self._analysis_graph_html = html
        self.history_graph_webview.setHtml(html)

    def _render(self, *args) -> None:
        analytics_tasks = self._analytics_tasks()
        self._update_metrics(analytics_tasks)
        self.analytics_count_label.setText(f"{len(analytics_tasks)} 条")
        self._update_history_graph(analytics_tasks)

        filtered = self._filtered_completed_tasks()
        self.count_label.setText(f"{len(filtered)} 条")
        self.records_count_label.setText(f"{len(filtered)} 条")
        exportable = self._exportable_tasks()
        self.export_count_label.setText(f"{len(exportable)} 条")

        self._sync_pagination(filtered)
        self._render_records(self._paged_tasks(filtered))

    def _jump_to_history_records(self, *, status: str = "all", priority: str = "all", tag: str = "all", search: str = "") -> None:
        self.search_input.setText(search)
        self.status_filter.setCurrentIndex(max(0, self.status_filter.findData(status)))
        self.priority_filter.setCurrentIndex(max(0, self.priority_filter.findData(priority)))
        self.tag_filter.setCurrentIndex(max(0, self.tag_filter.findData(tag)))
        self._selected_page_index = 0
        self._render()
        self._set_history_section("records")
        animate_content_swap(self.history_list_container, duration=220)

    def _jump_to_tag_records(self, tag: str) -> None:
        self._jump_to_history_records(tag=normalize_task_tag(tag))

    def _task_by_id(self, task_id: str) -> Task | None:
        return next((task for task in self.tasks if task.id == task_id), None)

    def open_history_graph_notes(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if task is None:
            return
        self.open_note_editor(task)

    def edit_history_graph_tag(self, task_id: str) -> None:
        task = self._task_by_id(task_id)
        if task is None:
            return
        current_tag = _task_tag(task)
        new_tag, accepted = QInputDialog.getText(self, "修改任务标签", "新的标签：", text=current_tag)
        if not accepted:
            return
        normalized = normalize_task_tag(new_tag)
        if normalized == current_tag:
            return
        self.tasks = [replace(item, tag=normalized) if item.id == task_id else item for item in self.tasks]
        self.store.save_tasks(self.tasks)
        self._refresh_tag_filter_options(selected=normalized)
        self._render()

    def _refresh_tag_filter_options(self, *, selected: str = "all") -> None:
        selected = normalize_task_tag(selected) if selected != "all" else "all"
        self.tag_filter.blockSignals(True)
        self.tag_filter.clear()
        self.tag_filter.addItem("全部标签", "all")
        for tag in _task_tags(self.tasks):
            self.tag_filter.addItem(tag, tag)
        index = self.tag_filter.findData(selected)
        self.tag_filter.setCurrentIndex(index if index >= 0 else 0)
        self.tag_filter.blockSignals(False)

    def export_history(self) -> None:
        tasks = self._exportable_tasks()
        if not tasks:
            QMessageBox.information(self, "导出历史记录", "没有可导出的历史记录。")
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出历史记录", "Todo-list-历史记录.csv", "CSV 表格 (*.csv);;All Files (*)")
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

    def _compact_text(self, text: str, limit: int = 96) -> str:
        compact = " ".join(str(text or "").split())
        if not compact:
            return ""
        return compact if len(compact) <= limit else f"{compact[:limit]}..."


def export_history_csv(path: str | Path, tasks: list[Task]) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "任务ID": task.id,
                    "标题": task.title,
                    "标签": _task_tag(task),
                    "优先级": priority_text(task.priority),
                    "预计工作量分钟": task.effort_minutes,
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
    chip.setMinimumHeight(44)
    layout = QHBoxLayout(chip)
    layout.setContentsMargins(6, 5, 6, 5)
    layout.setSpacing(6)
    label = QLabel(label_text)
    label.setObjectName("historyExportDateLabel")
    label.setAlignment(Qt.AlignCenter)
    label.setFixedSize(48, 32)
    date_edit.setMinimumHeight(32)
    layout.addWidget(label)
    layout.addWidget(date_edit, 1)
    return chip


def _ratio_text(value: int, total: int) -> str:
    return "0%" if total <= 0 else f"{round(value / total * 100)}%"


def _task_tag(task: Task) -> str:
    return normalize_task_tag(getattr(task, "tag", DEFAULT_TASK_TAG))


def _task_tags(tasks: list[Task]) -> list[str]:
    tags = {_task_tag(task) for task in tasks}
    return sorted(tags, key=lambda tag: (tag == DEFAULT_TASK_TAG, tag))


def _tag_duration_seconds(task: Task) -> int:
    actual = work_elapsed_seconds(task, task.completed_at or task.updated_at)
    return actual if actual > 0 else work_target_seconds(task)


def _tag_duration_stats(tasks: list[Task]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, int]] = {}
    for task in tasks:
        tag = _task_tag(task)
        if tag not in grouped:
            grouped[tag] = {"count": 0, "seconds": 0}
        grouped[tag]["count"] += 1
        grouped[tag]["seconds"] += max(0, _tag_duration_seconds(task))
    return [
        {"tag": tag, "count": values["count"], "seconds": values["seconds"]}
        for tag, values in sorted(grouped.items(), key=lambda item: (-item[1]["seconds"], item[0]))
    ]


def _tag_chart_color(index: int) -> str:
    return TAG_CHART_COLORS[index % len(TAG_CHART_COLORS)]


def _export_datetime(value) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _task_completed_date(task: Task) -> date | None:
    value = task.completed_at or task.updated_at
    return value.astimezone().date() if value else None


def _task_completed_late(task: Task) -> bool:
    completed_at = task.completed_at or task.updated_at
    return bool(task.deadline and completed_at and completed_at > task.deadline)


def _completion_trend(tasks: list[Task], *, max_days: int = 14) -> list[tuple[date, int]]:
    dates = [item for item in (_task_completed_date(task) for task in tasks) if item is not None]
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
  border-radius: 10px;
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
"""


def _history_window_style() -> str:
    return """
QDialog {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #020A13,
    stop:0.52 #041323,
    stop:1 #06202B);
}
QWidget {
  background: transparent;
  color: #E7F3FF;
}
QFrame#historySidebar {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #071422,
    stop:1 #0A2034);
  border: 1px solid rgba(98, 144, 176, 42);
  border-radius: 22px;
}
QFrame#historySidebarBrand {
  background: rgba(9, 25, 40, 0.92);
  border: 1px solid rgba(98, 144, 176, 36);
  border-radius: 18px;
}
QLabel#historySidebarLogo {
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.75,
    stop:0 rgba(12, 107, 138, 0.24),
    stop:1 rgba(10, 33, 55, 0.12));
  border: 1px solid rgba(103, 232, 249, 42);
  border-radius: 25px;
}
QLabel#historySidebarTitle {
  color: #F8FBFF;
  font-size: 14px;
  font-weight: 900;
}
QPushButton#historySidebarButton,
QPushButton#historySidebarUtility {
  color: #D6E6F4;
  background: rgba(10, 29, 45, 0.92);
  border: 1px solid rgba(98, 144, 176, 26);
  border-radius: 16px;
  min-height: 48px;
  text-align: left;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 900;
}
QPushButton#historySidebarButton:hover,
QPushButton#historySidebarUtility:hover {
  background: rgba(19, 55, 84, 0.95);
}
QPushButton#historySidebarButton:checked {
  color: #F4FCFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1B4D78,
    stop:1 #1E90B8);
  border: 1px solid rgba(103, 232, 249, 56);
}
QFrame#historyContentShell {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 rgba(4, 16, 29, 0.72),
    stop:1 rgba(6, 28, 43, 0.42));
  border: 1px solid rgba(89, 136, 170, 0.16);
  border-radius: 22px;
}
QStackedWidget#historySectionStack {
  background: transparent;
  border: none;
}
QScrollArea#historyOverviewPageScroll,
QScrollArea#historyRecordsPageScroll,
QScrollArea#historyAnalysisPageScroll {
  border: none;
  background: transparent;
}
QFrame#historyOverviewPage,
QFrame#historyRecordsPage,
QFrame#historyAnalysisPage {
  background: transparent;
  border: none;
}
QFrame#historyHeaderPanel,
QFrame#historyStatsPanel,
QFrame#historyAnalyticsPanel,
QFrame#historyGraphPanel,
QFrame#historyToolbar,
QScrollArea#historyRecordsPanel {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #071421,
    stop:0.42 #0B2238,
    stop:1 #0A3741);
  border: 1px solid rgba(98, 144, 176, 36);
  border-radius: 18px;
}
QWidget#historyRecordsViewport {
  background: transparent;
}
QLabel#historyTitle {
  color: #F8FBFF;
  font-size: 20px;
  font-weight: 900;
}
QLabel#historySubtitle,
QLabel#historyChartSubtitle,
QLabel#historyRecordDetail,
QLabel#historyEmptyHint {
  color: #9CB3C6;
  font-size: 12px;
  font-weight: 700;
}
QLabel#historyCountChip,
QLabel#historySectionCount,
QLabel#historyExportCount,
QLabel#historyAnalyticsCount,
QLabel#historyGraphCountChip {
  color: #EBFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #155E75,
    stop:1 #047857);
  border: none;
  border-radius: 10px;
  min-width: 72px;
  min-height: 34px;
  font-size: 14px;
  font-weight: 900;
  padding: 0 12px;
}
QFrame#historyMetricShell,
QFrame#historyMetricShellP1,
QFrame#historyMetricShellP2,
QFrame#historyMetricShellP3,
QFrame#historyMetricShellOverdue {
  border: none;
  border-radius: 16px;
  min-height: 68px;
}
QFrame#historyMetricShellP1 {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6B2E12, stop:1 #9A4C14);
}
QFrame#historyMetricShellP2 {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #20367E, stop:1 #3657B7);
}
QFrame#historyMetricShellP3 {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0D4A3D, stop:1 #15805C);
}
QFrame#historyMetricShell {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #17203B, stop:1 #0D4655);
}
QFrame#historyMetricShellOverdue {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #51172A, stop:1 #8B1D35);
}
QLabel#historyPriorityMetricP1,
QLabel#historyPriorityMetricP2,
QLabel#historyPriorityMetricP3,
QLabel#historyMetricChip,
QLabel#historyOverdueMetric {
  background: transparent;
  font-weight: 900;
  font-size: 16px;
}
QLabel#historyPriorityMetricP1 { color: #FFE1A6; }
QLabel#historyPriorityMetricP2 { color: #DCE7FF; }
QLabel#historyPriorityMetricP3 { color: #D9FBE8; }
QLabel#historyMetricChip { color: #DBEAFE; }
QLabel#historyOverdueMetric { color: #FFD5DF; }
QLabel#historyAnalyticsTitle,
QLabel#historySectionTitle,
QLabel#historyChartTitle,
QLabel#historyToolbarLabel,
QLabel#historyEmptyTitle {
  color: #F8FBFF;
  font-size: 15px;
  font-weight: 900;
}
QPushButton#historyAnalyticsPresetButton,
QPushButton#historyActionButton,
QPushButton#historyPageButton,
QPushButton#historyExportButton {
  color: #F6FBFF;
  background: #162033;
  border: none;
  border-radius: 12px;
  min-height: 38px;
  padding: 0 14px;
  font-weight: 900;
}
QPushButton#historyExportButton {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:1 #0F766E);
}
QPushButton#historyAnalyticsPresetButton:hover,
QPushButton#historyActionButton:hover,
QPushButton#historyPageButton:hover,
QPushButton#historyExportButton:hover {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1B3450,
    stop:1 #0E6070);
}
QFrame#historyExportDateChip {
  background: rgba(9, 27, 41, 0.92);
  border: 1px solid rgba(98, 144, 176, 26);
  border-radius: 12px;
}
QLabel#historyExportDateLabel {
  color: #B9F7E8;
  background: rgba(17, 63, 80, 0.95);
  border: none;
  border-radius: 8px;
  font-weight: 900;
}
QLabel#historyAnalyticsArrow,
QLabel#historyExportArrow {
  color: #A7F3D0;
  min-width: 22px;
  font-size: 18px;
  font-weight: 900;
}
QLineEdit#historySearch,
QComboBox#historyStatusFilter,
QComboBox#historyPriorityFilter,
QComboBox#historyTagFilter,
QComboBox#historySortMode,
QComboBox#historyPageSize,
QDateEdit#historyAnalyticsStartDate,
QDateEdit#historyAnalyticsEndDate,
QDateEdit#historyExportStartDate,
QDateEdit#historyExportEndDate,
QSpinBox#historyPageJump {
  background: #121A2B;
  color: #ECFEFF;
  font-weight: 700;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(110, 156, 184, 32);
  border-radius: 10px;
}
QDateEdit#historyAnalyticsStartDate::up-button,
QDateEdit#historyAnalyticsStartDate::down-button,
QDateEdit#historyAnalyticsStartDate::up-arrow,
QDateEdit#historyAnalyticsStartDate::down-arrow,
QDateEdit#historyAnalyticsEndDate::up-button,
QDateEdit#historyAnalyticsEndDate::down-button,
QDateEdit#historyAnalyticsEndDate::up-arrow,
QDateEdit#historyAnalyticsEndDate::down-arrow,
QDateEdit#historyExportStartDate::up-button,
QDateEdit#historyExportStartDate::down-button,
QDateEdit#historyExportStartDate::up-arrow,
QDateEdit#historyExportStartDate::down-arrow,
QDateEdit#historyExportEndDate::up-button,
QDateEdit#historyExportEndDate::down-button,
QDateEdit#historyExportEndDate::up-arrow,
QDateEdit#historyExportEndDate::down-arrow {
  width: 0;
  height: 0;
  border: none;
  image: none;
}
QLabel#historyPageLabel {
  color: #D8E7F5;
  background: rgba(12, 23, 38, 0.95);
  border: 1px solid rgba(110, 156, 184, 26);
  border-radius: 12px;
  padding: 8px 12px;
  font-weight: 900;
}
QFrame#historyChartsPanel {
  border: none;
  background: transparent;
}
QFrame#historyChartCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #081725,
    stop:0.58 #0D2134,
    stop:1 #0A3540);
  border: 1px solid rgba(93, 145, 175, 0.16);
  border-radius: 16px;
}
QFrame#historyChartCard[historyTone="priority"] {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #3A1608,
    stop:0.45 #71310F,
    stop:1 #5B1A2A);
}
QFrame#historyChartCard[historyTone="trend"] {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #04235C,
    stop:0.52 #075985,
    stop:1 #0E7490);
}
QFrame#historyChartCard[historyTone="deadline"] {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #073B34,
    stop:0.5 #0F766E,
    stop:1 #166534);
}
QFrame#historyChartCard[historyTone="tag"] {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #111827,
    stop:0.46 #162A52,
    stop:1 #0B4A5E);
}
QFrame#historyPagerPanel {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #101A33,
    stop:0.4 #14365C,
    stop:1 #115E59);
  border: 1px solid rgba(98, 144, 176, 26);
  border-radius: 16px;
}
QFrame#historyCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #081725,
    stop:0.58 #0D2134,
    stop:1 #0A3540);
  border: 1px solid rgba(98, 144, 176, 26);
  border-radius: 16px;
}
QFrame#historyAccentP1 { background: #F6A44D; border-radius: 2px; }
QFrame#historyAccentP2 { background: #8EA7FF; border-radius: 2px; }
QFrame#historyAccentP3 { background: #A7F3D0; border-radius: 2px; }
QFrame#historyPriorityBadgeP1,
QFrame#historyPriorityBadgeP2,
QFrame#historyPriorityBadgeP3 {
  border: none;
  border-radius: 10px;
  min-height: 28px;
}
QFrame#historyPriorityBadgeP1 { background: #5A2D12; }
QFrame#historyPriorityBadgeP2 { background: #1B2F69; }
QFrame#historyPriorityBadgeP3 { background: #123B34; }
QLabel#historyRecordTitle {
  color: #F8FBFF;
  font-size: 17px;
  font-weight: 900;
}
QLabel#historyPriorityP1,
QLabel#historyPriorityP2,
QLabel#historyPriorityP3,
QLabel#historyReviewChipDone,
QLabel#historyReviewChipEmpty,
QLabel#historyTagChip,
QLabel#historyStatusOnTime,
QLabel#historyStatusOverdue,
QLabel#historyStatusNeutral {
  border: none;
  border-radius: 10px;
  padding: 0 10px;
  font-weight: 900;
}
QLabel#historyPriorityP1 { color: #FFE1A6; background: #5A2D12; }
QLabel#historyPriorityP2 { color: #DCE7FF; background: #1B2F69; }
QLabel#historyPriorityP3 { color: #D9FBE8; background: #123B34; }
QLabel#historyReviewChipDone { color: #D7FEE6; background: #0D5947; min-height: 28px; }
QLabel#historyReviewChipEmpty { color: #FDE68A; background: #6B4E16; min-height: 28px; }
QLabel#historyTagChip { color: #BFF7FF; background: #114357; min-height: 28px; }
QLabel#historyStatusOnTime { color: #D7FEE6; background: #0D5947; }
QLabel#historyStatusOverdue { color: #FFD5DF; background: #7C1D34; }
QLabel#historyStatusNeutral { color: #D6E4F4; background: #334155; }
QLabel#historyRecordMeta {
  color: #AFC4D7;
  font-size: 12px;
  font-weight: 700;
}
QLabel#historyRecordMetaStrong {
  color: #EFFBFF;
  font-size: 13px;
  font-weight: 900;
}
QLabel#historyInlineIcon {
  background: rgba(12, 39, 63, 0.88);
  border: 1px solid rgba(103, 232, 249, 24);
  border-radius: 12px;
}
QFrame#historyPreview {
  background: rgba(9, 20, 33, 0.7);
  border: 1px solid rgba(110, 156, 184, 18);
  border-radius: 10px;
}
QLabel#historyPreviewText {
  color: #D8E7F5;
  font-size: 12px;
  font-weight: 700;
}
QToolButton#historyMoreButton {
  color: #F6FBFF;
  background: rgba(20, 37, 57, 0.95);
  border: 1px solid rgba(110, 156, 184, 26);
  border-radius: 12px;
  min-width: 38px;
  min-height: 38px;
}
QToolButton#historyMoreButton:hover {
  background: rgba(18, 96, 112, 0.95);
}
QLabel#historyPriorityP1,
QLabel#historyPriorityP2,
QLabel#historyPriorityP3 {
  background: transparent;
  padding: 0;
}
QLabel#historyMetricIcon,
QLabel#historyPriorityIcon {
  background: rgba(9, 27, 41, 0.46);
  border: 1px solid rgba(210, 236, 252, 0.12);
  border-radius: 12px;
}
QFrame#historyEmptyState {
  background: rgba(9, 20, 33, 0.7);
  border: 1px dashed rgba(110, 156, 184, 42);
  border-radius: 18px;
}
"""
