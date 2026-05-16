from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QLabel, QMainWindow

from floating_todo.settings import AppSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    yield app


def test_settings_window_initializes_controls_from_settings(qapp: QApplication) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    settings = AppSettings(
        always_on_top=False,
        mouse_passthrough=True,
        lock_position=True,
        close_to_tray=False,
        launch_on_startup=True,
        opacity=0.72,
        low_distraction_mode=True,
        notification_lead_minutes=45,
        notification_repeat_minutes=12,
    )
    dialog = SettingsWindow(settings)

    assert dialog.windowTitle() == "设置"
    assert dialog.always_on_top_checkbox.isChecked() is False
    assert dialog.mouse_passthrough_checkbox.isChecked() is False
    assert dialog.mouse_passthrough_checkbox.isEnabled() is False
    assert dialog.lock_position_checkbox.isChecked() is True
    assert dialog.close_to_tray_checkbox.isChecked() is False
    assert dialog.launch_on_startup_checkbox.isChecked() is True
    assert dialog.low_distraction_checkbox.isChecked() is True
    assert dialog.opacity_slider.minimum() == 30
    assert dialog.opacity_slider.maximum() == 100
    assert dialog.opacity_slider.value() == 72
    assert dialog.lead_minutes_spinbox.minimum() == 1
    assert dialog.lead_minutes_spinbox.maximum() == 240
    assert dialog.lead_minutes_spinbox.value() == 45
    assert dialog.repeat_minutes_spinbox.minimum() == 1
    assert dialog.repeat_minutes_spinbox.maximum() == 240
    assert dialog.repeat_minutes_spinbox.value() == 12

    visible_text = "\n".join(
        [widget.text() for widget in dialog.findChildren(QCheckBox)]
        + [widget.text() for widget in dialog.findChildren(QLabel)]
    )
    for label in (
        "窗口始终置顶",
        "鼠标穿透",
        "穿透后无法直接点击浮窗",
        "锁定位置",
        "关闭时进入托盘",
        "Windows 开机启动",
        "低干扰模式",
        "透明度",
        "提前提醒分钟",
        "重复提醒间隔分钟",
    ):
        assert label in visible_text

    dialog.close()


def test_build_settings_returns_updated_copy_preserving_other_fields(qapp: QApplication) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    settings = AppSettings(window_geometry={"x": 9, "y": 8, "width": 500, "height": 400}, theme="custom")
    dialog = SettingsWindow(settings)
    dialog.always_on_top_checkbox.setChecked(False)
    dialog.mouse_passthrough_checkbox.setChecked(True)
    dialog.lock_position_checkbox.setChecked(True)
    dialog.close_to_tray_checkbox.setChecked(False)
    dialog.launch_on_startup_checkbox.setChecked(True)
    dialog.low_distraction_checkbox.setChecked(True)
    dialog.opacity_slider.setValue(64)
    dialog.lead_minutes_spinbox.setValue(33)
    dialog.repeat_minutes_spinbox.setValue(9)

    updated = dialog.build_settings()

    assert updated is not settings
    assert updated.always_on_top is False
    assert updated.mouse_passthrough is False
    assert updated.lock_position is True
    assert updated.close_to_tray is False
    assert updated.launch_on_startup is True
    assert updated.low_distraction_mode is True
    assert updated.opacity == 0.64
    assert updated.notification_lead_minutes == 33
    assert updated.notification_repeat_minutes == 9
    assert dict(updated.window_geometry) == {"x": 9, "y": 8, "width": 500, "height": 400}
    assert updated.theme == "custom"

    dialog.close()


def test_mouse_passthrough_requires_topmost_setting(qapp: QApplication) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    dialog = SettingsWindow(AppSettings(always_on_top=True, mouse_passthrough=True))

    assert dialog.mouse_passthrough_checkbox.isChecked() is True
    assert dialog.build_settings().mouse_passthrough is True

    dialog.always_on_top_checkbox.setChecked(False)

    assert dialog.mouse_passthrough_checkbox.isChecked() is False
    assert dialog.mouse_passthrough_checkbox.isEnabled() is False
    assert dialog.build_settings().mouse_passthrough is False

    dialog.close()


def test_settings_window_previews_opacity_and_background(qapp: QApplication, tmp_path) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    parent = QMainWindow()
    previews: list[AppSettings] = []
    parent.preview_settings = lambda settings: previews.append(settings)
    image_path = tmp_path / "preview.png"

    dialog = SettingsWindow(AppSettings(opacity=0.72), parent)
    dialog.opacity_slider.setValue(58)
    dialog.background_path.setText(str(image_path))
    dialog.background_enabled.setChecked(True)
    dialog.background_overlay.setValue(45)

    assert previews
    assert previews[-1].opacity == 0.58
    assert previews[-1].background_image_path == str(image_path)
    assert previews[-1].background_enabled is True
    assert previews[-1].background_overlay == 0.45

    dialog.close()
    parent.close()


def test_settings_window_background_picker_accepts_gif(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    captured: dict[str, str] = {}
    gif_path = tmp_path / "motion.gif"

    def fake_get_open_file_name(parent, title, directory, file_filter):
        captured["filter"] = file_filter
        return str(gif_path), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    dialog = SettingsWindow(AppSettings())

    dialog.choose_background()

    assert "*.gif" in captured["filter"]
    assert dialog.background_path.text() == str(gif_path)
    assert dialog.background_enabled.isChecked() is True

    dialog.close()
