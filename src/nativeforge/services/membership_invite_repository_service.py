"""Gate 135C: the invite decision, written down.

`membership_invite_approval_service` decides and persists nothing — 694 lines,
`persisted: False` on every result, zero callers in `src/`. This is the seam
between that decision and migration 0038's table, built the way Gate 120's
binding repository was: the decision is made by the service and consumed here,
so the two cannot disagree about what is storable.

## The rule this exists to keep honest

```python
TRUSTED_PROVENANCES = {"completed_invite"}
```

A membership that did not come through a completed invite is not trusted, and a
completed invite must name itself — `completed_invite_provenance_without_invite_id`
is one of the service's refusals. That refusal is unfalsifiable while there is
nowhere for the invite to be, which is what this fixes.

## Self-dealing is refused here, on every dialect

An invite whose requester, approver and accepter are one person authorizes
nothing. The whole contract exists because somebody else has to say yes, and
`evaluate_invite` does **not** catch this — asked to evaluate the org owner
inviting themselves, approved by themselves, it returns no blocked reasons,
because every seat and role check is about the same person and they all pass.

Found while surveying Gate 135. Refused here rather than left to the PostgreSQL
CHECK, because the dev database is SQLite and a guard that only fires in
production is not a guard for the environment this runs in.

## Acceptance is where a person is required

`record_acceptance` needs an `accepted_by_identity_id` that is a real
`nf_identities` row and is not the requester or the approver. That is the step
no amount of code can supply: it is somebody logging in. An invite that has been
issued and approved but never accepted has bound nobody, and
`build_invite_binding_evidence` says so rather than counting it.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.membership_invite_approval_service import (
    APPROVAL_STATES,
    INVITE_STATES,
    TRUSTED_PROVENANCES,
    evaluate_invite,
)

SCHEMA_VERSION = "nf_membership_invite_repository_v1"

TABLE_NAME = "nf_membership_invites"
MEMBERSHIP_TABLE = "nf_org_memberships"
IDENTITY_TABLE = "nf_identities"

#: Fields a stored invite carries. Nothing outside this list is written, and a
#: test asserts the table's columns and this tuple agree.
INVITE_FIELDS: tuple[str, ...] = (
    "invite_id",
    "organization_id",
    "is_demo",
    "requested_role",
    "requested_by",
    "requested_by_role",
    "invited_email_domain",
    "invited_subject_fingerprint",
    # Gate 136A. The subject fingerprint is null on every invite anybody can
    # actually issue - an owner inviting somebody knows their address and
    # cannot know their Google subject - so acceptance had nothing to match
    # against. sha256(lower(strip(email)))[:32]; still never the address.
    "invited_email_fingerprint",
    "invite_state",
    "approval_state",
    "approved_by",
    "approved_by_role",
    "accepted_by_identity_id",
    "seat_cap",
    "seat_count",
    "expires_at",
    "accepted_at",
    "revoked_at",
    "blocked_reasons",
)

#: Values an invite must never keep. Named so the refusal is testable rather
#: than implied by the absence of a column.
FORBIDDEN_INVITE_KEYS: tuple[str, ...] = (
    "invited_email",
    "invited_subject",
    "email",
    "subject",
    "token",
    "id_token",
    "access_token",
)

SELF_DEALT = "invite_requested_approved_and_accepted_by_one_identity"

#: Gate 136A found `record_acceptance` reading none of the invite's own
#: identifying fields, so any existing identity that was not the requester or
#: the approver could accept any invite. These are the three refusals that were
#: missing, named individually because "acceptance refused" is not an answer.
ACCEPTER_NOT_INVITED = "accepting_identity_is_not_the_invited_identity"
INVITE_EXPIRED = "invite_expired"
ALREADY_ACCEPTED = "invite_already_accepted"

_METADATA = sa.MetaData()

INVITES = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("invite_id", sa.String(length=128), nullable=False),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("requested_role", sa.String(length=64), nullable=False),
    sa.Column("requested_by", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("requested_by_role", sa.String(length=64), nullable=False),
    sa.Column("invited_email_domain", sa.String(length=255), nullable=True),
    sa.Column("invited_subject_fingerprint", sa.String(length=32), nullable=True),
    sa.Column("invited_email_fingerprint", sa.String(length=64), nullable=True),
    sa.Column("invite_state", sa.String(length=32), nullable=False),
    sa.Column("approval_state", sa.String(length=32), nullable=False),
    sa.Column("approved_by", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("approved_by_role", sa.String(length=64), nullable=True),
    sa.Column("accepted_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("seat_count", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.CheckConstraint(
        "accepted_at IS NULL OR invite_state = 'accepted'",
        name="ck_nf_membership_invites_accepted_at_needs_state",
    ),
    sa.CheckConstraint(
        "invite_state <> 'accepted' OR accepted_by_identity_id IS NOT NULL",
        name="ck_nf_membership_invites_accepted_needs_accepter",
    ),
    sa.UniqueConstraint(
        "organization_id", "invite_id", name="uq_nf_membership_invites_org_invite"
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _fingerprint(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def email_fingerprint(email: Any) -> str | None:
    """A stable handle for an invited address that is not the address.

    Lower-cased and stripped first, because `A@B.com` and `a@b.com` are one
    mailbox and an invite that did not agree would refuse the person it named.

    Not secrecy, and not claimed as secrecy - plausible addresses are few
    enough to enumerate. It is matching: enough for acceptance to require that
    the identity accepting is the identity invited, without the row holding the
    address that would let something else send to it.
    """
    text = str(email or "").strip().lower()
    if not text or "@" not in text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _domain(email: Any) -> str | None:
    text = str(email or "").strip()
    if "@" not in text:
        return None
    return text.rpartition("@")[2] or None


def _accepter_matches_invite(row: Any, accepter_email: Any) -> bool:
    """Is this identity the one the invite names?

    Deny by default. The invite is asked what it knows, in order, and the
    first thing it actually recorded decides:

    ```text
    invited_email_fingerprint   exact, one mailbox
    invited_email_domain        the org's domain, when no address was named
    ```

    An invite that recorded neither identifies nobody, and an acceptance
    against it is refused - not admitted on the grounds that there was nothing
    to check. That inversion is how the original gap worked.
    """
    fingerprint = row["invited_email_fingerprint"] if row is not None else None
    domain = row["invited_email_domain"] if row is not None else None

    if fingerprint:
        return bool(
            accepter_email and email_fingerprint(accepter_email) == str(fingerprint)
        )
    if domain:
        return bool(
            accepter_email
            and _domain(accepter_email)
            and str(_domain(accepter_email)).lower() == str(domain).strip().lower()
        )
    return False


def _moment(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def prepare_invite_record(
    *,
    organization_id: Any = None,
    is_demo: bool = False,
    accepted_by_identity_id: Any = None,
    **invite_fields: Any,
) -> dict[str, Any]:
    """Reduce an invite to what may be stored. Decided by the service.

    ``is_demo`` is passed rather than derived here because the caller already
    classified the organization - `insert_invite` derives it from the row when
    it has a connection, and refuses a mismatch.
    """
    decision = evaluate_invite(
        organization_id=str(organization_id or ""), **invite_fields
    )
    blocked: list[str] = list(decision["blocked_reasons"])

    organization = _as_uuid(organization_id)
    if organization is None:
        blocked.append("invite_without_an_organization_id_anchor")

    requester = _as_uuid(invite_fields.get("requested_by"))
    approver = _as_uuid(invite_fields.get("approved_by"))
    accepter = _as_uuid(accepted_by_identity_id)

    if requester is None:
        blocked.append("invite_without_a_requester")

    # The gap `evaluate_invite` does not close. Every seat and role check passes
    # when one person plays all three parts, because they are all about the same
    # person.
    if accepter is not None and accepter in {requester, approver}:
        blocked.append(SELF_DEALT)

    state = str(decision.get("invite_state") or "unknown")
    approval = str(decision.get("approval_state") or "unknown")
    if state not in INVITE_STATES:
        blocked.append(f"invite_state_not_recognised:{state}")
    if approval not in APPROVAL_STATES:
        blocked.append(f"approval_state_not_recognised:{approval}")

    if state == "accepted" and accepter is None:
        blocked.append("accepted_invite_without_an_accepter")
    if accepter is not None and state != "accepted":
        blocked.append("accepter_recorded_on_an_unaccepted_invite")

    # Strings, because this is reported. `insert_invite` converts back to the
    # column types - reporting and writing want different shapes, and returning
    # UUIDs and datetimes made the result unserialisable.
    def _text(value: Any) -> str | None:
        return str(value) if value is not None else None

    record = {
        "invite_id": str(invite_fields.get("invite_id") or "").strip(),
        "organization_id": _text(organization),
        "is_demo": bool(is_demo),
        "requested_role": str(decision.get("requested_role") or "unknown"),
        "requested_by": _text(requester),
        "requested_by_role": str(invite_fields.get("requested_by_role") or "unknown"),
        # The domain half and a fingerprint. Never the address, never the subject.
        "invited_email_domain": _domain(invite_fields.get("invited_email")),
        "invited_subject_fingerprint": _fingerprint(
            invite_fields.get("invited_subject")
        ),
        "invited_email_fingerprint": email_fingerprint(
            invite_fields.get("invited_email")
        ),
        "invite_state": state,
        "approval_state": approval,
        "approved_by": _text(approver),
        "approved_by_role": (str(invite_fields.get("approved_by_role") or "") or None),
        "accepted_by_identity_id": _text(accepter),
        "seat_cap": int(decision.get("seat_cap") or 0),
        "seat_count": int(decision.get("seat_count") or 0),
        "expires_at": _text(_moment(invite_fields.get("expires_at"))),
        "accepted_at": _text(_moment(invite_fields.get("accepted_at"))),
        "revoked_at": _text(_moment(invite_fields.get("revoked_at"))),
        "blocked_reasons": sorted(set(blocked)),
    }

    if not record["invite_id"]:
        blocked.append("invite_without_an_invite_id")
        record["blocked_reasons"] = sorted(set(blocked))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "record": record,
            "service_allowed": bool(decision.get("allowed")),
            "can_activate_membership": bool(decision.get("can_activate_membership")),
            "storage_allowed": not blocked,
            "write_performed": False,
            "rows_written": 0,
            "self_dealt": SELF_DEALT in blocked,
            "email_address_recorded": False,
            "provider_subject_recorded": False,
            "email_sent": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def insert_invite(
    *,
    connection: Any = None,
    row_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    organization_id: Any = None,
    accepted_by_identity_id: Any = None,
    **invite_fields: Any,
) -> dict[str, Any]:
    """Write one invite, if the service and this repository both permit it.

    The row's timestamp is ``created_at``, not ``now``. `evaluate_invite`
    takes a ``now`` of its own - an ISO string it compares against
    ``expires_at`` - and a repository parameter of the same name silently
    captured it: the service never saw the clock it was given, and a string
    reached a DateTime column. Two meanings of *now* in one call is a
    collision waiting for somebody, and the caller passing both is doing
    nothing wrong.
    """
    from nativeforge.services.demo_org_classification_service import (
        classify_organization,
    )

    classification = classify_organization(organization_id, connection=connection)
    decision = prepare_invite_record(
        organization_id=organization_id,
        is_demo=bool(classification.get("is_demo")),
        accepted_by_identity_id=accepted_by_identity_id,
        **invite_fields,
    )
    blocked = list(decision["blocked_reasons"])

    if not classification.get("classification_available"):
        blocked.append("organization_could_not_be_classified")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if decision["storage_allowed"] and connection is not None and not blocked:
        record = dict(decision["record"])
        values = {
            **record,
            "organization_id": _as_uuid(record["organization_id"]),
            "requested_by": _as_uuid(record["requested_by"]),
            "approved_by": _as_uuid(record["approved_by"]),
            "accepted_by_identity_id": _as_uuid(record["accepted_by_identity_id"]),
            "expires_at": _moment(record["expires_at"]),
            "accepted_at": _moment(record["accepted_at"]),
            "revoked_at": _moment(record["revoked_at"]),
        }
        connection.execute(
            sa.insert(INVITES).values(
                id=row_id or uuid.uuid4(),
                created_at=created_at or datetime.now(UTC),
                **values,
            )
        )
        written = 1

    return _json_safe(
        {
            **decision,
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def record_acceptance(
    *,
    connection: Any = None,
    invite_id: str,
    organization_id: Any = None,
    accepted_by_identity_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Mark an invite accepted by the identity it was actually issued to.

    This is the step nothing here can supply on its own. An accepter must be a
    real `nf_identities` row, must not be the requester or the approver, and -
    since Gate 136 - must be the person the invite names.

    ## What Gate 136A found missing

    ```text
    an EXPIRED invite could be accepted
    an invite already in state 'accepted' could be accepted again, by
      somebody else, overwriting who accepted it
    the accepter was never checked against the invite at all
    ```

    The last one made the invite's own `invited_email_domain` and
    `invited_subject_fingerprint` decorative: the row named who it was for and
    nothing looked. Any identity in the database that was not the invite's
    author could accept any invite, which is not an invite - it is a queue.

    The match is against the invited identity's stored email, fingerprinted the
    same way the invite fingerprinted it. An identity whose email is absent
    cannot be matched and is refused rather than admitted, because an accepter
    nothing can identify is the one case this function exists to stop.
    """
    organization = _as_uuid(organization_id)
    accepter = _as_uuid(accepted_by_identity_id)
    blocked: list[str] = []

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")
    if organization is None:
        blocked.append("acceptance_without_an_organization_id_anchor")
    if accepter is None:
        blocked.append("acceptance_without_an_accepting_identity")

    row = None
    if connection is not None and organization is not None:
        row = (
            connection.execute(
                sa.select(INVITES).where(
                    INVITES.c.organization_id == organization,
                    INVITES.c.invite_id == str(invite_id),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked.append("invite_not_found")

    accepter_email: str | None = None
    if connection is not None and accepter is not None:
        found = (
            connection.execute(
                sa.text(f"SELECT email FROM {IDENTITY_TABLE} WHERE id = :i"),
                {"i": accepter.hex},
            )
            .mappings()
            .first()
        )
        if found is None:
            # An acceptance by nobody is the shape of a faked user.
            blocked.append("accepting_identity_does_not_exist")
        else:
            accepter_email = found["email"]

    if row is not None:
        if row["revoked_at"] is not None:
            blocked.append("invite_revoked")
        if str(row["approval_state"]) not in {"approved", "not_required"}:
            blocked.append(f"invite_not_approved:{row['approval_state']}")
        if str(row["invite_state"]) == "accepted":
            # Re-accepting would move accepted_by_identity_id to a different
            # person, which is the one column the CHECK exists to pin down.
            blocked.append(ALREADY_ACCEPTED)
        expires = _moment(row["expires_at"])
        if expires is not None and (now or datetime.now(UTC)) >= expires:
            # `evaluate_invite` derives expiry from the timestamp rather than
            # the state column, and this had no equivalent. An invite with a
            # deadline that nothing enforces has no deadline.
            blocked.append(INVITE_EXPIRED)
        if accepter is not None and accepter in {
            _as_uuid(row["requested_by"]),
            _as_uuid(row["approved_by"]),
        }:
            blocked.append(SELF_DEALT)
        if accepter is not None and "accepting_identity_does_not_exist" not in blocked:
            if not _accepter_matches_invite(row, accepter_email):
                blocked.append(ACCEPTER_NOT_INVITED)

    written = 0
    if not blocked and connection is not None and row is not None:
        connection.execute(
            sa.update(INVITES)
            .where(
                INVITES.c.organization_id == organization,
                INVITES.c.invite_id == str(invite_id),
            )
            .values(
                invite_state="accepted",
                accepted_by_identity_id=accepter,
                accepted_at=now or datetime.now(UTC),
            )
        )
        written = 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "invite_id": str(invite_id),
            "organization_id": str(organization) if organization else None,
            "accepted": bool(written),
            "rows_updated": written,
            "self_dealt": SELF_DEALT in blocked,
            "accepter_matched_the_invite": ACCEPTER_NOT_INVITED not in blocked,
            "accepter_email_recorded": False,
            "email_sent": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def build_invite_binding_evidence(*, connection: Any = None) -> dict[str, Any]:
    """Has an invite actually bound anybody? Ask the rows.

    An invite that was issued and approved and never accepted has bound nobody,
    and a membership that did not come through one is `operator_direct_write`,
    which `TRUSTED_PROVENANCES` refuses. Both are counted separately so the
    difference is visible rather than rolled into one boolean.
    """
    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "connection_supplied": False,
                "invite_rows": 0,
                "approved_invite_rows": 0,
                "accepted_invite_rows": 0,
                "memberships_from_a_completed_invite": 0,
                "memberships_matching_an_accepter_by_identity_only": 0,
                "membership_rows": 0,
                "invite_binding_passed": False,
                "trusted_provenances": sorted(TRUSTED_PROVENANCES),
                "blocked_reasons": ["no_connection_supplied"],
            }
        )

    blocked: list[str] = []
    invite_rows = approved = accepted = 0
    memberships = 0
    from_invite = 0

    try:
        invite_rows = int(
            connection.execute(
                sa.select(sa.func.count()).select_from(INVITES)
            ).scalar_one()
        )
        approved = int(
            connection.execute(
                sa.select(sa.func.count())
                .select_from(INVITES)
                .where(
                    INVITES.c.approval_state.in_(["approved", "not_required"]),
                    INVITES.c.revoked_at.is_(None),
                )
            ).scalar_one()
        )
        accepted_rows = (
            connection.execute(
                sa.select(
                    INVITES.c.invite_id,
                    INVITES.c.accepted_by_identity_id,
                ).where(
                    INVITES.c.invite_state == "accepted",
                    INVITES.c.accepted_by_identity_id.isnot(None),
                    INVITES.c.revoked_at.is_(None),
                )
            )
            .mappings()
            .all()
        )
        accepted = len(accepted_rows)
        accepted_identities = {
            _as_uuid(row["accepted_by_identity_id"]) for row in accepted_rows
        }
        # (invite_id, accepter) together. Either half alone is what the
        # inference below used to settle for.
        accepted_pairs = {
            (str(row["invite_id"]), _as_uuid(row["accepted_by_identity_id"]))
            for row in accepted_rows
        }
    except Exception:
        blocked.append("invite_table_unreadable")
        accepted_identities = set()
        accepted_pairs = set()

    try:
        membership_rows = (
            connection.execute(
                sa.text(
                    f"SELECT identity_id, invite_id FROM {MEMBERSHIP_TABLE} "
                    "WHERE state = 'active' AND revoked_at IS NULL"
                )
            )
            .mappings()
            .all()
        )
        memberships = len(membership_rows)
        # Gate 136A. This counted a membership as invite-derived when the
        # member's identity appeared among the identities that had accepted an
        # invite - so a membership an operator wrote for somebody who
        # separately accepted one counted, and `TRUSTED_PROVENANCES` was
        # satisfied by a coincidence.
        #
        # Migration 0039 gave the membership row somewhere to name its invite,
        # so this is a join: the membership names an invite, that invite was
        # accepted, and the accepter is this member.
        from_invite = sum(
            1
            for row in membership_rows
            if row["invite_id"]
            and (str(row["invite_id"]), _as_uuid(row["identity_id"])) in accepted_pairs
        )
        # Kept beside it, because the difference between the two is the defect
        # and a single number would hide it going back.
        by_identity_only = sum(
            1
            for row in membership_rows
            if _as_uuid(row["identity_id"]) in accepted_identities
        )
    except Exception:
        blocked.append("membership_table_unreadable")
        by_identity_only = 0

    # Derived affirmatively. An accepted invite, and a membership the accepter
    # actually holds. Either alone proves nothing.
    passed = bool(accepted and from_invite and not blocked)

    if not invite_rows:
        blocked.append("no_invite_has_been_recorded")
    elif not accepted:
        blocked.append("no_invite_has_been_accepted_by_an_identity")
    elif not from_invite:
        blocked.append("no_active_membership_came_through_a_completed_invite")
        if by_identity_only:
            # The state the old inference would have passed on. Named, so a
            # membership that merely shares an identity with an acceptance
            # reads as the near-miss it is rather than as nothing at all.
            blocked.append("membership_shares_an_identity_but_does_not_name_the_invite")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "connection_supplied": True,
            "invite_rows": invite_rows,
            "approved_invite_rows": approved,
            "accepted_invite_rows": accepted,
            "membership_rows": memberships,
            "memberships_from_a_completed_invite": from_invite,
            "memberships_matching_an_accepter_by_identity_only": by_identity_only,
            "invite_binding_passed": passed,
            "trusted_provenances": sorted(TRUSTED_PROVENANCES),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def invite_evidence_invariant_failures(evidence: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if evidence.get("invite_binding_passed"):
        if not evidence.get("connection_supplied"):
            fails.append("invite_binding_passed_without_reading_anything")
        if not evidence.get("accepted_invite_rows"):
            fails.append("invite_binding_passed_without_an_accepted_invite")
        if not evidence.get("memberships_from_a_completed_invite"):
            fails.append("invite_binding_passed_without_a_membership_from_one")
        if evidence.get("blocked_reasons"):
            fails.append("invite_binding_passed_alongside_blockers")

    if evidence.get("accepted_invite_rows", 0) > evidence.get("invite_rows", 0):
        fails.append("more_accepted_invites_than_invites")
    if evidence.get("memberships_from_a_completed_invite", 0) > evidence.get(
        "membership_rows", 0
    ):
        fails.append("more_invited_memberships_than_memberships")

    return fails


def invite_record_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a record that kept something it must not keep."""
    fails: list[str] = []
    record = result.get("record") or {}

    for key in record:
        if key not in INVITE_FIELDS:
            fails.append(f"record_carries_an_unknown_field:{key}")
    for key in FORBIDDEN_INVITE_KEYS:
        if key in record:
            fails.append(f"record_carries_a_forbidden_field:{key}")

    # A value check as well as a key check. An email address is a value.
    for key, value in record.items():
        if isinstance(value, str) and "@" in value:
            fails.append(f"record_carries_an_email_in:{key}")

    if result.get("rows_written") and not result.get("storage_allowed"):
        fails.append("invite_written_without_storage_permission")
    if result.get("rows_written") and result.get("self_dealt"):
        fails.append("self_dealt_invite_written")
    if result.get("email_sent"):
        fails.append("the_repository_sent_an_email")

    return fails
