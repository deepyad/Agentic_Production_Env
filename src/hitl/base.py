"""Human-in-the-loop (HITL): interface for escalation handling."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class EscalationContext:
    """Context passed to HITL when escalation is triggered."""
    session_id: str
    user_id: str
    reason: str  # e.g. "low_faithfulness", "agent_requested", "failover_failed"
    last_user_message: Optional[str] = None
    last_agent_message: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None  # e.g. {"faithfulness_score": 0.5}


class HitlHandler(ABC):
    """Interface: when the supervisor escalates, perform an action (create ticket, notify, etc.)."""

    @abstractmethod
    def on_escalate(self, ctx: EscalationContext) -> None:
        """
        Called when the graph takes the escalate path (e.g. low faithfulness or agent set needs_escalation).
        Implementations may: create a support ticket, send email to agents, push to a human queue, etc.
        """
        pass
