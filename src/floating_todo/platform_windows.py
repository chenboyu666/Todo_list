from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def current_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return str(Path(sys.argv[0]).resolve())


def current_startup_command() -> str:
    executable = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    return f'"{executable}" -m floating_todo'


def set_launch_on_startup(app_name: str, exe_path: str, enabled: bool, winreg_module: Any | None = None) -> None:
    if winreg_module is None:
        import winreg as winreg_module

    key = winreg_module.OpenKey(
        winreg_module.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg_module.KEY_SET_VALUE,
    )
    try:
        if enabled:
            command = exe_path if exe_path.startswith('"') else f'"{exe_path}"'
            winreg_module.SetValueEx(key, app_name, 0, winreg_module.REG_SZ, command)
        else:
            try:
                winreg_module.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
    finally:
        winreg_module.CloseKey(key)
