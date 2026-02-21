"""Circuit breaker for agent pools: avoid repeatedly calling failing agents."""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    """Circuit state: closed = normal, open = failing, half_open = probing."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _AgentCircuit:
    """Per-agent circuit state."""
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """
    Per-agent circuit breaker. After threshold consecutive failures, the circuit
    opens and the agent is skipped until cooldown expires (then half_open; one
    success closes it, one failure re-opens).
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1.0, cooldown_seconds)
        self._circuits: dict[str, _AgentCircuit] = {}

    def _get_circuit(self, agent_id: str) -> _AgentCircuit:
        if agent_id not in self._circuits:
            self._circuits[agent_id] = _AgentCircuit()
        return self._circuits[agent_id]

    def _maybe_transition_from_open(self, agent_id: str) -> None:
        c = self._get_circuit(agent_id)
        if c.state != CircuitState.OPEN:
            return
        if time.monotonic() - c.last_failure_time >= self.cooldown_seconds:
            c.state = CircuitState.HALF_OPEN
            c.failure_count = 0

    def record_success(self, agent_id: str) -> None:
        """Record a successful invocation; closes the circuit."""
        c = self._get_circuit(agent_id)
        c.failure_count = 0
        c.state = CircuitState.CLOSED

    def record_failure(self, agent_id: str) -> None:
        """Record a failed invocation; may open the circuit."""
        c = self._get_circuit(agent_id)
        c.last_failure_time = time.monotonic()
        c.failure_count += 1
        if c.state == CircuitState.HALF_OPEN:
            c.state = CircuitState.OPEN
        elif c.failure_count >= self.failure_threshold:
            c.state = CircuitState.OPEN

    def is_available(self, agent_id: str) -> bool:
        """
        Return True if the agent may be invoked (circuit closed or half_open).
        Updates open → half_open when cooldown has elapsed.
        """
        self._maybe_transition_from_open(agent_id)
        c = self._get_circuit(agent_id)
        return c.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def get_state(self, agent_id: str) -> CircuitState:
        """Return current circuit state for the agent."""
        self._maybe_transition_from_open(agent_id)
        return self._get_circuit(agent_id).state

    def get_status(self, agent_id: str) -> dict:
        """Return status dict for health/reporting: state, failure_count, last_failure_time."""
        self._maybe_transition_from_open(agent_id)
        c = self._get_circuit(agent_id)
        return {
            "state": c.state.value,
            "failure_count": c.failure_count,
            "last_failure_time": c.last_failure_time,
        }

    def get_all_agent_ids(self) -> list[str]:
        """Return all agent IDs that have been seen (have a circuit)."""
        return list(self._circuits.keys())
