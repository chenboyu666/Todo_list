from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from floating_todo.notifications import NotificationSender
from floating_todo.settings import settings_from_dict
from floating_todo.store import JsonTaskStore, load_json_object
from floating_todo.theme import CALM_TECH_QSS
from floating_todo.ui.tray import TrayController


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


def app_icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "app_icon.svg"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FloatingTodo")
    app.setStyleSheet(CALM_TECH_QSS)
    data_dir = ensure_data_files()
    store = JsonTaskStore(data_dir / "tasks.json")
    settings_path = data_dir / "settings.json"
    settings = settings_from_dict(load_json_object(settings_path, {}))
    notification_sender = NotificationSender()
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(store, settings, settings_path, notification_sender)
    icon = QIcon(str(app_icon_path()))
    try:
        window.tray_controller = TrayController(window, icon)
    except Exception:
        window.tray_controller = None
    window.show()
    return app.exec()
