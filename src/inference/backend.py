"""Inference backend abstraction for main LLM calls.

- OpenAIBackend: uses OpenAI API via langchain_openai.ChatOpenAI.
- SelfHostedBackend: uses an OpenAI-compatible HTTP API (e.g. vLLM, TensorRT-LLM)
  by pointing ChatOpenAI at base_url=INFERENCE_URL. Set INFERENCE_BACKEND=self_hosted
  and INFERENCE_URL=http://your-server:8000 to use it.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from langchain_openai import ChatOpenAI

from ..config import config


class LlmBackend(ABC):
    """Abstract backend for LLM inference."""

    @abstractmethod
    def create_tool_llm(
        self,
        model: str,
        tools: Sequence[Any],
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        """Return an object with .invoke(messages) that can use LangChain tools."""

    @abstractmethod
    def create_text_llm(
        self,
        model: str,
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        """Return an object with .invoke(messages) that takes/returns plain messages."""


class OpenAIBackend(LlmBackend):
    """Default backend using OpenAI's ChatCompletion via langchain_openai."""

    def create_tool_llm(
        self,
        model: str,
        tools: Sequence[Any],
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        llm = ChatOpenAI(model=model, temperature=temperature, top_p=top_p)
        return llm.bind_tools(list(tools))

    def create_text_llm(
        self,
        model: str,
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        return ChatOpenAI(model=model, temperature=temperature, top_p=top_p)


class SelfHostedBackend(LlmBackend):
    """Self-hosted inference via an OpenAI-compatible API (vLLM, TensorRT-LLM, etc.).

    Requires INFERENCE_URL (e.g. http://vllm:8000). Requests go to
    {base_url}/v1/chat/completions. Use INFERENCE_API_KEY if your server expects one.
    """

    def __init__(self, api_url: str | None = None, api_key: str | None = None) -> None:
        self.api_url = (api_url or getattr(config, "inference_url", "") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else getattr(config, "inference_api_key", "dummy")
        if not self.api_url:
            raise ValueError(
                "Self-hosted inference requires INFERENCE_URL (e.g. http://vllm:8000). "
                "Set it in env or use INFERENCE_BACKEND=openai."
            )
        self.base_url = f"{self.api_url}/v1"

    def _chat_openai(self, model: str, *, temperature: float, top_p: float) -> Any:
        return ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
        )

    def create_tool_llm(
        self,
        model: str,
        tools: Sequence[Any],
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        llm = self._chat_openai(model=model, temperature=temperature, top_p=top_p)
        return llm.bind_tools(list(tools))

    def create_text_llm(
        self,
        model: str,
        *,
        temperature: float,
        top_p: float,
    ) -> Any:
        return self._chat_openai(model=model, temperature=temperature, top_p=top_p)


_backend_singleton: LlmBackend | None = None


def get_llm_backend() -> LlmBackend:
    """Return a singleton LlmBackend based on config.inference_backend."""
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton

    backend_name = getattr(config, "inference_backend", "openai") or "openai"
    backend_name = backend_name.strip().lower()

    if backend_name == "openai":
        _backend_singleton = OpenAIBackend()
    elif backend_name in ("self_hosted", "self-hosted", "local"):
        _backend_singleton = SelfHostedBackend()
    else:
        # Fallback to OpenAI but make the choice explicit
        _backend_singleton = OpenAIBackend()
    return _backend_singleton

