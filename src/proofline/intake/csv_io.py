"""CSV import and export for the editable process-step intake path."""

import csv
import json
from collections.abc import Iterable
from json import JSONDecodeError
from typing import TextIO

from pydantic import ValidationError

from proofline.models.process_step import ProcessStep

from proofline.intake.validation import IntakeValidationError


class IntakeDataError(ValueError):
    """Identify malformed CSV data with the affected row or column."""


QUANTITY_FIELDS = (
    "frequency",
    "minutes_per_run",
    "people_doing_it",
    "error_rate",
)
CSV_FIELDS = (
    "step_id",
    "process",
    "department",
    "actor",
    "task",
    "tools",
    "frequency_basis",
    *(f"{name}_{part}" for name in QUANTITY_FIELDS for part in (
        "value",
        "unit",
        "status",
        "raw_text",
    )),
    "handles_sensitive_data",
    "evidence",
    "review_status",
    "conflicts",
)


def read_steps_csv(source: TextIO) -> list[ProcessStep]:
    """Read and validate all process steps from a flattened CSV template."""
    reader = csv.DictReader(source)
    headers = reader.fieldnames
    if headers is None:
        raise IntakeDataError("CSV has no header row.")
    if len(headers) != len(set(headers)):
        raise IntakeDataError("CSV contains duplicate column names.")

    missing_headers = set(CSV_FIELDS).difference(headers)
    unexpected_headers = set(headers).difference(CSV_FIELDS)
    if missing_headers or unexpected_headers:
        details: list[str] = []
        if missing_headers:
            details.append(f"missing columns: {', '.join(sorted(missing_headers))}")
        if unexpected_headers:
            details.append(
                f"unexpected columns: {', '.join(sorted(unexpected_headers))}"
            )
        raise IntakeDataError(f"Invalid CSV header: {'; '.join(details)}.")

    steps: list[ProcessStep] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise IntakeDataError(
                f"CSV row {row_number} has more values than header columns."
            )
        if all(value is None or value == "" for value in row.values()):
            continue
        try:
            steps.append(_step_from_row(row))
        except IntakeDataError as exc:
            raise IntakeDataError(f"CSV row {row_number}: {exc}") from exc
        except IntakeValidationError as exc:
            raise IntakeDataError(f"CSV row {row_number}: {exc}") from exc
    return steps


def write_steps_csv(steps: Iterable[ProcessStep], destination: TextIO) -> None:
    """Write process steps using the flattened CSV format accepted by the reader."""
    writer = csv.DictWriter(destination, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for step in steps:
        data = step.model_dump(mode="json")
        row: dict[str, str] = {
            "step_id": data["step_id"],
            "process": data["process"],
            "department": data["department"] or "",
            "actor": data["actor"],
            "task": data["task"],
            "tools": json.dumps(data["tools"], ensure_ascii=False),
            "frequency_basis": data["frequency_basis"],
            "handles_sensitive_data": _format_optional_bool(
                data["handles_sensitive_data"]
            ),
            "evidence": json.dumps(data["evidence"], ensure_ascii=False),
            "review_status": data["review_status"],
            "conflicts": json.dumps(data["conflicts"], ensure_ascii=False),
        }
        for field_name in QUANTITY_FIELDS:
            quantity = data[field_name]
            for part in ("value", "unit", "status", "raw_text"):
                value = quantity[part]
                row[f"{field_name}_{part}"] = "" if value is None else str(value)
        writer.writerow(row)


def _step_from_row(row: dict[str | None, str | None]) -> ProcessStep:
    """Convert one flattened CSV row into a validated process step."""
    entry: dict[str, object] = {
        "step_id": row["step_id"] or "",
        "process": row["process"] or "",
        "department": _optional_text(row["department"]),
        "actor": row["actor"] or "",
        "task": row["task"] or "",
        "tools": _parse_json_column(row, "tools"),
        "frequency_basis": row["frequency_basis"],
        "handles_sensitive_data": _parse_optional_bool(
            row["handles_sensitive_data"]
        ),
        "evidence": _parse_json_column(row, "evidence"),
        "review_status": row["review_status"],
        "conflicts": _parse_json_column(row, "conflicts"),
    }
    for field_name in QUANTITY_FIELDS:
        entry[field_name] = {
            "value": _parse_optional_number(row[f"{field_name}_value"], field_name),
            "unit": _optional_text(row[f"{field_name}_unit"]),
            "status": row[f"{field_name}_status"],
            "raw_text": _optional_text(row[f"{field_name}_raw_text"]),
        }
    try:
        return ProcessStep.model_validate(entry)
    except ValidationError as exc:
        raise IntakeValidationError(f"invalid process-step data: {exc}") from exc


def _parse_json_column(
    row: dict[str | None, str | None],
    column: str,
) -> object:
    """Decode one JSON-encoded CSV cell or return an explicit empty collection."""
    raw_value = row[column]
    if raw_value is None or raw_value == "":
        return [] if column in {"tools", "evidence", "conflicts"} else None
    try:
        return json.loads(raw_value)
    except JSONDecodeError as exc:
        raise IntakeDataError(
            f"column {column!r} contains invalid JSON at character {exc.pos}."
        ) from exc


def _parse_optional_number(
    raw_value: str | None,
    field_name: str,
) -> int | float | None:
    """Parse a numeric CSV cell without treating blank text as zero."""
    if raw_value is None or raw_value.strip() == "":
        return None
    try:
        value = json.loads(raw_value)
    except JSONDecodeError as exc:
        raise IntakeDataError(
            f"column {field_name + '_value'!r} must contain a JSON number."
        ) from exc
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise IntakeDataError(
            f"column {field_name + '_value'!r} must contain a JSON number."
        )
    return value


def _parse_optional_bool(raw_value: str | None) -> bool | None:
    """Parse an optional boolean CSV cell without guessing."""
    if raw_value is None or raw_value.strip() == "":
        return None
    normalized = raw_value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise IntakeDataError(
        "column 'handles_sensitive_data' must be true, false, or blank."
    )


def _optional_text(raw_value: str | None) -> str | None:
    """Map blank CSV text to an absent optional field."""
    if raw_value is None or raw_value == "":
        return None
    return raw_value


def _format_optional_bool(value: bool | None) -> str:
    """Format an optional boolean as a CSV cell."""
    if value is None:
        return ""
    return str(value).lower()
