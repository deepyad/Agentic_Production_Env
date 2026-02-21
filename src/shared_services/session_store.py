"""Session store interface for LangGraph checkpointer state. Production: Redis."""
from abc import ABC, abstractmethod
from typing import Any, Optional


class SessionStore(ABC):
    """Interface for short-term session state. Production: Redis."""

    @abstractmethod
    def get(self, session_id: str) -> Optional[Any]:
        """Get state for session."""
        pass

    @abstractmethod
    def set(self, session_id: str, state: Any, ttl_seconds: int = 86400) -> None:
        """Set state for session with optional TTL (default 24h)."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory stub. Replace with Redis in production."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, session_id: str) -> Optional[Any]:
        return self._store.get(session_id)

    def set(self, session_id: str, state: Any, ttl_seconds: int = 86400) -> None:
        self._store[session_id] = state
