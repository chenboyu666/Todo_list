from __future__ import annotations

import os
import json
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from floating_todo.domain import Task
from floating_todo.settings import AppSettings, settings_to_dict

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class MemoryStore:
    def __init__(self, tasks: list[Task]) -> None:
        self._tasks = tasks
        self.load_count = 0
        self.saved_tasks: list[Task] | None = None

    def load_tasks(self) -> list[Task]:
        self.load_count += 1
        return list(self._tasks)

    def save_tasks(self, tasks: list[Task]) -> None:
        self.saved_tasks = list(tasks)
        self._tasks = list(tasks)


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
    assert window.focus_progress.value() == 0
    assert window.active_count_label.text() == "0"
    assert window.today_completion_label.text() == "0%"

    window.close()


def test_refresh_renders_focus_summary_and_task_rows(qapp: QApplication) -> None:
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
        def __init__(self, parent: object) -> None:
            self.parent = parent

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
        def __init__(self, parent: object) -> None:
            self.parent = parent

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


def test_main_window_applies_initial_window_behavior_settings(
    qapp: QApplication, tmp_path
) -> None:
    from floating_todo.ui.main_window import MainWindow

    settings = AppSettings(always_on_top=False, opacity=0.58)
    window = MainWindow(MemoryStore([]), settings, tmp_path / "settings.json")

    assert not window.windowFlags() & Qt.WindowStaysOnTopHint
    assert window.windowOpacity() == pytest.approx(0.58, abs=0.01)

    window.close()


def test_settings_button_acceptance_saves_and_applies_runtime_settings(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    import floating_todo.ui.main_window as main_window

    settings_path = tmp_path / "settings.json"
    updated = AppSettings(always_on_top=False, opacity=0.67, notification_lead_minutes=22)

    class AcceptedSettingsWindow:
        def __init__(self, settings: AppSettings, parent: object | None = None) -> None:
            self.settings = settings
            self.parent = parent

        def exec(self) -> int:
            return QDialog.Accepted

        def build_settings(self) -> AppSettings:
            return updated

    monkeypatch.setattr(main_window, "SettingsWindow", AcceptedSettingsWindow)
    window = main_window.MainWindow(MemoryStore([]), AppSettings(), settings_path)

    window.settings_button.click()

    assert window.settings == updated
    assert window.windowOpacity() == pytest.approx(0.67, abs=0.01)
    assert not window.windowFlags() & Qt.WindowStaysOnTopHint
    assert settings_path.exists()
    assert settings_path.read_text(encoding="utf-8")
    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings_to_dict(updated).items() <= saved_settings.items()

    window.close()
