"""Supervisor LangGraph graph: route → invoke_agent → aggregate → (optional) escalate."""
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from .config import config
from .registry import AgentRegistry, InMemoryAgentRegistry
from .router import SessionRouter
from .agents.support import create_support_agent
from .agents.billing import create_billing_agent
from .shared_services.rag import StubRAGService
from .shared_services.faithfulness import (
    FaithfulnessScorer,
    StubFaithfulnessScorer,
    TFFaithfulnessScorer,
)


class SupervisorState(TypedDict, total=False):
    """State schema for the supervisor graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    current_agent: str | None
    session_id: str
    user_id: str
    suggested_agent_ids: list[str]
    metadata: dict[str, Any]
    needs_escalation: bool
    resolved: bool
    last_rag_context: str


def create_supervisor_graph(
    router: SessionRouter | None = None,
    registry: AgentRegistry | None = None,
    rag=None,
    faithfulness_scorer: FaithfulnessScorer | None = None,
) -> StateGraph:
    """Create the supervisor LangGraph graph with route, invoke_agent, aggregate, escalate."""

    router = router or SessionRouter()
    registry = registry or InMemoryAgentRegistry()
    rag = rag or StubRAGService()
    scorer = faithfulness_scorer or (
        TFFaithfulnessScorer(model_path=config.tf_faithfulness_model_path or None)
        if config.use_tf_faithfulness
        else StubFaithfulnessScorer()
    )

    support_agent = create_support_agent(rag=rag)
    billing_agent = create_billing_agent(rag=rag)
    agents_map = {"support": support_agent, "billing": billing_agent}

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        """Use router suggestions or first suggested agent. Production: LLM to pick from registry."""
        suggested = state.get("suggested_agent_ids", ["support"])
        # Pick first suggested agent that exists
        for aid in suggested:
            if aid in agents_map:
                return {"current_agent": aid}
        return {"current_agent": "support"}

    def invoke_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        """Invoke the chosen agent pool subgraph."""
        agent_id = state.get("current_agent", "support")
        agent = agents_map.get(agent_id, support_agent)
        result = agent(state)
        return {
            "messages": result.get("messages", []),
            "resolved": result.get("resolved", False),
            "needs_escalation": result.get("needs_escalation", False),
            "last_rag_context": result.get("last_rag_context", ""),
        }

    def aggregate_node(state: dict[str, Any]) -> dict[str, Any]:
        """Merge agent response into state. Run faithfulness scorer; if score < threshold, escalate."""
        out: dict[str, Any] = {}
        messages = state.get("messages", [])
        last_ai = next((m for m in reversed(messages) if hasattr(m, "type") and m.type == "ai"), None)
        response_text = getattr(last_ai, "content", None) or ""
        context = state.get("last_rag_context", "") or ""
        if response_text and scorer:
            faith = scorer.score(response_text, context)
            if faith < config.hallucination_threshold_faithfulness:
                out["needs_escalation"] = True
        return out

    def escalate_node(state: dict[str, Any]) -> dict[str, Any]:
        """Handle escalation: route to human or escalation agent."""
        return {
            "messages": [
                AIMessage(
                    content="I'm connecting you with a human agent. Please hold."
                )
            ],
        }

    # Build graph
    builder = StateGraph(SupervisorState)

    builder.add_node("route", route_node)
    builder.add_node("invoke_agent", invoke_agent_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("escalate", escalate_node)

    builder.set_entry_point("route")
    builder.add_edge("route", "invoke_agent")
    builder.add_edge("invoke_agent", "aggregate")

    def after_aggregate(state: dict) -> Literal["escalate", "__end__"]:
        if state.get("needs_escalation"):
            return "escalate"
        return "__end__"

    builder.add_conditional_edges("aggregate", after_aggregate, path_map={"escalate": "escalate", "__end__": END})
    builder.add_edge("escalate", END)

    return builder


def build_supervisor(
    router: SessionRouter | None = None,
    registry: AgentRegistry | None = None,
    use_checkpointer: bool = True,
) -> Any:
    """Build compiled supervisor graph with optional in-memory checkpointer."""
    graph = create_supervisor_graph(router=router, registry=registry)
    return graph.compile(checkpointer=MemorySaver() if use_checkpointer else None)
