"""Agent Registry: metadata store for agent capabilities. Production: DynamoDB."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    """Agent pool metadata."""
    agent_id: str
    capabilities: list[str]
    model: str
    max_concurrent: int = 500
    latency_p99_ms: Optional[int] = 1200


class AgentRegistry(ABC):
    """Interface for querying agents by capability."""

    @abstractmethod
    def get_agents_by_capability(self, capabilities: list[str]) -> list[AgentConfig]:
        """Return agents that support any of the given capabilities."""
        pass

    @abstractmethod
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent by ID."""
        pass


class InMemoryAgentRegistry(AgentRegistry):
    """In-memory registry with predefined support/billing/tech/escalation pools."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentConfig] = {
            "support": AgentConfig(
                agent_id="support",
                capabilities=["general", "support", "faq", "help"],
                model="gpt-4o-mini",
            ),
            "billing": AgentConfig(
                agent_id="billing",
                capabilities=["billing", "invoices", "payments", "refunds"],
                model="gpt-4o-mini",
            ),
            "tech": AgentConfig(
                agent_id="tech",
                capabilities=["tech", "technical", "troubleshooting"],
                model="gpt-4o-mini",
            ),
            "escalation": AgentConfig(
                agent_id="escalation",
                capabilities=["escalation", "human", "complex"],
                model="gpt-4o",
            ),
        }

    def get_agents_by_capability(self, capabilities: list[str]) -> list[AgentConfig]:
        cap_set = set(c.lower() for c in capabilities)
        return [
            a for a in self._agents.values()
            if any(c in cap_set for c in (c.lower() for c in a.capabilities))
        ]

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        return self._agents.get(agent_id)
