from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    yield
    app = QApplication.instance()
    if app is None:
        return
    app.processEvents()
