from __future__ import annotations


class FakeSignal:
    def __init__(self) -> None:
        self.callback = None

    def connect(self, callback) -> None:
        self.callback = callback

    def emit(self) -> None:
        assert self.callback is not None
        self.callback()


class FakeAction:
    def __init__(self, label: str, parent=None) -> None:
        self.label = label
        self.parent = parent
        self.triggered = FakeSignal()

    def trigger(self) -> None:
        self.triggered.emit()


class FakeMenu:
    def __init__(self) -> None:
        self.actions: list[FakeAction] = []

    def addAction(self, action: FakeAction) -> None:
        self.actions.append(action)


class FakeTrayIcon:
    def __init__(self, icon) -> None:
        self.icon = icon
        self.menu = None
        self.shown = False

    def setContextMenu(self, menu: FakeMenu) -> None:
        self.menu = menu

    def show(self) -> None:
        self.shown = True


class FakeWindow:
    def __init__(self, *, visible: bool = False) -> None:
        self.visible = visible
        self.calls: list[str] = []

    def isVisible(self) -> bool:
        return self.visible

    def hide(self) -> None:
        self.calls.append("hide")
        self.visible = False

    def show(self) -> None:
        self.calls.append("show")
        self.visible = True

    def raise_(self) -> None:
        self.calls.append("raise")

    def activateWindow(self) -> None:
        self.calls.append("activate")

    def add_task(self) -> None:
        self.calls.append("add_task")

    def open_settings(self) -> None:
        self.calls.append("open_settings")


class FakeApp:
    def __init__(self) -> None:
        self.quit_called = False

    def quit(self) -> None:
        self.quit_called = True


def make_controller(window: FakeWindow, app: FakeApp | None = None):
    from floating_todo.ui.tray import TrayController

    return TrayController(
        window,
        "icon",
        tray_cls=FakeTrayIcon,
        menu_cls=FakeMenu,
        action_cls=FakeAction,
        app_provider=lambda: app,
    )


def test_tray_controller_creates_menu_actions_and_shows_tray() -> None:
    window = FakeWindow()
    app = FakeApp()

    controller = make_controller(window, app)

    assert controller.tray.icon == "icon"
    assert controller.tray.menu is controller.menu
    assert controller.tray.shown is True
    assert [action.label for action in controller.menu.actions] == [
        "显示/隐藏",
        "快速新增任务",
        "设置",
        "退出",
    ]

    controller.menu.actions[1].trigger()
    controller.menu.actions[2].trigger()
    controller.menu.actions[3].trigger()

    assert "add_task" in window.calls
    assert "open_settings" in window.calls
    assert app.quit_called is True


def test_tray_toggle_hides_visible_window() -> None:
    window = FakeWindow(visible=True)
    controller = make_controller(window)

    controller.toggle_window()

    assert window.calls[-1] == "hide"
    assert window.visible is False


def test_tray_toggle_shows_raises_and_activates_hidden_window() -> None:
    window = FakeWindow(visible=False)
    controller = make_controller(window)

    controller.toggle_window()

    assert window.calls[-3:] == ["show", "raise", "activate"]
    assert window.visible is True


def test_tray_quit_action_is_safe_without_application_instance() -> None:
    controller = make_controller(FakeWindow(), app=None)

    controller.menu.actions[3].trigger()
