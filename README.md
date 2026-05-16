# Todo list

Windows floating task console built with Python and PySide6.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
python -m floating_todo
```

## Test

```powershell
python -m pytest -q
```

## Build

```powershell
.\scripts\build.ps1
```

The packaged app is created at `dist/Todo list/Todo list.exe`.
The packaged folder includes `data/` for portable tasks and settings.
