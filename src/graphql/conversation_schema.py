"""GraphQL schema for conversation history query API."""
from typing import Optional

import strawberry

from ..shared_services.conversation_store import ConversationStore


@strawberry.type
class Turn:
    """A single conversation turn."""
    role: str
    content: str
    metadata_json: Optional[str] = None

    @classmethod
    def from_store_turn(cls, turn) -> "Turn":
        import json
        meta = getattr(turn, "metadata", None)
        return cls(
            role=turn.role,
            content=turn.content,
            metadata_json=json.dumps(meta) if meta else None,
        )


@strawberry.type
class Conversation:
    """Conversation history for a session."""
    session_id: str
    turns: list[Turn]


@strawberry.type
class SessionInfo:
    """Session identifier (for list)."""
    session_id: str


@strawberry.type
class Query:
    """Conversation history queries."""

    @strawberry.field
    def conversation(
        self,
        info: strawberry.Info,
        session_id: str,
        limit: Optional[int] = None,
    ) -> Optional[Conversation]:
        """Get conversation history for a session. Returns null if session not found."""
        store: ConversationStore = info.context["conversation_store"]
        turns = store.get_history(session_id, limit=limit)
        if not turns:
            return None
        return Conversation(
            session_id=session_id,
            turns=[Turn.from_store_turn(t) for t in turns],
        )

    @strawberry.field
    def sessions(self, info: strawberry.Info, limit: Optional[int] = 50) -> list[SessionInfo]:
        """List recent session IDs (e.g. for admin or dropdown)."""
        store: ConversationStore = info.context["conversation_store"]
        session_ids = store.list_sessions(limit=limit)
        return [SessionInfo(session_id=sid) for sid in session_ids]


