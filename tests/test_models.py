"""Tests for the core process-step schemas."""

import pytest
from pydantic import ValidationError

from proofline.models import (
    Evidence,
    FrequencyBasis,
    ProcessStep,
    QuantityField,
    QuantityStatus,
    ReviewStatus,
)


def make_quantity(value: int | None, status: QuantityStatus) -> QuantityField:
    """Create a quantity with explicit source metadata for schema tests."""
    return QuantityField(value=value, unit="per week", status=status, raw_text=None)


def test_process_step_requires_explicit_frequency_basis() -> None:
    """Require frequency semantics rather than assuming team or per-person totals."""
    data = {
        "step_id": "step-1",
        "process": "Booking",
        "actor": "Coordinator",
        "task": "Enter a shipment",
        "tools": ["TMS"],
        "frequency": make_quantity(4, QuantityStatus.STATED),
        "minutes_per_run": make_quantity(10, QuantityStatus.STATED),
        "people_doing_it": make_quantity(2, QuantityStatus.STATED),
        "error_rate": make_quantity(None, QuantityStatus.UNKNOWN),
        "handles_sensitive_data": None,
        "evidence": [
            Evidence(
                document="interview.txt",
                location="line 2",
                quote="We enter four shipments a week.",
                verified=True,
            )
        ],
        "review_status": ReviewStatus.EXTRACTED,
        "conflicts": [],
    }

    with pytest.raises(ValidationError):
        ProcessStep.model_validate(data)

    data["frequency_basis"] = FrequencyBasis.TOTAL
    step = ProcessStep.model_validate(data)

    assert step.frequency_basis is FrequencyBasis.TOTAL
    assert step.error_rate.value is None
    assert step.error_rate.status is QuantityStatus.UNKNOWN


def test_quantity_rejects_numeric_text() -> None:
    """Prevent numeric-looking source text from being silently converted to a number."""
    with pytest.raises(ValidationError):
        QuantityField(
            value="4",
            unit="per week",
            status=QuantityStatus.STATED,
            raw_text="four per week",
        )


def test_quantity_requires_raw_text_for_vague_values() -> None:
    """Keep vague source language visible instead of turning it into a number."""
    with pytest.raises(ValidationError):
        QuantityField(
            value=None,
            unit=None,
            status=QuantityStatus.VAGUE,
            raw_text=None,
        )


def test_unknown_quantity_cannot_have_a_numeric_value() -> None:
    """Require explicit unknown status to mean the numeric value is absent."""
    with pytest.raises(ValidationError):
        QuantityField(
            value=4,
            unit="per week",
            status=QuantityStatus.UNKNOWN,
            raw_text=None,
        )


def test_evidence_requires_non_empty_source_quote() -> None:
    """Do not allow an empty quote to be marked verified evidence."""
    with pytest.raises(ValidationError, match="evidence quote must not be blank"):
        Evidence(
            document="interview.txt",
            location="line 2",
            quote="  ",
            verified=True,
        )
