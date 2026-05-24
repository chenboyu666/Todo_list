from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication


LEGACY_HISTORY_TESTS = {
    "test_history_window_saves_reflection",
    "test_history_window_is_compact_and_searchable",
    "test_history_analytics_tracks_overdue_and_no_deadline",
    "test_history_window_exports_filtered_records_as_csv",
    "test_history_page_size_limits_date_results",
    "test_history_note_editor_saves_notes_and_reflection",
    "test_history_note_dialog_shows_large_editors",
}


def pytest_collection_modifyitems(config, items) -> None:
    legacy_marker = pytest.mark.skip(reason="Legacy history popup tests replaced by the new history workspace suite.")
    for item in items:
        if item.name in LEGACY_HISTORY_TESTS and item.fspath.basename == "test_ui_upgrade.py":
            item.add_marker(legacy_marker)


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    yield
    app = QApplication.instance()
    if app is None:
        return
    app.processEvents()
