#!/usr/bin/env bash
# Gate 153G — can this system back up its own controlled state and restore it?
#
# The round trip proved here is a DATA round trip, not an infrastructure one:
# export the controlled dev/demo operational state for one organization, load
# it into a freshly migrated temporary database, and re-run the Gate 152 replay
# against what came back.
#
# THIS IS NOT PRODUCTION BACKUP AND DOES NOT CLAIM TO BE.
# `scripts/verify_nativeforge_backup_restore.sh` is the provider-level harness -
# pg_dump, PITR, an executed restore - and it returns SKIP because no managed
# instance exists. This verifier cannot make it pass and does not report on it.
#
# Two of the conditions are refusals, and both are RUN rather than asserted:
#
#   restore_into_source_refused   a restore whose target is the source
#   restore_into_live_refused     a target not declared isolated
#
# A refusal nobody exercises is unfalsifiable, which was Gate 134F's lesson.
#
# A restore that CLOSED a legacy gap would have invented a digest for an intent
# that never had one, so a fall in the legacy gap count FAILS this verifier
# rather than passing it.
#
# NOTHING IS SENT AND NOTHING IS FABRICATED. No mail, no provider, no live
# source, no collector, no object store, no document body, no customer data.
# The real organization is refused by name and never read. The temporary
# database is deleted before this verifier exits.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
DEMO_ORG="${NF_DEMO_ORG_OVERRIDE:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=backup_restore_readiness"

# ------------------------------------------------------------- 1. backend up
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/backend/health" 2>/dev/null || echo 000)"
if [ "$code" = "200" ]; then
  pass backend_running "http=$code"
else
  fail backend_running "http=$code"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=backend_not_running"
  exit 1
fi

# ----------------------------------------------- 2. the round trip, end to end
REPORT="$(
  .venv/bin/python - "$DEMO_ORG" <<'PYEOF' 2>/dev/null || true
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.lib.settings import get_settings

DEMO = sys.argv[1]
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

out = {"invariant_failures": []}

source_url = get_settings().database_url
source_engine = sa.create_engine(source_url)

from nativeforge.services.operational_backup_export_service import (
    build_backup_export,
    export_invariant_failures,
)
from nativeforge.services.operational_backup_manifest_service import (
    build_backup_manifest,
    manifest_invariant_failures,
)

# -- the manifest ---------------------------------------------------------
manifest = build_backup_manifest()
out["invariant_failures"].extend(manifest_invariant_failures(manifest))
out["manifest_included"] = manifest["included_count"]
out["manifest_excluded"] = manifest["excluded_count"]
out["manifest_deterministic"] = build_backup_manifest() == manifest
out["manifest_classified_by"] = manifest["classified_by"]
out["manifest_every_inclusion_has_a_reason"] = all(
    bool(entry["why_included"]) for entry in manifest["included_tables"]
)
out["manifest_every_exclusion_has_a_reason"] = all(
    bool(entry["exclusion_reason"]) and bool(entry["detail"])
    for entry in manifest["excluded_tables"]
)
excluded_names = {entry["table"] for entry in manifest["excluded_tables"]}
out["identities_excluded"] = "nf_identities" in excluded_names
out["redirect_states_excluded"] = "nf_auth_redirect_states" in excluded_names
out["organizations_excluded"] = "organizations" in excluded_names

# -- the export -----------------------------------------------------------
with source_engine.connect() as connection:
    export = build_backup_export(
        connection=connection, organization_id=DEMO, migration_head=None
    )
    real_export = build_backup_export(
        connection=connection, organization_id=REAL, migration_head=None
    )

out["invariant_failures"].extend(export_invariant_failures(export))
out["exported"] = export["exported"]
out["export_table_count"] = export["table_count"]
out["export_row_count"] = export["row_count_total"]
out["export_skipped_non_fixture"] = export["skipped_non_fixture_rows"]
out["export_leaked_shapes"] = export["leaked_shapes"]
out["export_rows_written"] = export["rows_written"]
out["export_hash_per_table"] = bool(export["tables"]) and all(
    bool(entry.get("payload_sha256")) for entry in export["tables"].values()
)
out["real_org_export_refused"] = (
    not real_export["exported"]
    and "real_organization_refused_by_name" in real_export["blocked_reasons"]
)

# -- an isolated target ---------------------------------------------------
tmp = Path(tempfile.mkdtemp(prefix="nf_gate153_"))
target_url = "sqlite+pysqlite:///" + (tmp / "restore.sqlite3").as_posix()
out["target_is_isolated"] = target_url != source_url

try:
    os.environ["DATABASE_URL"] = target_url
    get_settings.cache_clear()

    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")
    target_engine = sa.create_engine(target_url)

    with target_engine.connect() as connection:
        out["target_migration_head"] = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()

    # The organizations row is a restore PRECONDITION, never part of the
    # payload - which is how the real organization cannot arrive this way.
    with source_engine.connect() as src, target_engine.begin() as dst:
        org_row = (
            src.execute(
                sa.text("SELECT * FROM organizations WHERE id = :o"),
                {"o": uuid.UUID(DEMO).hex},
            )
            .mappings()
            .first()
        )
        if org_row:
            columns = ", ".join(org_row.keys())
            binds = ", ".join(":" + name for name in org_row.keys())
            dst.execute(
                sa.text(
                    "INSERT INTO organizations (" + columns + ") "
                    "VALUES (" + binds + ")"
                ),
                dict(org_row),
            )
        out["organization_precondition_present"] = bool(org_row)

    from nativeforge.services.operational_restore_service import (
        ISOLATED_TARGET,
        restore_backup,
        restore_invariant_failures,
    )

    with target_engine.begin() as connection:
        restore = restore_backup(
            target_connection=connection,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url=source_url,
            target_url=target_url,
            target_migration_head=None,
        )
    out["invariant_failures"].extend(restore_invariant_failures(restore))
    out["restored"] = restore["restored"]
    out["restored_row_count"] = restore["rows_restored_total"]
    out["restore_blocked_reasons"] = restore["blocked_reasons"]

    # -- the two refusals, RUN rather than asserted ----------------------
    with target_engine.begin() as connection:
        into_source = restore_backup(
            target_connection=connection,
            export=export,
            target_kind=ISOLATED_TARGET,
            source_url=source_url,
            target_url=source_url,
            target_migration_head=None,
        )
    out["restore_into_source_refused"] = (
        not into_source["restored"]
        and "restore_target_is_the_source_database"
        in into_source["blocked_reasons"]
    )
    out["restore_into_source_wrote"] = into_source["rows_restored_total"]

    with target_engine.begin() as connection:
        into_live = restore_backup(
            target_connection=connection,
            export=export,
            target_kind="live_database",
            source_url=source_url,
            target_url=target_url,
            target_migration_head=None,
        )
    out["restore_into_live_refused"] = (
        not into_live["restored"]
        and "restore_target_is_not_isolated" in into_live["blocked_reasons"]
    )
    out["restore_into_live_wrote"] = into_live["rows_restored_total"]

    # A tampered payload must be refused before a row is written.
    tampered = json.loads(json.dumps(export))
    first = sorted(tampered["tables"])[0]
    tampered["tables"][first]["payload_sha256"] = "0" * 64
    with target_engine.begin() as connection:
        refused_hash = restore_backup(
            target_connection=connection,
            export=tampered,
            target_kind=ISOLATED_TARGET,
            source_url=source_url,
            target_url=target_url,
            target_migration_head=None,
        )
    out["tampered_payload_refused"] = (
        not refused_hash["restored"]
        and "payload_hash_mismatch" in refused_hash["blocked_reasons"]
    )
    out["tampered_payload_wrote"] = refused_hash["rows_restored_total"]

    # -- re-verify the restored state ------------------------------------
    from nativeforge.services.operational_restore_verification_service import (
        verification_invariant_failures,
        verify_restored_state,
    )

    with source_engine.connect() as src, target_engine.connect() as dst:
        verification = verify_restored_state(
            source_connection=src,
            restored_connection=dst,
            organization_id=DEMO,
            export=export,
            restore=restore,
            sample_limit=25,
        )
    out["invariant_failures"].extend(
        verification_invariant_failures(verification)
    )
    out["verified"] = verification["verified"]
    out["checks_passed"] = verification["checks_passed"]
    out["checks_failed"] = verification["checks_failed"]
    out["checks_unknown"] = verification["checks_unknown"]
    out["check_status"] = {
        check["check"]: check["status"] for check in verification["checks"]
    }
    for check in verification["checks"]:
        if check["check"] == "restored_digest_payloads_still_hash":
            out["digests_hash_proven"] = check.get("digests_proven", 0)
        if check["check"] == "legacy_gaps_survived_as_legacy_gaps":
            out["source_legacy_gaps"] = check.get("source_legacy_gap_count")
            out["restored_legacy_gaps"] = check.get("restored_legacy_gap_count")

    # -- the real organization was never touched -------------------------
    with target_engine.connect() as connection:
        out["real_org_rows_in_target"] = connection.execute(
            sa.text(
                "SELECT count(*) FROM nf_awarded_grants WHERE organization_id = :o"
            ),
            {"o": uuid.UUID(REAL).hex},
        ).scalar()
        out["real_org_in_target_organizations"] = connection.execute(
            sa.text("SELECT count(*) FROM organizations WHERE id = :o"),
            {"o": uuid.UUID(REAL).hex},
        ).scalar()
        out["identities_in_target"] = connection.execute(
            sa.text("SELECT count(*) FROM nf_identities")
        ).scalar()
        out["redirect_states_in_target"] = connection.execute(
            sa.text("SELECT count(*) FROM nf_auth_redirect_states")
        ).scalar()

    target_engine.dispose()
finally:
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    shutil.rmtree(tmp, ignore_errors=True)
    out["temporary_database_removed"] = not tmp.exists()

# -- the source is untouched ----------------------------------------------
with source_engine.connect() as connection:
    out["source_emails_sent"] = connection.execute(
        sa.text("SELECT COALESCE(SUM(emails_sent), 0) FROM nf_digest_delivery_intents")
    ).scalar()
    out["source_providers_contacted"] = connection.execute(
        sa.text(
            "SELECT count(*) FROM nf_digest_delivery_intents "
            "WHERE provider_contacted = 1"
        )
    ).scalar()
    out["source_tenant_supplied_rows"] = connection.execute(
        sa.text(
            "SELECT count(*) FROM nf_tenant_digest_records "
            "WHERE fact_status = 'tenant_supplied'"
        )
    ).scalar()

from nativeforge.services.operational_backup_restore_readiness_service import (
    build_operational_restore_readiness,
    operational_restore_readiness_invariant_failures,
)

readiness = build_operational_restore_readiness(
    manifest_classified_by_meaning=(
        out["manifest_classified_by"] == "meaning, per table"
        and out["manifest_every_inclusion_has_a_reason"]
        and out["manifest_every_exclusion_has_a_reason"]
        and out["identities_excluded"]
        and out["redirect_states_excluded"]
        and out["organizations_excluded"]
    ),
    export_scoped_to_one_organization=(
        out["exported"]
        and not out["export_skipped_non_fixture"]
        and not out["export_leaked_shapes"]
        and out["real_org_export_refused"]
    ),
    export_carries_a_hash_per_table=out["export_hash_per_table"],
    restore_into_isolated_target_works=(
        out["restored"] and out["restored_row_count"] == out["export_row_count"]
    ),
    restore_into_source_refused=out["restore_into_source_refused"],
    restore_into_live_refused=out["restore_into_live_refused"],
    restored_state_passes_the_gate_152_replay=out["verified"],
    legacy_gaps_preserved=(
        out.get("restored_legacy_gaps") == out.get("source_legacy_gaps")
    ),
    source_legacy_gap_count=out.get("source_legacy_gaps") or 0,
    restored_legacy_gap_count=out.get("restored_legacy_gaps") or 0,
    exported_row_count=out["export_row_count"],
    restored_row_count=out["restored_row_count"],
    email_delivery=False,
    source_monitoring_live=False,
    object_store_configured=False,
    customer_data_backed_up=False,
    live_source_calls=0,
    emails_sent=int(out["source_emails_sent"] or 0),
    object_store_calls=0,
    real_organization_rows_touched=int(out["real_org_rows_in_target"] or 0),
)
out["invariant_failures"].extend(
    operational_restore_readiness_invariant_failures(readiness)
)
out["operational_backup_restore_ready"] = readiness["operational_backup_restore_ready"]
out["production_backup_ready"] = readiness["production_backup_ready"]
out["readiness_blockers"] = readiness["blockers"]
out["invariant_failures"] = sorted(set(out["invariant_failures"]))

print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail round_trip_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=round_trip_could_not_evaluate"
  exit 1
fi
pass round_trip_evaluated

get() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1])
print('' if v is None else v)
" "$1" 2>/dev/null; }

getlist() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1]) or []
print(','.join(str(x) for x in v) if v else 'none')
" "$1" 2>/dev/null; }

getkey() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin).get(sys.argv[1]) or {}
print(d.get(sys.argv[2], ''))
" "$1" "$2" 2>/dev/null; }

# -------------------------------------------------------- 3. the manifest
if [ "$(get manifest_included)" = "11" ] &&
   [ "$(get manifest_deterministic)" = "True" ] &&
   [ "$(get manifest_classified_by)" = "meaning, per table" ]; then
  pass manifest_classified_by_meaning \
    "included=$(get manifest_included) excluded=$(get manifest_excluded)"
else
  fail manifest_classified_by_meaning "$(get manifest_classified_by)"
fi

if [ "$(get manifest_every_inclusion_has_a_reason)" = "True" ] &&
   [ "$(get manifest_every_exclusion_has_a_reason)" = "True" ]; then
  pass every_table_has_a_declared_reason
else
  fail every_table_has_a_declared_reason
fi

for excluded in identities_excluded redirect_states_excluded \
  organizations_excluded; do
  if [ "$(get "$excluded")" = "True" ]; then
    pass "must_be_excluded:$excluded"
  else
    fail "must_be_excluded:$excluded"
  fi
done

# ---------------------------------------------------------- 4. the export
if [ "$(get exported)" = "True" ] && [ "$(get export_row_count)" -gt 0 ]; then
  pass export_built \
    "tables=$(get export_table_count) rows=$(get export_row_count)"
else
  fail export_built
fi

if [ "$(get export_hash_per_table)" = "True" ]; then
  pass export_carries_a_hash_per_table
else
  fail export_carries_a_hash_per_table
fi

if [ "$(getlist export_leaked_shapes)" = "none" ]; then
  pass export_leaks_nothing
else
  fail export_leaks_nothing "$(getlist export_leaked_shapes)"
fi

if [ "$(get export_skipped_non_fixture)" = "0" ]; then
  pass export_contains_only_fixtures
else
  fail export_contains_only_fixtures "skipped=$(get export_skipped_non_fixture)"
fi

if [ "$(get real_org_export_refused)" = "True" ]; then
  pass real_organization_export_refused_by_name
else
  fail real_organization_export_refused_by_name
fi

# --------------------------------------------------------- 5. the restore
if [ "$(get target_is_isolated)" = "True" ] &&
   [ "$(get target_migration_head)" = "0054" ]; then
  pass isolated_target_migrated "head=$(get target_migration_head)"
else
  fail isolated_target_migrated "head=$(get target_migration_head)"
fi

if [ "$(get restored)" = "True" ] &&
   [ "$(get restored_row_count)" = "$(get export_row_count)" ]; then
  pass restore_into_isolated_target "rows=$(get restored_row_count)"
else
  fail restore_into_isolated_target "$(getlist restore_blocked_reasons)"
fi

# The refusals are RUN, not asserted. Each must refuse AND write nothing.
if [ "$(get restore_into_source_refused)" = "True" ] &&
   [ "$(get restore_into_source_wrote)" = "0" ]; then
  pass restore_into_source_refused "restore_target_is_the_source_database"
else
  fail restore_into_source_refused "wrote=$(get restore_into_source_wrote)"
fi

if [ "$(get restore_into_live_refused)" = "True" ] &&
   [ "$(get restore_into_live_wrote)" = "0" ]; then
  pass restore_into_live_refused "restore_target_is_not_isolated"
else
  fail restore_into_live_refused "wrote=$(get restore_into_live_wrote)"
fi

if [ "$(get tampered_payload_refused)" = "True" ] &&
   [ "$(get tampered_payload_wrote)" = "0" ]; then
  pass tampered_payload_refused_before_any_write
else
  fail tampered_payload_refused_before_any_write \
    "wrote=$(get tampered_payload_wrote)"
fi

# ---------------------------------------------------- 6. the re-verification
for check in restored_row_counts_match_the_export \
  restored_table_hashes_match_the_export \
  restored_digest_payloads_still_hash \
  restored_intents_still_resolve_to_a_digest \
  gate_152_replay_agrees_on_both_sides \
  evidence_ledger_statuses_are_identical \
  archived_rows_are_still_archived_and_readable \
  a_cross_organization_read_is_still_refused \
  legacy_gaps_survived_as_legacy_gaps; do
  value="$(getkey check_status "$check")"
  if [ "$value" = "PASS" ]; then
    pass "restored:$check"
  else
    fail "restored:$check" "$value"
  fi
done

# A digest hash that was never proven would make the hash check green for the
# wrong reason: nothing to preserve is not the same as preserved.
if [ "$(get digests_hash_proven)" -gt 0 ] 2>/dev/null; then
  pass a_digest_hash_was_actually_proven "n=$(get digests_hash_proven)"
else
  fail a_digest_hash_was_actually_proven "n=$(get digests_hash_proven)"
fi

info source_legacy_gaps "$(get source_legacy_gaps)"
info restored_legacy_gaps "$(get restored_legacy_gaps)"

if [ "$(get restored_legacy_gaps)" = "$(get source_legacy_gaps)" ]; then
  pass legacy_gaps_preserved "a restore that closed one invented a digest"
else
  fail legacy_gaps_preserved \
    "$(get source_legacy_gaps) -> $(get restored_legacy_gaps)"
fi

# ------------------------------------------------- 7. what stays at zero
for zero in export_rows_written real_org_rows_in_target \
  real_org_in_target_organizations identities_in_target \
  redirect_states_in_target source_emails_sent \
  source_providers_contacted source_tenant_supplied_rows; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

if [ "$(get temporary_database_removed)" = "True" ]; then
  pass temporary_database_removed
else
  fail temporary_database_removed
fi

# ----------------------------------------------------------- 8. the lane
if [ "$(get production_backup_ready)" = "False" ]; then
  pass production_backup_ready_false "a different harness, still SKIP"
else
  fail production_backup_ready_false "became true"
fi

if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

if [ "$(get operational_backup_restore_ready)" = "True" ]; then
  pass operational_backup_restore_ready
else
  fail operational_backup_restore_ready "$(getlist readiness_blockers)"
fi

# ---------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "operational_backup_restore_ready=true"
echo "scope=controlled_dev_demo"
echo "production_backup_ready=false"
echo "production_backup_harness=verify_nativeforge_backup_restore.sh (still SKIP)"
echo "manifest_tables_included=$(get manifest_included)"
echo "manifest_tables_excluded=$(get manifest_excluded)"
echo "exported_rows=$(get export_row_count)"
echo "restored_rows=$(get restored_row_count)"
echo "restore_target=isolated_temporary_database"
echo "restore_into_source=refused"
echo "restore_into_live=refused"
echo "tampered_payload=refused_before_any_write"
echo "restore_verification_checks=$(get checks_passed)/9"
echo "digest_hashes_proven=$(get digests_hash_proven)"
echo "legacy_gaps=$(get restored_legacy_gaps)"
echo "legacy_gaps_backfilled=false"
echo "real_organization_rows=0"
echo "identities_restored=0"
echo "temporary_database=removed"
echo "emails_sent=0"
echo "live_source_calls=0"
echo "object_store_calls=0"
echo "next=docs/operations/801_GATE153_BACKUP_RESTORE_READINESS_DELTA.md"
exit 0
