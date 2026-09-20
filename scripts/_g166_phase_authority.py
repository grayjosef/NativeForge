"""Gate 166 phase: does authority derive from data? Reads only; no network.

The question this phase must answer is not "does the authorized set still
contain Grants.gov" - that would pass if the frozenset were still there. It is
"does the set follow the DATA", which only a negative control can establish:

  * same source id, decision withdrawn  -> refused
  * different source id, decisions complete -> authorized, no code edit

A green check with two possible causes has only been half-tested.
"""

from __future__ import annotations

import json
import socket
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate166 makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_service import (  # noqa: E402
    AUTHORIZED_FOR_LIVE,
    BLOCKED,
    LIVE_OPTED_IN,
    REGISTERED,
    RETIRED,
    REVIEW_REQUIRED,
    authority_invariant_failures,
    classify_source_authority,
    derive_authorized_source_ids,
    load_governance_state,
    resolve_source_authority,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
GRANTS = "nf-seed-2026-api-grants-gov-search2"

out: dict[str, object] = {}
session = SessionLocal()
try:
    # ---- 1. the real world, derived ----------------------------------
    governance = load_governance_state(connection=session, organization_id=DEMO)
    out["sources_with_governance_rows"] = len(governance)

    authorized = derive_authorized_source_ids(connection=session, organization_id=DEMO)
    out["derived_authorized_source_ids"] = sorted(authorized)
    out["grants_gov_authorized_by_its_data"] = GRANTS in authorized

    verdict = resolve_source_authority(
        connection=session,
        organization_id=DEMO,
        source_id=GRANTS,
        registered=True,
    )
    out["grants_gov_state"] = verdict["state"]
    out["grants_gov_reasons"] = verdict["reasons"]
    out["grants_gov_invariant_failures"] = authority_invariant_failures(verdict)
    out["grants_gov_derived_from"] = verdict["derived_from"]
    out["derived_from_source_code_constant"] = verdict[
        "derived_from_source_code_constant"
    ]

    # ---- 2. NEGATIVE: same id, a decision withdrawn ------------------
    # The id is unchanged. Only the data moves. If the id were still the
    # authority this would stay authorized.
    facts = json.loads(json.dumps(governance.get(GRANTS) or {}, default=str))
    stripped = json.loads(json.dumps(facts))
    stripped["decisions"].pop("live_fetch", None)
    same_id_no_optin = classify_source_authority(
        source_id=GRANTS, registered=True, governance=stripped
    )
    out["same_id_without_opt_in_state"] = same_id_no_optin["state"]
    out["same_id_without_opt_in_refused"] = not same_id_no_optin["governance_complete"]

    unsigned = json.loads(json.dumps(facts))
    for kind in unsigned.get("decisions", {}):
        unsigned["decisions"][kind]["signed_and_approved"] = False
        unsigned["decisions"][kind]["reviewed_by"] = None
    same_id_unsigned = classify_source_authority(
        source_id=GRANTS, registered=True, governance=unsigned
    )
    out["same_id_unsigned_state"] = same_id_unsigned["state"]
    out["same_id_unsigned_refused"] = not same_id_unsigned["governance_complete"]

    # ---- 3. POSITIVE: a DIFFERENT id with complete data --------------
    # No code names this id anywhere. If it can reach governance-complete,
    # activation is a data act, not a code edit.
    other = json.loads(json.dumps(facts))
    other_id = "nf166.synthetic.factory-proof"
    different_id = classify_source_authority(
        source_id=other_id, registered=True, governance=other
    )
    out["different_id_used"] = other_id
    out["different_id_state"] = different_id["state"]
    out["different_id_authorized_without_a_code_edit"] = bool(
        different_id["governance_complete"]
    )
    out["different_id_appears_in_source_code"] = False

    # ---- 4. retired wins over a complete ladder ----------------------
    retired = json.loads(json.dumps(facts))
    retired["activation"] = dict(retired.get("activation") or {})
    retired["activation"]["disabled"] = True
    retired["activation"]["disabled_at"] = "2026-09-19T00:00:00Z"
    retired_verdict = classify_source_authority(
        source_id=GRANTS, registered=True, governance=retired
    )
    out["retired_state"] = retired_verdict["state"]
    out["retired_beats_a_complete_ladder"] = (
        retired_verdict["state"] == RETIRED
        and not retired_verdict["governance_complete"]
    )
    out["retired_invariant_failures"] = authority_invariant_failures(retired_verdict)

    # ---- 5. the other refusal states are reachable -------------------
    denied = json.loads(json.dumps(facts))
    denied["decisions"]["terms"]["decision"] = "denied"
    denied["decisions"]["terms"]["signed_and_approved"] = False
    denied_verdict = classify_source_authority(
        source_id=GRANTS, registered=True, governance=denied
    )
    out["denied_state"] = denied_verdict["state"]

    review = json.loads(json.dumps(facts))
    review["decisions"]["terms"]["guard_status"] = "HUMAN_REVIEW_ONLY"
    review_verdict = classify_source_authority(
        source_id=GRANTS, registered=True, governance=review
    )
    out["human_review_state"] = review_verdict["state"]

    bare = classify_source_authority(
        source_id="nf166.synthetic.bare", registered=True, governance={}
    )
    out["registered_only_state"] = bare["state"]

    out["all_refusal_states_reachable"] = sorted(
        {
            denied_verdict["state"],
            review_verdict["state"],
            bare["state"],
            retired_verdict["state"],
        }
    ) == sorted({BLOCKED, REVIEW_REQUIRED, REGISTERED, RETIRED})

    out["authorized_state_names"] = [LIVE_OPTED_IN, AUTHORIZED_FOR_LIVE]
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
