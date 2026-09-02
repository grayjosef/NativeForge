"""Gate 136C: the accept path. An invite becomes a membership, or nothing does.

Gate 135 built both halves and left the middle out. `record_acceptance` marks
an invite accepted; `insert_membership` writes a membership; nothing joined
them, so `invite_binding_passed` - which needs an accepted invite **and** a
membership the accepter holds - could not be satisfied by any sequence of calls
a caller could make without deciding for itself that the two were related.

This module is that join, and it is one transaction. A half-completed
acceptance is the worst of the available states: an invite marked accepted with
no membership behind it reads as consumed, and the person it named cannot be
invited again because `uq_nf_membership_invites_org_invite` holds the id.

## Why this is not an API route

`api/auth.py`'s callback issues a session cookie only when the identity already
resolves to an organization through a membership row:

```text
if organization_id_resolved and membership_verified:
    ... set_cookie(...)
```

An invited person has no membership - that is what the invite is for - so they
cannot hold a session, so an authenticated accept route has nobody to
authenticate. A route accepting for an *un*authenticated caller would have to
trust an invite id in a URL, an email in a body, or a header, which is the
class of authority Gates 111 through 135 removed.

So the entry point is an operator script. What keeps that honest is that the
operator cannot choose the accepter: the identity is resolved from
`nf_identities` by the address the invite named, and `record_acceptance`
refuses an accepter that does not match the invite. An operator can run this
for somebody who has really signed in, or not at all.

## What it refuses

Everything `record_acceptance` refuses, plus:

```text
organization_is_not_a_demo_organization    real org, by classification
seat_cap_reached                           counted, not assumed
membership_already_exists                  idempotent, and says so
```

Demo scope is derived from `organizations.org_type`, never from a parameter -
the same argument `dev_org_membership_bootstrap_service` records. An
authorization in a chat log is not an enforcement.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.demo_org_classification_service import classify_organization
from nativeforge.services.dev_org_membership_bootstrap_service import (
    MEMBERSHIPS,
    insert_membership,
)
from nativeforge.services.membership_invite_approval_service import (
    evaluate_membership_provenance,
)
from nativeforge.services.membership_invite_repository_service import (
    INVITES,
    build_invite_binding_evidence,
    email_fingerprint,
    record_acceptance,
)

SCHEMA_VERSION = "nf_membership_invite_activation_v1"

IDENTITY_TABLE = "nf_identities"

#: The provenance a membership produced this way carries. One value, because
#: this module has one job and `TRUSTED_PROVENANCES` recognises one answer.
PROVENANCE = "completed_invite"

#: Which `membership_source` an invite approved by the organization's owner
#: produces. Not `verified_directory` - there is no directory - and not
#: `operator_approved`, because the operator running the script is not who
#: approved it. The invite's `approved_by` is.
MEMBERSHIP_SOURCE = "org_owner_approved"

#: nf_org_memberships.invite_id is String(64) and nf_membership_invites.invite_id
#: is String(128), so an id between the two writes fine as an invite and then
#: cannot be named by the membership it produces. Refused before either write
#: rather than discovered as a database error mid-transaction.
MEMBERSHIP_INVITE_ID_MAX = 64
INVITE_ID_TOO_LONG = "invite_id_too_long_for_a_membership_to_name_it"

NOT_DEMO = "organization_is_not_a_demo_organization"
SEAT_CAP_REACHED = "seat_cap_reached"
ALREADY_A_MEMBER = "membership_already_exists"
IDENTITY_NOT_FOUND = "no_identity_has_signed_in_with_that_address"
IDENTITY_AMBIGUOUS = "several_identities_share_that_address"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def resolve_invited_identity(
    *,
    connection: Any = None,
    email: Any = None,
) -> dict[str, Any]:
    """Which identity has signed in with this address?

    The address is taken at runtime and never returned. What comes back is an
    internal id and a fingerprint, which is what the invite and the acceptance
    both compare against.

    A resolution that finds nobody is the normal answer before the invited
    person has logged in, and it is reported as that rather than as an error:
    their first login is what creates the row.
    """
    blocked: list[str] = []
    text = str(email or "").strip().lower()
    if not text or "@" not in text:
        blocked.append("no_invited_email_supplied")
    if connection is None:
        blocked.append("no_connection_supplied")

    rows: list[Any] = []
    if connection is not None and not blocked:
        rows = list(
            connection.execute(
                sa.text(
                    f"SELECT id FROM {IDENTITY_TABLE} "
                    "WHERE lower(trim(email)) = :e AND disabled_at IS NULL"
                ),
                {"e": text},
            )
            .mappings()
            .all()
        )
        if not rows:
            blocked.append(IDENTITY_NOT_FOUND)
        elif len(rows) > 1:
            # `(issuer, subject)` is the identity key, so one address can
            # legitimately belong to two provider identities. Choosing one
            # would be choosing who gets the membership.
            blocked.append(IDENTITY_AMBIGUOUS)

    identity_id = str(_as_uuid(rows[0]["id"])) if len(rows) == 1 else None

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_resolved": bool(identity_id),
            "identity_id": identity_id,
            "invited_email_fingerprint": email_fingerprint(text),
            "invited_email_recorded": False,
            "candidates": len(rows),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def accept_invite_and_create_membership(
    *,
    connection: Any = None,
    invite_id: str,
    organization_id: Any = None,
    accepted_by_identity_id: Any = None,
    now: datetime | None = None,
    membership_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Accept one invite and write the membership it produced, or neither.

    The order matters and is not arbitrary: the invite is read and every
    refusal evaluated *before* anything is written, then the acceptance and the
    membership go in together. Writing the membership first would leave a
    member whose invite was never consumed; writing the acceptance first would
    consume an invite that produced nobody.
    """
    moment = now or datetime.now(UTC)
    organization = _as_uuid(organization_id)
    accepter = _as_uuid(accepted_by_identity_id)
    blocked: list[str] = []

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")
    if organization is None:
        blocked.append("acceptance_without_an_organization_id_anchor")
    if accepter is None:
        blocked.append("acceptance_without_an_accepting_identity")
    if len(str(invite_id)) > MEMBERSHIP_INVITE_ID_MAX:
        blocked.append(INVITE_ID_TOO_LONG)

    # -- demo scope, derived ------------------------------------------------
    classification = classify_organization(organization_id, connection=connection)
    if not classification.get("classification_available"):
        blocked.append("organization_could_not_be_classified")
    elif not classification.get("is_demo"):
        blocked.append(NOT_DEMO)

    # -- the invite, read once ---------------------------------------------
    invite = None
    if connection is not None and organization is not None:
        invite = (
            connection.execute(
                sa.select(INVITES).where(
                    INVITES.c.organization_id == organization,
                    INVITES.c.invite_id == str(invite_id),
                )
            )
            .mappings()
            .first()
        )
        if invite is None:
            blocked.append("invite_not_found")

    # -- seats and duplicates, counted -------------------------------------
    seat_count: int | None = None
    seat_cap: int | None = None
    already_member = False
    if connection is not None and organization is not None:
        try:
            seat_count = int(
                connection.execute(
                    sa.select(sa.func.count())
                    .select_from(MEMBERSHIPS)
                    .where(
                        MEMBERSHIPS.c.organization_id == organization,
                        MEMBERSHIPS.c.state == "active",
                        MEMBERSHIPS.c.revoked_at.is_(None),
                    )
                ).scalar_one()
            )
            if accepter is not None:
                already_member = bool(
                    connection.execute(
                        sa.select(sa.func.count())
                        .select_from(MEMBERSHIPS)
                        .where(
                            MEMBERSHIPS.c.organization_id == organization,
                            MEMBERSHIPS.c.identity_id == accepter,
                        )
                    ).scalar_one()
                )
        except Exception:
            blocked.append("membership_table_unreadable")

    if invite is not None:
        seat_cap = int(invite["seat_cap"] or 0)
        if seat_count is not None and seat_cap and seat_count >= seat_cap:
            blocked.append(SEAT_CAP_REACHED)
    if already_member:
        blocked.append(ALREADY_A_MEMBER)

    # -- provenance, asked rather than asserted ----------------------------
    provenance = evaluate_membership_provenance(
        organization_id=str(organization) if organization else "",
        subject_id=str(accepter) if accepter else None,
        provenance=PROVENANCE,
        invite_id=str(invite_id),
    )
    if not provenance.get("trusted"):
        blocked.append("membership_provenance_not_trusted")

    # -- and only now, the two writes --------------------------------------
    acceptance: dict[str, Any] = {
        "accepted": False,
        "rows_updated": 0,
        "blocked_reasons": ["acceptance_not_attempted"],
    }
    membership: dict[str, Any] = {
        "write_performed": False,
        "rows_written": 0,
        "blocked_reasons": ["membership_not_attempted"],
    }

    if not blocked and connection is not None and invite is not None:
        acceptance = record_acceptance(
            connection=connection,
            invite_id=str(invite_id),
            organization_id=organization,
            accepted_by_identity_id=accepter,
            now=moment,
        )
        if acceptance.get("accepted"):
            membership = insert_membership(
                connection=connection,
                membership_id=membership_id,
                organization_id=organization,
                identity_id=accepter,
                state="active",
                role=str(invite["requested_role"] or "") or None,
                membership_source=MEMBERSHIP_SOURCE,
                approved_by=invite["approved_by"],
                invited_by=invite["requested_by"],
                invite_id=str(invite_id),
                now=moment,
            )
            if not membership.get("write_performed"):
                # The acceptance is not allowed to stand on its own. Raising
                # is what makes "one transaction" true rather than intended -
                # the caller's `engine.begin()` rolls both back.
                blocked.extend(membership.get("blocked_reasons") or [])
                blocked.append("membership_write_failed_after_acceptance")
                raise InviteActivationFailed(sorted(set(blocked)))
        else:
            blocked.extend(acceptance.get("blocked_reasons") or [])

    activated = bool(acceptance.get("accepted") and membership.get("write_performed"))

    evidence = (
        build_invite_binding_evidence(connection=connection)
        if connection is not None
        else None
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invite_id": str(invite_id),
            "organization_id": str(organization) if organization else None,
            "is_demo": bool(classification.get("is_demo")),
            "membership_activated": activated,
            "invite_accepted": bool(acceptance.get("accepted")),
            "membership_rows_written": int(membership.get("rows_written") or 0),
            "provenance": PROVENANCE,
            "membership_source": MEMBERSHIP_SOURCE,
            "seat_cap": seat_cap,
            "seat_count_before": seat_count,
            "accepter_matched_the_invite": bool(
                acceptance.get("accepter_matched_the_invite")
            ),
            "self_dealt": bool(acceptance.get("self_dealt")),
            "invite_binding_passed": bool(
                (evidence or {}).get("invite_binding_passed")
            ),
            # Constants, so a future real-org path cannot inherit the claim.
            "real_customer_rows_written": 0,
            "email_sent": False,
            "invited_email_recorded": False,
            "provider_subject_recorded": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


class InviteActivationFailed(RuntimeError):
    """The acceptance succeeded and the membership did not.

    Raised so the caller's transaction rolls both back. A half-completed
    acceptance is worse than a refused one: the invite reads as consumed and
    its id cannot be reused, so the person it named cannot be invited again.
    """

    def __init__(self, blocked_reasons: list[str]) -> None:
        super().__init__(", ".join(blocked_reasons))
        self.blocked_reasons = list(blocked_reasons)


def activation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of an activation result."""
    fails: list[str] = []

    if result.get("membership_activated"):
        if not result.get("invite_accepted"):
            fails.append("membership_activated_without_an_accepted_invite")
        if not result.get("membership_rows_written"):
            fails.append("membership_activated_without_writing_a_membership")
        if not result.get("accepter_matched_the_invite"):
            fails.append("membership_activated_for_somebody_who_was_not_invited")
        if result.get("self_dealt"):
            fails.append("membership_activated_from_a_self_dealt_invite")
        if not result.get("is_demo"):
            fails.append("membership_activated_outside_a_demo_organization")
        if result.get("blocked_reasons"):
            fails.append("membership_activated_alongside_blockers")

    if result.get("invite_accepted") and not result.get("membership_rows_written"):
        fails.append("invite_accepted_without_a_membership")

    if result.get("provenance") != PROVENANCE:
        fails.append(f"provenance_changed:{result.get('provenance')}")
    if result.get("real_customer_rows_written"):
        fails.append("real_customer_rows_written")
    if result.get("email_sent"):
        fails.append("email_sent")
    if result.get("invited_email_recorded"):
        fails.append("invited_email_recorded")
    if result.get("provider_subject_recorded"):
        fails.append("provider_subject_recorded")

    if not result.get("membership_activated") and not result.get("blocked_reasons"):
        fails.append("nothing_activated_and_nothing_blocked_it")

    return fails
