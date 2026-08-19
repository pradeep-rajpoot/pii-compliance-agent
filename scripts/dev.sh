#!/usr/bin/env bash
# Runs the FastAPI backend (apps/api) and the Next.js frontend (apps/web)
# together for local development. Ctrl-C stops both.
#
# Deliberately a plain bash script rather than a pnpm-installed orchestrator
# (e.g. `concurrently`) -- the backend isn't a pnpm workspace member, and
# this avoids adding a JS dependency just to run two child processes.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pids=()

cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "[dev] starting api (http://127.0.0.1:8000) ..."
(cd "$ROOT_DIR/apps/api" && uv run uvicorn src.main:app --reload --workers 1) &
pids+=("$!")

echo "[dev] starting web (http://127.0.0.1:3000) ..."
(cd "$ROOT_DIR/apps/web" && pnpm dev) &
pids+=("$!")

wait "${pids[@]}"
