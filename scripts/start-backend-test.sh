#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST="${XQWEB_APP_HOST:-127.0.0.1}"
PORT="${XQWEB_APP_PORT:-18080}"
export XQWEB_APP_ENV="${XQWEB_APP_ENV:-test}"
export XQWEB_JWT_SECRET="${XQWEB_JWT_SECRET:-xqweb-test-secret-change-this-key-32-bytes-minimum}"

PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "[start-backend-test] Python executable not found: ${PYTHON_BIN}" >&2
  exit 1
fi

GENERATED_SQLITE_PATH=0
if [[ -z "${XQWEB_SQLITE_PATH:-}" ]]; then
  TEST_DB_DIR="${XQWEB_TEST_DB_DIR:-/tmp/xqweb-test}"
  mkdir -p "${TEST_DB_DIR}"
  export XQWEB_SQLITE_PATH="$(mktemp "${TEST_DB_DIR%/}/xqweb-test-XXXXXX.sqlite3")"
  GENERATED_SQLITE_PATH=1
fi

cleanup() {
  if [[ "${GENERATED_SQLITE_PATH}" == "1" ]]; then
    if [[ "${XQWEB_TEST_KEEP_DB:-0}" == "1" ]]; then
      echo "[start-backend-test] keep sqlite=${XQWEB_SQLITE_PATH}"
    else
      rm -f "${XQWEB_SQLITE_PATH}"
      echo "[start-backend-test] cleaned sqlite=${XQWEB_SQLITE_PATH}"
    fi
  fi
}
trap cleanup EXIT

RELOAD_ARGS=()
if [[ "${XQWEB_RELOAD:-0}" == "1" ]]; then
  RELOAD_ARGS=(--reload)
fi

echo "[start-backend-test] env=${XQWEB_APP_ENV} host=${HOST} port=${PORT}"
echo "[start-backend-test] sqlite=${XQWEB_SQLITE_PATH}"
echo "[start-backend-test] using ${PYTHON_BIN}"
if [[ -n "${HTTP_PROXY:-}" || -n "${http_proxy:-}" || -n "${HTTPS_PROXY:-}" || -n "${https_proxy:-}" ]]; then
  echo "[start-backend-test] detected proxy env; use curl --noproxy '*' for localhost checks"
fi

"${PYTHON_BIN}" -m uvicorn \
  --app-dir "${PROJECT_ROOT}/backend" \
  app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --log-level info \
  "${RELOAD_ARGS[@]}"
