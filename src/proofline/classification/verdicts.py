"""Deterministic verdict classification and human-confirmed risk checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from proofline.models.process_step import ProcessStep

VERDICT_LABELS = {
    "rules-based automation": "rules-based automation",
    "llm/generative": "LLM/generative",
    "classic ml": "classic ML",
    "rpa/integration": "RPA/integration",
    "keep human": "keep human",
    "unclassified": "unclassified",
}

VERDICT_PRIORITY = [
    "rules-based automation",
    "RPA/integration",
    "classic ML",
    "LLM/generative",
    "keep human",
    "unclassified",
]


class ClassificationResult(BaseModel):
    """Return the primary verdict, optional secondary verdict, and a reason."""

    model_config = ConfigDict(extra="forbid")

    primary_verdict: str
    secondary_verdict: str | None = None
    reason: str
    evidence_quote: str | None = None
    needs_human_review: bool = False

    @property
    def is_unclassified(self) -> bool:
        """True when no automation pattern is clear enough for a verdict."""
        return self.primary_verdict == "unclassified"


class RiskCheckResult(BaseModel):
    """Expose suggested risk flags that require user confirmation."""

    model_config = ConfigDict(extra="forbid")

    suggested_flags: list[str]
    confirmed_flags: list[str] = []
    requires_confirmation: bool = True


def classify_step(
    step: ProcessStep | Mapping[str, Any],
    *,
    reason: str | None = None,
    evidence_quote: str | None = None,
) -> ClassificationResult:
    """Classify an opportunity using a deterministic, prefer-simplest rule set.

    The model chooses a single primary verdict and may attach a secondary verdict when
    a task fits multiple patterns. The result is kept simple and explainable so the
    user can review it before scoring.
    """
    data = step.model_dump() if isinstance(step, ProcessStep) else dict(step)
    task_text = " ".join(
        part
        for part in (
            data.get("process"),
            data.get("task"),
            data.get("actor"),
            data.get("department"),
            " ".join(data.get("tools") or []),
        )
        if part is not None
    ).lower()

    found = _match_verdicts(task_text, step=data if isinstance(step, Mapping) else step)
    if not found:
        return ClassificationResult(
            primary_verdict="unclassified",
            secondary_verdict=None,
            reason="No clear automation pattern matched the task; route it to the gap report for follow-up.",
            evidence_quote=evidence_quote,
            needs_human_review=True,
        )

    primary = _preferred_primary(found)
    secondary = _preferred_secondary(found, primary)
    if primary == "keep human":
        base_reason = reason or (
            "Requires human judgment, exception handling, or accountability that should not be delegated."
        )
        return ClassificationResult(
            primary_verdict="keep human",
            secondary_verdict=secondary,
            reason=base_reason,
            evidence_quote=evidence_quote,
            needs_human_review=True,
        )

    default_reason = reason or _default_reason(primary)
    return ClassificationResult(
        primary_verdict=primary,
        secondary_verdict=secondary,
        reason=default_reason,
        evidence_quote=evidence_quote,
        needs_human_review=False,
    )


def classify_steps(steps: Iterable[ProcessStep | Mapping[str, Any]]) -> list[ClassificationResult]:
    """Classify a collection of process steps in order without LLM inference."""
    return [classify_step(step) for step in steps]


def risk_check(step: ProcessStep | Mapping[str, Any]) -> RiskCheckResult:
    """Generate suggested risk flags, leaving user confirmation as the final step."""
    data = step.model_dump() if isinstance(step, ProcessStep) else dict(step)
    suggested: list[str] = []

    if data.get("handles_sensitive_data") is True:
        suggested.append("sensitive_data")
    if data.get("review_status") == "edited":
        suggested.append("review_requires_confirmation")
    if (error_rate := data.get("error_rate")) is not None and isinstance(error_rate, dict):
        value = error_rate.get("value")
        if isinstance(value, (int, float)) and value > 0:
            suggested.append("low_error_tolerance")
    verdict = classify_step(step)
    if verdict.primary_verdict == "keep human":
        suggested.append("human_in_the_loop_required")

    if not suggested:
        return RiskCheckResult(suggested_flags=[], confirmed_flags=[], requires_confirmation=False)

    return RiskCheckResult(
        suggested_flags=sorted(set(suggested)),
        confirmed_flags=[],
        requires_confirmation=True,
    )


def _match_verdicts(task_text: str, *, step: ProcessStep | Mapping[str, Any]) -> list[str]:
    """Return candidate verdicts that match task language while preserving the simplest rule."""
    matches: list[str] = []
    if _contains_any(task_text, [
        "if ", "then ", "validate", "route", "triage", "check", "approval", "exception", "policy", "rules", "match", "decision tree", "threshold"
    ]):
        matches.append("rules-based automation")
    if _contains_any(task_text, [
        "api", "sync", "transfer", "copy", "reconcile", "import", "export", "update system", "move data", "workflow", "integration", "automation", "screen scrape", "ui automation"
    ]):
        matches.append("RPA/integration")
    if _contains_any(task_text, [
        "predict", "forecast", "score", "rank", "risk", "anomaly", "fraud", "churn", "segment", "classify", "recommend", "historical data"
    ]):
        matches.append("classic ML")
    if _contains_any(task_text, [
        "summarize", "draft", "rewrite", "extract", "answer questions", "review documents", "write email", "interpret", "generate", "chat", "language", "text analysis"
    ]):
        matches.append("LLM/generative")
    if _contains_any(task_text, [
        "approve", "sign off", "discretion", "judgment", "case review", "escalation", "exception handling", "human review", "ethical", "policy decision", "customer complaint"
    ]) or (isinstance(step, ProcessStep) and step.handles_sensitive_data is True):
        matches.append("keep human")
    return matches


def _preferred_primary(candidates: list[str]) -> str:
    """Choose the simplest candidate that still matches the task."""
    for label in VERDICT_PRIORITY:
        if label in candidates:
            return label
    return "unclassified"


def _preferred_secondary(candidates: list[str], primary: str) -> str | None:
    """Provide the next strongest applicable verdict without duplicating the primary."""
    ordered = [label for label in VERDICT_PRIORITY if label in candidates and label != primary]
    return ordered[0] if ordered else None


def _default_reason(primary: str) -> str:
    """Return a simple reason for a selected verdict."""
    reason_map = {
        "rules-based automation": "The workflow is a repeatable decision ladder with explicit conditions and little room for judgment.",
        "RPA/integration": "The task is mainly system-to-system workflow movement, data exchange, or orchestration.",
        "classic ML": "The task depends on learning a historical pattern to predict, score, or rank cases.",
        "LLM/generative": "The task depends on understanding or generating language, documents, or unstructured content.",
        "keep human": "The work requires human judgment, accountability, or discretion that should not be delegated.",
        "unclassified": "The task does not match a clear automation pattern and should be reviewed manually.",
    }
    return reason_map.get(primary, "No clear verdict matched the task and it should be reviewed.")


def _contains_any(text: str, tokens: list[str]) -> bool:
    """Return True when any target phrase appears in the task description."""
    return any(token in text for token in tokens)
