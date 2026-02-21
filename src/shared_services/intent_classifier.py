"""Intent classification for router: keyword-based or TensorFlow-based."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path

# Intent labels in fixed order (support = default index 0)
INTENT_LABELS: list[str] = ["support", "billing", "tech", "escalation"]

# Same as router: (keywords,) -> agent_id
INTENT_MAP: list[tuple[tuple[str, ...], str]] = [
    (("invoice", "bill", "payment", "refund", "billing"), "billing"),
    (("tech", "error", "bug", "install", "troubleshoot"), "tech"),
    (("human", "agent", "escalate", "speak to someone"), "escalation"),
]


class IntentClassifier(ABC):
    """Interface for intent classification. Returns suggested agent pool IDs."""

    @abstractmethod
    def classify(self, message: str) -> list[str]:
        """Return suggested agent pool IDs for the message (e.g. ['billing'], ['support'])."""
        pass


class KeywordIntentClassifier(IntentClassifier):
    """Keyword-based intent (current stub behavior). No TensorFlow."""

    def classify(self, message: str) -> list[str]:
        msg_lower = message.lower()
        suggested: list[str] = []
        for keywords, agent_id in INTENT_MAP:
            if any(kw in msg_lower for kw in keywords):
                suggested.append(agent_id)
        if not suggested:
            suggested = ["support"]
        return suggested


class TFIntentClassifier(IntentClassifier):
    """
    TensorFlow-based intent classifier. Uses a small Keras model (TextVectorization + Embedding + Dense).
    If model_path is provided and exists, loads it; otherwise trains from INTENT_MAP synthetic data
    and saves to default path. Requires tensorflow. Falls back to KeywordIntentClassifier if TF unavailable.
    """

    _DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / ".intent_model"
    _MAX_SEQ_LEN = 32
    _VOCAB_SIZE = 2000
    _EMBED_DIM = 32
    _EPOCHS = 8

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or str(self._DEFAULT_MODEL_DIR / "model.keras")
        self._model = None
        self._vectorize = None
        self._fallback = KeywordIntentClassifier()

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            import tensorflow as tf  # noqa: F401
            from tensorflow import keras
        except ImportError:
            return None

        path = self.model_path
        if path and os.path.isfile(path):
            self._model = keras.models.load_model(path)
            return self._model

        # Build and train from synthetic data
        texts, labels = self._synthetic_data()
        if not texts:
            # Fallback to keyword behavior if no data
            return None

        # TextVectorization
        self._vectorize = keras.layers.TextVectorization(
            max_tokens=self._VOCAB_SIZE,
            output_sequence_length=self._MAX_SEQ_LEN,
            output_mode="int",
        )
        self._vectorize.adapt(texts)

        # Model
        model = keras.Sequential([
            keras.Input(shape=(1,), dtype=tf.string),
            self._vectorize,
            keras.layers.Embedding(self._VOCAB_SIZE + 1, self._EMBED_DIM),
            keras.layers.GlobalAveragePooling1D(),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(len(INTENT_LABELS), activation="softmax"),
        ])
        model.compile(
            optimizer="adam",
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

        label_indices = [INTENT_LABELS.index(l) for l in labels]
        model.fit(
            tf.constant(texts),
            tf.constant(label_indices),
            epochs=self._EPOCHS,
            verbose=0,
        )

        self._model = model
        os.makedirs(os.path.dirname(path), exist_ok=True)
        model.save(path)
        return self._model

    def _synthetic_data(self) -> tuple[list[str], list[str]]:
        """Generate synthetic (text, intent) from INTENT_MAP for training."""
        texts: list[str] = []
        labels: list[str] = []
        for keywords, agent_id in INTENT_MAP:
            for kw in keywords:
                texts.append(kw)
                labels.append(agent_id)
            # Add a short phrase per intent
            phrase = " ".join(keywords[:2])
            texts.append(phrase)
            labels.append(agent_id)
        # Default/support examples
        for _ in range(6):
            texts.append("help")
            labels.append("support")
        texts.append("hello")
        labels.append("support")
        return texts, labels

    def classify(self, message: str) -> list[str]:
        try:
            model = self._get_model()
        except Exception:
            return self._fallback.classify(message)
        if model is None:
            return self._fallback.classify(message)

        import tensorflow as tf

        msg = message.strip() or "help"
        pred = model.predict(tf.constant([msg]), verbose=0)[0]
        idx = int(pred.argmax())
        confidence = float(pred[idx])
        # Return single best intent; if low confidence, default support
        if confidence < 0.5:
            return ["support"]
        return [INTENT_LABELS[idx]]
