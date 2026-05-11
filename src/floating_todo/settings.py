from __future__ import annotations

from dataclasses import dataclass, field
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
    window_geometry: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_GEOMETRY))
    theme: str = "calm-tech-dark"


def settings_from_dict(data: dict[str, Any] | None) -> AppSettings:
    data = data or {}
    geometry = dict(DEFAULT_GEOMETRY)
    raw_geometry = data.get("window_geometry")
    if isinstance(raw_geometry, dict):
        for key in ("x", "y", "width", "height"):
            if key in raw_geometry:
                geometry[key] = int(raw_geometry[key])
    opacity = float(data.get("opacity", 0.96))
    opacity = max(0.3, min(1.0, opacity))
    return AppSettings(
        always_on_top=bool(data.get("always_on_top", True)),
        lock_position=bool(data.get("lock_position", False)),
        close_to_tray=bool(data.get("close_to_tray", True)),
        launch_on_startup=bool(data.get("launch_on_startup", False)),
        opacity=opacity,
        low_distraction_mode=bool(data.get("low_distraction_mode", False)),
        notification_lead_minutes=max(1, int(data.get("notification_lead_minutes", 15))),
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
