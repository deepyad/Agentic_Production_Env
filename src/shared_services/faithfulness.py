"""Faithfulness scoring: rate how much agent response is supported by RAG context. TensorFlow-based trained model."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class FaithfulnessScorer(ABC):
    """Interface for scoring response vs context (0–1). Production: trained model, not LLM."""

    @abstractmethod
    def score(self, response: str, context: str) -> float:
        """Return faithfulness score in [0, 1]; higher = more grounded in context."""
        pass


class StubFaithfulnessScorer(FaithfulnessScorer):
    """Always returns 1.0 (no escalation from score)."""

    def score(self, response: str, context: str) -> float:
        return 1.0


class TFFaithfulnessScorer(FaithfulnessScorer):
    """
    TensorFlow-based faithfulness scorer. Input: (response, context); output: float 0–1.
    If model_path exists, loads it; else trains from synthetic (response, context, label) data and saves.
    Falls back to StubFaithfulnessScorer if TensorFlow unavailable.
    """

    _DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / ".faithfulness_model"
    _MAX_LEN = 512  # combined text length (chars)
    _VOCAB_SIZE = 3000
    _EMBED_DIM = 32
    _EPOCHS = 10

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or str(self._DEFAULT_MODEL_DIR / "model.keras")
        self._model = None
        self._fallback = StubFaithfulnessScorer()

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

        texts, labels = self._synthetic_data()
        if not texts:
            return None

        self._vectorize = keras.layers.TextVectorization(
            max_tokens=self._VOCAB_SIZE,
            output_sequence_length=128,
            output_mode="int",
        )
        self._vectorize.adapt(texts)

        model = keras.Sequential([
            keras.Input(shape=(1,), dtype=tf.string),
            self._vectorize,
            keras.layers.Embedding(self._VOCAB_SIZE + 1, self._EMBED_DIM),
            keras.layers.GlobalAveragePooling1D(),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(1, activation="sigmoid"),
        ])
        model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])

        model.fit(
            tf.constant(texts),
            tf.constant(labels, dtype=tf.float32),
            epochs=self._EPOCHS,
            verbose=0,
        )
        self._model = model
        os.makedirs(os.path.dirname(path), exist_ok=True)
        model.save(path)
        return self._model

    def _synthetic_data(self) -> tuple[list[str], list[float]]:
        """Synthetic (response, context) pairs: faithful (1) vs unfaithful (0)."""
        texts: list[str] = []
        labels: list[float] = []
        # Faithful: response consistent with or contained in context
        faithful_pairs = [
            ("The invoice total is $100.", "The invoice total is $100. Due in 30 days."),
            ("Your refund was processed.", "Your refund was processed. Allow 5-7 days."),
            ("Yes, that is correct.", "The account shows a credit of $50."),
            ("According to the doc, the limit is 10.", "According to the doc, the limit is 10."),
            ("I found that in the FAQ.", "I found that in the FAQ. See section 2."),
        ]
        for resp, ctx in faithful_pairs:
            texts.append(self._format_input(resp, ctx))
            labels.append(1.0)
        # More faithful by repeating/paraphrasing
        for _ in range(20):
            ctx = "The answer is 42. Please confirm."
            texts.append(self._format_input("The answer is 42.", ctx))
            labels.append(1.0)
        for _ in range(20):
            ctx = "Refund policy: 30 days. No exceptions."
            texts.append(self._format_input("Refunds are allowed within 30 days.", ctx))
            labels.append(1.0)
        # Unfaithful: response contradicts or invents
        unfaithful_pairs = [
            ("The invoice total is $999.", "The invoice total is $100."),
            ("Your refund was denied.", "Your refund was processed."),
            ("The limit is 99.", "The limit is 10."),
            ("I don't have that information.", "The answer is in the doc: 42."),
            ("The price is $50.", "The document does not mention price."),
        ]
        for resp, ctx in unfaithful_pairs:
            texts.append(self._format_input(resp, ctx))
            labels.append(0.0)
        for _ in range(30):
            texts.append(self._format_input("Random claim 12345.", "Unrelated context here."))
            labels.append(0.0)
        return texts, labels

    @staticmethod
    def _format_input(response: str, context: str) -> str:
        """Single string input for the model (concat response + context)."""
        r = (response or "").strip()[:500]
        c = (context or "").strip()[:500]
        return f"[RESPONSE] {r} [CONTEXT] {c}"

    def score(self, response: str, context: str) -> float:
        try:
            model = self._get_model()
        except Exception:
            return self._fallback.score(response, context)
        if model is None:
            return self._fallback.score(response, context)

        import tensorflow as tf

        inp = self._format_input(response, context)
        pred = model.predict(tf.constant([inp]), verbose=0)[0][0]
        return float(pred)
