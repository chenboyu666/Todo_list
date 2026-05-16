from __future__ import annotations

from pathlib import Path

from floating_todo.app_resources import resolve_resource_path

APP_DISPLAY_NAME = "Todo list"
APP_STARTUP_NAME = APP_DISPLAY_NAME
ICON_FILE_FILTER = "Icons and Images (*.ico *.png *.jpg *.jpeg *.bmp *.webp *.gif *.svg);;All Files (*)"


def default_app_icon_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "app_icon.svg"


def resolved_icon_path(icon_path: str = "") -> Path:
    custom_path = resolve_resource_path(icon_path) if icon_path else None
    if custom_path is not None and custom_path.exists():
        return custom_path
    return default_app_icon_path()
