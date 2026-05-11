from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class TrayController:
    def __init__(
        self,
        window: Any,
        icon: QIcon,
        *,
        tray_cls: type = QSystemTrayIcon,
        menu_cls: type = QMenu,
        action_cls: type = QAction,
        app_provider: Callable[[], QApplication | None] = QApplication.instance,
    ) -> None:
        self.window = window
        self._app_provider = app_provider
        self.tray = tray_cls(icon)
        self.menu = menu_cls()

        self.show_hide_action = self._add_action(action_cls, "显示/隐藏", self.toggle_window)
        self.quick_add_action = self._add_action(action_cls, "快速新增任务", self.window.add_task)
        self.settings_action = self._add_action(action_cls, "设置", self.window.open_settings)
        self.quit_action = self._add_action(action_cls, "退出", self._quit_application)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def _add_action(self, action_cls: type, label: str, callback: Callable[[], None]) -> Any:
        action = action_cls(label, self.menu)
        action.triggered.connect(callback)
        self.menu.addAction(action)
        return action

    def toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
            return

        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit_application(self) -> None:
        app = self._app_provider()
        if app is not None:
            app.quit()
