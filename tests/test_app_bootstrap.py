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
    assert THEME_COLORS["background"] == "#080A0F"
    assert THEME_COLORS["accent"] == "#7DD3FC"
    assert THEME_RADIUS["control"] == "8px"
    assert THEME_SPACING["control_padding"] == "5px 12px"
    assert THEME_FONT["family"] == '"Microsoft YaHei UI", "Segoe UI"'

    assert f"background: {THEME_COLORS['background']};" in CALM_TECH_QSS
    assert f"border-radius: {THEME_RADIUS['control']};" in CALM_TECH_QSS
    assert f"font-family: {THEME_FONT['family']};" in CALM_TECH_QSS
    assert "border: 1px" not in CALM_TECH_QSS


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
        def __init__(self, store, settings, path, notification_sender):
            captured["store_path"] = store.path
            captured["settings"] = settings
            captured["settings_path"] = path
            captured["notification_sender"] = notification_sender
            self.shown = False

        def show(self):
            captured["shown"] = True

    class FakeNotificationSender:
        pass

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "QIcon", lambda path: path)
    monkeypatch.setattr(app_module, "TrayController", lambda window, icon: object())
    monkeypatch.setattr(app_module, "NotificationSender", FakeNotificationSender)
    monkeypatch.setattr(app_module, "ensure_data_files", lambda: tmp_path / "data")
    monkeypatch.setattr(main_window_module, "MainWindow", FakeMainWindow)

    assert app_module.main() == 0

    assert captured["store_path"] == tmp_path / "data" / "tasks.json"
    assert captured["settings_path"] == settings_path
    assert settings_to_dict(captured["settings"])["always_on_top"] is False
    assert settings_to_dict(captured["settings"])["opacity"] == 0.7
    assert isinstance(captured["notification_sender"], FakeNotificationSender)
    assert captured["shown"] is True


def test_main_wires_tray_controller_before_showing_window(monkeypatch, tmp_path):
    import floating_todo.app as app_module
    import floating_todo.ui.main_window as main_window_module

    captured = {}

    class FakeApplication:
        def __init__(self, argv):
            self.argv = argv

        def setApplicationName(self, name):
            pass

        def setStyleSheet(self, qss):
            pass

        def exec(self):
            return 0

    class FakeMainWindow:
        def __init__(self, store, settings, path, notification_sender):
            self.tray_controller = None

        def show(self):
            captured["tray_before_show"] = self.tray_controller
            captured["shown"] = True

    class FakeIcon:
        def __init__(self, path):
            self.path = path

    class FakeTrayController:
        def __init__(self, window, icon):
            captured["window"] = window
            captured["icon"] = icon

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "QIcon", FakeIcon)
    monkeypatch.setattr(app_module, "TrayController", FakeTrayController)
    monkeypatch.setattr(app_module, "NotificationSender", lambda: object())
    monkeypatch.setattr(app_module, "ensure_data_files", lambda: tmp_path / "data")
    monkeypatch.setattr(main_window_module, "MainWindow", FakeMainWindow)

    assert app_module.main() == 0

    assert captured["shown"] is True
    assert isinstance(captured["tray_before_show"], FakeTrayController)
    assert captured["tray_before_show"] is captured["window"].tray_controller
    assert captured["icon"].path == str(app_module.app_icon_path())


def test_main_continues_without_tray_controller_when_tray_creation_fails(monkeypatch, tmp_path):
    import floating_todo.app as app_module
    import floating_todo.ui.main_window as main_window_module

    captured = {}

    class FakeApplication:
        def __init__(self, argv):
            pass

        def setApplicationName(self, name):
            pass

        def setStyleSheet(self, qss):
            pass

        def exec(self):
            return 0

    class FakeMainWindow:
        def __init__(self, store, settings, path, notification_sender):
            self.tray_controller = "unset"

        def show(self):
            captured["tray_before_show"] = self.tray_controller
            captured["shown"] = True

    def failing_tray_controller(window, icon):
        raise RuntimeError("system tray unavailable")

    monkeypatch.setattr(app_module, "QApplication", FakeApplication)
    monkeypatch.setattr(app_module, "QIcon", lambda path: path)
    monkeypatch.setattr(app_module, "TrayController", failing_tray_controller)
    monkeypatch.setattr(app_module, "NotificationSender", lambda: object())
    monkeypatch.setattr(app_module, "ensure_data_files", lambda: tmp_path / "data")
    monkeypatch.setattr(main_window_module, "MainWindow", FakeMainWindow)

    assert app_module.main() == 0

    assert captured["shown"] is True
    assert captured["tray_before_show"] is None


def test_package_data_includes_app_icon_svg():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.setuptools.package-data]" in pyproject
    assert 'floating_todo = ["assets/app_icon.svg"]' in pyproject
