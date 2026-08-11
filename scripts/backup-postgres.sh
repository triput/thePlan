#!/usr/bin/env bash
# Dump thePlan Postgres from Docker Compose into backups/.
# Intended for cron on Linux/macOS.
#
# Env overrides:
#   COMPOSE_FILE       — default: <repo>/infra/compose/compose.yaml
#   BACKUP_DIR         — default: <repo>/backups
#   BACKUP_KEEP_DAYS   — default: 14
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/infra/compose/compose.yaml}"
BACKUP_DIR="${BACKUP_DIR:-${REPO_ROOT}/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
stamp="$(date +%Y%m%d-%H%M%S)"
out_file="${BACKUP_DIR}/theplan-${stamp}.sql"

echo "Backing up to ${out_file}"
if ! docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_dump -U theplan theplan > "${out_file}"; then
  rm -f "${out_file}"
  echo "pg_dump failed (is Compose postgres running?)" >&2
  exit 1
fi

if [[ ! -s "${out_file}" ]]; then
  echo "Backup file missing or empty: ${out_file}" >&2
  exit 1
fi

find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'theplan-*.sql' -mtime "+${BACKUP_KEEP_DAYS}" -print -delete || true

echo "Done. Kept dumps newer than ${BACKUP_KEEP_DAYS} day(s)."
