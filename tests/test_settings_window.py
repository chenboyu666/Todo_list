from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QCheckBox, QFileDialog, QLabel, QMainWindow, QPushButton

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
        background_random_enabled=True,
        background_folder_path=r"C:\Wallpapers",
        icon_path=r"C:\Icons\todo.ico",
    )
    dialog = SettingsWindow(settings)

    assert dialog.windowTitle() == "设置"
    assert dialog.always_on_top_checkbox.isChecked() is False
    assert dialog.always_on_top_checkbox.text() == "关闭"
    assert dialog.mouse_passthrough_checkbox.isChecked() is False
    assert dialog.mouse_passthrough_checkbox.isEnabled() is False
    assert dialog.lock_position_checkbox.isChecked() is True
    assert dialog.close_to_tray_checkbox.isChecked() is False
    assert dialog.launch_on_startup_checkbox.isChecked() is True
    assert dialog.launch_on_startup_checkbox.text() == "开启"
    assert not hasattr(dialog, "low_distraction_checkbox")
    assert dialog.opacity_slider.minimum() == 30
    assert dialog.opacity_slider.maximum() == 100
    assert dialog.opacity_slider.value() == 72
    assert dialog.lead_minutes_spinbox.minimum() == 1
    assert dialog.lead_minutes_spinbox.maximum() == 240
    assert dialog.lead_minutes_spinbox.value() == 45
    assert not hasattr(dialog, "lead_minutes_step_hint")
    assert "↑ 增加" in dialog.lead_minutes_spinbox.toolTip()
    assert "↓ 减少" in dialog.lead_minutes_spinbox.toolTip()
    assert not hasattr(dialog, "repeat_minutes_spinbox")
    assert not hasattr(dialog, "background_overlay")
    assert "▼ 展开" in dialog.background_resource_combo.toolTip()
    assert "▼ 展开" in dialog.icon_resource_combo.toolTip()
    assert dialog.background_resource_combo.count() == 4
    assert dialog.background_resource_combo.itemText(1) == "一二学习图"
    assert dialog.background_random_enabled_checkbox.isChecked() is True
    assert dialog.background_folder_path_edit.text() == r"C:\Wallpapers"
    assert dialog.background_folder_path_edit.isHidden() is False
    assert dialog.icon_resource_combo.count() == 4
    assert dialog.icon_resource_combo.itemText(3) == "一二布布动图"
    assert dialog.icon_path_edit.text() == r"C:\Icons\todo.ico"
    assert dialog.background_path.isHidden()
    assert dialog.icon_path_edit.isHidden()
    assert dialog.icon_resource_combo.itemText(0) == "自定义图标"
    assert dialog.title_bar is not None
    assert dialog.scroll_area.widgetResizable()
    dialog.show()
    qapp.processEvents()
    title_icon = dialog.findChild(QLabel, "settingsTitleIcon")
    assert title_icon is not None
    assert title_icon.pixmap() is not None
    assert not title_icon.pixmap().isNull()
    assert not dialog.title_bar.findChild(QPushButton, "settingsCloseButton").icon().isNull()
    assert all(not button.icon().isNull() for button in dialog.sidebar_buttons)
    save_top = dialog.save_button.mapTo(dialog, QPoint(0, 0)).y()
    cancel_top = dialog.cancel_button.mapTo(dialog, QPoint(0, 0)).y()
    assert save_top >= dialog.scroll_area.geometry().bottom()
    assert cancel_top >= dialog.scroll_area.geometry().bottom()

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
        "透明度",
        "提前提醒分钟",
        "背景",
        "随机背景文件夹",
        "背景文件夹",
        "图标",
    ):
        assert label in visible_text
    for removed_label in ("低干扰模式", "重复提醒间隔分钟", "背景遮罩", "内置背景", "内置图标", "程序图标"):
        assert removed_label not in visible_text
    assert "右侧 ↑ 增加" not in visible_text
    assert "↓ 减少" not in visible_text

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
    dialog.opacity_slider.setValue(64)
    dialog.lead_minutes_spinbox.setValue(33)
    dialog.icon_path_edit.setText(r"C:\Icons\new-todo.ico")
    dialog.background_resource_combo.setCurrentIndex(1)
    dialog.background_folder_path_edit.setText(r"C:\Wallpapers")
    dialog.background_random_enabled_checkbox.setChecked(True)
    dialog.icon_resource_combo.setCurrentIndex(3)

    updated = dialog.build_settings()

    assert updated is not settings
    assert updated.always_on_top is False
    assert updated.mouse_passthrough is False
    assert updated.lock_position is True
    assert updated.close_to_tray is False
    assert updated.launch_on_startup is True
    assert updated.low_distraction_mode is False
    assert updated.opacity == 0.64
    assert updated.notification_lead_minutes == 33
    assert updated.notification_repeat_minutes == 10
    assert updated.background_enabled is True
    assert updated.background_image_path == "builtin:study"
    assert updated.background_random_enabled is True
    assert updated.background_folder_path == r"C:\Wallpapers"
    assert updated.background_overlay == 0.68
    assert updated.icon_path == "builtin:bubu-motion"
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
    icon_path = tmp_path / "icon.png"

    dialog = SettingsWindow(AppSettings(opacity=0.72), parent)
    dialog.opacity_slider.setValue(58)
    dialog.background_path.setText(str(image_path))
    dialog.background_enabled.setChecked(True)
    dialog.background_folder_path_edit.setText(str(tmp_path))
    dialog.background_random_enabled_checkbox.setChecked(True)
    dialog.icon_path_edit.setText(str(icon_path))

    assert previews
    assert previews[-1].opacity == 0.58
    assert previews[-1].background_image_path == str(image_path)
    assert previews[-1].background_enabled is True
    assert previews[-1].background_random_enabled is True
    assert previews[-1].background_folder_path == str(tmp_path)
    assert previews[-1].background_overlay == 0.68
    assert previews[-1].icon_path == str(icon_path)

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
    assert dialog.background_random_enabled.isChecked() is False

    dialog.close()


def test_settings_window_background_folder_picker_enables_random_mode(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    def fake_get_existing_directory(parent, title, directory):
        return str(tmp_path)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake_get_existing_directory)
    dialog = SettingsWindow(AppSettings())

    dialog.choose_background_folder()

    assert dialog.background_folder_path_edit.text() == str(tmp_path)
    assert dialog.background_random_enabled_checkbox.isChecked() is True
    assert dialog.background_enabled.isChecked() is True
    assert dialog.build_settings().background_folder_path == str(tmp_path)

    dialog.close()


def test_settings_window_icon_picker_accepts_icon_files(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    captured: dict[str, str] = {}
    icon_path = tmp_path / "todo.ico"

    def fake_get_open_file_name(parent, title, directory, file_filter):
        captured["title"] = title
        captured["filter"] = file_filter
        return str(icon_path), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    dialog = SettingsWindow(AppSettings())

    dialog.choose_icon()

    assert captured["title"] == "选择程序图标"
    assert "*.ico" in captured["filter"]
    assert "*.svg" in captured["filter"]
    assert dialog.icon_path_edit.text() == str(icon_path)
    assert dialog.icon_resource_combo.currentIndex() == 0
    assert dialog.icon_resource_combo.itemText(0) == "自定义图标"

    dialog.close()


def test_settings_window_builtin_resources_update_path_fields(qapp: QApplication) -> None:
    from floating_todo.ui.settings_window import SettingsWindow

    dialog = SettingsWindow(AppSettings())

    dialog.background_resource_combo.setCurrentIndex(2)
    dialog.icon_resource_combo.setCurrentIndex(1)

    assert dialog.background_enabled.isChecked() is True
    assert dialog.background_path.text() == "builtin:food"
    assert dialog.background_random_enabled.isChecked() is False
    assert dialog.icon_path_edit.text() == "builtin:study"

    dialog.background_path.setText(r"C:\custom\background.png")
    dialog.icon_path_edit.setText(r"C:\custom\icon.ico")

    assert dialog.background_resource_combo.currentIndex() == 0
    assert dialog.icon_resource_combo.currentIndex() == 0
    assert dialog.background_resource_combo.itemText(0) == "自定义背景"
    assert dialog.icon_resource_combo.itemText(0) == "自定义图标"

    dialog.close()
