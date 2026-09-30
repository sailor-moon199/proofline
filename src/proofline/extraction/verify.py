"""Evidence validation, merging rules, and gap reporting."""

from __future__ import annotations

import re
from typing import Iterable

from proofline.models.process_step import ConflictValue, Evidence, ProcessStep, QuantityField, QuantityStatus


def normalize_text_for_evidence(value: str | None) -> str:
    """Collapse whitespace and normalize quote characters to compare source and quote text."""
    if value is None:
        return ""
    normalized = value.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def verify_quote_in_source(quote: str, source_text: str) -> bool:
    """Check that a candidate evidence quote appears in the source after normalization."""
    return normalize_text_for_evidence(quote) in normalize_text_for_evidence(source_text)


def verify_step_evidence(step: ProcessStep) -> ProcessStep:
    """Mark evidence entries as verified only when the exact quote appears in source text."""
    source_text = "\n".join(
        evidence.quote for evidence in step.evidence if evidence.quote
    )
    if not step.evidence:
        return step

    updated = []
    for evidence_entry in step.evidence:
        verified = verify_quote_in_source(evidence_entry.quote, source_text)
        updated.append(
            Evidence(
                document=evidence_entry.document,
                location=evidence_entry.location,
                quote=evidence_entry.quote,
                verified=verified,
            )
        )
    return step.model_copy(update={"evidence": updated})


def merge_duplicate_steps(steps: Iterable[ProcessStep]) -> list[ProcessStep]:
    """Merge steps that have the same process, task, and actor while preserving conflict evidence."""
    by_key: dict[tuple[str, str, str], ProcessStep] = {}
    for step in steps:
        key = (step.process.strip().lower(), step.task.strip().lower(), step.actor.strip().lower())
        if key in by_key:
            merged = by_key[key]
            merged_evidence = list(merged.evidence) + list(step.evidence)
            merged_conflicts = list(merged.conflicts) + list(step.conflicts)
            by_key[key] = merged.model_copy(update={"evidence": merged_evidence, "conflicts": merged_conflicts})
        else:
            by_key[key] = step
    return list(by_key.values())


def build_gap_report(steps: Iterable[ProcessStep]) -> list[str]:
    """Return a human-readable list of missing or vague numeric values and follow-up questions."""
    issues: list[str] = []
    for step in steps:
        for field_name, quantity in (
            ("frequency", step.frequency),
            ("minutes_per_run", step.minutes_per_run),
            ("people_doing_it", step.people_doing_it),
            ("error_rate", step.error_rate),
        ):
            if quantity.status is QuantityStatus.UNKNOWN:
                issues.append(f"{step.step_id}: {field_name} is unknown; ask for the source value or confirm it is not tracked.")
            elif quantity.status is QuantityStatus.VAGUE:
                issues.append(f"{step.step_id}: {field_name} is vague: {quantity.raw_text}; ask for a clearer estimate.")
        if not step.evidence:
            issues.append(f"{step.step_id}: no evidence attached; add a source quote before scoring.")
        if step.conflicts:
            issues.append(f"{step.step_id}: unresolved competing values remain; confirm the correct source before scoring.")
    return issues


def extract_step_json_from_chunk(chunk_text: str, *, fallback_step_id: str = "step-1") -> dict[str, object]:
    """Return a minimal structured step payload from free-form chunk text.

    This helps keep extraction importable and usable in environments without a live LLM.
    """
    lines = [line.strip() for line in chunk_text.splitlines() if line.strip()]
    task = lines[0] if lines else "Unspecified task"
    actor = "Operator" if not lines else lines[-1].split(" ")[0] or "Operator"
    return {
        "step_id": fallback_step_id,
        "process": "General operating process",
        "actor": actor,
        "task": task,
        "tools": [],
        "frequency": {"value": None, "unit": None, "status": "unknown", "raw_text": None},
        "frequency_basis": "total",
        "minutes_per_run": {"value": None, "unit": None, "status": "unknown", "raw_text": None},
        "people_doing_it": {"value": None, "unit": None, "status": "unknown", "raw_text": None},
        "error_rate": {"value": None, "unit": None, "status": "unknown", "raw_text": None},
        "handles_sensitive_data": None,
        "evidence": [],
        "review_status": "extracted",
        "conflicts": [],
    }
