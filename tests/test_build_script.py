from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build.ps1"
README = PROJECT_ROOT / "README.md"


def test_build_script_uses_repeatable_pyinstaller_onedir_contract():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in script
    assert 'python -m venv ".venv"' in script
    assert '.venv\\Scripts\\python.exe" -m pip install --upgrade pip' in script
    assert '.venv\\Scripts\\python.exe" -m pip install -r "requirements.txt"' in script
    assert '"--noconfirm"' in script
    assert '"--onedir"' in script
    assert '"--windowed"' in script
    assert '"--name"' in script
    assert '"Todo list"' in script
    assert '"--add-data"' in script
    assert '"src/floating_todo/assets;floating_todo/assets"' in script
    assert '"--collect-all"' not in script
    assert '"PySide6.QtCore"' in script
    assert '"PySide6.QtGui"' in script
    assert '"PySide6.QtWidgets"' in script
    assert '"PySide6.QtSvg"' in script
    assert '"--exclude-module"' in script
    assert '"PySide6.QtWebEngineWidgets"' in script
    assert '"src/floating_todo/__main__.py"' in script
    assert "dist/Todo list/data" in script
    assert "Build complete: dist/Todo list/Todo list.exe" in script


def test_build_script_safely_cleans_only_project_directories():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "function Remove-ProjectDirectory" in script
    assert "Resolve-Path -LiteralPath $ProjectRoot" in script
    assert "StartsWith($rootPath" in script
    assert "Remove-Item -LiteralPath $resolvedTarget" in script
    assert "-Recurse" in script
    assert "-Force" in script
    assert "Remove-ProjectDirectory -RelativePath \"build\"" in script
    assert "Remove-ProjectDirectory -RelativePath \"dist\"" in script


def test_readme_documents_current_build_flow():
    readme = README.read_text(encoding="utf-8")

    assert "```powershell\n.\\scripts\\build.ps1\n```" in readme
    assert "dist/Todo list/Todo list.exe" in readme
    assert "data/" in readme
    assert "scaffold stage" not in readme
    assert "later packaging task" not in readme
    assert "later app bootstrap task" not in readme


def test_readme_installs_project_before_local_run_command():
    readme = README.read_text(encoding="utf-8")
    run_section = readme.split("## Run Locally", 1)[1].split("## Test", 1)[0]

    editable_install = run_section.index("pip install -e .")
    launch_command = run_section.index("python -m floating_todo")

    assert editable_install < launch_command
