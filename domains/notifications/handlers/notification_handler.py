# domains/notifications/handlers/notification_handler.py
from extensions import db
from datetime import datetime
from domains.notifications.models.notification import Notification


class NotificationHandler:

    @staticmethod
    def create(user_id: int, title: str, message: str, category: str = "action_plan", entity_id: int = None):
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            category=category,
            entity_id=entity_id,
        )
        db.session.add(notification)
        # No hace commit, se espera que el caller lo haga
        return notification

    @staticmethod
    def get_by_user(user_id: int, unread_only: bool = False):
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(Notification.created_at.desc()).all()

    @staticmethod
    def count_unread(user_id: int) -> int:
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()

    @staticmethod
    def mark_as_read(notification_id: int, user_id: int):
        notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if not notification:
            return None, {"notification": "No encontrada"}
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        return notification, None

    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        count = Notification.query.filter_by(user_id=user_id, is_read=False).update({
            "is_read": True,
            "read_at": datetime.utcnow()
        })
        db.session.commit()
        return count