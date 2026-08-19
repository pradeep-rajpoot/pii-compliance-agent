# pii-compliance-agent API

FastAPI backend for the PII Compliance Agent. Parses an uploaded document
(PDF, XLSX, XLS, CSV, DOCX, JSON), runs an LLM-based detection agent (Claude via
Amazon Bedrock) to find PII spans, and — on request — deterministically
masks every detected span with `X` characters and produces a downloadable,
PII-safe copy of the file.

See `/specs/mvp-spec.md` at the repo root for the full design spec.

## Setup

```bash
cd apps/api
uv sync
cp .env.example .env   # then fill in BEDROCK_REGION / BEDROCK_MODEL_ID
```

`BEDROCK_REGION` and `BEDROCK_MODEL_ID` have no defaults and the app will
fail fast at startup if they aren't set — this is intentional, so the
service never silently talks to the wrong AWS account/region/model.

AWS credentials are picked up from the standard credential chain (env vars,
shared config/profile, instance/task role, etc.) — nothing AWS-specific is
hardcoded here.

## Running

```bash
uv run uvicorn src.main:app --reload --workers 1
```

**The server MUST run with `--workers 1`.** Job state lives in a single
in-process, in-memory `JobStore` (see §8 of the spec) — it is not shared
across worker processes. Running with more than one worker means requests
for the same `job_id` can land on a worker that has never heard of it.
Horizontal scaling beyond one instance is a known v1 limitation (documented
in the spec), not something to work around by adding workers.

## Testing

```bash
uv run pytest -v
```

Tests never call real Bedrock, even though this environment has real
credentials configured for production use — `tests/conftest.py` monkeypatches
the detection agent's client-construction point (`build_client`) with a
scripted fake client. The periodic TTL-sweep background task is also
disabled during tests.

## Known limitations / judgment calls

- **PDF fidelity**: masked PDFs are entirely re-rendered from extracted,
  masked text via `reportlab` using simple flowed text — this is *not*
  pixel-for-pixel identical to the original layout (fonts, tables, images,
  precise positioning are not preserved). This is a documented v1 tradeoff
  per spec §7/§13, not a bug.
- **Legacy `.xls` correction**: `.xls` (legacy binary Excel) is parsed for
  detection via `xlrd` (read-only), but there is no writer library for that
  binary format in this project's dependency set (only `xlwt`/`xlutils`
  could add that, and they weren't in scope). Detecting PII in a `.xls` file
  works end-to-end; requesting `/correct` on a `.xls` job fails with
  `CORRECTION_ERROR` and a clear message asking the user to re-save as
  `.xlsx`. `.doc` (legacy binary Word) is rejected outright at upload time
  with `UNSUPPORTED_FILE_TYPE` — only `.docx` is supported, per product
  decision.
- **DOCX scope**: only paragraph-level text (`document.paragraphs`) is
  parsed/masked in v1; text inside tables is not yet walked. The
  `DocxLocator` model already has `table`/`row`/`cell` fields reserved for
  that follow-up.
- **CORS**: enabled via `CORS_ALLOW_ORIGINS` (comma-separated) for direct
  frontend-to-API calls (no proxy).
- **JSON type fidelity**: any scalar leaf (string, number, boolean) in a
  `.json` upload is eligible for detection, but a masked leaf is always
  written back as a JSON string of `X`s — e.g. an SSN stored as a JSON
  number becomes `"XXXXXXXXX"`, not a masked number. Same tradeoff as
  xlsx formula-result cells.
