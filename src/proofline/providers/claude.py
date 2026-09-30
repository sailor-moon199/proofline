"""Anthropic Claude provider implementation."""

from __future__ import annotations

import os
from typing import Any

from proofline.providers.base import BaseProvider, ProviderConfig, UsageRecord


class ClaudeProvider(BaseProvider):
    """Wrap the Anthropic SDK for chat completions when available."""

    provider_name = "claude"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

    def _complete_raw(self, prompt: str) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - depends on installed SDK
            raise RuntimeError(
                "Claude support requires the official anthropic package. Install it in the environment to use Claude."
            ) from exc

        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured in the environment.")

        client = Anthropic(api_key=self.api_key)
        response = self._execute_with_retry(
            lambda: client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
        )
        return response

    def _usage_from_response(self, raw_response: Any) -> UsageRecord | None:
        usage = getattr(raw_response, "usage", None)
        if usage is None:
            return None
        data = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0),
        }
        return UsageRecord.model_validate({k: v for k, v in data.items() if v is not None}) if any(v is not None for v in data.values()) else None
