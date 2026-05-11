from __future__ import annotations

from datetime import datetime

from floating_todo.domain import Task, normalize_datetime, sort_tasks


def countdown_label(deadline: datetime | None, now: datetime) -> str:
    if deadline is None:
        return "--:--:--"
    deadline = normalize_datetime(deadline)
    now = normalize_datetime(now)
    delta = deadline - now
    past = delta.total_seconds() < 0
    total_seconds = abs(int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    label = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"超时 {label}" if past else label


def today_completion_percent(tasks: list[Task]) -> int:
    visible = [task for task in tasks if task.status in {"active", "done"}]
    if not visible:
        return 0
    done = [task for task in visible if task.status == "done"]
    return round(len(done) / len(visible) * 100)


def task_rows(tasks: list[Task], now: datetime) -> list[dict[str, object]]:
    now = normalize_datetime(now)
    rows: list[dict[str, object]] = []
    for task in sort_tasks(tasks):
        rows.append(
            {
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "effort_label": f"{task.effort_minutes} min",
                "deadline_label": countdown_label(task.deadline, now),
                "progress": task.progress,
                "progress_label": f"{task.progress}%",
                "is_overdue": bool(task.deadline and task.deadline < now),
            }
        )
    return rows
