from __future__ import annotations

from math import sin

from PySide6.QtCore import QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QMovie, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from floating_todo.app_resources import resolve_resource_path
from floating_todo.theme import THEME_COLORS


class AnimatedBackdrop(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.background_image_path = ""
        self.background_enabled = False
        self.background_overlay = 0.68
        self._phase = 0
        self._pixmap = QPixmap()
        self._movie: QMovie | None = None
        self._click_pulses: list[tuple[QPointF, int]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    def set_background_settings(self, enabled: bool, image_path: str, overlay: float) -> None:
        self.background_enabled = enabled
        self.background_image_path = image_path
        self.background_overlay = max(0.25, min(0.95, overlay))
        path = resolve_resource_path(image_path)
        self._stop_movie()
        self._pixmap = QPixmap()
        if enabled and path.exists():
            if path.suffix.lower() == ".gif":
                self._movie = QMovie(str(path))
                self._movie.setCacheMode(QMovie.CacheAll)
                self._movie.frameChanged.connect(lambda frame_number: self.update())
                self._movie.start()
            else:
                self._pixmap = QPixmap(str(path))
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 10000
        self._click_pulses = [(point, life - 1) for point, life in self._click_pulses if life > 1]
        self.update()

    def stop_animation(self) -> None:
        self._timer.stop()
        self._stop_movie()

    def add_click_pulse(self, point: QPoint | QPointF) -> None:
        self._click_pulses.append((QPointF(point), 11))
        self._click_pulses = self._click_pulses[-8:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        if rect.isEmpty():
            return

        background = self._current_background_pixmap()
        if self.background_enabled and not background.isNull():
            scaled = background.scaled(rect.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
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
        self._draw_particles(painter, rect.width(), rect.height())
        self._draw_click_pulses(painter)
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

    def _draw_particles(self, painter: QPainter, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        painter.setPen(Qt.NoPen)
        for index in range(22):
            seed = index * 53 + 17
            speed = 0.18 + (index % 5) * 0.045
            x = (seed * 19 + self._phase * speed) % (width + 48) - 24
            wave = sin((self._phase + seed) / 42)
            y = (seed * 31 + self._phase * (0.12 + (index % 3) * 0.035)) % (height + 52) - 26
            radius = 1.3 + (index % 4) * 0.45
            alpha = 32 + int((wave + 1) * 18)
            if index % 3 == 0:
                color = QColor(125, 211, 252, alpha)
            elif index % 3 == 1:
                color = QColor(167, 243, 208, alpha)
            else:
                color = QColor(246, 193, 119, alpha)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(float(x), float(y)), radius, radius)

    def _draw_click_pulses(self, painter: QPainter) -> None:
        painter.setBrush(Qt.NoBrush)
        for point, life in self._click_pulses:
            progress = 1 - (life / 11)
            radius = 14 + progress * 98
            cyan = QColor(125, 211, 252, int(120 * (1 - progress)))
            mint = QColor(167, 243, 208, int(70 * (1 - progress)))
            painter.setPen(QPen(cyan, 1.8))
            painter.drawEllipse(point, radius, radius)
            painter.setPen(QPen(mint, 1.0))
            painter.drawEllipse(point, radius * 0.62, radius * 0.62)

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

    def _current_background_pixmap(self) -> QPixmap:
        if self._movie is not None:
            return self._movie.currentPixmap()
        return self._pixmap

    def _stop_movie(self) -> None:
        if self._movie is None:
            return
        self._movie.stop()
        self._movie.deleteLater()
        self._movie = None
