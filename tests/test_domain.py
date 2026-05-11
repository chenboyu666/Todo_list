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
