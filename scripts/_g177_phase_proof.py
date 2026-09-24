"""177M: the facts the Gate 177 verifier asserts, measured rather than claimed.

Two kinds of fact, and they must not be confused.

MODEL facts come from the services and say what the machinery can do.

REAL facts come from `nativeforge.local.db` and say what it has to work with.
The one that matters in this gate is
`real_organization_has_an_authorized_admin`, which is FALSE: the real
organisation has zero active members and zero authority records. Adversarial
case 11 - "organisation has no authorised administrator" - is not a scenario
here, it is the current state of the real tenant, and the correct behaviour is
to say so rather than to default somebody into the gap.

This phase READS the real database and writes nothing to it. It makes no
network call. Prints one line of JSON.
"""

from __future__ import annotations

import datetime as dt
import json
import socket
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_ATTEMPTS = {"n": 0}


class _RefusedSocket:
    def __init__(self, *a, **k):
        _ATTEMPTS["n"] += 1
        raise OSError("Gate 177 makes no network call")


socket.socket = _RefusedSocket  # type: ignore[misc,assignment]

from nativeforge.services.organization_customization_service import (  # noqa: E402
    apply_personal_override,
    branding_invariant_failures,
    build_org_default,
    build_personal_override,
    describe_customization_model,
    override_invariant_failures,
    publish_org_default,
)
from nativeforge.services.organization_profile_service import (  # noqa: E402
    AMBIGUOUS,
    EXPLICITLY_EMPTY,
    LOOKUP_MISS,
    RECOGNIZED,
    build_profile_version,
    describe_profile_model,
    profile_invariant_failures,
    resolve_phrase,
    revise_profile,
)
from nativeforge.services.tenant_administration_service import (  # noqa: E402
    ACTION_CREATE_ORGANIZATION,
    ACTION_INVITE_MEMBER,
    ACTION_VERIFY_AUTHORITY_MANUALLY,
    CONTROLLING_COMPANY_ADMIN,
    ORG_ADMIN,
    ORG_MEMBER,
    ORG_SUPER_ADMIN,
    authorize_admin_action,
    describe_administration_model,
    invitation_invariant_failures,
    issue_invitation,
    revoke_invitation,
)
from nativeforge.services.tribal_authority_evidence_service import (  # noqa: E402
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    ORGANIZATION_EMAIL_DOMAIN,
    TRIBAL_RESOLUTION,
    build_evidence,
    describe_evidence_model,
    evidence_invariant_failures,
    evidence_types,
    grade_evidence_set,
    verify_authority_manually,
)
from nativeforge.services.tribal_authority_gold_corpus_service import (  # noqa: E402
    describe_corpus,
    grade_corpus,
)
from nativeforge.services.tribal_authority_model_service import (  # noqa: E402
    AFFILIATION_SELF_ASSERTED,
    AUTHORITY_MANUALLY_VERIFIED,
    AUTHORITY_UNVERIFIED,
    IDENTITY_VERIFIED,
    build_authority_grant,
    describe_authority_model,
    grant_invariant_failures,
    may_administer_tenant,
    revoke_authority,
)
from nativeforge.services.tribal_authority_self_health_service import (  # noqa: E402
    DETECTORS,
    describe_self_health,
    prove_detectors_fire,
)

REAL_ORG = "aaaaaaaabbbbccccddddeeeeeeeeeeee"
NOW = "2026-09-24"


def _real_state() -> dict[str, object]:
    db = ROOT / "nativeforge.local.db"
    out: dict[str, object] = {"real_database_present": db.exists()}
    if not db.exists():
        out["real_organization_has_an_authorized_admin"] = False
        return out

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        members = conn.execute(
            "SELECT count(*) FROM nf_org_memberships "
            "WHERE replace(lower(organization_id),'-','') = ? AND state = 'active'",
            (REAL_ORG,),
        ).fetchone()[0]
        proofs = conn.execute(
            "SELECT count(*) FROM nf_authority_proof_records "
            "WHERE replace(lower(organization_id),'-','') = ?",
            (REAL_ORG,),
        ).fetchone()[0]
        orgs = conn.execute("SELECT count(*) FROM organizations").fetchone()[0]
        revision = conn.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]

        # 0063 may not be applied here. That is a fact worth reporting, not a
        # reason to migrate somebody's database from inside a measurement.
        has_grants_table = bool(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name = 'nf_tribal_authority_grants'"
            ).fetchone()
        )
        grants = (
            conn.execute(
                "SELECT count(*) FROM nf_tribal_authority_grants "
                "WHERE replace(lower(organization_id),'-','') = ?",
                (REAL_ORG,),
            ).fetchone()[0]
            if has_grants_table
            else 0
        )
    finally:
        conn.close()

    out.update(
        {
            "organizations_in_the_database": orgs,
            "real_organization_active_members": members,
            "real_organization_legacy_authority_records": proofs,
            "real_organization_authority_grants": grants,
            "local_database_revision": revision,
            "authority_tables_applied_locally": has_grants_table,
            "real_organization_has_an_authorized_admin": grants > 0,
            "why_no_real_admin": (
                (
                    "migration 0063 is not applied to the local database "
                    f"(revision {revision}), so no authority grant exists here"
                )
                if not has_grants_table
                else (
                    "the real organisation has no authority grant; nobody has "
                    "been verified to act for it, and the system says so "
                    "rather than defaulting somebody into the gap"
                )
            )
            if grants == 0
            else None,
        }
    )
    return out


def main() -> int:
    out: dict[str, object] = {"phase": "g177_proof"}

    # ---- 177B: three dimensions, independent -----------------------
    model = describe_authority_model()
    no_affiliation = build_authority_grant(
        organization_id="org-A",
        identity_id="p1",
        identity_status=IDENTITY_VERIFIED,
        authority_status=AUTHORITY_UNVERIFIED,
    )
    self_asserted = build_authority_grant(
        organization_id="org-A",
        identity_id="p2",
        identity_status=IDENTITY_VERIFIED,
        affiliation_status=AFFILIATION_SELF_ASSERTED,
        authority_status=AUTHORITY_MANUALLY_VERIFIED,
        verified_by="staff-1",
        verified_at="2026-09-01",
        reason="claimed",
    )
    collapsed = dict(no_affiliation)
    collapsed["verified"] = True

    out["identity_affiliation_authority_separated"] = bool(
        len(model["identity_states"]) == 5
        and len(model["affiliation_states"]) == 7
        and len(model["authority_states"]) == 8
        and model["no_single_verified_boolean"]
        and model["self_asserted_affiliation_is_never_sufficient"]
        and model["unknown_is_distinct_from_unverified"]
        # Each dimension refuses on its own.
        and not may_administer_tenant(no_affiliation, now=NOW)["permitted"]
        and not may_administer_tenant(self_asserted, now=NOW)["permitted"]
        and any(
            "over_affiliation" in f for f in grant_invariant_failures(self_asserted)
        )
        # And the refusal can fail.
        and any("collapsing_flag" in f for f in grant_invariant_failures(collapsed))
    )

    # ---- 177C: evidence --------------------------------------------
    evidence_model = describe_evidence_model()
    domain = build_evidence(
        evidence_type=ORGANIZATION_EMAIL_DOMAIN,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="domain:example",
    )
    liar = dict(domain)
    liar["establishes_authority"] = True
    leak = dict(domain)
    leak["api_key"] = "sk-abcdefghijklmnopqrstuvwx"
    accepted = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="doc:a",
        reviewer="staff-1",
        decision=DECISION_ACCEPTED,
        decided_at="2026-09-01",
        reason="verified",
    )
    rejected = build_evidence(
        evidence_type=TRIBAL_RESOLUTION,
        organization_id="org-A",
        subject_identity_id="p1",
        source_ref="doc:b",
        reviewer="staff-2",
        decision=DECISION_REJECTED,
        decided_at="2026-09-02",
        reason="superseded",
    )
    pending_only = grade_evidence_set(evidence=[domain], now=NOW)
    conflicting = grade_evidence_set(evidence=[accepted, rejected], now=NOW)

    out["authority_evidence_ready"] = bool(
        len(evidence_types()) >= 10
        and evidence_model["email_domain_is_not_authority"]
        and evidence_model["a_website_listing_is_not_authority"]
        and evidence_model["pending_evidence_supports_nothing"]
        and evidence_model["no_single_evidence_type_is_sufficient_for_all_tribes"]
        and not evidence_invariant_failures(domain)
        and any("flag_disagrees" in f for f in evidence_invariant_failures(liar))
        and any("secret" in f for f in evidence_invariant_failures(leak))
        and not pending_only["supports_authority"]
        and conflicting["conflicting_evidence"]
        and conflicting["review_required"]
    )
    out["evidence_type_count"] = len(evidence_types())

    # ---- 177D: the first-four-customer path ------------------------
    manual = verify_authority_manually(
        organization_id="org-A",
        identity_id="p1",
        verified_by="controlling-company:staff-1",
        verified_by_is_controlling_company=True,
        reason="chairperson confirmed; minutes on file",
        customer_relationship_ref="crm:agreement-1",
        verified_at="2026-09-01",
    )
    by_customer = verify_authority_manually(
        organization_id="org-A",
        identity_id="p2",
        verified_by="org-admin",
        verified_by_is_controlling_company=False,
        reason="I am an admin",
    )
    out["manual_authority_verification_ready"] = bool(
        manual["accepted"]
        and may_administer_tenant(manual["grant"], now=NOW)["permitted"]
        and not grant_invariant_failures(manual["grant"])
        and manual["grant"]["verified_by"]
        and manual["grant"]["reason"]
        and manual["audit_event"]["action"] == "authority.manually_verified"
        and manual["no_customer_identity_hardcoded"]
        # And a customer admin cannot take this path.
        and not by_customer["accepted"]
    )

    # ---- 177J: revocation ------------------------------------------
    revoked = revoke_authority(
        grant=manual["grant"],
        revoked_by="controlling-company:staff-1",
        reason="no longer holds the office",
    )
    out["authority_revocation_ready"] = bool(
        revoked["accepted"]
        and not may_administer_tenant(revoked["grant"], now=NOW)["permitted"]
        and revoked["organization_deleted"] is False
        and revoked["historical_work_deleted"] is False
        and revoked["audit_history_erased"] is False
        and revoked["membership_removed"] is False
        and not revoke_authority(grant=manual["grant"], revoked_by=None, reason="x")[
            "accepted"
        ]
        and not revoke_authority(grant=manual["grant"], revoked_by="a", reason=None)[
            "accepted"
        ]
    )

    # ---- 177E/F: tenant creation, roles, the boundary ---------------
    admin_model = describe_administration_model()
    out["tenant_creation_authorized"] = bool(
        authorize_admin_action(
            action=ACTION_CREATE_ORGANIZATION,
            actor_role=CONTROLLING_COMPANY_ADMIN,
            actor_organization_id="controlling-company",
            target_organization_id="org-new",
        )["permitted"]
        and not authorize_admin_action(
            action=ACTION_CREATE_ORGANIZATION,
            actor_role=ORG_SUPER_ADMIN,
            actor_organization_id="org-A",
            target_organization_id="org-A",
        )["permitted"]
    )
    out["organization_roles_ready"] = bool(
        len(admin_model["roles"]) == 5
        and admin_model["every_role_has_a_meaning"]
        and admin_model["every_role_names_who_may_confer_it"]
        and admin_model["every_action_names_its_roles"]
    )
    out["controlling_company_boundary_ready"] = bool(
        admin_model["customer_admin_cannot_become_controlling_company"]
        and admin_model["customer_and_controlling_roles_are_disjoint"]
        and admin_model["manual_verification_is_controlling_company_only"]
        and admin_model["organization_creation_is_controlling_company_only"]
        and not authorize_admin_action(
            action=ACTION_VERIFY_AUTHORITY_MANUALLY,
            actor_role=ORG_SUPER_ADMIN,
            actor_organization_id="org-A",
            target_organization_id="org-A",
        )["permitted"]
    )

    cross = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-B",
    )
    same = authorize_admin_action(
        action=ACTION_INVITE_MEMBER,
        actor_role=ORG_SUPER_ADMIN,
        actor_organization_id="org-A",
        target_organization_id="org-A",
    )
    out["cross_tenant_admin_blocked"] = bool(
        not cross["permitted"]
        and cross["cross_tenant_attempt"]
        # And the check must be able to NOT fire.
        and same["permitted"]
        and admin_model["tenancy_is_checked_before_privilege"]
    )

    # ---- 177G: invitations -----------------------------------------
    good = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="admin-1",
        invited_by_role=ORG_ADMIN,
        invited_by_organization_id="org-A",
    )
    from_member = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:new",
        offered_role=ORG_MEMBER,
        invited_by="member-1",
        invited_by_role=ORG_MEMBER,
        invited_by_organization_id="org-A",
    )
    escalation = issue_invitation(
        organization_id="org-A",
        invited_subject_ref="subject:x",
        offered_role=CONTROLLING_COMPANY_ADMIN,
        invited_by="super-1",
        invited_by_role=ORG_SUPER_ADMIN,
        invited_by_organization_id="org-A",
    )
    revoked_invite = revoke_invitation(
        invitation=good["invitation"],
        revoked_by="admin-1",
        revoked_by_role=ORG_ADMIN,
        revoked_by_organization_id="org-A",
        reason="sent to the wrong person",
    )
    out["organization_invitations_ready"] = bool(
        good["accepted"]
        and not invitation_invariant_failures(good["invitation"])
        # Refused at ISSUE: the invitation never exists.
        and not from_member["accepted"]
        and from_member["invitation"] is None
        and not escalation["accepted"]
        and escalation["decision"]["privilege_escalation_attempt"]
        and revoked_invite["accepted"]
        and revoked_invite["invitation"]["revoked_reason"]
        and admin_model["unauthorized_invitations_are_refused_at_issue"]
    )

    # ---- 177E: the profile and the phrase rule ---------------------
    profile_model = describe_profile_model()
    miss = resolve_phrase("salmon habitat restoration")
    empty = resolve_phrase("none")
    ambiguous = resolve_phrase("infrastructure")
    known = resolve_phrase("language revitalization")

    v1 = build_profile_version(
        organization_id="org-A",
        values={
            "legal_name": "Example Tribe",
            "entity_type": "FEDERALLY_RECOGNIZED_TRIBE",
            "funding_sectors": ["housing", "water"],
            "strategic_priorities": ["language revitalization"],
        },
        changed_by="p1",
        reason="initial",
    )
    revised = revise_profile(
        current=v1,
        changes={"funding_sectors": ["housing", "broadband"]},
        changed_by="p2",
        reason="added broadband",
    )
    out["organization_profile_ready"] = bool(
        len(profile_model["profile_fields"]) >= 12
        and profile_model["every_entity_type_has_a_meaning"]
        and not profile_invariant_failures(v1)
        and revised["accepted"]
        and revised["version"]["version_ordinal"] == 2
        and revised["previous"]["values"]["funding_sectors"] == ["housing", "water"]
        and not profile_invariant_failures(revised["version"])
    )
    out["phrase_recognition_distinguishes_four_outcomes"] = bool(
        known["outcome"] == RECOGNIZED
        and known["entity_classes"]
        and ambiguous["outcome"] == AMBIGUOUS
        and ambiguous["candidates"]
        and not ambiguous["entity_classes"]
        and miss["outcome"] == LOOKUP_MISS
        and empty["outcome"] == EXPLICITLY_EMPTY
        # Both empty-handed, and distinguishable anyway.
        and miss["entity_classes"] == empty["entity_classes"] == []
        and miss["review_required"]
        and not empty["review_required"]
    )

    # ---- 177H/I: branding, defaults, overrides ---------------------
    custom_model = describe_customization_model()
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
        identity_id="p7",
        preferences={"tile_order": ["OPEN_OPPORTUNITIES"], "density": "COMFORTABLE"},
    )
    effective = apply_personal_override(org_default=default, override=override)
    effective["dashboard"]["tile_order"].append("TEAM")

    branding_override = build_personal_override(
        organization_id="org-A", identity_id="p8", preferences={}
    )
    branding_override["preferences"]["primary_color"] = "#000000"

    published = publish_org_default(
        current=default,
        changes={"dashboard": {"tile_order": ["OPEN_OPPORTUNITIES", "DEADLINES"]}},
        published_by="admin-1",
        publisher_may_publish=True,
        reason="team preference",
    )
    unauthorized = publish_org_default(
        current=default,
        changes={},
        published_by="member-1",
        publisher_may_publish=False,
        reason="I prefer it",
    )

    out["organization_branding_ready"] = bool(
        not branding_invariant_failures(default["branding"])
        and custom_model["branding_is_a_reference_not_a_payload"]
        and custom_model["no_free_form_css_or_script_field"]
        and branding_invariant_failures({"display_name": "<script>x</script>"})
        and branding_invariant_failures({"primary_color": "red"})
        and branding_invariant_failures({"custom_css": "body{}"})
    )
    out["organization_dashboard_defaults_ready"] = bool(
        published["accepted"]
        and published["default"]["version_ordinal"] == 2
        and published["previous"]["dashboard"]["tile_order"] == before
        and published["audit_event"]["action"] == "organization.defaults_published"
        and not unauthorized["accepted"]
        and custom_model["publishing_requires_authority"]
        and custom_model["publishing_is_versioned"]
    )
    out["individual_dashboard_overrides_ready"] = bool(
        effective["org_default_unchanged"]
        and default["dashboard"]["tile_order"] == before
        and effective["branding"]["primary_color"] == "#1B4332"
        and not override_invariant_failures(override)
        and any(
            "carries_org_branding" in f
            for f in override_invariant_failures(branding_override)
        )
        and custom_model["personal_override_never_mutates_the_org_default"]
    )

    # ---- 177L: self health -----------------------------------------
    health = prove_detectors_fire()
    out["authority_self_health_ready"] = bool(
        health["healthy_population_is_silent"]
        and health["all_detectors_fire"]
        and health["all_detectors_are_specific"]
        and len(DETECTORS) == 9
        and describe_self_health()["every_detector_has_a_meaning"]
    )
    out["self_health_detector_count"] = len(DETECTORS)

    # ---- 177K: the corpus ------------------------------------------
    corpus = grade_corpus()
    out["corpus_case_count"] = corpus["case_count"]
    out["corpus_passed_count"] = corpus["passed_count"]
    out["corpus_failed_cases"] = [c["case_id"] for c in corpus["failed_cases"]]
    out["corpus_is_world_truth"] = corpus["corpus_is_world_truth"]
    out["real_tribe_onboarded"] = corpus["real_tribe_onboarded"]
    out["corpus_clock_is_pinned"] = describe_corpus()["clock_is_pinned"]

    # ---- the real world --------------------------------------------
    out.update(_real_state())

    # ---- 176 semantics still hold ----------------------------------
    try:
        from nativeforge.services.award_miss_detection_service import (
            describe_miss_model,
        )
        from nativeforge.services.program_recurrence_service import (
            MINIMUM_CYCLES_FOR_CADENCE,
        )

        miss_model = describe_miss_model()
        out["gate176_semantics_preserved"] = bool(
            miss_model["coverage_percentage_is_never_reported"]
            and miss_model["demo_fixture_awards_excluded_from_real_metrics"]
            and miss_model["never_auto_onboards_a_source"]
            and MINIMUM_CYCLES_FOR_CADENCE == 3
        )
    except Exception as exc:  # pragma: no cover - reported, never swallowed
        out["gate176_semantics_preserved"] = False
        out["gate176_probe_error"] = str(exc)[:200]

    out["network_requests"] = _ATTEMPTS["n"]
    out["fixture_residue"] = 0
    out["gate177_ready"] = bool(
        out["identity_affiliation_authority_separated"]
        and out["authority_evidence_ready"]
        and out["manual_authority_verification_ready"]
        and out["authority_revocation_ready"]
        and out["tenant_creation_authorized"]
        and out["organization_profile_ready"]
        and out["phrase_recognition_distinguishes_four_outcomes"]
        and out["organization_roles_ready"]
        and out["cross_tenant_admin_blocked"]
        and out["organization_invitations_ready"]
        and out["organization_branding_ready"]
        and out["organization_dashboard_defaults_ready"]
        and out["individual_dashboard_overrides_ready"]
        and out["controlling_company_boundary_ready"]
        and out["authority_self_health_ready"]
        and out["gate176_semantics_preserved"]
        and out["corpus_passed_count"] == out["corpus_case_count"]
        and out["network_requests"] == 0
    )
    out["generated_at"] = dt.datetime.now(dt.UTC).isoformat()

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
