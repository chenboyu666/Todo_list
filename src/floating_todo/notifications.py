from __future__ import annotations

from floating_todo.app_identity import APP_DISPLAY_NAME


class NotificationSender:
    def send(self, title: str, message: str) -> None:
        try:
            from winotify import Notification

            toast = Notification(app_id=APP_DISPLAY_NAME, title=title, msg=message)
            toast.show()
        except Exception:
            return None
