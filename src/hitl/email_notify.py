"""HITL handler: send email (or log) to notify support team of escalation."""
import logging
from .base import EscalationContext, HitlHandler

logger = logging.getLogger(__name__)


class EmailNotifyHitlHandler(HitlHandler):
    """
    Notify support team of escalation. Default: log only (no SMTP).
    Set HITL_EMAIL_TO and optionally use SMTP in production for real email.
    """

    def __init__(self, email_to: str | None = None) -> None:
        self.email_to = email_to

    def on_escalate(self, ctx: EscalationContext) -> None:
        body = (
            f"Escalation: session={ctx.session_id}, user={ctx.user_id}, reason={ctx.reason}\n"
            f"Last user message: {ctx.last_user_message or '(none)'}\n"
            f"Last agent message: {ctx.last_agent_message or '(none)'}"
        )
        if self.email_to:
            # Production: send via smtplib or your email API
            logger.info("HITL email (would send to %s): %s", self.email_to, body[:200])
        else:
            logger.info("HITL escalation (no email configured): %s", body[:300])
