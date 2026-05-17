import sys
from pathlib import Path

import pytest

from floating_todo import platform_windows
from floating_todo.platform_windows import set_launch_on_startup
from floating_todo.settings import AppSettings, settings_from_dict, settings_to_dict


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 1
    REG_SZ = 1

    def __init__(self):
        self.values = {}
        self.deleted = []
        self.closed = []
        self.raise_on_set = False
        self.missing_on_delete = False

    def OpenKey(self, root, path, reserved, access):
        return (root, path, access)

    def SetValueEx(self, key, name, reserved, value_type, value):
        if self.raise_on_set:
            raise RuntimeError("registry write failed")
        self.values[name] = value

    def DeleteValue(self, key, name):
        self.deleted.append(name)
        if self.missing_on_delete:
            raise FileNotFoundError(name)

    def CloseKey(self, key):
        self.closed.append(key)
        return None


def test_settings_round_trip_with_defaults():
    settings = settings_from_dict(
        {
            "opacity": 0.5,
            "window_geometry": {"x": 10, "y": 20, "width": 410, "height": 620},
            "icon_path": r"C:\Icons\todo.ico",
        }
    )

    assert settings.opacity == 0.5
    assert settings.close_to_tray is True
    assert settings.mouse_passthrough is False
    assert settings.icon_path == r"C:\Icons\todo.ico"
    assert settings.window_geometry["x"] == 10
    assert settings_to_dict(settings)["theme"] == "calm-tech-dark"
    assert settings_to_dict(settings)["icon_path"] == r"C:\Icons\todo.ico"


def test_opacity_is_clamped():
    assert settings_from_dict({"opacity": 2}).opacity == 1.0
    assert settings_from_dict({"opacity": 0.1}).opacity == 0.3


def test_window_geometry_cannot_be_mutated_directly():
    settings = settings_from_dict({"window_geometry": {"x": 10}})

    with pytest.raises(TypeError):
        settings.window_geometry["x"] = 99

    assert settings.window_geometry["x"] == 10


def test_malformed_settings_fall_back_without_raising():
    settings = settings_from_dict(
        {
            "opacity": "bad",
            "notification_lead_minutes": {},
            "notification_repeat_minutes": {},
            "window_geometry": {"x": "bad", "y": "30", "width": None, "height": []},
        }
    )

    assert settings.opacity == 0.96
    assert settings.notification_lead_minutes == 15
    assert settings.notification_repeat_minutes == 10
    assert dict(settings.window_geometry) == {"x": 1100, "y": 30, "width": 540, "height": 780}
    assert settings_from_dict({"opacity": None}).opacity == 0.96


def test_removed_settings_are_forced_to_defaults_for_compatibility():
    settings = settings_from_dict({"notification_repeat_minutes": "12"})

    assert settings.notification_repeat_minutes == 10
    assert settings_to_dict(settings)["notification_repeat_minutes"] == 10
    assert settings_from_dict({"notification_repeat_minutes": 0}).notification_repeat_minutes == 10
    assert settings_from_dict({"low_distraction_mode": True}).low_distraction_mode is False
    assert settings_from_dict({"background_overlay": 0.35}).background_overlay == 0.68


def test_boolean_strings_parse_predictably():
    settings = settings_from_dict(
        {
            "always_on_top": "false",
            "mouse_passthrough": "true",
            "lock_position": "0",
            "close_to_tray": "true",
            "launch_on_startup": "1",
            "low_distraction_mode": "true",
        }
    )

    assert settings.always_on_top is False
    assert settings.mouse_passthrough is True
    assert settings.lock_position is False
    assert settings.close_to_tray is True
    assert settings.launch_on_startup is True
    assert settings.low_distraction_mode is False


def test_launch_on_startup_writes_registry_value():
    fake = FakeWinreg()

    set_launch_on_startup("Todo list", r"C:\Apps\Todo list.exe", True, winreg_module=fake)

    assert fake.values["Todo list"] == r'"C:\Apps\Todo list.exe"'


def test_launch_on_startup_preserves_quoted_command_with_args():
    fake = FakeWinreg()

    set_launch_on_startup(
        "Todo list",
        r'"C:\Python312\python.exe" -m floating_todo',
        True,
        winreg_module=fake,
    )

    assert fake.values["Todo list"] == r'"C:\Python312\python.exe" -m floating_todo'


def test_current_startup_command_uses_packaged_executable_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\Todo list.exe")

    command = platform_windows.current_startup_command()

    assert command == f'"{Path(sys.executable).resolve()}"'


def test_current_startup_command_uses_python_module_when_unfrozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Python312\python.exe")

    command = platform_windows.current_startup_command()

    assert command == f'"{Path(sys.executable).resolve()}" -m floating_todo'


def test_launch_on_startup_deletes_registry_value():
    fake = FakeWinreg()

    set_launch_on_startup("Todo list", r"C:\Apps\Todo list.exe", False, winreg_module=fake)

    assert fake.deleted == ["Todo list"]


def test_launch_on_startup_closes_registry_key_when_write_fails():
    fake = FakeWinreg()
    fake.raise_on_set = True

    with pytest.raises(RuntimeError):
        set_launch_on_startup("Todo list", r"C:\Apps\Todo list.exe", True, winreg_module=fake)

    assert len(fake.closed) == 1


def test_launch_on_startup_ignores_missing_value_and_closes_key():
    fake = FakeWinreg()
    fake.missing_on_delete = True

    set_launch_on_startup("Todo list", r"C:\Apps\Todo list.exe", False, winreg_module=fake)

    assert fake.deleted == ["Todo list"]
    assert len(fake.closed) == 1
