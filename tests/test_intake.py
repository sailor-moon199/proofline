"""Tests for manual, CSV, and client-configuration intake."""

import csv
from io import StringIO
from pathlib import Path

import pytest

from proofline.intake import (
    ClientConfigLoadError,
    IntakeDataError,
    IntakeValidationError,
    load_client_config,
    read_steps_csv,
    validate_form_entry,
    write_steps_csv,
)
from proofline.models import (
    ClientConfig,
    Evidence,
    FrequencyBasis,
    ProcessStep,
    QuantityField,
    QuantityStatus,
    ReviewStatus,
)


def make_step() -> ProcessStep:
    """Create a fully populated process step for intake round-trip tests."""
    return ProcessStep(
        step_id="step-1",
        process="Shipment booking",
        department=None,
        actor="Coordinator",
        task="Enter shipment details",
        tools=["TMS", "Email"],
        frequency=QuantityField(
            value=4,
            unit="per week",
            status=QuantityStatus.STATED,
            raw_text="four times per week",
        ),
        frequency_basis=FrequencyBasis.TOTAL,
        minutes_per_run=QuantityField(
            value=15,
            unit="minutes",
            status=QuantityStatus.USER_ENTERED,
            raw_text=None,
        ),
        people_doing_it=QuantityField(
            value=None,
            unit=None,
            status=QuantityStatus.UNKNOWN,
            raw_text=None,
        ),
        error_rate=QuantityField(
            value=None,
            unit=None,
            status=QuantityStatus.VAGUE,
            raw_text="a few errors each month",
        ),
        handles_sensitive_data=None,
        evidence=[
            Evidence(
                document="interview.txt",
                location="line 8",
                quote="We book four shipments per week.",
                verified=True,
            )
        ],
        review_status=ReviewStatus.EDITED,
        conflicts=[],
    )


def make_config_toml() -> str:
    """Return a test-only config with explicit confirmed values."""
    return """
[client]
name = "Test Client"

[calendar]
work_days_per_week = 5
weeks_per_year = 50

[finance]
currency = "GBP"
role_hourly_rates = { Coordinator = 40 }

[coverage_by_verdict]
"rules-based automation" = 50
"LLM/generative" = ""
"classic ML" = ""
"RPA/integration" = ""
"keep human" = ""

[implementation_cost_by_verdict]
"rules-based automation" = 2400
"LLM/generative" = ""
"classic ML" = ""
"RPA/integration" = ""
"keep human" = ""
"""


def replace_csv_cell(csv_text: str, column: str, value: str) -> str:
    """Replace a CSV cell while preserving correct CSV quoting."""
    reader = csv.DictReader(StringIO(csv_text))
    if reader.fieldnames is None:
        raise AssertionError("test CSV must have a header")
    rows = list(reader)
    rows[0][column] = value
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def test_manual_form_validates_against_shared_process_model() -> None:
    """Use the same schema for manual form input and downstream processing."""
    step = make_step()

    assert validate_form_entry(step.model_dump()).step_id == step.step_id


def test_manual_form_reports_validation_errors() -> None:
    """Surface an invalid form payload as a labeled intake error."""
    with pytest.raises(IntakeValidationError, match="Invalid process-step form"):
        validate_form_entry({"step_id": "incomplete"})


def test_csv_round_trip_preserves_fields_and_unknown_values() -> None:
    """Keep evidence, units, and null numeric inputs through CSV editing."""
    step = make_step()
    destination = StringIO()
    write_steps_csv([step], destination)

    imported = read_steps_csv(StringIO(destination.getvalue()))

    assert imported == [step]
    assert imported[0].people_doing_it.value is None
    assert imported[0].error_rate.raw_text == "a few errors each month"


def test_csv_rejects_invalid_json_with_row_and_column() -> None:
    """Expose malformed list data rather than silently substituting empty lists."""
    step = make_step()
    destination = StringIO()
    write_steps_csv([step], destination)
    malformed_csv = replace_csv_cell(destination.getvalue(), "tools", "{broken")

    with pytest.raises(IntakeDataError, match="row 2: column 'tools'.*invalid JSON"):
        read_steps_csv(StringIO(malformed_csv))


def test_csv_rejects_invalid_boolean() -> None:
    """Do not interpret unrecognized boolean text as a default value."""
    step = make_step()
    destination = StringIO()
    write_steps_csv([step], destination)
    malformed_csv = replace_csv_cell(
        destination.getvalue(),
        "handles_sensitive_data",
        "maybe",
    )

    with pytest.raises(IntakeDataError):
        read_steps_csv(StringIO(malformed_csv))


def test_example_config_loader_keeps_empty_values_unset(tmp_path: Path) -> None:
    """Map blank template values to unset values, never to zero."""
    config_path = tmp_path / "client.toml"
    config_path.write_text(
        Path("config/client.example.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    config = load_client_config(config_path)

    assert config.work_days_per_week is None
    assert config.weeks_per_year is None
    assert config.currency is None
    assert config.coverage_by_verdict["rules-based automation"] is None
    assert config.operating_days_per_year is None
    assert config.working_days_per_month is None


def test_config_loader_parses_values_and_derives_days_without_defaults(
    tmp_path: Path,
) -> None:
    """Compute operating days from confirmed client inputs and a test fixture."""
    config_path = tmp_path / "client.toml"
    config_path.write_text(make_config_toml(), encoding="utf-8")

    config = load_client_config(config_path)

    assert config.client_name == "Test Client"
    assert config.operating_days_per_year == 250
    assert config.working_days_per_month == pytest.approx(250 / 12)
    assert config.currency == "GBP"
    assert config.role_hourly_rates["Coordinator"] == 40


def test_config_loader_labels_malformed_file(tmp_path: Path) -> None:
    """Expose invalid TOML with the affected client-config path."""
    config_path = tmp_path / "broken.toml"
    config_path.write_text("not = [valid", encoding="utf-8")

    with pytest.raises(ClientConfigLoadError, match="invalid TOML"):
        load_client_config(config_path)


def test_config_loader_rejects_unknown_keys_instead_of_ignoring_them(
    tmp_path: Path,
) -> None:
    """Make spelling errors in a client configuration visible."""
    config_path = tmp_path / "client.toml"
    config_path.write_text(
        make_config_toml().replace("work_days_per_week", "work_day_per_week"),
        encoding="utf-8",
    )

    with pytest.raises(
        ClientConfigLoadError,
        match="unexpected key.*work_day_per_week",
    ):
        load_client_config(config_path)


def test_config_rejects_coverage_above_one_hundred_percent() -> None:
    """Prevent invalid coverage input from inflating savings calculations."""
    with pytest.raises(ValueError, match="must not exceed 100 percent"):
        ClientConfig(
            client_name="Test",
            work_days_per_week=5,
            weeks_per_year=52,
            currency="GBP",
            role_hourly_rates={},
            coverage_by_verdict={"automation": 101},
            implementation_cost_by_verdict={},
        )
