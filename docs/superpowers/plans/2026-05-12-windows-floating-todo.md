# Windows Floating Todo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows PySide6 floating task console with realtime clock, manually tracked task progress, deadline countdowns, tray background mode, local JSON persistence, notifications, settings, and PyInstaller folder packaging.

**Architecture:** Keep business logic independent from PySide6 so sorting, persistence, settings, and reminder behavior can be tested with pytest. The UI layer binds PySide6 widgets to small view-model functions and services. Local JSON files live under `data/` next to the running app for portable folder distribution.

**Tech Stack:** Python 3.10+, PySide6, pytest, PyInstaller, Windows registry via `winreg`, optional Windows toast via `winotify`.

---

## File Structure

- Create: `pyproject.toml` - pytest configuration and package metadata.
- Create: `requirements.txt` - runtime and build dependencies.
- Create: `README.md` - local run, test, and packaging instructions.
- Create: `src/floating_todo/__init__.py` - package marker and version.
- Create: `src/floating_todo/__main__.py` - `python -m floating_todo` entrypoint.
- Create: `src/floating_todo/domain.py` - task dataclass, JSON conversion, sorting, focus selection.
- Create: `src/floating_todo/store.py` - atomic JSON file persistence for tasks and settings.
- Create: `src/floating_todo/settings.py` - settings dataclass and default values.
- Create: `src/floating_todo/platform_windows.py` - startup registry and executable path helpers.
- Create: `src/floating_todo/reminders.py` - reminder event planning and sent-state updates.
- Create: `src/floating_todo/view_models.py` - UI-ready display rows and countdown labels.
- Create: `src/floating_todo/theme.py` - shared QSS design tokens.
- Create: `src/floating_todo/app.py` - application bootstrap and service wiring.
- Create: `src/floating_todo/ui/main_window.py` - floating panel UI.
- Create: `src/floating_todo/ui/task_dialog.py` - add/edit task dialog.
- Create: `src/floating_todo/ui/settings_window.py` - settings window.
- Create: `src/floating_todo/ui/tray.py` - system tray icon and menu.
- Create: `src/floating_todo/assets/app_icon.svg` - app icon used by windows and tray.
- Create: `tests/test_domain.py` - domain behavior tests.
- Create: `tests/test_store.py` - persistence tests.
- Create: `tests/test_settings_platform.py` - settings and startup registry tests.
- Create: `tests/test_reminders.py` - notification event tests.
- Create: `tests/test_view_models.py` - UI display logic tests.
- Create: `scripts/build.ps1` - repeatable PyInstaller build.

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `README.md`
- Create: `src/floating_todo/__init__.py`
- Create: `src/floating_todo/__main__.py`
- Create: `tests/test_imports.py`

- [ ] **Step 1: Write import smoke test**

Create `tests/test_imports.py`:

```python
def test_package_imports():
    import floating_todo

    assert floating_todo.__version__ == "0.1.0"
```

- [ ] **Step 2: Run the smoke test and verify it fails**

Run: `python -m pytest tests/test_imports.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'floating_todo'`.

- [ ] **Step 3: Create package metadata and dependencies**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "floating-todo"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "PySide6>=6.7",
  "winotify>=1.1.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

Create `requirements.txt`:

```text
PySide6>=6.7
winotify>=1.1.0
pytest>=8.0
pyinstaller>=6.6
```

Create `src/floating_todo/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/floating_todo/__main__.py`:

```python
from floating_todo.app import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `README.md`:

````markdown
# Floating Todo

Windows floating task console built with Python and PySide6.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m floating_todo
```

## Test

```powershell
python -m pytest -q
```

## Build

```powershell
.\scripts\build.ps1
```

The packaged app is created at `dist/FloatingTodo/FloatingTodo.exe`.
````

- [ ] **Step 4: Run smoke test and verify it passes**

Run: `python -m pytest tests/test_imports.py -q`

Expected: PASS.

- [ ] **Step 5: Commit scaffold**

```bash
git add pyproject.toml requirements.txt README.md src/floating_todo/__init__.py src/floating_todo/__main__.py tests/test_imports.py
git commit -m "chore: scaffold floating todo project"
```

---

### Task 2: Task Domain Model

**Files:**
- Create: `src/floating_todo/domain.py`
- Create: `tests/test_domain.py`

- [ ] **Step 1: Write failing domain tests**

Create `tests/test_domain.py`:

```python
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task, select_focus_task, sort_tasks, task_from_dict, task_to_dict


UTC = timezone.utc


def make_task(title, priority, deadline_hours, effort, created_minutes):
    base = datetime(2026, 5, 12, 8, 0, tzinfo=UTC)
    return Task(
        id=title,
        title=title,
        priority=priority,
        effort_minutes=effort,
        deadline=base + timedelta(hours=deadline_hours) if deadline_hours is not None else None,
        progress=0,
        status="active",
        created_at=base + timedelta(minutes=created_minutes),
        updated_at=base + timedelta(minutes=created_minutes),
        completed_at=None,
        notes="",
        notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
    )


def test_sort_tasks_uses_priority_deadline_effort_created():
    tasks = [
        make_task("p2-near", "P2", 1, 30, 1),
        make_task("p1-far-small", "P1", 5, 30, 2),
        make_task("p1-near-large", "P1", 1, 120, 3),
        make_task("p1-near-small", "P1", 1, 20, 0),
        replace(make_task("done", "P1", 0, 999, 0), status="done"),
    ]

    assert [task.title for task in sort_tasks(tasks)] == [
        "p1-near-large",
        "p1-near-small",
        "p1-far-small",
        "p2-near",
    ]


def test_select_focus_task_returns_first_sorted_active_task():
    tasks = [
        make_task("p3", "P3", 1, 20, 0),
        make_task("p1", "P1", 4, 20, 0),
    ]

    assert select_focus_task(tasks).title == "p1"


def test_task_json_round_trip_preserves_datetime_and_notification_state():
    task = make_task("spec", "P1", 2, 90, 0)

    restored = task_from_dict(task_to_dict(task))

    assert restored == task
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_domain.py -q`

Expected: FAIL with missing `floating_todo.domain`.

- [ ] **Step 3: Implement domain model**

Create `src/floating_todo/domain.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Priority = Literal["P1", "P2", "P3"]
Status = Literal["active", "done", "archived"]

PRIORITY_RANK: dict[str, int] = {"P1": 0, "P2": 1, "P3": 2}
DEFAULT_NOTIFICATION_STATE = {
    "deadline_warning_sent": False,
    "deadline_due_sent": False,
}


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    priority: Priority
    effort_minutes: int
    deadline: datetime | None
    progress: int
    status: Status
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    notes: str = ""
    notification_state: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_NOTIFICATION_STATE))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def task_from_dict(data: dict[str, Any]) -> Task:
    notification_state = dict(DEFAULT_NOTIFICATION_STATE)
    notification_state.update(data.get("notification_state") or {})
    return Task(
        id=str(data["id"]),
        title=str(data["title"]),
        priority=data.get("priority", "P3"),
        effort_minutes=max(0, int(data.get("effort_minutes", 0))),
        deadline=parse_datetime(data.get("deadline")),
        progress=max(0, min(100, int(data.get("progress", 0)))),
        status=data.get("status", "active"),
        created_at=parse_datetime(data.get("created_at")) or utc_now(),
        updated_at=parse_datetime(data.get("updated_at")) or utc_now(),
        completed_at=parse_datetime(data.get("completed_at")),
        notes=str(data.get("notes", "")),
        notification_state=notification_state,
    )


def task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "priority": task.priority,
        "effort_minutes": task.effort_minutes,
        "deadline": format_datetime(task.deadline),
        "progress": task.progress,
        "status": task.status,
        "created_at": format_datetime(task.created_at),
        "updated_at": format_datetime(task.updated_at),
        "completed_at": format_datetime(task.completed_at),
        "notes": task.notes,
        "notification_state": dict(task.notification_state),
    }


def sort_tasks(tasks: list[Task]) -> list[Task]:
    active = [task for task in tasks if task.status == "active"]
    return sorted(
        active,
        key=lambda task: (
            PRIORITY_RANK.get(task.priority, 99),
            task.deadline is None,
            task.deadline or datetime.max.replace(tzinfo=timezone.utc),
            -task.effort_minutes,
            task.created_at,
        ),
    )


def select_focus_task(tasks: list[Task]) -> Task | None:
    sorted_tasks = sort_tasks(tasks)
    return sorted_tasks[0] if sorted_tasks else None
```

- [ ] **Step 4: Run domain tests**

Run: `python -m pytest tests/test_domain.py -q`

Expected: PASS.

- [ ] **Step 5: Commit domain model**

```bash
git add src/floating_todo/domain.py tests/test_domain.py
git commit -m "feat: add task domain model"
```

---

### Task 3: Atomic JSON Store

**Files:**
- Create: `src/floating_todo/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write failing store tests**

Create `tests/test_store.py`:

```python
import json
from datetime import datetime, timezone

from floating_todo.domain import Task
from floating_todo.store import JsonTaskStore


def sample_task():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id="1",
        title="Write spec",
        priority="P1",
        effort_minutes=90,
        deadline=now,
        progress=25,
        status="active",
        created_at=now,
        updated_at=now,
        completed_at=None,
        notes="",
        notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
    )


def test_load_missing_tasks_file_returns_empty_list(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks.json")

    assert store.load_tasks() == []


def test_save_then_load_tasks_round_trip(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks.json")
    task = sample_task()

    store.save_tasks([task])

    assert store.load_tasks() == [task]


def test_corrupt_json_is_preserved_and_empty_list_returned(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text("{not-json", encoding="utf-8")
    store = JsonTaskStore(path)

    assert store.load_tasks() == []
    broken_files = list(tmp_path.glob("tasks.json.broken-*"))
    assert len(broken_files) == 1
    assert broken_files[0].read_text(encoding="utf-8") == "{not-json"


def test_save_writes_valid_json_array(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks.json")

    store.save_tasks([sample_task()])

    raw = json.loads((tmp_path / "tasks.json").read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert raw[0]["title"] == "Write spec"
```

- [ ] **Step 2: Run store tests and verify failure**

Run: `python -m pytest tests/test_store.py -q`

Expected: FAIL with missing `JsonTaskStore`.

- [ ] **Step 3: Implement atomic JSON store**

Create `src/floating_todo/store.py`:

```python
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from floating_todo.domain import Task, task_from_dict, task_to_dict


class JsonTaskStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_tasks(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            return [task_from_dict(item) for item in raw if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            self._preserve_broken_file()
            return []

    def save_tasks(self, tasks: list[Task]) -> None:
        payload = [task_to_dict(task) for task in tasks]
        atomic_write_json(self.path, payload)

    def _preserve_broken_file(self) -> None:
        if not self.path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        broken_path = self.path.with_name(f"{self.path.name}.broken-{timestamp}")
        shutil.copy2(self.path, broken_path)


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)
```

- [ ] **Step 4: Run store tests**

Run: `python -m pytest tests/test_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit store**

```bash
git add src/floating_todo/store.py tests/test_store.py
git commit -m "feat: add atomic task storage"
```

---

### Task 4: Settings and Startup Registry Helpers

**Files:**
- Create: `src/floating_todo/settings.py`
- Create: `src/floating_todo/platform_windows.py`
- Create: `tests/test_settings_platform.py`

- [ ] **Step 1: Write failing settings and platform tests**

Create `tests/test_settings_platform.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_settings_platform.py -q`

Expected: FAIL with missing settings and platform modules.

- [ ] **Step 3: Implement settings and registry helpers**

Create `src/floating_todo/settings.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_GEOMETRY = {"x": 1200, "y": 120, "width": 410, "height": 620}


@dataclass(frozen=True)
class AppSettings:
    always_on_top: bool = True
    lock_position: bool = False
    close_to_tray: bool = True
    launch_on_startup: bool = False
    opacity: float = 0.96
    low_distraction_mode: bool = False
    notification_lead_minutes: int = 15
    window_geometry: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_GEOMETRY))
    theme: str = "calm-tech-dark"


def settings_from_dict(data: dict[str, Any] | None) -> AppSettings:
    data = data or {}
    geometry = dict(DEFAULT_GEOMETRY)
    raw_geometry = data.get("window_geometry")
    if isinstance(raw_geometry, dict):
        for key in ("x", "y", "width", "height"):
            if key in raw_geometry:
                geometry[key] = int(raw_geometry[key])
    opacity = float(data.get("opacity", 0.96))
    opacity = max(0.3, min(1.0, opacity))
    return AppSettings(
        always_on_top=bool(data.get("always_on_top", True)),
        lock_position=bool(data.get("lock_position", False)),
        close_to_tray=bool(data.get("close_to_tray", True)),
        launch_on_startup=bool(data.get("launch_on_startup", False)),
        opacity=opacity,
        low_distraction_mode=bool(data.get("low_distraction_mode", False)),
        notification_lead_minutes=max(1, int(data.get("notification_lead_minutes", 15))),
        window_geometry=geometry,
        theme=str(data.get("theme", "calm-tech-dark")),
    )


def settings_to_dict(settings: AppSettings) -> dict[str, object]:
    return {
        "always_on_top": settings.always_on_top,
        "lock_position": settings.lock_position,
        "close_to_tray": settings.close_to_tray,
        "launch_on_startup": settings.launch_on_startup,
        "opacity": settings.opacity,
        "low_distraction_mode": settings.low_distraction_mode,
        "notification_lead_minutes": settings.notification_lead_minutes,
        "window_geometry": dict(settings.window_geometry),
        "theme": settings.theme,
    }
```

Create `src/floating_todo/platform_windows.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def current_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve())
    return str(Path(sys.argv[0]).resolve())


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
            winreg_module.SetValueEx(key, app_name, 0, winreg_module.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg_module.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
    finally:
        winreg_module.CloseKey(key)
```

- [ ] **Step 4: Run settings tests**

Run: `python -m pytest tests/test_settings_platform.py -q`

Expected: PASS.

- [ ] **Step 5: Commit settings and platform helpers**

```bash
git add src/floating_todo/settings.py src/floating_todo/platform_windows.py tests/test_settings_platform.py
git commit -m "feat: add settings and startup helpers"
```

---

### Task 5: Reminder Planning

**Files:**
- Create: `src/floating_todo/reminders.py`
- Create: `tests/test_reminders.py`

- [ ] **Step 1: Write failing reminder tests**

Create `tests/test_reminders.py`:

```python
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task
from floating_todo.reminders import mark_event_sent, reminder_events


def task_with_deadline(deadline, state=None):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id="1",
        title="Ship app",
        priority="P1",
        effort_minutes=90,
        deadline=deadline,
        progress=20,
        status="active",
        created_at=now,
        updated_at=now,
        completed_at=None,
        notes="",
        notification_state=state or {"deadline_warning_sent": False, "deadline_due_sent": False},
    )


def test_warning_event_when_inside_lead_window():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    task = task_with_deadline(now + timedelta(minutes=10))

    assert reminder_events(task, now, lead_minutes=15) == ["deadline_warning"]


def test_due_event_when_deadline_passed():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    task = task_with_deadline(now - timedelta(seconds=1))

    assert reminder_events(task, now, lead_minutes=15) == ["deadline_warning", "deadline_due"]


def test_sent_events_do_not_repeat():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    task = task_with_deadline(
        now - timedelta(seconds=1),
        {"deadline_warning_sent": True, "deadline_due_sent": True},
    )

    assert reminder_events(task, now, lead_minutes=15) == []


def test_completed_task_has_no_events():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    task = replace(task_with_deadline(now), status="done")

    assert reminder_events(task, now, lead_minutes=15) == []


def test_mark_event_sent_sets_matching_flag():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    task = task_with_deadline(now)

    updated = mark_event_sent(task, "deadline_warning")

    assert updated.notification_state["deadline_warning_sent"] is True
    assert updated.notification_state["deadline_due_sent"] is False
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_reminders.py -q`

Expected: FAIL with missing `floating_todo.reminders`.

- [ ] **Step 3: Implement reminder planning**

Create `src/floating_todo/reminders.py`:

```python
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from floating_todo.domain import Task

EVENT_TO_FLAG = {
    "deadline_warning": "deadline_warning_sent",
    "deadline_due": "deadline_due_sent",
}


def reminder_events(task: Task, now: datetime, lead_minutes: int) -> list[str]:
    if task.status != "active" or task.deadline is None:
        return []

    events: list[str] = []
    warning_at = task.deadline - timedelta(minutes=lead_minutes)
    if now >= warning_at and not task.notification_state.get("deadline_warning_sent", False):
        events.append("deadline_warning")
    if now >= task.deadline and not task.notification_state.get("deadline_due_sent", False):
        events.append("deadline_due")
    return events


def mark_event_sent(task: Task, event: str) -> Task:
    flag = EVENT_TO_FLAG[event]
    state = dict(task.notification_state)
    state[flag] = True
    return replace(task, notification_state=state)
```

- [ ] **Step 4: Run reminder tests**

Run: `python -m pytest tests/test_reminders.py -q`

Expected: PASS.

- [ ] **Step 5: Commit reminder planning**

```bash
git add src/floating_todo/reminders.py tests/test_reminders.py
git commit -m "feat: add reminder planning"
```

---

### Task 6: View Models for UI Display

**Files:**
- Create: `src/floating_todo/view_models.py`
- Create: `tests/test_view_models.py`

- [ ] **Step 1: Write failing view-model tests**

Create `tests/test_view_models.py`:

```python
from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task
from floating_todo.view_models import countdown_label, task_rows, today_completion_percent


def make_task(title, progress, status="active", deadline_delta=None):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id=title,
        title=title,
        priority="P1",
        effort_minutes=90,
        deadline=now + deadline_delta if deadline_delta else None,
        progress=progress,
        status=status,
        created_at=now,
        updated_at=now,
        completed_at=now if status == "done" else None,
        notes="",
        notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
    )


def test_countdown_label_for_future_deadline():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)

    assert countdown_label(now + timedelta(hours=1, minutes=2, seconds=3), now) == "01:02:03"


def test_countdown_label_for_past_deadline():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)

    assert countdown_label(now - timedelta(minutes=3), now) == "超时 00:03:00"


def test_today_completion_percent_uses_done_tasks():
    tasks = [make_task("a", 100, "done"), make_task("b", 50), make_task("c", 0)]

    assert today_completion_percent(tasks) == 33


def test_task_rows_include_priority_deadline_and_progress():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    rows = task_rows([make_task("a", 30, deadline_delta=timedelta(minutes=15))], now)

    assert rows[0]["title"] == "a"
    assert rows[0]["progress_label"] == "30%"
    assert rows[0]["deadline_label"] == "00:15:00"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_view_models.py -q`

Expected: FAIL with missing `floating_todo.view_models`.

- [ ] **Step 3: Implement view models**

Create `src/floating_todo/view_models.py`:

```python
from __future__ import annotations

from datetime import datetime

from floating_todo.domain import Task, sort_tasks


def countdown_label(deadline: datetime | None, now: datetime) -> str:
    if deadline is None:
        return "--:--:--"
    delta = deadline - now
    past = delta.total_seconds() < 0
    total_seconds = abs(int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    label = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"超时 {label}" if past else label


def today_completion_percent(tasks: list[Task]) -> int:
    visible = [task for task in tasks if task.status in {"active", "done"}]
    if not visible:
        return 0
    done = [task for task in visible if task.status == "done"]
    return round(len(done) / len(visible) * 100)


def task_rows(tasks: list[Task], now: datetime) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for task in sort_tasks(tasks):
        rows.append(
            {
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "effort_label": f"{task.effort_minutes} min",
                "deadline_label": countdown_label(task.deadline, now),
                "progress": task.progress,
                "progress_label": f"{task.progress}%",
                "is_overdue": bool(task.deadline and task.deadline < now),
            }
        )
    return rows
```

- [ ] **Step 4: Run view-model tests**

Run: `python -m pytest tests/test_view_models.py -q`

Expected: PASS.

- [ ] **Step 5: Commit view models**

```bash
git add src/floating_todo/view_models.py tests/test_view_models.py
git commit -m "feat: add task display view models"
```

---

### Task 7: Application Bootstrap and Theme

**Files:**
- Create: `src/floating_todo/theme.py`
- Create: `src/floating_todo/app.py`
- Create: `src/floating_todo/assets/app_icon.svg`
- Modify: `src/floating_todo/__main__.py`

- [ ] **Step 1: Write bootstrap smoke test**

Create `tests/test_app_bootstrap.py`:

```python
from pathlib import Path

from floating_todo.app import app_data_dir, ensure_data_files


def test_app_data_dir_uses_base_path_data_folder(tmp_path):
    assert app_data_dir(tmp_path) == tmp_path / "data"


def test_ensure_data_files_creates_data_folder(tmp_path):
    data_dir = ensure_data_files(tmp_path)

    assert data_dir == tmp_path / "data"
    assert data_dir.exists()
```

- [ ] **Step 2: Run bootstrap test and verify failure**

Run: `python -m pytest tests/test_app_bootstrap.py -q`

Expected: FAIL with missing `floating_todo.app`.

- [ ] **Step 3: Implement theme and app bootstrap**

Create `src/floating_todo/theme.py`:

```python
CALM_TECH_QSS = """
QWidget {
  background: #0E1223;
  color: #F8FAFC;
  font-family: "Segoe UI";
  font-size: 13px;
}
QPushButton {
  background: #111827;
  border: 1px solid #334155;
  border-radius: 8px;
  min-height: 32px;
  padding: 4px 10px;
}
QPushButton:hover {
  border-color: #22D3EE;
  background: #172033;
}
QPushButton:pressed {
  background: #1A1E2F;
}
QLineEdit, QTextEdit, QSpinBox, QDateTimeEdit, QComboBox {
  background: #020617;
  border: 1px solid #334155;
  border-radius: 8px;
  min-height: 32px;
  padding: 4px 8px;
}
QProgressBar {
  background: #334155;
  border: 0;
  border-radius: 4px;
  height: 8px;
}
QProgressBar::chunk {
  background: #22D3EE;
  border-radius: 4px;
}
"""
```

Create `src/floating_todo/app.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from floating_todo.store import JsonTaskStore
from floating_todo.theme import CALM_TECH_QSS


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def app_data_dir(base_path: Path | None = None) -> Path:
    return (base_path or app_base_dir()) / "data"


def ensure_data_files(base_path: Path | None = None) -> Path:
    data_dir = app_data_dir(base_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FloatingTodo")
    app.setStyleSheet(CALM_TECH_QSS)
    data_dir = ensure_data_files()
    store = JsonTaskStore(data_dir / "tasks.json")
    from floating_todo.ui.main_window import MainWindow

    window = MainWindow(store)
    window.show()
    return app.exec()
```

Create `src/floating_todo/assets/app_icon.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#020617"/>
  <path d="M14 20h36M14 32h28M14 44h20" stroke="#22D3EE" stroke-width="5" stroke-linecap="round"/>
  <circle cx="50" cy="44" r="6" fill="#22C55E"/>
</svg>
```

- [ ] **Step 4: Run bootstrap test**

Run: `python -m pytest tests/test_app_bootstrap.py -q`

Expected: PASS.

- [ ] **Step 5: Commit bootstrap**

```bash
git add src/floating_todo/theme.py src/floating_todo/app.py src/floating_todo/assets/app_icon.svg tests/test_app_bootstrap.py
git commit -m "feat: add application bootstrap"
```

---

### Task 8: Main Floating Window

**Files:**
- Create: `src/floating_todo/ui/__init__.py`
- Create: `src/floating_todo/ui/main_window.py`

- [ ] **Step 1: Create UI package marker**

Create `src/floating_todo/ui/__init__.py`:

```python
"""PySide6 user interface widgets."""
```

- [ ] **Step 2: Implement floating main window**

Create `src/floating_todo/ui/main_window.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from floating_todo.domain import Task, select_focus_task
from floating_todo.store import JsonTaskStore
from floating_todo.view_models import countdown_label, task_rows, today_completion_percent


class MainWindow(QMainWindow):
    def __init__(self, store: JsonTaskStore) -> None:
        super().__init__()
        self.store = store
        self.tasks: list[Task] = store.load_tasks()
        self.setWindowTitle("FloatingTodo")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(410)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.time_label = QLabel()
        self.time_label.setObjectName("timeLabel")
        self.summary_label = QLabel()
        self.focus_title = QLabel("没有进行中的任务")
        self.focus_meta = QLabel("点击新增任务开始")
        self.focus_progress = QProgressBar()
        self.task_container = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_container)
        self.task_list_layout.setContentsMargins(0, 0, 0, 0)
        self.task_list_layout.setSpacing(8)

        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.time_label.setStyleSheet("font-size: 28px; font-weight: 700;")
        header.addWidget(self.time_label, 1)
        settings_button = QPushButton("设置")
        settings_button.setToolTip("打开设置")
        header.addWidget(settings_button)
        layout.addLayout(header)

        self.summary_label.setStyleSheet("color: #94A3B8;")
        layout.addWidget(self.summary_label)

        focus = QFrame()
        focus.setFrameShape(QFrame.StyledPanel)
        focus_layout = QVBoxLayout(focus)
        self.focus_title.setWordWrap(True)
        self.focus_title.setStyleSheet("font-size: 16px; font-weight: 650;")
        focus_layout.addWidget(self.focus_title)
        self.focus_meta.setStyleSheet("color: #94A3B8;")
        focus_layout.addWidget(self.focus_meta)
        focus_layout.addWidget(self.focus_progress)
        layout.addWidget(focus)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.task_container)
        layout.addWidget(scroll, 1)

        self.setCentralWidget(root)

    def refresh(self) -> None:
        now = datetime.now(timezone.utc)
        self.time_label.setText(datetime.now().strftime("%H:%M:%S"))
        active_count = len([task for task in self.tasks if task.status == "active"])
        self.summary_label.setText(f"今日完成 {today_completion_percent(self.tasks)}%   进行中 {active_count}")
        focus_task = select_focus_task(self.tasks)
        if focus_task:
            self.focus_title.setText(f"{focus_task.priority}  {focus_task.title}")
            self.focus_meta.setText(
                f"工作量 {focus_task.effort_minutes} min   截止 {countdown_label(focus_task.deadline, now)}"
            )
            self.focus_progress.setValue(focus_task.progress)
        self._render_task_rows(now)

    def _render_task_rows(self, now: datetime) -> None:
        while self.task_list_layout.count():
            item = self.task_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for row in task_rows(self.tasks, now):
            label = QLabel(
                f"{row['priority']}  {row['title']}  "
                f"{row['effort_label']}  {row['deadline_label']}  {row['progress_label']}"
            )
            label.setWordWrap(True)
            label.setStyleSheet("padding: 10px; border: 1px solid #334155; border-radius: 8px;")
            self.task_list_layout.addWidget(label)
        self.task_list_layout.addStretch(1)
```

- [ ] **Step 3: Run current test suite**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Manual UI smoke run**

Run: `python -m floating_todo`

Expected: a dark always-on-top window opens, time updates once per second, and the empty task state is visible.

- [ ] **Step 5: Commit main window**

```bash
git add src/floating_todo/ui/__init__.py src/floating_todo/ui/main_window.py
git commit -m "feat: add floating main window"
```

---

### Task 9: Add/Edit Task Dialog

**Files:**
- Create: `src/floating_todo/ui/task_dialog.py`
- Modify: `src/floating_todo/ui/main_window.py`

- [ ] **Step 1: Implement task dialog**

Create `src/floating_todo/ui/task_dialog.py`:

```python
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from floating_todo.domain import Task


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("任务")
        self.task = task
        self.title_input = QLineEdit(task.title if task else "")
        self.priority_input = QComboBox()
        self.priority_input.addItems(["P1", "P2", "P3"])
        if task:
            self.priority_input.setCurrentText(task.priority)
        self.effort_input = QSpinBox()
        self.effort_input.setRange(0, 24 * 60)
        self.effort_input.setSingleStep(15)
        self.effort_input.setValue(task.effort_minutes if task else 60)
        self.deadline_input = QDateTimeEdit()
        self.deadline_input.setCalendarPopup(True)
        self.deadline_input.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.progress_input = QSpinBox()
        self.progress_input.setRange(0, 100)
        self.progress_input.setValue(task.progress if task else 0)
        self.notes_input = QTextEdit(task.notes if task else "")

        form = QFormLayout()
        form.addRow("任务名称", self.title_input)
        form.addRow("优先级", self.priority_input)
        form.addRow("预计工作量", self.effort_input)
        form.addRow("截止时间", self.deadline_input)
        form.addRow("手动进度", self.progress_input)
        form.addRow("备注", self.notes_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def build_task(self) -> Task:
        now = datetime.now(timezone.utc)
        deadline = self.deadline_input.dateTime().toPython()
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if self.task:
            return replace(
                self.task,
                title=self.title_input.text().strip(),
                priority=self.priority_input.currentText(),
                effort_minutes=self.effort_input.value(),
                deadline=deadline,
                progress=self.progress_input.value(),
                updated_at=now,
                notes=self.notes_input.toPlainText(),
            )
        return Task(
            id=str(uuid4()),
            title=self.title_input.text().strip(),
            priority=self.priority_input.currentText(),
            effort_minutes=self.effort_input.value(),
            deadline=deadline,
            progress=self.progress_input.value(),
            status="active",
            created_at=now,
            updated_at=now,
            completed_at=None,
            notes=self.notes_input.toPlainText(),
            notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
        )
```

- [ ] **Step 2: Wire add button into main window**

Modify `src/floating_todo/ui/main_window.py`:

```python
# Add this import near the existing imports.
from floating_todo.ui.task_dialog import TaskDialog
```

In `_build_ui`, add the button after `settings_button`:

```python
add_button = QPushButton("新增")
add_button.setToolTip("新增任务")
add_button.clicked.connect(self.add_task)
header.addWidget(add_button)
```

Add this method to `MainWindow`:

```python
def add_task(self) -> None:
    dialog = TaskDialog(self)
    if dialog.exec() == TaskDialog.Accepted:
        task = dialog.build_task()
        if task.title:
            self.tasks.append(task)
            self.store.save_tasks(self.tasks)
            self.refresh()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Manual task creation smoke run**

Run: `python -m floating_todo`

Expected: clicking `新增` opens the task dialog; saving a task adds it to the floating window and persists it in `data/tasks.json`.

- [ ] **Step 5: Commit task dialog**

```bash
git add src/floating_todo/ui/task_dialog.py src/floating_todo/ui/main_window.py
git commit -m "feat: add task creation dialog"
```

---

### Task 10: Settings Window and Window Behavior

**Files:**
- Create: `src/floating_todo/ui/settings_window.py`
- Modify: `src/floating_todo/store.py`
- Modify: `src/floating_todo/app.py`
- Modify: `src/floating_todo/ui/main_window.py`

- [ ] **Step 1: Add generic JSON object methods to store**

Modify `src/floating_todo/store.py` by adding:

```python
def load_json_object(path: Path, default: dict[str, object]) -> dict[str, object]:
    if not Path(path).exists():
        return dict(default)
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else dict(default)
    except (OSError, json.JSONDecodeError):
        return dict(default)


def save_json_object(path: Path, payload: dict[str, object]) -> None:
    atomic_write_json(Path(path), payload)
```

- [ ] **Step 2: Implement settings window**

Create `src/floating_todo/ui/settings_window.py`:

```python
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QSlider, QSpinBox, QVBoxLayout
from PySide6.QtCore import Qt

from floating_todo.settings import AppSettings


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = settings
        self.always_on_top = QCheckBox()
        self.always_on_top.setChecked(settings.always_on_top)
        self.lock_position = QCheckBox()
        self.lock_position.setChecked(settings.lock_position)
        self.close_to_tray = QCheckBox()
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.launch_on_startup = QCheckBox()
        self.launch_on_startup.setChecked(settings.launch_on_startup)
        self.low_distraction = QCheckBox()
        self.low_distraction.setChecked(settings.low_distraction_mode)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(round(settings.opacity * 100))
        self.lead_minutes = QSpinBox()
        self.lead_minutes.setRange(1, 240)
        self.lead_minutes.setValue(settings.notification_lead_minutes)

        form = QFormLayout()
        form.addRow("窗口始终置顶", self.always_on_top)
        form.addRow("锁定位置", self.lock_position)
        form.addRow("关闭时进入托盘", self.close_to_tray)
        form.addRow("Windows 开机启动", self.launch_on_startup)
        form.addRow("低干扰模式", self.low_distraction)
        form.addRow("透明度", self.opacity)
        form.addRow("提前提醒分钟", self.lead_minutes)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def build_settings(self) -> AppSettings:
        return replace(
            self.settings,
            always_on_top=self.always_on_top.isChecked(),
            lock_position=self.lock_position.isChecked(),
            close_to_tray=self.close_to_tray.isChecked(),
            launch_on_startup=self.launch_on_startup.isChecked(),
            low_distraction_mode=self.low_distraction.isChecked(),
            opacity=self.opacity.value() / 100,
            notification_lead_minutes=self.lead_minutes.value(),
        )
```

- [ ] **Step 3: Wire settings into app and main window**

Modify `src/floating_todo/app.py` to load settings:

```python
from floating_todo.settings import settings_from_dict
from floating_todo.store import JsonTaskStore, load_json_object
```

Replace the window creation in `main()`:

```python
settings = settings_from_dict(load_json_object(data_dir / "settings.json", {}))
window = MainWindow(store, settings, data_dir / "settings.json")
```

Modify the `MainWindow` constructor signature:

```python
def __init__(self, store: JsonTaskStore, settings, settings_path) -> None:
    super().__init__()
    self.store = store
    self.settings = settings
    self.settings_path = settings_path
```

Add imports:

```python
from floating_todo.settings import settings_to_dict
from floating_todo.store import save_json_object
from floating_todo.ui.settings_window import SettingsWindow
```

Connect the existing settings button:

```python
settings_button.clicked.connect(self.open_settings)
```

Add this method:

```python
def open_settings(self) -> None:
    dialog = SettingsWindow(self.settings, self)
    if dialog.exec() == SettingsWindow.Accepted:
        self.settings = dialog.build_settings()
        save_json_object(self.settings_path, settings_to_dict(self.settings))
        self.setWindowOpacity(self.settings.opacity)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.settings.always_on_top)
        self.show()
```

- [ ] **Step 4: Run tests and manual settings smoke run**

Run: `python -m pytest -q`

Expected: PASS.

Run: `python -m floating_todo`

Expected: clicking `设置` opens the settings window; saving opacity changes the main window opacity and writes `data/settings.json`.

- [ ] **Step 5: Commit settings UI**

```bash
git add src/floating_todo/store.py src/floating_todo/app.py src/floating_todo/ui/main_window.py src/floating_todo/ui/settings_window.py
git commit -m "feat: add settings window"
```

---

### Task 11: Tray Background Mode and Notifications

**Files:**
- Create: `src/floating_todo/ui/tray.py`
- Modify: `src/floating_todo/app.py`
- Modify: `src/floating_todo/ui/main_window.py`

- [ ] **Step 1: Implement tray controller**

Create `src/floating_todo/ui/tray.py`:

```python
from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication


class TrayController:
    def __init__(self, window, icon: QIcon) -> None:
        self.window = window
        self.tray = QSystemTrayIcon(icon)
        self.menu = QMenu()
        self.show_action = QAction("显示/隐藏")
        self.show_action.triggered.connect(self.toggle_window)
        self.add_action = QAction("快速新增任务")
        self.add_action.triggered.connect(window.add_task)
        self.settings_action = QAction("设置")
        self.settings_action.triggered.connect(window.open_settings)
        self.quit_action = QAction("退出")
        self.quit_action.triggered.connect(QApplication.instance().quit)
        self.menu.addAction(self.show_action)
        self.menu.addAction(self.add_action)
        self.menu.addAction(self.settings_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def toggle_window(self) -> None:
        if self.window.isVisible():
            self.window.hide()
        else:
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()
```

- [ ] **Step 2: Override close behavior in main window**

Add to `MainWindow`:

```python
def closeEvent(self, event) -> None:
    if self.settings.close_to_tray:
        event.ignore()
        self.hide()
    else:
        event.accept()
```

- [ ] **Step 3: Wire tray controller in app bootstrap**

Modify `src/floating_todo/app.py`:

```python
from PySide6.QtGui import QIcon
from floating_todo.ui.tray import TrayController
```

After `window = MainWindow(...)`, add:

```python
icon = QIcon(str(Path(__file__).resolve().parent / "assets" / "app_icon.svg"))
tray = TrayController(window, icon)
window.tray_controller = tray
```

- [ ] **Step 4: Add simple Windows notification sender**

Create `src/floating_todo/notifications.py`:

```python
from __future__ import annotations


class NotificationSender:
    def send(self, title: str, message: str) -> None:
        try:
            from winotify import Notification

            toast = Notification(app_id="FloatingTodo", title=title, msg=message)
            toast.show()
        except Exception:
            return
```

- [ ] **Step 5: Run tests and manual tray smoke run**

Run: `python -m pytest -q`

Expected: PASS.

Run: `python -m floating_todo`

Expected: tray icon appears; closing the main window hides it; tray menu can show the window again and exit the app.

- [ ] **Step 6: Commit tray and notification foundation**

```bash
git add src/floating_todo/ui/tray.py src/floating_todo/ui/main_window.py src/floating_todo/app.py src/floating_todo/notifications.py
git commit -m "feat: add tray background mode"
```

---

### Task 12: Task Actions, Geometry, Startup, and Reminder Integration

**Files:**
- Modify: `src/floating_todo/ui/main_window.py`
- Modify: `src/floating_todo/app.py`
- Modify: `src/floating_todo/ui/settings_window.py`

- [ ] **Step 1: Add edit, complete, and delete actions to task rows**

Modify `src/floating_todo/ui/main_window.py` imports:

```python
from dataclasses import replace
from PySide6.QtWidgets import QMessageBox
```

Replace the label-only body in `_render_task_rows` with this card implementation:

```python
for row in task_rows(self.tasks, now):
    card = QFrame()
    card.setFrameShape(QFrame.StyledPanel)
    card_layout = QVBoxLayout(card)
    title = QLabel(
        f"{row['priority']}  {row['title']}  "
        f"{row['effort_label']}  {row['deadline_label']}  {row['progress_label']}"
    )
    title.setWordWrap(True)
    card_layout.addWidget(title)
    actions = QHBoxLayout()
    edit_button = QPushButton("编辑")
    edit_button.setToolTip("编辑任务")
    edit_button.clicked.connect(lambda checked=False, task_id=row["id"]: self.edit_task(str(task_id)))
    done_button = QPushButton("完成")
    done_button.setToolTip("标记任务完成")
    done_button.clicked.connect(lambda checked=False, task_id=row["id"]: self.complete_task(str(task_id)))
    delete_button = QPushButton("删除")
    delete_button.setToolTip("删除任务")
    delete_button.clicked.connect(lambda checked=False, task_id=row["id"]: self.delete_task(str(task_id)))
    actions.addWidget(edit_button)
    actions.addWidget(done_button)
    actions.addWidget(delete_button)
    card_layout.addLayout(actions)
    self.task_list_layout.addWidget(card)
```

Add these methods to `MainWindow`:

```python
def _replace_task(self, updated_task: Task) -> None:
    self.tasks = [updated_task if task.id == updated_task.id else task for task in self.tasks]
    self.store.save_tasks(self.tasks)
    self.refresh()


def edit_task(self, task_id: str) -> None:
    task = next((item for item in self.tasks if item.id == task_id), None)
    if task is None:
        return
    dialog = TaskDialog(self, task)
    if dialog.exec() == TaskDialog.Accepted:
        updated = dialog.build_task()
        if updated.title:
            self._replace_task(updated)


def complete_task(self, task_id: str) -> None:
    task = next((item for item in self.tasks if item.id == task_id), None)
    if task is None:
        return
    updated = replace(task, status="done", progress=100, completed_at=datetime.now(timezone.utc))
    self._replace_task(updated)


def delete_task(self, task_id: str) -> None:
    task = next((item for item in self.tasks if item.id == task_id), None)
    if task is None:
        return
    result = QMessageBox.question(self, "删除任务", f"删除任务：{task.title}？")
    if result == QMessageBox.Yes:
        self.tasks = [item for item in self.tasks if item.id != task_id]
        self.store.save_tasks(self.tasks)
        self.refresh()
```

- [ ] **Step 2: Persist window geometry and enforce position lock**

Modify `src/floating_todo/ui/main_window.py` imports:

```python
from PySide6.QtCore import QRect
from floating_todo.settings import settings_to_dict
from floating_todo.store import save_json_object
```

Add these methods to `MainWindow`:

```python
def apply_saved_geometry(self) -> None:
    geometry = self.settings.window_geometry
    self.setGeometry(
        QRect(
            int(geometry["x"]),
            int(geometry["y"]),
            int(geometry["width"]),
            int(geometry["height"]),
        )
    )
    self._locked_geometry = dict(geometry)


def persist_window_geometry(self) -> None:
    if self.settings.lock_position:
        return
    geometry = self.geometry()
    self.settings = replace(
        self.settings,
        window_geometry={
            "x": geometry.x(),
            "y": geometry.y(),
            "width": geometry.width(),
            "height": geometry.height(),
        },
    )
    save_json_object(self.settings_path, settings_to_dict(self.settings))
    self._locked_geometry = dict(self.settings.window_geometry)


def moveEvent(self, event) -> None:
    if getattr(self, "settings", None) and self.settings.lock_position:
        locked = getattr(self, "_locked_geometry", self.settings.window_geometry)
        self.setGeometry(QRect(locked["x"], locked["y"], locked["width"], locked["height"]))
        event.ignore()
        return
    self.persist_window_geometry()
    super().moveEvent(event)


def resizeEvent(self, event) -> None:
    self.persist_window_geometry()
    super().resizeEvent(event)
```

Call `self.apply_saved_geometry()` at the end of `MainWindow.__init__`, after `_build_ui()`.

- [ ] **Step 3: Apply startup registry setting when settings are saved**

Modify `src/floating_todo/ui/main_window.py` imports:

```python
from floating_todo.platform_windows import current_executable_path, set_launch_on_startup
```

In `open_settings`, after `save_json_object(...)`, add:

```python
try:
    set_launch_on_startup("FloatingTodo", current_executable_path(), self.settings.launch_on_startup)
except OSError:
    QMessageBox.warning(self, "开机自启失败", "无法写入 Windows 开机启动设置。")
```

- [ ] **Step 4: Wire reminder events to notifications**

Modify `src/floating_todo/app.py` imports:

```python
from floating_todo.notifications import NotificationSender
```

Change main-window creation:

```python
notification_sender = NotificationSender()
window = MainWindow(store, settings, data_dir / "settings.json", notification_sender)
```

Modify the `MainWindow` constructor signature:

```python
def __init__(self, store: JsonTaskStore, settings, settings_path, notification_sender=None) -> None:
```

Store the sender:

```python
self.notification_sender = notification_sender
```

Add imports in `src/floating_todo/ui/main_window.py`:

```python
from floating_todo.reminders import mark_event_sent, reminder_events
```

Add this method:

```python
def process_reminders(self, now: datetime) -> None:
    if self.notification_sender is None:
        return
    changed = False
    updated_tasks: list[Task] = []
    for task in self.tasks:
        updated = task
        for event in reminder_events(task, now, self.settings.notification_lead_minutes):
            if event == "deadline_warning":
                self.notification_sender.send("任务临近截止", task.title)
            elif event == "deadline_due":
                self.notification_sender.send("任务已到期", task.title)
            updated = mark_event_sent(updated, event)
            changed = True
        updated_tasks.append(updated)
    if changed:
        self.tasks = updated_tasks
        self.store.save_tasks(self.tasks)
```

Call `self.process_reminders(now)` inside `refresh()` immediately after `now = datetime.now(timezone.utc)`.

- [ ] **Step 5: Run tests and manual behavior check**

Run: `python -m pytest -q`

Expected: PASS.

Run: `python -m floating_todo`

Expected:
- task rows show edit, complete, and delete actions;
- completed tasks disappear from active queue;
- moving or resizing the window updates `data/settings.json`;
- enabling lock position prevents position changes from persisting;
- enabling startup writes the Windows Run registry value;
- tasks inside the reminder window trigger one notification and update notification flags in `data/tasks.json`.

- [ ] **Step 6: Commit integrated app behaviors**

```bash
git add src/floating_todo/ui/main_window.py src/floating_todo/app.py src/floating_todo/ui/settings_window.py
git commit -m "feat: integrate task actions and reminders"
```

---

### Task 13: Packaging Script

**Files:**
- Create: `scripts/build.ps1`
- Modify: `README.md`

- [ ] **Step 1: Create PyInstaller build script**

Create `scripts/build.ps1`:

```powershell
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt

if (Test-Path "build") {
  Remove-Item -Recurse -Force "build"
}

if (Test-Path "dist") {
  Remove-Item -Recurse -Force "dist"
}

.\.venv\Scripts\pyinstaller.exe `
  --noconfirm `
  --onedir `
  --windowed `
  --name FloatingTodo `
  --add-data "src/floating_todo/assets;floating_todo/assets" `
  --collect-all PySide6 `
  "src/floating_todo/__main__.py"

New-Item -ItemType Directory -Force -Path "dist/FloatingTodo/data" | Out-Null
Write-Host "Build complete: dist/FloatingTodo/FloatingTodo.exe"
```

- [ ] **Step 2: Update README build section**

Replace the `Build` section in `README.md` with:

````markdown
## Build

```powershell
.\scripts\build.ps1
```

The packaged app is created at `dist/FloatingTodo/FloatingTodo.exe`.
The folder includes a `data/` directory for portable tasks and settings.
````

- [ ] **Step 3: Run full tests before packaging**

Run: `python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Run package build**

Run: `.\scripts\build.ps1`

Expected: output includes `Build complete: dist/FloatingTodo/FloatingTodo.exe`.

- [ ] **Step 5: Manual packaged-app smoke run**

Run: `.\dist\FloatingTodo\FloatingTodo.exe`

Expected: packaged floating window opens without needing the development virtual environment.

- [ ] **Step 6: Commit packaging**

```bash
git add scripts/build.ps1 README.md
git commit -m "build: add pyinstaller packaging script"
```

---

### Task 14: Final Verification and Local Backup Commit

**Files:**
- Modify only files required by failures discovered in this task.

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest -q`

Expected: all tests PASS.

- [ ] **Step 2: Run local app**

Run: `python -m floating_todo`

Expected:
- realtime clock updates once per second;
- window stays above other windows;
- adding a task writes `data/tasks.json`;
- settings writes `data/settings.json`;
- close hides to tray;
- tray exit closes the process.

- [ ] **Step 3: Run packaged app**

Run: `.\scripts\build.ps1`

Expected: build completes with `dist/FloatingTodo/FloatingTodo.exe`.

Run: `.\dist\FloatingTodo\FloatingTodo.exe`

Expected: packaged app opens and can create a task in `dist/FloatingTodo/data/tasks.json`.

- [ ] **Step 4: Check git status**

Run: `git status --short`

Expected: no uncommitted source changes. `dist/`, `build/`, `.venv/`, and `.superpowers/` remain ignored.

- [ ] **Step 5: Create final local backup commit if source files changed during verification**

```bash
git add .
git commit -m "chore: verify floating todo app"
```

If `git status --short` is empty before this step, skip the commit.
