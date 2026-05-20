from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from floating_todo.domain import Task, task_from_dict, task_to_dict, utc_now


class JsonTaskStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load_tasks(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return []
            tasks, migrated = self._tasks_from_raw(raw)
            if migrated:
                self.save_tasks(tasks)
            return tasks
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            self._preserve_broken_file()
            return []

    def save_tasks(self, tasks: list[Task]) -> None:
        payload = [task_to_dict(task) for task in tasks]
        atomic_write_json(self.path, payload)

    def _preserve_broken_file(self) -> None:
        if not self.path.exists():
            return
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        broken_path = self.path.with_name(f"{self.path.name}.broken-{timestamp}")
        shutil.copy2(self.path, broken_path)

    def _tasks_from_raw(self, raw: list[object]) -> tuple[list[Task], bool]:
        tasks: list[Task] = []
        migrated = False
        started_at = utc_now()
        for item in raw:
            if not isinstance(item, dict):
                continue
            task = task_from_dict(item)
            if "work_elapsed_seconds" not in item:
                migrated = True
            if "work_started_at" not in item:
                migrated = True
                if task.status == "active":
                    task = replace(task, work_started_at=started_at)
            tasks.append(task)
        return tasks, migrated


def atomic_write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def load_json_object(path: Path, default: dict[str, object]) -> dict[str, object]:
    path = Path(path)
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    return raw


def save_json_object(path: Path, payload: dict[str, object]) -> None:
    atomic_write_json(path, payload)
