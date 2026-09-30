"""Explicit conversions for supported source frequency and duration units."""

from collections.abc import Mapping


FREQUENCY_UNITS: Mapping[str, str] = {
    "day": "day",
    "daily": "day",
    "per day": "day",
    "per operating day": "day",
    "per working day": "day",
    "week": "week",
    "weekly": "week",
    "per week": "week",
    "month": "month",
    "monthly": "month",
    "per month": "month",
    "year": "year",
    "yearly": "year",
    "annually": "year",
    "per year": "year",
    "per annum": "year",
}

DURATION_UNITS_TO_MINUTES: Mapping[str, float] = {
    "second": 1 / 60,
    "seconds": 1 / 60,
    "sec": 1 / 60,
    "secs": 1 / 60,
    "minute": 1,
    "minutes": 1,
    "min": 1,
    "mins": 1,
    "hour": 60,
    "hours": 60,
    "hr": 60,
    "hrs": 60,
}


def annualize_frequency_unit(
    unit: str | None,
    *,
    work_days_per_week: float | None,
    weeks_per_year: float | None,
) -> tuple[float | None, str | None, str | None]:
    """Return the annual multiplier, unit kind, and any visible failure reason."""
    if unit is None or unit.strip() == "":
        return None, None, "frequency unit is missing"

    normalized_unit = " ".join(unit.casefold().split())
    frequency_kind = FREQUENCY_UNITS.get(normalized_unit)
    if frequency_kind is None:
        return None, None, f"unsupported frequency unit {unit!r}"
    if frequency_kind == "day":
        if work_days_per_week is None:
            return None, frequency_kind, "client work_days_per_week is not configured"
        if weeks_per_year is None:
            return None, frequency_kind, "client weeks_per_year is not configured"
        return work_days_per_week * weeks_per_year, frequency_kind, None
    if frequency_kind == "week":
        if weeks_per_year is None:
            return None, frequency_kind, "client weeks_per_year is not configured"
        return weeks_per_year, frequency_kind, None
    if frequency_kind == "month":
        return 12, frequency_kind, None
    return 1, frequency_kind, None


def duration_to_minutes(unit: str | None) -> tuple[float | None, str | None]:
    """Return a supported duration conversion multiplier or a visible reason."""
    if unit is None or unit.strip() == "":
        return None, "duration unit is missing"
    normalized_unit = unit.casefold().strip()
    multiplier = DURATION_UNITS_TO_MINUTES.get(normalized_unit)
    if multiplier is None:
        return None, f"unsupported duration unit {unit!r}"
    return multiplier, None
