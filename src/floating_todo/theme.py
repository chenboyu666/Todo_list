THEME_COLORS = {
    "background": "#0E1223",
    "surface": "#111827",
    "surface_hover": "#172033",
    "surface_pressed": "#1A1E2F",
    "field": "#020617",
    "border": "#334155",
    "text": "#F8FAFC",
    "accent": "#22D3EE",
}

THEME_RADIUS = {
    "control": "8px",
    "progress": "4px",
}

THEME_SPACING = {
    "button_min_height": "32px",
    "control_min_height": "32px",
    "control_padding": "4px 10px",
    "field_padding": "4px 8px",
}

THEME_FONT = {
    "family": '"Segoe UI"',
    "size": "13px",
}

CALM_TECH_QSS = f"""
QWidget {{
  background: {THEME_COLORS["background"]};
  color: {THEME_COLORS["text"]};
  font-family: {THEME_FONT["family"]};
  font-size: {THEME_FONT["size"]};
}}
QPushButton {{
  background: {THEME_COLORS["surface"]};
  border: 1px solid {THEME_COLORS["border"]};
  border-radius: {THEME_RADIUS["control"]};
  min-height: {THEME_SPACING["button_min_height"]};
  padding: {THEME_SPACING["control_padding"]};
}}
QPushButton:hover {{
  border-color: {THEME_COLORS["accent"]};
  background: {THEME_COLORS["surface_hover"]};
}}
QPushButton:pressed {{
  background: {THEME_COLORS["surface_pressed"]};
}}
QLineEdit, QTextEdit, QSpinBox, QDateTimeEdit, QComboBox {{
  background: {THEME_COLORS["field"]};
  border: 1px solid {THEME_COLORS["border"]};
  border-radius: {THEME_RADIUS["control"]};
  min-height: {THEME_SPACING["control_min_height"]};
  padding: {THEME_SPACING["field_padding"]};
}}
QProgressBar {{
  background: {THEME_COLORS["border"]};
  border: 0;
  border-radius: {THEME_RADIUS["progress"]};
  height: 8px;
}}
QProgressBar::chunk {{
  background: {THEME_COLORS["accent"]};
  border-radius: {THEME_RADIUS["progress"]};
}}
"""
