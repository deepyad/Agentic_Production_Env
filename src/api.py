"""FastAPI entrypoint: receives message → router → supervisor graph → response; GraphQL for conversation history."""
from typing import Optional

import strawberry
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from strawberry.fastapi import GraphQLRouter

from .router import SessionRouter, RouterResult
from .supervisor import build_supervisor
from .shared_services.conversation_store import ConversationStore, InMemoryConversationStore
from .graphql.conversation_schema import Query as GraphQLQuery

# --- App setup ---

app = FastAPI(title="Agentic Production Framework", version="0.1.0")
router_svc = SessionRouter()
supervisor = build_supervisor(use_checkpointer=True)
conversation_store: ConversationStore = InMemoryConversationStore()

# GraphQL: conversation history query API at /graphql
graphql_schema = strawberry.Schema(GraphQLQuery)

def get_graphql_context(request=None):
    return {"conversation_store": conversation_store}

graphql_app = GraphQLRouter(graphql_schema, context_getter=get_graphql_context)
app.include_router(graphql_app, prefix="/graphql")


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
    """Health check."""
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
