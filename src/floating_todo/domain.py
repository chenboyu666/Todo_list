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
