"""AgentOps health: aggregate status for /health endpoint."""
from typing import Any, Optional

from .circuit_breaker import CircuitBreaker, CircuitState


def get_agent_ops_health(
    circuit_breaker: Optional[CircuitBreaker] = None,
    agent_ids: Optional[list[str]] = None,
    mcp_available: bool = True,
) -> dict[str, Any]:
    """
    Build health payload for AgentOps: agent circuit states and optional MCP status.
    Returns {"status": "ok"|"degraded", "agents": {agent_id: "healthy"|"circuit_open"|"half_open"}, "mcp": "ok"|"unavailable"}.
    """
    status = "ok"
    agents: dict[str, str] = {}
    if circuit_breaker and agent_ids:
        for aid in agent_ids:
            state = circuit_breaker.get_state(aid)
            if state == CircuitState.OPEN:
                agents[aid] = "circuit_open"
                status = "degraded"
            elif state == CircuitState.HALF_OPEN:
                agents[aid] = "half_open"
                status = "degraded"
            else:
                agents[aid] = "healthy"
    elif agent_ids:
        for aid in agent_ids:
            agents[aid] = "healthy"

    out: dict[str, Any] = {
        "status": status,
        "agents": agents,
    }
    if mcp_available is not None:
        out["mcp"] = "ok" if mcp_available else "unavailable"
        if not mcp_available:
            out["status"] = "degraded"
    return out
