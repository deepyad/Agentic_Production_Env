"""Base types for agent subgraphs."""
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State slice passed to/from agent subgraphs."""
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    resolved: bool
    needs_escalation: bool
    metadata: dict[str, Any]
