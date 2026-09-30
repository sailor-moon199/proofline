"""Load and validate client scoring settings from TOML."""

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from proofline.models.client_config import ClientConfig


class ClientConfigLoadError(ValueError):
    """Identify an unreadable or invalid client configuration file."""


def load_client_config(path: Path) -> ClientConfig:
    """Load client scoring settings, mapping blank TOML values to unset fields."""
    try:
        with path.open("rb") as config_file:
            raw_config = tomllib.load(config_file)
    except OSError as exc:
        raise ClientConfigLoadError(
            f"Cannot read client configuration at {path}: {exc}"
        ) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ClientConfigLoadError(
            f"Client configuration at {path} is invalid TOML: {exc}"
        ) from exc

    _reject_unknown_keys(
        raw_config,
        {
            "client",
            "calendar",
            "finance",
            "coverage_by_verdict",
            "implementation_cost_by_verdict",
        },
        "root",
        path,
    )
    client = _section(raw_config, "client", path)
    calendar = _section(raw_config, "calendar", path)
    finance = _section(raw_config, "finance", path)
    coverage = _section(raw_config, "coverage_by_verdict", path)
    costs = _section(raw_config, "implementation_cost_by_verdict", path)
    _reject_unknown_keys(client, {"name"}, "client", path)
    _reject_unknown_keys(
        calendar,
        {"work_days_per_week", "weeks_per_year"},
        "calendar",
        path,
    )
    _reject_unknown_keys(finance, {"currency", "role_hourly_rates"}, "finance", path)

    data: dict[str, object] = {
        "client_name": client.get("name"),
        "work_days_per_week": _blank_to_none(calendar.get("work_days_per_week")),
        "weeks_per_year": _blank_to_none(calendar.get("weeks_per_year")),
        "currency": _blank_to_none(finance.get("currency")),
        "role_hourly_rates": _normalize_numeric_mapping(
            finance.get("role_hourly_rates"), "finance.role_hourly_rates", path
        ),
        "coverage_by_verdict": _normalize_numeric_mapping(
            coverage, "coverage_by_verdict", path
        ),
        "implementation_cost_by_verdict": _normalize_numeric_mapping(
            costs, "implementation_cost_by_verdict", path
        ),
    }
    try:
        return ClientConfig.model_validate(data)
    except ValidationError as exc:
        raise ClientConfigLoadError(
            f"Client configuration at {path} failed validation: {exc}"
        ) from exc


def _section(
    config: Mapping[str, object],
    name: str,
    path: Path,
) -> Mapping[str, object]:
    """Return a required TOML table or raise a labeled configuration error."""
    value = config.get(name)
    if not isinstance(value, Mapping):
        raise ClientConfigLoadError(
            f"Client configuration at {path} must contain a [{name}] table."
        )
    return cast(Mapping[str, object], value)


def _reject_unknown_keys(
    config: Mapping[str, object],
    allowed_keys: set[str],
    section_name: str,
    path: Path,
) -> None:
    """Reject misspelled or unsupported keys instead of silently ignoring them."""
    unexpected_keys = set(config).difference(allowed_keys)
    if unexpected_keys:
        rendered_keys = ", ".join(sorted(unexpected_keys))
        raise ClientConfigLoadError(
            f"Client configuration at {path} has unexpected key(s) in "
            f"{section_name}: {rendered_keys}."
        )


def _normalize_numeric_mapping(
    value: object,
    key: str,
    path: Path,
) -> dict[str, object]:
    """Validate a TOML table and represent its blank entries as unset."""
    if not isinstance(value, Mapping):
        raise ClientConfigLoadError(
            f"Client configuration at {path} must define {key} as a table."
        )
    return {
        str(item_key): _blank_to_none(item_value)
        for item_key, item_value in value.items()
    }


def _blank_to_none(value: object) -> object:
    """Convert only empty or whitespace-only strings to an unset value."""
    if isinstance(value, str) and value.strip() == "":
        return None
    return value
