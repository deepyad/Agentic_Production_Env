"""Human-in-the-loop (HITL): when escalation is triggered, notify or create ticket for humans."""
from .base import HitlHandler, EscalationContext
from .stub import StubHitlHandler
from .ticket import TicketHitlHandler
from .email_notify import EmailNotifyHitlHandler

__all__ = [
    "HitlHandler",
    "EscalationContext",
    "StubHitlHandler",
    "TicketHitlHandler",
    "EmailNotifyHitlHandler",
    "get_hitl_handler",
]


def get_hitl_handler(handler_name: str = "stub", enabled: bool = True, email_to: str = "") -> "HitlHandler":
    """Return the configured HITL handler. handler_name: stub | ticket | email."""
    if not enabled:
        return StubHitlHandler()
    name = (handler_name or "stub").lower().strip()
    if name == "ticket":
        return TicketHitlHandler()
    if name == "email":
        return EmailNotifyHitlHandler(email_to=email_to or None)
    return StubHitlHandler()
