"""Configuration for the agentic framework."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """App configuration from environment."""
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    default_model: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    hallucination_threshold_faithfulness: float = float(os.getenv("HALLUCINATION_THRESHOLD_FAITHFULNESS", "0.8"))
    hallucination_threshold_confidence: float = float(os.getenv("HALLUCINATION_THRESHOLD_CONFIDENCE", "0.7"))
    weaviate_url: str = os.getenv("WEAVIATE_URL", "")
    weaviate_index: str = os.getenv("WEAVIATE_INDEX", "RAGChunks")
    # top_p: nucleus sampling; lower values = more focused, fewer hallucinations. 0.9 for factual support/billing.
    top_p: float = float(os.getenv("TOP_P", "0.9"))
    # Guardrails: enable input/output filtering (block off-topic, policy-violating content).
    guardrails_enabled: bool = os.getenv("GUARDRAILS_ENABLED", "true").lower() in ("true", "1", "yes")
    # Intent router: use TensorFlow classifier instead of keyword stub.
    use_tf_intent: bool = os.getenv("USE_TF_INTENT", "false").lower() in ("true", "1", "yes")
    tf_intent_model_path: str = os.getenv("TF_INTENT_MODEL_PATH", "")
    # Faithfulness scoring: use TensorFlow-trained model instead of LLM (recommended for production).
    use_tf_faithfulness: bool = os.getenv("USE_TF_FAITHFULNESS", "false").lower() in ("true", "1", "yes")
    tf_faithfulness_model_path: str = os.getenv("TF_FAITHFULNESS_MODEL_PATH", "")

    # AgentOps: circuit breaker and failover
    agent_ops_enabled: bool = os.getenv("AGENT_OPS_ENABLED", "true").lower() in ("true", "1", "yes")
    circuit_breaker_failure_threshold: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3"))
    circuit_breaker_cooldown_seconds: float = float(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60"))
    failover_enabled: bool = os.getenv("FAILOVER_ENABLED", "true").lower() in ("true", "1", "yes")
    failover_fallback_agent_id: str = os.getenv("FAILOVER_FALLBACK_AGENT_ID", "support")
    agent_invocation_timeout_seconds: float = float(os.getenv("AGENT_INVOCATION_TIMEOUT_SECONDS", "30"))

    # Optional agent patterns: Planning (supervisor), ReAct (agents)
    use_planning: bool = os.getenv("USE_PLANNING", "false").lower() in ("true", "1", "yes")
    use_react: bool = os.getenv("USE_REACT", "false").lower() in ("true", "1", "yes")
    react_max_steps: int = int(os.getenv("REACT_MAX_STEPS", "10"))


config = Config()
