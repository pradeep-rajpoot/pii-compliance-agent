# PII Compliance Agent — Development Spec

Status: Draft v1
Owner: Pradeep
Repo: `pii-compliance-agent` (monorepo)

## 1. Overview

A web tool that lets a user upload a document (PDF, XLS/XLSX, CSV, or Word), runs an LLM-based agent to detect PII, shows the detections inline on the document in the UI, and — on request — runs a second agent that masks each detected PII span with `X` characters (same length as the original) and produces a downloadable, PII-safe copy of the file.

Two agents:
- **pii-detection-agent** — finds and classifies PII spans in the uploaded file.
- **pii-correction-agent** — takes the detection result and the original file, replaces each PII span with `X` × length, and writes a new file in the original format.

## 2. Goals / Non-Goals

**Goals**
- Support PDF, XLS/XLSX, CSV, DOCX upload and parsing.
- Detect common PII types (see §6.2) using an LLM (Claude models via Amazon Bedrock).
- Return detections with enough positional info for the frontend to highlight them inline, without re-uploading the file.
- Mask detected PII in a new copy of the file, preserving original layout/formatting as much as the file format allows.
- Handle detection/correction as async jobs with status polling (files may be large or LLM calls slow).

**Non-goals (this spec)**
- Authentication / access control (assumed to be handled by an upstream gateway or added later).
- Persistent storage of files or results — everything is ephemeral (§8).
- Multi-user collaboration, audit trail UI, or admin dashboard.
- Batch/bulk upload (single file per job for v1).

## 3. Tech Stack & Repo Structure

Monorepo, single repo `pii-compliance-agent`:

```
pii-compliance-agent/
├── apps/
│   ├── web/                 # Next.js frontend
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/              # API client, polling hooks
│   │   ├── package.json
│   │   └── ...
│   └── api/                  # FastAPI backend
│       ├── src/
│       │   ├── main.py
│       │   ├── routers/
│       │   ├── agents/
│       │   │   ├── detection_agent.py
│       │   │   └── correction_agent.py
│       │   ├── parsers/       # pdf.py, xlsx.py, csv.py, docx.py
│       │   ├── jobs/          # job store, worker
│       │   └── models/        # pydantic schemas
│       ├── pyproject.toml
│       └── uv.lock
├── packages/                 # shared types (optional, e.g. OpenAPI-generated TS types)
├── pnpm-workspace.yaml
├── package.json               # root, pnpm workspaces
└── README.md
```

- **Frontend**: pnpm workspaces, Next.js (App Router), TypeScript.
- **Backend**: Python, `uv` for dependency/venv management, FastAPI, served via `uvicorn`.
- **Agent/LLM**: Anthropic Claude models accessed via **Amazon Bedrock** (Bedrock Runtime `InvokeModel`/`Converse` API), not the direct Anthropic API. Backend calls Bedrock either via `boto3` (`bedrock-runtime` client) or the `anthropic` Python SDK's `AnthropicBedrock` client (which wraps the same Bedrock endpoint with the familiar Anthropic Messages API surface — preferred, to keep prompt/tool-use code portable if the team ever needs to point at the direct Anthropic API instead). Only used for detection (§6); correction itself is deterministic string replacement, not LLM-driven — see §7.
- **AWS access/config**: model access requires the target Bedrock model (e.g. `anthropic.claude-*` model ID for the region) to be enabled in the AWS account, plus IAM credentials/role with `bedrock:InvokeModel` (and `bedrock:InvokeModelWithResponseStream` if streaming) scoped to that model ARN. Region and model ID are read from environment/config (e.g. `BEDROCK_REGION`, `BEDROCK_MODEL_ID`), not hardcoded.
- **Job queue**: in-process async task (e.g. FastAPI `BackgroundTasks` or an in-memory `asyncio` task registry) is sufficient for v1 given ephemeral, single-instance scope. Documented as swappable for Redis/Celery if scaled later.

## 4. High-Level Architecture

```
┌────────────┐        upload         ┌─────────────────────┐
│  Next.js   │ ───────────────────▶  │      FastAPI         │
│  Frontend  │                       │                       │
│            │  ◀── job_id ──────────│  POST /jobs/detect    │
│            │                       │                       │
│            │  GET /jobs/{id}       │  detection_agent.py   │
│            │  (poll status) ─────▶ │   - parse file        │
│            │  ◀── status+result ───│   - call Bedrock       │
│            │                       │     (Claude)           │
│            │                       │   - map spans→offsets │
│            │                       │                       │
│  highlight │                       │                       │
│  inline    │                       │                       │
│            │  POST /jobs/correct   │  correction_agent.py  │
│            │  {job_id} ──────────▶ │   - mask spans in     │
│            │  ◀── job_id ──────────│     original file     │
│            │                       │   - write new file    │
│            │  GET /jobs/{id}       │                       │
│            │  poll → done ────────▶│  GET /files/{id}/     │
│            │  ◀── download link ───│    download           │
└────────────┘                       └─────────────────────┘
```

Files and job state live only in the backend process memory / local temp dir for the lifetime of the job (§8).

## 5. End-to-End Workflow

1. User opens the app, sees an upload dropzone restricted to `.pdf, .xls, .xlsx, .csv, .doc, .docx`.
2. Frontend uploads the file via `POST /api/jobs/detect` (multipart/form-data). Backend validates type/size, stores the file in a temp dir keyed by a generated `job_id`, and immediately returns `{ job_id, status: "queued" }`.
3. Backend kicks off the **pii-detection-agent** as a background task:
   a. Parse the file into extractable text + positional metadata depending on type (§6.1).
   b. Send the extracted text (chunked if needed) to Claude — invoked via Amazon Bedrock — with a structured-output prompt asking it to return PII spans (type, value, start/end offsets or cell/page/paragraph locators, confidence).
   c. Normalize the LLM output into a canonical `Detection[]` schema (§9.1) mapped back to positions in the original file structure (character offsets for text/CSV, cell refs for XLSX, page+bbox or paragraph index for PDF/DOCX).
   d. Persist result in the in-memory job store; set job status to `detected`.
4. Frontend polls `GET /api/jobs/{job_id}` every ~1.5s. On `status: "detected"`, it receives the detections plus a rendering payload (extracted text/HTML preview) and renders the document with PII spans highlighted inline (e.g. colored `<mark>` per PII type), each with a tooltip showing type/confidence.
5. UI shows a **"Convert to PII Safe"** button once detections are available (enabled even if zero PII found, to allow producing a pass-through copy — configurable).
6. On click, frontend calls `POST /api/jobs/{job_id}/correct`. Backend validates the job is in `detected` state, and starts the **pii-correction-agent** as a background task:
   a. Re-open the original file from the temp dir.
   b. For every `Detection`, replace the matched content with `"X" * len(detection.value)`, applied at the correct location for the file type (text offset splice for PDF/CSV/text extraction layer re-injected into PDF where feasible, cell value replacement for XLSX, run-level text replacement for DOCX preserving styling).
   c. Write the corrected file to the temp dir under a new file id; set job status to `corrected`, with a download URL/token.
7. Frontend polls until `status: "corrected"`, then enables/reveals the **"Download"** button pointing at `GET /api/jobs/{job_id}/download`.
8. Backend streams the corrected file with appropriate `Content-Type` and `Content-Disposition`, then marks the job for cleanup (temp files deleted immediately after successful download, or after a TTL — see §8).

## 6. pii-detection-agent

### 6.1 File Parsing (per type)

| Type | Library | Extraction unit | Positional metadata returned |
|---|---|---|---|
| PDF | `pypdf` / `pdfplumber` | text per page | page number + char offset (+ bbox if using pdfplumber, for future exact-highlight overlay) |
| XLSX/XLS | `openpyxl` (xlsx) / `xlrd` fallback (xls) | cell value | sheet name, cell ref (e.g. `Sheet1!B7`) |
| CSV | Python `csv` / `pandas` | cell value | row index, column name/index |
| DOCX | `python-docx` | paragraph / table cell text | paragraph index (or table/row/cell index), char offset within run |

All parsers output a common intermediate representation: a list of `TextBlock { id, text, locator }`, which is what gets sent to the LLM and later re-used by the correction agent to know where to splice masked text back in.

### 6.2 PII categories (v1)

Name, email address, phone number, physical address, SSN / national ID, date of birth, credit card / payment card number, bank account/routing number, IP address, driver's license number, passport number. Extensible via a config list without code changes to the prompt structure.

### 6.3 Detection approach

- Text blocks are batched into calls to Claude via **Amazon Bedrock** (respecting context window/cost limits) with a system prompt instructing the model to return **only** structured JSON (using Claude's tool-use/structured-output support, available through Bedrock's Converse API, to guarantee a parseable schema): a list of `{ block_id, matched_text, pii_type, start_offset, end_offset, confidence }`.
- Backend validates that `matched_text == block.text[start_offset:end_offset]` before accepting a detection (guards against LLM offset drift); mismatches trigger a fallback exact-string search within the block to re-anchor offsets, and unresolvable ones are dropped with a logged warning rather than corrupting the file later.
- Detections are deduplicated/merged (e.g. overlapping spans of the same type) before returning to the frontend.

### 6.4 Output payload to frontend

```json
{
  "job_id": "…",
  "status": "detected",
  "file_type": "docx",
  "blocks": [ { "id": "p12", "text": "…", "locator": {"paragraph": 12} } ],
  "detections": [
    {
      "id": "d1",
      "block_id": "p12",
      "pii_type": "email",
      "value": "jane.doe@example.com",
      "start_offset": 34,
      "end_offset": 55,
      "confidence": 0.97
    }
  ]
}
```

Frontend renders `blocks` as the document preview and overlays `detections` as highlighted spans within the matching block.

## 7. pii-correction-agent

Deliberately **deterministic, not LLM-driven** — it consumes the already-validated `Detection[]` from the detection step and performs plain string/cell replacement:

- Replacement value: `"X" * len(detection.value)` (length-preserving, per the spec).
- PDF: since PDFs aren't easily edited in place with reflow-safe text splicing, v1 approach is to re-render a new PDF from the extracted-and-masked text per page using a simple layout (documented limitation — exact visual fidelity isn't guaranteed for PDFs; flagged as a follow-up to investigate incremental PDF text replacement, e.g. via `pikepdf`/content-stream editing, if visual fidelity becomes a requirement).
- XLSX/CSV: direct cell value overwrite, preserving all other cells/formatting/formulas untouched.
- DOCX: run-level text replacement within the identified paragraph/run, preserving existing run formatting (bold/italic/font).
- After masking, the corrected file is written under a new `file_id`, and the job store records the download path and MIME type.

## 8. Ephemeral Storage & Data Handling

Per the "ephemeral only" decision:

- Uploaded originals and corrected outputs are written to a process-local temp directory (e.g. `tempfile.mkdtemp()` per job), never to a database or object store.
- Job metadata (status, detections, file paths) lives in an in-memory store (dict keyed by `job_id`), not persisted to disk beyond the temp files themselves.
- **Cleanup**: temp files + job entry are deleted immediately after a successful download, and independently via a background TTL sweep (e.g. every 10 min, delete jobs/files older than 30 min) to catch abandoned jobs.
- Because this service parses and holds real PII in memory/temp disk during processing, treat all uploaded files as sensitive by default: no logging of extracted text or detection `value` fields at info level (log only counts/types/positions), restrict temp dir permissions, and ensure the process isn't multi-tenant-shared without additional isolation. This aligns with Chegg's data-protection obligations for consumer/personal information — if this tool is later extended to persist files or add multi-user access, revisit encryption-at-rest and access-control requirements at that time.
- Single-instance/in-memory job store means this doesn't horizontally scale past one backend replica in v1 — documented as a known limitation, not a blocker for MVP.

## 9. API Contracts

### 9.1 `POST /api/jobs/detect`
Request: `multipart/form-data`, field `file`.
Response `202`:
```json
{ "job_id": "abc123", "status": "queued" }
```

### 9.2 `GET /api/jobs/{job_id}`
Response `200`:
```json
{
  "job_id": "abc123",
  "status": "queued | detecting | detected | correcting | corrected | failed",
  "file_type": "docx",
  "blocks": [...],
  "detections": [...],
  "error": null
}
```

### 9.3 `POST /api/jobs/{job_id}/correct`
No body required. Response `202`: `{ "job_id": "abc123", "status": "correcting" }`. Returns `409` if job isn't in `detected` state.

### 9.4 `GET /api/jobs/{job_id}/download`
Streams the corrected file (only valid once `status == "corrected"`); `404` otherwise. Sets `Content-Disposition: attachment; filename="<original-name>-pii-safe.<ext>"`.

### 9.5 Error model
All error responses: `{ "status": "failed", "error": { "code": "...", "message": "..." } }`, e.g. `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `PARSE_ERROR`, `LLM_ERROR`, `JOB_NOT_FOUND`.

## 10. Frontend Design (Next.js)

- **Pages/routes**: single-page flow at `/` (or `/scan`) — Upload → Review/Highlight → Download states driven by local state + job polling, no separate routes needed for v1.
- **Components**:
  - `UploadDropzone` — drag/drop + file picker, client-side validation of extension/size before upload.
  - `DocumentPreview` — renders `blocks` and overlays `<Highlight>` spans colored by `pii_type`, with a legend.
  - `ConvertButton` — disabled until `status === "detected"`, shows spinner while `correcting`.
  - `DownloadButton` — appears once `status === "corrected"`, links to the download endpoint.
  - `JobStatusBanner` — shows queued/detecting/correcting progress and surfaces `failed` errors.
- **Polling hook**: `useJobPolling(jobId)` — interval-based `GET /api/jobs/{id}`, stops on terminal states (`corrected`, `failed`), exposes `status`, `detections`, `error`.
- **State management**: local React state / `useReducer` for the single job flow is sufficient — no global store needed for v1.

## 11. Non-Functional Requirements

- **File size limit**: configurable, default 10 MB per upload (reject with `FILE_TOO_LARGE` above this).
- **Timeouts**: LLM calls wrapped with a timeout + single retry; job marked `failed` with `LLM_ERROR` on exhaustion.
- **Concurrency**: v1 assumes low concurrent job volume (internal tool); document as a scaling limitation given in-memory job store (§8).
- **Observability**: structured logs per job (`job_id`, stage, duration, detection count by type — not values), basic request logging in FastAPI.
- **Cost control**: cap number/size of LLM calls per job (chunking strategy), reject absurdly large files up front.

## 12. Testing Strategy

- **Backend unit tests**: parser tests per file type (fixtures with known PII placed at known offsets), offset-validation logic, correction/masking logic (assert length-preserving `X` replacement, assert non-PII content untouched).
- **Backend integration tests**: full `detect → correct → download` flow against the FastAPI app using `TestClient`/`httpx`, with the Bedrock/Claude call mocked (e.g. via `botocore.stub.Stubber` or a mocked `AnthropicBedrock` client) to return deterministic detections.
- **Frontend tests**: component tests for `DocumentPreview` highlighting given a fixed `detections` payload; polling hook tests with mocked fetch transitioning through job states.
- **Manual QA checklist**: one sample file per supported type, including edge cases — empty file, file with no PII, file exceeding size limit, unsupported extension.

## 13. Open Questions / Follow-Ups

- PDF visual fidelity after masking (re-render vs. in-place content-stream edit) — flagged in §7, needs a spike if pixel-perfect output is required.
- Whether "Convert to PII Safe" should be blocked when zero PII is detected, or always allowed to produce a pass-through copy.
- Job store backend if this needs to scale beyond a single instance (Redis-backed job queue + object storage would replace §8's in-memory/temp-disk approach).
- Auth/access control (explicitly out of scope here per current decision) — revisit before any external or multi-tenant exposure, given this handles PII.

---

*Note: this document is a design spec, not implementation. When building this out, generating the actual FastAPI/Next.js code in Code mode (Claude Code) against this repo is recommended over generating it in chat, so repo-specific lint/type/test conventions can be applied directly.*
