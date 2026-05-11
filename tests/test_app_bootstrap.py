from pathlib import Path

from floating_todo.app import app_data_dir, ensure_data_files
from floating_todo.theme import (
    CALM_TECH_QSS,
    THEME_COLORS,
    THEME_FONT,
    THEME_RADIUS,
    THEME_SPACING,
)


def test_app_data_dir_uses_base_path_data_folder(tmp_path):
    assert app_data_dir(tmp_path) == tmp_path / "data"


def test_ensure_data_files_creates_data_folder(tmp_path):
    data_dir = ensure_data_files(tmp_path)

    assert data_dir == tmp_path / "data"
    assert data_dir.exists()


def test_theme_exposes_reusable_tokens_used_by_qss():
    assert THEME_COLORS["background"] == "#0E1223"
    assert THEME_COLORS["accent"] == "#22D3EE"
    assert THEME_RADIUS["control"] == "8px"
    assert THEME_SPACING["control_padding"] == "4px 10px"
    assert THEME_FONT["family"] == '"Segoe UI"'

    assert f"background: {THEME_COLORS['background']};" in CALM_TECH_QSS
    assert f"border-radius: {THEME_RADIUS['control']};" in CALM_TECH_QSS
    assert f"font-family: {THEME_FONT['family']};" in CALM_TECH_QSS
