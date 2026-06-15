from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from floating_todo.settings import DEFAULT_UI_SCALE, MAX_UI_SCALE, MIN_UI_SCALE


def clamp_ui_scale(scale: float) -> float:
    return round(max(MIN_UI_SCALE, min(MAX_UI_SCALE, float(scale))), 2)


def ui_scale_from_parent(parent: QWidget | None, fallback: float = MAX_UI_SCALE) -> float:
    settings = getattr(parent, "settings", None)
    return ui_scale_from_settings(settings, fallback=fallback)


def ui_scale_from_settings(settings, *, fallback: float = DEFAULT_UI_SCALE) -> float:
    return clamp_ui_scale(getattr(settings, "ui_scale", fallback))


def scaled_size(width: int, height: int, scale: float) -> QSize:
    clamped = clamp_ui_scale(scale)
    return QSize(max(1, round(width * clamped)), max(1, round(height * clamped)))


def apply_scaled_window_size(
    window: QWidget,
    scale: float,
    *,
    minimum: tuple[int, int],
    default: tuple[int, int],
) -> None:
    window.setMinimumSize(scaled_size(*minimum, scale))
    window.resize(scaled_size(*default, scale))
