from __future__ import annotations

from floating_todo.app_identity import resolved_icon_path
from floating_todo.app_resources import (
    BUILTIN_RESOURCES,
    DATA_RESOURCE_PREFIX,
    background_image_candidates,
    materialize_custom_resource,
    resolve_resource_path,
)


def test_builtin_resources_exist_and_resolve_from_tokens() -> None:
    assert [resource.id for resource in BUILTIN_RESOURCES] == ["study", "food", "bubu-motion"]

    for resource in BUILTIN_RESOURCES:
        assert resource.path.exists()
        assert resolve_resource_path(resource.value) == resource.path


def test_builtin_resource_can_be_used_as_icon_path() -> None:
    assert resolved_icon_path("builtin:study").name == "study.jpeg"
    assert resolved_icon_path("builtin:bubu-motion").name == "bubu-motion.gif"


def test_background_image_candidates_returns_supported_files(tmp_path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "b.gif").write_bytes(b"x")
    (tmp_path / "note.txt").write_text("skip", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "c.png").write_bytes(b"x")

    assert [path.name for path in background_image_candidates(str(tmp_path))] == ["a.jpg", "b.gif"]
    assert background_image_candidates(str(tmp_path / "missing")) == []


def test_custom_resource_is_copied_into_data_resources(tmp_path) -> None:
    source = tmp_path / "picked background.PNG"
    source.write_bytes(b"image")
    data_dir = tmp_path / "data"

    token = materialize_custom_resource(str(source), data_dir, "background")

    assert token.startswith(DATA_RESOURCE_PREFIX)
    stored = data_dir / "resources" / token.removeprefix(DATA_RESOURCE_PREFIX)
    assert stored.exists()
    assert stored.suffix == ".png"
    assert stored.read_bytes() == b"image"
    assert materialize_custom_resource(token, data_dir, "background") == token
    assert materialize_custom_resource("builtin:study", data_dir, "background") == "builtin:study"


def test_data_resource_token_resolves_relative_to_runtime_data_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resource = tmp_path / "data" / "resources" / "icon.png"

    assert resolve_resource_path("data:icon.png") == resource
