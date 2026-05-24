from __future__ import annotations

from datetime import datetime

from floating_todo.domain import Task, normalize_datetime, normalize_task_tag, sort_visible_tasks, work_elapsed_seconds, work_target_seconds


PRIORITY_ORDER = ("P1", "P2", "P3")
PRIORITY_DISPLAY = {
    "P1": {"symbol": "▲", "text": "高"},
    "P2": {"symbol": "◆", "text": "中"},
    "P3": {"symbol": "▼", "text": "低"},
}


def priority_symbol(priority: str) -> str:
    return PRIORITY_DISPLAY.get(priority, {"symbol": "•"})["symbol"]


def priority_text(priority: str) -> str:
    return PRIORITY_DISPLAY.get(priority, {"text": str(priority)})["text"]


def priority_display_label(priority: str) -> str:
    display = PRIORITY_DISPLAY.get(priority)
    if display is None:
        return str(priority)
    return f"{display['symbol']} {display['text']}"


def priority_from_display(value: str) -> str:
    value = str(value).strip()
    if value in PRIORITY_DISPLAY:
        return value
    for priority, display in PRIORITY_DISPLAY.items():
        candidates = {
            display["text"],
            f"{display['symbol']} {display['text']}",
            f"{display['symbol']}{display['text']}",
        }
        if value in candidates:
            return priority
    return "P2"


def deadline_at_label(deadline: datetime | None) -> str:
    if deadline is None:
        return "--"
    return normalize_datetime(deadline).astimezone().strftime("%Y-%m-%d %H:%M")


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


def duration_clock_label(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def effort_short_label(minutes: int) -> str:
    minutes = max(0, int(minutes))
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours}h{remainder:02d}m"
    if hours:
        return f"{hours}h"
    return f"{remainder}m"


def work_timer_label(task: Task, now: datetime) -> str:
    elapsed = duration_clock_label(work_elapsed_seconds(task, now))
    target_minutes = max(0, work_target_seconds(task) // 60)
    return f"{elapsed} / {effort_short_label(target_minutes)}"


def deadline_urgency(deadline: datetime | None, now: datetime) -> tuple[str, str]:
    if deadline is None:
        return "none", "无截止"
    deadline = normalize_datetime(deadline)
    now = normalize_datetime(now)
    remaining_seconds = (deadline - now).total_seconds()
    if remaining_seconds < 0:
        return "overdue", "已超时"
    if remaining_seconds <= 10 * 60:
        return "critical", "10 分内"
    if remaining_seconds <= 30 * 60:
        return "urgent", "半小时内"
    if remaining_seconds <= 2 * 60 * 60:
        return "soon", "临近"
    return "normal", "充裕"


def today_completion_percent(tasks: list[Task]) -> int:
    visible = [task for task in tasks if task.status in {"active", "paused", "done"}]
    if not visible:
        return 0
    done = [task for task in visible if task.status == "done"]
    return round(len(done) / len(visible) * 100)


def task_rows(tasks: list[Task], now: datetime) -> list[dict[str, object]]:
    now = normalize_datetime(now)
    rows: list[dict[str, object]] = []
    for task in sort_visible_tasks(tasks):
        urgency, urgency_label = deadline_urgency(task.deadline, now)
        if task.status == "paused":
            urgency_label = f"已暂停 · {urgency_label}"
        rows.append(
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "is_paused": task.status == "paused",
                "notes": task.notes,
                "tag": normalize_task_tag(getattr(task, "tag", "")),
                "priority": task.priority,
                "effort_label": f"{task.effort_minutes} min",
                "work_timer_label": work_timer_label(task, now),
                "work_elapsed_label": duration_clock_label(work_elapsed_seconds(task, now)),
                "work_target_label": effort_short_label(max(0, work_target_seconds(task) // 60)),
                "deadline_label": countdown_label(task.deadline, now),
                "deadline_at_label": deadline_at_label(task.deadline),
                "progress": task.progress,
                "progress_label": f"{task.progress}%",
                "is_overdue": bool(task.deadline and task.deadline < now),
                "urgency": urgency,
                "urgency_label": urgency_label,
            }
        )
    return rows
