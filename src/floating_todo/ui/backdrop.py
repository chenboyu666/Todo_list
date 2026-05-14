from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from floating_todo.theme import THEME_COLORS


class AnimatedBackdrop(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.background_image_path = ""
        self.background_enabled = False
        self.background_overlay = 0.68
        self._phase = 0
        self._pixmap = QPixmap()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    def set_background_settings(self, enabled: bool, image_path: str, overlay: float) -> None:
        self.background_enabled = enabled
        self.background_image_path = image_path
        self.background_overlay = max(0.25, min(0.95, overlay))
        path = Path(image_path)
        self._pixmap = QPixmap(str(path)) if enabled and path.exists() else QPixmap()
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 10000
        self.update()

    def stop_animation(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if rect.isEmpty():
            return

        if self.background_enabled and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            overlay_alpha = int(self.background_overlay * 255)
            painter.fillRect(rect, QColor(8, 10, 15, overlay_alpha))
        else:
            base = QLinearGradient(rect.topLeft(), rect.bottomRight())
            base.setColorAt(0, QColor(THEME_COLORS["background"]))
            base.setColorAt(0.52, QColor("#10151F"))
            base.setColorAt(1, QColor("#0B1117"))
            painter.fillRect(rect, base)

        self._draw_grid(painter, rect.width(), rect.height())
        self._draw_scan(painter, rect.width(), rect.height())
        painter.end()

    def _draw_grid(self, painter: QPainter, width: int, height: int) -> None:
        spacing = 28
        offset = self._phase % spacing
        painter.setPen(QPen(QColor(125, 211, 252, 18), 1))
        for x in range(-offset, width + spacing, spacing):
            painter.drawLine(x, 0, x, height)
        for y in range(-offset, height + spacing, spacing):
            painter.drawLine(0, y, width, y)

    def _draw_scan(self, painter: QPainter, width: int, height: int) -> None:
        if height <= 0:
            return
        y = (self._phase * 3) % (height + 80) - 40
        scan = QLinearGradient(0, y, width, y)
        scan.setColorAt(0, QColor(125, 211, 252, 0))
        scan.setColorAt(0.5, QColor(167, 243, 208, 70))
        scan.setColorAt(1, QColor(246, 193, 119, 0))
        painter.setPen(QPen(scan, 2))
        painter.drawLine(0, y, width, y)
