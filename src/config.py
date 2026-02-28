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

    # Inference backend: which implementation handles main LLM calls.
    # "openai" (default) = OpenAI API; "self_hosted" = OpenAI-compatible server (vLLM, TensorRT-LLM, etc.).
    inference_backend: str = os.getenv("INFERENCE_BACKEND", "openai").strip().lower()
    # When inference_backend is self_hosted: base URL of the inference server (e.g. http://vllm:8000).
    # Chat completions are called at {inference_url}/v1/chat/completions.
    inference_url: str = os.getenv("INFERENCE_URL", "").strip()
    # Optional API key for self-hosted server (many accept any value; use "dummy" if not required).
    inference_api_key: str = os.getenv("INFERENCE_API_KEY", "dummy").strip()

    # Human-in-the-loop (HITL): when we escalate, create ticket / notify
    hitl_enabled: bool = os.getenv("HITL_ENABLED", "true").lower() in ("true", "1", "yes")
    hitl_handler: str = os.getenv("HITL_HANDLER", "ticket").strip().lower() or "stub"  # stub | ticket | email
    hitl_email_to: str = os.getenv("HITL_EMAIL_TO", "").strip()

    # LangGraph checkpointer: Redis for production (reduces pod memory, survives restarts). Empty = in-memory.
    redis_url: str = os.getenv("REDIS_URL", "").strip()
    # Session checkpoint TTL in minutes (e.g. 1440 = 24h). Only used when redis_url is set. 0 = no expiry.

    # Langfuse: classic observability (traces, spans, faithfulness score). Enable when keys are set.
    langfuse_enabled: bool = bool(os.getenv("LANGFUSE_SECRET_KEY", "").strip())
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    langfuse_base_url: str = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com").strip()


config = Config()
