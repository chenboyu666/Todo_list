from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)

from floating_todo.app_resources import BUILTIN_RESOURCES, BUILTIN_RESOURCE_PREFIX
from floating_todo.app_identity import ICON_FILE_FILTER
from floating_todo.settings import (
    AppSettings,
    DEFAULT_BACKGROUND_OVERLAY,
    DEFAULT_LOW_DISTRACTION_MODE,
    DEFAULT_NOTIFICATION_REPEAT_MINUTES,
)


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings = settings
        self._preview_ready = False
        self.setMinimumWidth(460)

        self.always_on_top = QCheckBox()
        self.always_on_top.setChecked(settings.always_on_top)
        self.always_on_top_checkbox = self.always_on_top
        self.mouse_passthrough = QCheckBox()
        self.mouse_passthrough.setChecked(settings.mouse_passthrough and settings.always_on_top)
        self.mouse_passthrough.setToolTip("开启后窗口仍显示在最上层，但鼠标点击会落到后方窗口。")
        self.mouse_passthrough_checkbox = self.mouse_passthrough
        self.passthrough_hint = QLabel("穿透后无法直接点击浮窗；右键托盘图标，选择“退出鼠标穿透”即可恢复普通模式。")
        self.passthrough_hint.setWordWrap(True)
        self.passthrough_hint.setStyleSheet("color: #8FA7B8; font-weight: 600;")
        self.lock_position = QCheckBox()
        self.lock_position.setChecked(settings.lock_position)
        self.lock_position_checkbox = self.lock_position
        self.close_to_tray = QCheckBox()
        self.close_to_tray.setChecked(settings.close_to_tray)
        self.close_to_tray_checkbox = self.close_to_tray
        self.launch_on_startup = QCheckBox()
        self.launch_on_startup.setChecked(settings.launch_on_startup)
        self.launch_on_startup_checkbox = self.launch_on_startup
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(30, 100)
        self.opacity.setValue(round(settings.opacity * 100))
        self.opacity_slider = self.opacity
        self.lead_minutes = QSpinBox()
        self.lead_minutes.setRange(1, 240)
        self.lead_minutes.setValue(settings.notification_lead_minutes)
        self.lead_minutes.setSuffix(" 分钟")
        self.lead_minutes.setToolTip("右侧 ↑ 增加、↓ 减少；每次调整 1 分钟")
        self.lead_minutes_spin = self.lead_minutes
        self.lead_minutes_spinbox = self.lead_minutes
        self.background_enabled = QCheckBox()
        self.background_enabled.setChecked(settings.background_enabled)
        self.background_resource = QComboBox()
        self.background_resource_combo = self.background_resource
        self._populate_resource_combo(self.background_resource, "选择内置背景")
        self.background_resource.setToolTip("右侧 ▼ 展开内置背景列表")
        self.background_path = QLineEdit(settings.background_image_path)
        self.background_path.setPlaceholderText("选择背景图片")
        browse_button = QPushButton("选择")
        browse_button.clicked.connect(self.choose_background)
        self.icon_path = QLineEdit(settings.icon_path)
        self.icon_path.setPlaceholderText("选择程序图标")
        self.icon_path_edit = self.icon_path
        self.icon_resource = QComboBox()
        self.icon_resource_combo = self.icon_resource
        self._populate_resource_combo(self.icon_resource, "选择内置图标")
        self.icon_resource.setToolTip("右侧 ▼ 展开内置图标列表")
        icon_browse_button = QPushButton("选择")
        icon_browse_button.clicked.connect(self.choose_icon)

        for checkbox in (
            self.always_on_top,
            self.mouse_passthrough,
            self.lock_position,
            self.close_to_tray,
            self.launch_on_startup,
            self.background_enabled,
        ):
            self._configure_toggle(checkbox)

        form = QFormLayout()
        form.addRow("窗口始终置顶", self.always_on_top)
        form.addRow("鼠标穿透", self.mouse_passthrough)
        form.addRow("", self.passthrough_hint)
        form.addRow("锁定位置", self.lock_position)
        form.addRow("关闭时进入托盘", self.close_to_tray)
        form.addRow("Windows 开机启动", self.launch_on_startup)
        form.addRow("透明度", self.opacity)
        self.lead_minutes_step_hint = _step_hint_label("右侧 ↑ 增加 / ↓ 减少")
        form.addRow("提前提醒分钟", _with_hint(self.lead_minutes, self.lead_minutes_step_hint))
        form.addRow("启用背景图片", self.background_enabled)
        form.addRow("内置背景", self.background_resource)

        background_layout = QHBoxLayout()
        background_layout.addWidget(self.background_path, 1)
        background_layout.addWidget(browse_button)
        form.addRow("背景图片", background_layout)

        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.icon_path, 1)
        icon_layout.addWidget(icon_browse_button)
        form.addRow("内置图标", self.icon_resource)
        form.addRow("程序图标", icon_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._preview_ready = True
        self._sync_resource_combo(self.background_resource, self.background_path.text())
        self._sync_resource_combo(self.icon_resource, self.icon_path.text())
        self._sync_passthrough_availability()
        self._connect_preview_signals()

    def _populate_resource_combo(self, combo: QComboBox, placeholder: str) -> None:
        combo.addItem(placeholder, "")
        for resource in BUILTIN_RESOURCES:
            combo.addItem(resource.label, resource.value)

    def _configure_toggle(self, checkbox: QCheckBox) -> None:
        checkbox.setObjectName("settingsToggle")
        checkbox.setCursor(Qt.PointingHandCursor)
        checkbox.toggled.connect(lambda checked, control=checkbox: self._update_toggle_text(control, checked))
        self._update_toggle_text(checkbox, checkbox.isChecked())

    def _update_toggle_text(self, checkbox: QCheckBox, checked: bool) -> None:
        checkbox.setText("开启" if checked else "关闭")

    def choose_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            self.background_path.text(),
            "Images and GIFs (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;All Files (*)",
        )
        if path:
            self.background_path.setText(path)
            self.background_enabled.setChecked(True)

    def choose_icon(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择程序图标",
            self.icon_path.text(),
            ICON_FILE_FILTER,
        )
        if path:
            self.icon_path.setText(path)

    def _connect_preview_signals(self) -> None:
        self.always_on_top.toggled.connect(self._sync_passthrough_availability)
        self.background_resource.currentIndexChanged.connect(self.apply_background_resource)
        self.icon_resource.currentIndexChanged.connect(self.apply_icon_resource)
        self.opacity.valueChanged.connect(self._emit_preview)
        self.background_enabled.toggled.connect(self._emit_preview)
        self.background_path.textChanged.connect(self._emit_preview)
        self.background_path.textChanged.connect(lambda text: self._sync_resource_combo(self.background_resource, text))
        self.icon_path.textChanged.connect(self._emit_preview)
        self.icon_path.textChanged.connect(lambda text: self._sync_resource_combo(self.icon_resource, text))

    def apply_background_resource(self, *args) -> None:
        value = self.background_resource.currentData()
        if not value:
            return
        self.background_path.setText(str(value))
        self.background_enabled.setChecked(True)

    def apply_icon_resource(self, *args) -> None:
        value = self.icon_resource.currentData()
        if value:
            self.icon_path.setText(str(value))

    def _sync_resource_combo(self, combo: QComboBox, value: str) -> None:
        if value and value.startswith(BUILTIN_RESOURCE_PREFIX):
            index = combo.findData(value)
        else:
            index = 0
        combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index if index >= 0 else 0)
        finally:
            combo.blockSignals(False)

    def _sync_passthrough_availability(self, *args) -> None:
        enabled = self.always_on_top.isChecked()
        self.mouse_passthrough.setEnabled(enabled)
        self.passthrough_hint.setEnabled(enabled)
        if not enabled:
            self.mouse_passthrough.setChecked(False)

    def _emit_preview(self, *args) -> None:
        if not self._preview_ready:
            return
        preview_settings = getattr(self.parent(), "preview_settings", None)
        if callable(preview_settings):
            preview_settings(self.build_settings())

    def build_settings(self) -> AppSettings:
        return replace(
            self.settings,
            always_on_top=self.always_on_top.isChecked(),
            mouse_passthrough=self.mouse_passthrough.isChecked() and self.always_on_top.isChecked(),
            lock_position=self.lock_position.isChecked(),
            close_to_tray=self.close_to_tray.isChecked(),
            launch_on_startup=self.launch_on_startup.isChecked(),
            low_distraction_mode=DEFAULT_LOW_DISTRACTION_MODE,
            opacity=self.opacity.value() / 100,
            notification_lead_minutes=self.lead_minutes.value(),
            notification_repeat_minutes=DEFAULT_NOTIFICATION_REPEAT_MINUTES,
            background_enabled=self.background_enabled.isChecked(),
            background_image_path=self.background_path.text().strip(),
            background_overlay=DEFAULT_BACKGROUND_OVERLAY,
            icon_path=self.icon_path.text().strip(),
        )


def _with_hint(control, hint: QLabel) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(control, 1)
    layout.addWidget(hint)
    return layout


def _step_hint_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("settingsStepHintLabel")
    label.setAlignment(Qt.AlignCenter)
    label.setToolTip("说明右侧灰色箭头控制区的含义")
    label.setStyleSheet(
        "color: #BAE6FD;"
        "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #102033, stop:1 #103A3D);"
        "border: none;"
        "border-radius: 8px;"
        "font-size: 12px;"
        "font-weight: 900;"
        "padding: 6px 8px;"
    )
    return label
