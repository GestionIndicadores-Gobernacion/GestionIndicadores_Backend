# app/modules/notifications/services/notification_handler.py
from app.core.extensions import db
from datetime import datetime, date, timedelta
from app.modules.notifications.models.notification import Notification


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

    # ── NUEVO ────────────────────────────────────────────────────────────────

    @staticmethod
    def generate_activity_reminders(user_id: int) -> None:
        """
        Genera recordatorios para actividades pendientes cuya fecha
        es hoy, mañana (+1) o en 3 días (+3).
        Evita duplicados comparando (entity_id, title) en las notificaciones
        ya existentes con category='action_plan_reminder'.
        """
        from app.modules.action_plans.models.action_plan import (
            ActionPlan, ActionPlanObjective, ActionPlanActivity
        )
        from sqlalchemy.orm import selectinload

        today = date.today()
        targets = {
            today:                    "hoy",
            today + timedelta(days=1): "mañana",
            today + timedelta(days=3): "en 3 días",
        }

        # Claves ya existentes para no duplicar
        existing_keys = {
            (n.entity_id, n.title)
            for n in Notification.query.filter_by(
                user_id=user_id,
                category="action_plan_reminder"
            ).all()
        }

        plans = (
            ActionPlan.query
            .options(
                selectinload(ActionPlan.plan_objectives)
                .selectinload(ActionPlanObjective.activities)
            )
            .filter(ActionPlan.responsible_user_id == user_id)
            .all()
        )

        created = False
        for plan in plans:
            for obj in plan.plan_objectives:
                for activity in obj.activities:
                    if activity.evidence_url:
                        continue  # ya realizada

                    if activity.delivery_date not in targets:
                        continue

                    label = targets[activity.delivery_date]
                    title = f"Recordatorio: actividad para {label}"

                    if (activity.id, title) in existing_keys:
                        continue  # ya notificado

                    NotificationHandler.create(
                        user_id=user_id,
                        title=title,
                        message=f'"{activity.name}" vence {label}.',
                        category="action_plan_reminder",
                        entity_id=activity.id,
                    )
                    created = True

        if created:
            db.session.commit()