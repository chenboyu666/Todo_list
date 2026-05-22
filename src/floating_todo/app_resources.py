from __future__ import annotations

import hashlib
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

BUILTIN_RESOURCE_PREFIX = "builtin:"
DATA_RESOURCE_PREFIX = "data:"
BACKGROUND_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif"}


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


def default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path.cwd() / "data"


def data_resources_dir(data_dir: Path | str | None = None) -> Path:
    return Path(data_dir) / "resources" if data_dir is not None else default_data_dir() / "resources"


def builtin_resource_by_value(value: str) -> BuiltinResource | None:
    if not value.startswith(BUILTIN_RESOURCE_PREFIX):
        return None
    resource_id = value[len(BUILTIN_RESOURCE_PREFIX) :]
    return next((resource for resource in BUILTIN_RESOURCES if resource.id == resource_id), None)


def resolve_resource_path(value: str) -> Path:
    text = str(value or "")
    resource = builtin_resource_by_value(text)
    if resource is not None:
        return resource.path
    if text.startswith(DATA_RESOURCE_PREFIX):
        resource_name = Path(text[len(DATA_RESOURCE_PREFIX) :].replace("\\", "/")).name
        return data_resources_dir() / resource_name
    return Path(text).expanduser()


def materialize_custom_resource(value: str, data_dir: Path | str, kind: str) -> str:
    text = str(value or "").strip()
    if not text or text.startswith(BUILTIN_RESOURCE_PREFIX) or text.startswith(DATA_RESOURCE_PREFIX):
        return text

    source = Path(text).expanduser()
    if not source.is_file():
        return text

    target_dir = data_resources_dir(data_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = _stored_resource_name(source, kind)
    target = target_dir / target_name

    try:
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    except OSError:
        return text
    return f"{DATA_RESOURCE_PREFIX}{target_name}"


def _stored_resource_name(source: Path, kind: str) -> str:
    safe_kind = re.sub(r"[^A-Za-z0-9_-]+", "-", str(kind or "resource")).strip("-") or "resource"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-") or "resource"
    safe_stem = safe_stem[:40]
    try:
        unique_source = str(source.resolve())
    except OSError:
        unique_source = str(source)
    digest = hashlib.sha1(unique_source.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"{safe_kind}-{safe_stem}-{digest}{source.suffix.lower()}"


def background_image_candidates(folder_path: str) -> list[Path]:
    folder = Path(str(folder_path or "")).expanduser()
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in BACKGROUND_IMAGE_EXTENSIONS
    )
