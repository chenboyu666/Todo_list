THEME_COLORS = {
    "background": "#080A0F",
    "surface": "#121722",
    "surface_alt": "#171D2A",
    "surface_hover": "#1D2634",
    "surface_pressed": "#252D3B",
    "field": "#090D15",
    "border": "#8B95AC",
    "text": "#F6F8FC",
    "muted": "#9AA4B8",
    "accent": "#7DD3FC",
    "accent_secondary": "#A7F3D0",
    "warning": "#F6C177",
    "danger": "#FCA5A5",
}

THEME_RADIUS = {
    "control": "8px",
    "progress": "4px",
}

THEME_SPACING = {
    "button_min_height": "34px",
    "control_min_height": "34px",
    "control_padding": "5px 12px",
    "field_padding": "5px 10px",
}

THEME_FONT = {
    "family": '"Segoe UI Variable", "HarmonyOS Sans SC", "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", "Source Han Sans SC", "Segoe UI"',
    "size": "13px",
}

CALM_TECH_QSS = f"""
QWidget {{
  color: {THEME_COLORS["text"]};
  font-family: {THEME_FONT["family"]};
  font-size: {THEME_FONT["size"]};
}}
QMainWindow, QDialog {{
  background: {THEME_COLORS["background"]};
}}
QLabel {{
  background: transparent;
}}
QFrame {{
  border: none;
}}
QPushButton {{
  background: {THEME_COLORS["surface_alt"]};
  border: none;
  border-radius: {THEME_RADIUS["control"]};
  min-height: {THEME_SPACING["button_min_height"]};
  padding: {THEME_SPACING["control_padding"]};
}}
QPushButton:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 {THEME_COLORS["surface_hover"]},
    stop:1 #203242);
}}
QPushButton:pressed {{
  background: {THEME_COLORS["surface_pressed"]};
}}
QPushButton#currentTaskButton {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #155E75,
    stop:0.52 #0E7490,
    stop:1 #047857);
  color: #ECFEFF;
  font-weight: 800;
}}
QPushButton#currentTaskButton:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0E7490,
    stop:0.48 #0891B2,
    stop:1 #059669);
}}
QPushButton#taskExpandButton, QPushButton#taskCollapseButton {{
  min-height: 28px;
  padding: 3px 9px;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #162333,
    stop:1 #183943);
  color: #BAE6FD;
  font-weight: 700;
}}
QPushButton#taskExpandButton:hover, QPushButton#taskCollapseButton:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1D3147,
    stop:1 #1E4E4A);
}}
QPushButton#dangerButton {{
  background: #3A1822;
  color: #FFD5DF;
}}
QPushButton#dangerButton:hover {{
  background: #5A1F2B;
}}
QPushButton#dangerButton:pressed {{
  background: #742538;
}}
QSizeGrip {{
  background: transparent;
  width: 18px;
  height: 18px;
}}
QLineEdit, QTextEdit, QSpinBox, QDateTimeEdit, QDateEdit, QComboBox {{
  background: {THEME_COLORS["field"]};
  border: none;
  border-radius: {THEME_RADIUS["control"]};
  min-height: {THEME_SPACING["control_min_height"]};
  padding: {THEME_SPACING["field_padding"]};
  selection-background-color: {THEME_COLORS["accent"]};
  selection-color: {THEME_COLORS["background"]};
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDateTimeEdit:focus, QDateEdit:focus, QComboBox:focus {{
  background: #0D1420;
}}
QComboBox::drop-down, QDateTimeEdit::drop-down, QDateEdit::drop-down {{
  border: none;
  width: 28px;
  background: {THEME_COLORS["surface_alt"]};
  border-top-right-radius: {THEME_RADIUS["control"]};
  border-bottom-right-radius: {THEME_RADIUS["control"]};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
  border: none;
  background: {THEME_COLORS["surface_alt"]};
  width: 24px;
}}
QProgressBar {{
  background: #0A0E15;
  border: none;
  border-radius: {THEME_RADIUS["progress"]};
  height: 8px;
}}
QProgressBar::chunk {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 {THEME_COLORS["accent_secondary"]},
    stop:0.55 {THEME_COLORS["accent"]},
    stop:1 {THEME_COLORS["warning"]});
  border-radius: {THEME_RADIUS["progress"]};
}}
QSlider {{
  background: transparent;
  min-height: 24px;
}}
QSlider::groove:horizontal {{
  background: #0A0E15;
  border: none;
  height: 8px;
  border-radius: {THEME_RADIUS["progress"]};
}}
QSlider::sub-page:horizontal {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 {THEME_COLORS["accent_secondary"]},
    stop:0.55 {THEME_COLORS["accent"]},
    stop:1 {THEME_COLORS["warning"]});
  border-radius: {THEME_RADIUS["progress"]};
}}
QSlider::add-page:horizontal {{
  background: #0A0E15;
  border-radius: {THEME_RADIUS["progress"]};
}}
QSlider::handle:horizontal {{
  background: {THEME_COLORS["text"]};
  border: none;
  width: 16px;
  height: 16px;
  margin: -4px 0;
  border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
  background: {THEME_COLORS["accent"]};
}}
QSlider#focusProgress::groove:horizontal, QSlider#activeTaskProgress::groove:horizontal {{
  background: #07111B;
  height: 12px;
  border-radius: 6px;
}}
QSlider#focusProgress::sub-page:horizontal, QSlider#activeTaskProgress::sub-page:horizontal {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #A7F3D0,
    stop:0.45 #7DD3FC,
    stop:1 #F6C177);
  border-radius: 6px;
}}
QSlider#focusProgress::handle:horizontal, QSlider#activeTaskProgress::handle:horizontal {{
  background: #ECFEFF;
  width: 20px;
  height: 20px;
  margin: -4px 0;
  border-radius: 10px;
}}
QSlider#focusProgress::handle:horizontal:hover, QSlider#activeTaskProgress::handle:horizontal:hover {{
  background: #A7F3D0;
}}
QScrollArea, QAbstractScrollArea {{
  background: transparent;
  border: none;
}}
QScrollBar:vertical {{
  background: transparent;
  width: 7px;
  margin: 0;
}}
QScrollBar::handle:vertical {{
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #2B4256,
    stop:1 #1E5A62);
  border-radius: 4px;
  min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #365E77,
    stop:1 #238071);
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
  background: transparent;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
  height: 0;
  background: transparent;
}}
QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
  background: transparent;
  width: 0;
  height: 0;
}}
QCheckBox {{
  background: transparent;
  spacing: 8px;
}}
QMenu {{
  background: {THEME_COLORS["surface"]};
  color: {THEME_COLORS["text"]};
  border: none;
  border-radius: 8px;
  padding: 6px;
}}
QMenu::item {{
  background: transparent;
  color: {THEME_COLORS["text"]};
  min-height: 28px;
  padding: 6px 28px 6px 14px;
  border-radius: 6px;
}}
QMenu::item:selected {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #143044,
    stop:1 #1E3A36);
  color: {THEME_COLORS["text"]};
}}
QMenu::item:disabled {{
  color: {THEME_COLORS["muted"]};
}}
QMenu::separator {{
  height: 1px;
  background: #253044;
  margin: 6px 8px;
}}
"""
