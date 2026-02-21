"""Guardrail layer: block off-topic or policy-violating content in agent input/output."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool
    filtered_text: str
    reason: Optional[str] = None


class GuardrailService(ABC):
    """Interface for input/output guardrails. Production: guardrails-ai or custom rules."""

    @abstractmethod
    def guard_input(self, text: str) -> GuardrailResult:
        """Check user input; block toxic/off-topic content. Returns (passed, filtered_text)."""
        pass

    @abstractmethod
    def guard_output(self, text: str) -> GuardrailResult:
        """Validate/filter agent output; block policy-violating content."""
        pass


class StubGuardrailService(GuardrailService):
    """No-op: passes all input and output."""

    def guard_input(self, text: str) -> GuardrailResult:
        return GuardrailResult(passed=True, filtered_text=text)

    def guard_output(self, text: str) -> GuardrailResult:
        return GuardrailResult(passed=True, filtered_text=text)


class SimpleGuardrailService(GuardrailService):
    """
    Lightweight guardrails: keyword-based input blocking, output filtering.
    Blocks toxic/off-topic input; filters policy-violating output.
    """

    # Block user input containing these (case-insensitive)
    _INPUT_BLOCK_PATTERNS: set[str] = frozenset({
        "hack", "exploit", "ddos", "password crack", "credential steal",
    })

    # Filter/replace these in agent output if present (case-insensitive)
    _OUTPUT_BLOCK_PATTERNS: set[str] = frozenset({
        "internal api key", "secret token", "admin password",
    })

    # Max chars for agent output
    _MAX_OUTPUT_LEN: int = 4000

    def guard_input(self, text: str) -> GuardrailResult:
        """Block user input that looks off-topic or policy-violating."""
        if not text or not text.strip():
            return GuardrailResult(passed=False, filtered_text="", reason="empty")
        lower = text.lower()
        for pat in self._INPUT_BLOCK_PATTERNS:
            if pat in lower:
                return GuardrailResult(
                    passed=False,
                    filtered_text=text,
                    reason=f"input_blocked:{pat}",
                )
        return GuardrailResult(passed=True, filtered_text=text)

    def guard_output(self, text: str) -> GuardrailResult:
        """Filter agent output: truncate, block policy-violating phrases."""
        if not text:
            return GuardrailResult(passed=True, filtered_text="")
        filtered = text
        lower = filtered.lower()
        for pat in self._OUTPUT_BLOCK_PATTERNS:
            if pat in lower:
                # Replace blocked phrase with placeholder
                idx = lower.find(pat)
                filtered = filtered[:idx] + "[content removed]" + filtered[idx + len(pat):]
                lower = filtered.lower()
        if len(filtered) > self._MAX_OUTPUT_LEN:
            filtered = filtered[: self._MAX_OUTPUT_LEN] + "\n[...truncated]"
        return GuardrailResult(passed=True, filtered_text=filtered)
