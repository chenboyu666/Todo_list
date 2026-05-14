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
    "family": '"Microsoft YaHei UI", "Segoe UI"',
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
QScrollArea, QAbstractScrollArea {{
  background: transparent;
  border: none;
}}
QScrollBar:vertical {{
  background: transparent;
  width: 8px;
  margin: 0;
}}
QScrollBar::handle:vertical {{
  background: #273142;
  border-radius: 4px;
  min-height: 28px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
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
