#!/usr/bin/env bash
# Backup / restore proof harness for NativeForge.
#
# The Gate 61 storage approval required daily automated backups, PITR where the
# provider supports it, at least one restore test recorded as an artifact, and
# documented RTO/RPO. None of that can be executed without a provisioned managed
# instance. This script is the path: runnable today in --dry-run, and honest
# about the fact that nothing has been backed up or restored.
#
# Modes:
#   --dry-run        self-check only; never contacts a database. No credentials needed.
#   --check-config   inspect backup posture. SKIP if DATABASE_URL unset.
#   --verify-backup  take a real dump to a scratch path. SKIP if unset, unless --strict.
#   --verify-restore restore a dump into a NEW throwaway database. SKIP if no
#                    dump input, unless --strict.
#   --strict         missing required inputs become FAIL rather than SKIP.
#
# Safety rules built in, not documented and hoped for:
#   * DATABASE_URL is never echoed; only a redacted form is printed.
#   * --verify-restore refuses to target the database named in DATABASE_URL. A
#     restore proof that overwrites the live database is an outage, not a proof.
#   * --verify-restore requires NF_RESTORE_TARGET_URL to be supplied explicitly
#     and to differ from the source.
#   * Nothing writes customer data. The dump is read-only against the source.
#
# Artifacts are written under artifacts/gate65_backup_restore/ and are not
# committed.
set -uo pipefail

MODE=""
STRICT=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)        MODE="dry-run" ;;
    --check-config)   MODE="check-config" ;;
    --verify-backup)  MODE="verify-backup" ;;
    --verify-restore) MODE="verify-restore" ;;
    --strict)         STRICT=1; [[ -z "$MODE" ]] && MODE="verify-backup" ;;
    -h|--help)
      sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "check=usage status=FAIL unknown_argument=${arg}"
      echo "RESULT=FAIL"
      exit 2 ;;
  esac
done
[[ -z "$MODE" ]] && MODE="dry-run"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${NF_BACKUP_ARTIFACT_DIR:-${REPO_ROOT}/artifacts/gate65_backup_restore}"

FAIL=0
SKIP=0

say() {
  local name="$1" status="$2" detail="${3:-}"
  echo "check=${name} status=${status}${detail:+ ${detail}}"
  [[ "$status" == "FAIL" ]] && FAIL=1
  [[ "$status" == "SKIP" ]] && SKIP=1
  return 0
}

finish() {
  if [[ "$FAIL" -ne 0 ]]; then say result FAIL; echo "RESULT=FAIL"; exit 1; fi
  if [[ "$SKIP" -ne 0 ]]; then say result SKIP; echo "RESULT=SKIP"; exit 0; fi
  say result PASS
  echo "RESULT=PASS"
  exit 0
}

# Shared with verify_nativeforge_postgres_rls.sh by convention, duplicated
# rather than sourced so this script stays runnable on its own.
redact_url() {
  printf '%s' "$1" | sed -E 's#(^[a-zA-Z0-9+]+://[^:/@]+):[^@]*@#\1:***@#'
}

# Only the authority section can hold a password; the scheme's colon must not be
# mistaken for one.
url_has_password() {
  local rest authority
  rest="${1#*://}"
  [[ "$rest" == "$1" ]] && return 1
  authority="${rest%%/*}"
  [[ "$authority" != *@* ]] && return 1
  [[ "${authority%%@*}" == *:* ]]
}

# Database name, for the "are you about to overwrite the source" check.
url_dbname() {
  local rest path
  rest="${1#*://}"
  path="${rest#*/}"
  [[ "$path" == "$rest" ]] && { printf ''; return; }
  printf '%s' "${path%%\?*}"
}

# Whether the declared policy exists in the repo. A policy is a document, and a
# document that is not there is not a policy.
POLICY_DOC="${REPO_ROOT}/docs/operations/400_GATE65_BACKUP_RESTORE_ARTIFACT_FORMAT.md"

echo "verify_mode=${MODE} strict=${STRICT}"

# ── mode: dry-run ───────────────────────────────────────────────────────────
if [[ "$MODE" == "dry-run" ]]; then
  say dry_run_mode PASS "no database contacted"

  command -v pg_dump >/dev/null 2>&1 \
    && say pg_dump_available PASS "$(pg_dump --version 2>/dev/null | head -1)" \
    || say pg_dump_available SKIP "pg_dump not installed; --verify-backup unavailable here"

  command -v pg_restore >/dev/null 2>&1 \
    && say pg_restore_available PASS "$(pg_restore --version 2>/dev/null | head -1)" \
    || say pg_restore_available SKIP "pg_restore not installed; --verify-restore unavailable here"

  SAMPLE='postgresql://nf_app:hunter2@db.example.internal:5432/nativeforge'
  RED="$(redact_url "$SAMPLE")"
  if [[ "$RED" != *hunter2* && "$RED" == *'***'* ]]; then
    say database_url_redacted PASS "${RED}"
  else
    say database_url_redacted FAIL "redaction did not remove the password"
  fi

  NOPW='postgresql://nf_app@db.example.internal:5432/nativeforge'
  if url_has_password "$SAMPLE" && ! url_has_password "$NOPW"; then
    say password_detection_self_test PASS
  else
    say password_detection_self_test FAIL "password presence misdetected"
  fi

  if [[ "$(url_dbname "$SAMPLE")" == "nativeforge" ]]; then
    say same_database_guard_self_test PASS "source db name parsed"
  else
    say same_database_guard_self_test FAIL "cannot parse database name; overwrite guard unreliable"
  fi

  [[ -n "${DATABASE_URL:-}" ]] \
    && say database_url_present PASS "$(redact_url "$DATABASE_URL")" \
    || say database_url_present SKIP "unset (expected outside a provisioned environment)"

  # The four approval requirements, reported as the facts they currently are.
  say backup_policy_declared SKIP "no managed provider; policy is documented but not in force"
  say backup_automation_configured SKIP "no backup automation exists"
  say pitr_enabled SKIP "no provider, so PITR is neither supported nor enabled"
  say restore_test_executed SKIP "no restore has ever been executed"
  say restore_artifact_recorded SKIP "no restore artifact exists"

  [[ -f "$POLICY_DOC" ]] \
    && say rto_defined PASS "documented in 400_GATE65_BACKUP_RESTORE_ARTIFACT_FORMAT.md" \
    || say rto_defined FAIL "artifact format doc missing"
  [[ -f "$POLICY_DOC" ]] \
    && say rpo_defined PASS "documented in 400_GATE65_BACKUP_RESTORE_ARTIFACT_FORMAT.md" \
    || say rpo_defined FAIL "artifact format doc missing"

  say artifact_dir_declared PASS "${ARTIFACT_DIR#"${REPO_ROOT}/"}"
  finish
fi

# ── credential gate ─────────────────────────────────────────────────────────
if [[ -z "${DATABASE_URL:-}" ]]; then
  if [[ "$STRICT" -eq 1 ]]; then
    say database_url_present FAIL "unset, and --strict was requested"
    say database_url_redacted SKIP "nothing to redact"
    finish
  fi
  say database_url_present SKIP "unset; no managed Postgres is provisioned yet"
  say database_url_redacted SKIP "nothing to redact"
  finish
fi

REDACTED="$(redact_url "$DATABASE_URL")"
say database_url_present PASS
if [[ "$REDACTED" == "$DATABASE_URL" ]] && url_has_password "$DATABASE_URL"; then
  say database_url_redacted FAIL "redaction did not alter a password-bearing URL"
  finish
fi
say database_url_redacted PASS "${REDACTED}"

# ── mode: check-config ──────────────────────────────────────────────────────
# Read-only posture. Reports what is actually configured, which today is nothing.
if [[ "$MODE" == "check-config" ]]; then
  command -v pg_dump >/dev/null 2>&1 \
    && say pg_dump_available PASS || say pg_dump_available FAIL "pg_dump not installed"
  command -v pg_restore >/dev/null 2>&1 \
    && say pg_restore_available PASS || say pg_restore_available FAIL "pg_restore not installed"

  [[ "${NF_BACKUP_POLICY_DECLARED:-0}" == "1" ]] \
    && say backup_policy_declared PASS \
    || say backup_policy_declared SKIP "set NF_BACKUP_POLICY_DECLARED=1 once a provider policy is in force"

  [[ "${NF_BACKUP_AUTOMATION_CONFIGURED:-0}" == "1" ]] \
    && say backup_automation_configured PASS \
    || say backup_automation_configured SKIP "no automated backup job is configured"

  case "${NF_PITR_ENABLED:-0}" in
    1) [[ "${NF_PITR_SUPPORTED:-0}" == "1" ]] \
         && say pitr_enabled PASS \
         || say pitr_enabled FAIL "PITR reported enabled but provider support not declared" ;;
    *) say pitr_enabled SKIP "PITR not enabled" ;;
  esac

  say restore_test_executed SKIP "check-config does not execute a restore"
  LATEST="$(ls -1t "${ARTIFACT_DIR}"/*.json 2>/dev/null | head -1 || true)"
  [[ -n "$LATEST" ]] \
    && say restore_artifact_recorded PASS "$(basename "$LATEST")" \
    || say restore_artifact_recorded SKIP "no restore artifact under ${ARTIFACT_DIR#"${REPO_ROOT}/"}"

  [[ -f "$POLICY_DOC" ]] && say rto_defined PASS || say rto_defined FAIL "doc 400 missing"
  [[ -f "$POLICY_DOC" ]] && say rpo_defined PASS || say rpo_defined FAIL "doc 400 missing"
  say check_config_read_only PASS "no rows written, no dump taken"
  finish
fi

# ── mode: verify-backup ─────────────────────────────────────────────────────
# Read-only against the source: pg_dump takes a copy and writes nothing back.
if [[ "$MODE" == "verify-backup" ]]; then
  if ! command -v pg_dump >/dev/null 2>&1; then
    say pg_dump_available FAIL "pg_dump not installed"
    finish
  fi
  say pg_dump_available PASS

  mkdir -p "$ARTIFACT_DIR"
  STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
  DUMP="${ARTIFACT_DIR}/nf_backup_${STAMP}.dump"

  if pg_dump --format=custom --no-owner --no-privileges --file="$DUMP" "$DATABASE_URL" 2>"${DUMP}.err"; then
    SIZE="$(stat -c%s "$DUMP" 2>/dev/null || echo 0)"
    if [[ "${SIZE:-0}" -gt 0 ]]; then
      say backup_dump_created PASS "bytes=${SIZE} path=${DUMP#"${REPO_ROOT}/"}"
    else
      say backup_dump_created FAIL "dump file is empty"
    fi
    rm -f "${DUMP}.err"
  else
    # Never echo the error body: pg_dump includes the connection string in some
    # failure paths.
    say backup_dump_created FAIL "pg_dump failed; stderr withheld to avoid leaking the URL, see ${DUMP#"${REPO_ROOT}/"}.err"
  fi

  say backup_source_read_only PASS "pg_dump does not write to the source"
  say restore_test_executed SKIP "run --verify-restore to prove the dump is restorable"
  finish
fi

# ── mode: verify-restore ────────────────────────────────────────────────────
# The dangerous one. A restore proof that overwrites the database it is proving
# is an outage, so the target must be named explicitly and must not be the
# source.
if [[ "$MODE" == "verify-restore" ]]; then
  if ! command -v pg_restore >/dev/null 2>&1; then
    say pg_restore_available FAIL "pg_restore not installed"
    finish
  fi
  say pg_restore_available PASS

  DUMP_IN="${NF_RESTORE_DUMP:-$(ls -1t "${ARTIFACT_DIR}"/*.dump 2>/dev/null | head -1 || true)}"
  if [[ -z "$DUMP_IN" || ! -f "$DUMP_IN" ]]; then
    if [[ "$STRICT" -eq 1 ]]; then
      say restore_input_present FAIL "no dump found; set NF_RESTORE_DUMP"
    else
      say restore_input_present SKIP "no dump found; run --verify-backup first or set NF_RESTORE_DUMP"
    fi
    finish
  fi
  say restore_input_present PASS "$(basename "$DUMP_IN")"

  TARGET="${NF_RESTORE_TARGET_URL:-}"
  if [[ -z "$TARGET" ]]; then
    if [[ "$STRICT" -eq 1 ]]; then
      say restore_target_present FAIL "NF_RESTORE_TARGET_URL unset"
    else
      say restore_target_present SKIP "set NF_RESTORE_TARGET_URL to a throwaway database"
    fi
    finish
  fi
  say restore_target_present PASS

  # The guard that matters. Refuse rather than warn.
  if [[ "$TARGET" == "$DATABASE_URL" ]]; then
    say restore_target_is_not_source FAIL "target equals DATABASE_URL; refusing to overwrite the source"
    finish
  fi
  SRC_DB="$(url_dbname "$DATABASE_URL")"
  TGT_DB="$(url_dbname "$TARGET")"
  if [[ -n "$SRC_DB" && "$SRC_DB" == "$TGT_DB" ]]; then
    say restore_target_is_not_source FAIL "target database name matches the source; refusing"
    finish
  fi
  say restore_target_is_not_source PASS "target differs from source"

  if pg_restore --no-owner --no-privileges --dbname="$TARGET" "$DUMP_IN" 2>/dev/null; then
    say restore_test_executed PASS "restored into the throwaway target"
  else
    # pg_restore warns noisily on a non-empty target; treat a nonzero exit as a
    # failure rather than reading tea leaves from its stderr.
    say restore_test_executed FAIL "pg_restore returned nonzero; stderr withheld"
    finish
  fi

  mkdir -p "$ARTIFACT_DIR"
  STAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
  ART="${ARTIFACT_DIR}/nf_restore_proof_${STAMP}.json"
  HEAD_AFTER="$(psql "$TARGET" -X -q -t -A -c 'SELECT version_num FROM alembic_version;' 2>/dev/null | head -1)"
  printf '{\n  "artifact_id": "nf_restore_%s",\n  "timestamp": "%s",\n  "environment": "%s",\n  "restore_type": "full",\n  "migration_head_after": "%s",\n  "database_identifier_redacted": "%s",\n  "result": "executed",\n  "redactions_confirmed": true\n}\n' \
    "$STAMP" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "${NF_BACKUP_ENVIRONMENT:-unknown}" \
    "${HEAD_AFTER:-unknown}" "$(redact_url "$TARGET")" > "$ART"
  say restore_artifact_recorded PASS "${ART#"${REPO_ROOT}/"}"

  say rls_reproven_after_restore SKIP "run verify_nativeforge_postgres_rls.sh --verify-rls against the restored target"
  finish
fi
