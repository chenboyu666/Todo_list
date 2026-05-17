from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Literal

Priority = Literal["P1", "P2", "P3"]
Status = Literal["active", "paused", "done", "archived"]

PRIORITY_RANK: dict[str, int] = {"P1": 0, "P2": 1, "P3": 2}
VISIBLE_STATUS_RANK: dict[str, int] = {"active": 0, "paused": 1}
VALID_STATUSES = {"active", "paused", "done", "archived"}
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
    reflection: str = ""
    notification_state: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_NOTIFICATION_STATE))

    def __post_init__(self) -> None:
        object.__setattr__(self, "deadline", normalize_datetime(self.deadline))
        object.__setattr__(self, "created_at", normalize_datetime(self.created_at))
        object.__setattr__(self, "updated_at", normalize_datetime(self.updated_at))
        object.__setattr__(self, "completed_at", normalize_datetime(self.completed_at))

        notification_state = dict(DEFAULT_NOTIFICATION_STATE)
        notification_state.update(self.notification_state)
        object.__setattr__(self, "notification_state", MappingProxyType(notification_state))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return normalize_datetime(datetime.fromisoformat(value))


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def task_from_dict(data: dict[str, Any]) -> Task:
    now = utc_now()
    notification_state = dict(DEFAULT_NOTIFICATION_STATE)
    notification_state.update(data.get("notification_state") or {})
    status = str(data.get("status", "active"))
    if status not in VALID_STATUSES:
        status = "active"
    return Task(
        id=str(data["id"]),
        title=str(data["title"]),
        priority=data.get("priority", "P3"),
        effort_minutes=max(0, int(data.get("effort_minutes", 0))),
        deadline=parse_datetime(data.get("deadline")),
        progress=max(0, min(100, int(data.get("progress", 0)))),
        status=status,
        created_at=parse_datetime(data.get("created_at")) or now,
        updated_at=parse_datetime(data.get("updated_at")) or now,
        completed_at=parse_datetime(data.get("completed_at")),
        notes=str(data.get("notes", "")),
        reflection=str(data.get("reflection", "")),
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
        "reflection": task.reflection,
        "notification_state": dict(task.notification_state),
    }


def sort_tasks(tasks: list[Task]) -> list[Task]:
    active = [task for task in tasks if task.status == "active"]
    return sorted(active, key=_task_sort_key)


def sort_visible_tasks(tasks: list[Task]) -> list[Task]:
    visible = [task for task in tasks if task.status in VISIBLE_STATUS_RANK]
    return sorted(
        visible,
        key=lambda task: (
            VISIBLE_STATUS_RANK.get(task.status, 99),
            *_task_sort_key(task),
        ),
    )


def _task_sort_key(task: Task) -> tuple[int, bool, datetime, int, datetime]:
    return (
        PRIORITY_RANK.get(task.priority, 99),
        task.deadline is None,
        task.deadline or datetime.max.replace(tzinfo=timezone.utc),
        -task.effort_minutes,
        task.created_at,
    )


def select_focus_task(tasks: list[Task]) -> Task | None:
    sorted_tasks = sort_tasks(tasks)
    return sorted_tasks[0] if sorted_tasks else None
