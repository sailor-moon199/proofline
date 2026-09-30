"""Gemini provider implementation."""

from __future__ import annotations

import json
import os
from typing import Any

from proofline.providers.base import BaseProvider, ProviderConfig, UsageRecord


class GeminiProvider(BaseProvider):
    """Wrap the official Gemini SDK if it is installed in the runtime."""

    provider_name = "gemini"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            self.api_key = ""

    def _complete_raw(self, prompt: str) -> Any:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - depends on installed SDK
            raise RuntimeError(
                "Gemini support requires the official google-genai package. Install it in the environment to use Gemini."
            ) from exc

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured in the environment.")

        client = genai.Client(api_key=self.api_key)
        response = self._execute_with_retry(
            lambda: client.models.generate_content(model=self.model_name, contents=prompt)
        )
        return response

    def _usage_from_response(self, raw_response: Any) -> UsageRecord | None:
        usage = getattr(raw_response, "usage_metadata", None)
        if usage is None:
            return None
        data = {
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        }
        return UsageRecord.model_validate({k: v for k, v in data.items() if v is not None}) if any(v is not None for v in data.values()) else None
