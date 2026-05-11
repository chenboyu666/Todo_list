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
