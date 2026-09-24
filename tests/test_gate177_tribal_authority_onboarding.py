"""Gate 177: Tribal authority, onboarding and tenant administration.

The permanent principle under test:

    IDENTITY VERIFIED is not AFFILIATION VERIFIED is not AUTHORITY VERIFIED

Each dimension is tested for refusing on its own, and the instruments are
tested for falsifiability rather than only for passing.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from nativeforge.services.organization_customization_service import (
    apply_personal_override,
    branding_invariant_failures,
    build_org_default,
    build_personal_override,
    dashboard_invariant_failures,
    describe_customization_model,
    override_invariant_failures,
    publish_org_default,
)
from nativeforge.services.organization_profile_service import (
    AMBIGUOUS,
    EXPLICITLY_EMPTY,
    LOOKUP_MISS,
    RECOGNIZED,
    build_profile_version,
    phrase_resolution_failures,
    profile_invariant_failures,
    resolve_phrase,
    resolve_phrases,
    revise_profile,
)
from nativeforge.services.tenant_administration_service import (
    ACTION_CREATE_ORGANIZATION,
    ACTION_INVITE_MEMBER,
    ACTION_VERIFY_AUTHORITY_MANUALLY,
    ASSIGNABLE_BY,
    CONTROLLING_COMPANY_ADMIN,
    CUSTOMER_ROLES,
    ORG_ADMIN,
    ORG_MEMBER,
    ORG_SUPER_ADMIN,
    authorize_admin_action,
    describe_administration_model,
    invitation_invariant_failures,
    issue_invitation,
    revoke_invitation,
)
from nativeforge.services.tribal_authority_evidence_service import (
    CONTROLLING_COMPANY_VERIFICATION,
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    ESTABLISHES_AUTHORITY,
    OFFICIAL_TRIBAL_WEBSITE,
    ORGANIZATION_EMAIL_DOMAIN,
    TRIBAL_RESOLUTION,
    build_evidence,
    decide_evidence,
    describe_evidence_model,
    evidence_invariant_failures,
    grade_evidence_set,
    verify_authority_manually,
)
from nativeforge.services.tribal_authority_gold_corpus_service import (
    CASES,
    describe_corpus,
    grade_case,
    grade_corpus,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_SELF_ASSERTED,
    AFFILIATION_UNVERIFIED,
    AFFILIATION_VERIFIED,
    AUTHORITY_MANUALLY_VERIFIED,
    AUTHORITY_UNVERIFIED,
    GRANT_FIELDS,
    IDENTITY_UNKNOWN,
    IDENTITY_UNVERIFIED,
    IDENTITY_VERIFIED,
    SCOPE_ADMINISTER_TENANT,
    SCOPE_MANAGE_PROFILE,
    build_authority_grant,
    describe_authority_model,
    grant_invariant_failures,
    may_administer_tenant,
    revoke_authority,
)
from nativeforge.services.tribal_authority_self_health_service import (
    DETECTORS,
    assess_authority_health,
    describe_self_health,
    prove_detectors_fire,
)

REPO = Path(__file__).resolve().parents[1]

NOW = "2026-09-24"

SIGNED = dict(
    verified_by="controlling-company:staff-1",
    verified_at="2026-09-01",
    reason="council resolution 2026-14 reviewed",
)


def _grant(**over):
    base = dict(
        organization_id="org-A",
        identity_id="person-1",
        identity_status=IDENTITY_VERIFIED,
        affiliation_status=AFFILIATION_VERIFIED,
        authority_status=AUTHORITY_UNVERIFIED,
    )
    base.update(over)
    return build_authority_grant(**base)


# ==================== 177B: three questions, three answers ============


def test_identity_affiliation_and_authority_are_three_columns():
    """The principle, stated as structure rather than as intent."""
    model = describe_authority_model()
    assert len(model["identity_states"]) == 5
    assert len(model["affiliation_states"]) == 7
    assert len(model["authority_states"]) == 8
    assert model["no_single_verified_boolean"] is True
    assert not {"verified", "is_verified", "authority_verified"} & set(GRANT_FIELDS)


def test_each_dimension_refuses_on_its_own():
    """A refusal must name WHICH question failed, not just that one did."""
    no_affiliation = _grant(affiliation_status=AFFILIATION_UNVERIFIED)
    verdict = may_administer_tenant(no_affiliation, now=NOW)
    assert verdict["permitted"] is False
    assert verdict["identity_sufficient"] is True
    assert verdict["affiliation_sufficient"] is False
    assert "affiliation_is_UNVERIFIED" in verdict["refusals"]

    no_identity = _grant(identity_status=IDENTITY_UNVERIFIED)
    verdict = may_administer_tenant(no_identity, now=NOW)
    assert verdict["identity_sufficient"] is False
    assert verdict["affiliation_sufficient"] is True


def test_self_asserted_affiliation_never_suffices():
    """ "I work there" is a claim. A system that accepts it has no model."""
    grant = _grant(
        affiliation_status=AFFILIATION_SELF_ASSERTED,
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        **SIGNED,
    )
    assert may_administer_tenant(grant, now=NOW)["permitted"] is False
    # And a second, independent mechanism catches the same lie.
    assert any("over_affiliation" in f for f in grant_invariant_failures(grant))


def test_unknown_is_not_unverified():
    """ "We never asked" must not decay into "we asked and the answer was no"."""
    assert IDENTITY_UNKNOWN != IDENTITY_UNVERIFIED
    assert describe_authority_model()["unknown_is_distinct_from_unverified"] is True


def test_a_collapsing_flag_is_refused():
    """The refusal that keeps the three questions three."""
    grant = _grant()
    grant["verified"] = True
    assert any("collapsing_flag" in f for f in grant_invariant_failures(grant))


def test_expiry_is_applied_at_read_time():
    """Reading the stored column is how an expired admin keeps administering."""
    grant = _grant(
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        expires_at="2026-06-30",
        **SIGNED,
    )
    expired = may_administer_tenant(grant, now=NOW)
    assert expired["permitted"] is False
    assert expired["authority_status_effective"] == "EXPIRED"
    assert expired["authority_status_stored"] == AUTHORITY_MANUALLY_VERIFIED
    # The check must be able to NOT fire.
    assert may_administer_tenant(grant, now="2026-06-01")["permitted"] is True


def test_scope_is_not_a_blanket_grant():
    """A grant to manage a profile is not a grant to administer a tenant."""
    grant = _grant(
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        scope=SCOPE_MANAGE_PROFILE,
        **SIGNED,
    )
    assert (
        may_administer_tenant(grant, scope=SCOPE_ADMINISTER_TENANT, now=NOW)[
            "permitted"
        ]
        is False
    )
    assert (
        may_administer_tenant(grant, scope=SCOPE_MANAGE_PROFILE, now=NOW)["permitted"]
        is True
    )


# ==================== 177C: evidence ==================================


def test_a_mailbox_is_not_a_mandate():
    """The intern and the chairperson share a domain."""
    assert ORGANIZATION_EMAIL_DOMAIN not in ESTABLISHES_AUTHORITY
    assert OFFICIAL_TRIBAL_WEBSITE not in ESTABLISHES_AUTHORITY
    domain = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="domain:example",
    )
    assert domain["establishes_affiliation"] is True
    assert domain["establishes_authority"] is False
    assert evidence_invariant_failures(domain) == []


def test_evidence_that_lies_about_itself_is_refused():
    domain = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="domain:example",
    )
    domain["establishes_authority"] = True
    assert any("flag_disagrees" in f for f in evidence_invariant_failures(domain))


def test_no_secret_is_ever_stored():
    """The cheapest way to leak credentials is to store them somewhere helpful."""
    evidence = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="doc:1",
    )
    evidence["api_key"] = "sk-abcdefghijklmnopqrstuvwx"
    failures = evidence_invariant_failures(evidence)
    assert any("looks_like_a_secret" in f for f in failures)


def test_pending_evidence_supports_nothing():
    """Evidence nobody has judged is a queue item, not a warrant."""
    pending = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="doc:1",
    )
    assert (
        grade_evidence_set(evidence=[pending], now=NOW)["supports_authority"] is False
    )

    decided = decide_evidence(
        evidence=pending,
        decision=DECISION_ACCEPTED,
        reviewer="staff-1",
        reason="resolution verified",
    )
    assert decided["accepted"] is True
    graded = grade_evidence_set(evidence=[decided["evidence"]], now=NOW)
    assert graded["supports_authority"] is True
    assert graded["authority_states_supported"] == ["DOCUMENT_VERIFIED"]


def test_a_machine_may_not_judge_evidence():
    pending = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="doc:1",
    )
    assert (
        decide_evidence(
            evidence=pending, decision=DECISION_ACCEPTED, reviewer=None, reason="x"
        )["accepted"]
        is False
    )
    assert (
        decide_evidence(
            evidence=pending, decision=DECISION_ACCEPTED, reviewer="r", reason=None
        )["accepted"]
        is False
    )


def test_conflicting_evidence_asks_for_a_human():
    """Not whichever row was written last."""
    common = dict(organization_id="org-A", subject_identity_id="p1")
    accepted = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        source_ref="doc:a",
        reviewer="staff-1",
        decision=DECISION_ACCEPTED,
        decided_at="2026-09-01",
        reason="verified",
        **common,
    )
    rejected = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        source_ref="doc:b",
        reviewer="staff-2",
        decision=DECISION_REJECTED,
        decided_at="2026-09-02",
        reason="superseded",
        **common,
    )
    graded = grade_evidence_set(evidence=[accepted, rejected], now=NOW)
    assert graded["conflicting_evidence"] is True
    assert graded["review_required"] is True
    # And it must be able to NOT fire.
    assert (
        grade_evidence_set(evidence=[accepted], now=NOW)["conflicting_evidence"]
        is False
    )


def test_no_single_evidence_type_is_assumed_sufficient():
    model = describe_evidence_model()
    assert model["no_single_evidence_type_is_sufficient_for_all_tribes"] is True
    assert model["evidence_types_are_extensible"] is True
    assert model["email_domain_is_not_authority"] is True
    assert model["pending_evidence_supports_nothing"] is True


# ==================== 177D: the first four customers ==================


def test_manual_verification_is_attributed():
    result = verify_authority_manually(
        organization_id="org-A",
        identity_id="p1",
        verified_by="controlling-company:staff-1",
        verified_by_is_controlling_company=True,
        reason="chairperson confirmed; minutes on file",
        customer_relationship_ref="crm:agreement-1",
        verified_at="2026-09-01",
    )
    assert result["accepted"] is True
    grant = result["grant"]
    assert grant["authority_status"] == AUTHORITY_MANUALLY_VERIFIED
    assert grant["authority_method"] == CONTROLLING_COMPANY_VERIFICATION
    assert grant["verified_by"] and grant["reason"] and grant["verified_at"]
    assert grant_invariant_failures(grant) == []
    assert may_administer_tenant(grant, now=NOW)["permitted"] is True
    assert result["audit_event"]["action"] == "authority.manually_verified"
    assert result["no_customer_identity_hardcoded"] is True


def test_a_customer_admin_cannot_manually_verify():
    result = verify_authority_manually(
        organization_id="org-A",
        identity_id="p2",
        verified_by="org-super-admin",
        verified_by_is_controlling_company=False,
        reason="I am the super admin",
    )
    assert result["accepted"] is False
    assert result["grant"] is None


def test_verified_authority_must_be_signed():
    grant = _grant(authority_status=AUTHORITY_MANUALLY_VERIFIED)
    failures = grant_invariant_failures(grant)
    assert "verified_authority_names_no_verifier" in failures
    assert "verified_authority_has_no_date" in failures
    assert "verified_authority_states_no_reason" in failures


# ==================== 177J: revocation ================================


def test_revocation_removes_authority_and_nothing_else():
    grant = _grant(authority_status=AUTHORITY_MANUALLY_VERIFIED, **SIGNED)
    result = revoke_authority(
        grant=grant, revoked_by="staff-1", reason="no longer holds the office"
    )
    assert result["accepted"] is True
    assert may_administer_tenant(result["grant"], now=NOW)["permitted"] is False
    assert result["organization_deleted"] is False
    assert result["historical_work_deleted"] is False
    assert result["audit_history_erased"] is False
    assert result["membership_removed"] is False
    # Identity and affiliation are untouched: losing authority says nothing
    # about who somebody is or where they work.
    assert result["grant"]["identity_status"] == IDENTITY_VERIFIED
    assert result["grant"]["affiliation_status"] == AFFILIATION_VERIFIED


def test_revocation_must_be_attributed_and_explained():
    grant = _grant(authority_status=AUTHORITY_MANUALLY_VERIFIED, **SIGNED)
    assert (
        revoke_authority(grant=grant, revoked_by=None, reason="x")["accepted"] is False
    )
    assert (
        revoke_authority(grant=grant, revoked_by="a", reason=None)["accepted"] is False
    )


def test_membership_removal_is_a_separate_decision():
    grant = _grant(authority_status=AUTHORITY_MANUALLY_VERIFIED, **SIGNED)
    kept = revoke_authority(grant=grant, revoked_by="s", reason="r")
    removed = revoke_authority(
        grant=grant, revoked_by="s", reason="r", remove_membership=True
    )
    assert kept["membership_removed"] is False
    assert removed["membership_removed"] is True
    assert removed["membership_removal_was_requested_separately"] is True


# ==================== 177F: the controlling-company boundary ==========


def test_no_customer_role_can_confer_controlling_company():
    """Not the top of the ladder. A different ladder."""
    assert not (set(ASSIGNABLE_BY[CONTROLLING_COMPANY_ADMIN]) & CUSTOMER_ROLES)
    model = describe_administration_model()
    assert model["customer_admin_cannot_become_controlling_company"] is True
    assert model["customer_and_controlling_roles_are_disjoint"] is True


@pytest.mark.parametrize("role", sorted(CUSTOMER_ROLES))
def test_no_customer_role_may_verify_authority_manually(role):
    decision = authorize_admin_action(
        action=ACTION_VERIFY_AUTHORITY_MANUALLY,
        actor_role=role,
        actor_organization_id="org-A",
        target_organization_id="org-A",
    )
    assert decision["permitted"] is False


@pytest.mark.parametrize("role", sorted(CUSTOMER_ROLES))
def test_no_customer_role_may_create_an_organization(role):
    decision = authorize_admin_action(
        action=ACTION_CREATE_ORGANIZATION,
        actor_role=role,
        actor_organization_id="org-A",
        target_organization_id="org-A",
    )
    assert decision["permitted"] is False


def test_controlling_company_may_do_both():
    """The boundary must be able to say yes, or it is just a ban."""
    for action in (ACTION_VERIFY_AUTHORITY_MANUALLY, ACTION_CREATE_ORGANIZATION):
        decision = authorize_admin_action(
            action=action,
            actor_role=CONTROLLING_COMPANY_ADMIN,
            actor_organization_id="controlling-company",
            target_organization_id="org-A",
        )
        assert decision["permitted"] is True, action


def test_cross_tenant_administration_is_refused():
    cross = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-B",
    )
    assert cross["permitted"] is False
    assert cross["cross_tenant_attempt"] is True
    # And the same actor is permitted at home.
    same = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-A",
    )
    assert same["permitted"] is True


def test_tenancy_is_checked_before_privilege():
    """A genuine admin is refused elsewhere before their role is consulted."""
    decision = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_MEMBER,
        actor_organization_id="org-A",
        target_organization_id="org-B",
    )
    assert decision["cross_tenant_attempt"] is True


# ==================== 177G: invitations ===============================


def test_an_unauthorized_invitation_never_exists():
    """Refused at issue, not filtered at acceptance."""
    result = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="member-1",
        invited_by_role=ORG_MEMBER,
        invited_by_organization_id="org-A",
    )
    assert result["accepted"] is False
    assert result["invitation"] is None


def test_an_authorized_invitation_works():
    result = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="admin-1",
        invited_by_role=ORG_ADMIN,
        invited_by_organization_id="org-A",
    )
    assert result["accepted"] is True
    assert invitation_invariant_failures(result["invitation"]) == []


def test_an_invitation_cannot_escalate_to_controlling_company():
    result = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:x",
        offered_role=CONTROLLING_COMPANY_ADMIN,
        invited_by="super-1",
        invited_by_role=ORG_SUPER_ADMIN,
        invited_by_organization_id="org-A",
    )
    assert result["accepted"] is False
    assert result["decision"]["privilege_escalation_attempt"] is True

    # And a forged row is refused by its invariants too.
    good = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="admin-1",
        invited_by_role=ORG_ADMIN,
        invited_by_organization_id="org-A",
    )["invitation"]
    forged = dict(good, offered_role=CONTROLLING_COMPANY_ADMIN)
    assert any(
        "controlling_company" in f for f in invitation_invariant_failures(forged)
    )


def test_revoking_an_invitation_requires_a_reason():
    invitation = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="admin-1",
        invited_by_role=ORG_ADMIN,
        invited_by_organization_id="org-A",
    )["invitation"]
    assert (
        revoke_invitation(
            invitation=invitation,
            revoked_by="admin-1",
            revoked_by_role=ORG_ADMIN,
            revoked_by_organization_id="org-A",
            reason=None,
        )["accepted"]
        is False
    )
    revoked = revoke_invitation(
        invitation=invitation,
        revoked_by="admin-1",
        revoked_by_role=ORG_ADMIN,
        revoked_by_organization_id="org-A",
        reason="sent to the wrong person",
    )
    assert revoked["accepted"] is True
    assert revoked["invitation"]["revoked_reason"]


def test_an_invitation_cannot_cross_tenants():
    result = issue_invitation(
        organization_id="org-B",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="admin-1",
        invited_by_role=ORG_SUPER_ADMIN,
        invited_by_organization_id="org-A",
    )
    assert result["accepted"] is False


# ==================== 177E: the phrase rule ===========================


def test_a_lookup_miss_is_not_an_empty_answer():
    """The rule the block called critical.

    A Tribe writing "language revitalization" must never be treated as though
    they left the field blank.
    """
    miss = resolve_phrase("salmon habitat restoration")
    empty = resolve_phrase("none")
    assert miss["outcome"] == LOOKUP_MISS
    assert empty["outcome"] == EXPLICITLY_EMPTY
    # Both yield no classes, and are still distinguishable.
    assert miss["entity_classes"] == empty["entity_classes"] == []
    assert miss["review_required"] is True
    assert empty["review_required"] is False


def test_an_ambiguous_phrase_keeps_its_candidates():
    """Discarding them would lose the fact that we knew something."""
    ambiguous = resolve_phrase("infrastructure")
    assert ambiguous["outcome"] == AMBIGUOUS
    assert ambiguous["candidates"]
    assert ambiguous["entity_classes"] == []
    assert ambiguous["review_required"] is True


def test_a_recognized_phrase_yields_classes():
    known = resolve_phrase("language revitalization")
    assert known["outcome"] == RECOGNIZED
    assert "LANGUAGE" in known["entity_classes"]
    assert known["review_required"] is False


def test_the_phrase_detector_can_fail():
    """A detector that cannot fail proves nothing."""
    asserted = {
        "resolved": [
            {
                "phrase": "x",
                "outcome": AMBIGUOUS,
                "entity_classes": ["A"],
                "candidates": ["A", "B"],
                "review_required": True,
            }
        ]
    }
    assert any(
        "ambiguous_phrase_asserted_classes" in f
        for f in phrase_resolution_failures(asserted)
    )
    quiet = {
        "resolved": [
            {
                "phrase": "y",
                "outcome": LOOKUP_MISS,
                "entity_classes": [],
                "candidates": [],
                "review_required": False,
            }
        ]
    }
    assert any("did_not_ask_for_review" in f for f in phrase_resolution_failures(quiet))


def test_no_phrase_is_silently_discarded():
    resolution = resolve_phrases(
        ["housing", "language revitalization", "infrastructure", "salmon habitat"]
    )
    assert resolution["lookup_miss_count"] == 1
    assert resolution["ambiguous_count"] == 1
    assert resolution["review_required"] is True
    assert len(resolution["unresolved_phrases"]) == 2
    assert phrase_resolution_failures(resolution) == []


# ==================== 177E: profile versioning ========================


def test_a_profile_change_keeps_the_previous_version():
    v1 = build_profile_version(
        organization_id="org-A",
        values={
            "legal_name": "Example Tribe",
            "entity_type": "FEDERALLY_RECOGNIZED_TRIBE",
            "funding_sectors": ["housing", "water"],
        },
        changed_by="p1",
        reason="initial",
    )
    result = revise_profile(
        current=v1,
        changes={"funding_sectors": ["housing", "broadband"]},
        changed_by="p2",
        reason="added broadband",
    )
    assert result["accepted"] is True
    assert result["version"]["version_ordinal"] == 2
    assert result["version"]["supersedes_version_id"] == v1["profile_version_id"]
    assert result["previous"]["values"]["funding_sectors"] == ["housing", "water"]
    assert result["changed_fields"] == ["funding_sectors"]
    assert profile_invariant_failures(result["version"]) == []


def test_a_profile_change_requires_a_named_actor():
    v1 = build_profile_version(
        organization_id="org-A", values={}, changed_by="p1", reason="initial"
    )
    assert (
        revise_profile(current=v1, changes={"legal_name": "x"}, changed_by=None)[
            "accepted"
        ]
        is False
    )


def test_unresolved_phrases_send_the_profile_to_review():
    version = build_profile_version(
        organization_id="org-A",
        values={"strategic_priorities": ["salmon habitat restoration"]},
        changed_by="p1",
        reason="initial",
    )
    assert version["review_required"] is True
    assert version["unresolved_phrases"]
    assert profile_invariant_failures(version) == []


# ==================== 177H/I: defaults and overrides ==================


def _default():
    return build_org_default(
        organization_id="org-A",
        branding={"primary_color": "#1B4332", "display_name": "Example Tribe"},
        dashboard={
            "tile_order": ["DEADLINES", "OPEN_OPPORTUNITIES"],
            "density": "COMPACT",
        },
        published_by="admin-1",
        reason="initial",
    )


def test_a_personal_override_never_moves_the_org_default():
    """The quiet, expensive failure this module exists to prevent."""
    default = _default()
    before = list(default["dashboard"]["tile_order"])
    override = build_personal_override(
        organization_id="org-A",
        identity_id="p7",
        preferences={"tile_order": ["OPEN_OPPORTUNITIES"], "density": "COMFORTABLE"},
    )
    effective = apply_personal_override(org_default=default, override=override)

    assert effective["dashboard"]["tile_order"] == ["OPEN_OPPORTUNITIES"]
    assert effective["org_default_unchanged"] is True
    assert default["dashboard"]["tile_order"] == before
    assert default["dashboard"]["density"] == "COMPACT"

    # Deep mutation of what the person sees must not reach the organisation.
    effective["dashboard"]["tile_order"].append("TEAM")
    assert "TEAM" not in default["dashboard"]["tile_order"]


def test_a_personal_override_cannot_carry_branding():
    default = _default()
    override = build_personal_override(
        organization_id="org-A", identity_id="p8", preferences={}
    )
    override["preferences"]["primary_color"] = "#000000"
    assert any(
        "carries_org_branding" in f for f in override_invariant_failures(override)
    )
    effective = apply_personal_override(org_default=default, override=override)
    assert effective["ignored_fields"] == ["primary_color"]
    assert effective["branding"]["primary_color"] == "#1B4332"


def test_publishing_an_org_default_is_deliberate_and_attributed():
    default = _default()
    published = publish_org_default(
        current=default,
        changes={"dashboard": {"tile_order": ["OPEN_OPPORTUNITIES", "DEADLINES"]}},
        published_by="admin-1",
        publisher_may_publish=True,
        reason="the team asked for opportunities first",
    )
    assert published["accepted"] is True
    assert published["default"]["version_ordinal"] == 2
    assert published["previous"]["dashboard"]["tile_order"] == [
        "DEADLINES",
        "OPEN_OPPORTUNITIES",
    ]
    assert published["audit_event"]["action"] == "organization.defaults_published"


@pytest.mark.parametrize(
    ("label", "kwargs"),
    [
        (
            "no authority",
            {"publisher_may_publish": False, "published_by": "x", "reason": "r"},
        ),
        (
            "no actor",
            {"publisher_may_publish": True, "published_by": None, "reason": "r"},
        ),
        (
            "no reason",
            {"publisher_may_publish": True, "published_by": "x", "reason": None},
        ),
    ],
)
def test_publishing_is_refused_without_standing(label, kwargs):
    assert (
        publish_org_default(current=_default(), changes={}, **kwargs)["accepted"]
        is False
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "<script>alert(1)</script>"},
        {"logo_ref": "javascript:alert(1)"},
        {"primary_color": "red"},
        {"custom_css": "body{background:url(x)}"},
        {"display_name": "a&#x3c;b"},
    ],
)
def test_unsafe_branding_is_refused(payload):
    """A theming text box is how a dashboard becomes somebody else's JS."""
    assert branding_invariant_failures(payload) != []


def test_safe_branding_is_accepted():
    """The refusal must be able to say yes."""
    assert (
        branding_invariant_failures(
            {
                "display_name": "Example Tribe",
                "primary_color": "#1B4332",
                "logo_ref": "media:logo-1",
            }
        )
        == []
    )


def test_a_hidden_landing_tile_is_refused():
    assert (
        dashboard_invariant_failures(
            {
                "tile_order": ["DEADLINES"],
                "hidden_tiles": ["TEAM"],
                "landing_tile": "TEAM",
            }
        )
        != []
    )


def test_the_customization_model_states_its_separation():
    model = describe_customization_model()
    assert model["personal_override_never_mutates_the_org_default"] is True
    assert model["org_default_changes_only_by_publishing"] is True
    assert model["no_free_form_css_or_script_field"] is True


# ==================== 177L: self health ===============================


def test_specific_self_health_detectors_fire():
    """A generic "invalid" is not a result."""
    proof = prove_detectors_fire()
    assert proof["healthy_population_is_silent"] is True, proof["baseline_findings"]
    assert proof["all_detectors_fire"] is True, proof["detectors_that_did_not_fire"]
    assert proof["all_detectors_are_specific"] is True, proof[
        "detectors_that_fired_too_broadly"
    ]
    assert proof["detector_count"] == len(DETECTORS) == 9
    assert describe_self_health()["every_detector_has_a_meaning"] is True


def test_the_revocation_detector_compares_two_sources():
    """It once asked the function it was checking, and could never disagree."""
    grant = _grant(authority_status=AUTHORITY_MANUALLY_VERIFIED, **SIGNED)
    health = assess_authority_health(
        grants=[grant],
        revocations=[
            {"authority_id": grant["authority_id"], "revoked_at": "2026-09-10"}
        ],
        now=NOW,
    )
    assert "revoked_authority_still_administers" in health["detectors_fired"]
    # With no revocation recorded, it must stay silent.
    assert (
        "revoked_authority_still_administers"
        not in assess_authority_health(grants=[grant], revocations=[], now=NOW)[
            "detectors_fired"
        ]
    )


# ==================== 177K: the corpus ================================


def test_the_corpus_passes_every_case():
    report = grade_corpus()
    assert report["case_count"] == 15
    assert report["failed_cases"] == [], report["failed_cases"]


def test_the_corpus_can_fail():
    """Mutating an expectation must turn a green case red."""
    case = dict(next(c for c in CASES if c["name"] == "cross_tenant_admin_attempt"))
    case["expect"] = dict(case["expect"], permitted=True)
    graded = grade_case(case)
    assert graded["passed"] is False
    assert any("permitted_expected_True" in f for f in graded["failures"])


def test_the_corpus_never_claims_to_be_the_world():
    for payload in (describe_corpus(), grade_corpus()):
        assert payload["corpus_is_world_truth"] is False
        assert payload["real_tribe_onboarded"] is False
    assert describe_corpus()["clock_is_pinned"] == NOW


# ==================== 0063: the constraints are real ==================

NOW_DT = dt.datetime(2026, 9, 24, tzinfo=dt.UTC)

_GRANT_ROW = {
    "organization_id": "org-A",
    "identity_id": "person-1",
    "identity_status": "VERIFIED",
    "affiliation_status": "VERIFIED",
    "authority_status": "MANUALLY_VERIFIED",
    "authority_method": "CONTROLLING_COMPANY_VERIFICATION",
    "scope": "ADMINISTER_TENANT",
    "verified_by": "staff-1",
    "verified_at": NOW_DT,
    "expires_at": None,
    "revoked_at": None,
    "revoked_by": None,
    "revoked_reason": None,
    "reason": "council resolution reviewed",
    "evidence_ids_json": '["e1"]',
    "is_demo": False,
    "model_version": "test",
    "created_at": NOW_DT,
}

_INVITE_ROW = {
    "organization_id": "org-A",
    "invited_by": "admin-1",
    "invited_by_role": "ORG_ADMIN",
    "invited_subject_ref": "subject:new",
    "offered_role": "ORG_MEMBER",
    "invite_state": "PENDING",
    "issued_at": NOW_DT,
    "expires_at": None,
    "answered_at": None,
    "revoked_by": None,
    "revoked_reason": None,
    "is_demo": False,
    "model_version": "test",
}


def _insert(session, table, key_column, key, defaults, override):
    row = {key_column: key, **defaults, **override}
    columns = ", ".join(row)
    values = ", ".join(f":{name}" for name in row)
    session.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), row)


@pytest.mark.parametrize(
    ("label", "override"),
    [
        (
            "authority over self-asserted affiliation",
            {"affiliation_status": "SELF_ASSERTED"},
        ),
        ("authority over unverified affiliation", {"affiliation_status": "UNVERIFIED"}),
        ("authority over unverified identity", {"identity_status": "UNVERIFIED"}),
        ("verified authority with no verifier", {"verified_by": None}),
        ("verified authority with no reason", {"reason": None}),
        ("revocation with no actor", {"revoked_at": NOW_DT, "revoked_by": None}),
    ],
)
def test_the_database_refuses_an_authority_that_outranks_its_evidence(label, override):
    """The collapse, made unrepresentable rather than merely discouraged."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(
                session,
                "nf_tribal_authority_grants",
                "authority_id",
                f"bad-{label}",
                _GRANT_ROW,
                override,
            )
            session.commit()
        session.rollback()


def test_the_database_accepts_an_honest_unverified_grant():
    """The constraint must be able to say yes, or it is just a ban on writing."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        try:
            _insert(
                session,
                "nf_tribal_authority_grants",
                "authority_id",
                "honest-unverified",
                _GRANT_ROW,
                {
                    "authority_status": "UNVERIFIED",
                    "affiliation_status": "SELF_ASSERTED",
                    "identity_status": "UNVERIFIED",
                    "verified_by": None,
                    "verified_at": None,
                    "reason": None,
                },
            )
            session.commit()
        finally:
            session.execute(text("DELETE FROM nf_tribal_authority_grants"))
            session.commit()


@pytest.mark.parametrize(
    ("label", "override"),
    [
        (
            "org admin confers controlling company",
            {"offered_role": "CONTROLLING_COMPANY_ADMIN"},
        ),
        ("ordinary member invites", {"invited_by_role": "ORG_MEMBER"}),
        ("reviewer invites", {"invited_by_role": "ORG_REVIEWER"}),
    ],
)
def test_the_database_refuses_an_impossible_invitation(label, override):
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(
                session,
                "nf_organization_invitations",
                "invitation_id",
                f"bad-inv-{label}",
                _INVITE_ROW,
                override,
            )
            session.commit()
        session.rollback()


def test_the_personal_override_table_has_no_branding_column():
    """One person's taste has nowhere to become the Tribe's identity."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        rows = session.execute(
            text("PRAGMA table_info(nf_personal_dashboard_overrides)")
        ).fetchall()
    columns = {row[1] for row in rows}
    assert columns, "the override table does not exist"
    assert not columns & {
        "logo_ref",
        "symbol_ref",
        "primary_color",
        "secondary_color",
        "accent_color",
        "display_name",
    }


def test_the_database_refuses_evidence_claiming_authority_it_cannot_have():
    from nativeforge.db.session import SessionLocal

    row = {
        "evidence_type": "ORGANIZATION_EMAIL_DOMAIN",
        "organization_id": "org-A",
        "subject_identity_id": "person-1",
        "issuer": None,
        "source_ref": "domain:example",
        "artifact_ref": None,
        "reviewer": None,
        "decision": "PENDING",
        "decided_at": None,
        "recorded_at": NOW_DT,
        "expires_at": None,
        "reason": None,
        "establishes_identity": False,
        "establishes_affiliation": True,
        "establishes_authority": True,
        "is_demo": False,
        "model_version": "test",
    }
    with SessionLocal() as session:
        with pytest.raises(sa.exc.IntegrityError):
            _insert(
                session,
                "nf_tribal_authority_evidence",
                "evidence_id",
                "bad-domain",
                row,
                {},
            )
            session.commit()
        session.rollback()


# ==================== the instruments =================================


def test_network_zero():
    """The machinery exists without reaching anybody."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g177_phase_proof.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["network_requests"] == 0
    assert report["fixture_residue"] == 0
    assert report["gate177_ready"] is True
    # The measurement this gate turns on, asserted false on purpose.
    assert report["real_organization_has_an_authorized_admin"] is False


def test_the_survey_makes_no_network_call_and_writes_nothing():
    result = subprocess.run(  # noqa: S603
        [sys.executable, "scripts/_g177_survey_tribal_authority.py"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr[-3000:]
    report = json.loads(
        [line for line in result.stdout.splitlines() if line.startswith("{")][-1]
    )
    assert report["network_requests"] == 0
    assert report["wrote_nothing"] is True
    # The finding that shaped the gate.
    assert report["identity_affiliation_authority_separated"] is False
    assert "nf_authority_proof_records" in report["collapsed_structures"]
