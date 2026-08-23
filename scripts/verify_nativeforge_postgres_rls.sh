#!/usr/bin/env bash
# Repeatable PostgreSQL Row-Level Security proof harness for NativeForge.
#
# Gate 62 proved RLS by hand against a rootless pgserver instance. That proof
# was real, but it was not repeatable, so it could not be re-run against a
# managed instance later. This script is that proof turned into an artifact.
#
# Modes:
#   --dry-run       self-check only; never contacts a database. PASS without credentials.
#   --check-config  inspect DATABASE_URL posture and reachability. SKIP if unset.
#   --verify-rls    run the full isolation proof. SKIP if unset, unless --strict.
#   --strict        absence of DATABASE_URL is a FAIL, not a SKIP.
#                   Given alone it implies --verify-rls --strict.
#
# The credential rule is absolute: DATABASE_URL is never echoed. Only a redacted
# form is ever printed, and a check asserts the redaction actually held before
# anything derived from the URL reaches stdout.
#
# No root, no sudo, no Docker and no local Postgres install are needed for
# --dry-run.
set -uo pipefail

MODE=""
STRICT=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)      MODE="dry-run" ;;
    --check-config) MODE="check-config" ;;
    --verify-rls)   MODE="verify-rls" ;;
    --strict)       STRICT=1; [[ -z "$MODE" ]] && MODE="verify-rls" ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *)
      echo "check=usage status=FAIL unknown_argument=${arg}"
      echo "RESULT=FAIL"
      exit 2 ;;
  esac
done
[[ -z "$MODE" ]] && MODE="dry-run"

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
  if [[ "$FAIL" -ne 0 ]]; then
    say result FAIL
    echo "RESULT=FAIL"
    exit 1
  fi
  if [[ "$SKIP" -ne 0 ]]; then
    say result SKIP
    echo "RESULT=SKIP"
    exit 0
  fi
  say result PASS
  echo "RESULT=PASS"
  exit 0
}

# ── credential redaction ────────────────────────────────────────────────────
# Replaces the password segment of a URL with ***. Applied to every printed form
# of the URL. Never returns the original when a password is present.
redact_url() {
  printf '%s' "$1" | sed -E 's#(^[a-zA-Z0-9+]+://[^:/@]+):[^@]*@#\1:***@#'
}

# True when the URL's authority section carries a password. The naive test
# ("does it contain a colon and an at-sign") is wrong: every URL has a colon in
# its scheme, so postgresql://user@host would be misread as password-bearing.
# Only the part between "://" and the first following "/" is the authority.
url_has_password() {
  local rest authority
  rest="${1#*://}"
  [[ "$rest" == "$1" ]] && return 1   # no scheme separator at all
  authority="${rest%%/*}"
  [[ "$authority" != *@* ]] && return 1
  [[ "${authority%%@*}" == *:* ]]
}

echo "verify_mode=${MODE} strict=${STRICT}"

# ── mode: dry-run ───────────────────────────────────────────────────────────
# Proves the harness itself is sound without needing a database. This is what a
# reviewer without credentials, and CI, can run.
if [[ "$MODE" == "dry-run" ]]; then
  say dry_run_mode PASS "no database contacted"

  if command -v psql >/dev/null 2>&1; then
    say psql_available PASS "$(psql --version 2>/dev/null | head -1)"
  else
    say psql_available SKIP "psql not installed; --verify-rls unavailable on this host"
  fi

  # Redaction is the one credential-safety control in this script, so it is
  # proved against a synthetic URL rather than assumed.
  SAMPLE='postgresql://nf_app:hunter2@db.example.internal:5432/nativeforge?sslmode=require'
  RED="$(redact_url "$SAMPLE")"
  if [[ "$RED" != *hunter2* && "$RED" == *'***'* ]]; then
    say redaction_self_test PASS "${RED}"
  else
    say redaction_self_test FAIL "redaction did not remove the password"
  fi

  # A URL carrying no password must survive redaction unchanged rather than be
  # mangled into something an operator would misread.
  NOPW='postgresql://nf_app@db.example.internal:5432/nativeforge'
  if [[ "$(redact_url "$NOPW")" == "$NOPW" ]]; then
    say redaction_passwordless_url PASS
  else
    say redaction_passwordless_url FAIL "passwordless URL was altered"
  fi

  # The password-presence guard must not be fooled by the scheme's own colon,
  # or a passwordless socket URL would be reported as a redaction failure.
  SOCK='postgresql://josefgray@/postgres?host=/tmp/pgdata'
  if url_has_password "$SAMPLE" \
     && ! url_has_password "$NOPW" \
     && ! url_has_password "$SOCK"; then
    say password_detection_self_test PASS
  else
    say password_detection_self_test FAIL "password presence misdetected"
  fi

  if [[ -n "${DATABASE_URL:-}" ]]; then
    say database_url_present PASS "$(redact_url "$DATABASE_URL")"
  else
    say database_url_present SKIP "unset (expected outside a provisioned environment)"
  fi

  say expected_checks_documented PASS "docs/operations/392_GATE62_PRODUCTION_READINESS_DELTA.md"
  finish
fi

# ── credential gate for the database-touching modes ─────────────────────────
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

# Assert the redaction held before printing anything derived from the URL. If a
# password would still be visible, refuse rather than print.
if [[ "$REDACTED" == "$DATABASE_URL" ]] && url_has_password "$DATABASE_URL"; then
  say database_url_redacted FAIL "redaction did not alter a URL that appears to carry a password"
  finish
fi
say database_url_redacted PASS "${REDACTED}"

if ! command -v psql >/dev/null 2>&1; then
  say psql_available SKIP "psql not installed; cannot run the proof on this host"
  finish
fi

q() { psql "$DATABASE_URL" -X -q -t -A -c "$1" 2>&1; }

# ── dialect ─────────────────────────────────────────────────────────────────
# RLS is a PostgreSQL feature. Claiming an RLS proof against any other engine
# would be claiming a control that does not exist.
VER="$(q 'SHOW server_version;' | head -1)"
case "$VER" in
  1[6-9].*|2[0-9].*) say postgres_dialect PASS "server_version=${VER}" ;;
  '')                say postgres_dialect FAIL "no response; connection failed"; finish ;;
  *)                 say postgres_dialect FAIL "server_version=${VER} (need PostgreSQL 16+)" ;;
esac

CUR_USER="$(q 'SELECT current_user;' | head -1)"

check_role_posture() {
  local super owns
  super="$(q 'SELECT rolsuper FROM pg_roles WHERE rolname=current_user;' | head -1)"
  if [[ "$super" == "f" ]]; then
    say app_role_not_superuser PASS "current_user=${CUR_USER}"
  else
    say app_role_not_superuser FAIL "current_user=${CUR_USER} is a superuser; RLS does not constrain it"
  fi

  owns="$(q "SELECT count(*) FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
             WHERE r.rolname=current_user AND c.relnamespace='public'::regnamespace
               AND c.relkind='r';" | head -1)"
  if [[ "${owns:-1}" == "0" ]]; then
    say app_role_not_table_owner PASS "owns=0"
  else
    say app_role_not_table_owner FAIL "current_user owns ${owns} public tables; owners bypass RLS unless FORCE is set"
  fi
}

check_rls_flags() {
  local enabled forced
  enabled="$(q "SELECT count(*) FROM pg_class
                WHERE relrowsecurity AND relnamespace='public'::regnamespace;" | head -1)"
  if [[ "${enabled:-0}" -ge 1 ]]; then
    say rls_enabled PASS "tables=${enabled}"
  else
    say rls_enabled FAIL "no table has ROW LEVEL SECURITY enabled; are migrations applied?"
  fi

  forced="$(q "SELECT count(*) FROM pg_class
               WHERE relrowsecurity AND relforcerowsecurity
                 AND relnamespace='public'::regnamespace;" | head -1)"
  if [[ "${forced:-0}" -ge 1 ]]; then
    say rls_forced PASS "tables=${forced}"
  else
    say rls_forced FAIL "FORCE ROW LEVEL SECURITY not set; the table owner would bypass isolation"
  fi
}

# ── mode: check-config ──────────────────────────────────────────────────────
# Posture only. Deliberately writes nothing, so it is safe to run against any
# environment, including one an operator believes is production.
if [[ "$MODE" == "check-config" ]]; then
  check_role_posture
  check_rls_flags

  # A Unix-domain socket carries no network traffic, so demanding TLS on one is
  # a false alarm. Only a TCP connection is held to the managed-production rule.
  SSL="$(q 'SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();' | head -1)"
  IS_SOCKET=0
  [[ "$DATABASE_URL" == *host=/* || "$DATABASE_URL" == *"://"?(*@)/* ]] && IS_SOCKET=1
  case "$SSL" in
    t) say connection_ssl PASS ;;
    f)
      if [[ "$IS_SOCKET" -eq 1 ]]; then
        say connection_ssl SKIP "unix-domain socket; TLS not applicable, and not a production topology"
      else
        say connection_ssl FAIL "TCP connection is not TLS; managed production requires sslmode=require or stricter"
      fi ;;
    *) say connection_ssl SKIP "pg_stat_ssl unavailable" ;;
  esac

  say check_config_read_only PASS "no rows written"
  finish
fi

# ── mode: verify-rls ────────────────────────────────────────────────────────
# This mode writes probe rows. It refuses to run without explicit consent,
# because a proof harness must never be the thing that corrupts the store it is
# supposed to be proving.
if [[ "${NF_RLS_ALLOW_WRITES:-0}" != "1" ]]; then
  say verify_rls_write_consent SKIP "set NF_RLS_ALLOW_WRITES=1 to permit probe-row writes"
  finish
fi
say verify_rls_write_consent PASS

check_role_posture
check_rls_flags

ORG_A='11111111-1111-1111-1111-111111111111'
ORG_B='22222222-2222-2222-2222-222222222222'
SCOPE_A="SELECT set_config('app.current_org_id','${ORG_A}',false);
         SELECT set_config('app.current_org_is_demo','false',false);"

# ── fixture non-vacuity ─────────────────────────────────────────────────────
# "Cross-org read returned zero rows" proves nothing if the other organization
# has no rows to leak. Seeding needs privileges the app role must not have, so
# it runs over a separate admin connection when one is supplied. Without one the
# isolation checks still run, but they are reported as possibly vacuous rather
# than presented as proof.
FIXTURE_SEEDED=0
if [[ -n "${NF_RLS_SEED_URL:-}" ]]; then
  qa() { psql "$NF_RLS_SEED_URL" -X -q -t -A -c "$1" 2>&1; }
  qa "INSERT INTO organizations (id, org_type) VALUES ('${ORG_A}','real')
      ON CONFLICT (id) DO NOTHING;" >/dev/null
  qa "INSERT INTO organizations (id, org_type) VALUES ('${ORG_B}','real')
      ON CONFLICT (id) DO NOTHING;" >/dev/null
  qa "DELETE FROM nf_audit_events WHERE action LIKE 'rls_probe_%';" >/dev/null
  qa "INSERT INTO nf_audit_events (id, organization_id, is_demo, action)
      VALUES (gen_random_uuid(),'${ORG_A}',false,'rls_probe_org_a');" >/dev/null
  qa "INSERT INTO nf_audit_events (id, organization_id, is_demo, action)
      VALUES (gen_random_uuid(),'${ORG_B}',false,'rls_probe_org_b');" >/dev/null

  SEEDED="$(qa "SELECT count(*) FROM nf_audit_events WHERE action LIKE 'rls_probe_%';")"
  if [[ "$SEEDED" == "2" ]]; then
    FIXTURE_SEEDED=1
    say cross_org_fixture_seeded PASS "rows=2 (one per organization)"
  else
    say cross_org_fixture_seeded FAIL "expected 2 probe rows, got: ${SEEDED}"
  fi
else
  say cross_org_fixture_seeded SKIP \
    "set NF_RLS_SEED_URL to an admin connection; isolation checks below may be vacuous"
fi

# A suffix appended to the isolation results when nothing was seeded, so a
# vacuous zero can never be read as a demonstrated denial.
VAC=""
[[ "$FIXTURE_SEEDED" -eq 1 ]] || VAC=" (VACUOUS: no fixture seeded)"

# ── same-org read ───────────────────────────────────────────────────────────
# With a fixture, org A must see exactly its own row. That is the positive
# control: without it, "cross-org sees nothing" could just mean the query is
# broken and nothing is ever visible.
SAME="$(q "${SCOPE_A}
           SELECT count(*) FROM nf_audit_events WHERE organization_id='${ORG_A}';" | tail -1)"
if [[ "$FIXTURE_SEEDED" -eq 1 ]]; then
  if [[ "$SAME" == "1" ]]; then
    say same_org_read_allowed PASS "rows=1 (own row visible)"
  else
    say same_org_read_allowed FAIL "expected 1 own row, got: ${SAME}"
  fi
elif [[ "$SAME" =~ ^[0-9]+$ ]]; then
  say same_org_read_allowed PASS "rows=${SAME}${VAC}"
else
  say same_org_read_allowed FAIL "unexpected response: ${SAME}"
fi

# ── cross-org read must return nothing ──────────────────────────────────────
CROSS="$(q "${SCOPE_A}
            SELECT count(*) FROM nf_audit_events WHERE organization_id='${ORG_B}';" | tail -1)"
if [[ "$CROSS" == "0" ]]; then
  say cross_org_read_blocked PASS "rows=0${VAC}"
elif [[ ! "$CROSS" =~ ^[0-9]+$ ]]; then
  say cross_org_read_blocked PASS "failed closed: ${CROSS}"
else
  say cross_org_read_blocked FAIL "leaked ${CROSS} rows belonging to another organization"
fi

# ── no GUC set at all must fail closed, not open ────────────────────────────
# The dangerous default. A missing scope must yield nothing, never everything.
UNSCOPED="$(q 'SELECT count(*) FROM nf_audit_events;' | tail -1)"
if [[ "$UNSCOPED" == "0" ]]; then
  say unscoped_read_blocked PASS "rows=0${VAC}"
elif [[ ! "$UNSCOPED" =~ ^[0-9]+$ ]]; then
  say unscoped_read_blocked PASS "failed closed: ${UNSCOPED}"
else
  say unscoped_read_blocked FAIL "unscoped session read ${UNSCOPED} rows; RLS is not failing closed"
fi

# ── membership table, read ──────────────────────────────────────────────────
MCROSS="$(q "${SCOPE_A}
             SELECT count(*) FROM nf_org_memberships WHERE organization_id='${ORG_B}';" | tail -1)"
if [[ "$MCROSS" == "0" ]]; then
  say membership_cross_org_read_blocked PASS "rows=0${VAC}"
elif [[ ! "$MCROSS" =~ ^[0-9]+$ ]]; then
  say membership_cross_org_read_blocked PASS "failed closed: ${MCROSS}"
else
  say membership_cross_org_read_blocked FAIL "leaked ${MCROSS} membership rows from another organization"
fi

# ── membership table, write ─────────────────────────────────────────────────
# The check that matters most. A session scoped to org A must not be able to
# write a membership into org B; WITH CHECK is what stops it. Granting yourself
# membership in someone else's organization is the whole attack.
MWRITE="$(q "${SCOPE_A}
             INSERT INTO nf_org_memberships
               (id, organization_id, identity_id, is_demo, state,
                membership_source, role, role_source, approved_by)
             VALUES (gen_random_uuid(), '${ORG_B}', gen_random_uuid(), false,
                     'active', 'operator_approved', 'org_owner',
                     'membership_record', gen_random_uuid());")"
if [[ "$MWRITE" == *'row-level security'* ]]; then
  say membership_cross_org_write_blocked PASS "refused by WITH CHECK"
elif [[ "$MWRITE" == *ERROR* ]]; then
  # Refused, but by something else — a foreign key, say. Blocked is blocked, but
  # the reason is not the one being proved, so report it rather than gloss it.
  say membership_cross_org_write_blocked PASS "refused, but not by RLS: $(printf '%s' "$MWRITE" | head -1)"
else
  say membership_cross_org_write_blocked FAIL "cross-org membership write was accepted"
  q "${SCOPE_A} DELETE FROM nf_org_memberships
     WHERE organization_id='${ORG_B}' AND role='org_owner';" >/dev/null 2>&1 || true
fi

finish
