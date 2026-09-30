# Verified external APIs and libraries

Checked 2026-09-30 against the official sources below. Model catalogs, SDKs, quotas,
and APIs can change; recheck before implementation and before choosing a model.

## Gemini

- Google recommends the official `google-genai` Python SDK and the official
  Interactions API quickstart. The Python example creates `genai.Client()`, reads
  the API key from the environment, and calls the model through
  `client.models.generate_content(...)`.
- The official docs also describe structured output support and JSON-schema
  response handling; when the model is configured to return JSON, the SDK can be
  paired with a Pydantic schema and validation in application code.
- The current model catalog lists Gemini 3 and Gemini 2.5 Flash-family entries, and
  the live provider smoke test showed that older 2.5 model names can be rejected for
  new-user access. Model availability is account-, tier-, and region-specific; the
  app must not hardcode a model name and must read `LLM_MODEL` from config or the
  environment.
- The docs state that request limits vary by model, project, and usage tier; there is
  no single stable numeric quota suitable for an app default. Free-tier quotas can
  also change by account and usage pattern.
- The pricing docs reinforce that real client content requires explicit confirmation
  before any cloud provider call. The free tier is not treated as a default
  production path for client material.

Sources:

- [Google GenAI SDK libraries](https://ai.google.dev/gemini-api/docs/libraries)
- [Gemini Python quickstart](https://ai.google.dev/gemini-api/docs/get-started)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini models](https://ai.google.dev/gemini-api/docs/models)
- [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Gemini pricing and data use](https://ai.google.dev/gemini-api/docs/pricing)

The official quickstart uses `GEMINI_API_KEY` in the environment and treats the model
name as configuration rather than a hardcoded app default.

## Anthropic

- Anthropic publishes an official Python SDK for its Messages API.
- The documented Python structured-output method is
  `client.messages.parse(...)`, with a Pydantic model passed as `output_format`.
  The SDK sends the schema using `output_config.format` and returns a parsed result.
- The current model overview lists IDs including `claude-opus-5-5`,
  `claude-sonnet-5-5`, `claude-fable-5-1`, and `claude-haiku-4-5-20251001`.
  These are examples only; the application will not hardcode a model name.

Sources:

- [Anthropic Python SDK](https://platform.claude.com/docs/en/cli-sdks-libraries/sdks/python)
- [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic model overview](https://platform.claude.com/docs/en/models/overview)

The official Python SDK example reads `ANTHROPIC_API_KEY` from the process
environment. Its suggestion to use `python-dotenv` is optional; that package is not
included in Phase 1 dependencies.

## Ollama

- The local Ollama API exposes chat at `http://localhost:11434/api/chat`.
- Its local structured-output documentation accepts a JSON Schema in the request's
  `format` field, and demonstrates using a Pydantic model's `model_json_schema()`.
- Ollama's documentation explicitly says Ollama Cloud does not currently support
  structured outputs. Schema-constrained output is therefore documented for the
  local API, not the hosted cloud service.

Sources:

- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

## Document ingestion

- `python-docx` opens a `.docx` from a path or file-like object using
  `docx.Document(...)`; its document API exposes document paragraphs and related
  structures. The pipeline can preserve deterministic paragraph-derived text
  locations; it must not claim rendered page numbers that this extraction did not
  establish.
- `pdfplumber.open(...)` accepts a PDF path or file-like object and exposes pages;
  page text can be extracted with the page text API. Its project documentation says
  it works best with machine-generated PDFs rather than scanned PDFs. Scanned-PDF
  OCR support is not part of this verified capability.

Sources:

- [python-docx quickstart](https://python-docx.readthedocs.io/en/latest/user/quickstart.html)
- [python-docx Document API](https://python-docx.readthedocs.io/en/latest/api/document.html)
- [pdfplumber documentation](https://github.com/jsvine/pdfplumber)

## Streamlit

- The official API provides `st.data_editor` for editing dataframes and other
  supported data structures in a table-like UI, matching the planned human review
  table.
- The official `st.file_uploader` API is available for document intake.

Sources:

- [Streamlit `st.data_editor`](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)
- [Streamlit `st.file_uploader`](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader)

## Packaging follow-up

The official Python Packaging User Guide recommends declaring project metadata in the
`[project]` table and a build backend in `[build-system]`. Setuptools documents
package data as files associated with packages; its automatic package-data behavior
does not make an unrelated repository-root `prompts/` directory importable as package
resources.

Decision for this phase: keep `prompts/` at the repository root as requested, and
resolve it from the project root while running from a checkout. Do not claim that
root prompts are available in a built wheel. Before adding installed-wheel support,
choose and test an explicit packaging strategy (for example, relocating prompt data
into the Python package or declaring and resolving a distribution data-files
location). The prompt directory is currently empty.

Source: [Python Packaging User Guide: Writing your `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/);
[Setuptools: Data Files Support](https://setuptools.pypa.io/en/latest/userguide/datafiles.html).

The setuptools guide distinguishes package data from general data files and explains
the `pyproject.toml` `include-package-data` behavior for files associated with
packages. Root-level prompt files therefore remain available only from a source
checkout under this phase's decision; wheel inclusion and runtime lookup need a
separately tested strategy before distribution.

## Phase 1 validation and CI

- Pydantic documents `BaseModel` schemas with annotated fields and custom model
  validators for cross-field constraints. The quantity schema uses these mechanisms
  to reject inconsistent value/status combinations.
- GitHub's official Python CI guide recommends `actions/setup-python` for selecting
  the interpreter. The workflow tests Python 3.12 on Windows and Ubuntu, installs
  project/test dependencies, and then runs pytest with outbound socket connections
  blocked and without API credentials or LLM calls. Dependency installation happens
  before the network-blocked test step.

Sources:

- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- [Pydantic validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [GitHub Actions: Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
