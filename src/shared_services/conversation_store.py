"""Conversation store for long-term history. Production: DynamoDB."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Turn:
    """A single conversation turn."""
    role: str  # "user" | "assistant" | "system"
    content: str
    metadata: Optional[dict[str, Any]] = None


class ConversationStore(ABC):
    """Interface for long-term conversation history. Production: DynamoDB."""

    @abstractmethod
    def append_turn(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
        """Append a turn to the conversation."""
        pass

    @abstractmethod
    def get_history(self, session_id: str, limit: Optional[int] = None) -> list[Turn]:
        """Get conversation history for a session."""
        pass

    @abstractmethod
    def list_sessions(self, limit: Optional[int] = None) -> list[str]:
        """List session IDs (e.g. for GraphQL / admin). Order not guaranteed in stub."""
        pass


class InMemoryConversationStore(ConversationStore):
    """In-memory stub. Replace with DynamoDB in production."""

    def __init__(self) -> None:
        self._history: dict[str, list[Turn]] = {}

    def append_turn(self, session_id: str, role: str, content: str, metadata: Optional[dict] = None) -> None:
        if session_id not in self._history:
            self._history[session_id] = []
        self._history[session_id].append(Turn(role=role, content=content, metadata=metadata))

    def get_history(self, session_id: str, limit: Optional[int] = None) -> list[Turn]:
        turns = self._history.get(session_id, [])
        if limit:
            return turns[-limit:]
        return turns

    def list_sessions(self, limit: Optional[int] = None) -> list[str]:
        ids = list(self._history.keys())
        if limit:
            return ids[:limit]
        return ids
