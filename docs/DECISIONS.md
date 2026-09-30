# Project decisions

Confirmed by the project owner before and during the project.

| Topic | Decision |
|---|---|
| Project name | `proofline` |
| License and copyright | MIT; Copyright (c) 2026 Levi Okpanachi |
| Python | Minimum `>=3.12`; local development uses the installed stable version at or above that minimum |
| Development OS | Windows |
| Package manager | pip |
| UI | Streamlit page |
| Report | HTML only |
| Fictional demo | Harborlight Logistics, a fictional small freight-forwarding and road-haulage company |
| Frequency semantics | Total runs for the step across the team |
| Frequency basis schema field | Required `frequency_basis`, with `total` and `per_person` values; the form/extraction path must set it explicitly |
| Calendar normalization | “Per day” means client operating day; annual operating days are `work_days_per_week × weeks_per_year`, so a seven-day operation needs no separate calendar-day setting. Derived working days per month are that product divided by 12. No defaults in the example config. |
| Currency and labor rate | Client-configured currency and per-role hourly rates; leave unset until supplied |
| Coverage and implementation cost | Per-verdict client configuration; leave unset until supplied |
| Deployment | None chosen; revisit after Phase 8 |
| Prompts | Keep `prompts/` at repository root for now; do not claim root prompt files are included in a built wheel |
| Phase 1 layout | Use the approved `config/`, `demo_data/harborlight/`, `docs/`, `prompts/`, ten `src/proofline/` modules, `tests/`, `.github/workflows/`, and approved root files |
| Phase 1 CI | Run tests with outbound socket connections blocked on both Windows and Ubuntu, without API calls or configured secrets |
| Phase 1 architecture test | Scoring code must not import provider code |
| Phase 1 test organization | Each of the ten modules has its own test file |
| Phase 1 build backend | Setuptools, approved for use with pip and the `src/` package layout |
| Phase 1 dependencies | Pydantic for schemas, pytest for tests, and setuptools as the approved build backend; request approval before adding other dependencies |
| Phase 1 local verification runtime | Python 3.13.15 |
| Phase 2 daily frequency | Treat “per day” as a client operating day. Annualize with `work_days_per_week × weeks_per_year`; a seven-day operation uses `work_days_per_week = 7`. Derive average operating days per month by dividing annual operating days by 12. |
| Phase 2 scoring gate | Require a human-confirmed step and all its attached quotes verified before scoring. |
| Phase 2 frequency-basis behavior | Multiply frequency by `people_doing_it` only when `frequency_basis = per_person`; team-total frequency does not use the people count. |
| Phase 2 recognized units | Frequency: explicit day/week/month/year forms; duration: seconds/minutes/hours and documented abbreviations. Unsupported wording is not inferred and yields “not computed.” |
| Phase 2 coverage scale | Coverage is configured as a percentage from 0 through 100 and divided by 100 in the savings formula. |
| Phase 2 verdict config keys | Coverage and implementation-cost tables use the exact taxonomy labels as keys to avoid an implicit verdict-name mapping. |
