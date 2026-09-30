# Assumptions and unconfirmed inputs

This log records only provisional values or behavior. Explicit project decisions are
listed separately in the Phase 0 checkpoint and are not assumptions.

## Phase 0

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-001 | Derived operating days per month are `(work_days_per_week × weeks_per_year) ÷ 12`. The previously discussed 21.67 is only the arithmetic result for a five-day, 52-week year, not a configured client value. | Each client's operating week and year have not been confirmed; the latest instruction requires an empty config rather than defaults. | Leave `work_days_per_week` and `weeks_per_year` unset until confirmed. Show the derived monthly value only when both are available; any provisional input must be labeled `PLACEHOLDER` wherever used. |
| A-002 | `weeks_per_year` has no default value in the example client config. The previously discussed 52 is not a configured client value. | The client's applicable calendar has not been confirmed; the latest instruction requires an empty config rather than defaults. | Leave the field unset until confirmed. Any later provisional value must be labeled `PLACEHOLDER` in config, UI, and every report that uses it. |
| A-003 | No client currency, role hourly rates, verdict coverage percentages, or verdict implementation costs are currently known. | These are client-specific business inputs and have not been supplied. | Include the fields in the example config but leave their values empty. Do not substitute defaults or calculate affected financial figures. |

The example client config is to contain the requested fields, but no business-number
defaults. Any placeholder that is explicitly introduced later must be labeled
`PLACEHOLDER` everywhere it is displayed or reported.

## Phase 1

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-004 | The TOML example represents unset scalar inputs with empty strings and unset mappings with empty tables. | TOML has no `null` value; this is a serialization choice, not a client business value. | Config loading must map empty scalar strings to an unset value, never to zero or a usable default. Keep all business inputs visibly unconfigured until confirmed. |

## Phase 2

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-005 | Frequency units accepted for automatic annualization will be explicit daily, weekly, monthly, or yearly units; unsupported or ambiguous source wording will remain uncomputed. | Source materials can express cadence in many forms and no exhaustive unit vocabulary was approved. | Preserve the original unit and report a visible “not computed” reason for unrecognized units; do not infer a cadence. |
| A-006 | Run-duration units accepted for automatic conversion will be seconds, minutes, or hours. | No broader time-unit vocabulary was approved. | Preserve source wording and leave unsupported units uncomputed. |

## Phase 3

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-007 | The provider runtime should prefer the official SDKs when installed, but remain usable in offline environments by failing clearly if the SDK is absent. | The exact dependency set in the local environment has not been confirmed. | Keep provider imports optional at runtime, surface a clear install message instead of guessing, and rely on `LLM_MODEL` from the environment rather than hardcoded model names. |

## Phase 4

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-008 | The first document-ingestion implementation preserves source text and approximate line positions while remaining usable without optional ingestion dependencies installed. | The exact document corpus and ingestion environment were not in scope for the phase. | Keep `.txt`/`.docx`/`.pdf` reading explicit, surface clear runtime errors when optional dependencies are absent, and keep chunking deterministic and source-grounded. |

## Phase 5

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-009 | The classification rule set uses a primary verdict plus an optional secondary verdict, prefers the simplest viable automation pattern, and exposes an explicit `unclassified` state. | The final wording for the taxonomy and decision hierarchy was revised during Phase 5 review. | Keep the rule deterministic, require a reason when the verdict is `keep human`, and route `unclassified` outcomes to the gap report rather than forcing a guessed label. |

## Phase 6

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-010 | The UI and HTML export remain minimal, human-facing shells for review and report rendering; no PDF export or advanced styling has been approved yet. | The project has not yet chosen a final report-delivery design beyond the approved HTML-only output. | Keep the interface small and explicit, show the formula and assumptions in the report, and avoid adding PDF or extra UI features without a new decision. |

## Phase 7

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-011 | The evaluation harness compares extracted steps via the normalized process + actor + task key and reports step precision, recall, fabricated quotes, unverified quotes, and numeric/null-handling accuracy for a single run. | The specific benchmark corpus and provider set were not finalized beyond the fictional Harborlight demo and answer key. | Keep the evaluation result explicit and comparable across provider/model/prompt-version runs; do not hide a missing metric behind a guessed default. |

## Phase 8

| ID | Assumption or provisional value | Why it is unconfirmed | Required handling |
|---|---|---|---|
| A-012 | The README and final project narrative will describe the repository's validated scaffold and current evidence-backed workflow without claiming unrun live provider benchmarks or a deployment target. | No final deployment choice was approved, and the repository does not include a production benchmark run on real client data. | Keep the README factual, explicitly label fictional demo data and the evaluation harness output as benchmark-only, and avoid claiming any unmeasured production results. |

## Maintenance rule

Append a dated or phase-labeled row whenever implementation proceeds on an
unconfirmed fact. Resolve or retain each entry explicitly at later checkpoints.
