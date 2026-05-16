from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from floating_todo.app_identity import APP_DISPLAY_NAME, resolved_icon_path
from floating_todo.notifications import NotificationSender
from floating_todo.settings import settings_from_dict
from floating_todo.store import JsonTaskStore, load_json_object
from floating_todo.theme import CALM_TECH_QSS
from floating_todo.ui.effects import install_global_interaction_effects, prepare_window_entrance
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
    return resolved_icon_path()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setStyleSheet(CALM_TECH_QSS)
    install_global_interaction_effects(app)
    data_dir = ensure_data_files()
    store = JsonTaskStore(data_dir / "tasks.json")
    settings_path = data_dir / "settings.json"
    settings = settings_from_dict(load_json_object(settings_path, {}))
    notification_sender = NotificationSender()
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(store, settings, settings_path, notification_sender)
    icon = QIcon(str(resolved_icon_path(settings.icon_path)))
    try:
        window.tray_controller = TrayController(window, icon)
    except Exception:
        window.tray_controller = None
    apply_window_behavior_settings = getattr(window, "apply_window_behavior_settings", None)
    if callable(apply_window_behavior_settings):
        apply_window_behavior_settings()
    prepare_window_entrance(window, target_opacity=settings.opacity, slide=0, duration=260)
    window.show()
    return app.exec()
