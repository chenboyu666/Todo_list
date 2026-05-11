from pathlib import Path

from floating_todo.settings import settings_to_dict
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


def test_main_loads_settings_json_and_passes_settings_path(monkeypatch, tmp_path):
    import floating_todo.app as app_module
    import floating_todo.ui.main_window as main_window_module

    settings_path = tmp_path / "data" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"always_on_top": false, "opacity": 0.7}', encoding="utf-8")
    captured = {}

    class FakeApplication:
        def __init__(self, argv):
            self.argv = argv
            self.application_name = None
            self.style_sheet = None

        def setApplicationName(self, name):
            self.application_name = name

        def setStyleSheet(self, qss):
            self.style_sheet = qss

        def exec(self):
            return 0

    class FakeMainWindow:
        def __init__(self, store, settings, path):
            captured["store_path"] = store.path
            captured["settings"] = settings
            captured["settings_path"] = path
            self.shown = False

        def show(self):
            captured["shown"] = True

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "ensure_data_files", lambda: tmp_path / "data")
    monkeypatch.setattr(main_window_module, "MainWindow", FakeMainWindow)

    assert app_module.main() == 0

    assert captured["store_path"] == tmp_path / "data" / "tasks.json"
    assert captured["settings_path"] == settings_path
    assert settings_to_dict(captured["settings"])["always_on_top"] is False
    assert settings_to_dict(captured["settings"])["opacity"] == 0.7
    assert captured["shown"] is True
