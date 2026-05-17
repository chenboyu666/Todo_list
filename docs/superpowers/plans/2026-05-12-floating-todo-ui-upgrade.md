# Floating Todo UI Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved UI/interaction upgrade to the Windows FloatingTodo app.

**Architecture:** Extend existing domain/settings JSON models with backward-compatible optional fields, keep UI changes in PySide6 widgets, and preserve the existing store/tray/packaging boundaries. MainWindow owns shell interactions and task focus; dialogs own editing/settings/history workflows.

**Tech Stack:** Python 3.10+, PySide6, pytest, PyInstaller.

---

### Task 1: Data and Settings Fields

**Files:**
- Modify: `src/floating_todo/domain.py`
- Modify: `src/floating_todo/settings.py`

- [ ] Add `Task.reflection` with JSON round-trip support.
- [ ] Add settings for `focus_task_id`, `background_image_path`, `background_enabled`, and `background_overlay`.
- [ ] Keep defaults compatible with old JSON files.

### Task 2: Dialog and Settings UI

**Files:**
- Modify: `src/floating_todo/ui/task_dialog.py`
- Modify: `src/floating_todo/ui/settings_window.py`

- [ ] Replace text-like deadline editing with date, hour, and minute controls.
- [ ] Use a slider for manual task progress.
- [ ] Add background image settings controls.
- [ ] Preserve existing widget aliases used by tests.

### Task 3: Main Window Interaction Upgrade

**Files:**
- Modify: `src/floating_todo/ui/main_window.py`

- [ ] Make the window frameless and add a draggable custom title bar.
- [ ] Add focus-card drop handling and draggable task row cards.
- [ ] Persist focus task selection.
- [ ] Use sliders for focus and row progress.
- [ ] Apply background image settings.
- [ ] Preserve existing task/settings/tray/reminder behavior.

### Task 4: History View

**Files:**
- Create: `src/floating_todo/ui/history_window.py`
- Modify: `src/floating_todo/ui/main_window.py`

- [ ] Add history button.
- [ ] Show completed tasks with completion status.
- [ ] Allow editing and saving reflection text.

### Task 5: Verification and Packaging

**Files:**
- Create/modify tests as needed.

- [ ] Add focused tests for the new UI behaviors.
- [ ] Run `python -m pytest -q`.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1`.
- [ ] Smoke start and stop packaged exe.
- [ ] Commit the upgrade.
