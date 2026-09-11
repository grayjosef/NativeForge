#!/usr/bin/env bash
# Gate 146C — is the second-person invite path ready, and how far has it got?
#
# This verifier answers TWO questions and never collapses them:
#
#   readiness_passed     is the path correct, safe and runnable?
#   customer_auth_live   has anybody actually walked it?
#
# RESULT=PASS means the first. It does NOT mean the second, and the second is
# printed on its own line beside it with the exact blocker and the stage.
#
# Why PASS while customer_auth_live is false: the remaining blocker is a real
# human event — a second person completing real Google OAuth — and a gate that
# failed because a human has not yet done a human thing would train an operator
# to ignore it. Gate 145 named this conflation five times over. This is the
# sixth: readiness is not the capability beside it.
#
# RESULT=BLOCKED is reserved for the path itself being broken: the backend
# down, the evidence unreadable, an invariant failing, or the gate claiming
# customer_auth_live while the measurements disagree.
#
# Nothing is issued, accepted, written or activated. Every number is read from
# the live database or the running backend; none is supplied.
#
# No secrets. No tokens. No cookies. No state. No PKCE verifier. No provider
# subject. No email address. Counts, booleans, stage names and blocker names.
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

echo "verify=customer_auth_second_person_event"

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

# -------------------------------------------- 2. the checklist, from the live DB
# Read-only. `nf_identities` is counted, never selected: it holds a real
# address and the provider subject, and neither may reach this terminal.
CHECKLIST="$(
  .venv/bin/python - "$DEMO_ORG" <<'PYEOF' 2>/dev/null || true
import json
import sys

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.lib.settings import get_settings
from nativeforge.services.customer_auth_second_person_event_checklist_service import (
    build_second_person_checklist,
    checklist_invariant_failures,
)
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)

organization_id = sys.argv[1]
engine = sa.create_engine(get_settings().database_url)
with engine.connect() as connection:
    evidence = build_invite_binding_evidence(connection=connection)
    evidence["identity_rows"] = connection.execute(
        sa.text("SELECT count(*) FROM nf_identities")
    ).scalar()

checklist = build_second_person_checklist(
    evidence=evidence, organization_id=organization_id
)
checklist["invariant_failures"] = checklist_invariant_failures(checklist)

# The refusal branch, proved on every run rather than asserted in a comment.
refused = build_second_person_checklist(
    evidence=evidence, organization_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
)
checklist["real_org_refused"] = bool(refused.get("organization_refused"))
checklist["real_org_readiness_passed"] = bool(refused.get("readiness_passed"))

print(json.dumps(checklist, sort_keys=True))
PYEOF
)"

if [ -z "$CHECKLIST" ]; then
  fail checklist_readable "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=checklist_unreadable"
  exit 1
fi
pass checklist_readable

get() { printf '%s' "$CHECKLIST" | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split('.'):
    d = (d or {}).get(k) if isinstance(d, dict) else None
print('' if d is None else d)
" "$1" 2>/dev/null; }

getlist() { printf '%s' "$CHECKLIST" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1]) or []
print(','.join(str(x) for x in v) if v else 'none')
" "$1" 2>/dev/null; }

READINESS="$(get readiness_passed)"
AUTH_LIVE="$(get customer_auth_live)"
BINDING="$(get invite_binding_passed)"
STAGE="$(get stage)"
INVARIANTS="$(getlist invariant_failures)"
LEAKED="$(getlist leaked_shapes)"

# ------------------------------------------------------------- 3. the counts
for key in identity_rows invite_rows accepted_invite_rows membership_rows \
  memberships_from_a_completed_invite \
  memberships_matching_an_accepter_by_identity_only; do
  echo "count=$key n=$(get "counts.$key")"
done

# ---------------------------------------------- 4. the path is safe to run
if [ "$(get real_org_refused)" = "True" ]; then
  pass real_organization_refused "by_name"
else
  fail real_organization_refused "not_refused"
fi

if [ "$(get real_org_readiness_passed)" = "False" ]; then
  pass real_organization_readiness_refused
else
  fail real_organization_readiness_refused "readiness_passed_on_the_real_org"
fi

for script in scripts/nativeforge_demo_invite_issue.py \
  scripts/nativeforge_demo_invite_accept.py; do
  if [ -x "$script" ]; then
    pass "command_available:$(basename "$script")"
  else
    fail "command_available:$(basename "$script")" "missing_or_not_executable"
  fi
done

# The accept path must have no flag that accepts for somebody who has not
# signed in. That is the faked user this gate exists to avoid, so its absence
# is checked rather than trusted.
if grep -qE -- "--force|--skip-identity|--no-identity|--synthetic" \
  scripts/nativeforge_demo_invite_accept.py 2>/dev/null; then
  fail accept_has_no_bypass_flag "a bypass flag appeared"
else
  pass accept_has_no_bypass_flag
fi

# ------------------------------------------------- 5. nothing was activated
for flag in invite_issued_by_this_module invite_accepted_by_this_module \
  identity_written_by_this_module session_minted_by_this_module \
  email_sent real_organization_touched; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

# ------------------------------------------------------------- 6. no leaks
if [ "$LEAKED" = "none" ]; then
  pass no_forbidden_shape_in_payload
else
  fail no_forbidden_shape_in_payload "$LEAKED"
fi

if [ "$INVARIANTS" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$INVARIANTS"
fi

# ------------------------------- 7. the gate must not claim more than it has
if [ "$AUTH_LIVE" = "True" ] && [ "$BINDING" != "True" ]; then
  fail gate_consistency "customer_auth_live_without_invite_binding"
fi

# --------------------------------------------- 8. the one unobservable step
info google_test_user_enrolment \
  "$(get google_test_user_enrolment.state) not_observable_from_here"

# ------------------------------------------------------------- 9. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  echo "readiness_passed=false"
  exit 1
fi

if [ "$READINESS" != "True" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=readiness_path_incorrect"
  echo "readiness_passed=false"
  exit 1
fi

echo "RESULT=PASS"
echo "readiness_passed=true"

if [ "$AUTH_LIVE" = "True" ]; then
  echo "customer_auth_live=true"
  echo "invite_binding_passed=true"
  echo "stage=complete"
  echo "scope=controlled_dev_demo_org_only"
else
  # The expected shape today. PASS is the readiness gate; the event has its
  # own line, its own blocker and its own stage, so nobody reads one as the
  # other.
  echo "customer_auth_live=false"
  echo "invite_binding_passed=false"
  echo "event_status=BLOCKED"
  echo "blocker=invite_binding_passed"
  echo "stage=$STAGE"
  echo "blockers=$(getlist blockers)"
  echo "next_human_action=$(get next_human_action.stage)"
  echo "next_human_action_owner=$(get next_human_action.who)"
  echo "next=docs/operations/765_GATE146_NEXT_HUMAN_ACTION.md"
fi

echo "controlled_customer_pilot=false"
echo "production_rollout=false"
exit 0
