from __future__ import annotations

import sys
from types import SimpleNamespace


def test_notification_sender_builds_and_shows_winotify_notification(monkeypatch) -> None:
    from floating_todo.notifications import NotificationSender

    created = {}

    class FakeNotification:
        def __init__(self, *, app_id: str, title: str, msg: str) -> None:
            created["args"] = {"app_id": app_id, "title": title, "msg": msg}
            created["shown"] = False

        def show(self) -> None:
            created["shown"] = True

    monkeypatch.setitem(sys.modules, "winotify", SimpleNamespace(Notification=FakeNotification))

    assert NotificationSender().send("Deadline", "Ship it") is None

    assert created["args"] == {
        "app_id": "FloatingTodo",
        "title": "Deadline",
        "msg": "Ship it",
    }
    assert created["shown"] is True


def test_notification_sender_swallows_missing_or_failing_winotify(monkeypatch) -> None:
    from floating_todo.notifications import NotificationSender

    class FailingNotification:
        def __init__(self, *, app_id: str, title: str, msg: str) -> None:
            raise RuntimeError("toast unavailable")

    monkeypatch.setitem(sys.modules, "winotify", SimpleNamespace(Notification=FailingNotification))

    assert NotificationSender().send("Deadline", "Ship it") is None

    monkeypatch.delitem(sys.modules, "winotify", raising=False)

    assert NotificationSender().send("Deadline", "Ship it") is None
