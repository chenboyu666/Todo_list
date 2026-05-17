from __future__ import annotations

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QCalendarWidget, QDateEdit


def apply_dark_calendar_popup(date_edit: QDateEdit, object_name: str) -> QCalendarWidget:
    calendar = QCalendarWidget(date_edit)
    calendar.setObjectName(object_name)
    calendar.setLocale(QLocale(QLocale.Chinese, QLocale.China))
    calendar.setGridVisible(False)
    calendar.setFirstDayOfWeek(Qt.Monday)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
    calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    calendar.setNavigationBarVisible(True)
    calendar.setStyleSheet(_dark_calendar_style())

    weekday_format = QTextCharFormat()
    weekday_format.setForeground(QColor("#F8FBFF"))
    for day in (
        Qt.Monday,
        Qt.Tuesday,
        Qt.Wednesday,
        Qt.Thursday,
        Qt.Friday,
        Qt.Saturday,
        Qt.Sunday,
    ):
        calendar.setWeekdayTextFormat(day, weekday_format)

    header_format = QTextCharFormat()
    header_format.setForeground(QColor("#9EB5C8"))
    calendar.setHeaderTextFormat(header_format)

    date_edit.setCalendarWidget(calendar)
    return calendar


def _dark_calendar_style() -> str:
    return """
QCalendarWidget {
  background: #070B12;
  color: #F8FBFF;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #0C1724,
    stop:1 #12362D);
  border: none;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}
QCalendarWidget QToolButton {
  color: #ECFEFF;
  background: #102033;
  border: none;
  border-radius: 7px;
  min-height: 28px;
  margin: 4px;
  padding: 3px 8px;
  font-weight: 900;
}
QCalendarWidget QToolButton:hover {
  background: #155E75;
}
QCalendarWidget QToolButton:pressed {
  background: #0E7490;
}
QCalendarWidget QToolButton::menu-indicator {
  image: none;
  width: 0;
}
QCalendarWidget QSpinBox {
  color: #ECFEFF;
  background: #101827;
  border: none;
  border-radius: 7px;
  min-height: 28px;
  padding: 2px 8px;
  font-weight: 900;
}
QCalendarWidget QMenu {
  color: #F8FBFF;
  background: #0A111B;
  border: none;
  padding: 5px;
}
QCalendarWidget QMenu::item {
  padding: 5px 12px;
  border-radius: 6px;
}
QCalendarWidget QMenu::item:selected {
  background: #155E75;
}
QCalendarWidget QAbstractItemView {
  color: #F8FBFF;
  background: #070B12;
  alternate-background-color: #0C121D;
  border: none;
  outline: 0;
  selection-background-color: #0E7490;
  selection-color: #ECFEFF;
}
QCalendarWidget QAbstractItemView:disabled {
  color: #4B5563;
}
"""
