from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from floating_todo.settings import AppSettings


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.setMinimumWidth(320)

        self.always_on_top_checkbox = QCheckBox("窗口始终置顶")
        self.lock_position_checkbox = QCheckBox("锁定位置")
        self.close_to_tray_checkbox = QCheckBox("关闭时进入托盘")
        self.launch_on_startup_checkbox = QCheckBox("Windows 开机启动")
        self.low_distraction_checkbox = QCheckBox("低干扰模式")
        for checkbox in (
            self.always_on_top_checkbox,
            self.lock_position_checkbox,
            self.close_to_tray_checkbox,
            self.launch_on_startup_checkbox,
            self.low_distraction_checkbox,
        ):
            checkbox.setToolTip(checkbox.text())

        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setToolTip("透明度")

        self.lead_minutes_spinbox = QSpinBox()
        self.lead_minutes_spinbox.setRange(1, 240)
        self.lead_minutes_spinbox.setToolTip("提前提醒分钟")

        self._load_settings()
        self._build_ui()

    def _load_settings(self) -> None:
        self.always_on_top_checkbox.setChecked(self.settings.always_on_top)
        self.lock_position_checkbox.setChecked(self.settings.lock_position)
        self.close_to_tray_checkbox.setChecked(self.settings.close_to_tray)
        self.launch_on_startup_checkbox.setChecked(self.settings.launch_on_startup)
        self.low_distraction_checkbox.setChecked(self.settings.low_distraction_mode)
        self.opacity_slider.setValue(round(self.settings.opacity * 100))
        self.lead_minutes_spinbox.setValue(self.settings.notification_lead_minutes)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.addRow(self.always_on_top_checkbox)
        form.addRow(self.lock_position_checkbox)
        form.addRow(self.close_to_tray_checkbox)
        form.addRow(self.launch_on_startup_checkbox)
        form.addRow(self.low_distraction_checkbox)
        form.addRow(QLabel("透明度"), self.opacity_slider)
        form.addRow(QLabel("提前提醒分钟"), self.lead_minutes_spinbox)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def build_settings(self) -> AppSettings:
        return replace(
            self.settings,
            always_on_top=self.always_on_top_checkbox.isChecked(),
            lock_position=self.lock_position_checkbox.isChecked(),
            close_to_tray=self.close_to_tray_checkbox.isChecked(),
            launch_on_startup=self.launch_on_startup_checkbox.isChecked(),
            opacity=self.opacity_slider.value() / 100,
            low_distraction_mode=self.low_distraction_checkbox.isChecked(),
            notification_lead_minutes=self.lead_minutes_spinbox.value(),
        )
