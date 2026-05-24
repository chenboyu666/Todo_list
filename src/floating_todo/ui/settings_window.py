from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from floating_todo.app_identity import ICON_FILE_FILTER
from floating_todo.app_resources import (
    BUILTIN_RESOURCES,
    BUILTIN_RESOURCE_PREFIX,
    data_resources_dir,
    default_data_dir,
)
from floating_todo.settings import (
    AppSettings,
    DEFAULT_BACKGROUND_OVERLAY,
    DEFAULT_GEOMETRY,
    DEFAULT_LOW_DISTRACTION_MODE,
    DEFAULT_NOTIFICATION_REPEAT_MINUTES,
)
from floating_todo.theme import THEME_COLORS

UI_ICON_DIR = Path(__file__).resolve().parents[1] / "assets" / "ui"


class SettingsTitleBar(QFrame):
    def __init__(self, window: QDialog) -> None:
        super().__init__(window)
        self.window = window
        self._drag_start: QPoint | None = None
        self.setObjectName("settingsTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        icon = QLabel("")
        icon.setObjectName("settingsTitleIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(28, 28)
        icon.setPixmap(QIcon(str(UI_ICON_DIR / "nav-settings.svg")).pixmap(18, 18))
        layout.addWidget(icon)

        title = QLabel("设置")
        title.setObjectName("settingsWindowTitle")
        layout.addWidget(title)
        layout.addStretch(1)

        close_button = QPushButton("")
        close_button.setObjectName("settingsCloseButton")
        close_button.setToolTip("关闭设置")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setIcon(QIcon(str(UI_ICON_DIR / "window-close.svg")))
        close_button.setIconSize(icon.pixmap().size() if icon.pixmap() is not None else icon.size())
        close_button.setProperty("effectVariant", "icon")
        close_button.clicked.connect(window.reject)
        layout.addWidget(close_button)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None and event.buttons() & Qt.LeftButton:
            self.window.move(event.globalPosition().toPoint() - self._drag_start)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


class SettingsWindow(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.settings = settings
        self._preview_ready = False
        self._reset_window_geometry_requested = False
        self.sidebar_buttons: list[QPushButton] = []
        self.setMinimumSize(980, 820)
        self.resize(1100, 900)
        self.setStyleSheet(_settings_window_style())

        self.data_dir = self._resolve_data_dir()
        self.resources_dir = data_resources_dir(self.data_dir)
        self.settings_file = self.data_dir / "settings.json"

        self.always_on_top = QCheckBox()
        self.always_on_top.setChecked(settings.always_on_top)
        self.always_on_top_checkbox = self.always_on_top

        self.mouse_passthrough = QCheckBox()
        self.mouse_passthrough.setChecked(settings.mouse_passthrough and settings.always_on_top)
        self.mouse_passthrough.setToolTip("穿透后无法直接点击浮窗；右键托盘图标，选择“退出鼠标穿透”即可恢复。")
        self.mouse_passthrough_checkbox = self.mouse_passthrough

        self.passthrough_hint = QLabel("穿透后无法直接点击浮窗；右键托盘图标，选择“退出鼠标穿透”即可恢复普通模式。")
        self.passthrough_hint.setObjectName("settingsRowHint")
        self.passthrough_hint.setWordWrap(True)

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
        self.opacity_value_label = QLabel(f"{self.opacity.value()}%")
        self.opacity_value_label.setObjectName("settingsValueLabel")
        self.opacity.valueChanged.connect(lambda value: self.opacity_value_label.setText(f"{value}%"))

        self.ui_scale = QSlider(Qt.Horizontal)
        self.ui_scale.setRange(85, 130)
        self.ui_scale.setValue(round(settings.ui_scale * 100))
        self.ui_scale_slider = self.ui_scale
        self.ui_scale_value_label = QLabel(f"{self.ui_scale.value()}%")
        self.ui_scale_value_label.setObjectName("settingsValueLabel")
        self.ui_scale.valueChanged.connect(lambda value: self.ui_scale_value_label.setText(f"{value}%"))

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
        self.background_resource.setToolTip("▼ 展开后可直接切换内置背景")

        self.background_path = QLineEdit(settings.background_image_path)
        self.background_path.hide()

        self.background_browse_button = QPushButton("自定义")
        self.background_browse_button.setToolTip("选择本地背景图片或动图")
        self.background_browse_button.clicked.connect(self.choose_background)

        self.background_random_enabled = QCheckBox()
        self.background_random_enabled.setChecked(settings.background_random_enabled)
        self.background_random_enabled_checkbox = self.background_random_enabled

        self.background_folder_path = QLineEdit(settings.background_folder_path)
        self.background_folder_path.setObjectName("settingsPathPreview")
        self.background_folder_path.setPlaceholderText("未选择文件夹")
        self.background_folder_path_edit = self.background_folder_path
        self.background_folder_display = self.background_folder_path

        self.background_folder_browse_button = QPushButton("选择")
        self.background_folder_browse_button.setToolTip("选择一个文件夹，用于随机轮换背景")
        self.background_folder_browse_button.clicked.connect(self.choose_background_folder)

        self.icon_path = QLineEdit(settings.icon_path)
        self.icon_path.hide()
        self.icon_path_edit = self.icon_path

        self.icon_resource = QComboBox()
        self.icon_resource_combo = self.icon_resource
        self._populate_resource_combo(self.icon_resource, "选择内置图标")
        self.icon_resource.setToolTip("▼ 展开后可直接切换内置图标")

        self.icon_browse_button = QPushButton("自定义")
        self.icon_browse_button.setToolTip("选择本地图标文件")
        self.icon_browse_button.clicked.connect(self.choose_icon)

        self.data_dir_display = _readonly_path(str(self.data_dir))
        self.resources_dir_display = _readonly_path(str(self.resources_dir))
        self.settings_file_display = _readonly_path(str(self.settings_file))

        self.reset_geometry_status = QLabel("当前保留窗口位置与大小")
        self.reset_geometry_status.setObjectName("settingsRowHint")

        self.reset_geometry_button = QPushButton("恢复默认窗口大小")
        self.reset_geometry_button.clicked.connect(self.request_reset_window_geometry)

        for checkbox in (
            self.always_on_top,
            self.mouse_passthrough,
            self.lock_position,
            self.close_to_tray,
            self.launch_on_startup,
            self.background_enabled,
            self.background_random_enabled,
        ):
            self._configure_toggle(checkbox)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("settingsPageStack")
        self.page_stack.addWidget(self._build_window_page())
        self.page_stack.addWidget(self._build_reminder_page())
        self.page_stack.addWidget(self._build_appearance_page())
        self.page_stack.addWidget(self._build_data_page())

        shell = QHBoxLayout()
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(16)
        shell.addWidget(self._settings_sidebar())

        content_panel = QFrame()
        content_panel.setObjectName("settingsContentPanel")
        content_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(12)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("settingsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(self.page_stack)
        content_layout.addWidget(self.scroll_area, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.save_button = self.button_box.button(QDialogButtonBox.Save)
        self.cancel_button = self.button_box.button(QDialogButtonBox.Cancel)
        if self.save_button is not None:
            self.save_button.setText("保存")
            self.save_button.setObjectName("settingsSaveButton")
        if self.cancel_button is not None:
            self.cancel_button.setText("取消")
            self.cancel_button.setObjectName("settingsCancelButton")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        content_layout.addWidget(self.button_box, 0, Qt.AlignRight)
        shell.addWidget(content_panel, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 16, 22, 18)
        layout.setSpacing(16)
        self.title_bar = SettingsTitleBar(self)
        layout.addWidget(self.title_bar)
        layout.addLayout(shell, 1)

        self._preview_ready = True
        self._sync_resource_combo(self.background_resource, self.background_path.text())
        self._sync_resource_combo(self.icon_resource, self.icon_path.text())
        self._sync_passthrough_availability()
        self._sync_folder_display()
        self._select_page(0)
        self._connect_preview_signals()

    def _resolve_data_dir(self) -> Path:
        parent = self.parent()
        settings_path = getattr(parent, "settings_path", None)
        if settings_path is not None:
            return Path(settings_path).resolve().parent
        return default_data_dir().resolve()

    def _build_window_page(self) -> QWidget:
        page = _settings_page()
        page.layout().addWidget(
            _settings_section(
                "窗口行为",
                _settings_row("窗口始终置顶", self.always_on_top),
                _settings_row("鼠标穿透", self.mouse_passthrough, self.passthrough_hint),
                _settings_row("锁定位置", self.lock_position),
                _settings_row("关闭时进入托盘", self.close_to_tray),
                _settings_row("Windows 开机启动", self.launch_on_startup),
            )
        )
        page.layout().addWidget(
            _settings_section(
                "显示设置",
                _settings_row("透明度", _inline_controls(self.opacity, self.opacity_value_label)),
                _settings_row("界面缩放", _inline_controls(self.ui_scale, self.ui_scale_value_label)),
            )
        )
        page.layout().addStretch(1)
        return page

    def _build_reminder_page(self) -> QWidget:
        repeat_label = QLabel(f"{DEFAULT_NOTIFICATION_REPEAT_MINUTES} 分钟")
        repeat_label.setObjectName("settingsReadonlyValue")
        reminder_note = QLabel("临近截止后会按固定间隔重复提醒；超时后会弹出提醒小窗。")
        reminder_note.setObjectName("settingsRowHint")
        reminder_note.setWordWrap(True)

        page = _settings_page()
        page.layout().addWidget(
            _settings_section(
                "提醒规则",
                _settings_row("提前提醒分钟", self.lead_minutes),
                _settings_row("重复提醒间隔", repeat_label, reminder_note),
            )
        )
        page.layout().addWidget(
            _settings_section(
                "提醒小窗",
                _info_row("提醒小窗会沿用外观页的背景图和透明度，让提醒和主窗口保持一致。"),
            )
        )
        page.layout().addStretch(1)
        return page

    def _build_appearance_page(self) -> QWidget:
        background_layout = _inline_controls(self.background_resource, self.background_browse_button)
        folder_layout = _inline_controls(self.background_folder_display, self.background_folder_browse_button)
        icon_layout = _inline_controls(self.icon_resource, self.icon_browse_button)

        page = _settings_page()
        page.layout().addWidget(
            _settings_section(
                "背景设置",
                _settings_row("启用背景图片", self.background_enabled),
                _settings_row("背景", background_layout),
                _settings_row("随机背景文件夹", self.background_random_enabled),
                _settings_row("背景文件夹", folder_layout),
            )
        )
        page.layout().addWidget(
            _settings_section(
                "图标设置",
                _settings_row("图标", icon_layout),
            )
        )
        page.layout().addStretch(1)
        return page

    def _build_data_page(self) -> QWidget:
        page = _settings_page()
        page.layout().addWidget(
            _settings_section(
                "本地数据",
                _settings_row(
                    "数据目录",
                    _inline_controls(
                        self.data_dir_display,
                        _action_button("打开", self.open_data_directory),
                        _action_button("复制", lambda: self.copy_path(self.data_dir)),
                    ),
                ),
                _settings_row(
                    "资源目录",
                    _inline_controls(
                        self.resources_dir_display,
                        _action_button("打开", self.open_resources_directory),
                        _action_button("复制", lambda: self.copy_path(self.resources_dir)),
                    ),
                ),
                _settings_row(
                    "设置文件",
                    _inline_controls(
                        self.settings_file_display,
                        _action_button("打开", self.open_settings_file_directory),
                        _action_button("复制", lambda: self.copy_path(self.settings_file)),
                    ),
                ),
            )
        )
        page.layout().addWidget(
            _settings_section(
                "维护",
                _settings_row("恢复窗口布局", self.reset_geometry_button, self.reset_geometry_status),
                _info_row("任务、历史记录、设置和自定义资源都保存在 data 目录中；移动程序时请一起保留该目录。"),
            )
        )
        page.layout().addStretch(1)
        return page

    def _settings_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("settingsSidebar")
        sidebar.setFixedWidth(176)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(12)

        definitions = [
            ("窗口", "pane-window.svg"),
            ("提醒", "pane-bell.svg"),
            ("外观", "pane-palette.svg"),
            ("数据", "pane-data.svg"),
        ]
        for index, (text, icon_name) in enumerate(definitions):
            button = QPushButton(text)
            button.setObjectName("settingsSidebarItem")
            button.setProperty("effectVariant", "nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(54)
            button.setIcon(QIcon(str(UI_ICON_DIR / icon_name)))
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, page=index: self._select_page(page))
            self.sidebar_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        return sidebar

    def _select_page(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.sidebar_buttons):
            button.setChecked(button_index == index)

    def _populate_resource_combo(self, combo: QComboBox, placeholder: str) -> None:
        combo.addItem(placeholder, "")
        for resource in BUILTIN_RESOURCES:
            combo.addItem(resource.label, resource.value)

    def _configure_toggle(self, checkbox: QCheckBox) -> None:
        checkbox.setObjectName("settingsToggle")
        checkbox.setCursor(Qt.PointingHandCursor)
        checkbox.setFixedWidth(54)
        checkbox.toggled.connect(lambda checked, control=checkbox: self._update_toggle_text(control, checked))
        self._update_toggle_text(checkbox, checkbox.isChecked())

    def _update_toggle_text(self, checkbox: QCheckBox, checked: bool) -> None:
        checkbox.setText("开启" if checked else "关闭")
        checkbox.setToolTip("开启" if checked else "关闭")

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
            self.background_random_enabled.setChecked(False)

    def choose_background_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "选择背景图片文件夹",
            self.background_folder_path.text(),
        )
        if path:
            self.background_folder_path.setText(path)
            self.background_random_enabled.setChecked(True)
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

    def request_reset_window_geometry(self) -> None:
        self._reset_window_geometry_requested = True
        self.reset_geometry_status.setText("保存后将恢复默认窗口位置与大小")
        self.reset_geometry_button.setText("已准备恢复")
        self.reset_geometry_button.setEnabled(False)

    def open_data_directory(self) -> None:
        self._open_path(self.data_dir)

    def open_resources_directory(self) -> None:
        self.resources_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(self.resources_dir)

    def open_settings_file_directory(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(self.data_dir)

    def copy_path(self, path: Path) -> None:
        QApplication.clipboard().setText(str(path))

    def _open_path(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _connect_preview_signals(self) -> None:
        self.always_on_top.toggled.connect(self._sync_passthrough_availability)
        self.background_random_enabled.toggled.connect(self._sync_random_background_enabled)
        self.background_resource.currentIndexChanged.connect(self.apply_background_resource)
        self.icon_resource.currentIndexChanged.connect(self.apply_icon_resource)
        self.opacity.valueChanged.connect(self._emit_preview)
        self.background_enabled.toggled.connect(self._emit_preview)
        self.background_random_enabled.toggled.connect(self._emit_preview)
        self.background_path.textChanged.connect(self._emit_preview)
        self.background_path.textChanged.connect(lambda text: self._sync_resource_combo(self.background_resource, text))
        self.background_folder_path.textChanged.connect(self._sync_folder_display)
        self.background_folder_path.textChanged.connect(self._emit_preview)
        self.icon_path.textChanged.connect(self._emit_preview)
        self.icon_path.textChanged.connect(lambda text: self._sync_resource_combo(self.icon_resource, text))

    def apply_background_resource(self, *args) -> None:
        value = self.background_resource.currentData()
        if not value:
            return
        self.background_path.setText(str(value))
        self.background_enabled.setChecked(True)
        self.background_random_enabled.setChecked(False)

    def apply_icon_resource(self, *args) -> None:
        value = self.icon_resource.currentData()
        if value:
            self.icon_path.setText(str(value))

    def _sync_random_background_enabled(self, checked: bool) -> None:
        if checked:
            self.background_enabled.setChecked(True)

    def _sync_folder_display(self, *args) -> None:
        text = self.background_folder_path.text().strip()
        if self.background_folder_display.text() != text:
            self.background_folder_display.setText(text)

    def _sync_resource_combo(self, combo: QComboBox, value: str) -> None:
        if value and value.startswith(BUILTIN_RESOURCE_PREFIX):
            index = combo.findData(value)
        else:
            index = 0
        placeholder = "选择内置背景" if combo is self.background_resource else "选择内置图标"
        custom_label = "自定义背景" if combo is self.background_resource else "自定义图标"
        combo.setItemText(0, custom_label if value and not value.startswith(BUILTIN_RESOURCE_PREFIX) else placeholder)
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
        geometry = DEFAULT_GEOMETRY if self._reset_window_geometry_requested else dict(self.settings.window_geometry)
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
            window_geometry=geometry,
            background_enabled=self.background_enabled.isChecked(),
            background_random_enabled=self.background_random_enabled.isChecked(),
            background_image_path=self.background_path.text().strip(),
            background_folder_path=self.background_folder_path.text().strip(),
            background_overlay=DEFAULT_BACKGROUND_OVERLAY,
            icon_path=self.icon_path.text().strip(),
            ui_scale=self.ui_scale.value() / 100,
        )


def _readonly_path(text: str) -> QLineEdit:
    control = QLineEdit(text)
    control.setObjectName("settingsPathPreview")
    control.setReadOnly(True)
    return control


def _action_button(text: str, callback) -> QPushButton:
    button = QPushButton(text)
    button.clicked.connect(callback)
    return button


def _settings_page() -> QWidget:
    page = QWidget()
    page.setObjectName("settingsPage")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(6, 4, 6, 4)
    layout.setSpacing(18)
    return page


def _settings_section(title: str, *rows: QWidget) -> QFrame:
    section = QFrame()
    section.setObjectName("settingsSection")
    section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    outer = QVBoxLayout(section)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(12)

    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(10)
    accent = QFrame()
    accent.setObjectName("settingsSectionAccent")
    accent.setFixedSize(5, 24)
    header.addWidget(accent)
    label = QLabel(title)
    label.setObjectName("settingsSectionTitle")
    header.addWidget(label)
    header.addStretch(1)
    outer.addLayout(header)

    group = QFrame()
    group.setObjectName("settingsGroup")
    group_layout = QVBoxLayout(group)
    group_layout.setContentsMargins(0, 0, 0, 0)
    group_layout.setSpacing(0)
    for row in rows:
        group_layout.addWidget(row)
    outer.addWidget(group)
    return section


def _settings_row(title: str, control: QWidget, hint: QLabel | None = None) -> QFrame:
    row = QFrame()
    row.setObjectName("settingsRow")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(20, 12, 20, 12)
    row_layout.setSpacing(18)

    text_stack = QVBoxLayout()
    text_stack.setContentsMargins(0, 0, 0, 0)
    text_stack.setSpacing(4)
    if title:
        label = QLabel(title)
        label.setObjectName("settingsRowTitle")
        text_stack.addWidget(label)
    if hint is not None:
        text_stack.addWidget(hint)
    row_layout.addLayout(text_stack, 1)
    row_layout.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)
    return row


def _info_row(text: str) -> QFrame:
    label = QLabel(text)
    label.setObjectName("settingsInfoText")
    label.setWordWrap(True)
    return _settings_row("", label)


def _inline_controls(*widgets: QWidget) -> QWidget:
    container = QWidget()
    container.setObjectName("settingsInlineControls")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    for index, widget in enumerate(widgets):
        layout.addWidget(widget, 1 if index == 0 else 0)
    return container


def _settings_window_style() -> str:
    return f"""
QDialog {{
  background: {THEME_COLORS["background"]};
}}
QFrame#settingsTitleBar {{
  background: transparent;
}}
QLabel#settingsTitleIcon {{
  color: #B8C8D8;
  font-size: 24px;
  font-weight: 900;
}}
QLabel#settingsWindowTitle {{
  color: #F8FBFF;
  font-size: 24px;
  font-weight: 900;
}}
QPushButton#settingsCloseButton {{
  color: #D4E0EA;
  background: rgba(13, 25, 40, 0.72);
  border: 1px solid rgba(120, 168, 197, 0.24);
  border-radius: 10px;
  min-width: 36px;
  min-height: 36px;
  max-width: 36px;
  max-height: 36px;
  padding: 0;
  font-size: 19px;
  font-weight: 500;
}}
QPushButton#settingsCloseButton:hover {{
  background: rgba(34, 211, 238, 0.14);
}}
QFrame#settingsSidebar {{
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #061321,
    stop:1 #082238);
  border: 1px solid rgba(91, 141, 164, 48);
  border-radius: 16px;
}}
QPushButton#settingsSidebarItem {{
  color: #AFC3D8;
  background: transparent;
  border: none;
  border-radius: 12px;
  text-align: left;
  padding-left: 20px;
  font-size: 16px;
  font-weight: 900;
}}
QPushButton#settingsSidebarItem:hover {{
  color: #EAFBFF;
  background: rgba(17, 56, 88, 142);
}}
QPushButton#settingsSidebarItem:checked {{
  color: #EAFBFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:0.06 #22D3EE,
    stop:0.07 #0B63A5,
    stop:1 #102E55);
}}
QFrame#settingsContentPanel {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #061321,
    stop:0.5 #08243A,
    stop:1 #06313B);
  border: 1px solid rgba(91, 141, 164, 54);
  border-radius: 16px;
}}
QScrollArea#settingsScrollArea {{
  background: transparent;
  border: none;
}}
QFrame#settingsSection {{
  background: transparent;
  border: none;
}}
QFrame#settingsSectionAccent {{
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #22D3EE,
    stop:1 #0F766E);
  border: none;
  border-radius: 2px;
}}
QLabel#settingsSectionTitle {{
  color: #EAF7FF;
  font-size: 18px;
  font-weight: 900;
}}
QFrame#settingsGroup {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 rgba(10, 28, 46, 220),
    stop:1 rgba(12, 42, 62, 212));
  border: 1px solid rgba(91, 141, 164, 42);
  border-radius: 14px;
}}
QFrame#settingsRow {{
  background: transparent;
  border-bottom: 1px solid rgba(116, 151, 176, 28);
}}
QLabel#settingsRowTitle {{
  color: #D8E8F5;
  font-size: 16px;
  font-weight: 900;
}}
QLabel#settingsRowHint {{
  color: #8EA2B7;
  font-size: 12px;
  font-weight: 700;
}}
QLabel#settingsInfoText {{
  color: #AFC3D8;
  font-size: 14px;
  font-weight: 700;
}}
QLabel#settingsReadonlyValue,
QLabel#settingsValueLabel {{
  color: #D8E8F5;
  font-size: 16px;
  font-weight: 900;
  min-width: 58px;
}}
QCheckBox#settingsToggle {{
  color: transparent;
  spacing: 0;
}}
QCheckBox#settingsToggle::indicator {{
  width: 50px;
  height: 26px;
  border-radius: 13px;
  background: #102338;
  border: 1px solid rgba(148, 163, 184, 60);
}}
QCheckBox#settingsToggle::indicator:checked {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:1 #14B8A6);
  border: 1px solid rgba(94, 234, 212, 150);
}}
QCheckBox#settingsToggle::indicator:disabled {{
  background: #172033;
  border: 1px solid rgba(148, 163, 184, 36);
}}
QSlider::groove:horizontal {{
  height: 8px;
  border-radius: 4px;
  background: #183044;
}}
QSlider::sub-page:horizontal {{
  border-radius: 4px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #8CF4D3,
    stop:0.45 #22D3EE,
    stop:1 #3B82F6);
}}
QSlider::handle:horizontal {{
  width: 20px;
  height: 20px;
  margin: -6px 0;
  border-radius: 10px;
  background: #D9E8F7;
  border: 2px solid #6EA8F7;
}}
QComboBox,
QSpinBox,
QLineEdit#settingsPathPreview {{
  color: #D8E8F5;
  background: #061321;
  border: 1px solid rgba(91, 141, 164, 48);
  border-radius: 10px;
  min-height: 38px;
  padding: 0 12px;
  font-size: 15px;
  font-weight: 800;
}}
QComboBox::drop-down {{
  width: 34px;
  border: none;
}}
QPushButton {{
  color: #D8E8F5;
  background: #10263A;
  border: 1px solid rgba(91, 141, 164, 54);
  border-radius: 10px;
  min-height: 38px;
  padding: 0 18px;
  font-size: 15px;
  font-weight: 900;
}}
QPushButton:hover {{
  background: #123B55;
}}
QPushButton#settingsSaveButton {{
  color: #ECFEFF;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:1 #14B8A6);
  border: 1px solid rgba(94, 234, 212, 130);
  min-width: 120px;
}}
QPushButton#settingsCancelButton {{
  min-width: 120px;
}}
"""
