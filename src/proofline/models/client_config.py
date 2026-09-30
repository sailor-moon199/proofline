"""Validated client-specific calendar and financial settings."""

from math import isfinite

from pydantic import BaseModel, ConfigDict, StrictFloat, StrictInt, model_validator

NumericSetting = StrictInt | StrictFloat | None


class ClientConfig(BaseModel):
    """Hold client-confirmed scoring inputs without business-number defaults."""

    model_config = ConfigDict(extra="forbid")

    client_name: str
    work_days_per_week: NumericSetting
    weeks_per_year: NumericSetting
    currency: str | None
    role_hourly_rates: dict[str, NumericSetting]
    coverage_by_verdict: dict[str, NumericSetting]
    implementation_cost_by_verdict: dict[str, NumericSetting]

    @model_validator(mode="after")
    def validate_configured_numbers(self) -> "ClientConfig":
        """Reject invalid configured values rather than silently accepting them."""
        if self.work_days_per_week is not None and not (
            0 < self.work_days_per_week <= 7
        ):
            raise ValueError("work_days_per_week must be greater than 0 and at most 7")
        if self.weeks_per_year is not None and self.weeks_per_year <= 0:
            raise ValueError("weeks_per_year must be greater than 0")

        numeric_values = [
            *self.role_hourly_rates.values(),
            *self.coverage_by_verdict.values(),
            *self.implementation_cost_by_verdict.values(),
        ]
        for value in numeric_values:
            if value is not None and (
                not isfinite(value) or value < 0
            ):
                raise ValueError(
                    "configured rates, coverage, and costs must be finite "
                    "and nonnegative"
                )

        for verdict_key, coverage in self.coverage_by_verdict.items():
            if coverage is not None and coverage > 100:
                raise ValueError(
                    f"coverage for {verdict_key!r} must not exceed 100 percent"
                )
        return self

    @property
    def operating_days_per_year(self) -> float | None:
        """Return confirmed operating days per year, or `None` if unconfigured."""
        if self.work_days_per_week is None or self.weeks_per_year is None:
            return None
        return float(self.work_days_per_week * self.weeks_per_year)

    @property
    def working_days_per_month(self) -> float | None:
        """Derive average operating days per month without a default value."""
        operating_days_per_year = self.operating_days_per_year
        if operating_days_per_year is None:
            return None
        return operating_days_per_year / 12
