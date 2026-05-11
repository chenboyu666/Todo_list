from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QPushButton

from floating_todo.domain import Task
from floating_todo.settings import AppSettings, settings_to_dict

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryStore:
    def __init__(self, tasks: list[Task]) -> None:
        self._tasks = tasks
        self.load_count = 0
        self.save_count = 0
        self.saved_tasks: list[Task] | None = None

    def load_tasks(self) -> list[Task]:
        self.load_count += 1
        return list(self._tasks)

    def save_tasks(self, tasks: list[Task]) -> None:
        self.save_count += 1
        self.saved_tasks = list(tasks)
        self._tasks = list(tasks)


class FakeNotificationSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, title: str, message: str) -> None:
        self.sent.append((title, message))


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app


def make_task(
    title: str,
    *,
    task_id: str | None = None,
    priority: str = "P1",
    progress: int = 25,
    effort_minutes: int = 45,
    deadline_delta: timedelta | None = timedelta(hours=2),
    status: str = "active",
    notification_state: dict[str, bool] | None = None,
) -> Task:
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id=task_id or title,
        title=title,
        priority=priority,
        effort_minutes=effort_minutes,
        deadline=now + deadline_delta if deadline_delta is not None else None,
        progress=progress,
        status=status,
        created_at=now,
        updated_at=now,
        completed_at=now if status == "done" else None,
        notes="",
        notification_state=notification_state or {},
    )


def test_main_window_constructs_with_empty_state(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]))

    assert window.windowTitle() == "FloatingTodo"
    assert window.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.minimumWidth() >= 410
    assert not window.empty_state_widget.isHidden()
    assert window.empty_state_label.text() == "没有进行中的任务"
    assert window.empty_state_hint_label.text() == "点击新增任务开始"
    assert window.focus_title_label.text() == "没有进行中的任务"
    assert window.focus_meta_label.text() == "工作量 --"
    assert window.focus_deadline_label.text() == "截止 --:--:--"
    assert window.settings_button.text() == "设置"
    assert window.settings_button.toolTip() == "打开设置"
    assert window.focus_progress.value() == 0
    assert window.active_count_label.text() == "0"
    assert window.today_completion_label.text() == "0%"

    window.close()


def test_refresh_renders_focus_summary_task_rows_and_actions(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    tasks = [
        make_task("完成归档", status="done", progress=100),
        make_task("低优先任务", priority="P3", progress=10, effort_minutes=20),
        make_task("关键交付", priority="P1", progress=60, effort_minutes=90),
    ]
    window = MainWindow(MemoryStore(tasks))

    assert window.empty_state_widget.isHidden()
    assert window.active_count_label.text() == "2"
    assert window.today_completion_label.text() == "33%"
    assert window.focus_title_label.text() == "关键交付"
    assert window.focus_meta_label.text() == "P1 · 工作量 90 min"
    assert window.focus_progress.value() == 60
    assert window.task_list_layout.count() == 2

    row_labels = window.task_rows_container.findChildren(QLabel)
    row_text = "\n".join(label.text() for label in row_labels)
    assert "关键交付" in row_text
    assert "低优先任务" in row_text
    assert "截止" in row_text
    assert "60%" in row_text

    buttons = window.task_rows_container.findChildren(QPushButton)
    button_texts = [button.text() for button in buttons]
    button_tooltips = [button.toolTip() for button in buttons]
    assert {"编辑", "完成", "删除"} <= set(button_texts)
    assert {"编辑任务", "标记任务完成", "删除任务"} <= set(button_tooltips)

    window.close()


def test_timer_timeout_refreshes_window_from_store(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    store = MemoryStore([])
    window = MainWindow(store)
    initial_loads = store.load_count

    store._tasks = [make_task("定时刷新任务")]
    window._clock_timer.timeout.emit()

    assert store.load_count == initial_loads + 1
    assert window.active_count_label.text() == "1"
    assert window.focus_title_label.text() == "定时刷新任务"

    window.close()


def test_add_button_opens_dialog_and_persists_non_empty_task(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window

    task = make_task("新增任务", task_id="new-task")

    class AcceptedDialog:
        def __init__(self, parent: object, task: Task | None = None) -> None:
            self.parent = parent
            self.task = task

        def exec(self) -> int:
            return QDialog.Accepted

        def build_task(self) -> Task:
            return task

    store = MemoryStore([])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window, "TaskDialog", AcceptedDialog)

    window.add_button.click()

    assert store.saved_tasks == [task]
    assert window.tasks == [task]
    assert window.focus_title_label.text() == "新增任务"
    assert window.task_list_layout.count() == 1

    window.close()


def test_add_task_ignores_blank_title(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    import floating_todo.ui.main_window as main_window

    task = make_task("   ", task_id="blank-task")

    class AcceptedDialog:
        def __init__(self, parent: object, task: Task | None = None) -> None:
            self.parent = parent
            self.task = task

        def exec(self) -> int:
            return QDialog.Accepted

        def build_task(self) -> Task:
            return task

    store = MemoryStore([])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window, "TaskDialog", AcceptedDialog)

    window.add_task()

    assert store.saved_tasks is None
    assert window.tasks == []
    assert window.task_list_layout.count() == 0

    window.close()


def test_edit_task_replaces_existing_task_when_dialog_accepts(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window

    original = make_task("原始任务", task_id="task-1", progress=20)
    updated = replace(original, title="编辑后任务", progress=75)
    constructed: dict[str, object] = {}

    class AcceptedDialog:
        def __init__(self, parent: object, task: Task | None = None) -> None:
            constructed["parent"] = parent
            constructed["task"] = task

        def exec(self) -> int:
            return QDialog.Accepted

        def build_task(self) -> Task:
            return updated

    store = MemoryStore([original])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window, "TaskDialog", AcceptedDialog)

    window.edit_task("task-1")

    assert constructed["parent"] is window
    assert constructed["task"] == original
    assert store.saved_tasks == [updated]
    assert window.tasks == [updated]
    assert window.focus_title_label.text() == "编辑后任务"

    window.close()


def test_edit_task_ignores_missing_task_and_blank_title(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window

    original = make_task("原始任务", task_id="task-1")
    blank = replace(original, title="   ")

    class AcceptedDialog:
        def __init__(self, parent: object, task: Task | None = None) -> None:
            pass

        def exec(self) -> int:
            return QDialog.Accepted

        def build_task(self) -> Task:
            return blank

    store = MemoryStore([original])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window, "TaskDialog", AcceptedDialog)

    window.edit_task("missing")
    window.edit_task("task-1")

    assert store.saved_tasks is None
    assert window.tasks == [original]

    window.close()


def test_complete_task_marks_done_with_progress_and_completion_time(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    original = make_task("完成我", task_id="task-1", progress=40)
    store = MemoryStore([original])
    window = MainWindow(store)

    window.complete_task("task-1")

    assert store.saved_tasks is not None
    completed = store.saved_tasks[0]
    assert completed.id == "task-1"
    assert completed.status == "done"
    assert completed.progress == 100
    assert completed.completed_at is not None
    assert completed.completed_at.tzinfo is timezone.utc
    assert window.task_list_layout.count() == 0

    window.close()


def test_delete_task_confirms_before_removing(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window

    task = make_task("删除我", task_id="task-1")
    store = MemoryStore([task])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    window.delete_task("task-1")

    assert store.saved_tasks == []
    assert window.tasks == []

    window.close()


def test_delete_task_keeps_task_when_confirmation_declines_or_task_missing(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    import floating_todo.ui.main_window as main_window

    task = make_task("保留我", task_id="task-1")
    store = MemoryStore([task])
    window = main_window.MainWindow(store)
    monkeypatch.setattr(main_window.QMessageBox, "question", lambda *args, **kwargs: QMessageBox.No)

    window.delete_task("missing")
    window.delete_task("task-1")

    assert store.saved_tasks is None
    assert window.tasks == [task]

    window.close()


def test_main_window_applies_initial_window_behavior_and_geometry_settings(
    qapp: QApplication, tmp_path
) -> None:
    from floating_todo.ui.main_window import MainWindow

    settings = AppSettings(
        always_on_top=False,
        opacity=0.58,
        window_geometry={"x": 33, "y": 44, "width": 455, "height": 566},
    )
    window = MainWindow(MemoryStore([]), settings, tmp_path / "settings.json")

    assert not window.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.windowOpacity() == pytest.approx(0.58, abs=0.01)
    assert window.geometry().x() == 33
    assert window.geometry().y() == 44
    assert window.geometry().width() == 455
    assert window.geometry().height() == 566

    window.close()


def test_geometry_changes_are_saved_when_position_is_unlocked(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    settings = AppSettings(lock_position=False)
    window = MainWindow(MemoryStore([]), settings, settings_path)

    window.setGeometry(31, 42, 480, 640)
    qapp.processEvents()

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["window_geometry"] == {"x": 31, "y": 42, "width": 480, "height": 640}
    assert dict(window.settings.window_geometry) == saved["window_geometry"]

    window.close()


def test_geometry_changes_are_not_saved_and_locked_geometry_is_restored(
    qapp: QApplication, tmp_path
) -> None:
    from floating_todo.ui.main_window import MainWindow

    settings_path = tmp_path / "settings.json"
    locked_geometry = {"x": 71, "y": 82, "width": 430, "height": 610}
    settings = AppSettings(lock_position=True, window_geometry=locked_geometry)
    window = MainWindow(MemoryStore([]), settings, settings_path)

    window.setGeometry(10, 20, 500, 700)
    qapp.processEvents()

    assert not settings_path.exists()
    assert dict(window.settings.window_geometry) == locked_geometry
    assert window.geometry().x() == locked_geometry["x"]
    assert window.geometry().y() == locked_geometry["y"]
    assert window.geometry().width() == locked_geometry["width"]
    assert window.geometry().height() == locked_geometry["height"]

    window.close()


def test_settings_button_acceptance_saves_applies_and_updates_startup(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import floating_todo.ui.main_window as main_window

    settings_path = tmp_path / "settings.json"
    updated = AppSettings(
        always_on_top=False,
        opacity=0.67,
        notification_lead_minutes=22,
        launch_on_startup=True,
    )
    captured: dict[str, object] = {}

    class AcceptedSettingsWindow:
        def __init__(self, settings: AppSettings, parent: object | None = None) -> None:
            self.settings = settings
            self.parent = parent

        def exec(self) -> int:
            return QDialog.Accepted

        def build_settings(self) -> AppSettings:
            return updated

    def fake_set_launch_on_startup(app_name: str, exe_path: str, enabled: bool) -> None:
        captured["startup"] = (app_name, exe_path, enabled)

    monkeypatch.setattr(main_window, "SettingsWindow", AcceptedSettingsWindow)
    monkeypatch.setattr(main_window, "current_executable_path", lambda: "E:/app/FloatingTodo.exe")
    monkeypatch.setattr(main_window, "set_launch_on_startup", fake_set_launch_on_startup)
    window = main_window.MainWindow(MemoryStore([]), AppSettings(), settings_path)

    window.settings_button.click()

    assert window.settings == updated
    assert window.windowOpacity() == pytest.approx(0.67, abs=0.01)
    assert not window.windowFlags() & Qt.WindowStaysOnTopHint
    assert captured["startup"] == ("FloatingTodo", "E:/app/FloatingTodo.exe", True)
    assert settings_path.exists()
    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings_to_dict(updated).items() <= saved_settings.items()

    window.close()


def test_settings_startup_oserror_shows_warning(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import floating_todo.ui.main_window as main_window

    updated = AppSettings(launch_on_startup=True)
    warnings: list[tuple[str, str]] = []

    class AcceptedSettingsWindow:
        def __init__(self, settings: AppSettings, parent: object | None = None) -> None:
            pass

        def exec(self) -> int:
            return QDialog.Accepted

        def build_settings(self) -> AppSettings:
            return updated

    def failing_set_launch_on_startup(app_name: str, exe_path: str, enabled: bool) -> None:
        raise OSError("registry denied")

    monkeypatch.setattr(main_window, "SettingsWindow", AcceptedSettingsWindow)
    monkeypatch.setattr(main_window, "current_executable_path", lambda: "E:/app/FloatingTodo.exe")
    monkeypatch.setattr(main_window, "set_launch_on_startup", failing_set_launch_on_startup)
    monkeypatch.setattr(
        main_window.QMessageBox,
        "warning",
        lambda parent, title, text: warnings.append((title, text)),
    )
    window = main_window.MainWindow(MemoryStore([]), AppSettings(), tmp_path / "settings.json")

    window.open_settings()

    assert warnings == [("启动设置失败", "无法更新开机启动设置：registry denied")]

    window.close()


def test_settings_startup_failure_preserves_previous_startup_setting(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import floating_todo.ui.main_window as main_window

    settings_path = tmp_path / "settings.json"
    previous = AppSettings(launch_on_startup=False, opacity=0.81)
    settings_path.write_text(json.dumps(settings_to_dict(previous)), encoding="utf-8")
    updated = AppSettings(launch_on_startup=True, opacity=0.62)
    warnings: list[tuple[str, str]] = []

    class AcceptedSettingsWindow:
        def __init__(self, settings: AppSettings, parent: object | None = None) -> None:
            pass

        def exec(self) -> int:
            return QDialog.Accepted

        def build_settings(self) -> AppSettings:
            return updated

    def failing_set_launch_on_startup(app_name: str, exe_path: str, enabled: bool) -> None:
        raise OSError("registry denied")

    monkeypatch.setattr(main_window, "SettingsWindow", AcceptedSettingsWindow)
    monkeypatch.setattr(main_window, "current_executable_path", lambda: "E:/app/FloatingTodo.exe")
    monkeypatch.setattr(main_window, "set_launch_on_startup", failing_set_launch_on_startup)
    monkeypatch.setattr(
        main_window.QMessageBox,
        "warning",
        lambda parent, title, text: warnings.append((title, text)),
    )
    window = main_window.MainWindow(MemoryStore([]), previous, settings_path)

    window.open_settings()

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert warnings
    assert window.settings.launch_on_startup is False
    assert saved_settings["launch_on_startup"] is False

    window.close()


def test_refresh_sends_due_reminders_once_and_persists_flags(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    now = datetime.now(timezone.utc)
    task = make_task(
        "提醒任务",
        task_id="task-1",
        deadline_delta=None,
        notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
    )
    task = replace(task, deadline=now - timedelta(minutes=1))
    store = MemoryStore([task])
    sender = FakeNotificationSender()

    window = MainWindow(store, AppSettings(notification_lead_minutes=15), notification_sender=sender)

    assert sender.sent == [("任务临近截止", "提醒任务"), ("任务已到期", "提醒任务")]
    assert store.save_count == 1
    assert store.saved_tasks is not None
    saved_task = store.saved_tasks[0]
    assert saved_task.notification_state["deadline_warning_sent"] is True
    assert saved_task.notification_state["deadline_due_sent"] is True

    window.refresh()

    assert sender.sent == [("任务临近截止", "提醒任务"), ("任务已到期", "提醒任务")]
    assert store.save_count == 1

    window.close()


class CloseEventProbe:
    def __init__(self) -> None:
        self.ignored = False
        self.accepted = False

    def ignore(self) -> None:
        self.ignored = True

    def accept(self) -> None:
        self.accepted = True


def test_close_event_hides_window_when_close_to_tray_enabled(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]), AppSettings(close_to_tray=True))
    window.tray_controller = type("AvailableTray", (), {"is_available": lambda self: True})()
    window.show()
    event = CloseEventProbe()

    window.closeEvent(event)

    assert event.ignored is True
    assert event.accepted is False
    assert window.isHidden()

    window.close()


def test_close_event_accepts_when_close_to_tray_enabled_without_tray_controller(
    qapp: QApplication,
) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]), AppSettings(close_to_tray=True))
    event = CloseEventProbe()

    window.closeEvent(event)

    assert event.accepted is True
    assert event.ignored is False


def test_close_event_accepts_when_tray_controller_is_unavailable(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]), AppSettings(close_to_tray=True))
    window.tray_controller = type("UnavailableTray", (), {"is_available": lambda self: False})()
    event = CloseEventProbe()

    window.closeEvent(event)

    assert event.accepted is True
    assert event.ignored is False


def test_close_event_accepts_when_close_to_tray_disabled(qapp: QApplication) -> None:
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(MemoryStore([]), AppSettings(close_to_tray=False))
    event = CloseEventProbe()

    window.closeEvent(event)

    assert event.accepted is True
    assert event.ignored is False
