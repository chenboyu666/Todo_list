import json
from datetime import datetime, timezone

from floating_todo.domain import Task
from floating_todo.store import JsonTaskStore, load_json_object, save_json_object


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


def test_load_migrates_old_active_tasks_to_work_timer_fields(tmp_path):
    path = tmp_path / "tasks.json"
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    path.write_text(
        json.dumps(
            [
                {
                    "id": "old-active",
                    "title": "旧任务",
                    "priority": "P1",
                    "effort_minutes": 45,
                    "deadline": now.isoformat(),
                    "progress": 10,
                    "status": "active",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "completed_at": None,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = JsonTaskStore(path)

    tasks = store.load_tasks()
    migrated = json.loads(path.read_text(encoding="utf-8"))

    assert tasks[0].work_elapsed_seconds == 0
    assert tasks[0].work_started_at is not None
    assert migrated[0]["work_elapsed_seconds"] == 0
    assert migrated[0]["work_started_at"]


def test_load_json_object_missing_file_returns_shallow_default_copy(tmp_path):
    default = {"opacity": 0.96, "nested": {"kept": True}}

    loaded = load_json_object(tmp_path / "settings.json", default)

    assert loaded == default
    assert loaded is not default
    assert loaded["nested"] is default["nested"]


def test_load_json_object_returns_valid_json_object(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"always_on_top": false, "opacity": 0.75}', encoding="utf-8")

    assert load_json_object(path, {"always_on_top": True}) == {
        "always_on_top": False,
        "opacity": 0.75,
    }


def test_load_json_object_non_object_or_corrupt_json_returns_default_copy(tmp_path):
    default = {"close_to_tray": True}
    path = tmp_path / "settings.json"

    path.write_text("[1, 2, 3]", encoding="utf-8")
    non_object = load_json_object(path, default)

    path.write_text("{bad-json", encoding="utf-8")
    corrupt = load_json_object(path, default)

    assert non_object == default
    assert non_object is not default
    assert corrupt == default
    assert corrupt is not default


def test_load_json_object_invalid_utf8_returns_shallow_default_copy(tmp_path):
    default = {"opacity": 0.96}
    path = tmp_path / "settings.json"
    path.write_bytes(b'{"opacity": "\xff"}')

    loaded = load_json_object(path, default)

    assert loaded == default
    assert loaded is not default


def test_save_json_object_writes_json_object(tmp_path):
    path = tmp_path / "settings.json"

    save_json_object(path, {"low_distraction_mode": True})

    assert json.loads(path.read_text(encoding="utf-8")) == {"low_distraction_mode": True}
