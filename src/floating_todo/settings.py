from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


DEFAULT_GEOMETRY = {"x": 1200, "y": 120, "width": 410, "height": 620}


@dataclass(frozen=True)
class AppSettings:
    always_on_top: bool = True
    lock_position: bool = False
    close_to_tray: bool = True
    launch_on_startup: bool = False
    opacity: float = 0.96
    low_distraction_mode: bool = False
    notification_lead_minutes: int = 15
    window_geometry: Mapping[str, int] = field(default_factory=lambda: MappingProxyType(dict(DEFAULT_GEOMETRY)))
    theme: str = "calm-tech-dark"

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
    return AppSettings(
        always_on_top=_coerce_bool(data.get("always_on_top", True), True),
        lock_position=_coerce_bool(data.get("lock_position", False), False),
        close_to_tray=_coerce_bool(data.get("close_to_tray", True), True),
        launch_on_startup=_coerce_bool(data.get("launch_on_startup", False), False),
        opacity=opacity,
        low_distraction_mode=_coerce_bool(data.get("low_distraction_mode", False), False),
        notification_lead_minutes=max(1, _coerce_int(data.get("notification_lead_minutes", 15), 15)),
        window_geometry=geometry,
        theme=str(data.get("theme", "calm-tech-dark")),
    )


def settings_to_dict(settings: AppSettings) -> dict[str, object]:
    return {
        "always_on_top": settings.always_on_top,
        "lock_position": settings.lock_position,
        "close_to_tray": settings.close_to_tray,
        "launch_on_startup": settings.launch_on_startup,
        "opacity": settings.opacity,
        "low_distraction_mode": settings.low_distraction_mode,
        "notification_lead_minutes": settings.notification_lead_minutes,
        "window_geometry": dict(settings.window_geometry),
        "theme": settings.theme,
    }
