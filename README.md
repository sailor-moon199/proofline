# proofline

An evidence-backed AI opportunity audit tool for AI consultants.

proofline helps a consultant turn messy operating material into a prioritized
opportunity register: every item is tied to a source quote, every savings figure
is derived in pure Python from user-confirmed inputs, and every result exposes its
assumptions and reasons rather than hiding uncertainty.

This repository is intentionally designed around a hybrid workflow. A human enters
or verifies the structured step data first; extraction from .txt, .docx, and .pdf
files is treated as a pre-fill step, not as a source of trusted numbers without
confirmation. The model may suggest verdicts, but the actual savings computation
stays in deterministic Python code.

The Harborlight Logistics example is fictional and is not a real client or a real
report of real operational results.

Architecture overview

+-----------------------+
| Source material       |
| .txt / .docx / .pdf   |
| + manual form / CSV   |
+----------+------------+
           |
           v
+----------+------------+
| Ingestion + chunking   |
| preserve source pos    |
+----------+------------+
           |
           v
+----------+------------+
| Extraction + review    |
| evidence verification  |
| conflict detection     |
+----------+------------+
           |
           v
+----------+------------+
| Classification + risk  |
| verdict + suggestions   |
+----------+------------+
           |
           v
+----------+------------+
| Pure-Python scoring    |
| formulas + assumptions |
+----------+------------+
           |
           v
+----------+------------+
| HTML report + review  |
| table + gaps           |
+-----------------------+

Core principles

- The model does not compute savings figures.
- Missing, vague, or conflicting numeric facts stay visible as “not computed”.
- No business numbers are silently defaulted.
- Every step requires a human-confirmed review state before scoring.
- Every evidence item is checked against source text before it can contribute to a score.
- Provider and model choices live in environment/config values rather than in code.
- Real client documents are not sent to a cloud provider without an explicit confirmation step.

Repository layout

- config/ — client TOML example and settings templates
- demo_data/harborlight/ — fictional demo input documents
- docs/ — verified third-party fact sheet, assumptions, decisions, and gold answer key
- prompts/ — prompt files live at the repo root for this phase
- src/proofline/ — package modules for models, intake, ingress, extraction, scoring, providers, UI, reports, and evaluation
- tests/ — offline validation suite
- .github/workflows/tests.yml — CI workflow that runs pytest without network access

Quick start

1. Copy the environment template:
   - copy .env.example to .env and fill in only the values you actually use locally
2. Set provider configuration:
   - LLM_PROVIDER=gemini or claude or ollama
   - LLM_MODEL=<provider model name from config>
   - GEMINI_API_KEY or ANTHROPIC_API_KEY if you are using a cloud provider
3. Install dependencies:
   - python -m pip install --editable ".[test]"
4. Run the offline suite:
   - python -m pytest
5. Run the app:
   - streamlit run src/proofline/ui/streamlit_app.py

Usage notes

- The form-first path works without any LLM provider.
- Document ingestion is a pre-fill step for an editable review table.
- Human review is required before scoring and before any converted result is treated as a final opportunity.
- The evaluation harness expects a gold key under docs/eval/gold.json and compares step matches using the normalized process + actor + task key.

Privacy and data handling stance

This project intentionally treats AI processing as a user-controlled step. It does
not ship secret keys or credentials in the repo, reads API keys from environment
variables only, and prints the provider/model choice before a run without exposing
secrets. With the project rules in place, the default expectation is that no real
client document is sent to a cloud provider unless the user explicitly confirms the
processing choice at the time of use.

Known limitations and failure modes

- Document ingestion can only read formats it has a verified parser for: .txt, .docx, and .pdf.
- Unsupported or ambiguous cadence units and duration units stay uncomputed instead of being guessed.
- If a model or provider is unavailable or rate-limited, the code raises a visible failure; it does not silently substitute a value.
- PDF extraction depends on the underlying library's quality and the nature of the source file; machine-generated PDFs are significantly easier to parse than scanned documents.
- The current HTML report is intentionally minimal and remains within the approved HTML-only delivery scope.
- The current project does not claim a production deployment target, and no deployment is configured by default.

Evaluation status

The repository includes the evaluation harness and a fictional Harborlight demo key,
but it does not claim live provider benchmark numbers. The actual evaluation runs
that the project can compare are the ones produced by the user after they run the
harness against a chosen provider model and prompt version. This keeps performance
reporting grounded in the repo's own benchmark outputs instead of invented or
copy-pasted numbers.

CI and offline validation

The GitHub Actions workflow runs the tests on Windows and Ubuntu with the project
installed as an editable package and with outbound network access blocked. This is
how the project enforces the offline-by-default rule during CI.

A note on the current implementation

The project is a working scaffold and a validated core engine with hybrid intake,
scoring, classification, evaluation, UI, and report modules. It is intentionally
structured to stay modular and to keep the model layer separate from the plain-Python
scoring logic.
