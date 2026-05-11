from floating_todo.platform_windows import set_launch_on_startup
from floating_todo.settings import AppSettings, settings_from_dict, settings_to_dict


class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 1
    REG_SZ = 1

    def __init__(self):
        self.values = {}
        self.deleted = []

    def OpenKey(self, root, path, reserved, access):
        return (root, path, access)

    def SetValueEx(self, key, name, reserved, value_type, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        self.deleted.append(name)

    def CloseKey(self, key):
        return None


def test_settings_round_trip_with_defaults():
    settings = settings_from_dict({"opacity": 0.5, "window_geometry": {"x": 10, "y": 20, "width": 410, "height": 620}})

    assert settings.opacity == 0.5
    assert settings.close_to_tray is True
    assert settings.window_geometry["x"] == 10
    assert settings_to_dict(settings)["theme"] == "calm-tech-dark"


def test_opacity_is_clamped():
    assert settings_from_dict({"opacity": 2}).opacity == 1.0
    assert settings_from_dict({"opacity": 0.1}).opacity == 0.3


def test_launch_on_startup_writes_registry_value():
    fake = FakeWinreg()

    set_launch_on_startup("FloatingTodo", r"C:\Apps\FloatingTodo.exe", True, winreg_module=fake)

    assert fake.values["FloatingTodo"] == r'"C:\Apps\FloatingTodo.exe"'


def test_launch_on_startup_deletes_registry_value():
    fake = FakeWinreg()

    set_launch_on_startup("FloatingTodo", r"C:\Apps\FloatingTodo.exe", False, winreg_module=fake)

    assert fake.deleted == ["FloatingTodo"]
