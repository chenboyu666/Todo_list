from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task
from floating_todo.view_models import (
    countdown_label,
    deadline_at_label,
    deadline_urgency,
    task_rows,
    today_completion_percent,
)


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


def test_deadline_at_label_shows_local_date_and_time():
    deadline = datetime(2026, 5, 12, 8, 15, tzinfo=timezone.utc)

    assert deadline_at_label(deadline) == deadline.astimezone().strftime("%Y-%m-%d %H:%M")


def test_deadline_urgency_levels_follow_remaining_time():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)

    assert deadline_urgency(None, now) == ("none", "无截止")
    assert deadline_urgency(now - timedelta(seconds=1), now) == ("overdue", "已超时")
    assert deadline_urgency(now + timedelta(minutes=9), now) == ("critical", "10 分内")
    assert deadline_urgency(now + timedelta(minutes=20), now) == ("urgent", "半小时内")
    assert deadline_urgency(now + timedelta(minutes=90), now) == ("soon", "临近")
    assert deadline_urgency(now + timedelta(hours=3), now) == ("normal", "充裕")


def test_today_completion_percent_uses_done_tasks():
    tasks = [make_task("a", 100, "done"), make_task("b", 50), make_task("c", 0), make_task("d", 20, "paused")]

    assert today_completion_percent(tasks) == 25


def test_task_rows_include_priority_deadline_and_progress():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    rows = task_rows([make_task("a", 30, deadline_delta=timedelta(0))], now)

    assert rows[0]["title"] == "a"
    assert rows[0]["notes"] == ""
    assert rows[0]["progress_label"] == "30%"
    assert rows[0]["deadline_label"] == "00:00:00"
    assert rows[0]["deadline_at_label"] == now.astimezone().strftime("%Y-%m-%d %H:%M")
    assert rows[0]["urgency"] == "critical"
    assert rows[0]["urgency_label"] == "10 分内"


def test_task_rows_uses_sorted_active_tasks():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    tasks = [
        make_task("active-p2", 20, deadline_delta=timedelta(minutes=5), priority="P2"),
        make_task("done-p1", 100, status="done", deadline_delta=timedelta(minutes=1), priority="P1"),
        make_task("active-p1", 10, deadline_delta=timedelta(minutes=30), priority="P1"),
    ]

    rows = task_rows(tasks, now)

    assert [row["title"] for row in rows] == ["active-p1", "active-p2"]


def test_task_rows_show_paused_tasks_after_active_tasks():
    now = datetime(2026, 5, 12, 8, 0, tzinfo=timezone.utc)
    tasks = [
        make_task("paused-p1", 40, status="paused", deadline_delta=timedelta(minutes=5), priority="P1"),
        make_task("active-p2", 20, deadline_delta=timedelta(minutes=15), priority="P2"),
        make_task("done-p1", 100, status="done", deadline_delta=timedelta(minutes=1), priority="P1"),
    ]

    rows = task_rows(tasks, now)

    assert [row["title"] for row in rows] == ["active-p2", "paused-p1"]
    assert rows[1]["status"] == "paused"
    assert rows[1]["is_paused"] is True
    assert rows[1]["urgency"] == "critical"
    assert rows[1]["urgency_label"] == "已暂停 · 10 分内"
    assert rows[1]["work_timer_label"].endswith(" / 1h30m")


def test_task_rows_accept_naive_now_from_ui_callers():
    now = datetime(2026, 5, 12, 8, 0)
    rows = task_rows([make_task("a", 30, deadline_delta=timedelta(minutes=15))], now)

    assert rows[0]["deadline_label"] == "00:15:00"
    assert rows[0]["is_overdue"] is False
