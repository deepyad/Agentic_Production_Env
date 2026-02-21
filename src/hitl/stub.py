"""Stub HITL handler: no-op (no ticket, no email). User still sees 'Connecting you with a human agent'."""
from .base import EscalationContext, HitlHandler


class StubHitlHandler(HitlHandler):
    """No-op: does nothing. Use when HITL is disabled or for testing."""

    def on_escalate(self, ctx: EscalationContext) -> None:
        pass
