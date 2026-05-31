from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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


class InteractionEffectFilter(QObject):
    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QWidget) and event.type() == QEvent.MouseButtonPress:
            self._play_backdrop_pulse(watched, event)
        return super().eventFilter(watched, event)

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


def animate_value_tick(widget: QWidget, *, duration: int = 180) -> None:
    if not isinstance(widget, QWidget):
        return
    old_animation = getattr(widget, "_floating_todo_value_tick_animation", None)
    if old_animation is not None:
        old_animation.stop()

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.88)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(0.88)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.OutQuad)
    widget._floating_todo_value_tick_animation = animation

    def finish() -> None:
        if widget.graphicsEffect() is effect:
            widget.setGraphicsEffect(None)
        widget._floating_todo_value_tick_animation = None

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
