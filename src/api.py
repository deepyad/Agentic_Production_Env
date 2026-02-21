"""FastAPI entrypoint: receives message → router → supervisor graph → response; GraphQL for conversation history."""
from typing import Optional

import strawberry
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from strawberry.fastapi import GraphQLRouter

from .config import config
from .router import SessionRouter, RouterResult
from .supervisor import build_supervisor
from .shared_services.conversation_store import ConversationStore, InMemoryConversationStore
from .graphql.conversation_schema import Query as GraphQLQuery
from .agent_ops import CircuitBreaker, get_agent_ops_health
from .hitl.ticket import get_pending_escalations, clear_pending_escalation

# --- App setup ---

app = FastAPI(title="Agentic Production Framework", version="0.1.0")
router_svc = SessionRouter()

# AgentOps: circuit breaker shared between supervisor and /health
circuit_breaker: Optional[CircuitBreaker] = None
if config.agent_ops_enabled:
    circuit_breaker = CircuitBreaker(
        failure_threshold=config.circuit_breaker_failure_threshold,
        cooldown_seconds=config.circuit_breaker_cooldown_seconds,
    )

supervisor = build_supervisor(use_checkpointer=True, circuit_breaker=circuit_breaker)
conversation_store: ConversationStore = InMemoryConversationStore()

# Agent IDs used by supervisor (for health reporting)
AGENT_IDS = ["support", "billing"]

# GraphQL: conversation history query API at /graphql
graphql_schema = strawberry.Schema(GraphQLQuery)

def get_graphql_context(request=None):
    return {"conversation_store": conversation_store}

graphql_app = GraphQLRouter(graphql_schema, context_getter=get_graphql_context)
app.include_router(graphql_app, prefix="/graphql")


# --- HITL (human-in-the-loop) endpoints ---

@app.get("/hitl/pending")
def hitl_pending():
    """Return pending escalations (sessions waiting for a human). Populated when HITL_HANDLER=ticket."""
    return get_pending_escalations()


@app.post("/hitl/pending/{session_id}/clear")
def hitl_clear(session_id: str):
    """Mark a session as picked up by a human (remove from pending list)."""
    clear_pending_escalation(session_id)
    return {"session_id": session_id, "cleared": True}


# --- Request / Response models ---

class ChatRequest(BaseModel):
    """Incoming chat message."""
    user_id: str
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat reply."""
    session_id: str
    reply: str
    agent_id: Optional[str] = None


# --- Endpoints ---

@app.get("/health")
def health():
    """
    Health check. When AgentOps is enabled, returns agent circuit states and MCP status.
    status: ok | degraded (e.g. one or more agents circuit_open or MCP unavailable).
    Returns 503 when status is degraded.
    """
    if circuit_breaker is not None:
        payload = get_agent_ops_health(
            circuit_breaker=circuit_breaker,
            agent_ids=AGENT_IDS,
            mcp_available=True,  # Assumed ok if app started; extend to probe MCP if needed
        )
        status_code = 200 if payload["status"] == "ok" else 503
        return JSONResponse(content=payload, status_code=status_code)
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Chat endpoint: message → router → supervisor → reply.
    Mimics chatbot: user sends message, gets reply from appropriate agent.
    """
    # 1. Route: get session_id + suggested agent pool IDs
    route_result: RouterResult = router_svc.route(
        user_id=req.user_id,
        message=req.message,
        session_id=req.session_id,
    )

    # 2. Build initial state for supervisor
    thread_id = route_result.session_id
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=req.message)],
        "session_id": thread_id,
        "user_id": req.user_id,
        "suggested_agent_ids": route_result.suggested_agent_pool_ids,
    }

    # 3. Invoke supervisor graph
    try:
        result = supervisor.invoke(initial_state, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # 4. Extract last AIMessage as reply
    messages = result.get("messages", [])
    reply = ""
    for m in reversed(messages):
        if hasattr(m, "content") and m.type == "ai":
            reply = str(m.content)
            break

    if not reply:
        reply = "I couldn't generate a response. Please try again."

    agent_id = result.get("current_agent")

    # Persist to conversation store (long-term history for RAG / analytics)
    conversation_store.append_turn(thread_id, "user", req.message)
    conversation_store.append_turn(thread_id, "assistant", reply, metadata={"agent_id": agent_id})

    return ChatResponse(
        session_id=thread_id,
        reply=reply,
        agent_id=agent_id,
    )
