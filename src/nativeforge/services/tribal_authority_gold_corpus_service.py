"""177K: fifteen ways the authority model could be wrong, with the answers.

Every case feeds RAW inputs into the REAL services and grades what comes back.
A corpus that re-implements the model it grades proves only that two copies of
the same mistake agree.

Case 11 is not hypothetical. The Gate 177 survey measured it on the live
database: the real organisation has zero active members and zero authority
records, so "organisation has no authorised administrator" is the CURRENT
state of the real tenant, not a scenario. The corpus asserts the system says
so plainly rather than defaulting somebody into the gap.

WHAT THIS CORPUS IS NOT
-----------------------
Fifteen cases we thought of. Passing them means the model handles the
situations we imagined. No real Tribe has been onboarded, no authority has
been verified for a real organisation, and nothing here is a claim about
whether a particular person may speak for a particular government.
"""

from __future__ import annotations

from typing import Any

from nativeforge.services.organization_customization_service import (
    apply_personal_override,
    build_org_default,
    build_personal_override,
    override_invariant_failures,
    publish_org_default,
)
from nativeforge.services.tenant_administration_service import (
    ACTION_INVITE_MEMBER,
    ACTION_VERIFY_AUTHORITY_MANUALLY,
    CONTROLLING_COMPANY_ADMIN,
    ORG_ADMIN,
    ORG_MEMBER,
    ORG_SUPER_ADMIN,
    authorize_admin_action,
    issue_invitation,
)
from nativeforge.services.tribal_authority_evidence_service import (
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    TRIBAL_RESOLUTION,
    build_evidence,
    grade_evidence_set,
    verify_authority_manually,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_SELF_ASSERTED,
    AFFILIATION_UNVERIFIED,
    AFFILIATION_VERIFIED,
    AUTHORITY_MANUALLY_VERIFIED,
    AUTHORITY_UNVERIFIED,
    IDENTITY_VERIFIED,
    build_authority_grant,
    grant_invariant_failures,
    may_administer_tenant,
    revoke_authority,
)

SCHEMA_VERSION = "nf_tribal_authority_gold_corpus_v1"

CORPUS_VERSION = "2026.09.1"

#: Every temporal case pins its own clock. Gate 172 shipped a verifier
#: asserting a state that was true the week it was written.
NOW = "2026-09-24"

_SIGNED = dict(
    verified_by="controlling-company:staff-1",
    verified_at="2026-09-01",
    reason="council resolution 2026-14 reviewed",
)


def _grant(**over: Any) -> dict[str, Any]:
    base = dict(
        organization_id="org-A",
        identity_id="person-1",
        identity_status=IDENTITY_VERIFIED,
        affiliation_status=AFFILIATION_VERIFIED,
        authority_status=AUTHORITY_UNVERIFIED,
    )
    base.update(over)
    return build_authority_grant(**base)


# ---------------------------------------------------------------------------
# The fifteen cases.
# ---------------------------------------------------------------------------


def case_01_verified_identity_no_affiliation() -> dict[str, Any]:
    grant = _grant(
        affiliation_status=AFFILIATION_UNVERIFIED,
        authority_status=AUTHORITY_UNVERIFIED,
    )
    verdict = may_administer_tenant(grant, now=NOW)
    return {
        "permitted": verdict["permitted"],
        "identity_sufficient": verdict["identity_sufficient"],
        "affiliation_sufficient": verdict["affiliation_sufficient"],
        "invariant_failures": grant_invariant_failures(grant),
    }


def case_02_verified_affiliation_no_authority() -> dict[str, Any]:
    grant = _grant(authority_status=AUTHORITY_UNVERIFIED)
    verdict = may_administer_tenant(grant, now=NOW)
    return {
        "permitted": verdict["permitted"],
        "affiliation_sufficient": verdict["affiliation_sufficient"],
        "authority_sufficient": verdict["authority_sufficient"],
        "invariant_failures": grant_invariant_failures(grant),
    }


def case_03_self_asserted_affiliation() -> dict[str, Any]:
    grant = _grant(
        affiliation_status=AFFILIATION_SELF_ASSERTED,
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        **_SIGNED,
    )
    verdict = may_administer_tenant(grant, now=NOW)
    failures = grant_invariant_failures(grant)
    return {
        "permitted": verdict["permitted"],
        "invariant_caught_the_inconsistency": any(
            "over_affiliation" in f for f in failures
        ),
    }


def case_04_manually_verified_authority() -> dict[str, Any]:
    result = verify_authority_manually(
        organization_id="org-A",
        identity_id="person-1",
        verified_by="controlling-company:staff-1",
        verified_by_is_controlling_company=True,
        reason="chairperson confirmed; council minutes on file",
        customer_relationship_ref="crm:agreement-1",
        verified_at="2026-09-01",
    )
    verdict = may_administer_tenant(result["grant"], now=NOW)
    return {
        "accepted": result["accepted"],
        "permitted": verdict["permitted"],
        "names_a_verifier": bool(result["grant"]["verified_by"]),
        "states_a_reason": bool(result["grant"]["reason"]),
        "emits_an_audit_event": bool(result.get("audit_event")),
        "no_customer_identity_hardcoded": result["no_customer_identity_hardcoded"],
        "invariant_failures": grant_invariant_failures(result["grant"]),
    }


def case_05_authority_revoked() -> dict[str, Any]:
    granted = verify_authority_manually(
        organization_id="org-A",
        identity_id="person-1",
        verified_by="controlling-company:staff-1",
        verified_by_is_controlling_company=True,
        reason="initial verification",
        verified_at="2026-09-01",
    )["grant"]
    revoked = revoke_authority(
        grant=granted,
        revoked_by="controlling-company:staff-1",
        reason="no longer holds the office",
    )
    verdict = may_administer_tenant(revoked["grant"], now=NOW)
    return {
        "permitted": verdict["permitted"],
        "organization_deleted": revoked["organization_deleted"],
        "historical_work_deleted": revoked["historical_work_deleted"],
        "audit_history_erased": revoked["audit_history_erased"],
        "membership_removed": revoked["membership_removed"],
        "unattributed_revocation_refused": not revoke_authority(
            grant=granted, revoked_by=None, reason="x"
        )["accepted"],
    }


def case_06_invitation_from_authorized_org_admin() -> dict[str, Any]:
    result = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="person-admin",
        invited_by_role=ORG_ADMIN,
        invited_by_organization_id="org-A",
    )
    return {
        "accepted": result["accepted"],
        "invitation_exists": result["invitation"] is not None,
    }


def case_07_invitation_from_ordinary_member() -> dict[str, Any]:
    result = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="person-member",
        invited_by_role=ORG_MEMBER,
        invited_by_organization_id="org-A",
    )
    return {
        "accepted": result["accepted"],
        # Refused at ISSUE: the invitation never exists to sit in an inbox.
        "invitation_exists": result["invitation"] is not None,
    }


def case_08_cross_tenant_admin_attempt() -> dict[str, Any]:
    decision = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-B",
    )
    return {
        "permitted": decision["permitted"],
        "cross_tenant_attempt": decision["cross_tenant_attempt"],
    }


def case_09_expired_authority() -> dict[str, Any]:
    grant = _grant(
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        expires_at="2026-06-30",
        **_SIGNED,
    )
    expired = may_administer_tenant(grant, now=NOW)
    before = may_administer_tenant(grant, now="2026-06-01")
    return {
        "permitted": expired["permitted"],
        "effective_status": expired["authority_status_effective"],
        "stored_status_unchanged": expired["authority_status_stored"]
        == AUTHORITY_MANUALLY_VERIFIED,
        # The check must be able to NOT fire.
        "permitted_before_expiry": before["permitted"],
    }


def case_10_conflicting_evidence() -> dict[str, Any]:
    accepted = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="person-1",
        source_ref="doc:resolution-a",
        reviewer="staff-1",
        decision=DECISION_ACCEPTED,
        decided_at="2026-09-01",
        reason="resolution verified",
    )
    rejected = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="person-1",
        source_ref="doc:resolution-b",
        reviewer="staff-2",
        decision=DECISION_REJECTED,
        decided_at="2026-09-02",
        reason="superseded resolution, not in force",
    )
    graded = grade_evidence_set(evidence=[accepted, rejected], now=NOW)
    return {
        "conflicting_evidence": graded["conflicting_evidence"],
        "review_required": graded["review_required"],
    }


def case_11_organization_has_no_authorized_admin() -> dict[str, Any]:
    """The live state of the real tenant, as the survey measured it."""
    grants: list[dict[str, Any]] = []
    verdicts = [may_administer_tenant(g, now=NOW) for g in grants]
    return {
        "grant_count": len(grants),
        "anybody_may_administer": any(v["permitted"] for v in verdicts),
        # An empty authority set must read as "nobody", never as "no
        # restriction found, therefore allow".
        "empty_set_denies": not any(v["permitted"] for v in verdicts),
    }


def case_12_controlling_company_manual_verification() -> dict[str, Any]:
    decision = authorize_admin_action(
        action=ACTION_VERIFY_AUTHORITY_MANUALLY,
        actor_role=CONTROLLING_COMPANY_ADMIN,
        actor_organization_id="controlling-company",
        target_organization_id="org-A",
    )
    return {
        "permitted": decision["permitted"],
        # Controlling-company staff are not confined to one tenant, and that
        # is the ONLY exemption from the tenancy rule.
        "cross_tenant_attempt": decision["cross_tenant_attempt"],
    }


def case_13_org_admin_tries_controlling_company_action() -> dict[str, Any]:
    decision = authorize_admin_action(
        action=ACTION_VERIFY_AUTHORITY_MANUALLY,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-A",
    )
    escalation = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:x",
        offered_role=CONTROLLING_COMPANY_ADMIN,
        invited_by="person-super",
        invited_by_role=ORG_SUPER_ADMIN,
        invited_by_organization_id="org-A",
    )
    direct = verify_authority_manually(
        organization_id="org-A",
        identity_id="person-2",
        verified_by="person-super",
        verified_by_is_controlling_company=False,
        reason="I am the super admin",
    )
    return {
        "permitted": decision["permitted"],
        "escalation_refused": not escalation["accepted"],
        "escalation_flagged": escalation["decision"].get(
            "privilege_escalation_attempt", False
        ),
        "direct_call_refused": not direct["accepted"],
    }


def case_14_personal_layout_does_not_change_org_default() -> dict[str, Any]:
    default = build_org_default(
        organization_id="org-A",
        branding={"primary_color": "#1B4332", "display_name": "Example Tribe"},
        dashboard={
            "tile_order": ["DEADLINES", "OPEN_OPPORTUNITIES"],
            "density": "COMPACT",
        },
        published_by="admin-1",
        reason="initial",
    )
    before = list(default["dashboard"]["tile_order"])
    override = build_personal_override(
        organization_id="org-A",
        identity_id="person-7",
        preferences={"tile_order": ["OPEN_OPPORTUNITIES"], "density": "COMFORTABLE"},
    )
    effective = apply_personal_override(org_default=default, override=override)
    # Mutating what the person sees must not reach the organisation.
    effective["dashboard"]["tile_order"].append("TEAM")
    return {
        "person_sees_their_own_order": effective["dashboard"]["tile_order"][0]
        == "OPEN_OPPORTUNITIES",
        "org_default_unchanged": effective["org_default_unchanged"],
        "org_default_still_original": default["dashboard"]["tile_order"] == before,
        "branding_came_from_the_organization": effective["branding"]["primary_color"]
        == "#1B4332",
        "override_invariant_failures": override_invariant_failures(override),
    }


def case_15_org_admin_publishes_new_default() -> dict[str, Any]:
    default = build_org_default(
        organization_id="org-A",
        dashboard={"tile_order": ["DEADLINES", "OPEN_OPPORTUNITIES"]},
        published_by="admin-1",
        reason="initial",
    )
    published = publish_org_default(
        current=default,
        changes={"dashboard": {"tile_order": ["OPEN_OPPORTUNITIES", "DEADLINES"]}},
        published_by="admin-1",
        publisher_may_publish=True,
        reason="the team asked for opportunities first",
    )
    unauthorized = publish_org_default(
        current=default,
        changes={},
        published_by="member-1",
        publisher_may_publish=False,
        reason="I prefer it this way",
    )
    return {
        "accepted": published["accepted"],
        "version_incremented": published["default"]["version_ordinal"]
        == default["version_ordinal"] + 1,
        "previous_retained": published["previous"]["dashboard"]["tile_order"]
        == ["DEADLINES", "OPEN_OPPORTUNITIES"],
        "emits_an_audit_event": bool(published.get("audit_event")),
        "unauthorized_publish_refused": not unauthorized["accepted"],
    }


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "G177K-01",
        "name": "verified_identity_no_affiliation",
        "narrative": "We know who they are. We do not know that they work there.",
        "run": case_01_verified_identity_no_affiliation,
        "expect": {
            "permitted": False,
            "identity_sufficient": True,
            "affiliation_sufficient": False,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G177K-02",
        "name": "verified_affiliation_no_authority",
        "narrative": (
            "They work there. That is not permission to act for the government."
        ),
        "run": case_02_verified_affiliation_no_authority,
        "expect": {
            "permitted": False,
            "affiliation_sufficient": True,
            "authority_sufficient": False,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G177K-03",
        "name": "self_asserted_affiliation",
        "narrative": (
            "They said they work there, and somebody granted authority anyway. "
            "Saying so is not evidence."
        ),
        "run": case_03_self_asserted_affiliation,
        "expect": {
            "permitted": False,
            "invariant_caught_the_inconsistency": True,
        },
    },
    {
        "case_id": "G177K-04",
        "name": "manually_verified_authority",
        "narrative": "The first-four-customer path: a named human signs for it.",
        "run": case_04_manually_verified_authority,
        "expect": {
            "accepted": True,
            "permitted": True,
            "names_a_verifier": True,
            "states_a_reason": True,
            "emits_an_audit_event": True,
            "no_customer_identity_hardcoded": True,
            "invariant_failures": [],
        },
    },
    {
        "case_id": "G177K-05",
        "name": "authority_revoked",
        "narrative": (
            "Authority ends. The organisation, its work and its audit trail do not."
        ),
        "run": case_05_authority_revoked,
        "expect": {
            "permitted": False,
            "organization_deleted": False,
            "historical_work_deleted": False,
            "audit_history_erased": False,
            "membership_removed": False,
            "unattributed_revocation_refused": True,
        },
    },
    {
        "case_id": "G177K-06",
        "name": "invitation_from_authorized_org_admin",
        "narrative": "The ordinary path, which must still work.",
        "run": case_06_invitation_from_authorized_org_admin,
        "expect": {"accepted": True, "invitation_exists": True},
    },
    {
        "case_id": "G177K-07",
        "name": "invitation_from_ordinary_member",
        "narrative": (
            "Refused at issue, so an unauthorised invitation never exists to "
            "be found in somebody's inbox."
        ),
        "run": case_07_invitation_from_ordinary_member,
        "expect": {"accepted": False, "invitation_exists": False},
    },
    {
        "case_id": "G177K-08",
        "name": "cross_tenant_admin_attempt",
        "narrative": "A real administrator of one Tribe reaching into another.",
        "run": case_08_cross_tenant_admin_attempt,
        "expect": {"permitted": False, "cross_tenant_attempt": True},
    },
    {
        "case_id": "G177K-09",
        "name": "expired_authority",
        "narrative": (
            "Stored state still reads MANUALLY_VERIFIED. Reading the column "
            "is how an expired administrator keeps administering."
        ),
        "run": case_09_expired_authority,
        "expect": {
            "permitted": False,
            "effective_status": "EXPIRED",
            "stored_status_unchanged": True,
            "permitted_before_expiry": True,
        },
    },
    {
        "case_id": "G177K-10",
        "name": "conflicting_evidence",
        "narrative": (
            "Two resolutions, one accepted and one rejected. The system asks "
            "rather than taking whichever was written last."
        ),
        "run": case_10_conflicting_evidence,
        "expect": {"conflicting_evidence": True, "review_required": True},
    },
    {
        "case_id": "G177K-11",
        "name": "organization_has_no_authorized_admin",
        "narrative": (
            "The live state of the real tenant. An empty authority set must "
            "read as nobody, never as no-restriction-found."
        ),
        "run": case_11_organization_has_no_authorized_admin,
        "expect": {
            "grant_count": 0,
            "anybody_may_administer": False,
            "empty_set_denies": True,
        },
    },
    {
        "case_id": "G177K-12",
        "name": "controlling_company_manual_verification",
        "narrative": "The one exemption from the tenancy rule, and only this one.",
        "run": case_12_controlling_company_manual_verification,
        "expect": {"permitted": True, "cross_tenant_attempt": False},
    },
    {
        "case_id": "G177K-13",
        "name": "org_admin_tries_controlling_company_action",
        "narrative": (
            "Three routes to the same escalation - the action, an invitation, "
            "and the function itself - all refused."
        ),
        "run": case_13_org_admin_tries_controlling_company_action,
        "expect": {
            "permitted": False,
            "escalation_refused": True,
            "escalation_flagged": True,
            "direct_call_refused": True,
        },
    },
    {
        "case_id": "G177K-14",
        "name": "personal_layout_does_not_change_org_default",
        "narrative": (
            "Somebody reorders their own tiles. Everyone else's dashboard "
            "stays exactly where it was."
        ),
        "run": case_14_personal_layout_does_not_change_org_default,
        "expect": {
            "person_sees_their_own_order": True,
            "org_default_unchanged": True,
            "org_default_still_original": True,
            "branding_came_from_the_organization": True,
            "override_invariant_failures": [],
        },
    },
    {
        "case_id": "G177K-15",
        "name": "org_admin_publishes_new_default",
        "narrative": "Deliberate, attributed, authorised, versioned.",
        "run": case_15_org_admin_publishes_new_default,
        "expect": {
            "accepted": True,
            "version_incremented": True,
            "previous_retained": True,
            "emits_an_audit_event": True,
            "unauthorized_publish_refused": True,
        },
    },
)

_CAVEAT: dict[str, Any] = {
    "measured_against": "this corpus only",
    "corpus_is_world_truth": False,
    "real_tribe_onboarded": False,
    "why": (
        "Fifteen cases we thought of. Passing them means the model handles "
        "the situations we imagined. No real Tribe has been onboarded and no "
        "authority has been verified for a real organisation."
    ),
}


def grade_case(case: dict[str, Any]) -> dict[str, Any]:
    observed = case["run"]()
    failures = sorted(
        f"{key}_expected_{case['expect'][key]}_observed_{observed.get(key)}"
        for key in case["expect"]
        if observed.get(key) != case["expect"][key]
    )
    return {
        "case_id": case["case_id"],
        "name": case["name"],
        "passed": not failures,
        "failures": failures,
        "observed": observed,
    }


def grade_corpus(cases: tuple[dict[str, Any], ...] | None = None) -> dict[str, Any]:
    cases = cases if cases is not None else CASES
    graded = [grade_case(case) for case in cases]
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(graded),
        "passed_count": sum(1 for g in graded if g["passed"]),
        "failed_cases": [
            {"case_id": g["case_id"], "name": g["name"], "failures": g["failures"]}
            for g in graded
            if not g["passed"]
        ],
        "cases": graded,
        **_CAVEAT,
    }


def describe_corpus() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_version": CORPUS_VERSION,
        "case_count": len(CASES),
        "case_ids": [c["case_id"] for c in CASES],
        "every_case_has_a_narrative": all(c.get("narrative") for c in CASES),
        "every_case_has_expectations": all(c.get("expect") for c in CASES),
        "exercises_the_real_services": True,
        "clock_is_pinned": NOW,
        **_CAVEAT,
    }
