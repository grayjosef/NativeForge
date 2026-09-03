"""Gate 138: persistence measured by a round trip, in controlled dev/demo.

Gate 138A found `customer_persistence_live` false for one reason across every
lane that could otherwise work:

```text
no_customer_auth_so_nobody_owns_the_row
```

That blocker reaches for *somebody is accountable for this row*, and the fact
is already true — an identity resolves to an organization through a membership
row, a session was validated, the role comes from `nf_org_memberships`. The
repositories underneath already draw the line in the right place:
`production_write = not demo_fixture`, and only a production write needs
`customer_auth_live`.

So a fixture-labelled write into a demo organization can be proved today, and
everything below is about whether it can be proved *wrongly*.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import award_document_store_repository_service as docs
from nativeforge.services import award_requirement_proof_audit_repository_service as prf
from nativeforge.services import award_requirements_repository_service as reqs
from nativeforge.services import awarded_grants_repository_service as awards
from nativeforge.services import customer_persistence_artifact_gate138_service as art
from nativeforge.services import tenant_profile_repository_service as profiles
from nativeforge.services.customer_auth_activation_gate_service import (
    activation_gate_invariant_failures,
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_persistence_activation_service import (
    CONTROLLED_SCOPE,
    FIXTURE_FACT_STATUS,
    FORBIDDEN_AUTHORITY_KEYS,
    LANE_ROUTES,
    LANES,
    NOT_DEMO,
    build_accountable_principal_evidence,
    persistence_activation_invariant_failures,
    prove_customer_persistence,
    resolve_accountable_identity,
)
from nativeforge.services.customer_persistence_capability_service import (
    build_capability_matrix,
    capability_matrix_invariant_failures,
)
from nativeforge.services.org_scoped_customer_persistence_guard_service import (
    evaluate_persistence_write,
)
from nativeforge.services.verified_operational_binding_activation_boundary_service import (  # noqa: E501
    DEMO_ORGANIZATION_ID,
    REAL_ORGANIZATION_ID,
)

DEMO = DEMO_ORGANIZATION_ID
REAL = REAL_ORGANIZATION_ID
OTHER = "cccccccc-dddd-eeee-ffff-00000000d138"
IDENTITY = "dddddddd-eeee-ffff-0000-111111111138"
NOW = datetime(2026, 9, 2, tzinfo=UTC)

BINDING = {
    "org_binding_passed": True,
    "callback_session_validated": True,
    "identity_rows": 1,
    "active_membership_rows": 1,
}
ROLES = {
    "role_mapping_passed": True,
    "role_mapping_source": "nf_org_memberships",
    "cookie_claim_can_override_membership": False,
    "email_domain_can_map_a_role": False,
}

ORGANIZATIONS = sa.Table(
    "organizations",
    sa.MetaData(),
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


@pytest.fixture
def persistence_db():
    """Five lane tables and three organizations. Never the dev database."""
    engine = sa.create_engine("sqlite://")
    ORGANIZATIONS.create(engine)
    for module in (profiles, awards, reqs, prf, docs):
        for attribute in dir(module):
            candidate = getattr(module, attribute)
            if isinstance(candidate, sa.Table):
                candidate.create(engine, checkfirst=True)
    with engine.begin() as conn:
        for organization_id, org_type in (
            (DEMO, "demo"),
            (REAL, "real"),
            (OTHER, "real"),
        ):
            conn.execute(
                sa.insert(ORGANIZATIONS).values(
                    id=uuid.UUID(organization_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=NOW,
                )
            )
        yield conn
    engine.dispose()


def _prove(conn, organization_id=DEMO, *, seed="t", **overrides):
    fields = {
        "connection": conn,
        "organization_id": organization_id,
        "other_organization_id": OTHER,
        "identity_id": IDENTITY,
        "now": NOW,
        "seed": seed,
        "binding_evidence": BINDING,
        "role_mapping_evidence": ROLES,
    }
    fields.update(overrides)
    return prove_customer_persistence(**fields)


# ---------------------------------------------------------------------------
# the round trip
# ---------------------------------------------------------------------------


def test_persistence_live_is_measured_from_a_real_round_trip(persistence_db):
    """Not from five import checks and a boolean."""
    result = _prove(persistence_db, seed="round-trip")
    assert result["customer_persistence_live"] is True
    assert result["scope"] == CONTROLLED_SCOPE
    assert result["rows_written"] == len(LANES)
    assert result["rows_archived"] == len(LANES)
    assert result["rows_left_live"] == 0
    assert result["cross_org_rows_read"] == 0
    assert persistence_activation_invariant_failures(result) == []


@pytest.mark.parametrize("lane", LANES)
def test_every_lane_completes_all_four_steps(persistence_db, lane):
    result = _prove(persistence_db, seed=f"lane-{lane}", lanes=(lane,))
    row = result["lane_results"][0]
    assert row["lane"] == lane
    assert row["steps"] == {
        "write": True,
        "read": True,
        "cross_org_refused": True,
        "cleanup": True,
    }, row["blocked_reasons"]
    assert row["round_trip_proved"] is True
    assert row["this_row_read_back_by_id"] is True


def test_the_written_row_is_read_back_by_id_not_merely_counted(persistence_db):
    """A count is not a proof that THIS row round-tripped.

    The first version asserted `rows_read >= 1`. Against a database carrying
    archived rows from earlier runs it read 15 for five writes and passed - so
    it proved the table had rows, not that the write did anything.
    """
    result = _prove(persistence_db, seed="by-id")
    for lane in result["lane_results"]:
        assert lane["this_row_read_back_by_id"] is True, lane["lane"]


def test_the_read_happens_before_the_cleanup(persistence_db):
    """Ordering, found by the invariant when it did not.

    Three lanes read `include_archived=False` by default, so asking after the
    archive found nothing and the step failed for rows that had round-tripped
    perfectly well.
    """
    result = _prove(persistence_db, seed="order")
    assert result["customer_persistence_live"] is True
    assert all(lane["steps"]["read"] for lane in result["lane_results"])
    assert all(lane["steps"]["cleanup"] for lane in result["lane_results"])


def test_scaffolding_rows_are_cleaned_up_too(persistence_db):
    """Four lanes hang off an award they write themselves.

    The first version archived only the lane's own row, and a live-database
    count found three awards and two requirements left behind.
    """
    result = _prove(persistence_db, seed="scaffold")
    assert result["scaffold_rows_written"] > 0
    assert result["scaffold_rows_archived"] == result["scaffold_rows_written"]
    assert result["rows_left_live"] == 0

    for table in (
        "nf_tenant_beta_profiles",
        "nf_awarded_grants",
        "nf_award_requirements",
        "nf_award_requirement_proof_events",
        "nf_award_documents",
    ):
        live = persistence_db.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE archived_at IS NULL")
        ).scalar_one()
        assert live == 0, table


def test_rows_left_live_fails_an_invariant():
    """Per-row, not per-total. Five leftovers used to sum to "some archived"."""
    forged = {
        "customer_persistence_live": True,
        "scope": CONTROLLED_SCOPE,
        "organization_is_demo": True,
        "accountable_principal_available": True,
        "lanes_round_trip_proved": ["awarded_grants_persistence"],
        "rows_written": 5,
        "rows_read": 5,
        "rows_archived": 2,
        "rows_left_live": 3,
        "fact_status_written": FIXTURE_FACT_STATUS,
        "blocked_reasons": [],
        "lane_results": [{"this_row_read_back_by_id": True}],
    }
    fails = persistence_activation_invariant_failures(forged)
    assert "rows_left_live_after_the_proof:3" in fails


# ---------------------------------------------------------------------------
# what it refuses
# ---------------------------------------------------------------------------


def test_the_real_org_is_refused(persistence_db):
    result = _prove(persistence_db, REAL, seed="real")
    assert result["customer_persistence_live"] is False
    assert result["rows_written"] == 0
    assert (
        "organization_is_the_explicitly_refused_real_org" in result["blocked_reasons"]
    )
    assert NOT_DEMO in result["blocked_reasons"]
    assert persistence_activation_invariant_failures(result) == []


def test_a_non_demo_organization_is_refused(persistence_db):
    """Controlled dev/demo means demo, derived from organizations.org_type."""
    result = _prove(persistence_db, OTHER, seed="other")
    assert result["customer_persistence_live"] is False
    assert result["organization_is_demo"] is False
    assert NOT_DEMO in result["blocked_reasons"]
    assert result["rows_written"] == 0


def test_persistence_is_refused_without_an_accountable_principal(persistence_db):
    result = _prove(
        persistence_db,
        seed="no-principal",
        binding_evidence={},
        role_mapping_evidence={},
    )
    assert result["customer_persistence_live"] is False
    assert result["rows_written"] == 0
    assert (
        "no_accountable_principal_resolves_to_this_organization"
        in result["blocked_reasons"]
    )


def test_a_cookie_claim_overriding_a_membership_breaks_accountability():
    """Gate 133's refusals, restated as requirements rather than assumed."""
    evidence = build_accountable_principal_evidence(
        binding_evidence=BINDING,
        role_mapping_evidence={**ROLES, "cookie_claim_can_override_membership": True},
    )
    assert evidence["accountable_principal_available"] is False
    assert "a_cookie_claim_can_override_a_membership_row" in evidence["blocked_reasons"]


def test_an_email_domain_mapping_a_role_breaks_accountability():
    evidence = build_accountable_principal_evidence(
        binding_evidence=BINDING,
        role_mapping_evidence={**ROLES, "email_domain_can_map_a_role": True},
    )
    assert evidence["accountable_principal_available"] is False
    assert "an_email_domain_can_map_a_role" in evidence["blocked_reasons"]


def test_accountability_is_not_customer_auth_live():
    """Named, so the narrower claim cannot be read as the broader one."""
    evidence = build_accountable_principal_evidence(
        binding_evidence=BINDING, role_mapping_evidence=ROLES
    )
    assert evidence["accountable_principal_available"] is True
    assert evidence["customer_auth_live"] is False
    assert evidence["is_not_customer_auth_live"] is True


@pytest.mark.parametrize("key", FORBIDDEN_AUTHORITY_KEYS)
def test_no_label_can_authorize_persistence(persistence_db, key):
    result = _prove(persistence_db, seed=f"label-{key}", **{key: "a-label"})
    assert result["customer_persistence_live"] is False
    assert result["rows_written"] == 0
    assert f"not_an_authority_for_persistence:{key}" in result["blocked_reasons"]


def test_organization_id_is_the_only_authority(persistence_db):
    result = _prove(persistence_db, organization_id=None, seed="no-anchor")
    assert result["customer_persistence_live"] is False
    assert "persistence_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_a_cross_org_read_returning_rows_fails_an_invariant():
    forged = {
        "customer_persistence_live": True,
        "scope": CONTROLLED_SCOPE,
        "organization_is_demo": True,
        "accountable_principal_available": True,
        "lanes_round_trip_proved": ["awarded_grants_persistence"],
        "rows_written": 1,
        "rows_read": 1,
        "rows_archived": 1,
        "rows_left_live": 0,
        "cross_org_rows_read": 1,
        "fact_status_written": FIXTURE_FACT_STATUS,
        "blocked_reasons": [],
        "lane_results": [{"this_row_read_back_by_id": True}],
    }
    assert "a_cross_organization_read_returned_rows" in (
        persistence_activation_invariant_failures(forged)
    )


# ---------------------------------------------------------------------------
# the identity a row is attributed to
# ---------------------------------------------------------------------------


def test_the_accountable_identity_is_read_from_the_membership_row(persistence_db):
    """Derived, not supplied. Found by a live foreign key refusing a synthetic id."""
    memberships = sa.Table(
        "nf_org_memberships",
        sa.MetaData(),
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("identity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    memberships.create(persistence_db.engine, checkfirst=True)
    owner = uuid.uuid4()
    persistence_db.execute(
        sa.insert(memberships).values(
            id=uuid.uuid4(),
            organization_id=uuid.UUID(DEMO),
            identity_id=owner,
            state="active",
            role="org_owner",
            revoked_at=None,
            created_at=NOW,
        )
    )
    resolved = resolve_accountable_identity(
        connection=persistence_db, organization_id=DEMO
    )
    assert resolved == str(owner)


def test_persistence_is_refused_with_nobody_to_attribute_rows_to(persistence_db):
    """No memberships table at all: the honest answer is a refusal."""
    result = prove_customer_persistence(
        connection=persistence_db,
        organization_id=DEMO,
        other_organization_id=OTHER,
        now=NOW,
        seed="no-identity",
        binding_evidence=BINDING,
        role_mapping_evidence=ROLES,
    )
    assert result["customer_persistence_live"] is False
    assert result["rows_written"] == 0
    assert (
        "no_active_membership_identity_to_attribute_the_row_to"
        in result["blocked_reasons"]
    )


# ---------------------------------------------------------------------------
# what it never claims
# ---------------------------------------------------------------------------


def test_no_object_store_is_contacted_and_no_body_is_written(persistence_db):
    result = _prove(persistence_db, seed="no-store")
    assert result["object_store_contacted"] is False
    assert result["object_store_configured"] is False
    assert result["document_bodies_written"] == 0
    for lane in result["lane_results"]:
        assert lane["object_store_contacted"] is False
        assert lane["document_body_written"] is False


def test_production_persistence_stays_false(persistence_db):
    result = _prove(persistence_db, seed="not-production")
    assert result["customer_persistence_live"] is True
    assert result["production_persistence_ready"] is False
    assert result["production_rows_written"] == 0
    assert result["customer_auth_live"] is False


def test_the_proof_never_claims_real_customer_data(persistence_db):
    result = _prove(persistence_db, seed="no-customer-data")
    assert result["real_customer_data_written"] is False
    assert result["real_organization_touched"] is False
    assert result["live_grant_sources_called"] is False
    assert result["collectors_activated"] is False
    assert result["email_sent"] is False
    assert result["fact_status_written"] == FIXTURE_FACT_STATUS


def test_every_written_row_is_fixture_labelled(persistence_db):
    _prove(persistence_db, seed="labelled", lanes=("awarded_grants_persistence",))
    rows = (
        persistence_db.execute(
            sa.text("SELECT fact_status, is_demo FROM nf_awarded_grants")
        )
        .mappings()
        .all()
    )
    assert rows
    for row in rows:
        assert row["fact_status"] == FIXTURE_FACT_STATUS
        assert bool(row["is_demo"]) is True


def test_a_claimed_production_write_fails_an_invariant():
    forged = {
        "customer_persistence_live": True,
        "scope": CONTROLLED_SCOPE,
        "organization_is_demo": True,
        "accountable_principal_available": True,
        "lanes_round_trip_proved": ["awarded_grants_persistence"],
        "rows_written": 1,
        "rows_read": 1,
        "rows_archived": 1,
        "rows_left_live": 0,
        "fact_status_written": FIXTURE_FACT_STATUS,
        "production_persistence_ready": True,
        "object_store_contacted": True,
        "blocked_reasons": [],
        "lane_results": [{"this_row_read_back_by_id": True}],
    }
    fails = persistence_activation_invariant_failures(forged)
    assert "claimed:production_persistence_ready" in fails
    assert "claimed:object_store_contacted" in fails


# ---------------------------------------------------------------------------
# route level
# ---------------------------------------------------------------------------


def test_the_route_wired_lane_is_reported_separately(persistence_db):
    result = _prove(persistence_db, seed="routes")
    assert result["route_persistence_live_lanes"] == ["tenant_profile_persistence"]
    assert len(result["route_missing_lanes"]) == 4
    assert set(result["route_missing_lanes"]) | set(
        result["route_persistence_live_lanes"]
    ) == set(LANES)


def test_route_missing_lanes_are_not_faked():
    """Four lanes have no routes, and the map says so rather than implying one."""
    assert LANE_ROUTES["tenant_profile_persistence"] == "api/tribal_profile_routes.py"
    for lane in (
        "awarded_grants_persistence",
        "award_requirements_persistence",
        "proof_audit_persistence",
        "document_library_persistence",
    ):
        assert LANE_ROUTES[lane] is None


def test_the_route_module_exists_and_uses_the_session_org_context():
    source = Path("src/nativeforge/api/tribal_profile_routes.py").read_text(
        encoding="utf-8"
    )
    assert "require_demo_org_session" in source
    assert "require_real_org_session" in source
    # The path organization must match the session organization.
    assert "_same_org(org_id, ctx)" in source
    # And nothing reads the dev header.
    assert "X-NF-Org-Id" not in source
    assert "get_org_context_with_db" not in source


# ---------------------------------------------------------------------------
# the guard and the capability matrix
# ---------------------------------------------------------------------------


def test_the_guard_reports_which_kind_of_write_it_judged():
    result = evaluate_persistence_write(
        controlled_dev_fixture_write=True,
        operation="create_awarded_grant",
        organization_id=DEMO,
        auth_principal_status="authenticated_demo",
        is_demo_fixture=True,
    )
    assert result["controlled_dev_fixture_write"] is True


def test_the_guard_still_refuses_a_label_as_the_anchor():
    result = evaluate_persistence_write(
        controlled_dev_fixture_write=True,
        operation="create_awarded_grant",
        organization_id=None,
        tenant_id="a-tenant",
        auth_principal_status="authenticated_demo",
        is_demo_fixture=True,
    )
    assert result["write_allowed"] is False
    assert result["blocked_reasons"]


def test_the_capability_matrix_separates_production_from_controlled_dev():
    matrix = build_capability_matrix()
    # Production persistence is unchanged and still false.
    assert matrix["customer_persistence_live"] is False
    assert matrix["production_persistence_ready"] is False
    # And seven lanes are available for a controlled dev/demo fixture write.
    # Six at Gate 138; Gate 140B built `nf_source_watchlist_entries` and 140D
    # the service that writes it, which is the seventh.
    assert matrix["controlled_dev_persistence_available_count"] == 7
    assert capability_matrix_invariant_failures(matrix) == []


def test_the_capability_matrix_still_writes_nothing():
    matrix = build_capability_matrix()
    assert matrix["rows_written"] == 0
    assert matrix["persisted"] is False


def test_a_lane_with_no_table_is_available_for_neither():
    matrix = build_capability_matrix()
    absent = {
        row["capability"] for row in matrix["rows"] if not row["schema_available"]
    }
    # `source_watchlist_persistence` left this set in Gate 140: 140B built the
    # table and 140D the repository. `tenant_digest_persistence` stays, because
    # Gate 140 makes a digest PREVIEWABLE and does not persist one - there is
    # still no `nf_tenant_digest_records`.
    assert absent == {
        "tenant_digest_persistence",
        "beta_onboarding_persistence",
    }
    for row in matrix["rows"]:
        if row["capability"] in absent:
            assert row["controlled_dev_persistence_available"] is False
            assert row["production_operational"] is False


# ---------------------------------------------------------------------------
# the activation gate
# ---------------------------------------------------------------------------


def test_customer_auth_live_is_not_silently_made_true(persistence_db):
    proof = _prove(persistence_db, seed="gate")
    gate = build_customer_auth_activation_gate(persistence_proof=proof)
    assert gate["customer_persistence_live"] is True
    assert gate["customer_auth_live"] is False
    assert activation_gate_invariant_failures(gate) == []


def test_persistence_live_requires_the_controlled_scope():
    gate = dict(
        build_customer_auth_activation_gate(
            persistence_proof={
                "customer_persistence_live": True,
                "scope": CONTROLLED_SCOPE,
                "repository_persistence_live_lanes": ["awarded_grants_persistence"],
            }
        )
    )
    assert gate["customer_persistence_scope"] == CONTROLLED_SCOPE
    gate["customer_persistence_scope"] = "production"
    assert any(
        "outside_the_controlled_scope" in fail
        for fail in activation_gate_invariant_failures(gate)
    )


def test_the_gate_reports_persistence_false_without_a_proof():
    gate = build_customer_auth_activation_gate()
    assert gate["customer_persistence_live"] is False
    assert gate["customer_persistence_scope"] == "none"
    assert gate["customer_persistence_proof_supplied"] is False
    assert activation_gate_invariant_failures(gate) == []


def test_the_gate_keeps_production_persistence_and_the_store_false():
    gate = build_customer_auth_activation_gate()
    assert gate["production_persistence_ready"] is False
    assert gate["object_store_configured"] is False
    assert gate["awarded_operational_tracking"] is False


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifacts_regenerate_deterministically(tmp_path):
    art.write_persistence_artifacts(repo_root=tmp_path)
    written = {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / art.ARTIFACT_DIR).iterdir()
    }
    assert set(written) == set(art.ARTIFACT_FILES)

    again = art.build_persistence_artifacts()
    for name, body in written.items():
        assert body == again[name], name

    committed = Path(art.ARTIFACT_DIR)
    for name, body in written.items():
        assert (committed / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_carry_no_secret_or_customer_data():
    files = art.build_persistence_artifacts()
    blob = "\n".join(files.values()).lower()
    for forbidden in ("gocspx-", "set-cookie:", "eyj", "@gmail.com"):
        assert forbidden not in blob, forbidden

    import re

    for field in art.CREDENTIAL_FIELDS:
        assert not re.search(rf'"{re.escape(field)}"\s*:\s*"', blob), field


def test_the_artifacts_record_a_measured_round_trip():
    files = art.build_persistence_artifacts()
    smoke = json.loads(files["authenticated_org_persistence_smoke.json"])
    assert smoke["customer_persistence_live"] is True
    assert smoke["scope"] == CONTROLLED_SCOPE
    assert smoke["rows_written"] == len(LANES)
    assert smoke["rows_left_live"] == 0
    assert smoke["invariant_failures"] == []
    assert smoke["customer_auth_live"] is False
    assert smoke["customer_auth_live_required"] is False


def test_the_artifacts_record_every_refusal():
    files = art.build_persistence_artifacts()
    refusals = json.loads(files["cross_org_refusal_results.json"])
    assert refusals["cross_org_rows_read_total"] == 0
    for name in (
        "real_organization",
        "no_accountable_principal",
        "label_offered_as_authority",
    ):
        entry = refusals["refusals"][name]
        assert entry["customer_persistence_live"] is False, name
        assert entry["rows_written"] == 0, name
        assert entry["blocked_reasons"], name


def test_the_artifacts_do_not_claim_production_readiness():
    files = art.build_persistence_artifacts()
    readiness = json.loads(files["customer_persistence_readiness.json"])
    supplied = readiness["with_the_proof_supplied"]
    assert supplied["customer_persistence_live"] is True
    assert supplied["customer_auth_live"] is False
    assert supplied["production_persistence_ready"] is False
    assert supplied["object_store_configured"] is False
    assert supplied["awarded_operational_tracking"] is False
    assert readiness["production_rollout"] is False
    assert readiness["real_customer_data_written"] is False


def test_the_artifact_invariants_hold(tmp_path):
    result = art.write_persistence_artifacts(repo_root=tmp_path)
    assert art.persistence_artifact_invariant_failures(result) == []
    assert result["file_count"] == len(art.ARTIFACT_FILES)
