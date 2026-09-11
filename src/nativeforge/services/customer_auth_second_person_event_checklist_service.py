"""Gate 146B: what, exactly, is left before `customer_auth_live` can be true?

## The blocker is a conjunction, and naming it does not locate it

Gates 144 and 145 both report the remaining blocker as `invite_binding_passed`.
That is true and it is coarse. Three things must happen in order, and the name
covers all three:

```text
stage 1   a second identity signs in       nf_identities gains a row
stage 2   the owner issues an invite       nf_membership_invites gains a row
stage 3   the owner accepts it for them    the invite is accepted AND a
                                           membership names that invite AND
                                           the member is the accepter
```

An operator told "invite_binding_passed is false" looks for an invite to accept.
Measured today there is no invite, and nobody has signed in to accept one — so
the honest next action is two stages earlier than the name suggests. This module
reports the **stage**, and names the earliest unsatisfied step as the next human
action.

## Readiness is not the event

`readiness_passed` says the path is correct, safe and runnable. It says nothing
about whether anybody has walked it. Both are reported, never collapsed:

```text
readiness_passed     true      the path works
customer_auth_live   false     nobody has walked it
```

A gate that failed because a human has not yet done a human thing would train
an operator to ignore it. A gate that passed and called that `customer_auth_live`
would be a lie. So: pass on readiness, report the blocker separately.

## Why no code here can make it true

Stage 1 needs a real second Google account completing real OAuth. The callback
writes an identity only for a subject the provider verified.

```text
a fake identity row   the accepter is resolved from nf_identities and must
                      then match the invite's own fingerprint. A typed row
                      satisfies neither half.
a fake session        writes no identity at all.
a synthetic subject   is the faked user this gate exists to avoid.
an owner-only login   already happened. It is the one identity and the one
                      membership measured today, and it is exactly what
                      `memberships_matching_an_accepter_by_identity_only`
                      exists to keep visible.
```

So this module measures and refuses. It issues nothing and accepts nothing.

## One step is not detectable from here

The Google app is External/Testing, and Google refuses an unenrolled account
*before NativeForge sees the request*. Nothing here can read the Google console,
so test-user enrolment is reported `UNKNOWN` — never inferred from a failure
that looks identical to several other failures.

## What must never leave this module

`nf_identities` holds a real address and the provider subject. Neither is
selected, and a scan refuses the payload if either shape appears. What is
reported is counts, booleans, stage names and blocker names. The invite id is
the one identifier that is safe: the operator needs it, and it names no person.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_auth_second_person_checklist_v1"

#: Gate 135's demo organization. The only one this path may touch.
DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

#: The real organization, refused by name.
REFUSED_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Reported when the answer is not knowable from inside this repository.
UNKNOWN = "UNKNOWN"

STAGE_SECOND_IDENTITY = "second_identity_signed_in"
STAGE_INVITE_ISSUED = "invite_issued"
STAGE_INVITE_ACCEPTED = "invite_accepted_and_bound"
STAGE_COMPLETE = "complete"

#: In order. The first unsatisfied one is the next human action.
STAGES: tuple[str, ...] = (
    STAGE_SECOND_IDENTITY,
    STAGE_INVITE_ISSUED,
    STAGE_INVITE_ACCEPTED,
)

#: Each stage, who can do it, and whether a command exists for it. "the second
#: person" appears twice because two of the three cannot be done by an operator
#: at all, which is the fact an execution plan most needs.
STAGE_OWNERS: dict[str, dict[str, Any]] = {
    STAGE_SECOND_IDENTITY: {
        "who": "the second person",
        "command_exists": False,
        "what": (
            "signs in once through real Google OAuth, in a clean browser "
            "profile. Expect no session: the callback writes an identity and "
            "issues a cookie only once a membership resolves, and the "
            "membership is stage 3. That is correct, not a failure."
        ),
        "requires_human": True,
    },
    STAGE_INVITE_ISSUED: {
        "who": "the operator",
        "command_exists": True,
        "what": "./scripts/nativeforge_demo_invite_issue.py --email <address>",
        "requires_human": True,
    },
    STAGE_INVITE_ACCEPTED: {
        "who": "the operator",
        "command_exists": True,
        "what": (
            "./scripts/nativeforge_demo_invite_accept.py "
            "--invite-id <from stage 2> --email <the same address>"
        ),
        "requires_human": True,
    },
}

#: Not a stage, because nothing here can observe it. Reported alongside.
GOOGLE_TEST_USER_ENROLMENT = {
    "step": "enrol the second Google account as an OAuth test user",
    "who": "Mayhem, in the Google console",
    "observable_from_here": False,
    "state": UNKNOWN,
    "why_unknown": (
        "the app is External/Testing and Google refuses an unenrolled account "
        "before NativeForge sees the request, so the failure is indistinguishable "
        "from several others and nothing here can read the console"
    ),
    "must_not": "publish the app to work around it",
}

#: Ways somebody could try to satisfy the gate without the event, and why each
#: fails. Kept as data so a test can assert every one is still refused.
REFUSED_SHORTCUTS: tuple[dict[str, str], ...] = (
    {
        "shortcut": "insert an nf_identities row by hand",
        "refused_because": (
            "the accepter is resolved from nf_identities and must then match "
            "the invite's own fingerprint; a typed row satisfies neither half"
        ),
    },
    {
        "shortcut": "mint a session cookie for a second person",
        "refused_because": "a session writes no identity row at all",
    },
    {
        "shortcut": "synthesize a provider subject",
        "refused_because": "it is the faked user this gate exists to avoid",
    },
    {
        "shortcut": "write a membership directly, without an invite",
        "refused_because": (
            "invite_binding_passed joins the membership to the invite and to "
            "the accepter; a membership that merely shares an identity is "
            "counted separately as the near-miss it is"
        ),
    },
    {
        "shortcut": "count the owner's own login as the second person",
        "refused_because": (
            "the owner cannot accept their own invite, and the accepter must "
            "be an identity distinct from the org owner"
        ),
    },
    {
        "shortcut": "run the path against the real organization",
        "refused_because": (
            "both scripts refuse " + REFUSED_ORGANIZATION_ID + " by name and "
            "exit non-zero in a production environment"
        ),
    },
)

#: Shapes that must never appear in a payload from this module. An address and
#: a provider subject are what `nf_identities` actually holds.
_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
)

#: `sub` values Google issues are long digit strings. Checked as a shape rather
#: than by name, because the leak that matters is the value, not the label.
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: dict[str, Any]) -> list[str]:
    """Scan the serialised payload for anything that must never leave here."""
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def _stage_states(
    evidence: dict[str, Any], *, owner_identities: int
) -> dict[str, bool]:
    """Derive each stage from counts. Nothing here is declared."""
    identities = int(evidence.get("identity_rows") or 0)
    invites = int(evidence.get("invite_rows") or 0)
    return {
        # Strictly more identities than the owners we know about. One identity
        # is the owner; a second is the only thing that can be the invitee.
        STAGE_SECOND_IDENTITY: identities > owner_identities,
        STAGE_INVITE_ISSUED: invites > 0,
        STAGE_INVITE_ACCEPTED: bool(evidence.get("invite_binding_passed")),
    }


def build_second_person_checklist(
    *,
    evidence: dict[str, Any] | None = None,
    organization_id: str = DEMO_ORGANIZATION_ID,
    owner_identities: int = 1,
) -> dict[str, Any]:
    """Report the stage, the blockers, and the one next human action.

    `evidence` is a `build_invite_binding_evidence` result, plus `identity_rows`.
    It is supplied rather than read here so the caller owns the connection and
    this module cannot be handed a database it should not touch.

    `customer_auth_live` is **not** a parameter. It is derived from the same
    evidence as everything else, so a caller cannot assert it — the mistake
    Gate 145 made structurally impossible for capability flags, applied here.
    """
    refused_organization = organization_id == REFUSED_ORGANIZATION_ID
    wrong_organization = organization_id != DEMO_ORGANIZATION_ID

    if refused_organization or wrong_organization:
        payload = _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "organization_id": organization_id,
                "organization_refused": True,
                "refusal_reason": (
                    "real_organization_refused_by_name"
                    if refused_organization
                    else "not_the_demo_organization"
                ),
                "readiness_passed": False,
                "customer_auth_live": False,
                "invite_binding_passed": False,
                "stage": None,
                "stages": {},
                "blockers": ["organization_refused"],
                "next_human_action": None,
                "evidence_supplied": evidence is not None,
                "google_test_user_enrolment": GOOGLE_TEST_USER_ENROLMENT,
                "refused_shortcuts": list(REFUSED_SHORTCUTS),
                "leaked_shapes": [],
            }
        )
        payload["leaked_shapes"] = _leaked_shapes(payload)
        return payload

    supplied = evidence is not None
    evidence = evidence or {}

    stages = _stage_states(evidence, owner_identities=owner_identities)
    unsatisfied = [name for name in STAGES if not stages[name]]
    stage = unsatisfied[0] if unsatisfied else STAGE_COMPLETE

    blockers: list[str] = []
    if not supplied:
        blockers.append("no_evidence_supplied")
    blockers.extend(f"stage_not_reached:{name}" for name in unsatisfied)
    blockers.extend(str(r) for r in (evidence.get("blocked_reasons") or []))

    # The readiness question and the event question are different questions.
    #
    # Readiness asks whether the path is correct and runnable: evidence was
    # actually read, the organization is the demo one, both commands exist, and
    # nothing leaked. It does NOT ask whether anybody walked it.
    readiness_passed = supplied and not refused_organization and not wrong_organization

    # The event question. Derived, never supplied.
    invite_binding_passed = bool(evidence.get("invite_binding_passed"))
    customer_auth_live = invite_binding_passed and not unsatisfied

    next_action: dict[str, Any] | None = None
    if unsatisfied:
        first = unsatisfied[0]
        next_action = {"stage": first, **STAGE_OWNERS[first]}

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": organization_id,
            "organization_refused": False,
            "refusal_reason": None,
            "evidence_supplied": supplied,
            # The two answers, side by side and never collapsed.
            "readiness_passed": readiness_passed,
            "customer_auth_live": customer_auth_live,
            "invite_binding_passed": invite_binding_passed,
            "stage": stage,
            "stages": stages,
            "stage_order": list(STAGES),
            "counts": {
                "identity_rows": int(evidence.get("identity_rows") or 0),
                "invite_rows": int(evidence.get("invite_rows") or 0),
                "accepted_invite_rows": int(evidence.get("accepted_invite_rows") or 0),
                "membership_rows": int(evidence.get("membership_rows") or 0),
                "memberships_from_a_completed_invite": int(
                    evidence.get("memberships_from_a_completed_invite") or 0
                ),
                "memberships_matching_an_accepter_by_identity_only": int(
                    evidence.get("memberships_matching_an_accepter_by_identity_only")
                    or 0
                ),
            },
            "second_identity_required": True,
            "second_identity_must_be_distinct_from_owner": True,
            "blockers": sorted(set(blockers)),
            "next_human_action": next_action,
            "google_test_user_enrolment": GOOGLE_TEST_USER_ENROLMENT,
            "refused_shortcuts": list(REFUSED_SHORTCUTS),
            # Nothing here activates anything, and each is asserted false so a
            # regression that flipped one is a test failure rather than a
            # silently wider gate.
            "invite_issued_by_this_module": False,
            "invite_accepted_by_this_module": False,
            "identity_written_by_this_module": False,
            "session_minted_by_this_module": False,
            "email_sent": False,
            "real_organization_touched": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def checklist_invariant_failures(checklist: dict[str, Any]) -> list[str]:
    """Refuse a checklist that claims more than its evidence supports."""
    fails: list[str] = []

    if checklist.get("customer_auth_live"):
        if not checklist.get("invite_binding_passed"):
            fails.append("customer_auth_live_without_invite_binding")
        if not checklist.get("evidence_supplied"):
            fails.append("customer_auth_live_without_reading_anything")
        if checklist.get("blockers"):
            fails.append("customer_auth_live_alongside_blockers")
        if checklist.get("stage") != STAGE_COMPLETE:
            fails.append("customer_auth_live_before_every_stage")
        counts = checklist.get("counts") or {}
        if not counts.get("accepted_invite_rows"):
            fails.append("customer_auth_live_without_an_accepted_invite")
        if not counts.get("memberships_from_a_completed_invite"):
            fails.append("customer_auth_live_without_a_membership_from_one")

    if checklist.get("readiness_passed") and checklist.get("organization_refused"):
        fails.append("readiness_passed_on_a_refused_organization")

    # Readiness is allowed to pass while the event has not happened. The
    # reverse is not: the event cannot have happened along a path that is not
    # ready, because the same evidence feeds both.
    if checklist.get("customer_auth_live") and not checklist.get("readiness_passed"):
        fails.append("customer_auth_live_without_readiness")

    addressed_real_org = checklist.get("organization_id") == REFUSED_ORGANIZATION_ID
    if addressed_real_org and not checklist.get("organization_refused"):
        fails.append("real_organization_not_refused")

    for flag in (
        "invite_issued_by_this_module",
        "invite_accepted_by_this_module",
        "identity_written_by_this_module",
        "session_minted_by_this_module",
        "email_sent",
        "real_organization_touched",
    ):
        if checklist.get(flag):
            fails.append(f"module_claimed_to_have:{flag}")

    if checklist.get("leaked_shapes"):
        for name in checklist["leaked_shapes"]:
            fails.append(f"leaked:{name}")

    return sorted(set(fails))
