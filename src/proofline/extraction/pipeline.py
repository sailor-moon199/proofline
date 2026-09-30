"""Structured extraction pipeline for document chunks."""

from __future__ import annotations

from typing import Any, Iterable

from proofline.extraction.verify import extract_step_json_from_chunk, merge_duplicate_steps, verify_step_evidence
from proofline.models.process_step import ProcessStep
from proofline.providers.base import LLMClient


def extract_steps_from_chunks(
    chunks: Iterable[str],
    *,
    client: LLMClient | None = None,
    schema: Any | None = None,
    prompt_version: str = "phase-4",
) -> list[ProcessStep]:
    """Convert text chunks into validated ProcessStep entries.

    If a client is supplied, the provider is asked to return JSON matching the schema.
    When no client is available, the function falls back to a deterministic heuristic
    payload so the pipeline remains functional in offline environments.
    """
    steps: list[ProcessStep] = []
    for index, chunk in enumerate(chunks):
        if client is not None:
            try:
                payload = client.extract_json(
                    f"Extract one operational process step from the text below. Return JSON keyed by process, actor, task, evidence, and quantities.\n\n{chunk}",
                    schema=schema,
                    prompt_version=prompt_version,
                )
                if isinstance(payload, dict):
                    if "step_id" not in payload:
                        payload["step_id"] = f"step-{index + 1}"
                    step = ProcessStep.model_validate(payload)
                    steps.append(step)
                    continue
            except Exception:
                pass
        payload = extract_step_json_from_chunk(chunk, fallback_step_id=f"step-{index + 1}")
        steps.append(ProcessStep.model_validate(payload))
    return merge_duplicate_steps(steps)


def verify_evidence_for_steps(steps: Iterable[ProcessStep]) -> list[ProcessStep]:
    """Recompute evidence verification state using the source-text normalization rules."""
    return [verify_step_evidence(step) for step in steps]
