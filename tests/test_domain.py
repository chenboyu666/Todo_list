from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from floating_todo.domain import (
    DEFAULT_TASK_TAG,
    Task,
    freeze_work_timer,
    pause_work_timer,
    resume_work_timer,
    select_focus_task,
    sort_tasks,
    sort_visible_tasks,
    task_from_dict,
    task_to_dict,
    work_elapsed_seconds,
)


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
        tag="学习",
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
        replace(make_task("paused-p1", "P1", 0, 200, -1), status="paused"),
    ]

    assert select_focus_task(tasks).title == "p1"


def test_select_focus_task_returns_none_for_empty_list():
    assert select_focus_task([]) is None


def test_task_json_round_trip_preserves_datetime_and_notification_state():
    task = make_task("spec", "P1", 2, 90, 0)

    restored = task_from_dict(task_to_dict(task))

    assert restored == task


def test_paused_tasks_are_visible_but_not_focus_candidates():
    active = make_task("active", "P3", 4, 20, 0)
    paused = replace(make_task("paused", "P1", 1, 120, 0), status="paused")

    assert [task.title for task in sort_tasks([active, paused])] == ["active"]
    assert [task.title for task in sort_visible_tasks([paused, active])] == ["active", "paused"]
    assert select_focus_task([paused]) is None


def test_task_from_dict_accepts_paused_and_normalizes_unknown_status():
    paused = task_from_dict({"id": "paused", "title": "paused", "status": "paused"})
    unknown = task_from_dict({"id": "unknown", "title": "unknown", "status": "blocked"})

    assert paused.status == "paused"
    assert unknown.status == "active"


def test_sort_tasks_normalizes_mixed_naive_and_aware_datetimes():
    base = datetime(2026, 5, 12, 8, 0, tzinfo=UTC)
    naive_near = Task(
        id="naive-near",
        title="naive-near",
        priority="P1",
        effort_minutes=30,
        deadline=datetime(2026, 5, 12, 9, 0),
        progress=0,
        status="active",
        created_at=datetime(2026, 5, 12, 8, 0),
        updated_at=datetime(2026, 5, 12, 8, 0),
        completed_at=None,
        notes="",
        notification_state={"deadline_warning_sent": False, "deadline_due_sent": False},
    )
    aware_far = make_task("aware-far", "P1", 3, 30, 1)

    assert [task.title for task in sort_tasks([aware_far, naive_near])] == [
        "naive-near",
        "aware-far",
    ]
    assert naive_near.deadline == base + timedelta(hours=1)
    assert naive_near.created_at == base


def test_task_from_dict_backfills_notification_state_without_mutating_input():
    data = {
        "id": "partial",
        "title": "partial",
        "notification_state": {"deadline_warning_sent": True},
    }

    task = task_from_dict(data)

    assert task.notification_state == {
        "deadline_warning_sent": True,
        "deadline_due_sent": False,
    }
    assert data["notification_state"] == {"deadline_warning_sent": True}


def test_task_tag_round_trip_and_legacy_default():
    task = make_task("tagged", "P2", 3, 45, 0)

    payload = task_to_dict(task)
    restored = task_from_dict(payload)
    legacy = task_from_dict({"id": "legacy", "title": "legacy"})
    blank = task_from_dict({"id": "blank", "title": "blank", "tag": "   "})

    assert payload["tag"] == "学习"
    assert restored.tag == "学习"
    assert legacy.tag == DEFAULT_TASK_TAG
    assert blank.tag == DEFAULT_TASK_TAG


def test_same_priority_no_deadline_tasks_sort_after_dated_tasks():
    tasks = [
        make_task("no-deadline", "P1", None, 120, 0),
        make_task("dated", "P1", 24, 20, 1),
    ]

    assert [task.title for task in sort_tasks(tasks)] == ["dated", "no-deadline"]


def test_task_notification_state_cannot_be_mutated_directly():
    task = make_task("immutable", "P1", 1, 30, 0)

    with pytest.raises(TypeError):
        task.notification_state["deadline_warning_sent"] = True


def test_work_timer_pauses_resumes_and_freezes_without_changing_deadline():
    base = datetime(2026, 5, 12, 8, 0, tzinfo=UTC)
    task = replace(
        make_task("timer", "P1", 2, 30, 0),
        work_elapsed_seconds=30,
        work_started_at=base,
    )

    assert work_elapsed_seconds(task, base + timedelta(seconds=45)) == 75

    paused = pause_work_timer(task, base + timedelta(seconds=45))
    assert paused.status == "paused"
    assert paused.deadline == task.deadline
    assert paused.work_elapsed_seconds == 75
    assert paused.work_started_at is None
    assert work_elapsed_seconds(paused, base + timedelta(minutes=5)) == 75

    resumed = resume_work_timer(paused, base + timedelta(minutes=5))
    assert resumed.status == "active"
    assert resumed.work_started_at == base + timedelta(minutes=5)
    assert work_elapsed_seconds(resumed, base + timedelta(minutes=5, seconds=30)) == 105

    frozen = freeze_work_timer(resumed, base + timedelta(minutes=5, seconds=30))
    assert frozen.status == "active"
    assert frozen.work_elapsed_seconds == 105
    assert frozen.work_started_at is None
