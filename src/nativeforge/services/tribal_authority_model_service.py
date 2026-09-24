"""177B: identity, affiliation and authority are three questions, not one.

```text
IDENTITY VERIFIED     we know who this person is
AFFILIATION VERIFIED  we know they belong to this organisation
AUTHORITY VERIFIED    we know they may ACT for it
```

The survey found these collapsed: `nf_authority_proof_records` governs
authority through a single `state` column naming two of the three dimensions,
so "verified" could not say verified *as what*.

Collapsing them is not a modelling preference. A person with a working
`@tribe.gov` mailbox has proven control of a mailbox. That is identity
evidence, and possibly affiliation evidence. It says nothing about whether the
Tribal Council has authorised them to establish a tenant, invite staff and
represent the government to funders. A system that treats the three as one
boolean will let a summer intern with a `.gov` address speak for a sovereign
nation, and it will do so silently, because from the inside that looks
exactly like success.

So the three states live in three columns, are graded by three functions, and
`may_administer_tenant` requires all three independently. There is no single
`verified` flag anywhere in this module, and `describe_authority_model`
asserts its own absence.

## Why so many UNKNOWNs

Every dimension has an `UNKNOWN` distinct from `UNVERIFIED`. `UNVERIFIED`
means we looked and found nothing. `UNKNOWN` means we have not established
it - a record migrated from an older shape, a dimension the evidence did not
speak to. Treating the second as the first would silently convert "we never
asked" into "we asked and the answer was no", which is the same class of
error as a coverage percentage with an invented denominator.

## One evidence type is never enough for all Tribes

574 federally recognised Tribes plus state-recognised Tribes and Native
non-profits do not share one governance structure, one domain convention or
one document. A model that required, say, a Tribal resolution would exclude
organisations that do not issue them; one that accepted a matching email
domain would accept anyone who can register a lookalike domain. So authority
carries the METHOD by which it was established, and the methods are plural
and extensible.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

SCHEMA_VERSION = "nf_tribal_authority_model_v1"

AUTHORITY_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 177B: three vocabularies, deliberately not one.
# ---------------------------------------------------------------------------

# ---- identity: do we know who this person is? --------------------------
IDENTITY_UNVERIFIED = "UNVERIFIED"
IDENTITY_VERIFIED = "VERIFIED"
IDENTITY_REVIEW_REQUIRED = "REVIEW_REQUIRED"
IDENTITY_REVOKED = "REVOKED"
IDENTITY_UNKNOWN = "UNKNOWN"

IDENTITY_STATES: tuple[str, ...] = (
    IDENTITY_UNVERIFIED,
    IDENTITY_VERIFIED,
    IDENTITY_REVIEW_REQUIRED,
    IDENTITY_REVOKED,
    IDENTITY_UNKNOWN,
)

IDENTITY_MEANINGS: dict[str, str] = {
    IDENTITY_UNVERIFIED: "no identity evidence has been accepted",
    IDENTITY_VERIFIED: "this person's identity has been established",
    IDENTITY_REVIEW_REQUIRED: "identity evidence exists and a human must judge it",
    IDENTITY_REVOKED: "an identity we accepted has been withdrawn",
    IDENTITY_UNKNOWN: "we have not established this, which is not the same as no",
}

# ---- affiliation: do they belong to this organisation? ------------------
AFFILIATION_UNVERIFIED = "UNVERIFIED"
AFFILIATION_SELF_ASSERTED = "SELF_ASSERTED"
AFFILIATION_EVIDENCE_PROVIDED = "EVIDENCE_PROVIDED"
AFFILIATION_VERIFIED = "VERIFIED"
AFFILIATION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
AFFILIATION_REVOKED = "REVOKED"
AFFILIATION_UNKNOWN = "UNKNOWN"

AFFILIATION_STATES: tuple[str, ...] = (
    AFFILIATION_UNVERIFIED,
    AFFILIATION_SELF_ASSERTED,
    AFFILIATION_EVIDENCE_PROVIDED,
    AFFILIATION_VERIFIED,
    AFFILIATION_REVIEW_REQUIRED,
    AFFILIATION_REVOKED,
    AFFILIATION_UNKNOWN,
)

AFFILIATION_MEANINGS: dict[str, str] = {
    AFFILIATION_UNVERIFIED: "no affiliation evidence has been accepted",
    AFFILIATION_SELF_ASSERTED: "they said so, and saying so is not evidence",
    AFFILIATION_EVIDENCE_PROVIDED: "evidence exists and has not yet been judged",
    AFFILIATION_VERIFIED: "their belonging to this organisation is established",
    AFFILIATION_REVIEW_REQUIRED: "affiliation evidence conflicts or is unclear",
    AFFILIATION_REVOKED: "an affiliation we accepted has ended",
    AFFILIATION_UNKNOWN: "we have not established this",
}

# ---- authority: may they ACT for it? ------------------------------------
AUTHORITY_UNVERIFIED = "UNVERIFIED"
AUTHORITY_MANUALLY_VERIFIED = "MANUALLY_VERIFIED"
AUTHORITY_DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
AUTHORITY_ORG_ADMIN_CONFIRMED = "ORG_ADMIN_CONFIRMED"
AUTHORITY_REVIEW_REQUIRED = "REVIEW_REQUIRED"
AUTHORITY_REVOKED = "REVOKED"
AUTHORITY_EXPIRED = "EXPIRED"
AUTHORITY_UNKNOWN = "UNKNOWN"

AUTHORITY_STATES: tuple[str, ...] = (
    AUTHORITY_UNVERIFIED,
    AUTHORITY_MANUALLY_VERIFIED,
    AUTHORITY_DOCUMENT_VERIFIED,
    AUTHORITY_ORG_ADMIN_CONFIRMED,
    AUTHORITY_REVIEW_REQUIRED,
    AUTHORITY_REVOKED,
    AUTHORITY_EXPIRED,
    AUTHORITY_UNKNOWN,
)

AUTHORITY_MEANINGS: dict[str, str] = {
    AUTHORITY_UNVERIFIED: "nobody has established that they may act for this org",
    AUTHORITY_MANUALLY_VERIFIED: (
        "controlling-company personnel verified this out of band and signed for it"
    ),
    AUTHORITY_DOCUMENT_VERIFIED: (
        "a document from the organisation establishes the authority"
    ),
    AUTHORITY_ORG_ADMIN_CONFIRMED: (
        "an already-authorised administrator of THIS organisation conferred it"
    ),
    AUTHORITY_REVIEW_REQUIRED: "authority evidence conflicts or is unclear",
    AUTHORITY_REVOKED: "authority was withdrawn; the person and their work remain",
    AUTHORITY_EXPIRED: "authority had an end date and that date has passed",
    AUTHORITY_UNKNOWN: "we have not established this",
}

#: Authority states that permit administering a tenant - IF identity and
#: affiliation independently allow it. Never sufficient alone.
AUTHORITY_SUFFICIENT: frozenset[str] = frozenset(
    {
        AUTHORITY_MANUALLY_VERIFIED,
        AUTHORITY_DOCUMENT_VERIFIED,
        AUTHORITY_ORG_ADMIN_CONFIRMED,
    }
)

#: Identity states that permit administering a tenant.
IDENTITY_SUFFICIENT: frozenset[str] = frozenset({IDENTITY_VERIFIED})

#: Affiliation states that permit administering a tenant. SELF_ASSERTED is
#: deliberately absent: "I work there" is a claim, not evidence, and a system
#: that accepted it would have no affiliation model at all.
AFFILIATION_SUFFICIENT: frozenset[str] = frozenset({AFFILIATION_VERIFIED})

#: States that mean somebody deliberately took authority away. Distinguished
#: from EXPIRED, which nobody decided.
WITHDRAWN: frozenset[str] = frozenset(
    {IDENTITY_REVOKED, AFFILIATION_REVOKED, AUTHORITY_REVOKED}
)

#: States that send a case to a human rather than answering it.
ASKS_FOR_A_HUMAN: frozenset[str] = frozenset(
    {
        IDENTITY_REVIEW_REQUIRED,
        AFFILIATION_REVIEW_REQUIRED,
        AUTHORITY_REVIEW_REQUIRED,
        AFFILIATION_EVIDENCE_PROVIDED,
    }
)

GRANT_FIELDS: tuple[str, ...] = (
    "authority_id",
    "organization_id",
    "identity_id",
    "identity_status",
    "affiliation_status",
    "authority_status",
    "authority_method",
    "verified_by",
    "verified_at",
    "expires_at",
    "revoked_at",
    "revoked_by",
    "revoked_reason",
    "reason",
    "scope",
    "evidence_ids",
    "is_demo",
    "model_version",
)

#: 177E/177F. What an authority grant may cover. Scope is stated so that a
#: grant to manage a profile is not silently a grant to invite staff.
SCOPE_ADMINISTER_TENANT = "ADMINISTER_TENANT"
SCOPE_MANAGE_MEMBERS = "MANAGE_MEMBERS"
SCOPE_MANAGE_PROFILE = "MANAGE_PROFILE"
SCOPE_SUBMIT_APPLICATIONS = "SUBMIT_APPLICATIONS"

SCOPES: tuple[str, ...] = (
    SCOPE_ADMINISTER_TENANT,
    SCOPE_MANAGE_MEMBERS,
    SCOPE_MANAGE_PROFILE,
    SCOPE_SUBMIT_APPLICATIONS,
)

SCOPE_MEANINGS: dict[str, str] = {
    SCOPE_ADMINISTER_TENANT: "establish and administer the organisation's tenant",
    SCOPE_MANAGE_MEMBERS: "invite, remove and re-role members of this organisation",
    SCOPE_MANAGE_PROFILE: "change the organisation's profile and defaults",
    SCOPE_SUBMIT_APPLICATIONS: "act on funding pursuits for this organisation",
}


def _as_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def build_authority_id(*, organization_id: Any, identity_id: Any, scope: Any) -> str:
    """Derived, so the same grant recorded twice is one grant."""
    parts = [str(organization_id or ""), str(identity_id or ""), str(scope or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_authority_grant(
    *,
    organization_id: Any,
    identity_id: Any,
    identity_status: str = IDENTITY_UNKNOWN,
    affiliation_status: str = AFFILIATION_UNKNOWN,
    authority_status: str = AUTHORITY_UNKNOWN,
    authority_method: Any = None,
    scope: str = SCOPE_ADMINISTER_TENANT,
    verified_by: Any = None,
    verified_at: Any = None,
    expires_at: Any = None,
    reason: Any = None,
    evidence_ids: list[str] | None = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """One grant, carrying three independent states and never a summary flag."""
    return {
        "schema_version": SCHEMA_VERSION,
        "authority_id": build_authority_id(
            organization_id=organization_id, identity_id=identity_id, scope=scope
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "identity_id": str(identity_id) if identity_id else None,
        # Three questions. Three answers. No fourth field summarising them,
        # because a summary is what everything downstream would read instead.
        "identity_status": str(identity_status),
        "affiliation_status": str(affiliation_status),
        "authority_status": str(authority_status),
        "authority_method": str(authority_method) if authority_method else None,
        "scope": str(scope),
        "verified_by": str(verified_by) if verified_by else None,
        "verified_at": verified_at,
        "expires_at": expires_at,
        "revoked_at": None,
        "revoked_by": None,
        "revoked_reason": None,
        "reason": str(reason) if reason else None,
        "evidence_ids": sorted(evidence_ids or []),
        "is_demo": bool(is_demo),
        "model_version": AUTHORITY_MODEL_VERSION,
    }


def effective_authority_status(grant: dict[str, Any], *, now: Any = None) -> str:
    """What the authority status IS today, expiry and revocation applied.

    Stored state is what somebody decided. Effective state is what is true
    now. A grant that expired last week still reads MANUALLY_VERIFIED in the
    column, and reading the column is how an expired administrator keeps
    administering.
    """
    stored = str(grant.get("authority_status") or AUTHORITY_UNKNOWN)
    if grant.get("revoked_at"):
        return AUTHORITY_REVOKED
    if stored == AUTHORITY_REVOKED:
        return AUTHORITY_REVOKED

    expires = _as_date(grant.get("expires_at"))
    today = _as_date(now) or dt.datetime.now(dt.UTC).date()
    if expires and today > expires:
        return AUTHORITY_EXPIRED
    return stored


def may_administer_tenant(
    grant: dict[str, Any], *, scope: str = SCOPE_ADMINISTER_TENANT, now: Any = None
) -> dict[str, Any]:
    """Three independent questions, answered separately, then combined.

    Returns the three sub-answers alongside the verdict. A caller that wants
    to know WHY is not forced to re-derive it, and a caller that logs the
    refusal logs which dimension failed.
    """
    identity = str(grant.get("identity_status") or IDENTITY_UNKNOWN)
    affiliation = str(grant.get("affiliation_status") or AFFILIATION_UNKNOWN)
    authority = effective_authority_status(grant, now=now)
    granted_scope = str(grant.get("scope") or "")

    identity_ok = identity in IDENTITY_SUFFICIENT
    affiliation_ok = affiliation in AFFILIATION_SUFFICIENT
    authority_ok = authority in AUTHORITY_SUFFICIENT
    scope_ok = granted_scope == str(scope)

    refusals: list[str] = []
    if not identity_ok:
        refusals.append(f"identity_is_{identity}")
    if not affiliation_ok:
        refusals.append(f"affiliation_is_{affiliation}")
    if not authority_ok:
        refusals.append(f"authority_is_{authority}")
    if not scope_ok:
        refusals.append(f"scope_is_{granted_scope or 'missing'}_not_{scope}")

    return {
        "schema_version": SCHEMA_VERSION,
        "permitted": not refusals,
        # The three answers, kept apart on the way out as well as in.
        "identity_sufficient": identity_ok,
        "affiliation_sufficient": affiliation_ok,
        "authority_sufficient": authority_ok,
        "scope_matches": scope_ok,
        "identity_status": identity,
        "affiliation_status": affiliation,
        "authority_status_stored": str(
            grant.get("authority_status") or AUTHORITY_UNKNOWN
        ),
        "authority_status_effective": authority,
        "requested_scope": str(scope),
        "refusals": refusals,
        "review_required": any(
            state in ASKS_FOR_A_HUMAN for state in (identity, affiliation, authority)
        ),
    }


def revoke_authority(
    *,
    grant: dict[str, Any],
    revoked_by: Any,
    reason: Any,
    revoked_at: Any = None,
    remove_membership: bool = False,
) -> dict[str, Any]:
    """177J: take away the authority, and nothing else.

    Revocation removes the right to administer. It does NOT delete the
    organisation, the historical work, or the audit trail, and it does not by
    itself end ordinary membership - a council member who loses signing
    authority is still a member of the Tribe. Removing membership is a
    separate decision and must be asked for explicitly.
    """
    if not revoked_by:
        return {
            "accepted": False,
            "why": "revocation requires a named actor",
            "grant": grant,
        }
    if not reason:
        return {
            "accepted": False,
            "why": "revocation requires a stated reason",
            "grant": grant,
        }

    revoked = dict(grant)
    revoked["authority_status"] = AUTHORITY_REVOKED
    revoked["revoked_at"] = revoked_at or dt.datetime.now(dt.UTC).isoformat()
    revoked["revoked_by"] = str(revoked_by)
    revoked["revoked_reason"] = str(reason)
    # Identity and affiliation are untouched on purpose. Losing authority is
    # not a statement about who somebody is or where they work.
    return {
        "accepted": True,
        "grant": revoked,
        "authority_removed": True,
        "organization_deleted": False,
        "historical_work_deleted": False,
        "audit_history_erased": False,
        "membership_removed": bool(remove_membership),
        "membership_removal_was_requested_separately": bool(remove_membership),
        "why": str(reason),
    }


def grant_invariant_failures(grant: dict[str, Any]) -> list[str]:
    """Refuse a grant that claims more than its evidence supports."""
    failures: list[str] = []

    for field in GRANT_FIELDS:
        if field not in grant:
            failures.append(f"grant_missing_field:{field}")

    identity = str(grant.get("identity_status") or "")
    affiliation = str(grant.get("affiliation_status") or "")
    authority = str(grant.get("authority_status") or "")

    if identity not in IDENTITY_STATES:
        failures.append(f"identity_outside_the_vocabulary:{identity or 'missing'}")
    if affiliation not in AFFILIATION_STATES:
        failures.append(
            f"affiliation_outside_the_vocabulary:{affiliation or 'missing'}"
        )
    if authority not in AUTHORITY_STATES:
        failures.append(f"authority_outside_the_vocabulary:{authority or 'missing'}")
    if str(grant.get("scope") or "") not in SCOPES:
        failures.append(f"scope_outside_the_vocabulary:{grant.get('scope')}")

    # Verified authority must say who verified it and why. An authority
    # nobody signed for is the thing this gate exists to prevent.
    if authority in AUTHORITY_SUFFICIENT:
        if not grant.get("verified_by"):
            failures.append("verified_authority_names_no_verifier")
        if not grant.get("verified_at"):
            failures.append("verified_authority_has_no_date")
        if not grant.get("reason"):
            failures.append("verified_authority_states_no_reason")
        if not grant.get("evidence_ids") and authority != AUTHORITY_MANUALLY_VERIFIED:
            failures.append("verified_authority_references_no_evidence")

    # Authority may not outrank the dimensions beneath it.
    if authority in AUTHORITY_SUFFICIENT and affiliation not in AFFILIATION_SUFFICIENT:
        failures.append(f"authority_{authority}_over_affiliation_{affiliation}")
    if authority in AUTHORITY_SUFFICIENT and identity not in IDENTITY_SUFFICIENT:
        failures.append(f"authority_{authority}_over_identity_{identity}")

    if grant.get("revoked_at") and not grant.get("revoked_by"):
        failures.append("revoked_grant_names_no_actor")
    if grant.get("revoked_at") and not grant.get("revoked_reason"):
        failures.append("revoked_grant_states_no_reason")

    # The refusal that keeps the three questions three.
    for forbidden in ("verified", "is_verified", "authority_verified"):
        if forbidden in grant:
            failures.append(f"grant_carries_a_collapsing_flag:{forbidden}")

    return sorted(set(failures))


def describe_authority_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": AUTHORITY_MODEL_VERSION,
        "identity_states": list(IDENTITY_STATES),
        "affiliation_states": list(AFFILIATION_STATES),
        "authority_states": list(AUTHORITY_STATES),
        "scopes": list(SCOPES),
        "every_identity_state_has_a_meaning": set(IDENTITY_MEANINGS)
        == set(IDENTITY_STATES),
        "every_affiliation_state_has_a_meaning": set(AFFILIATION_MEANINGS)
        == set(AFFILIATION_STATES),
        "every_authority_state_has_a_meaning": set(AUTHORITY_MEANINGS)
        == set(AUTHORITY_STATES),
        "every_scope_has_a_meaning": set(SCOPE_MEANINGS) == set(SCOPES),
        # The load-bearing claims.
        "three_dimensions_are_independent": True,
        "no_single_verified_boolean": not any(
            field in GRANT_FIELDS
            for field in ("verified", "is_verified", "authority_verified")
        ),
        "self_asserted_affiliation_is_never_sufficient": (
            AFFILIATION_SELF_ASSERTED not in AFFILIATION_SUFFICIENT
        ),
        "authority_may_not_outrank_affiliation": True,
        "expiry_is_applied_at_read_time": True,
        "revocation_preserves_the_organization": True,
        "revocation_preserves_historical_work": True,
        "revocation_preserves_audit_history": True,
        "membership_removal_is_a_separate_decision": True,
        "one_evidence_type_is_never_assumed_sufficient": True,
        "unknown_is_distinct_from_unverified": (
            IDENTITY_UNKNOWN != IDENTITY_UNVERIFIED
        ),
    }
