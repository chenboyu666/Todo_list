from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from floating_todo.domain import Task, format_datetime, parse_datetime, utc_now

EVENT_TO_FLAG = {
    "deadline_warning": "deadline_warning_sent",
    "deadline_due": "deadline_due_sent",
}
WARNING_LAST_SENT_KEY = "deadline_warning_last_sent_at"
DEADLINE_DUE_SENT_AT_KEY = "deadline_due_sent_at"


def reminder_events(task: Task, now: datetime, lead_minutes: int, repeat_minutes: int = 10) -> list[str]:
    if lead_minutes < 0:
        raise ValueError("lead_minutes must be non-negative")
    if repeat_minutes <= 0:
        raise ValueError("repeat_minutes must be positive")
    if task.status != "active" or task.deadline is None:
        return []
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    events: list[str] = []
    if now >= task.deadline:
        if not task.notification_state.get("deadline_due_sent", False):
            events.append("deadline_due")
        return events

    warning_at = task.deadline - timedelta(minutes=lead_minutes)
    last_warning_at = _notification_datetime(task, WARNING_LAST_SENT_KEY)
    should_repeat_warning = (
        last_warning_at is None
        or now - last_warning_at >= timedelta(minutes=repeat_minutes)
    )
    if now >= warning_at and should_repeat_warning:
        events.append("deadline_warning")
    return events


def mark_event_sent(task: Task, event: str, sent_at: datetime | None = None) -> Task:
    try:
        flag = EVENT_TO_FLAG[event]
    except KeyError as exc:
        raise ValueError(f"Unknown reminder event: {event}") from exc
    sent_at = sent_at or utc_now()
    state = dict(task.notification_state)
    state[flag] = True
    if event == "deadline_warning":
        state[WARNING_LAST_SENT_KEY] = format_datetime(sent_at)
    if event == "deadline_due":
        state[DEADLINE_DUE_SENT_AT_KEY] = format_datetime(sent_at)
    return replace(task, notification_state=state)


def _notification_datetime(task: Task, key: str) -> datetime | None:
    value = task.notification_state.get(key)
    if not isinstance(value, str):
        return None
    return parse_datetime(value)
