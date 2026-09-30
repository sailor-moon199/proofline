"""Factory helpers to resolve the configured provider implementation."""

from __future__ import annotations

import os

from proofline.providers.base import BaseProvider, ProviderConfig
from proofline.providers.claude import ClaudeProvider
from proofline.providers.gemini import GeminiProvider
from proofline.providers.ollama import OllamaProvider


def get_llm_client(
    *,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str = "default",
) -> BaseProvider:
    """Return the selected provider implementation without hardcoded model names."""
    selected_provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    config = ProviderConfig.from_environment(
        provider=selected_provider,
        model=model,
        prompt_version=prompt_version,
    )
    if selected_provider == "gemini":
        return GeminiProvider(config)
    if selected_provider == "claude":
        return ClaudeProvider(config)
    if selected_provider == "ollama":
        return OllamaProvider(config)
    raise ValueError(f"Unsupported LLM provider: {selected_provider!r}")
