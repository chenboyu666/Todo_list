# Floating Todo

Windows floating task console built with Python and PySide6.

This project is currently in scaffold stage. The package import and test
configuration are available now; app launch and packaging commands become
usable after the later app bootstrap and packaging tasks land.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m floating_todo
```

The `python -m floating_todo` launch command is documented for the completed
app flow and depends on the later app bootstrap task.

## Test

```powershell
python -m pytest -q
```

## Build

```powershell
.\scripts\build.ps1
```

The build script is documented for the completed packaging flow and depends on
the later packaging task.

The packaged app is created at `dist/FloatingTodo/FloatingTodo.exe`.
