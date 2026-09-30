"""Shared interfaces and helpers for LLM provider clients."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from pydantic import BaseModel, ConfigDict

from proofline.providers.cache import DiskCache

JSONValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None


class LLMClient(Protocol):
    """A minimal protocol for LLM text generation and structured extraction."""

    def complete(self, prompt: str, *, prompt_version: str | None = None) -> str:
        """Return a free-form completion for the supplied prompt."""

    def extract_json(
        self,
        prompt: str,
        schema: Any | None = None,
        *,
        prompt_version: str | None = None,
    ) -> Any:
        """Return a JSON-compatible object validated against an optional schema."""


class UsageRecord(BaseModel):
    """Capture token usage when the provider reports it."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cache_tokens: int | None = None


class ProviderConfig:
    """Configuration surfaced through environment and optional explicit override."""

    def __init__(
        self,
        *,
        provider: str,
        model: str | None = None,
        prompt_version: str = "default",
        cache_dir: str | Path | None = None,
        minimum_delay_seconds: float | None = None,
        max_retries: int | None = None,
        backoff_seconds: float | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.model = model.strip() if model else None
        self.prompt_version = prompt_version
        self.cache_dir = Path(cache_dir or os.getenv("LLM_CACHE_DIR", ".llm_cache"))
        self.minimum_delay_seconds = (
            float(minimum_delay_seconds)
            if minimum_delay_seconds is not None
            else float(os.getenv("LLM_MIN_DELAY_SECONDS", "0") or 0)
        )
        self.max_retries = (
            int(max_retries) if max_retries is not None else int(os.getenv("LLM_MAX_RETRIES", "3") or 3)
        )
        self.backoff_seconds = (
            float(backoff_seconds)
            if backoff_seconds is not None
            else float(os.getenv("LLM_BACKOFF_SECONDS", "1.0") or 1.0)
        )

    @classmethod
    def from_environment(
        cls,
        *,
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str = "default",
    ) -> "ProviderConfig":
        """Build configuration from the running environment without defaults for model names."""
        selected_provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
        selected_model = model or os.getenv("LLM_MODEL")
        return cls(
            provider=selected_provider,
            model=selected_model,
            prompt_version=prompt_version,
        )


class BaseProvider(ABC):
    """Abstract provider implementation with retry, cache, rate-limit, and schema parsing helpers."""

    provider_name = "base"

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self.config = config or ProviderConfig.from_environment(provider=self.provider_name)
        self.cache = DiskCache(self.config.cache_dir / self.config.provider)
        self._last_call_at = 0.0

    @property
    def model_name(self) -> str:
        """Return the configured model name or raise a clear error when unset."""
        if not self.config.model:
            raise ValueError(
                "LLM_MODEL is not configured. Set it in the environment before calling a provider."
            )
        return self.config.model

    @abstractmethod
    def _complete_raw(self, prompt: str) -> Any:
        """Execute the underlying provider call and return raw response data."""

    @abstractmethod
    def _usage_from_response(self, raw_response: Any) -> UsageRecord | None:
        """Extract token usage when the provider reports it."""

    def complete(self, prompt: str, *, prompt_version: str | None = None) -> str:
        """Return completion text and reuse a cached result when it is available."""
        resolved_version = prompt_version or self.config.prompt_version
        key = self._cache_key(prompt=prompt, schema=None, output_kind="complete", prompt_version=resolved_version)
        cached = self.cache.get(key)
        if cached is not None:
            if isinstance(cached, dict) and "content" in cached:
                return str(cached["content"])
            return str(cached)

        result = self._execute_with_retry(lambda: self._complete_raw(prompt))
        content = self._text_from_response(result)
        usage = self._usage_from_response(result)
        payload = {
            "content": content,
            "provider": self.config.provider,
            "model": self.model_name,
            "usage": usage.model_dump(mode="json") if usage else None,
        }
        self.cache.set(key, payload)
        return content

    def extract_json(
        self,
        prompt: str,
        schema: Any | None = None,
        *,
        prompt_version: str | None = None,
    ) -> Any:
        """Return JSON payload parsed from the provider response and validate it if possible."""
        resolved_version = prompt_version or self.config.prompt_version
        key = self._cache_key(prompt=prompt, schema=schema, output_kind="json", prompt_version=resolved_version)
        cached = self.cache.get(key)
        if cached is not None:
            return self._restore_cached_json(cached, schema)

        text = self.complete(prompt, prompt_version=resolved_version)
        data = _extract_json_payload(text)
        if schema is not None and hasattr(schema, "model_validate"):
            validated = schema.model_validate(data)
        else:
            validated = data
        self.cache.set(
            key,
            {"data": validated.model_dump(mode="json") if hasattr(validated, "model_dump") else validated},
        )
        return validated

    def _execute_with_retry(self, call: Any) -> Any:
        """Honor a minimum delay and retry rate-limited requests with exponential backoff."""
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            self._enforce_min_delay()
            try:
                result = call()
                self._last_call_at = time.monotonic()
                return result
            except Exception as exc:  # pragma: no cover - exercised by provider-specific tests
                last_error = exc
                self._last_call_at = time.monotonic()
                text = str(exc).lower()
                if "429" not in text and "rate limit" not in text and "too many requests" not in text:
                    raise
                if attempt >= self.config.max_retries:
                    raise RuntimeError(f"rate limit exceeded for {self.config.provider}") from exc
                time.sleep(self.config.backoff_seconds * (2**attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"provider call for {self.config.provider} failed without a result")

    def _enforce_min_delay(self) -> None:
        """Prevent provider calls from exceeding any configured minimum gap."""
        if self.config.minimum_delay_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_call_at
        if elapsed < self.config.minimum_delay_seconds:
            time.sleep(self.config.minimum_delay_seconds - elapsed)

    def _cache_key(
        self,
        *,
        prompt: str,
        schema: Any | None,
        output_kind: str,
        prompt_version: str,
    ) -> str:
        """Create a stable, provider-specific hash."""
        payload = {
            "provider": self.config.provider,
            "model": self.model_name,
            "prompt_version": prompt_version,
            "output_kind": output_kind,
            "prompt": prompt,
            "schema": _schema_signature(schema),
        }
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _text_from_response(self, response: Any) -> str:
        """Normalize provider responses into plain text."""
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            for key in ("text", "content", "response"):
                value = response.get(key)
                if isinstance(value, str):
                    return value
                if isinstance(value, list):
                    parts = []
                    for element in value:
                        if isinstance(element, dict):
                            if "text" in element:
                                parts.append(str(element["text"]))
                            elif "content" in element:
                                parts.append(str(element["content"]))
                        else:
                            parts.append(str(element))
                    if parts:
                        return "".join(parts)
        if hasattr(response, "text"):
            return str(response.text)
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = []
                for item in content:
                    if hasattr(item, "text"):
                        texts.append(str(item.text))
                    elif isinstance(item, dict) and "text" in item:
                        texts.append(str(item["text"]))
                if texts:
                    return "".join(texts)
        return str(response)

    def _restore_cached_json(self, cached: Any, schema: Any | None) -> Any:
        """Return cached JSON data and revalidate it if a Pydantic schema is supplied."""
        data = cached.get("data") if isinstance(cached, dict) else cached
        if schema is not None and hasattr(schema, "model_validate"):
            return schema.model_validate(data)
        return data


def _schema_signature(schema: Any | None) -> str:
    """Return a stable representation of a schema for cache keys."""
    if schema is None:
        return "none"
    if hasattr(schema, "model_json_schema"):
        return json.dumps(schema.model_json_schema(), ensure_ascii=True, sort_keys=True)
    if isinstance(schema, dict):
        return json.dumps(schema, ensure_ascii=True, sort_keys=True)
    return str(schema)


def _extract_json_payload(text: str) -> Any:
    """Extract a JSON object or array from a provider response string."""
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if cleaned.startswith("{") or cleaned.startswith("["):
        return json.loads(cleaned)
    match = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("provider output was not valid JSON")


def print_provider_notice(provider: str | None = None, model: str | None = None) -> None:
    """Print the selected provider and model before a run without exposing secrets."""
    selected_provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    selected_model = model or os.getenv("LLM_MODEL")
    if selected_model:
        print(f"Info: provider {selected_provider} will process the input using model {selected_model}.")
    else:
        print(f"Info: provider {selected_provider} will process the input. Set LLM_MODEL before running.")
