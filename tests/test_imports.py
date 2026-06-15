import os
import subprocess
import sys
from pathlib import Path


def test_package_imports():
    import floating_todo

    assert floating_todo.__version__ == "1.1.0"


def test_main_window_import_defers_history_webengine_modules():
    project_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(project_root / "src"), env.get("PYTHONPATH", "")])
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import floating_todo.ui.main_window; "
                "print('floating_todo.ui.history_window' in sys.modules); "
                "print('PySide6.QtWebEngineWidgets' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.stdout.splitlines() == ["False", "False"]
