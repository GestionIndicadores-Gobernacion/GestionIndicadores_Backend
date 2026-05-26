# app/modules/support/models/__init__.py
from app.modules.support.models.ticket import SupportTicket, TICKET_STATUSES
from app.modules.support.models.message import SupportMessage

__all__ = ["SupportTicket", "SupportMessage", "TICKET_STATUSES"]
