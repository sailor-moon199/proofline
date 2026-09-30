"""Pure-Python opportunity savings and payback calculations."""

from enum import StrEnum
from math import isfinite
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict

from proofline.models.client_config import ClientConfig
from proofline.models.process_step import (
    FrequencyBasis,
    ProcessStep,
    QuantityField,
    QuantityStatus,
    ReviewStatus,
)
from proofline.scoring.units import annualize_frequency_unit, duration_to_minutes


MetricInput: TypeAlias = str | int | float | None


class MetricStatus(StrEnum):
    """Distinguish computed values from explicit missing-input outcomes."""

    COMPUTED = "computed"
    NOT_COMPUTED = "not computed"


class MetricResult(BaseModel):
    """Expose each computed value with its formula, inputs, and status."""

    model_config = ConfigDict(extra="forbid")

    status: MetricStatus
    value: float | None
    unit: str
    formula: str
    inputs: dict[str, MetricInput]
    reason: str | None


class StepScore(BaseModel):
    """Return all supported savings metrics for one confirmed process step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    currency: str | None
    annual_runs: MetricResult
    hours_saved_per_year: MetricResult
    cost_saved_per_year: MetricResult
    payback_months: MetricResult


def score_step(
    step: ProcessStep,
    client_config: ClientConfig,
    *,
    verdict_key: str,
) -> StepScore:
    """Compute transparent savings estimates from confirmed step and client inputs."""
    blocked_reason = _score_block_reason(step)
    if blocked_reason is not None:
        annual_runs = _not_computed(
            "runs/year",
            "frequency × annual cadence multiplier",
            {},
            blocked_reason,
        )
        hours_saved = _not_computed(
            "hours/year",
            "annual runs × (minutes per run ÷ 60) × (coverage percent ÷ 100)",
            {},
            blocked_reason,
        )
        cost_saved = _not_computed(
            _currency_unit(client_config.currency),
            "hours saved per year × role hourly rate",
            {},
            blocked_reason,
        )
        payback = _not_computed(
            "months",
            "implementation cost ÷ (annual cost saved ÷ 12)",
            {},
            blocked_reason,
        )
        return StepScore(
            step_id=step.step_id,
            currency=client_config.currency,
            annual_runs=annual_runs,
            hours_saved_per_year=hours_saved,
            cost_saved_per_year=cost_saved,
            payback_months=payback,
        )

    annual_runs = _annual_runs(step, client_config)
    hours_saved = _hours_saved(step, client_config, verdict_key, annual_runs)
    cost_saved = _cost_saved(step, client_config, hours_saved)
    payback = _payback(step, client_config, verdict_key, cost_saved)
    return StepScore(
        step_id=step.step_id,
        currency=client_config.currency,
        annual_runs=annual_runs,
        hours_saved_per_year=hours_saved,
        cost_saved_per_year=cost_saved,
        payback_months=payback,
    )


def _score_block_reason(step: ProcessStep) -> str | None:
    """Require a human-confirmed step with every attached quote verified."""
    if step.review_status is not ReviewStatus.CONFIRMED:
        return "process step has not been human-confirmed"
    if not step.evidence:
        return "no source evidence is attached"
    unverified_count = sum(not evidence.verified for evidence in step.evidence)
    if unverified_count:
        return f"{unverified_count} source quote(s) remain unverified"
    return None


def _annual_runs(step: ProcessStep, config: ClientConfig) -> MetricResult:
    """Annualize team-wide or per-person cadence using only configured periods."""
    conflict_reason = _conflict_reason(step, "frequency")
    if conflict_reason is not None:
        return _not_computed(
            "runs/year",
            "frequency × annual cadence multiplier",
            {"frequency": step.frequency.value, "unit": step.frequency.unit},
            conflict_reason,
        )
    frequency_error = _quantity_error(step.frequency, "frequency")
    if frequency_error is not None:
        return _not_computed(
            "runs/year",
            "frequency × annual cadence multiplier",
            {"frequency": step.frequency.value, "unit": step.frequency.unit},
            frequency_error,
        )

    multiplier, frequency_kind, unit_error = annualize_frequency_unit(
        step.frequency.unit,
        work_days_per_week=config.work_days_per_week,
        weeks_per_year=config.weeks_per_year,
    )
    if unit_error is not None or multiplier is None or frequency_kind is None:
        return _not_computed(
            "runs/year",
            "frequency × annual cadence multiplier",
            {"frequency": step.frequency.value, "unit": step.frequency.unit},
            unit_error or "frequency conversion could not be completed",
        )

    inputs: dict[str, MetricInput] = {
        "frequency": step.frequency.value,
        "source_unit": step.frequency.unit,
        "annual_cadence_multiplier": multiplier,
        "frequency_basis": step.frequency_basis.value,
    }
    annual_runs = float(step.frequency.value) * multiplier
    if step.frequency_basis is FrequencyBasis.PER_PERSON:
        people_conflict = _conflict_reason(step, "people_doing_it")
        if people_conflict is not None:
            return _not_computed(
                "runs/year",
                "runs per person × people doing it × annual cadence multiplier",
                inputs,
                people_conflict,
            )
        people_error = _quantity_error(step.people_doing_it, "people_doing_it")
        if people_error is not None:
            return _not_computed(
                "runs/year",
                "runs per person × people doing it × annual cadence multiplier",
                inputs,
                people_error,
            )
        inputs["people_doing_it"] = step.people_doing_it.value
        annual_runs *= float(step.people_doing_it.value)

    return _computed(
        annual_runs,
        "runs/year",
        (
            "frequency × people doing it × annual cadence multiplier"
            if step.frequency_basis is FrequencyBasis.PER_PERSON
            else "frequency × annual cadence multiplier"
        ),
        inputs,
    )


def _hours_saved(
    step: ProcessStep,
    config: ClientConfig,
    verdict_key: str,
    annual_runs: MetricResult,
) -> MetricResult:
    """Calculate covered annual task time using explicit coverage and duration units."""
    formula = "annual runs × (minutes per run ÷ 60) × (coverage percent ÷ 100)"
    if annual_runs.value is None:
        return _not_computed("hours/year", formula, {}, _metric_reason(annual_runs))
    conflict_reason = _conflict_reason(step, "minutes_per_run")
    if conflict_reason is not None:
        return _not_computed(
            "hours/year",
            formula,
            {"annual_runs": annual_runs.value},
            conflict_reason,
        )
    duration_error = _quantity_error(step.minutes_per_run, "minutes_per_run")
    if duration_error is not None:
        return _not_computed(
            "hours/year",
            formula,
            {"annual_runs": annual_runs.value},
            duration_error,
        )
    duration_multiplier, unit_error = duration_to_minutes(step.minutes_per_run.unit)
    if unit_error is not None or duration_multiplier is None:
        return _not_computed(
            "hours/year",
            formula,
            {"annual_runs": annual_runs.value},
            unit_error or "duration conversion could not be completed",
        )
    coverage_percent = config.coverage_by_verdict.get(verdict_key)
    if coverage_percent is None:
        return _not_computed(
            "hours/year",
            formula,
            {
                "annual_runs": annual_runs.value,
                "minutes_per_run": step.minutes_per_run.value,
                "duration_to_minutes_multiplier": duration_multiplier,
                "verdict_key": verdict_key,
            },
            f"coverage for verdict {verdict_key!r} is not configured",
        )

    minutes_per_run = float(step.minutes_per_run.value) * duration_multiplier
    inputs: dict[str, MetricInput] = {
        "annual_runs": annual_runs.value,
        "minutes_per_run_source_value": step.minutes_per_run.value,
        "minutes_per_run_source_unit": step.minutes_per_run.unit,
        "duration_to_minutes_multiplier": duration_multiplier,
        "minutes_per_run_normalized": minutes_per_run,
        "coverage_percent": coverage_percent,
        "verdict_key": verdict_key,
    }
    hours = annual_runs.value * (minutes_per_run / 60) * (
        float(coverage_percent) / 100
    )
    return _computed(hours, "hours/year", formula, inputs)


def _cost_saved(
    step: ProcessStep,
    config: ClientConfig,
    hours_saved: MetricResult,
) -> MetricResult:
    """Calculate annual labor savings using the configured role rate and currency."""
    formula = "hours saved per year × role hourly rate"
    if hours_saved.value is None:
        return _not_computed(
            _currency_unit(config.currency),
            formula,
            {},
            _metric_reason(hours_saved),
        )
    if config.currency is None or config.currency.strip() == "":
        return _not_computed(
            "client currency",
            formula,
            {"hours_saved_per_year": hours_saved.value, "role": step.actor},
            "client currency is not configured",
        )
    hourly_rate = config.role_hourly_rates.get(step.actor)
    if hourly_rate is None:
        return _not_computed(
            config.currency,
            formula,
            {"hours_saved_per_year": hours_saved.value, "role": step.actor},
            f"hourly rate for role {step.actor!r} is not configured",
        )
    return _computed(
        hours_saved.value * float(hourly_rate),
        f"{config.currency}/year",
        formula,
        {
            "hours_saved_per_year": hours_saved.value,
            "role": step.actor,
            "hourly_rate": hourly_rate,
            "currency": config.currency,
        },
    )


def _payback(
    step: ProcessStep,
    config: ClientConfig,
    verdict_key: str,
    cost_saved: MetricResult,
) -> MetricResult:
    """Calculate payback only when monthly savings and implementation cost are known."""
    formula = "implementation cost ÷ (annual cost saved ÷ 12)"
    if cost_saved.value is None:
        return _not_computed("months", formula, {}, _metric_reason(cost_saved))
    implementation_cost = config.implementation_cost_by_verdict.get(verdict_key)
    if implementation_cost is None:
        return _not_computed(
            "months",
            formula,
            {
                "annual_cost_saved": cost_saved.value,
                "verdict_key": verdict_key,
            },
            f"implementation cost for verdict {verdict_key!r} is not configured",
        )
    monthly_saving = cost_saved.value / 12
    if monthly_saving <= 0:
        return _not_computed(
            "months",
            formula,
            {
                "implementation_cost": implementation_cost,
                "annual_cost_saved": cost_saved.value,
                "monthly_saving": monthly_saving,
            },
            "monthly savings are not positive",
        )
    return _computed(
        float(implementation_cost) / monthly_saving,
        "months",
        formula,
        {
            "implementation_cost": implementation_cost,
            "annual_cost_saved": cost_saved.value,
            "monthly_saving": monthly_saving,
            "currency": config.currency,
            "verdict_key": verdict_key,
        },
    )


def _quantity_error(quantity: QuantityField, field_name: str) -> str | None:
    """Describe missing or vague quantity inputs without approximating them."""
    if quantity.status is QuantityStatus.UNKNOWN:
        return f"{field_name} is unknown"
    if quantity.status is QuantityStatus.VAGUE:
        return f"{field_name} is vague: {quantity.raw_text!r}"
    if quantity.status not in {QuantityStatus.STATED, QuantityStatus.USER_ENTERED}:
        return f"{field_name} is not a confirmed numeric input"
    if quantity.value is None:
        return f"{field_name} has no numeric value"
    if not isfinite(float(quantity.value)):
        return f"{field_name} is not finite"
    if quantity.value < 0:
        return f"{field_name} cannot be negative"
    return None


def _conflict_reason(step: ProcessStep, field_name: str) -> str | None:
    """Block use of a field while unresolved competing values remain."""
    conflicts = [
        conflict
        for conflict in step.conflicts
        if conflict.field == field_name
        or conflict.field.startswith(f"{field_name}.")
    ]
    if not conflicts:
        return None
    return f"{field_name} has {len(conflicts)} unresolved competing value(s)"


def _computed(
    value: float,
    unit: str,
    formula: str,
    inputs: dict[str, MetricInput],
) -> MetricResult:
    """Create a successful metric, rejecting invalid numeric outputs."""
    if not isfinite(value):
        return _not_computed(
            unit,
            formula,
            inputs,
            "calculation produced a non-finite result",
        )
    return MetricResult(
        status=MetricStatus.COMPUTED,
        value=value,
        unit=unit,
        formula=formula,
        inputs=inputs,
        reason=None,
    )


def _not_computed(
    unit: str,
    formula: str,
    inputs: dict[str, MetricInput],
    reason: str,
) -> MetricResult:
    """Create a visible not-computed result with its reason and known inputs."""
    return MetricResult(
        status=MetricStatus.NOT_COMPUTED,
        value=None,
        unit=unit,
        formula=formula,
        inputs=inputs,
        reason=f"not computed: {reason}",
    )


def _metric_reason(metric: MetricResult) -> str:
    """Return a non-empty reason when a dependent metric is unavailable."""
    if metric.reason is None:
        return f"not computed: {metric.unit} is unavailable"
    return metric.reason


def _currency_unit(currency: str | None) -> str:
    """Return a display unit without substituting an unknown currency."""
    if currency is None or currency.strip() == "":
        return "client currency/year"
    return f"{currency}/year"
