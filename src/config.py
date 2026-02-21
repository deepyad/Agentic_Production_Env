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


config = Config()
