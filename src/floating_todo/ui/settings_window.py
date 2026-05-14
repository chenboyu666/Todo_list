from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from floating_todo.settings import AppSettings


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = settings
        self.setMinimumWidth(460)

        self.always_on_top = QCheckBox()
        self.always_on_top.setChecked(settings.always_on_top)
        self.always_on_top_checkbox = self.always_on_top
        self.lock_position = QCheckBox()
        self.lock_position.setChecked(settings.lock_position)
        self.lock_position_checkbox = self.lock_position
        self.close_to_tray = QCheckBox()
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.close_to_tray_checkbox = self.close_to_tray
        self.launch_on_startup = QCheckBox()
        self.launch_on_startup.setChecked(settings.launch_on_startup)
        self.launch_on_startup_checkbox = self.launch_on_startup
        self.low_distraction = QCheckBox()
        self.low_distraction.setChecked(settings.low_distraction_mode)
        self.low_distraction_checkbox = self.low_distraction
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(round(settings.opacity * 100))
        self.opacity_slider = self.opacity
        self.lead_minutes = QSpinBox()
        self.lead_minutes.setRange(1, 240)
        self.lead_minutes.setValue(settings.notification_lead_minutes)
        self.lead_minutes_spin = self.lead_minutes
        self.lead_minutes_spinbox = self.lead_minutes
        self.repeat_minutes = QSpinBox()
        self.repeat_minutes.setRange(1, 240)
        self.repeat_minutes.setValue(settings.notification_repeat_minutes)
        self.repeat_minutes_spin = self.repeat_minutes
        self.repeat_minutes_spinbox = self.repeat_minutes

        self.background_enabled = QCheckBox()
        self.background_enabled.setChecked(settings.background_enabled)
        self.background_path = QLineEdit(settings.background_image_path)
        self.background_path.setPlaceholderText("选择背景图片")
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self.choose_background)
        self.background_overlay = QSlider(Qt.Horizontal)
        self.background_overlay.setRange(25, 95)
        self.background_overlay.setValue(round(settings.background_overlay * 100))

        form = QFormLayout()
        form.addRow("窗口始终置顶", self.always_on_top)
        form.addRow("锁定位置", self.lock_position)
        form.addRow("关闭时进入托盘", self.close_to_tray)
        form.addRow("Windows 开机启动", self.launch_on_startup)
        form.addRow("低干扰模式", self.low_distraction)
        form.addRow("透明度", self.opacity)
        form.addRow("提前提醒分钟", self.lead_minutes)
        form.addRow("重复提醒间隔分钟", self.repeat_minutes)
        form.addRow("启用背景图片", self.background_enabled)

        background_layout = QHBoxLayout()
        background_layout.addWidget(self.background_path, 1)
        background_layout.addWidget(browse_button)
        form.addRow("背景图片", background_layout)
        form.addRow("背景遮罩", self.background_overlay)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            self.background_path.text(),
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)",
        )
        if path:
            self.background_path.setText(path)
            self.background_enabled.setChecked(True)

    def build_settings(self) -> AppSettings:
        return replace(
            self.settings,
            always_on_top=self.always_on_top.isChecked(),
            lock_position=self.lock_position.isChecked(),
            close_to_tray=self.close_to_tray.isChecked(),
            launch_on_startup=self.launch_on_startup.isChecked(),
            low_distraction_mode=self.low_distraction.isChecked(),
            opacity=self.opacity.value() / 100,
            notification_lead_minutes=self.lead_minutes.value(),
            notification_repeat_minutes=self.repeat_minutes.value(),
            background_enabled=self.background_enabled.isChecked(),
            background_image_path=self.background_path.text().strip(),
            background_overlay=self.background_overlay.value() / 100,
        )
