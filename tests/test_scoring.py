"""Tests for deterministic savings calculations and their visible failure results."""

import ast
from pathlib import Path

import pytest

import proofline.scoring
from proofline.models import (
    ClientConfig,
    ConflictValue,
    Evidence,
    FrequencyBasis,
    ProcessStep,
    QuantityField,
    QuantityStatus,
    ReviewStatus,
)
from proofline.scoring import MetricStatus, score_step
from proofline.scoring.engine import StepScore
from proofline.scoring.units import annualize_frequency_unit, duration_to_minutes


def make_quantity(
    value: int | float | None,
    unit: str | None,
    status: QuantityStatus = QuantityStatus.STATED,
    raw_text: str | None = None,
) -> QuantityField:
    """Create a quantity fixture without inferring values or units."""
    return QuantityField(value=value, unit=unit, status=status, raw_text=raw_text)


def make_step(
    *,
    frequency_value: int | float | None = 4,
    frequency_unit: str | None = "per week",
    frequency_status: QuantityStatus = QuantityStatus.STATED,
    duration_value: int | float | None = 30,
    duration_unit: str | None = "minutes",
    duration_status: QuantityStatus = QuantityStatus.STATED,
    frequency_basis: FrequencyBasis = FrequencyBasis.TOTAL,
    people_value: int | float | None = 3,
    review_status: ReviewStatus = ReviewStatus.CONFIRMED,
    evidence_verified: bool = True,
    conflicts: list[ConflictValue] | None = None,
) -> ProcessStep:
    """Create a confirmed step fixture with adjustable scoring inputs."""
    frequency_raw = (
        "a few times each week"
        if frequency_status is QuantityStatus.VAGUE
        else None
    )
    duration_raw = "a while" if duration_status is QuantityStatus.VAGUE else None
    return ProcessStep(
        step_id="step-1",
        process="Shipment booking",
        actor="Coordinator",
        task="Enter shipment details",
        tools=["TMS"],
        frequency=make_quantity(
            frequency_value,
            frequency_unit,
            frequency_status,
            frequency_raw,
        ),
        frequency_basis=frequency_basis,
        minutes_per_run=make_quantity(
            duration_value,
            duration_unit,
            duration_status,
            duration_raw,
        ),
        people_doing_it=make_quantity(
            people_value,
            "people",
            (
                QuantityStatus.STATED
                if people_value is not None
                else QuantityStatus.UNKNOWN
            ),
        ),
        error_rate=make_quantity(None, None, QuantityStatus.UNKNOWN),
        handles_sensitive_data=None,
        evidence=[
            Evidence(
                document="interview.txt",
                location="line 8",
                quote="We book four shipments per week.",
                verified=evidence_verified,
            )
        ],
        review_status=review_status,
        conflicts=conflicts or [],
    )


def make_config(
    *,
    work_days_per_week: int | float | None = 5,
    weeks_per_year: int | float | None = 50,
    currency: str | None = "GBP",
    hourly_rate: int | float | None = 40,
    coverage_percent: int | float | None = 50,
    implementation_cost: int | float | None = 2400,
) -> ClientConfig:
    """Create explicit test configuration values, not project defaults."""
    return ClientConfig(
        client_name="Test Client",
        work_days_per_week=work_days_per_week,
        weeks_per_year=weeks_per_year,
        currency=currency,
        role_hourly_rates={"Coordinator": hourly_rate},
        coverage_by_verdict={"rules-based automation": coverage_percent},
        implementation_cost_by_verdict={
            "rules-based automation": implementation_cost
        },
    )


def score(step: ProcessStep, config: ClientConfig | None = None) -> StepScore:
    """Score a test step using explicit settings and a stable verdict key."""
    if config is None:
        config = make_config()
    return score_step(
        step,
        config,
        verdict_key="rules-based automation",
    )


def test_scoring_does_not_import_providers() -> None:
    """Prevent scoring code from depending on LLM provider implementations."""
    scoring_directory = Path(proofline.scoring.__file__).parent
    for source_path in scoring_directory.rglob("*.py"):
        syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(syntax_tree):
            if isinstance(node, ast.Import):
                assert all(
                    alias.name != "proofline.providers"
                    and not alias.name.startswith("proofline.providers.")
                    for alias in node.names
                ), source_path
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "proofline.providers" and not (
                    node.module or ""
                ).startswith("proofline.providers."), source_path


def test_team_total_weekly_frequency_uses_python_formulas() -> None:
    """Compute hours, money, and payback from visible client inputs."""
    result = score(make_step())

    assert result.annual_runs.value == 200
    assert result.hours_saved_per_year.value == 50
    assert result.cost_saved_per_year.value == 2000
    assert result.payback_months.value == pytest.approx(14.4)
    assert result.hours_saved_per_year.formula == (
        "annual runs × (minutes per run ÷ 60) × (coverage percent ÷ 100)"
    )
    assert result.hours_saved_per_year.inputs["coverage_percent"] == 50
    assert result.cost_saved_per_year.inputs["hourly_rate"] == 40
    assert result.payback_months.inputs["implementation_cost"] == 2400


def test_per_person_frequency_multiplies_by_confirmed_people_count() -> None:
    """Use people_doing_it only when frequency is explicitly per person."""
    step = make_step(frequency_basis=FrequencyBasis.PER_PERSON)

    result = score(step)

    assert result.annual_runs.value == 600
    assert result.annual_runs.inputs["people_doing_it"] == 3
    assert result.hours_saved_per_year.value == 150


def test_per_person_frequency_without_people_count_is_not_computed() -> None:
    """Do not assume a team size for per-person source frequencies."""
    result = score(
        make_step(
            frequency_basis=FrequencyBasis.PER_PERSON,
            people_value=None,
        )
    )

    assert result.annual_runs.status is MetricStatus.NOT_COMPUTED
    assert "people_doing_it is unknown" in (result.annual_runs.reason or "")


def test_daily_frequency_uses_operating_days_per_week_and_weeks_per_year() -> None:
    """Annualize daily cadence with the client-confirmed operating calendar."""
    result = score(
        make_step(frequency_value=2, frequency_unit="per operating day"),
        make_config(work_days_per_week=7, weeks_per_year=52),
    )

    assert result.annual_runs.value == 728
    assert result.annual_runs.inputs["annual_cadence_multiplier"] == 364


def test_any_unverified_evidence_blocks_step_scoring() -> None:
    """Do not let another verified citation mask an unverified quote on the step."""
    step = make_step().model_copy(
        update={
            "evidence": [
                Evidence(
                    document="interview.txt",
                    location="line 8",
                    quote="Verified source quote.",
                    verified=True,
                ),
                Evidence(
                    document="notes.txt",
                    location="line 3",
                    quote="Unverified source quote.",
                    verified=False,
                ),
            ]
        }
    )

    result = score(step)

    assert result.annual_runs.status is MetricStatus.NOT_COMPUTED
    assert "1 source quote(s) remain unverified" in (
        result.annual_runs.reason or ""
    )


def test_step_without_evidence_is_not_computed() -> None:
    """Do not compute estimates for a step lacking a source citation."""
    step = make_step().model_copy(update={"evidence": []})

    result = score(step)

    assert result.annual_runs.status is MetricStatus.NOT_COMPUTED
    assert "no source evidence is attached" in (result.annual_runs.reason or "")


@pytest.mark.parametrize(
    ("unit", "days", "weeks", "expected"),
    [
        ("per day", 5, 50, 250),
        ("per operating day", 7, 52, 364),
        ("per week", 5, 50, 50),
        ("per month", None, None, 12),
        ("per annum", None, None, 1),
    ],
)
def test_frequency_annualization_uses_explicit_unit_and_calendar(
    unit: str,
    days: int | None,
    weeks: int | None,
    expected: int,
) -> None:
    """Normalize supported source frequencies without a built-in calendar default."""
    multiplier, _, reason = annualize_frequency_unit(
        unit,
        work_days_per_week=days,
        weeks_per_year=weeks,
    )

    assert multiplier == expected
    assert reason is None


def test_unknown_frequency_period_and_duration_unit_are_not_computed() -> None:
    """Leave unsupported source cadence and duration units visible and unguessed."""
    frequency_result = score(make_step(frequency_unit="every so often"))
    duration_result = score(make_step(duration_unit="shifts"))

    assert frequency_result.annual_runs.status is MetricStatus.NOT_COMPUTED
    assert "unsupported frequency unit" in (frequency_result.annual_runs.reason or "")
    assert duration_result.hours_saved_per_year.status is MetricStatus.NOT_COMPUTED
    assert "unsupported duration unit" in (
        duration_result.hours_saved_per_year.reason or ""
    )
    assert duration_to_minutes("hours") == (60, None)


@pytest.mark.parametrize(
    ("step", "config", "expected_fragment"),
    [
        (
            make_step(review_status=ReviewStatus.EDITED),
            make_config(),
            "not been human-confirmed",
        ),
        (
            make_step(evidence_verified=False),
            make_config(),
            "source quote(s) remain unverified",
        ),
        (
            make_step(frequency_status=QuantityStatus.UNKNOWN, frequency_value=None),
            make_config(),
            "frequency is unknown",
        ),
        (
            make_step(
                frequency_status=QuantityStatus.VAGUE,
                frequency_value=None,
            ),
            make_config(),
            "frequency is vague",
        ),
        (
            make_step(duration_status=QuantityStatus.UNKNOWN, duration_value=None),
            make_config(),
            "minutes_per_run is unknown",
        ),
        (
            make_step(
                conflicts=[
                    ConflictValue(
                        field="frequency",
                        value="6 per week",
                        document="other.txt",
                        location="line 4",
                    )
                ]
            ),
            make_config(),
            "unresolved competing",
        ),
        (
            make_step(
                conflicts=[
                    ConflictValue(
                        field="minutes_per_run",
                        value="45 minutes",
                        document="other.txt",
                        location="line 4",
                    )
                ]
            ),
            make_config(),
            "unresolved competing",
        ),
        (
            make_step(frequency_unit="per day"),
            make_config(work_days_per_week=None),
            "work_days_per_week is not configured",
        ),
        (
            make_step(frequency_unit="per day"),
            make_config(weeks_per_year=None),
            "weeks_per_year is not configured",
        ),
    ],
)
def test_missing_unconfirmed_or_conflicted_inputs_return_reason(
    step: ProcessStep,
    config: ClientConfig,
    expected_fragment: str,
) -> None:
    """Make unavailable estimates explicit instead of substituting default numbers."""
    result = score(step, config)

    assert result.annual_runs.status is MetricStatus.NOT_COMPUTED or (
        result.hours_saved_per_year.status is MetricStatus.NOT_COMPUTED
    )
    all_reasons = " ".join(
        metric.reason or ""
        for metric in (
            result.annual_runs,
            result.hours_saved_per_year,
            result.cost_saved_per_year,
            result.payback_months,
        )
    )
    assert expected_fragment in all_reasons


@pytest.mark.parametrize(
    ("config", "expected_fragment", "metric_name"),
    [
        (make_config(coverage_percent=None), "coverage", "hours_saved_per_year"),
        (make_config(hourly_rate=None), "hourly rate", "cost_saved_per_year"),
        (make_config(currency=None), "currency", "cost_saved_per_year"),
        (
            make_config(implementation_cost=None),
            "implementation cost",
            "payback_months",
        ),
    ],
)
def test_unset_financial_settings_return_not_computed_metric(
    config: ClientConfig,
    expected_fragment: str,
    metric_name: str,
) -> None:
    """Leave metrics unavailable when any client financial setting is unset."""
    result = score(make_step(), config)
    metric = getattr(result, metric_name)

    assert metric.status is MetricStatus.NOT_COMPUTED
    assert metric.value is None
    assert expected_fragment in (metric.reason or "")


def test_zero_monthly_savings_cannot_produce_payback() -> None:
    """Report a reason when there are no positive monthly savings to repay cost."""
    result = score(make_step(), make_config(coverage_percent=0))

    assert result.hours_saved_per_year.value == 0
    assert result.cost_saved_per_year.value == 0
    assert result.payback_months.status is MetricStatus.NOT_COMPUTED
    assert "monthly savings are not positive" in (result.payback_months.reason or "")


def test_monthly_operating_days_are_derived_only_when_inputs_exist() -> None:
    """Expose an average derived month without rounding or an implicit default."""
    assert make_config(weeks_per_year=52).working_days_per_month == pytest.approx(
        260 / 12
    )
    assert make_config(work_days_per_week=None).working_days_per_month is None
