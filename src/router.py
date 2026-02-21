"""Session Router: intent classification → suggested agent pool IDs. Keyword, TensorFlow, or Weaviate."""
import uuid
from dataclasses import dataclass
from typing import Optional

from .config import config
from .shared_services.intent_classifier import (
    IntentClassifier,
    KeywordIntentClassifier,
    TFIntentClassifier,
)


@dataclass
class RouterResult:
    """Output of session router."""
    session_id: str
    suggested_agent_pool_ids: list[str]
    embedding_cache_key: Optional[str] = None


class SessionRouter:
    """
    Routes user message to suggested agent pools via intent.
    Uses KeywordIntentClassifier (default) or TFIntentClassifier (USE_TF_INTENT=true).
    Production alternative: embed → Weaviate query.
    """

    def __init__(self, intent_classifier: Optional[IntentClassifier] = None) -> None:
        if intent_classifier is not None:
            self._classifier = intent_classifier
        elif config.use_tf_intent:
            self._classifier = TFIntentClassifier(model_path=config.tf_intent_model_path or None)
        else:
            self._classifier = KeywordIntentClassifier()

    def route(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
    ) -> RouterResult:
        """
        Classify intent and return suggested agent pool IDs.
        Delegates to IntentClassifier (keyword or TensorFlow).
        """
        sid = session_id or str(uuid.uuid4())
        suggested = self._classifier.classify(message)
        return RouterResult(
            session_id=sid,
            suggested_agent_pool_ids=suggested,
            embedding_cache_key=f"emb_{hash(message) % 10**8}",
        )
