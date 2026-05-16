from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BUILTIN_RESOURCE_PREFIX = "builtin:"


@dataclass(frozen=True)
class BuiltinResource:
    id: str
    label: str
    filename: str

    @property
    def value(self) -> str:
        return f"{BUILTIN_RESOURCE_PREFIX}{self.id}"

    @property
    def path(self) -> Path:
        return resources_dir() / self.filename


BUILTIN_RESOURCES = (
    BuiltinResource("study", "一二学习图", "study.jpeg"),
    BuiltinResource("food", "一二干饭图", "food.jpg"),
    BuiltinResource("bubu-motion", "一二布布动图", "bubu-motion.gif"),
)


def resources_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "resources"


def builtin_resource_by_value(value: str) -> BuiltinResource | None:
    if not value.startswith(BUILTIN_RESOURCE_PREFIX):
        return None
    resource_id = value[len(BUILTIN_RESOURCE_PREFIX) :]
    return next((resource for resource in BUILTIN_RESOURCES if resource.id == resource_id), None)


def resolve_resource_path(value: str) -> Path:
    resource = builtin_resource_by_value(str(value or ""))
    if resource is not None:
        return resource.path
    return Path(str(value or "")).expanduser()
