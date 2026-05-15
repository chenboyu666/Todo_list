from __future__ import annotations

from PySide6.QtWidgets import QSlider


class NoWheelSlider(QSlider):
    def wheelEvent(self, event) -> None:
        event.ignore()
