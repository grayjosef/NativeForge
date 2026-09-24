"""177L: the detectors that catch this gate lying, and the proof they fire.

Nine named detectors, each looking for one specific way the authority layer
could hold something that looks like a decision and is not. A generic
"invalid" verdict is worthless: a fixture broken in nine ways that produces
the same word nine times has taught nobody anything.

`prove_detectors_fire()` builds a population broken in EXACTLY one way per
detector and proves three things about each:

  1. it fires on its own breakage
  2. it stays silent on a healthy population
  3. nothing else fires

Point 3 is the one that matters. In Gate 176 a fixture broke two things at
once and proved neither; the specificity check is what caught it.
"""

from __future__ import annotations

from typing import Any

from nativeforge.services.tenant_administration_service import (
    ASSIGNABLE_BY,
    CONTROLLING_COMPANY_ROLES,
    CUSTOMER_ROLES,
    INVITE_PENDING,
    ORG_ADMIN,
    ORG_MEMBER,
    ORG_SUPER_ADMIN,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_VERIFIED,
    AUTHORITY_REVOKED,
    AUTHORITY_SUFFICIENT,
    IDENTITY_VERIFIED,
    build_authority_grant,
    may_administer_tenant,
)

SCHEMA_VERSION = "nf_tribal_authority_self_health_v1"

HEALTH_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# The nine detectors. Each name is a specific accusation.
# ---------------------------------------------------------------------------

AUTHORITY_VERIFIED_WITHOUT_EVIDENCE = "authority_verified_without_evidence"
ORG_WITHOUT_TENANT_IDENTITY = "org_without_tenant_identity"
CROSS_TENANT_MEMBERSHIP = "cross_tenant_membership"
CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN = "controlling_role_assigned_by_org_admin"
REVOKED_AUTHORITY_STILL_ADMINISTERS = "revoked_authority_still_administers"
INVITATION_WITHOUT_INVITER_AUTHORITY = "invitation_without_inviter_authority"
ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE = "org_default_mutated_by_personal_override"
AUDIT_GAP = "audit_gap"
ORPHAN_AUTHORITY_EVIDENCE = "orphan_authority_evidence"

DETECTORS: tuple[str, ...] = (
    AUTHORITY_VERIFIED_WITHOUT_EVIDENCE,
    ORG_WITHOUT_TENANT_IDENTITY,
    CROSS_TENANT_MEMBERSHIP,
    CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN,
    REVOKED_AUTHORITY_STILL_ADMINISTERS,
    INVITATION_WITHOUT_INVITER_AUTHORITY,
    ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE,
    AUDIT_GAP,
    ORPHAN_AUTHORITY_EVIDENCE,
)

DETECTOR_MEANINGS: dict[str, str] = {
    AUTHORITY_VERIFIED_WITHOUT_EVIDENCE: (
        "a grant claims sufficient authority while naming no verifier, no "
        "reason, and no accepted evidence"
    ),
    ORG_WITHOUT_TENANT_IDENTITY: (
        "an organisation exists with no tenant identity, so its records "
        "cannot be kept apart from anybody else's"
    ),
    CROSS_TENANT_MEMBERSHIP: (
        "a membership names one organisation while its grant names another"
    ),
    CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN: (
        "a customer role conferred controlling-company powers"
    ),
    REVOKED_AUTHORITY_STILL_ADMINISTERS: (
        "a revoked or expired grant still answers yes to may_administer_tenant"
    ),
    INVITATION_WITHOUT_INVITER_AUTHORITY: (
        "a pending invitation whose issuer could not have issued it"
    ),
    ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE: (
        "one person's preferences changed what everybody sees"
    ),
    AUDIT_GAP: (
        "an authority decision or membership change with no audit event "
        "recording who did it"
    ),
    ORPHAN_AUTHORITY_EVIDENCE: (
        "evidence referencing a grant, organisation or subject that is not there"
    ),
}

CRITICAL = "CRITICAL"
SERIOUS = "SERIOUS"

DETECTOR_SEVERITY: dict[str, str] = {
    AUTHORITY_VERIFIED_WITHOUT_EVIDENCE: CRITICAL,
    ORG_WITHOUT_TENANT_IDENTITY: CRITICAL,
    CROSS_TENANT_MEMBERSHIP: CRITICAL,
    CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN: CRITICAL,
    REVOKED_AUTHORITY_STILL_ADMINISTERS: CRITICAL,
    INVITATION_WITHOUT_INVITER_AUTHORITY: SERIOUS,
    ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE: SERIOUS,
    AUDIT_GAP: SERIOUS,
    ORPHAN_AUTHORITY_EVIDENCE: SERIOUS,
}

#: Actions whose occurrence must be matched by an audit event.
AUDITED_ACTIONS: frozenset[str] = frozenset(
    {
        "authority.manually_verified",
        "authority.revoked",
        "organization.invitation_issued",
        "organization.invitation_revoked",
        "organization.defaults_published",
        "organization.member_removed",
        "organization.role_changed",
    }
)


def _finding(detector: str, subject: Any, why: str) -> dict[str, Any]:
    return {
        "detector": detector,
        "severity": DETECTOR_SEVERITY[detector],
        "subject": str(subject) if subject is not None else None,
        "why": why,
    }


def assess_authority_health(
    *,
    grants: list[dict[str, Any]] | None = None,
    organizations: list[dict[str, Any]] | None = None,
    memberships: list[dict[str, Any]] | None = None,
    invitations: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    revocations: list[dict[str, Any]] | None = None,
    audit_events: list[dict[str, Any]] | None = None,
    expected_audited_actions: list[dict[str, Any]] | None = None,
    org_default_before: Any = None,
    org_default_after: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Run every detector over a population and report what each one found."""
    grants = grants or []
    organizations = organizations or []
    memberships = memberships or []
    invitations = invitations or []
    evidence = evidence or []
    revocations = revocations or []
    audit_events = audit_events or []
    expected_audited_actions = expected_audited_actions or []

    findings: list[dict[str, Any]] = []
    known_orgs = {str(o.get("organization_id")) for o in organizations}
    known_identities = {
        str(m.get("identity_id")) for m in memberships if m.get("identity_id")
    }
    known_grant_ids = {str(g.get("authority_id")) for g in grants}
    # The authoritative record of who had authority taken away. The grant row
    # is a cache of this; when the two disagree, the log wins and somebody
    # needs to know.
    revoked_ids = {
        str(r.get("authority_id")) for r in revocations if r.get("revoked_at")
    }

    for grant in grants:
        gid = grant.get("authority_id")
        status = str(grant.get("authority_status") or "")

        if status in AUTHORITY_SUFFICIENT:
            accepted = [
                e
                for e in evidence
                if str(e.get("evidence_id")) in set(grant.get("evidence_ids") or [])
                and str(e.get("decision")) == "ACCEPTED"
            ]
            if not grant.get("verified_by") or not grant.get("reason"):
                findings.append(
                    _finding(
                        AUTHORITY_VERIFIED_WITHOUT_EVIDENCE,
                        gid,
                        f"{status} with no verifier or no stated reason",
                    )
                )
            elif not accepted and not grant.get("evidence_ids"):
                findings.append(
                    _finding(
                        AUTHORITY_VERIFIED_WITHOUT_EVIDENCE,
                        gid,
                        f"{status} referencing no accepted evidence",
                    )
                )

        # Two INDEPENDENT sources, compared. Asking may_administer_tenant
        # and then re-reading the fields it already applies would be asking
        # the same question twice and calling the agreement a proof.
        verdict = may_administer_tenant(grant, now=now)
        if verdict["permitted"] and str(gid) in revoked_ids:
            findings.append(
                _finding(
                    REVOKED_AUTHORITY_STILL_ADMINISTERS,
                    gid,
                    "the revocation log says revoked and the grant still "
                    "permits administration",
                )
            )
        elif verdict["permitted"] and status == AUTHORITY_REVOKED:
            findings.append(
                _finding(
                    REVOKED_AUTHORITY_STILL_ADMINISTERS,
                    gid,
                    "a grant marked REVOKED still permits administration",
                )
            )

    for org in organizations:
        if not org.get("tenant_id"):
            findings.append(
                _finding(
                    ORG_WITHOUT_TENANT_IDENTITY,
                    org.get("organization_id"),
                    "the organisation has no tenant identity",
                )
            )

    for membership in memberships:
        member_org = str(membership.get("organization_id") or "")
        identity = str(membership.get("identity_id") or "")
        for grant in grants:
            if str(grant.get("identity_id") or "") != identity:
                continue
            grant_org = str(grant.get("organization_id") or "")
            if grant_org and member_org and grant_org != member_org:
                findings.append(
                    _finding(
                        CROSS_TENANT_MEMBERSHIP,
                        identity,
                        f"membership in {member_org} with a grant in {grant_org}",
                    )
                )

        conferred = str(membership.get("role") or "")
        conferred_by = str(membership.get("role_conferred_by_role") or "")
        if conferred in CONTROLLING_COMPANY_ROLES and conferred_by in CUSTOMER_ROLES:
            findings.append(
                _finding(
                    CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN,
                    identity,
                    f"{conferred_by} conferred {conferred}",
                )
            )
        elif (
            conferred in ASSIGNABLE_BY
            and conferred_by
            and conferred_by not in ASSIGNABLE_BY[conferred]
        ):
            findings.append(
                _finding(
                    CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN,
                    identity,
                    f"{conferred_by} may not confer {conferred}",
                )
            )

    for invitation in invitations:
        if str(invitation.get("invite_state")) != INVITE_PENDING:
            continue
        inviter_role = str(invitation.get("invited_by_role") or "")
        offered = str(invitation.get("offered_role") or "")
        if offered in ASSIGNABLE_BY and inviter_role not in ASSIGNABLE_BY[offered]:
            findings.append(
                _finding(
                    INVITATION_WITHOUT_INVITER_AUTHORITY,
                    invitation.get("invitation_id"),
                    f"{inviter_role} could not have offered {offered}",
                )
            )

    if org_default_before is not None and org_default_after is not None:
        if org_default_before != org_default_after:
            findings.append(
                _finding(
                    ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE,
                    None,
                    "the organisation default changed while applying a "
                    "personal override",
                )
            )

    recorded = {str(e.get("action")) for e in audit_events}
    for expected in expected_audited_actions:
        action = str(expected.get("action") or "")
        if action in AUDITED_ACTIONS and action not in recorded:
            findings.append(
                _finding(AUDIT_GAP, action, f"{action} happened with no audit event")
            )
    for event in audit_events:
        if not event.get("actor_id"):
            findings.append(
                _finding(
                    AUDIT_GAP,
                    event.get("action"),
                    "an audit event names no actor",
                )
            )

    for row in evidence:
        org = str(row.get("organization_id") or "")
        subject = str(row.get("subject_identity_id") or "")
        if known_orgs and org and org not in known_orgs:
            findings.append(
                _finding(
                    ORPHAN_AUTHORITY_EVIDENCE,
                    row.get("evidence_id"),
                    f"evidence for organisation {org}, which is not here",
                )
            )
        elif known_identities and subject and subject not in known_identities:
            findings.append(
                _finding(
                    ORPHAN_AUTHORITY_EVIDENCE,
                    row.get("evidence_id"),
                    f"evidence about {subject}, who is not a member here",
                )
            )
        elif row.get("grant_ref") and str(row["grant_ref"]) not in known_grant_ids:
            findings.append(
                _finding(
                    ORPHAN_AUTHORITY_EVIDENCE,
                    row.get("evidence_id"),
                    "evidence references a grant that is not here",
                )
            )

    fired = sorted({f["detector"] for f in findings})
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "healthy": not findings,
        "finding_count": len(findings),
        "detectors_fired": fired,
        "detectors_silent": [d for d in DETECTORS if d not in fired],
        "critical_finding_count": sum(1 for f in findings if f["severity"] == CRITICAL),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# The proof.
# ---------------------------------------------------------------------------

_NOW = "2026-09-24"


def _healthy_population() -> dict[str, Any]:
    grant = build_authority_grant(
        organization_id="org-A",
        identity_id="person-1",
        identity_status=IDENTITY_VERIFIED,
        affiliation_status=AFFILIATION_VERIFIED,
        authority_status="MANUALLY_VERIFIED",
        verified_by="controlling-company:staff-1",
        verified_at="2026-09-01",
        reason="council resolution reviewed",
        evidence_ids=["evidence-1"],
    )
    return {
        "grants": [grant],
        "organizations": [{"organization_id": "org-A", "tenant_id": "tenant-A"}],
        "memberships": [
            {
                "organization_id": "org-A",
                "identity_id": "person-1",
                "role": ORG_SUPER_ADMIN,
                "role_conferred_by_role": "CONTROLLING_COMPANY_ADMIN",
            }
        ],
        "invitations": [
            {
                "invitation_id": "invite-1",
                "organization_id": "org-A",
                "invited_by_role": ORG_ADMIN,
                "offered_role": ORG_MEMBER,
                "invite_state": INVITE_PENDING,
            }
        ],
        "evidence": [
            {
                "evidence_id": "evidence-1",
                "organization_id": "org-A",
                "subject_identity_id": "person-1",
                "decision": "ACCEPTED",
            }
        ],
        "revocations": [],
        "audit_events": [
            {"action": "authority.manually_verified", "actor_id": "staff-1"}
        ],
        "expected_audited_actions": [{"action": "authority.manually_verified"}],
        "org_default_before": {"tile_order": ["DEADLINES"]},
        "org_default_after": {"tile_order": ["DEADLINES"]},
        "now": _NOW,
    }


def _break_one_way(detector: str) -> dict[str, Any]:
    """Return the healthy population, damaged in EXACTLY one way."""
    pop = _healthy_population()

    if detector == AUTHORITY_VERIFIED_WITHOUT_EVIDENCE:
        grant = dict(pop["grants"][0])
        grant["verified_by"] = None
        pop["grants"] = [grant]

    elif detector == ORG_WITHOUT_TENANT_IDENTITY:
        pop["organizations"] = [{"organization_id": "org-A", "tenant_id": None}]

    elif detector == CROSS_TENANT_MEMBERSHIP:
        membership = dict(pop["memberships"][0])
        membership["organization_id"] = "org-B"
        pop["memberships"] = [membership]
        # The evidence subject must stay findable, or the orphan detector
        # would fire too and the fixture would prove two things badly.
        pop["evidence"] = [
            {**pop["evidence"][0], "organization_id": "org-A"},
        ]
        pop["organizations"] = [
            {"organization_id": "org-A", "tenant_id": "tenant-A"},
            {"organization_id": "org-B", "tenant_id": "tenant-B"},
        ]

    elif detector == CONTROLLING_ROLE_ASSIGNED_BY_ORG_ADMIN:
        membership = dict(pop["memberships"][0])
        membership["role"] = "CONTROLLING_COMPANY_ADMIN"
        membership["role_conferred_by_role"] = ORG_SUPER_ADMIN
        pop["memberships"] = [membership]

    elif detector == REVOKED_AUTHORITY_STILL_ADMINISTERS:
        # The partial write: the revocation log records the decision and the
        # grant row was never updated. This is what a crash between two
        # statements leaves behind, and it is the only shape in which a
        # removed administrator keeps administering.
        pop["revocations"] = [
            {
                "authority_id": pop["grants"][0]["authority_id"],
                "revoked_at": "2026-09-10",
                "revoked_by": "staff-1",
                "reason": "left the organisation",
            }
        ]

    elif detector == INVITATION_WITHOUT_INVITER_AUTHORITY:
        invitation = dict(pop["invitations"][0])
        invitation["invited_by_role"] = ORG_MEMBER
        pop["invitations"] = [invitation]

    elif detector == ORG_DEFAULT_MUTATED_BY_PERSONAL_OVERRIDE:
        pop["org_default_after"] = {"tile_order": ["EARLY_SIGNALS"]}

    elif detector == AUDIT_GAP:
        pop["audit_events"] = []

    elif detector == ORPHAN_AUTHORITY_EVIDENCE:
        pop["evidence"] = [
            {
                "evidence_id": "evidence-9",
                "organization_id": "org-ZZZ",
                "subject_identity_id": "person-1",
                "decision": "ACCEPTED",
            }
        ]
        # The grant must not then read as evidence-less, or two detectors
        # fire and the fixture proves neither.
        grant = dict(pop["grants"][0])
        grant["evidence_ids"] = ["evidence-9"]
        pop["grants"] = [grant]

    else:  # pragma: no cover - a detector with no fixture is a bug
        raise ValueError(f"no broken fixture for detector {detector}")

    return pop


def prove_detectors_fire() -> dict[str, Any]:
    """Prove each detector fires on its OWN breakage and nothing else's."""
    baseline = assess_authority_health(**_healthy_population())

    proofs: list[dict[str, Any]] = []
    for detector in DETECTORS:
        result = assess_authority_health(**_break_one_way(detector))
        fired = result["detectors_fired"]
        proofs.append(
            {
                "detector": detector,
                "severity": DETECTOR_SEVERITY[detector],
                "fires_on_its_own_breakage": detector in fired,
                "no_other_detector_fired": fired == [detector],
                "detectors_fired": fired,
                "why": next(
                    (f["why"] for f in result["findings"] if f["detector"] == detector),
                    None,
                ),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detector_count": len(DETECTORS),
        "healthy_population_is_silent": baseline["healthy"],
        "baseline_findings": baseline["findings"],
        "all_detectors_fire": all(p["fires_on_its_own_breakage"] for p in proofs),
        "all_detectors_are_specific": all(p["no_other_detector_fired"] for p in proofs),
        "detectors_that_did_not_fire": [
            p["detector"] for p in proofs if not p["fires_on_its_own_breakage"]
        ],
        "detectors_that_fired_too_broadly": [
            p["detector"] for p in proofs if not p["no_other_detector_fired"]
        ],
        "proofs": proofs,
    }


def describe_self_health() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": HEALTH_MODEL_VERSION,
        "detectors": list(DETECTORS),
        "detector_count": len(DETECTORS),
        "audited_actions": sorted(AUDITED_ACTIONS),
        "every_detector_has_a_meaning": set(DETECTOR_MEANINGS) == set(DETECTORS),
        "every_detector_has_a_severity": set(DETECTOR_SEVERITY) == set(DETECTORS),
        "every_detector_has_a_broken_fixture": True,
        "generic_invalid_is_not_a_result": True,
    }
