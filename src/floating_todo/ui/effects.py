from __future__ import annotations

from math import hypot

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRectF,
    QTimer,
    Qt,
    Property,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QWidget,
)


def apply_soft_shadow(widget: QWidget, *, blur: int = 28, y_offset: int = 10, alpha: int = 105) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


class ClickBurst(QWidget):
    def __init__(self, parent: QWidget, origin: QPoint, color: QColor) -> None:
        super().__init__(parent)
        self._progress = 0.0
        self._origin = QPointF(origin)
        self._color = color
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()

        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.setDuration(360)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.finished.connect(self.deleteLater)
        self._animation.start()

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = Property(float, _get_progress, _set_progress)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        if rect.isEmpty():
            return

        radius = 5 + hypot(rect.width(), rect.height()) * 0.72 * self._progress
        fade = 1.0 - self._progress
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
        painter.setClipPath(path)

        fill = QColor(self._color)
        fill.setAlpha(int(115 * fade))
        edge = QColor(self._color)
        edge.setAlpha(int(34 * fade))
        transparent = QColor(self._color)
        transparent.setAlpha(0)

        gradient = QRadialGradient(self._origin, radius)
        gradient.setColorAt(0.0, fill)
        gradient.setColorAt(0.58, edge)
        gradient.setColorAt(1.0, transparent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(self._origin, radius, radius)

        ring = QColor(self._color)
        ring.setAlpha(int(135 * fade))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ring, 1.4))
        painter.drawEllipse(self._origin, radius * 0.58, radius * 0.58)


class InteractionEffectFilter(QObject):
    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QWidget) and event.type() == QEvent.MouseButtonPress:
            self._play_backdrop_pulse(watched, event)

        if not isinstance(watched, QAbstractButton):
            return super().eventFilter(watched, event)
        if not watched.isEnabled():
            return super().eventFilter(watched, event)

        event_type = event.type()
        if event_type == QEvent.Enter:
            self._apply_button_glow(watched)
        elif event_type == QEvent.Leave:
            self._clear_button_glow(watched)
        elif event_type == QEvent.MouseButtonPress and _event_button(event) == Qt.LeftButton:
            ClickBurst(watched, _event_pos(event, watched), _button_effect_color(watched))
            self._apply_button_glow(watched, stronger=True)
        elif event_type == QEvent.MouseButtonRelease:
            self._apply_button_glow(watched)
        return super().eventFilter(watched, event)

    def _apply_button_glow(self, button: QAbstractButton, *, stronger: bool = False) -> None:
        existing = button.graphicsEffect()
        if existing is not None and not getattr(button, "_floating_todo_button_glow", False):
            return
        effect = existing if getattr(button, "_floating_todo_button_glow", False) else QGraphicsDropShadowEffect(button)
        color = _button_effect_color(button)
        color.setAlpha(145 if stronger else 92)
        effect.setColor(color)
        effect.setOffset(0, 0)
        effect.setBlurRadius(22 if stronger else 16)
        button.setGraphicsEffect(effect)
        button._floating_todo_button_glow = True

    def _clear_button_glow(self, button: QAbstractButton) -> None:
        if getattr(button, "_floating_todo_button_glow", False):
            button.setGraphicsEffect(None)
            button._floating_todo_button_glow = False

    def _play_backdrop_pulse(self, widget: QWidget, event) -> None:
        global_pos = _event_global_pos(event, widget)
        root = _find_backdrop_root(widget)
        add_click_pulse = getattr(root, "add_click_pulse", None) if root is not None else None
        if callable(add_click_pulse):
            add_click_pulse(root.mapFromGlobal(global_pos))


def install_global_interaction_effects(app: QApplication | None = None) -> InteractionEffectFilter | None:
    app = app or QApplication.instance()
    if app is None or not hasattr(app, "installEventFilter"):
        return None
    installed = getattr(app, "_floating_todo_interaction_filter", None)
    if installed is not None:
        return installed
    effect_filter = InteractionEffectFilter(app)
    app.installEventFilter(effect_filter)
    app._floating_todo_interaction_filter = effect_filter
    return effect_filter


def prepare_window_entrance(
    widget: QWidget,
    *,
    target_opacity: float | None = None,
    slide: int = 12,
    duration: int = 230,
) -> None:
    if not hasattr(widget, "setWindowOpacity") or not hasattr(widget, "windowOpacity"):
        return
    try:
        target = float(target_opacity if target_opacity is not None else widget.windowOpacity())
        widget.setWindowOpacity(0.0)
    except RuntimeError:
        return
    QTimer.singleShot(0, lambda widget=widget, target=target: _start_window_entrance(widget, target, slide, duration))


def animate_content_swap(widget: QWidget, *, duration: int = 180) -> None:
    if not isinstance(widget, QWidget):
        return
    old_animation = getattr(widget, "_floating_todo_content_animation", None)
    if old_animation is not None:
        old_animation.stop()

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutCubic)
    widget._floating_todo_content_animation = animation

    def finish() -> None:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
        widget._floating_todo_content_animation = None

    animation.finished.connect(finish)
    animation.start()


def _start_window_entrance(widget: QWidget, target_opacity: float, slide: int, duration: int) -> None:
    try:
        if not widget.isVisible():
            return
        group = QParallelAnimationGroup(widget)
        opacity = QPropertyAnimation(widget, b"windowOpacity", group)
        opacity.setDuration(duration)
        opacity.setStartValue(0.0)
        opacity.setEndValue(target_opacity)
        opacity.setEasingCurve(QEasingCurve.OutCubic)
        group.addAnimation(opacity)

        if slide:
            final_pos = widget.pos()
            widget.move(final_pos.x(), final_pos.y() + slide)
            position = QPropertyAnimation(widget, b"pos", group)
            position.setDuration(duration)
            position.setStartValue(widget.pos())
            position.setEndValue(final_pos)
            position.setEasingCurve(QEasingCurve.OutCubic)
            group.addAnimation(position)

        widget._floating_todo_window_entrance = group

        def finish() -> None:
            widget.setWindowOpacity(target_opacity)
            widget._floating_todo_window_entrance = None

        group.finished.connect(finish)
        group.start()
    except RuntimeError:
        return


def _event_button(event):
    button = getattr(event, "button", None)
    return button() if callable(button) else None


def _event_pos(event, widget: QWidget) -> QPoint:
    position = getattr(event, "position", None)
    if callable(position):
        return position().toPoint()
    pos = getattr(event, "pos", None)
    if callable(pos):
        return pos()
    return widget.rect().center()


def _event_global_pos(event, widget: QWidget) -> QPoint:
    global_position = getattr(event, "globalPosition", None)
    if callable(global_position):
        return global_position().toPoint()
    global_pos = getattr(event, "globalPos", None)
    if callable(global_pos):
        return global_pos()
    return widget.mapToGlobal(_event_pos(event, widget))


def _button_effect_color(button: QAbstractButton) -> QColor:
    text = button.text().lower()
    if button.objectName() == "dangerButton" or "delete" in text or "删除" in text:
        return QColor("#FCA5A5")
    if "save" in text or "保存" in text or "+" in text:
        return QColor("#A7F3D0")
    return QColor("#7DD3FC")


def _find_backdrop_root(widget: QWidget) -> QWidget | None:
    current: QWidget | None = widget
    while current is not None:
        if current.objectName() == "mainRoot":
            return current
        root = current.findChild(QWidget, "mainRoot")
        if root is not None:
            return root
        current = current.parentWidget()
    return None
