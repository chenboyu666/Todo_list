from __future__ import annotations

from floating_todo.app_identity import resolved_icon_path
from floating_todo.app_resources import BUILTIN_RESOURCES, resolve_resource_path


def test_builtin_resources_exist_and_resolve_from_tokens() -> None:
    assert [resource.id for resource in BUILTIN_RESOURCES] == ["study", "food", "bubu-motion"]

    for resource in BUILTIN_RESOURCES:
        assert resource.path.exists()
        assert resolve_resource_path(resource.value) == resource.path


def test_builtin_resource_can_be_used_as_icon_path() -> None:
    assert resolved_icon_path("builtin:study").name == "study.jpeg"
    assert resolved_icon_path("builtin:bubu-motion").name == "bubu-motion.gif"
