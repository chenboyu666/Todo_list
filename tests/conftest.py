from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    yield
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        if hasattr(widget, "settings"):
            widget.settings = replace(widget.settings, close_to_tray=False)
        timer = getattr(widget, "_clock_timer", None)
        if timer is not None:
            timer.stop()
        root_widget = getattr(widget, "root_widget", None)
        stop_animation = getattr(root_widget, "stop_animation", None)
        if stop_animation is not None:
            stop_animation()
        widget.close()
        widget.deleteLater()
    app.processEvents()
