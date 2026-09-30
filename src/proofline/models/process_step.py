"""Pydantic schemas for process steps and their supporting evidence."""

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictFloat,
    StrictInt,
    model_validator,
)


class QuantityStatus(StrEnum):
    """Describe how a quantity value was obtained from its source."""

    STATED = "stated"
    VAGUE = "vague"
    UNKNOWN = "unknown"
    USER_ENTERED = "user_entered"


class ReviewStatus(StrEnum):
    """Track the human review state of an extracted process step."""

    EXTRACTED = "extracted"
    EDITED = "edited"
    CONFIRMED = "confirmed"


class FrequencyBasis(StrEnum):
    """Specify whether frequency counts team-wide runs or per-person runs."""

    TOTAL = "total"
    PER_PERSON = "per_person"


class QuantityField(BaseModel):
    """Store a source-grounded numeric quantity without inventing missing values."""

    model_config = ConfigDict(extra="forbid")

    value: StrictInt | StrictFloat | None
    unit: str | None
    status: QuantityStatus
    raw_text: str | None

    @model_validator(mode="after")
    def validate_value_status(self) -> Self:
        """Keep missing, vague, stated, and user-entered values distinct."""
        if self.status is QuantityStatus.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown quantities must not have a numeric value")
        elif self.status is QuantityStatus.VAGUE:
            if self.value is not None or not self.raw_text:
                raise ValueError("vague quantities require raw_text and a null value")
        elif self.value is None:
            raise ValueError("stated and user-entered quantities require a value")
        return self


class Evidence(BaseModel):
    """Identify a source quote and whether code verified its exact presence."""

    model_config = ConfigDict(extra="forbid")

    document: str
    location: str
    quote: str
    verified: bool

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        """Require non-empty source identity, location, and quote text."""
        for field_name, value in (
            ("document", self.document),
            ("location", self.location),
            ("quote", self.quote),
        ):
            if value.strip() == "":
                raise ValueError(f"evidence {field_name} must not be blank")
        return self


class ConflictValue(BaseModel):
    """Preserve a competing source value instead of silently resolving it."""

    model_config = ConfigDict(extra="forbid")

    field: str
    value: str
    document: str
    location: str


class ProcessStep(BaseModel):
    """Represent a process step and its source, review, and quantity details."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    process: str
    department: str | None = None
    actor: str
    task: str
    tools: list[str]
    frequency: QuantityField
    frequency_basis: FrequencyBasis
    minutes_per_run: QuantityField
    people_doing_it: QuantityField
    error_rate: QuantityField
    handles_sensitive_data: bool | None
    evidence: list[Evidence]
    review_status: ReviewStatus
    conflicts: list[ConflictValue]
