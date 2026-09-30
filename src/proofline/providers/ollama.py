"""Local Ollama provider."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import request, error

from proofline.providers.base import BaseProvider, ProviderConfig, UsageRecord


class OllamaProvider(BaseProvider):
    """Send prompt payloads to the local Ollama API when the service is running."""

    provider_name = "ollama"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _complete_raw(self, prompt: str) -> Any:
        payload = json.dumps({"model": self.model_name, "prompt": prompt, "stream": False}).encode("utf-8")
        url = f"{self.base_url.rstrip('/')}/api/generate"
        req = request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with request.urlopen(req, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:  # pragma: no cover - requires live local server
            raise RuntimeError("Ollama is not running or is not reachable at the configured base URL.") from exc

    def _usage_from_response(self, raw_response: Any) -> UsageRecord | None:
        usage = raw_response.get("usage") if isinstance(raw_response, dict) else None
        if not usage:
            return None
        data = {
            "input_tokens": usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            "output_tokens": usage.get("completion_tokens") if isinstance(usage, dict) else None,
            "total_tokens": usage.get("total_tokens") if isinstance(usage, dict) else None,
        }
        return UsageRecord.model_validate({k: v for k, v in data.items() if v is not None}) if any(v is not None for v in data.values()) else None

    def complete(self, prompt: str, *, prompt_version: str | None = None) -> str:
        response = self._execute_with_retry(lambda: self._complete_raw(prompt))
        data = response if isinstance(response, dict) else {"response": str(response)}
        return str(data.get("response", ""))
