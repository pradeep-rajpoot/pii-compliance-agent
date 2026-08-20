# pii-compliance-agent

A web tool that lets a user upload a document (PDF, XLS/XLSX, CSV, DOCX, or
JSON), runs an LLM-based agent to detect PII, shows the detections inline in
the UI, and — on request — produces a downloadable, PII-safe copy with every
detected span masked with `X` characters.

Monorepo: `apps/api` (FastAPI backend) + `apps/web` (Next.js frontend). See
[`specs/mvp-spec.md`](specs/mvp-spec.md) for the full design spec.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python package/venv manager)
- [`pnpm`](https://pnpm.io/) (Node 20+)
- An AWS identity with `bedrock:InvokeModel` access to a Claude model in
  Amazon Bedrock (see [AWS / Bedrock access](#aws--bedrock-access) below)

## Setup

Clone, then from the repo root:

```bash
# Backend
cd apps/api
uv sync
cp .env.example .env   # fill in BEDROCK_REGION / BEDROCK_MODEL_ID at minimum
cd ../..

# Frontend
cd apps/web
pnpm install
cp .env.local.example .env.local.example
cd ../..
```

`BEDROCK_REGION` and `BEDROCK_MODEL_ID` have no defaults — the backend fails
fast at startup if either is missing, rather than silently talking to the
wrong region/model. See `apps/api/.env.example` for every configurable
value (upload size limit, job TTL, detection chunking, CORS origins, etc.).

AWS credentials are picked up from the standard credential chain (shared
`~/.aws/credentials` profile, env vars, SSO, etc.) — nothing AWS-specific is
hardcoded. `apps/web/.env.local.example` only needs `NEXT_PUBLIC_API_BASE_URL`
pointed at wherever the backend is running.

## Running

Start both apps together from the repo root:

```bash
pnpm dev
```

This runs the FastAPI backend on `http://127.0.0.1:8000` and the Next.js
frontend on `http://127.0.0.1:3000` via `scripts/dev.sh`. Ctrl-C stops both.

To run either one on its own:

```bash
pnpm dev:api   # backend only, --workers 1 (required -- see apps/api/README.md)
pnpm dev:web   # frontend only
```

Then open `http://localhost:3000`, upload a file, and watch it go
queued → detecting → detected (highlighted inline) → correcting → corrected
(downloadable).

## Testing

```bash
# Backend
cd apps/api && uv run pytest -v

# Frontend
cd apps/web && pnpm test
```

Neither test suite calls real Bedrock or needs network access — both mock
the LLM client. See each app's own README for more detail:
[`apps/api/README.md`](apps/api/README.md).

## AWS / Bedrock access

The backend calls Claude via Amazon Bedrock using the `anthropic` SDK's
`AnthropicBedrock` client, authenticated through your normal AWS credential
chain (no API key lives in `.env`). To refresh Chegg SSO credentials locally:

```bash
okta-aws <account-name> <role-name> <profile-name>   # e.g. see internal onboarding docs
```

To find a model you actually have access to invoke:

```bash
# List Claude models visible in a region
aws bedrock list-foundation-models --region us-west-2 \
  --query "modelSummaries[?contains(modelId,'claude')].modelId" --output table

# Newer models require a cross-region inference profile id, not the bare model id
aws bedrock list-inference-profiles --region us-west-2 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'claude')].inferenceProfileId" --output table
```

If you hit a `403`/`LLM_ERROR` mentioning **AWS Marketplace subscription**,
that's an account/IAM entitlement issue, not an app bug — check
**Bedrock → Model access** in the AWS Console for the account/region you're
using and (re-)request access to the Claude model in question.

## Notes

- **Don't commit `.env`/`.env.local`** — only the `.example` files are
  tracked. (`apps/api/.env` doesn't hold literal secrets today — Bedrock
  auth goes through AWS IAM, not a key in the file — but treat it as
  sensitive regardless and keep it out of git.)
- If your `pnpm install` fails against Chegg's CodeArtifact proxy with a
  `401`, your CodeArtifact login token has likely expired and needs
  refreshing before falling back to any other registry configuration.
