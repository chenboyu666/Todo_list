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
