"""Support agent tools: knowledge base search, create ticket."""
from langchain_core.tools import tool


@tool
def search_knowledge_base(query: str) -> str:
    """Search the support knowledge base for FAQs and help articles. Use when the user asks about products, policies, or how-to questions."""
    # Stub: production would call real KB / Weaviate
    return f"[Stub KB] Found 2 articles for '{query}': (1) Getting started guide, (2) Common troubleshooting. Suggest checking the docs or escalating if needed."


@tool
def create_support_ticket(
    subject: str,
    description: str,
    priority: str = "normal",
) -> str:
    """Create a support ticket for human follow-up. Use when the user needs escalation or the issue cannot be resolved by the bot."""
    # Stub: production would call ticketing API
    return f"[Stub] Ticket created: subject='{subject}', priority={priority}. Ref: TKT-{hash(description) % 100000}. A human agent will follow up within 24 hours."


def get_support_tools() -> list:
    """Return tools for the Support agent."""
    return [search_knowledge_base, create_support_ticket]
