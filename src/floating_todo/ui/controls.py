from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle


class NoWheelSlider(QSlider):
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setSliderDown(True)
            self._set_value_from_position(event.position().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.LeftButton:
            self._set_value_from_position(event.position().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._set_value_from_position(event.position().toPoint())
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        event.ignore()

    def _set_value_from_position(self, point) -> None:
        if self.orientation() == Qt.Horizontal:
            span = max(1, self.width())
            position = max(0, min(point.x(), span))
            value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), position, span)
        else:
            span = max(1, self.height())
            position = max(0, min(point.y(), span))
            value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), span - position, span)
        self.setValue(value)
