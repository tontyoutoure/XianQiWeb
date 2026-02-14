#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST="${XQWEB_APP_HOST:-127.0.0.1}"
PORT="${XQWEB_APP_PORT:-18080}"
export XQWEB_SQLITE_PATH="${XQWEB_SQLITE_PATH:-${PROJECT_ROOT}/backend/xqweb.dev.sqlite3}"
export XQWEB_JWT_SECRET="${XQWEB_JWT_SECRET:-xqweb-dev-secret-change-this-key-32-bytes-minimum}"

PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[start-backend] Python executable not found: ${PYTHON_BIN}" >&2
  exit 1
fi

RELOAD_ARGS=()
if [[ "${XQWEB_RELOAD:-0}" == "1" ]]; then
  RELOAD_ARGS=(--reload)
fi

echo "[start-backend] host=${HOST} port=${PORT}"
echo "[start-backend] sqlite=${XQWEB_SQLITE_PATH}"
echo "[start-backend] using ${PYTHON_BIN}"
if [[ -n "${HTTP_PROXY:-}" || -n "${http_proxy:-}" || -n "${HTTPS_PROXY:-}" || -n "${https_proxy:-}" ]]; then
  echo "[start-backend] detected proxy env; use curl --noproxy '*' for localhost checks"
fi

exec "${PYTHON_BIN}" -m uvicorn \
  --app-dir "${PROJECT_ROOT}/backend" \
  app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --log-level info \
  "${RELOAD_ARGS[@]}"
