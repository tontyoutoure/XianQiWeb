#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

KEYWORD_EXPR="${XQWEB_MILESTONE_EXPR:-m4 or m5 or m6}"
ENGINE_PATH="${XQWEB_ENGINE_TEST_PATH:-engine/tests}"
BACKEND_PATH="${XQWEB_BACKEND_TEST_PATH:-backend/tests}"
EXTRA_ARGS=("$@")

build_pytest_runner() {
  local -n runner_ref="$1"
  if [[ "${XQWEB_USE_CONDA:-1}" == "1" ]] && command -v conda >/dev/null 2>&1; then
    runner_ref=(conda run -n "${XQWEB_CONDA_ENV:-XQB}" pytest)
  else
    runner_ref=(pytest)
  fi
}

run_suite() {
  local suite_name="$1"
  shift
  echo "[m4-m6] running ${suite_name}..."
  "${PYTEST_RUNNER[@]}" "$@" "${EXTRA_ARGS[@]}"
}

declare -a PYTEST_RUNNER
build_pytest_runner PYTEST_RUNNER

run_suite "engine (${ENGINE_PATH})" "${ENGINE_PATH}" -q -k "${KEYWORD_EXPR}"
run_suite "backend (${BACKEND_PATH})" "${BACKEND_PATH}" -q -k "${KEYWORD_EXPR}"

echo "[m4-m6] all selected tests passed."
