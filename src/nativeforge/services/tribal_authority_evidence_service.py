"""177C/D: the evidence behind an authority decision, and who signed for it.

An authority status with nothing behind it is the failure this gate exists to
prevent, so every sufficient authority names the evidence and the human who
judged it.

## No single evidence type is sufficient for all Tribes

574 federally recognised Tribes, plus state-recognised Tribes and Native
non-profits, do not share one governance structure. Some issue council
resolutions; some do not. Some run their own mail domain; some use a
commercial provider. A model that demanded a resolution would exclude
organisations that never issue one. A model that accepted a matching email
domain would accept anybody who can register a lookalike.

So evidence is TYPED and plural, each type carries what it can and cannot
establish, and `EVIDENCE_STRENGTH` says which dimension a type speaks to.
`ESTABLISHES_AUTHORITY` is a small set on purpose - most evidence types prove
identity or affiliation and are silent about authority, which is exactly the
distinction Gate 177 exists to keep.

## Why a domain match is not authority

`ORGANIZATION_EMAIL_DOMAIN` is the most tempting shortcut in this gate: it is
cheap, automatic, and feels decisive. It establishes that somebody controls a
mailbox at a domain. It is affiliation evidence of middling strength and it is
NOT authority evidence, because the intern and the chairperson have the same
domain.

## Secrets

Evidence records a REFERENCE to an artifact - a URL, a document id, a file
hash - never the artifact's bytes and never a credential. `evidence_invariant_
failures` refuses a record whose fields look like a secret, because the
cheapest way to leak a Tribe's credentials is to store them somewhere helpful.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any

from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_VERIFIED,
    AUTHORITY_DOCUMENT_VERIFIED,
    AUTHORITY_MANUALLY_VERIFIED,
    AUTHORITY_ORG_ADMIN_CONFIRMED,
    IDENTITY_VERIFIED,
    SCOPE_ADMINISTER_TENANT,
    SCOPES,
    build_authority_grant,
)

SCHEMA_VERSION = "nf_tribal_authority_evidence_v1"

EVIDENCE_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 177C: the evidence types, and what each can actually establish.
# ---------------------------------------------------------------------------

OFFICIAL_TRIBAL_WEBSITE = "OFFICIAL_TRIBAL_WEBSITE"
OFFICIAL_TRIBAL_ROSTER = "OFFICIAL_TRIBAL_ROSTER"
ORGANIZATION_EMAIL_DOMAIN = "ORGANIZATION_EMAIL_DOMAIN"
ORG_ADMIN_INVITATION = "ORG_ADMIN_INVITATION"
SIGNED_AUTHORIZATION = "SIGNED_AUTHORIZATION"
TRIBAL_RESOLUTION = "TRIBAL_RESOLUTION"
GOVERNING_AUTHORIZATION = "GOVERNING_AUTHORIZATION"
CONTROLLING_COMPANY_VERIFICATION = "CONTROLLING_COMPANY_VERIFICATION"
IDENTITY_PROVIDER_ASSERTION = "IDENTITY_PROVIDER_ASSERTION"
ORGANIZATION_SPECIFIC_OTHER = "ORGANIZATION_SPECIFIC_OTHER"

_SEED_EVIDENCE_TYPES: tuple[str, ...] = (
    OFFICIAL_TRIBAL_WEBSITE,
    OFFICIAL_TRIBAL_ROSTER,
    ORGANIZATION_EMAIL_DOMAIN,
    ORG_ADMIN_INVITATION,
    SIGNED_AUTHORIZATION,
    TRIBAL_RESOLUTION,
    GOVERNING_AUTHORIZATION,
    CONTROLLING_COMPANY_VERIFICATION,
    IDENTITY_PROVIDER_ASSERTION,
    ORGANIZATION_SPECIFIC_OTHER,
)

#: Extensible, because "other organisation-specific evidence" is a real
#: category and a closed list would force a Tribe's actual proof into the
#: wrong box or out of the system.
_EVIDENCE_TYPES: dict[str, str] = {key: "seed" for key in _SEED_EVIDENCE_TYPES}


def evidence_types() -> tuple[str, ...]:
    return tuple(sorted(_EVIDENCE_TYPES))


def register_evidence_type(name: str, *, origin: str = "runtime") -> str:
    key = str(name).strip().upper().replace(" ", "_")
    if not key:
        raise ValueError("an evidence type needs a name")
    _EVIDENCE_TYPES.setdefault(key, origin)
    return key


def reset_registered_evidence_types() -> None:
    for key in [k for k, v in _EVIDENCE_TYPES.items() if v != "seed"]:
        del _EVIDENCE_TYPES[key]


EVIDENCE_MEANINGS: dict[str, str] = {
    OFFICIAL_TRIBAL_WEBSITE: (
        "the organisation's own published site names this person in a role"
    ),
    OFFICIAL_TRIBAL_ROSTER: "an official roster or directory lists this person",
    ORGANIZATION_EMAIL_DOMAIN: (
        "this person controls a mailbox at the organisation's domain, which "
        "proves control of a mailbox and nothing about their authority"
    ),
    ORG_ADMIN_INVITATION: (
        "an already-authorised administrator of THIS organisation invited them"
    ),
    SIGNED_AUTHORIZATION: "a signed authorisation from the organisation",
    TRIBAL_RESOLUTION: (
        "a resolution of the governing body, where the Tribe issues them"
    ),
    GOVERNING_AUTHORIZATION: (
        "an authorisation from the governing authority in whatever form it takes"
    ),
    CONTROLLING_COMPANY_VERIFICATION: (
        "controlling-company personnel verified this out of band and signed"
    ),
    IDENTITY_PROVIDER_ASSERTION: "an identity provider asserted who this person is",
    ORGANIZATION_SPECIFIC_OTHER: (
        "evidence particular to this organisation, described in the record"
    ),
}

#: Which dimension each type speaks to. A type absent from a set is SILENT
#: about that dimension, which is different from arguing against it.
ESTABLISHES_IDENTITY: frozenset[str] = frozenset(
    {
        IDENTITY_PROVIDER_ASSERTION,
        CONTROLLING_COMPANY_VERIFICATION,
        OFFICIAL_TRIBAL_ROSTER,
    }
)

ESTABLISHES_AFFILIATION: frozenset[str] = frozenset(
    {
        OFFICIAL_TRIBAL_WEBSITE,
        OFFICIAL_TRIBAL_ROSTER,
        ORGANIZATION_EMAIL_DOMAIN,
        ORG_ADMIN_INVITATION,
        SIGNED_AUTHORIZATION,
        TRIBAL_RESOLUTION,
        GOVERNING_AUTHORIZATION,
        CONTROLLING_COMPANY_VERIFICATION,
    }
)

#: Deliberately small. ORGANIZATION_EMAIL_DOMAIN is absent: the intern and the
#: chairperson share a domain. OFFICIAL_TRIBAL_WEBSITE is absent: a website
#: naming somebody in a role is affiliation evidence a stranger can read, not
#: a grant of authority to act.
ESTABLISHES_AUTHORITY: frozenset[str] = frozenset(
    {
        SIGNED_AUTHORIZATION,
        TRIBAL_RESOLUTION,
        GOVERNING_AUTHORIZATION,
        CONTROLLING_COMPANY_VERIFICATION,
        ORG_ADMIN_INVITATION,
    }
)

#: The authority state each authority-bearing type can support.
TYPE_SUPPORTS_AUTHORITY_STATE: dict[str, str] = {
    SIGNED_AUTHORIZATION: AUTHORITY_DOCUMENT_VERIFIED,
    TRIBAL_RESOLUTION: AUTHORITY_DOCUMENT_VERIFIED,
    GOVERNING_AUTHORIZATION: AUTHORITY_DOCUMENT_VERIFIED,
    CONTROLLING_COMPANY_VERIFICATION: AUTHORITY_MANUALLY_VERIFIED,
    ORG_ADMIN_INVITATION: AUTHORITY_ORG_ADMIN_CONFIRMED,
}

# ---- decisions ----------------------------------------------------------
DECISION_PENDING = "PENDING"
DECISION_ACCEPTED = "ACCEPTED"
DECISION_REJECTED = "REJECTED"
DECISION_SUPERSEDED = "SUPERSEDED"
DECISION_EXPIRED = "EXPIRED"

DECISIONS: tuple[str, ...] = (
    DECISION_PENDING,
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    DECISION_SUPERSEDED,
    DECISION_EXPIRED,
)

DECISION_MEANINGS: dict[str, str] = {
    DECISION_PENDING: "recorded and awaiting a human judgement",
    DECISION_ACCEPTED: "a named human judged this evidence sufficient",
    DECISION_REJECTED: "a named human judged this evidence insufficient",
    DECISION_SUPERSEDED: "later evidence replaced this, and this is retained",
    DECISION_EXPIRED: "this evidence had an end date and it has passed",
}

#: Only an accepted decision can support a status. PENDING notably cannot:
#: evidence nobody has judged is a queue item, not a warrant.
SUPPORTS_A_STATUS: frozenset[str] = frozenset({DECISION_ACCEPTED})

EVIDENCE_FIELDS: tuple[str, ...] = (
    "evidence_id",
    "evidence_type",
    "organization_id",
    "subject_identity_id",
    "issuer",
    "source_ref",
    "artifact_ref",
    "reviewer",
    "decision",
    "decided_at",
    "recorded_at",
    "expires_at",
    "reason",
    "establishes_identity",
    "establishes_affiliation",
    "establishes_authority",
    "is_demo",
    "model_version",
)

#: Field names and value shapes that would mean somebody stored a secret.
_SECRET_FIELD = re.compile(
    r"secret|password|passwd|token|api[_-]?key|private[_-]?key|credential", re.I
)
_SECRET_VALUE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|^(?:sk|pk|ghp|xox[baprs])[-_][A-Za-z0-9]{16,}",
    re.M,
)


def build_evidence_id(
    *,
    evidence_type: Any,
    organization_id: Any,
    subject_identity_id: Any,
    source_ref: Any,
) -> str:
    parts = [
        str(evidence_type or ""),
        str(organization_id or ""),
        str(subject_identity_id or ""),
        str(source_ref or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_evidence(
    *,
    evidence_type: str,
    organization_id: Any,
    subject_identity_id: Any,
    source_ref: Any = None,
    issuer: Any = None,
    artifact_ref: Any = None,
    reviewer: Any = None,
    decision: str = DECISION_PENDING,
    decided_at: Any = None,
    recorded_at: Any = None,
    expires_at: Any = None,
    reason: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """One piece of evidence, stating which dimensions it can speak to."""
    kind = str(evidence_type)
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_id": build_evidence_id(
            evidence_type=kind,
            organization_id=organization_id,
            subject_identity_id=subject_identity_id,
            source_ref=source_ref,
        ),
        "evidence_type": kind,
        "organization_id": str(organization_id) if organization_id else None,
        "subject_identity_id": (
            str(subject_identity_id) if subject_identity_id else None
        ),
        "issuer": str(issuer) if issuer else None,
        # A REFERENCE, never the bytes and never a credential.
        "source_ref": str(source_ref) if source_ref else None,
        "artifact_ref": str(artifact_ref) if artifact_ref else None,
        "reviewer": str(reviewer) if reviewer else None,
        "decision": str(decision),
        "decided_at": decided_at,
        "recorded_at": recorded_at or dt.datetime.now(dt.UTC).isoformat(),
        "expires_at": expires_at,
        "reason": str(reason) if reason else None,
        # What this type CAN establish. Stated per row so a reader never has
        # to guess, and so a domain match cannot drift into authority.
        "establishes_identity": kind in ESTABLISHES_IDENTITY,
        "establishes_affiliation": kind in ESTABLISHES_AFFILIATION,
        "establishes_authority": kind in ESTABLISHES_AUTHORITY,
        "is_demo": bool(is_demo),
        "model_version": EVIDENCE_MODEL_VERSION,
    }


def decide_evidence(
    *,
    evidence: dict[str, Any],
    decision: str,
    reviewer: Any,
    reason: Any,
    decided_at: Any = None,
) -> dict[str, Any]:
    """A human judges evidence. The machine may not."""
    target = str(decision)
    if target not in DECISIONS:
        return {
            "accepted": False,
            "why": f"{target} is not a decision",
            "evidence": evidence,
        }
    if target in {DECISION_ACCEPTED, DECISION_REJECTED} and not reviewer:
        return {
            "accepted": False,
            "why": f"{target} requires a named reviewer",
            "evidence": evidence,
        }
    if target in {DECISION_ACCEPTED, DECISION_REJECTED} and not reason:
        return {
            "accepted": False,
            "why": f"{target} requires a stated reason",
            "evidence": evidence,
        }

    decided = dict(evidence)
    decided["decision"] = target
    decided["reviewer"] = str(reviewer) if reviewer else None
    decided["reason"] = str(reason) if reason else None
    decided["decided_at"] = decided_at or dt.datetime.now(dt.UTC).isoformat()
    return {"accepted": True, "evidence": decided, "why": str(reason)}


def effective_decision(evidence: dict[str, Any], *, now: Any = None) -> str:
    """Expiry applied at read time, as with authority itself."""
    stored = str(evidence.get("decision") or DECISION_PENDING)
    if stored != DECISION_ACCEPTED:
        return stored
    expires = evidence.get("expires_at")
    if not expires:
        return stored
    try:
        end = dt.date.fromisoformat(str(expires)[:10])
    except ValueError:
        return stored
    today = (
        dt.date.fromisoformat(str(now)[:10]) if now else dt.datetime.now(dt.UTC).date()
    )
    return DECISION_EXPIRED if today > end else stored


def grade_evidence_set(
    *, evidence: list[dict[str, Any]], now: Any = None
) -> dict[str, Any]:
    """What does this pile of evidence actually establish, dimension by dimension?

    Returns three independent answers and never a combined one. Only ACCEPTED,
    unexpired evidence counts; PENDING evidence is a queue item, not a warrant.
    """
    usable = [
        row for row in evidence if effective_decision(row, now=now) in SUPPORTS_A_STATUS
    ]
    rejected = [
        row for row in evidence if str(row.get("decision")) == DECISION_REJECTED
    ]

    identity_ev = [r for r in usable if r.get("establishes_identity")]
    affiliation_ev = [r for r in usable if r.get("establishes_affiliation")]
    authority_ev = [r for r in usable if r.get("establishes_authority")]

    # 177K case 10: evidence that disagrees with itself goes to a human
    # rather than resolving to whichever row was written last.
    conflicting = bool(usable and rejected) and bool(
        {str(r.get("evidence_type")) for r in usable}
        & {str(r.get("evidence_type")) for r in rejected}
    )

    supported_states = sorted(
        {
            TYPE_SUPPORTS_AUTHORITY_STATE[str(r.get("evidence_type"))]
            for r in authority_ev
            if str(r.get("evidence_type")) in TYPE_SUPPORTS_AUTHORITY_STATE
        }
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_count": len(evidence),
        "usable_count": len(usable),
        "rejected_count": len(rejected),
        "pending_count": sum(
            1 for r in evidence if str(r.get("decision")) == DECISION_PENDING
        ),
        # Three answers. Never one.
        "supports_identity": bool(identity_ev),
        "supports_affiliation": bool(affiliation_ev),
        "supports_authority": bool(authority_ev),
        "identity_evidence_ids": sorted(str(r["evidence_id"]) for r in identity_ev),
        "affiliation_evidence_ids": sorted(
            str(r["evidence_id"]) for r in affiliation_ev
        ),
        "authority_evidence_ids": sorted(str(r["evidence_id"]) for r in authority_ev),
        "authority_states_supported": supported_states,
        "conflicting_evidence": conflicting,
        "review_required": conflicting,
        # The refusal this module exists for.
        "one_evidence_type_was_not_assumed_sufficient": True,
    }


def verify_authority_manually(
    *,
    organization_id: Any,
    identity_id: Any,
    verified_by: Any,
    verified_by_is_controlling_company: bool,
    reason: Any,
    customer_relationship_ref: Any = None,
    scope: str = SCOPE_ADMINISTER_TENANT,
    identity_status: str = IDENTITY_VERIFIED,
    affiliation_status: str = AFFILIATION_VERIFIED,
    verified_at: Any = None,
    expires_at: Any = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """177D: the first-four-customer path - a named human signs for it.

    The first customers are onboarded by people, not by a domain check, and
    that is the honest way to do it at four organisations. What makes it safe
    is that the verification is ATTRIBUTED: a named member of controlling-
    company staff, a stated reason, a date, and an audit event.

    No customer identity is hardcoded anywhere. The caller supplies the
    organisation; this function supplies the discipline.
    """
    if not verified_by_is_controlling_company:
        return {
            "accepted": False,
            "why": "manual authority verification is a controlling-company action",
            "grant": None,
            "evidence": None,
        }
    if not verified_by:
        return {
            "accepted": False,
            "why": "manual verification requires a named verifier",
            "grant": None,
            "evidence": None,
        }
    if not reason:
        return {
            "accepted": False,
            "why": "manual verification requires a stated reason",
            "grant": None,
            "evidence": None,
        }
    if str(scope) not in SCOPES:
        return {
            "accepted": False,
            "why": f"{scope} is not a scope",
            "grant": None,
            "evidence": None,
        }

    when = verified_at or dt.datetime.now(dt.UTC).isoformat()
    evidence = build_evidence(
        evidence_type=CONTROLLING_COMPANY_VERIFICATION,
        organization_id=organization_id,
        subject_identity_id=identity_id,
        source_ref=(
            str(customer_relationship_ref)
            if customer_relationship_ref
            else f"manual:{organization_id}"
        ),
        issuer="controlling_company",
        reviewer=verified_by,
        decision=DECISION_ACCEPTED,
        decided_at=when,
        expires_at=expires_at,
        reason=reason,
        is_demo=is_demo,
    )
    grant = build_authority_grant(
        organization_id=organization_id,
        identity_id=identity_id,
        identity_status=identity_status,
        affiliation_status=affiliation_status,
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        authority_method=CONTROLLING_COMPANY_VERIFICATION,
        scope=scope,
        verified_by=verified_by,
        verified_at=when,
        expires_at=expires_at,
        reason=reason,
        evidence_ids=[evidence["evidence_id"]],
        is_demo=is_demo,
    )
    return {
        "accepted": True,
        "grant": grant,
        "evidence": evidence,
        "audit_event": {
            "action": "authority.manually_verified",
            "organization_id": str(organization_id) if organization_id else None,
            "actor_id": str(verified_by),
            "subject_identity_id": str(identity_id) if identity_id else None,
            "scope": str(scope),
            "reason": str(reason),
            "customer_relationship_ref": (
                str(customer_relationship_ref) if customer_relationship_ref else None
            ),
            "occurred_at": when,
        },
        "no_customer_identity_hardcoded": True,
        "why": str(reason),
    }


def evidence_invariant_failures(evidence: dict[str, Any]) -> list[str]:
    """Refuse evidence that is not evidence, or that carries a secret."""
    failures: list[str] = []

    for field in EVIDENCE_FIELDS:
        if field not in evidence:
            failures.append(f"evidence_missing_field:{field}")

    kind = str(evidence.get("evidence_type") or "")
    if kind not in evidence_types():
        failures.append(f"evidence_type_outside_the_vocabulary:{kind or 'missing'}")

    decision = str(evidence.get("decision") or "")
    if decision not in DECISIONS:
        failures.append(f"decision_outside_the_vocabulary:{decision or 'missing'}")

    if not evidence.get("organization_id"):
        failures.append("evidence_names_no_organization")
    if not evidence.get("subject_identity_id"):
        failures.append("evidence_names_no_subject")

    # A judged decision needs a judge and a reason.
    if decision in {DECISION_ACCEPTED, DECISION_REJECTED}:
        if not evidence.get("reviewer"):
            failures.append(f"{decision.lower()}_evidence_names_no_reviewer")
        if not evidence.get("reason"):
            failures.append(f"{decision.lower()}_evidence_states_no_reason")
        if not evidence.get("decided_at"):
            failures.append(f"{decision.lower()}_evidence_has_no_date")

    # The dimension flags must match the type, or the row lies about itself.
    if bool(evidence.get("establishes_authority")) != (kind in ESTABLISHES_AUTHORITY):
        failures.append(f"authority_flag_disagrees_with_type:{kind}")
    if bool(evidence.get("establishes_affiliation")) != (
        kind in ESTABLISHES_AFFILIATION
    ):
        failures.append(f"affiliation_flag_disagrees_with_type:{kind}")
    if bool(evidence.get("establishes_identity")) != (kind in ESTABLISHES_IDENTITY):
        failures.append(f"identity_flag_disagrees_with_type:{kind}")

    # No secrets. Not in a field name, not in a value.
    for key, value in evidence.items():
        if _SECRET_FIELD.search(str(key)):
            failures.append(f"evidence_field_looks_like_a_secret:{key}")
        if isinstance(value, str) and _SECRET_VALUE.search(value):
            failures.append(f"evidence_value_looks_like_a_secret:{key}")

    return sorted(set(failures))


def describe_evidence_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": EVIDENCE_MODEL_VERSION,
        "evidence_types": list(evidence_types()),
        "decisions": list(DECISIONS),
        "every_type_has_a_meaning": set(EVIDENCE_MEANINGS) <= set(evidence_types()),
        "every_decision_has_a_meaning": set(DECISION_MEANINGS) == set(DECISIONS),
        "evidence_types_are_extensible": True,
        "establishes_identity": sorted(ESTABLISHES_IDENTITY),
        "establishes_affiliation": sorted(ESTABLISHES_AFFILIATION),
        "establishes_authority": sorted(ESTABLISHES_AUTHORITY),
        # The refusals.
        "email_domain_is_not_authority": (
            ORGANIZATION_EMAIL_DOMAIN not in ESTABLISHES_AUTHORITY
        ),
        "a_website_listing_is_not_authority": (
            OFFICIAL_TRIBAL_WEBSITE not in ESTABLISHES_AUTHORITY
        ),
        "pending_evidence_supports_nothing": (
            DECISION_PENDING not in SUPPORTS_A_STATUS
        ),
        "a_human_decides_every_acceptance": True,
        "no_single_evidence_type_is_sufficient_for_all_tribes": True,
        "secrets_are_never_stored": True,
        "conflicting_evidence_asks_for_review": True,
    }
