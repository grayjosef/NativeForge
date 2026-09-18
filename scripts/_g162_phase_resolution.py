"""Gate 162 verifier phase: every real source, and the synthetic branch.

Proves claims 1-11, 19, 21-23 and 27.

Claim 21 is the load-bearing one and it is ASSERTED, not printed: a fully
recorded synthetic fact set must reach `authorized=true`. Without it, "every
real source is refused" proves nothing - the code could refuse unconditionally
and no check could tell.

Claim 22 is its companion: that same authorized fixture must still sit at
`guard_allowed=false` with `live_fetch_not_opted_in`. Authorization complete is
not live fetch opted in.

Rows written here are removed by `_g162_phase_cleanup.py`, the LAST phase.
Nothing that writes may run after it.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

import sqlalchemy as sa  # noqa: E402
from tests import session_org_helper as soh  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_authorization_decision_repository import (  # noqa: E402,E501
    DECISIONS_TABLE,
    HUMAN_REVIEW,
    TERMS,
    record_decision,
)
from nativeforge.services.live_network_guard_service import (  # noqa: E402
    build_live_network_decision,
)
from nativeforge.services.source_allowlist_projection_service import (  # noqa: E402,E501
    allowlist_projection_invariant_failures,
    project_allowlist,
)
from nativeforge.services.source_authorization_fixture_registry_service import (  # noqa: E402,E501
    FIXTURE_ROWS,
    PERMITTABLE_FIXTURE,
    UNDECIDED_FIXTURE,
    describe_fixture_registry,
    fixture_evidence_fingerprint,
    fixture_registry_invariant_failures,
)
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorization_invariant_failures,
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    AUTHORIZED_SOURCE_IDS,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    evaluate_registry,
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
NOW = dt.datetime(2026, 9, 17, tzinfo=dt.UTC)
LATER = dt.datetime(2027, 9, 17, tzinfo=dt.UTC)
EXPIRED = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)

#: Every row this phase writes carries it, so cleanup can find them all.
ARTIFACT_ID = "nf162-verify-activation"

#: The ONLY real sources permitted to carry terms / human-review / activation
#: decisions. Gate 163 activated exactly one, signed by MAYHEM. Any other real
#: source carrying any such decision fails this verifier.
ALLOWED_REAL_DECISION_SOURCES: frozenset[str] = frozenset(
    {"nf-seed-2026-api-grants-gov-search2"}
)

#: A LITERAL, deliberately. The authoritative set lives in the code under test
#: as `source_live_warrant_service.AUTHORIZED_SOURCE_IDS`; deriving this from
#: it would make the check follow the code, so adding a source there would
#: silently widen what this verifier permits. Pinned here and cross-checked
#: against the code, so drift in either direction fails.

out: dict[str, object] = {}
detail: list[str] = []

ACTIVE_SOURCES = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_id", sa.Text()),
    sa.Column("source_name", sa.Text()),
    sa.Column("source_type", sa.Text()),
    sa.Column("source_lane", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("update_frequency", sa.Text()),
    sa.Column("source_health_status", sa.Text()),
    sa.Column("activation_approved_by", sa.Text()),
    sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
    sa.Column("activation_approval_artifact_id", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

session = SessionLocal()

try:
    soh.ensure_org(DEMO, "demo")
    shipped = load_registry_rows()
    real_ids = sorted(shipped)

    def authorize(source_id: str) -> dict:
        result = authorize_source_for_live_access(
            connection=session,
            organization_id=DEMO,
            source_id=source_id,
            now=NOW,
        )
        detail.extend(authorization_invariant_failures(result))
        return result

    def decide(source_id: str, kind: str, **kw) -> dict:
        base = {
            "connection": session,
            "organization_id": DEMO,
            "source_id": source_id,
            "decision_kind": kind,
            "fact_status": "synthetic_fixture",
            "now": NOW,
        }
        base.update(kw)
        return record_decision(**base)

    # ---- 1. every real source resolves ------------------------------
    resolved_ok = 0
    approved_real = []
    for source_id in real_ids:
        result = authorize(source_id)
        if result.get("authorization_status"):
            resolved_ok += 1
        if result.get("authorized"):
            approved_real.append(source_id)
    out["every_real_source_resolves"] = bool(resolved_ok == len(real_ids))
    out["real_sources_resolved"] = resolved_ok
    out["real_sources_in_registry"] = len(real_ids)

    # ---- 2/23. real approved count is zero --------------------------
    out["real_approved_count_is_zero"] = not approved_real
    if approved_real:
        detail.append(f"real sources authorized: {approved_real[:5]}")

    # ---- 3/4. the registry's own blocked counts are preserved -------
    evaluated = evaluate_registry()
    out["terms_blocked_count"] = int(evaluated.get("terms_blocked_count") or 0)
    out["human_review_blocked_count"] = int(
        evaluated.get("human_review_blocked_count") or 0
    )
    out["registry_activation_approved_count_is_zero"] = bool(
        int(evaluated.get("activation_approved_count") or 0) == 0
    )
    out["registry_monitorable_count_is_zero"] = bool(
        int(evaluated.get("monitorable_count") or 0) == 0
    )

    # ---- 5-11. each blocking shape, on the UNDECIDED fixture --------
    #
    # A fixture, so no real source ever receives a decision. Each case records
    # one decision shape and checks the fact the resolver derives from it.
    def fact_status(source_id: str, name: str) -> str:
        result = authorize(source_id)
        return (
            (result.get("resolution") or {})
            .get("resolved_facts", {})
            .get(name, {})
            .get("fact_status")
        )

    fingerprint = fixture_evidence_fingerprint(UNDECIDED_FIXTURE) or ("d" * 64)

    # ---- establish "missing", do not inherit it ----------------------
    #
    # `missing_terms_blocks` asserts the resolver refuses a MISSING terms
    # fact. Nothing here made it missing. This phase writes a terms decision
    # for this same fixture forty lines down, and `record_decision` upserts,
    # so the fact was missing only when some EARLIER run had deleted it - and
    # that deletion lives in the cleanup phase, which runs last.
    #
    # The check therefore passed after a clean run and failed after a crashed
    # one. A green check with two possible causes has only been half-tested,
    # so the precondition is established here and confirmed.
    #
    # PINNED to the two named fixture constants. Not the reserved prefix, not
    # registry ordering, not `sorted(shipped)[0]`, and nothing that
    # ALLOWED_REAL_DECISION_SOURCES can move: those two ids are what this
    # phase writes and they are the only ids it may clear.
    PINNED_FIXTURES = (UNDECIDED_FIXTURE, PERMITTABLE_FIXTURE)
    out["pinned_fixture_subjects"] = list(PINNED_FIXTURES)
    out["the_fixture_subjects_are_reserved_ids"] = all(
        str(fixture).startswith("nf162.fixture.") for fixture in PINNED_FIXTURES
    )

    def real_decision_count() -> int:
        return int(
            session.execute(
                sa.select(sa.func.count())
                .select_from(DECISIONS_TABLE)
                .where(
                    DECISIONS_TABLE.c.organization_id == DEMO,
                    DECISIONS_TABLE.c.source_id.in_(
                        sorted(ALLOWED_REAL_DECISION_SOURCES)
                    ),
                )
            ).scalar_one()
            or 0
        )

    # Counted before, counted after. The delete below must be provably
    # incapable of reaching the one real source that carries decisions.
    real_decisions_before = real_decision_count()

    def real_activation_count() -> int:
        return int(
            session.execute(
                sa.select(sa.func.count())
                .select_from(ACTIVE_SOURCES)
                .where(
                    ACTIVE_SOURCES.c.organization_id == DEMO,
                    ACTIVE_SOURCES.c.source_id.in_(
                        sorted(ALLOWED_REAL_DECISION_SOURCES)
                    ),
                )
            ).scalar_one()
            or 0
        )

    real_activations_before = real_activation_count()

    session.execute(
        sa.delete(DECISIONS_TABLE).where(
            DECISIONS_TABLE.c.organization_id == DEMO,
            DECISIONS_TABLE.c.source_id.in_(PINNED_FIXTURES),
        )
    )

    # The activation row has the same defect. This phase INSERTs it below and
    # the unique key is the legacy display-name tuple, so a row surviving any
    # earlier run collides and kills the phase at
    # `synthetic_branch_reaches_authorized` - which then reads as "the
    # permitted branch is unreachable" when the cause is residue.
    #
    # Pinned three ways over: a named fixture id, or a row carrying THIS
    # phase's own artifact tag, and in either case of fixture type. The real
    # Grants.gov activation row carries a different artifact id, is not a
    # fixture type and is not a pinned id.
    session.execute(
        sa.delete(ACTIVE_SOURCES).where(
            ACTIVE_SOURCES.c.organization_id == DEMO,
            ACTIVE_SOURCES.c.source_type == "fixture",
            sa.or_(
                ACTIVE_SOURCES.c.source_id.in_(PINNED_FIXTURES),
                ACTIVE_SOURCES.c.activation_approval_artifact_id == ARTIFACT_ID,
            ),
        )
    )
    session.commit()

    residue = int(
        session.execute(
            sa.select(sa.func.count())
            .select_from(DECISIONS_TABLE)
            .where(
                DECISIONS_TABLE.c.organization_id == DEMO,
                DECISIONS_TABLE.c.source_id.in_(PINNED_FIXTURES),
            )
        ).scalar_one()
        or 0
    )
    out["the_fixtures_start_with_no_decisions"] = bool(residue == 0)
    if residue:
        detail.append(f"fixture decision residue survived the reset: {residue}")

    out["clearing_the_fixtures_left_the_real_decisions_alone"] = bool(
        real_decision_count() == real_decisions_before
    )
    out["real_source_decisions_preserved"] = real_decisions_before

    out["the_code_authorizes_exactly_the_pinned_set"] = bool(
        frozenset(AUTHORIZED_SOURCE_IDS) == ALLOWED_REAL_DECISION_SOURCES
    )
    if frozenset(AUTHORIZED_SOURCE_IDS) != ALLOWED_REAL_DECISION_SOURCES:
        detail.append(
            "the code's AUTHORIZED_SOURCE_IDS drifted from the pinned set: "
            f"{sorted(AUTHORIZED_SOURCE_IDS)}"
        )

    # "The delete was narrow" is a claim. This is the measurement.
    out["clearing_the_fixtures_left_the_real_activation_alone"] = bool(
        real_activation_count() == real_activations_before
    )
    out["real_source_activations_preserved"] = real_activations_before

    fixture_activations = int(
        session.execute(
            sa.select(sa.func.count())
            .select_from(ACTIVE_SOURCES)
            .where(
                ACTIVE_SOURCES.c.organization_id == DEMO,
                ACTIVE_SOURCES.c.source_id.in_(PINNED_FIXTURES),
            )
        ).scalar_one()
        or 0
    )
    out["the_fixtures_start_with_no_activation"] = bool(fixture_activations == 0)
    if fixture_activations:
        detail.append(
            f"fixture activation residue survived the reset: {fixture_activations}"
        )

    out["missing_terms_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "terms_status") == "missing"
    )
    out["missing_human_review_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "human_review_status") == "missing"
    )
    out["missing_activation_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "activation_status") == "missing"
    )

    decide(
        UNDECIDED_FIXTURE,
        TERMS,
        decision="denied",
        guard_status="TERMS_REVIEW_REQUIRED",
        reviewed_by="reviewer:nf162-verify",
        reviewed_at=NOW,
    )
    denied = authorize(UNDECIDED_FIXTURE)
    out["terms_denial_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "terms_status") == "denied"
        and not denied["authorized"]
    )
    out["a_denial_is_reported_as_a_decision"] = bool(
        denied["denial_is_a_decision"] and denied["authorization_status"] == "denied"
    )

    decide(
        UNDECIDED_FIXTURE,
        TERMS,
        decision="needs_review",
        guard_status="TERMS_REVIEW_REQUIRED",
    )
    out["needs_review_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "terms_status") == "needs_review"
        and not authorize(UNDECIDED_FIXTURE)["authorized"]
    )

    decide(
        UNDECIDED_FIXTURE,
        HUMAN_REVIEW,
        decision="denied",
        guard_status="NOT_APPLICABLE",
        reviewed_by="reviewer:nf162-verify",
        reviewed_at=NOW,
    )
    out["human_denial_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "human_review_status") == "denied"
        and not authorize(UNDECIDED_FIXTURE)["authorized"]
    )

    # An expired affirmative answer is stale, not permitting.
    decide(
        UNDECIDED_FIXTURE,
        TERMS,
        decision="approved",
        guard_status="NO_REVIEW_REQUIRED",
        reviewed_by="reviewer:nf162-verify",
        reviewed_at=EXPIRED,
        evidence_fingerprint=fingerprint,
        expires_at=EXPIRED,
    )
    out["stale_terms_blocks"] = bool(
        fact_status(UNDECIDED_FIXTURE, "terms_status") == "stale"
        and not authorize(UNDECIDED_FIXTURE)["authorized"]
    )

    # An unsigned approval cannot even be written.
    unsigned = decide(
        UNDECIDED_FIXTURE,
        TERMS,
        decision="approved",
        guard_status="NO_REVIEW_REQUIRED",
        evidence_fingerprint=fingerprint,
    )
    out["an_unsigned_approval_is_refused"] = bool(not unsigned["recorded"])

    # ---- 21. the synthetic branch MUST reach approved ---------------
    for kind, guard in (
        (TERMS, "NO_REVIEW_REQUIRED"),
        (HUMAN_REVIEW, "NOT_APPLICABLE"),
    ):
        decide(
            PERMITTABLE_FIXTURE,
            kind,
            decision="approved",
            guard_status=guard,
            reviewed_by="reviewer:nf162-verify",
            reviewed_at=NOW,
            review_authority="nf162_verifier",
            evidence_fingerprint=fixture_evidence_fingerprint(PERMITTABLE_FIXTURE),
            expires_at=LATER,
        )
    row = FIXTURE_ROWS[PERMITTABLE_FIXTURE]
    session.execute(
        sa.insert(ACTIVE_SOURCES).values(
            id=uuid.uuid4(),
            organization_id=DEMO,
            # Gate 163A: the stable key. Without it the resolver falls through
            # to the legacy source_name join and trips
            # `a_permitting_fact_joined_on_a_display_name`, which stays strict.
            source_id=PERMITTABLE_FIXTURE,
            source_name=row["source_name"],
            source_type="fixture",
            source_lane="fixture",
            source_url_or_search_target=row["source_url"],
            collection_method="hermetic_fixture",
            update_frequency="manual",
            source_health_status="healthy",
            activation_approved_by="operator:nf162-verify",
            activation_approved_at=NOW,
            activation_approval_artifact_id=ARTIFACT_ID,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    permitted = authorize(PERMITTABLE_FIXTURE)
    facts = (permitted.get("resolution") or {}).get("resolved_facts") or {}
    recorded = [name for name, f in facts.items() if f.get("fact_status") == "recorded"]

    out["synthetic_branch_reaches_authorized"] = bool(permitted["authorized"])
    out["synthetic_branch_status_is_approved"] = bool(
        permitted["authorization_status"] == "approved"
    )
    out["synthetic_recorded_fact_count"] = len(recorded)
    out["synthetic_all_eleven_facts_recorded"] = bool(len(recorded) == 11)
    if not permitted["authorized"]:
        detail.append(f"synthetic branch UNREACHABLE: {permitted['refusal_reasons']}")

    # ---- 22. and it still does not opt into a live fetch ------------
    guard_blockers = (permitted.get("guard_decision") or {}).get(
        "blocked_reasons"
    ) or []
    out["synthetic_authorization_does_not_opt_into_live_fetch"] = bool(
        not permitted["guard_allowed"] and "live_fetch_not_opted_in" in guard_blockers
    )
    out["synthetic_authorization_permits_no_live_transport"] = bool(
        not permitted["live_transport_permitted"]
    )

    # ---- 19. forged caller booleans change nothing ------------------
    forged = build_live_network_decision(
        purpose="source_collection",
        target_url=shipped[real_ids[0]]["source_url"],
        caller="an_attacker",
        source_id=real_ids[0],
        method="GET",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        activation_status="activation_allowed",
        collector_status="active",
        robots_status="allowed",
        credential_status="not_required",
        rate_limit_status="policy_declared",
        user_agent_status="canonical",
        attribution_status="not_required",
    )
    after_forgery = authorize(real_ids[0])
    out["the_low_level_guard_is_a_pure_function"] = bool(forged.get("allowed"))
    out["forged_booleans_do_not_change_authorization"] = bool(
        not after_forgery["authorized"]
    )

    # ---- the allowlist projection ----------------------------------
    projection = project_allowlist(connection=session, organization_id=DEMO, now=NOW)
    detail.extend(allowlist_projection_invariant_failures(projection))
    out["allowlist_evaluated"] = int(projection["evaluated"])
    out["allowlisted_real_sources_is_zero"] = bool(
        int(projection["real_sources_allowlisted"]) == 0
    )
    out["allowlisted_synthetic_fixtures"] = int(
        projection["synthetic_fixtures_allowlisted"]
    )
    out["exactly_one_synthetic_fixture_is_allowlisted"] = bool(
        int(projection["synthetic_fixtures_allowlisted"]) == 1
    )

    # ---- 27. no UNAPPROVED real source received a decision -----------
    #
    # Gate 162 proved zero real decisions, which was the right property while
    # no source could be activated. Gate 163 deliberately gave exactly one
    # real source signed decisions, so the assertion narrows rather than
    # disappears: any real source outside the allowed set still fails.
    rows = session.execute(
        sa.select(
            DECISIONS_TABLE.c.source_id,
            DECISIONS_TABLE.c.reviewed_by,
            DECISIONS_TABLE.c.reviewed_at,
        ).where(DECISIONS_TABLE.c.organization_id == DEMO)
    ).all()
    real_with_decisions = {r[0] for r in rows} & set(real_ids)
    unapproved = sorted(real_with_decisions - ALLOWED_REAL_DECISION_SOURCES)
    out["no_unapproved_real_source_received_a_decision"] = not unapproved
    if unapproved:
        detail.append(f"UNAPPROVED real sources with decisions: {unapproved}")

    # And the allowed one's decisions must be signed and attributable, or the
    # exception is a hole rather than a permission.
    allowed_rows = [r for r in rows if r[0] in ALLOWED_REAL_DECISION_SOURCES]
    out["the_allowed_real_source_decisions_are_signed"] = bool(
        allowed_rows and all(r[1] and r[2] for r in allowed_rows)
    )
    if allowed_rows and not all(r[1] and r[2] for r in allowed_rows):
        detail.append("an allowed real-source decision is unsigned")

    # ---- the fixture registry stays reserved -----------------------
    described = describe_fixture_registry(shipped)
    detail.extend(fixture_registry_invariant_failures(described))
    out["fixture_prefix_is_reserved"] = bool(described["prefix_is_reserved"])
    out["no_fixture_shadows_a_real_source"] = bool(
        described["no_fixture_shadows_a_real_source"]
    )

    session.commit()
except Exception as exc:  # noqa: BLE001 - the phase reports rather than raises
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
    session.rollback()
finally:
    session.close()

for key in (
    "every_real_source_resolves",
    "real_approved_count_is_zero",
    "registry_activation_approved_count_is_zero",
    "registry_monitorable_count_is_zero",
    "the_fixture_subjects_are_reserved_ids",
    "the_fixtures_start_with_no_decisions",
    "the_fixtures_start_with_no_activation",
    "the_code_authorizes_exactly_the_pinned_set",
    "clearing_the_fixtures_left_the_real_decisions_alone",
    "clearing_the_fixtures_left_the_real_activation_alone",
    "missing_terms_blocks",
    "missing_human_review_blocks",
    "missing_activation_blocks",
    "terms_denial_blocks",
    "a_denial_is_reported_as_a_decision",
    "needs_review_blocks",
    "human_denial_blocks",
    "stale_terms_blocks",
    "an_unsigned_approval_is_refused",
    "synthetic_branch_reaches_authorized",
    "synthetic_branch_status_is_approved",
    "synthetic_all_eleven_facts_recorded",
    "synthetic_authorization_does_not_opt_into_live_fetch",
    "synthetic_authorization_permits_no_live_transport",
    "the_low_level_guard_is_a_pure_function",
    "forged_booleans_do_not_change_authorization",
    "allowlisted_real_sources_is_zero",
    "exactly_one_synthetic_fixture_is_allowlisted",
    "no_unapproved_real_source_received_a_decision",
    "the_allowed_real_source_decisions_are_signed",
    "fixture_prefix_is_reserved",
    "no_fixture_shadows_a_real_source",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
