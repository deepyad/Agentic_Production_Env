"""Supervisor LangGraph graph: (optional) plan → route → invoke_agent → aggregate → (optional) escalate."""
import re
from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
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
from .agent_ops.circuit_breaker import CircuitBreaker


class SupervisorState(TypedDict, total=False):
    """State schema for the supervisor graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    current_agent: str | None
    session_id: str
    user_id: str
    suggested_agent_ids: list[str]
    planned_agent_ids: list[str]
    metadata: dict[str, Any]
    needs_escalation: bool
    escalation_reason: str
    resolved: bool
    last_rag_context: str


def create_supervisor_graph(
    router: SessionRouter | None = None,
    registry: AgentRegistry | None = None,
    rag=None,
    faithfulness_scorer: FaithfulnessScorer | None = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> StateGraph:
    """Create the supervisor LangGraph graph with route, invoke_agent, aggregate, escalate.
    When circuit_breaker is provided and agent_ops_enabled, route skips open circuits and
    invoke_agent uses failover on failure.
    """

    router = router or SessionRouter()
    registry = registry or InMemoryAgentRegistry()
    rag = rag or StubRAGService()
    scorer = faithfulness_scorer or (
        TFFaithfulnessScorer(model_path=config.tf_faithfulness_model_path or None)
        if config.use_tf_faithfulness
        else StubFaithfulnessScorer()
    )
    use_ops = config.agent_ops_enabled and circuit_breaker is not None
    fallback_id = config.failover_fallback_agent_id

    support_agent = create_support_agent(rag=rag)
    billing_agent = create_billing_agent(rag=rag)
    agents_map = {"support": support_agent, "billing": billing_agent}
    use_planning = getattr(config, "use_planning", False)

    def plan_node(state: dict[str, Any]) -> dict[str, Any]:
        """When USE_PLANNING: use LLM to pick which agent(s) should handle this turn; otherwise no-op."""
        if not use_planning:
            return {}
        messages = state.get("messages", [])
        last_human = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        suggested = state.get("suggested_agent_ids", ["support"])
        if not last_human or not getattr(last_human, "content", None):
            return {"planned_agent_ids": list(suggested)[:1] or ["support"]}
        user_text = str(last_human.content).strip()[:500]
        available = [a for a in ["support", "billing"] if a in agents_map]
        prompt = (
            f"User message: {user_text}\n"
            f"Suggested agents from router: {suggested}\n"
            f"Available agents: {available}. Which single agent should handle this? Reply with exactly one word: support or billing."
        )
        llm = ChatOpenAI(model=config.default_model, temperature=0)
        try:
            resp = llm.invoke([SystemMessage(content="You are a router. Reply with only one word: support or billing."), HumanMessage(content=prompt)])
            text = (getattr(resp, "content", None) or "").strip().lower()
            match = re.search(r"\b(support|billing)\b", text)
            chosen = match.group(1) if match and match.group(1) in agents_map else (available[0] if available else "support")
            return {"planned_agent_ids": [chosen]}
        except Exception:
            return {"planned_agent_ids": list(suggested)[:1] or ["support"]}

    def route_node(state: dict[str, Any]) -> dict[str, Any]:
        """Use planned_agent_ids (if planning) or router suggestions; skip agents with open circuit when AgentOps enabled."""
        planned = state.get("planned_agent_ids") or []
        suggested = list(planned) if planned else list(state.get("suggested_agent_ids", ["support"]))
        for aid in suggested:
            if aid not in agents_map:
                continue
            if use_ops and not circuit_breaker.is_available(aid):
                continue
            return {"current_agent": aid}
        # No available suggested agent: pick first existing (may be circuit-open; invoke_agent will failover)
        for aid in suggested:
            if aid in agents_map:
                return {"current_agent": aid}
        return {"current_agent": "support"}

    def invoke_agent_node(state: dict[str, Any]) -> dict[str, Any]:
        """Invoke the chosen agent; on failure record and optionally failover to fallback agent."""
        agent_id = state.get("current_agent", "support")
        agent = agents_map.get(agent_id, support_agent)
        fallback_agent = agents_map.get(fallback_id, support_agent) if fallback_id != agent_id else None

        def run_agent(agt: Any, aid: str) -> dict[str, Any]:
            result = agt(state)
            if use_ops:
                circuit_breaker.record_success(aid)
            return {
                "messages": result.get("messages", []),
                "resolved": result.get("resolved", False),
                "needs_escalation": result.get("needs_escalation", False),
                "last_rag_context": result.get("last_rag_context", ""),
            }

        try:
            return run_agent(agent, agent_id)
        except Exception:
            if use_ops:
                circuit_breaker.record_failure(agent_id)
            if config.failover_enabled and fallback_agent is not None and use_ops:
                try:
                    return run_agent(fallback_agent, fallback_id)
                except Exception:
                    if use_ops:
                        circuit_breaker.record_failure(fallback_id)
            # All failed: return friendly message and escalate
            return {
                "messages": [
                    AIMessage(
                        content="I'm sorry, I'm having trouble right now. Please try again in a moment or contact support directly."
                    )
                ],
                "resolved": False,
                "needs_escalation": True,
                "last_rag_context": "",
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
                out["escalation_reason"] = "low_faithfulness"
        return out

    _hitl = hitl_handler if hitl_handler is not None else get_hitl_handler(
        handler_name=getattr(config, "hitl_handler", "stub"),
        enabled=getattr(config, "hitl_enabled", True),
        email_to=getattr(config, "hitl_email_to", ""),
    )

    def escalate_node(state: dict[str, Any]) -> dict[str, Any]:
        """Handle escalation: call HITL (ticket/email) then return message to user."""
        messages = state.get("messages", [])
        last_human = next((m for m in reversed(messages) if hasattr(m, "type") and m.type == "human"), None)
        last_ai = next((m for m in reversed(messages) if hasattr(m, "type") and m.type == "ai"), None)
        reason = state.get("escalation_reason") or "agent_requested"
        ctx = EscalationContext(
            session_id=state.get("session_id", ""),
            user_id=state.get("user_id", ""),
            reason=reason,
            last_user_message=getattr(last_human, "content", None) if last_human else None,
            last_agent_message=getattr(last_ai, "content", None) if last_ai else None,
            metadata=state.get("metadata"),
        )
        try:
            _hitl.on_escalate(ctx)
        except Exception:
            pass
        return {
            "messages": [
                AIMessage(content="I'm connecting you with a human agent. Please hold.")
            ],
        }

    # Build graph: plan (when USE_PLANNING) → route → invoke_agent → aggregate → (optional) escalate
    builder = StateGraph(SupervisorState)

    builder.add_node("plan", plan_node)
    builder.add_node("route", route_node)
    builder.add_node("invoke_agent", invoke_agent_node)
    builder.add_node("aggregate", aggregate_node)
    builder.add_node("escalate", escalate_node)

    builder.set_entry_point("plan")
    builder.add_edge("plan", "route")
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
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> Any:
    """Build compiled supervisor graph with optional in-memory checkpointer and AgentOps circuit breaker."""
    graph = create_supervisor_graph(router=router, registry=registry, circuit_breaker=circuit_breaker)
    return graph.compile(checkpointer=MemorySaver() if use_checkpointer else None)
