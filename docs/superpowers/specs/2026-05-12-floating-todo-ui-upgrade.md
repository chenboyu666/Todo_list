# Floating Todo UI Upgrade Spec

## Goal

Improve the first packaged FloatingTodo build based on visual review feedback: make the window borderless, support focus-task drag selection, make progress draggable, improve deadline editing, add a history/reflection view, and allow a configurable background image.

## Requirements

- The main window uses a frameless shell with a custom title bar. The title bar remains draggable unless the position is locked.
- A task from the list can be assigned as the current focus task by dragging it into the focus card. The selected focus task is persisted in settings.
- Focus and row progress use sliders. Changing a slider updates the task progress and persists the JSON file.
- The task dialog uses a polished dark panel layout. Deadline editing is split into date, hour, and minute controls.
- Completed tasks are available in a history window. Each completed task can store and update a reflection field.
- Settings support a background image path, enable/disable toggle, and overlay strength. The main window applies the image while preserving text contrast.
- Existing tray, reminder, startup, geometry, and packaging behavior must continue to work.

## Design Notes

- Keep the calm dark task-console style. Avoid flashy effects and keep controls dense enough for desktop daily use.
- Preserve old public widget aliases where tests or future code may depend on them.
- Store new user preferences in `AppSettings`; store task reflections in `Task`.
- Use JSON-compatible fields only so old data remains readable.

## Verification

- Unit/UI tests cover the new focus task, progress slider, background settings, and history reflection behavior.
- Full pytest suite must pass.
- PyInstaller build must still produce `dist/FloatingTodo/FloatingTodo.exe`.
