from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task
from floating_todo.view_models import countdown_label, task_rows, today_completion_percent


def make_task(title, progress, status="active", deadline_delta=None, priority="P1"):
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    return Task(
        id=title,
        title=title,
        priority=priority,
        effort_minutes=90,
        deadline=now + deadline_delta if deadline_delta is not None else None,
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


def test_countdown_label_for_missing_deadline():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)

    assert countdown_label(None, now) == "--:--:--"


def test_countdown_label_accepts_naive_deadline_as_utc():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    deadline = datetime(2026, 5, 12, 8, 15)

    assert countdown_label(deadline, now) == "00:15:00"


def test_today_completion_percent_uses_done_tasks():
    tasks = [make_task("a", 100, "done"), make_task("b", 50), make_task("c", 0)]

    assert today_completion_percent(tasks) == 33


def test_task_rows_include_priority_deadline_and_progress():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    rows = task_rows([make_task("a", 30, deadline_delta=timedelta(0))], now)

    assert rows[0]["title"] == "a"
    assert rows[0]["progress_label"] == "30%"
    assert rows[0]["deadline_label"] == "00:00:00"


def test_task_rows_uses_sorted_active_tasks():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    tasks = [
        make_task("active-p2", 20, deadline_delta=timedelta(minutes=5), priority="P2"),
        make_task("done-p1", 100, status="done", deadline_delta=timedelta(minutes=1), priority="P1"),
        make_task("active-p1", 10, deadline_delta=timedelta(minutes=30), priority="P1"),
    ]

    rows = task_rows(tasks, now)

    assert [row["title"] for row in rows] == ["active-p1", "active-p2"]


def test_task_rows_accept_naive_now_from_ui_callers():
    now = datetime(2026, 5, 12, 8, 0)
    rows = task_rows([make_task("a", 30, deadline_delta=timedelta(minutes=15))], now)

    assert rows[0]["deadline_label"] == "00:15:00"
    assert rows[0]["is_overdue"] is False
