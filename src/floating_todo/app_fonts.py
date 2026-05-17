from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from floating_todo.theme import APP_FONT_FAMILY


APP_FONT_FILES = (
    "AlibabaPuHuiTi-3-55-Regular.ttf",
    "AlibabaPuHuiTi-3-65-Medium.ttf",
    "AlibabaPuHuiTi-3-85-Bold.ttf",
)


def font_assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "fonts"


def install_app_fonts(app=None) -> list[str]:
    if app is not None and not callable(getattr(app, "setFont", None)):
        return []

    families: list[str] = []
    for filename in APP_FONT_FILES:
        font_path = font_assets_dir() / filename
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id < 0:
            continue
        families.extend(QFontDatabase.applicationFontFamilies(font_id))

    if app is not None and APP_FONT_FAMILY in families:
        font = QFont(APP_FONT_FAMILY)
        font.setPointSize(10)
        app.setFont(font)
    return sorted(set(families))
