"""HITL handler: create a support ticket and record in pending escalations for human pickup."""
from .base import EscalationContext, HitlHandler

# Lazy import to avoid circular deps; we only need the tool's logic
def _create_ticket(subject: str, description: str, priority: str = "high") -> str:
    from ..tools.support_tools import create_support_ticket
    return create_support_ticket.invoke({"subject": subject, "description": description, "priority": priority})


# In-memory store of pending escalations (session_id -> context summary) for dashboards/APIs
_pending_escalations: dict[str, dict] = {}


def get_pending_escalations() -> dict[str, dict]:
    """Return current pending escalations (session_id -> summary). For admin/API use."""
    return dict(_pending_escalations)


def clear_pending_escalation(session_id: str) -> None:
    """Remove a session from pending (e.g. when a human has picked it up)."""
    _pending_escalations.pop(session_id, None)


class TicketHitlHandler(HitlHandler):
    """Create a support ticket and add session to pending escalations so humans can pick up."""

    def on_escalate(self, ctx: EscalationContext) -> None:
        subject = f"Escalation: session {ctx.session_id} ({ctx.reason})"
        description = (
            f"Session: {ctx.session_id}\nUser: {ctx.user_id}\nReason: {ctx.reason}\n"
            f"Last user message: {ctx.last_user_message or '(none)'}\n"
            f"Last agent message: {ctx.last_agent_message or '(none)'}\n"
            + (f"Metadata: {ctx.metadata}" if ctx.metadata else "")
        )
        try:
            _create_ticket(subject=subject, description=description, priority="high")
        except Exception:
            pass
        _pending_escalations[ctx.session_id] = {
            "session_id": ctx.session_id,
            "user_id": ctx.user_id,
            "reason": ctx.reason,
            "last_user_message": ctx.last_user_message,
        }
