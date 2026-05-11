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
