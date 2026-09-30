"""Evaluation harness and comparable provider results."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict


class VerdictAgreement(BaseModel):
    """Capture agreement between expected and predicted verdict labels."""

    model_config = ConfigDict(extra="forbid")

    expected_primary: str | None = None
    predicted_primary: str | None = None
    expected_secondary: str | None = None
    predicted_secondary: str | None = None
    primary_match: bool = False
    secondary_match: bool | None = None
    agreement: float = 0.0


class EvaluationResult(BaseModel):
    """Store comparable provider/model results for a single evaluation run."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str
    prompt_version: str
    expected_steps: int
    steps_found: int
    step_precision: float
    step_recall: float
    fabricated_quote_count: int
    unverified_quote_count: int
    numeric_accuracy: float
    null_handling_accuracy: float
    verdict_agreement: list[VerdictAgreement] = []


def verdict_agreement(
    *,
    expected_primary: str | None,
    predicted_primary: str | None,
    expected_secondary: str | None = None,
    predicted_secondary: str | None = None,
) -> VerdictAgreement:
    """Return a comparable verdict-agreement record for classification evaluation."""
    primary_match = expected_primary == predicted_primary
    secondary_match = None
    if expected_secondary is not None or predicted_secondary is not None:
        secondary_match = expected_secondary == predicted_secondary
    agreement = 1.0 if primary_match and (secondary_match is not False) else 0.0
    return VerdictAgreement(
        expected_primary=expected_primary,
        predicted_primary=predicted_primary,
        expected_secondary=expected_secondary,
        predicted_secondary=predicted_secondary,
        primary_match=primary_match,
        secondary_match=secondary_match,
        agreement=agreement,
    )


def load_gold_key(path: str | Path) -> dict[str, Any]:
    """Load the evaluation answer key from a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize_step_key(step: MappingLike) -> str:
    """Match steps using the project rule: normalized process + actor + task."""
    process = str(step.get("process", "")).strip().lower()
    actor = str(step.get("actor", "")).strip().lower()
    task = str(step.get("task", "")).strip().lower()
    return f"{_collapse_text(process)}|{_collapse_text(actor)}|{_collapse_text(task)}"


def evaluate_steps(
    actual_steps: Iterable[Mapping[str, Any]],
    expected_steps: Iterable[Mapping[str, Any]],
    *,
    provider: str,
    model: str,
    prompt_version: str,
    source_documents: dict[str, str] | None = None,
) -> EvaluationResult:
    """Compare extracted steps against the expected answer key and report comparable metrics.

    Matching rule: normalize process, actor, and task and compare those three fields.
    The step match is not based on an LLM guess or a fuzzy semantic match.
    """
    expected_list = list(expected_steps)
    actual_list = list(actual_steps)
    expected_lookup = {normalize_step_key(step): step for step in expected_list}
    actual_lookup = {normalize_step_key(step): step for step in actual_list}
    matched_keys = sorted(set(expected_lookup) & set(actual_lookup))

    fabricated_quote_count = 0
    unverified_quote_count = 0
    numeric_accuracy_total = 0
    numeric_accuracy_score = 0
    null_total = 0
    null_correct = 0

    for key in matched_keys:
        expected = expected_lookup[key]
        actual = actual_lookup[key]

        expected_evidence = expected.get("evidence", []) or []
        actual_evidence = actual.get("evidence", []) or []
        source_text = "\n".join(source_documents.get(doc["document"], "") for doc in expected_evidence if isinstance(doc, dict))

        for evidence in actual_evidence:
            if isinstance(evidence, dict):
                quote = str(evidence.get("quote", ""))
                if not evidence.get("verified", False):
                    unverified_quote_count += 1
                if not _quote_in_text(quote, source_text):
                    fabricated_quote_count += 1

        fields = ["frequency", "minutes_per_run", "people_doing_it", "error_rate"]
        for field_name in fields:
            expected_field = (expected.get(field_name) or {}) if isinstance(expected.get(field_name), dict) else {}
            actual_field = (actual.get(field_name) or {}) if isinstance(actual.get(field_name), dict) else {}
            expected_value = expected_field.get("value")
            actual_value = actual_field.get("value")
            numeric_accuracy_total += 1
            if expected_value is None and actual_value is None:
                numeric_accuracy_score += 1
            elif expected_value == actual_value:
                numeric_accuracy_score += 1
            if expected_value is None or actual_value is None:
                null_total += 1
                if expected_value is None and actual_value is None:
                    null_correct += 1
                elif expected_value is not None and actual_value is not None:
                    null_correct += 1

    step_precision = len(matched_keys) / len(actual_list) if actual_list else 0.0
    step_recall = len(matched_keys) / len(expected_list) if expected_list else 0.0
    numeric_accuracy = numeric_accuracy_score / numeric_accuracy_total if numeric_accuracy_total else 1.0
    null_handling_accuracy = null_correct / null_total if null_total else 1.0

    return EvaluationResult(
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        expected_steps=len(expected_list),
        steps_found=len(matched_keys),
        step_precision=step_precision,
        step_recall=step_recall,
        fabricated_quote_count=fabricated_quote_count,
        unverified_quote_count=unverified_quote_count,
        numeric_accuracy=numeric_accuracy,
        null_handling_accuracy=null_handling_accuracy,
    )


def save_evaluation_result(result: EvaluationResult, path: str | Path) -> Path:
    """Persist one evaluation result as JSON for later comparison across providers."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    return destination


def _collapse_text(value: str) -> str:
    """Normalize whitespace and punctuation so the step key comparison is deterministic."""
    return re.sub(r"\s+", " ", value.replace("-", " ")).strip()


def _quote_in_text(quote: str, source_text: str) -> bool:
    """Check whether a quote appears in the source after normalizing whitespace and quotes."""
    normalized_quote = _collapse_text(quote).replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    normalized_source = _collapse_text(source_text).replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return normalized_quote in normalized_source


MappingLike = dict[str, Any]

__all__ = [
    "EvaluationResult",
    "VerdictAgreement",
    "evaluate_steps",
    "load_gold_key",
    "save_evaluation_result",
    "verdict_agreement",
]
