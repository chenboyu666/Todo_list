from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build.ps1"
README = PROJECT_ROOT / "README.md"
GITIGNORE = PROJECT_ROOT / ".gitignore"


def test_build_script_uses_repeatable_pyinstaller_onefile_contract():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in script
    assert 'python -m venv ".venv"' in script
    assert '.venv\\Scripts\\python.exe" -m pip install --upgrade pip' in script
    assert '.venv\\Scripts\\python.exe" -m pip install -r "requirements.txt"' in script
    assert '"--noconfirm"' in script
    assert '"--onefile"' in script
    assert '"--onedir"' not in script
    assert '"--windowed"' in script
    assert '"--name"' in script
    assert '"Todo list"' in script
    assert '"--add-data"' in script
    assert '"src/floating_todo/assets;floating_todo/assets"' in script
    assert '"--collect-all"' in script
    assert '"PySide6.QtCore"' in script
    assert '"PySide6.QtGui"' in script
    assert '"PySide6.QtWidgets"' in script
    assert '"PySide6.QtSvg"' in script
    assert '"PySide6.QtWebEngineCore"' in script
    assert '"--exclude-module"' in script
    assert '"PySide6.QtWebEngineWidgets"' in script
    assert '"PySide6.QtWebChannel"' in script
    assert '"PySide6.QtQml"' in script
    assert '"PySide6.QtQuick"' in script
    assert '"PySide6.QtQuickWidgets"' in script
    assert '"PySide6.QtPositioning"' in script
    assert '"PySide6.QtPrintSupport"' in script
    assert '"--exclude-module",\n    "PySide6.QtWebEngineCore"' not in script
    assert '"--exclude-module",\n    "PySide6.QtWebEngineWidgets"' not in script
    assert '"--exclude-module",\n    "PySide6.QtQml"' not in script
    assert '"--exclude-module",\n    "PySide6.QtQuick"' not in script
    assert '"--exclude-module",\n    "PySide6.QtQuickWidgets"' not in script
    assert '"--exclude-module",\n    "PySide6.QtPositioning"' not in script
    assert '"--exclude-module",\n    "PySide6.QtPrintSupport"' not in script
    assert '"src/floating_todo/__main__.py"' in script
    assert "dist/data" in script
    assert "Build complete: dist/Todo list.exe" in script


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


def test_readme_documents_download_user_flow():
    readme = README.read_text(encoding="utf-8")

    assert "https://github.com/chenboyu666/Todo_list/releases/download/v1.0/Todo-list-V1.0-windows.exe" in readme
    assert "下载后双击 `Todo-list-V1.0-windows.exe` 即可运行。" in readme
    assert "3D 洞察图" in readme
    assert "CSV 导出" in readme
    assert "data\\" in readme
    assert "## 本地开发" not in readme
    assert "## 测试" not in readme
    assert "## 构建" not in readme
    assert "## 项目结构" not in readme
    assert "dist\\Todo list.exe" not in readme
    assert "release\\V1.0" not in readme
    assert "快捷方式" not in readme
    assert "常见问题" not in readme
    assert "不提交到 GitHub" not in readme
    assert "scaffold stage" not in readme
    assert "later packaging task" not in readme
    assert "later app bootstrap task" not in readme


def test_readme_describes_portable_data_folder():
    readme = README.read_text(encoding="utf-8")

    assert "程序会在 exe 同级目录创建" in readme
    assert "移动程序时，请把 `Todo-list-V1.0-windows.exe` 和同级 `data` 文件夹一起移动。" in readme


def test_shortcuts_are_ignored_for_release_artifacts():
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    assert "*.lnk" in gitignore
