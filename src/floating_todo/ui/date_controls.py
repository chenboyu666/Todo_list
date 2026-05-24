from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QDate, QEvent, QLocale, QObject, QPoint, Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QAbstractSpinBox, QCalendarWidget, QComboBox, QDateEdit, QMenu, QSpinBox, QToolButton


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:
        event.ignore()


class NoWheelDateEdit(QDateEdit):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setKeyboardTracking(False)
        self._popup_calendar: QCalendarWidget | None = None
        self._calendar_popup_connections_ready = False
        self.setCursor(Qt.PointingHandCursor)

    def wheelEvent(self, event) -> None:
        event.ignore()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if self.calendarPopup() and event.button() == Qt.LeftButton:
            self.open_calendar_popup()
            event.accept()

    def keyPressEvent(self, event) -> None:
        if self.calendarPopup() and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_F4):
            self.open_calendar_popup()
            event.accept()
            return
        if self.calendarPopup() and event.key() == Qt.Key_Down and event.modifiers() & Qt.AltModifier:
            self.open_calendar_popup()
            event.accept()
            return
        super().keyPressEvent(event)

    def attach_calendar_popup(self, calendar: QCalendarWidget) -> None:
        self._popup_calendar = calendar
        calendar.setWindowFlag(Qt.Popup, True)
        calendar.setWindowFlag(Qt.FramelessWindowHint, True)
        calendar.setFocusPolicy(Qt.StrongFocus)
        if self._calendar_popup_connections_ready:
            return

        def sync_from_calendar() -> None:
            selected_date = calendar.selectedDate()
            if selected_date.isValid() and selected_date != self.date():
                self.setDate(selected_date)

        def choose_date(selected_date: QDate) -> None:
            if selected_date.isValid():
                self.setDate(selected_date)
            calendar.hide()

        calendar.selectionChanged.connect(sync_from_calendar)
        calendar.clicked.connect(choose_date)
        calendar.activated.connect(choose_date)
        self.dateChanged.connect(lambda selected_date: calendar.setSelectedDate(selected_date))
        self._calendar_popup_connections_ready = True

    def open_calendar_popup(self) -> None:
        calendar = self._popup_calendar or self.calendarWidget()
        if calendar is None:
            return
        if not self._calendar_popup_connections_ready:
            self.attach_calendar_popup(calendar)

        calendar.setSelectedDate(self.date())
        calendar.setCurrentPage(self.date().year(), self.date().month())
        calendar.adjustSize()

        popup_size = calendar.sizeHint()
        target = self.mapToGlobal(QPoint(0, self.height() + 6))
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            if target.y() + popup_size.height() > available.bottom():
                target.setY(self.mapToGlobal(QPoint(0, 0)).y() - popup_size.height() - 6)
            target.setX(min(max(available.left(), target.x()), max(available.left(), available.right() - popup_size.width())))
        calendar.move(target)
        calendar.show()
        calendar.raise_()
        calendar.setFocus(Qt.PopupFocusReason)


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:
        event.ignore()


class _YearEditEventFilter(QObject):
    def __init__(self, finish: Callable[[], None], cancel: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self._finish = finish
        self._cancel = cancel

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.KeyPress, QEvent.ShortcutOverride):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._finish()
                event.accept()
                return True
            if event.key() == Qt.Key_Escape:
                self._cancel()
                event.accept()
                return True
        return super().eventFilter(watched, event)


def apply_dark_calendar_popup(date_edit: QDateEdit, object_name: str) -> QCalendarWidget:
    calendar = QCalendarWidget(date_edit)
    calendar.setObjectName(object_name)
    calendar.setMinimumSize(342, 306)
    calendar.setLocale(QLocale(QLocale.Chinese, QLocale.China))
    calendar.setGridVisible(False)
    calendar.setFirstDayOfWeek(Qt.Monday)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
    calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
    calendar.setNavigationBarVisible(True)
    calendar.setStyleSheet(_dark_calendar_style())

    weekday_format = QTextCharFormat()
    weekday_format.setForeground(QColor("#D8E7F5"))
    for day in (Qt.Monday, Qt.Tuesday, Qt.Wednesday, Qt.Thursday, Qt.Friday):
        calendar.setWeekdayTextFormat(day, weekday_format)

    weekend_format = QTextCharFormat()
    weekend_format.setForeground(QColor("#F6C177"))
    for day in (Qt.Saturday, Qt.Sunday):
        calendar.setWeekdayTextFormat(day, weekend_format)

    header_format = QTextCharFormat()
    header_format.setForeground(QColor("#9EB5C8"))
    header_format.setFontWeight(700)
    calendar.setHeaderTextFormat(header_format)

    today_format = QTextCharFormat()
    today_format.setForeground(QColor("#ECFEFF"))
    today_format.setBackground(QColor(14, 116, 144, 74))
    today_format.setFontWeight(900)
    calendar.setDateTextFormat(QDate.currentDate(), today_format)

    _enhance_calendar_navigation(calendar)
    date_edit.setCalendarWidget(calendar)
    if isinstance(date_edit, NoWheelDateEdit):
        date_edit.attach_calendar_popup(calendar)
    return calendar


def _enhance_calendar_navigation(calendar: QCalendarWidget) -> None:
    prev_button = calendar.findChild(QToolButton, "qt_calendar_prevmonth")
    next_button = calendar.findChild(QToolButton, "qt_calendar_nextmonth")
    month_button = calendar.findChild(QToolButton, "qt_calendar_monthbutton")
    year_button = calendar.findChild(QToolButton, "qt_calendar_yearbutton")
    year_edit = calendar.findChild(QSpinBox, "qt_calendar_yearedit")

    for button, arrow_type, tooltip in (
        (prev_button, Qt.LeftArrow, "Previous month"),
        (next_button, Qt.RightArrow, "Next month"),
    ):
        if button is not None:
            button.setArrowType(arrow_type)
            button.setText("")
            button.setToolTip(tooltip)
            button.setCursor(Qt.PointingHandCursor)

    if month_button is not None:
        month_menu = QMenu(month_button)
        for month in range(1, 13):
            action = month_menu.addAction(f"{month}月")
            action.triggered.connect(lambda checked=False, selected_month=month: calendar.setCurrentPage(calendar.yearShown(), selected_month))
        month_button.setMenu(month_menu)
        month_button.setPopupMode(QToolButton.InstantPopup)
        month_button.setCursor(Qt.PointingHandCursor)
        month_button.setToolTip("点击选择月份")

    if year_button is None or year_edit is None:
        return

    year_edit.setRange(1970, 2199)
    year_edit.setButtonSymbols(QSpinBox.NoButtons)
    year_edit.setKeyboardTracking(False)
    year_edit.setMinimumWidth(74)
    year_edit.setAlignment(Qt.AlignCenter)
    year_edit.hide()
    year_button.setCursor(Qt.PointingHandCursor)
    year_button.setToolTip("点击直接修改年份")

    def sync_year_editor(year: int, month: int) -> None:
        year_edit.blockSignals(True)
        year_edit.setValue(year)
        year_edit.blockSignals(False)

    editing_state = {"active": False, "year": calendar.yearShown(), "month": calendar.monthShown()}

    def selected_date_for_year(year: int, month: int) -> QDate:
        selected = calendar.selectedDate()
        day = min(max(1, selected.day()), QDate(year, month, 1).daysInMonth())
        return QDate(year, month, day)

    def end_year_edit(*, apply_value: bool) -> None:
        if not editing_state["active"] and year_edit.isHidden():
            return
        if apply_value:
            year_edit.interpretText()
            year = year_edit.value()
            month = calendar.monthShown()
            calendar.setSelectedDate(selected_date_for_year(year, month))
            calendar.setCurrentPage(year, month)
        else:
            year = int(editing_state["year"])
            month = int(editing_state["month"])
            year_edit.blockSignals(True)
            year_edit.setValue(year)
            year_edit.blockSignals(False)
            calendar.setCurrentPage(year, month)
        editing_state["active"] = False
        year_edit.hide()
        year_button.show()
        year_button.setFocus(Qt.OtherFocusReason)

    def finish_year_edit() -> None:
        end_year_edit(apply_value=True)

    def cancel_year_edit() -> None:
        end_year_edit(apply_value=False)

    def begin_year_edit() -> None:
        editing_state["active"] = True
        editing_state["year"] = calendar.yearShown()
        editing_state["month"] = calendar.monthShown()
        sync_year_editor(calendar.yearShown(), calendar.monthShown())
        year_button.hide()
        year_edit.show()
        year_edit.setFocus(Qt.OtherFocusReason)
        year_edit.selectAll()

    year_filter = _YearEditEventFilter(finish_year_edit, cancel_year_edit, calendar)
    year_edit.installEventFilter(year_filter)
    line_edit = year_edit.lineEdit()
    if line_edit is not None:
        line_edit.installEventFilter(year_filter)
    calendar._year_edit_filter = year_filter  # keep the QObject alive

    year_button.clicked.connect(begin_year_edit)
    year_edit.editingFinished.connect(finish_year_edit)
    calendar.currentPageChanged.connect(sync_year_editor)
    sync_year_editor(calendar.yearShown(), calendar.monthShown())


def _dark_calendar_style() -> str:
    return """
QCalendarWidget {
  background: #06111C;
  color: #F8FBFF;
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 14px;
  selection-background-color: #22D3EE;
  selection-color: #03111B;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 rgba(10, 24, 39, 245),
    stop:0.55 rgba(11, 46, 62, 245),
    stop:1 rgba(13, 69, 63, 235));
  border: none;
  border-top-left-radius: 14px;
  border-top-right-radius: 14px;
  min-height: 44px;
}
QCalendarWidget QToolButton {
  color: #ECFEFF;
  background: rgba(15, 35, 55, 0.88);
  border: none;
  border-radius: 10px;
  min-height: 30px;
  margin: 6px 4px;
  padding: 3px 10px;
  font-weight: 900;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
  min-width: 32px;
  max-width: 36px;
  padding: 0;
  font-size: 18px;
  color: #7DF9FF;
}
QCalendarWidget QToolButton#qt_calendar_monthbutton,
QCalendarWidget QToolButton#qt_calendar_yearbutton {
  min-width: 84px;
}
QCalendarWidget QToolButton:hover {
  color: #FFFFFF;
  background: rgba(14, 116, 144, 0.9);
}
QCalendarWidget QToolButton:pressed {
  background: rgba(8, 145, 178, 0.95);
}
QCalendarWidget QToolButton::menu-indicator {
  image: none;
  width: 0;
}
QCalendarWidget QSpinBox {
  color: #ECFEFF;
  background: rgba(6, 18, 31, 0.98);
  border: none;
  border-radius: 10px;
  min-height: 30px;
  padding: 2px 10px;
  font-weight: 900;
  selection-background-color: #22D3EE;
  selection-color: #03111B;
}
QCalendarWidget QMenu {
  color: #F8FBFF;
  background: #07111C;
  border: 1px solid rgba(125, 211, 252, 0.2);
  border-radius: 12px;
  padding: 6px;
}
QCalendarWidget QMenu::item {
  padding: 7px 16px;
  border-radius: 8px;
  margin: 1px;
}
QCalendarWidget QMenu::item:selected {
  color: #ECFEFF;
  background: rgba(14, 116, 144, 0.92);
}
QCalendarWidget QAbstractItemView {
  color: #D8E7F5;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #07111D,
    stop:1 #061926);
  alternate-background-color: #0B1724;
  border: none;
  outline: 0;
  selection-background-color: #22D3EE;
  selection-color: #03111B;
  font-weight: 800;
}
QCalendarWidget QAbstractItemView::item {
  min-width: 34px;
  min-height: 28px;
  border-radius: 9px;
  padding: 3px;
}
QCalendarWidget QAbstractItemView::item:hover {
  color: #ECFEFF;
  background: rgba(34, 211, 238, 0.14);
}
QCalendarWidget QAbstractItemView::item:selected {
  color: #03111B;
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #7DF9FF,
    stop:1 #5EEAD4);
  border: 1px solid rgba(236, 254, 255, 0.68);
}
QCalendarWidget QAbstractItemView:disabled {
  color: #536174;
}
"""
