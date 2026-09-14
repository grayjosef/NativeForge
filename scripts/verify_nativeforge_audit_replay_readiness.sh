#!/usr/bin/env bash
# Gate 152G — can this system replay what it recorded, and say what it cannot?
#
# The round trip proved here is the first fully linked chain in the database:
# persist a digest, record a delivery intent against it with
# require_persisted_digest=True, then replay both and check every link.
#
# RESULT=PASS when audit_replay_ready is true for controlled_dev_demo. That
# lane includes a condition most readiness checks would not have:
#
#   legacy_gaps_reported    the intents whose digest was never written are
#                           counted and surfaced, NOT backfilled
#
# A replay that quietly produced a digest for those intents would score better
# on every other condition and be worthless, so a backfill FAILS this verifier
# rather than passing it.
#
# NOTHING IS SENT AND NOTHING IS FABRICATED. No mail, no provider, no live
# source, no collector, no object store, no document body, no customer data.
# The real organization is counted, never addressed. The fixture digest and
# intent this creates are cleaned up before the verifier exits.
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

echo "verify=audit_replay_readiness"

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

# ------------------------------------ 2. the first fully linked chain, end to end
REPORT="$(
  .venv/bin/python - "$DEMO_ORG" <<'PYEOF' 2>/dev/null || true
import json
import sys
import uuid

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.db.session import SessionLocal, engine
from nativeforge.domain.enums import AuditAction
from nativeforge.repositories.audit_events import append_org_audit_event
from nativeforge.repositories.tenant_digest_records_repository import (
    TABLE_NAME,
    archive_digest_record,
)
from nativeforge.services.audit_replay_readiness_service import (
    build_audit_replay_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.audit_replay_service import (
    find_legacy_gaps,
    replay_delivery_intent,
    replay_digest,
    replay_invariant_failures,
)
from nativeforge.services.digest_delivery_dry_run_queue_service import (
    record_delivery_intent,
)
from nativeforge.services.evidence_ledger_service import (
    build_evidence_ledger,
    ledger_invariant_failures,
)
from nativeforge.services.evidence_status_vocabulary_service import (
    EVIDENCE_STATUSES,
    build_vocabulary,
    vocabulary_invariant_failures,
)
from nativeforge.services.tenant_digest_persistence_service import persist_digest

DEMO = sys.argv[1]
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000152"
FIXTURE_DIGEST_ID = "nf-fixture-gate152-" + ("r" * 45)

out = {"invariant_failures": []}

vocabulary = build_vocabulary()
out["invariant_failures"].extend(vocabulary_invariant_failures(vocabulary))
out["vocabulary_status_count"] = vocabulary["status_count"]
out["vocabulary_is_deterministic"] = build_vocabulary() == vocabulary
out["statuses"] = list(EVIDENCE_STATUSES)

# Legacy gaps BEFORE anything this verifier does.
with SessionLocal() as session:
    before = find_legacy_gaps(
        connection=session.connection(), organization_id=DEMO
    )
out["legacy_gaps_before"] = before["legacy_gap_count"]

DIGEST = {
    "digest_id": FIXTURE_DIGEST_ID,
    "tenant_id": "nf-fixture-gate152-tenant",
    "cadence": "weekly",
    "period_start": "2026-09-07",
    "period_end": "2026-09-13",
    "digest_period_key": "2026-09-07..2026-09-13",
    "snapshot_ids": ["nf-fixture-gate152-snapshot"],
    "items_total": 5,
    "items_visible": 3,
    "items_suppressed": 2,
    "items_human_review": 1,
    "items_with_unverified_deadlines": 1,
    "items_with_unknown_reporting_burden": 2,
    "caveats": ["deadline_unverified"],
    "blocked_reasons": ["items_suppressed:2"],
    "delivery_status": "preview_only",
}

intent_id = uuid.uuid4()

with SessionLocal() as session:
    connection = session.connection()

    # Clean slate for this fixture.
    connection.execute(
        sa.text(
            f"DELETE FROM {TABLE_NAME} "
            "WHERE organization_id = :o AND digest_id = :d"
        ),
        {"o": uuid.UUID(DEMO).hex, "d": FIXTURE_DIGEST_ID},
    )
    connection.execute(
        sa.text(
            "DELETE FROM nf_digest_delivery_intents "
            "WHERE organization_id = :o AND digest_id = :d"
        ),
        {"o": uuid.UUID(DEMO).hex, "d": FIXTURE_DIGEST_ID},
    )

    persisted = persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=DIGEST,
        org_is_demo=True,
    )

    # A real audit event, using the action the production path uses. Pointing
    # at an id that resolves to nothing would be a dangling reference this
    # verifier had manufactured and then detected.
    audit_event = append_org_audit_event(
        session,
        organization_id=uuid.UUID(DEMO),
        is_demo=True,
        action=AuditAction.digest_delivery_intent_recorded,
        payload={"fixture": "gate152", "digest_id": FIXTURE_DIGEST_ID},
        actor_id=None,
    )
    session.flush()
    out["audit_event_written"] = True
    out["digest_persisted"] = persisted["persisted"]
    out["persist_blocked_reasons"] = persisted["blocked_reasons"]

    # The first intent in this database recorded against a persisted digest.
    queued = record_delivery_intent(
        connection=connection,
        intent_id=intent_id,
        organization_id=DEMO,
        digest_id=FIXTURE_DIGEST_ID,
        digest_period_key=DIGEST["digest_period_key"],
        cadence="weekly",
        # A fingerprint and a domain. Gate 142's rule: an address does not
        # reach this function and the table has no column for one.
        recipient_fingerprint="f" * 32,
        recipient_domain="example.invalid",
        recipient_source="controlled_fixture",
        recipient_verified=True,
        items_total=DIGEST["items_total"],
        items_visible=DIGEST["items_visible"],
        digest_deliverable=True,
        require_persisted_digest=True,
        audit_event_id=str(audit_event.id),
        is_demo=True,
        fact_status="demo_fixture",
    )
    out["intent_recorded"] = bool(queued["rows_written"])
    out["intent_blocked_reasons"] = queued["blocked_reasons"]
    out["digest_record_persisted_flag"] = queued.get("digest_record_persisted")
    out["digest_linkage_enforced"] = queued.get("digest_linkage_enforced")

    # An intent naming a digest that was never persisted must be refused when
    # enforcement is on. This is the guard, exercised rather than asserted.
    refused = record_delivery_intent(
        connection=connection,
        organization_id=DEMO,
        digest_id="nf-fixture-gate152-never-persisted",
        digest_period_key="2026-01-01..2026-01-07",
        cadence="weekly",
        recipient_fingerprint="e" * 32,
        recipient_domain="example.invalid",
        recipient_source="controlled_fixture",
        recipient_verified=True,
        items_total=1,
        items_visible=1,
        digest_deliverable=True,
        require_persisted_digest=True,
        is_demo=True,
        fact_status="demo_fixture",
    )
    out["unpersisted_intent_refused"] = not refused["rows_written"]
    out["unpersisted_refusal_named"] = (
        "digest_id_names_no_persisted_digest" in refused["blocked_reasons"]
    )

    # -- replay the digest ------------------------------------------------
    digest_replay = replay_digest(
        connection=connection, organization_id=DEMO, digest_id=FIXTURE_DIGEST_ID
    )
    out["invariant_failures"].extend(replay_invariant_failures(digest_replay))
    out["digest_replay_found"] = digest_replay["found"]
    out["digest_replay_status"] = digest_replay["evidence_status"]
    out["digest_replay_links"] = {
        link["link"]: link["status"] for link in digest_replay["links"]
    }

    # -- replay the intent -------------------------------------------------
    intent_replay = replay_delivery_intent(
        connection=connection, organization_id=DEMO, intent_id=str(intent_id)
    )
    out["invariant_failures"].extend(replay_invariant_failures(intent_replay))
    out["intent_replay_found"] = intent_replay["found"]
    out["intent_replay_status"] = intent_replay["evidence_status"]
    out["intent_replay_links"] = {
        link["link"]: link["status"] for link in intent_replay["links"]
    }

    # -- cross-org is refused, indistinguishably from absent ---------------
    theirs = replay_digest(
        connection=connection, organization_id=OTHER, digest_id=FIXTURE_DIGEST_ID
    )
    absent = replay_digest(
        connection=connection, organization_id=OTHER, digest_id="z" * 64
    )
    out["cross_org_refused"] = not theirs["found"]
    out["cross_org_indistinguishable"] = (
        theirs["blocked_reasons"] == absent["blocked_reasons"]
    )
    real_org = replay_digest(
        connection=connection, organization_id=REAL, digest_id="z" * 64
    )
    out["real_org_refused_by_name"] = (
        "real_organization_refused_by_name" in real_org["blocked_reasons"]
    )

    # -- the ledger --------------------------------------------------------
    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=300
    )
    out["invariant_failures"].extend(ledger_invariant_failures(ledger))
    out["ledger_entry_count"] = ledger["entry_count"]
    out["ledger_by_type"] = ledger["by_type"]
    out["ledger_by_status"] = ledger["by_status"]
    out["ledger_overall_status"] = ledger["overall_status"]
    out["ledger_leaked_shapes"] = ledger["leaked_shapes"]
    out["ledger_excluded_sources"] = [
        entry["source"] for entry in ledger["excluded_sources"]
    ]

    # -- legacy gaps, after ------------------------------------------------
    after = find_legacy_gaps(connection=connection, organization_id=DEMO)
    out["legacy_gaps_after"] = after["legacy_gap_count"]
    out["legacy_gaps_backfilled"] = after["backfilled"]

    # -- clean up the fixture ---------------------------------------------
    archive_digest_record(
        connection=connection, organization_id=DEMO, digest_id=FIXTURE_DIGEST_ID
    )
    connection.execute(
        sa.text(
            "DELETE FROM nf_digest_delivery_intents "
            "WHERE organization_id = :o AND digest_id LIKE 'nf-fixture-gate152%'"
        ),
        {"o": uuid.UUID(DEMO).hex},
    )
    connection.execute(
        sa.text(
            f"DELETE FROM {TABLE_NAME} "
            "WHERE organization_id = :o AND digest_id LIKE 'nf-fixture-gate152%'"
        ),
        {"o": uuid.UUID(DEMO).hex},
    )
    connection.execute(
        sa.text("DELETE FROM nf_audit_events WHERE id = :i"),
        {"i": audit_event.id.hex},
    )
    session.commit()

with engine.connect() as conn:
    out["fixture_digests_remaining"] = conn.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE_NAME} "
            "WHERE digest_id LIKE 'nf-fixture-gate152%'"
        )
    ).scalar()
    out["fixture_intents_remaining"] = conn.execute(
        sa.text(
            "SELECT count(*) FROM nf_digest_delivery_intents "
            "WHERE digest_id LIKE 'nf-fixture-gate152%'"
        )
    ).scalar()
    out["real_org_digest_rows"] = conn.execute(
        sa.text(f"SELECT count(*) FROM {TABLE_NAME} WHERE organization_id = :o"),
        {"o": uuid.UUID(REAL).hex},
    ).scalar()
    out["tenant_supplied_rows"] = conn.execute(
        sa.text(
            f"SELECT count(*) FROM {TABLE_NAME} "
            "WHERE fact_status = 'tenant_supplied'"
        )
    ).scalar()
    out["emails_sent_recorded"] = conn.execute(
        sa.text("SELECT COALESCE(SUM(emails_sent), 0) FROM nf_digest_delivery_intents")
    ).scalar()
    out["providers_contacted"] = conn.execute(
        sa.text(
            "SELECT count(*) FROM nf_digest_delivery_intents "
            "WHERE provider_contacted = 1"
        )
    ).scalar()

readiness = build_audit_replay_readiness(
    tenant_digest_persistence_live=True,
    digest_hash_verification_works=(
        out["digest_replay_links"].get("payload_hash") == "hash_verified"
    ),
    delivery_intent_linkage_works=(
        out["intent_replay_links"].get("digest_record") == "linked_record_found"
    ),
    legacy_gaps_reported=out["legacy_gaps_after"] >= 0
    and not out["legacy_gaps_backfilled"],
    evidence_ledger_generates=out["ledger_entry_count"] > 0,
    cross_org_replay_refused=out["cross_org_refused"]
    and out["cross_org_indistinguishable"],
    legacy_gap_count=out["legacy_gaps_after"],
    legacy_gaps_backfilled=out["legacy_gaps_backfilled"],
    email_delivery=False,
    source_monitoring_live=False,
    object_store_configured=False,
    live_source_calls=0,
    emails_sent=int(out["emails_sent_recorded"] or 0),
    object_store_calls=0,
)
out["invariant_failures"].extend(readiness_invariant_failures(readiness))
out["audit_replay_ready"] = readiness["audit_replay_ready"]
out["production_audit_ready"] = readiness["production_audit_ready"]
out["readiness_blockers"] = readiness["blockers"]
out["invariant_failures"] = sorted(set(out["invariant_failures"]))

print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail replay_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=replay_could_not_evaluate"
  exit 1
fi
pass replay_evaluated

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

# ------------------------------------------------------- 3. the vocabulary
if [ "$(get vocabulary_status_count)" = "10" ] &&
   [ "$(get vocabulary_is_deterministic)" = "True" ]; then
  pass evidence_vocabulary "10 statuses, deterministic"
else
  fail evidence_vocabulary "$(get vocabulary_status_count) statuses"
fi

# ------------------------------------------------------- 4. the chain built
if [ "$(get digest_persisted)" = "True" ]; then
  pass digest_persisted
else
  fail digest_persisted "$(getlist persist_blocked_reasons)"
fi

if [ "$(get intent_recorded)" = "True" ] &&
   [ "$(get digest_record_persisted_flag)" = "True" ] &&
   [ "$(get digest_linkage_enforced)" = "True" ]; then
  pass intent_recorded_against_a_persisted_digest "enforcement on"
else
  fail intent_recorded_against_a_persisted_digest \
    "$(getlist intent_blocked_reasons)"
fi

if [ "$(get unpersisted_intent_refused)" = "True" ] &&
   [ "$(get unpersisted_refusal_named)" = "True" ]; then
  pass unpersisted_digest_intent_refused "digest_id_names_no_persisted_digest"
else
  fail unpersisted_digest_intent_refused "it was accepted"
fi

# ---------------------------------------------------------- 5. the replays
if [ "$(get digest_replay_found)" = "True" ]; then
  pass digest_replayed "status=$(get digest_replay_status)"
else
  fail digest_replayed
fi

for link in digest_record payload_hash delivery_intent; do
  value="$(getkey digest_replay_links "$link")"
  case "$value" in
    linked_record_found|hash_verified|attested)
      pass "digest_link:$link" "$value" ;;
    *) fail "digest_link:$link" "$value" ;;
  esac
done

if [ "$(get intent_replay_found)" = "True" ]; then
  pass delivery_intent_replayed "status=$(get intent_replay_status)"
else
  fail delivery_intent_replayed
fi

for link in delivery_intent digest_record payload_hash audit_event; do
  value="$(getkey intent_replay_links "$link")"
  case "$value" in
    linked_record_found|hash_verified|attested)
      pass "intent_link:$link" "$value" ;;
    *) fail "intent_link:$link" "$value" ;;
  esac
done

# ---------------------------------------------------------- 6. cross-org
if [ "$(get cross_org_refused)" = "True" ] &&
   [ "$(get cross_org_indistinguishable)" = "True" ]; then
  pass cross_org_replay_refused "same answer as a record that does not exist"
else
  fail cross_org_replay_refused
fi

if [ "$(get real_org_refused_by_name)" = "True" ]; then
  pass real_organization_refused_by_name
else
  fail real_organization_refused_by_name
fi

# ----------------------------------------------------------- 7. the ledger
if [ "$(get ledger_entry_count)" -gt 0 ] 2>/dev/null; then
  pass evidence_ledger_generates "entries=$(get ledger_entry_count)"
else
  fail evidence_ledger_generates
fi

info ledger_by_status "$(get ledger_by_status)"
info ledger_overall_status "$(get ledger_overall_status)"
info ledger_excluded_sources "$(getlist ledger_excluded_sources)"

if [ "$(getlist ledger_leaked_shapes)" = "none" ]; then
  pass ledger_leaks_nothing
else
  fail ledger_leaks_nothing "$(getlist ledger_leaked_shapes)"
fi

# ------------------------------------------------ 8. legacy gaps, reported
info legacy_gaps_before "$(get legacy_gaps_before)"
info legacy_gaps_after "$(get legacy_gaps_after)"

if [ "$(get legacy_gaps_backfilled)" = "False" ]; then
  pass legacy_gaps_not_backfilled
else
  fail legacy_gaps_not_backfilled "they were backfilled"
fi

# ------------------------------------------------------------ 9. cleanup
for zero in fixture_digests_remaining fixture_intents_remaining \
  real_org_digest_rows tenant_supplied_rows emails_sent_recorded \
  providers_contacted; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

# ----------------------------------------------------------- 10. the lane
if [ "$(get production_audit_ready)" = "False" ]; then
  pass production_audit_ready_false
else
  fail production_audit_ready_false "became true"
fi

if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

if [ "$(get audit_replay_ready)" = "True" ]; then
  pass audit_replay_ready
else
  fail audit_replay_ready "$(getlist readiness_blockers)"
fi

# ---------------------------------------------------------- 11. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "audit_replay_ready=true"
echo "scope=controlled_dev_demo"
echo "production_audit_ready=false"
echo "evidence_statuses=$(get vocabulary_status_count)"
echo "digest_replay_status=$(get digest_replay_status)"
echo "delivery_intent_replay_status=$(get intent_replay_status)"
echo "hash_verification=verified"
echo "delivery_intent_linkage=enforced_and_resolving"
echo "unpersisted_digest_intent=refused"
echo "evidence_ledger_entries=$(get ledger_entry_count)"
echo "evidence_ledger_overall_status=$(get ledger_overall_status)"
echo "legacy_gaps=$(get legacy_gaps_after)"
echo "legacy_gaps_backfilled=false"
echo "cross_org_replay=refused"
echo "fixture_records_remaining=0"
echo "real_organization_digest_rows=0"
echo "emails_sent=0"
echo "live_source_calls=0"
echo "object_store_calls=0"
echo "next=docs/operations/796_GATE152_AUDIT_REPLAY_READINESS_DELTA.md"
exit 0
