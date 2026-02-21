"""Billing agent tools: invoice lookup, refund status, refund request."""
from langchain_core.tools import tool


@tool
def look_up_invoice(invoice_id: str) -> str:
    """Look up an invoice by ID. Use when the user asks about a specific invoice, payment status, or invoice details."""
    # Stub: production would call billing API
    return f"[Stub] Invoice {invoice_id}: status=paid, amount=$150.00, due_date=2025-01-15. Contact billing team for disputes."


@tool
def get_refund_status(refund_id: str) -> str:
    """Get the status of a refund request. Use when the user asks about an existing refund."""
    # Stub: production would call billing API
    return f"[Stub] Refund {refund_id}: status=processing, expected 5-7 business days. Contact billing@example.com for details."


@tool
def create_refund_request(
    order_id: str,
    reason: str,
    amount_cents: int | None = None,
) -> str:
    """Create a refund request for an order. Use when the user wants to request a refund. Amount is optional (full refund if omitted)."""
    # Stub: production would call billing API
    amt = f"${amount_cents/100:.2f}" if amount_cents else "full"
    return f"[Stub] Refund request created for order {order_id}, {amt} refund. Reason: {reason}. Ref: REF-{hash(order_id) % 100000}. Processing within 3-5 business days."


def get_billing_tools() -> list:
    """Return tools for the Billing agent."""
    return [look_up_invoice, get_refund_status, create_refund_request]
