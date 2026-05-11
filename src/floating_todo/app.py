from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from floating_todo.store import JsonTaskStore
from floating_todo.theme import CALM_TECH_QSS


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def app_data_dir(base_path: Path | None = None) -> Path:
    return (base_path or app_base_dir()) / "data"


def ensure_data_files(base_path: Path | None = None) -> Path:
    data_dir = app_data_dir(base_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FloatingTodo")
    app.setStyleSheet(CALM_TECH_QSS)
    data_dir = ensure_data_files()
    store = JsonTaskStore(data_dir / "tasks.json")
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(store)
    window.show()
    return app.exec()
