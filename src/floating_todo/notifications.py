from __future__ import annotations


class NotificationSender:
    def send(self, title: str, message: str) -> None:
        try:
            from winotify import Notification

            toast = Notification(app_id="FloatingTodo", title=title, msg=message)
            toast.show()
        except Exception:
            return None
