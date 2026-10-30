#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[act-run] %s\n' "$*"
}

fail() {
  printf '[act-run] ERROR: %s\n' "$*" >&2
  exit 1
}

command -v act >/dev/null 2>&1 || fail "'act' is not installed or not in PATH."
command -v docker >/dev/null 2>&1 || fail "'docker' is not installed or not in PATH."

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is unreachable. Start Docker Desktop or your Docker service, then retry."
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
mkdir -p "${SCRIPT_DIR}/.act-artifacts"

if (($# == 0)); then
  set -- pull_request
fi

log "Running act $*"
exec act --bind --reuse=false "$@"
