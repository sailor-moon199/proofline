"""Validation helpers for manual process-step form submissions."""

from collections.abc import Mapping

from pydantic import ValidationError

from proofline.models.process_step import ProcessStep


class IntakeValidationError(ValueError):
    """Identify invalid structured form input with its schema errors."""


def validate_form_entry(data: Mapping[str, object]) -> ProcessStep:
    """Validate a manual form payload against the shared process-step schema."""
    try:
        return ProcessStep.model_validate(data)
    except ValidationError as exc:
        raise IntakeValidationError(f"Invalid process-step form entry: {exc}") from exc
