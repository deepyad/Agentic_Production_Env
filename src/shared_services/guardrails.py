"""Guardrail layer: block off-topic, policy-violating, or prompt-injection content in agent input/output."""
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
    Blocks toxic/off-topic input, prompt-injection attempts, and policy-violating output.
    """

    # Block user input containing these (case-insensitive) — toxic / unlawful intent
    _INPUT_BLOCK_PATTERNS: set[str] = frozenset({
        "hack", "exploit", "ddos", "password crack", "credential steal",
    })

    # Prompt-injection / jailbreak: user trying to override agent instructions (case-insensitive substrings)
    _INJECTION_PATTERNS: set[str] = frozenset({
        "ignore previous instructions",
        "ignore all previous",
        "disregard your instructions",
        "you are now",
        "new instructions:",
        "system prompt",
        "developer mode",
        "jailbreak",
        "bypass your",
        "pretend you are",
        "act as if",
        "forget everything",
        "output your instructions",
        "repeat the above",
        "ignore the above",
        "override",
        "disregard safety",
        "no longer bound",
        "from now on you",
    })

    # Filter/replace these in agent output if present (case-insensitive)
    _OUTPUT_BLOCK_PATTERNS: set[str] = frozenset({
        "internal api key", "secret token", "admin password",
    })

    # Max chars for agent output
    _MAX_OUTPUT_LEN: int = 4000

    def guard_input(self, text: str) -> GuardrailResult:
        """Block user input that looks off-topic, policy-violating, or like prompt injection."""
        if not text or not text.strip():
            return GuardrailResult(passed=False, filtered_text="", reason="empty")
        lower = text.lower()
        # Unlawful / toxic intent
        for pat in self._INPUT_BLOCK_PATTERNS:
            if pat in lower:
                return GuardrailResult(
                    passed=False,
                    filtered_text=text,
                    reason=f"input_blocked:{pat}",
                )
        # Prompt-injection / jailbreak attempts (avoid user overriding agent to do unlawful things)
        for pat in self._INJECTION_PATTERNS:
            if pat in lower:
                return GuardrailResult(
                    passed=False,
                    filtered_text=text,
                    reason=f"injection_blocked:{pat}",
                )
        # Optional: reject very long input that could hide injected instructions
        if len(text) > 8000:
            return GuardrailResult(passed=False, filtered_text=text, reason="input_too_long")
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
