from pathlib import Path

from floating_todo.app import app_data_dir, ensure_data_files


def test_app_data_dir_uses_base_path_data_folder(tmp_path):
    assert app_data_dir(tmp_path) == tmp_path / "data"


def test_ensure_data_files_creates_data_folder(tmp_path):
    data_dir = ensure_data_files(tmp_path)

    assert data_dir == tmp_path / "data"
    assert data_dir.exists()
