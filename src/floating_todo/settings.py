from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any


DEFAULT_GEOMETRY = {"x": 980, "y": 60, "width": 820, "height": 1040}
DEFAULT_LOW_DISTRACTION_MODE = False
DEFAULT_NOTIFICATION_REPEAT_MINUTES = 10
DEFAULT_BACKGROUND_OVERLAY = 0.68
DEFAULT_UI_SCALE = 1.0
MIN_UI_SCALE = 0.85
MAX_UI_SCALE = 1.3


@dataclass(frozen=True)
class AppSettings:
    always_on_top: bool = True
    mouse_passthrough: bool = False
    lock_position: bool = False
    close_to_tray: bool = True
    launch_on_startup: bool = False
    opacity: float = 0.96
    low_distraction_mode: bool = DEFAULT_LOW_DISTRACTION_MODE
    notification_lead_minutes: int = 15
    notification_repeat_minutes: int = DEFAULT_NOTIFICATION_REPEAT_MINUTES
    window_geometry: Mapping[str, int] = field(default_factory=lambda: MappingProxyType(dict(DEFAULT_GEOMETRY)))
    theme: str = "calm-tech-dark"
    focus_task_id: str | None = None
    background_image_path: str = ""
    background_enabled: bool = False
    background_random_enabled: bool = False
    background_folder_path: str = ""
    background_overlay: float = DEFAULT_BACKGROUND_OVERLAY
    icon_path: str = ""
    ui_scale: float = DEFAULT_UI_SCALE

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_geometry", MappingProxyType(dict(self.window_geometry)))


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        return default
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def settings_from_dict(data: dict[str, Any] | None) -> AppSettings:
    if not isinstance(data, dict):
        data = {}
    geometry = dict(DEFAULT_GEOMETRY)
    raw_geometry = data.get("window_geometry")
    if isinstance(raw_geometry, dict):
        for key in ("x", "y", "width", "height"):
            if key in raw_geometry:
                geometry[key] = _coerce_int(raw_geometry[key], DEFAULT_GEOMETRY[key])
    opacity = _coerce_float(data.get("opacity", 0.96), 0.96)
    opacity = max(0.3, min(1.0, opacity))
    ui_scale = _coerce_float(data.get("ui_scale", DEFAULT_UI_SCALE), DEFAULT_UI_SCALE)
    ui_scale = round(max(MIN_UI_SCALE, min(MAX_UI_SCALE, ui_scale)), 2)
    raw_focus_task_id = data.get("focus_task_id")
    raw_background_path = data.get("background_image_path", "")
    raw_background_folder_path = data.get("background_folder_path", "")
    raw_icon_path = data.get("icon_path", "")
    return AppSettings(
        always_on_top=_coerce_bool(data.get("always_on_top", True), True),
        mouse_passthrough=_coerce_bool(data.get("mouse_passthrough", False), False),
        lock_position=_coerce_bool(data.get("lock_position", False), False),
        close_to_tray=_coerce_bool(data.get("close_to_tray", True), True),
        launch_on_startup=_coerce_bool(data.get("launch_on_startup", False), False),
        opacity=opacity,
        low_distraction_mode=DEFAULT_LOW_DISTRACTION_MODE,
        notification_lead_minutes=max(1, _coerce_int(data.get("notification_lead_minutes", 15), 15)),
        notification_repeat_minutes=DEFAULT_NOTIFICATION_REPEAT_MINUTES,
        window_geometry=geometry,
        theme=str(data.get("theme", "calm-tech-dark")),
        focus_task_id=str(raw_focus_task_id) if raw_focus_task_id else None,
        background_image_path=str(raw_background_path) if raw_background_path else "",
        background_enabled=_coerce_bool(data.get("background_enabled", False), False),
        background_random_enabled=_coerce_bool(data.get("background_random_enabled", False), False),
        background_folder_path=str(raw_background_folder_path) if raw_background_folder_path else "",
        background_overlay=DEFAULT_BACKGROUND_OVERLAY,
        icon_path=str(raw_icon_path) if raw_icon_path else "",
        ui_scale=ui_scale,
    )


def remove_deprecated_setting_features(settings: AppSettings) -> AppSettings:
    return replace(
        settings,
        low_distraction_mode=DEFAULT_LOW_DISTRACTION_MODE,
        notification_repeat_minutes=DEFAULT_NOTIFICATION_REPEAT_MINUTES,
        background_overlay=DEFAULT_BACKGROUND_OVERLAY,
    )


def settings_to_dict(settings: AppSettings) -> dict[str, object]:
    return {
        "always_on_top": settings.always_on_top,
        "mouse_passthrough": settings.mouse_passthrough,
        "lock_position": settings.lock_position,
        "close_to_tray": settings.close_to_tray,
        "launch_on_startup": settings.launch_on_startup,
        "opacity": settings.opacity,
        "low_distraction_mode": DEFAULT_LOW_DISTRACTION_MODE,
        "notification_lead_minutes": settings.notification_lead_minutes,
        "notification_repeat_minutes": DEFAULT_NOTIFICATION_REPEAT_MINUTES,
        "window_geometry": dict(settings.window_geometry),
        "theme": settings.theme,
        "focus_task_id": settings.focus_task_id,
        "background_image_path": settings.background_image_path,
        "background_enabled": settings.background_enabled,
        "background_random_enabled": settings.background_random_enabled,
        "background_folder_path": settings.background_folder_path,
        "background_overlay": DEFAULT_BACKGROUND_OVERLAY,
        "icon_path": settings.icon_path,
        "ui_scale": settings.ui_scale,
    }
