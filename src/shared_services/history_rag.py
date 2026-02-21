"""RAG over conversation history for issue handling. Production: Weaviate index of past turns."""
from dataclasses import dataclass
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


@dataclass
class HistoryChunk:
    """A retrieved turn from conversation history."""
    content: str
    role: str
    turn_index: int


class ConversationHistoryRAG:
    """
    Retrieve from conversation history for issue handling.
    Simple: returns last N turns. Production: embed turns, store in Weaviate, retrieve similar.
    """

    def __init__(self, max_turns: int = 10) -> None:
        self.max_turns = max_turns

    def retrieve(
        self,
        messages: list[BaseMessage],
        query: str,
        top_k: Optional[int] = None,
    ) -> list[HistoryChunk]:
        """
        Retrieve relevant turns from conversation history.
        Simple impl: return last N turns for context. Production: Weaviate search over embedded turns.
        """
        k = top_k or self.max_turns
        chunks: list[HistoryChunk] = []
        for i, m in enumerate(messages[-k:]):
            content = getattr(m, "content", None)
            if not content:
                continue
            role = "user" if isinstance(m, HumanMessage) else "assistant"
            chunks.append(HistoryChunk(content=str(content), role=role, turn_index=i))
        return chunks

    def format_for_context(self, messages: list[BaseMessage], max_turns: int = 10) -> str:
        """Format conversation history for inclusion in agent prompt."""
        chunks = self.retrieve(messages, "", top_k=max_turns)
        if not chunks:
            return "(No previous conversation)"
        lines = []
        for c in chunks:
            prefix = "User:" if c.role == "user" else "Agent:"
            lines.append(f"{prefix} {c.content}")
        return "\n".join(lines)
