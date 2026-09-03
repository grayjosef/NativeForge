"""Gate 139: the four post-award lanes, behind an authenticated org context.

Gate 138 proved these lanes round-trip at the repository and reported the
honest thing: repository-live is not customer-usable, because four of five had
no routes. This gate built them, and everything below is about whether they can
be used wrongly.

The two refusals the gate is forbidden from weakening get their own tests and
their own reachable branches:

```text
an unsupported requirement stays unknown / needs_human_review
a due date is never inferred - it arrives with a status or it does not arrive
```
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.api.post_award_common import (
    BODY_STORAGE_FIELDS,
    CALLER_MAY_NOT_SET,
    CONTROLLED_SCOPE,
    FIXTURE_FACT_STATUS,
)
from nativeforge.main import create_app
from nativeforge.services import awarded_operational_artifact_gate139_service as art
from nativeforge.services.awarded_operational_route_smoke_service import (
    AWARD_BODY,
    DOCUMENT_BODY,
    PROOF_BODY,
    REQUIREMENT_BODY,
    UNSUPPORTED_REQUIREMENT,
    route_smoke_invariant_failures,
    run_post_award_route_smoke,
)
from nativeforge.services.awarded_operational_tracking_readiness_service import (
    LANE_CAPABILITIES,
    LANE_ROUTE_MODULES,
    awarded_readiness_invariant_failures,
    build_awarded_operational_readiness,
    detect_route_module,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d139"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPOSITORY_PROOF = {
    "customer_persistence_live": True,
    "repository_persistence_live_lanes": sorted(LANE_CAPABILITIES.values()),
}


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    return soh.session_headers(uuid.UUID(DEMO))


@pytest.fixture
def other_session():
    soh.ensure_signing_key()
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(OTHER)
    return soh.session_headers(uuid.UUID(OTHER))


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


def _create_award(client, headers, organization_id: str = DEMO) -> str:
    response = client.post(
        f"{_base(organization_id)}/awarded-grants", json=AWARD_BODY, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["award_id"]


def _create_requirement(client, headers, award_id: str, **overrides) -> str:
    body = {**REQUIREMENT_BODY, **overrides}
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/requirements", json=body, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["requirement_id"]


# ---------------------------------------------------------------------------
# the routes exist and are session-wired
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lane", sorted(LANE_ROUTE_MODULES))
def test_every_lane_has_a_session_wired_route_module(lane):
    detected = detect_route_module(lane)
    assert detected["route_module_available"] is True
    assert detected["session_wired"] is True
    assert detected["reads_dev_header"] is False
    assert detected["blocked_reasons"] == []


def test_the_route_module_detector_can_report_absent(tmp_path):
    """Otherwise `route_module_available: False` is unreachable."""
    detected = detect_route_module("awarded_grants", repo_root=tmp_path)
    assert detected["route_module_available"] is False
    assert "route_module_does_not_exist" in detected["blocked_reasons"]


def test_no_real_organization_route_was_built():
    """A real-org path would reach an organization nobody authorized."""
    for relative in LANE_ROUTE_MODULES.values():
        source = Path(relative).read_text(encoding="utf-8")
        assert "require_real_org_session" not in source, relative
        assert "/v1/nf/real/orgs" not in source, relative


# ---------------------------------------------------------------------------
# failing closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_base()}/awarded-grants"),
        ("POST", f"{_base()}/awarded-grants"),
        ("GET", f"{_base()}/awarded-grants/{uuid.uuid4()}"),
        ("GET", f"{_base()}/awarded-grants/{uuid.uuid4()}/requirements"),
        ("POST", f"{_base()}/awarded-grants/{uuid.uuid4()}/requirements"),
        ("GET", f"{_base()}/requirements/{uuid.uuid4()}"),
        ("GET", f"{_base()}/requirements/{uuid.uuid4()}/proof-events"),
        ("POST", f"{_base()}/requirements/{uuid.uuid4()}/proof-events"),
        ("GET", f"{_base()}/proof-events/{uuid.uuid4()}"),
        ("GET", f"{_base()}/awarded-grants/{uuid.uuid4()}/documents"),
        ("POST", f"{_base()}/awarded-grants/{uuid.uuid4()}/documents"),
        ("GET", f"{_base()}/documents/{uuid.uuid4()}"),
    ],
)
def test_an_unauthenticated_caller_gets_401(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_a_forged_dev_header_does_not_admit_anybody(client):
    """The header is not a parameter on any of these routes."""
    response = client.get(
        f"{_base()}/awarded-grants", headers=soh.forged_header_only(DEMO)
    )
    assert response.status_code == 401


def test_a_forged_session_cookie_does_not_admit_anybody(client):
    response = client.get(
        f"{_base()}/awarded-grants", cookies={"nf_session": "not-a-real-session"}
    )
    assert response.status_code == 401


def test_a_session_without_a_membership_gets_403(client):
    """401 means authenticate; 403 means you did, and it is still no."""
    soh.ensure_signing_key()
    orphan = "cccccccc-dddd-eeee-ffff-00000000d140"
    soh.ensure_org(orphan, "demo")
    # A session for an organization the caller is a member of, pointed at one
    # they are not.
    soh.ensure_member(DEMO)
    headers = soh.session_headers(uuid.UUID(DEMO))
    response = client.get(f"{_base(orphan)}/awarded-grants", headers=headers)
    assert response.status_code in {403, 404}


def test_a_session_plus_a_forged_header_still_uses_the_session(client, demo_session):
    """A converted route reads the session, and the header changes nothing."""
    with_header = {**demo_session, "X-NF-Org-Id": OTHER}
    response = client.get(f"{_base()}/awarded-grants", headers=with_header)
    assert response.status_code == 200
    assert response.json()["organization_id"] == DEMO


# ---------------------------------------------------------------------------
# awarded grants
# ---------------------------------------------------------------------------


def test_an_authenticated_org_can_create_read_list_and_archive(client, demo_session):
    award_id = _create_award(client, demo_session)

    read = client.get(f"{_base()}/awarded-grants/{award_id}", headers=demo_session)
    assert read.status_code == 200
    assert read.json()["award_id"] == award_id
    assert read.json()["scope"] == CONTROLLED_SCOPE

    listed = client.get(f"{_base()}/awarded-grants", headers=demo_session)
    assert listed.status_code == 200
    assert listed.json()["rows_read"] >= 1

    archived = client.post(
        f"{_base()}/awarded-grants/{award_id}/archive", json={}, headers=demo_session
    )
    assert archived.status_code == 200
    assert archived.json()["archived"] is True
    assert archived.json()["update_path_available"] is False


def test_every_written_row_is_fixture_labelled(client, demo_session):
    award_id = _create_award(client, demo_session)
    from nativeforge.db.session import engine

    with engine.connect() as connection:
        row = (
            connection.execute(
                sa.text(
                    "SELECT fact_status, is_demo FROM nf_awarded_grants WHERE id = :i"
                ),
                {"i": uuid.UUID(award_id).hex},
            )
            .mappings()
            .one()
        )
    assert row["fact_status"] == FIXTURE_FACT_STATUS
    assert bool(row["is_demo"]) is True


@pytest.mark.parametrize("field", sorted(CALLER_MAY_NOT_SET))
def test_a_caller_cannot_relabel_the_write(client, demo_session, field):
    """Pydantic drops an unknown field silently, so the bodies allow extras.

    Found by this gate's own smoke invariant: `is_demo: false` was being
    ignored rather than refused, which is how a caller comes to believe a
    production write happened.
    """
    response = client.post(
        f"{_base()}/awarded-grants",
        json={**AWARD_BODY, field: "anything"},
        headers=demo_session,
    )
    assert response.status_code == 400
    assert field in response.json()["detail"]["fields"]


def test_a_cross_org_award_read_is_refused(client, demo_session, other_session):
    award_id = _create_award(client, demo_session)
    # The other organization's session, asking for its own URL.
    response = client.get(
        f"{_base(OTHER)}/awarded-grants/{award_id}", headers=other_session
    )
    # 404: the row is not in that organization, and the response does not
    # confirm that it exists anywhere.
    assert response.status_code == 404


def test_no_route_offers_an_update():
    for relative in LANE_ROUTE_MODULES.values():
        source = Path(relative).read_text(encoding="utf-8")
        assert "@router.patch" not in source, relative
        assert "@router.put" not in source, relative


# ---------------------------------------------------------------------------
# award requirements: the two refusals that must not weaken
# ---------------------------------------------------------------------------


def test_a_requirement_attaches_to_an_award_in_the_same_organization(
    client, demo_session
):
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(client, demo_session, award_id)

    read = client.get(f"{_base()}/requirements/{requirement_id}", headers=demo_session)
    assert read.status_code == 200
    assert read.json()["requirement_id"] == requirement_id


def test_a_requirement_cannot_attach_to_another_organizations_award(
    client, demo_session, other_session
):
    award_id = _create_award(client, other_session, organization_id=OTHER)
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/requirements",
        json=REQUIREMENT_BODY,
        headers=demo_session,
    )
    assert response.status_code == 404
    assert (
        response.json()["detail"]["error"]
        == "awarded_grant_not_found_in_this_organization"
    )


def test_a_due_date_without_a_status_is_refused(client, demo_session):
    """A bare date would read as verified to anybody looking at it."""
    award_id = _create_award(client, demo_session)
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/requirements",
        json={
            **REQUIREMENT_BODY,
            "requirement_due_date": "2026-06-30",
            "due_date_status": None,
        },
        headers=demo_session,
    )
    assert response.status_code == 422
    assert "due_date_supplied_without_a_due_date_status" in response.text


def test_no_route_computes_a_due_date():
    """Parsed, not grepped: nothing derives a date from anything."""
    source = Path(LANE_ROUTE_MODULES["award_requirements"]).read_text(encoding="utf-8")
    for forbidden in ("timedelta", "relativedelta", "date.today", "datetime.now"):
        assert forbidden not in source, forbidden


def test_an_unsupported_requirement_stays_unresolved(client, demo_session):
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(
        client,
        demo_session,
        award_id,
        **{
            key: value
            for key, value in UNSUPPORTED_REQUIREMENT.items()
            if key not in REQUIREMENT_BODY
            or UNSUPPORTED_REQUIREMENT[key] != REQUIREMENT_BODY.get(key)
        },
    )
    read = client.get(f"{_base()}/requirements/{requirement_id}", headers=demo_session)
    assert read.status_code == 200
    payload = read.json()
    assert payload["unresolved"] is True
    assert payload["requirement_status"] in {"unknown", "needs_human_review"}
    assert not payload["requirement_due_date"]


def test_the_route_does_not_default_a_requirement_source(client, demo_session):
    """No default means nothing claims an extraction happened."""
    award_id = _create_award(client, demo_session)
    body = {key: value for key, value in REQUIREMENT_BODY.items()}
    body.pop("requirement_source")
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/requirements",
        json=body,
        headers=demo_session,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# proof and audit
# ---------------------------------------------------------------------------


def test_a_proof_event_attaches_to_a_requirement_in_the_same_organization(
    client, demo_session
):
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(client, demo_session, award_id)
    response = client.post(
        f"{_base()}/requirements/{requirement_id}/proof-events",
        json=PROOF_BODY,
        headers=demo_session,
    )
    assert response.status_code == 201
    assert response.json()["immutable"] is True
    assert response.json()["document_storage_available"] is False


def test_a_proof_event_cannot_attach_to_another_organizations_requirement(
    client, demo_session, other_session
):
    award_id = _create_award(client, other_session, organization_id=OTHER)
    other_body = {**REQUIREMENT_BODY}
    created = client.post(
        f"{_base(OTHER)}/awarded-grants/{award_id}/requirements",
        json=other_body,
        headers=other_session,
    )
    assert created.status_code == 201
    requirement_id = created.json()["requirement_id"]

    response = client.post(
        f"{_base()}/requirements/{requirement_id}/proof-events",
        json=PROOF_BODY,
        headers=demo_session,
    )
    assert response.status_code == 404


def test_a_proof_event_is_corrected_by_supersede_not_update(client, demo_session):
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(client, demo_session, award_id)
    created = client.post(
        f"{_base()}/requirements/{requirement_id}/proof-events",
        json=PROOF_BODY,
        headers=demo_session,
    )
    event_id = created.json()["event_id"]

    # No `event_type`: the repository names it `proof_superseded` itself.
    #
    # `proof_missing` rather than `proof_accepted`, because accepted needs an
    # acceptance timestamp AND a document reference and the repository refuses
    # it without them - which is the next test.
    body = {key: value for key, value in PROOF_BODY.items() if key != "event_type"}
    response = client.post(
        f"{_base()}/proof-events/{event_id}/supersede",
        json={**body, "event_status": "proof_missing"},
        headers=demo_session,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["superseded_event_id"] == event_id
    assert payload["event_id"] != event_id
    assert payload["event_type"] == "proof_superseded"
    assert payload["update_path_available"] is False

    # -- teardown, and a finding this gate turned up ------------------------
    #
    # `supersedes_event_id` is `ON DELETE SET NULL` and the CHECK is
    #
    #     (event_type = 'proof_superseded') = (supersedes_event_id IS NOT NULL)
    #
    # so deleting the predecessor nulls the successor's pointer and violates
    # the CHECK - the delete is impossible. Nothing had exercised supersede
    # before, so nothing had met it.
    #
    # It does not fire in production: proof events are append-only and
    # `rows_deleted` is a constant 0 in the repository, asserted by parsing.
    # It fires here because the suite truncates tables between files, so the
    # successor goes first and the pointer never has to be nulled.
    from nativeforge.db.session import engine

    with engine.begin() as connection:
        connection.execute(
            sa.text("DELETE FROM nf_award_requirement_proof_events WHERE id = :i"),
            {"i": uuid.UUID(payload["event_id"]).hex},
        )
        connection.execute(
            sa.text("DELETE FROM nf_award_requirement_proof_events WHERE id = :i"),
            {"i": uuid.UUID(event_id).hex},
        )


def test_a_superseded_event_cannot_be_deleted_before_its_successor():
    """The contradiction above, stated as a fact rather than a footnote.

    Not a bug this gate fixes: changing the FK to CASCADE or relaxing the CHECK
    would be a schema change, and the audit model says these rows are never
    deleted - `rows_deleted` is a constant 0 and there is no DELETE path in the
    repository at all. Recorded so the next person to meet it knows why.
    """
    migration = Path("alembic/versions").glob("0034_*.py")
    source = next(migration).read_text(encoding="utf-8")
    assert 'ondelete="SET NULL"' in source
    assert (
        "(event_type = 'proof_superseded') = (supersedes_event_id IS NOT NULL)"
        in source
    )

    repository = Path(
        "src/nativeforge/services/award_requirement_proof_audit_repository_service.py"
    ).read_text(encoding="utf-8")
    assert "sa.delete(" not in repository


def test_an_accepted_proof_without_evidence_is_refused(client, demo_session):
    """`proof_accepted` is a claim about a funder's decision.

    The repository refuses it without an acceptance timestamp and a document
    reference, and that refusal reaches the caller unchanged rather than being
    paraphrased into an HTTP message.
    """
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(client, demo_session, award_id)
    response = client.post(
        f"{_base()}/requirements/{requirement_id}/proof-events",
        json={**PROOF_BODY, "event_status": "proof_accepted"},
        headers=demo_session,
    )
    assert response.status_code == 422
    reasons = response.json()["detail"]["blocked_reasons"]
    assert "accepted_status_without_an_acceptance_timestamp" in reasons
    assert "proof_accepted_without_a_document_reference" in reasons


def test_a_supersede_caller_cannot_name_the_event_type(client, demo_session):
    """The repository names it, because a supersede is a supersede."""
    source = Path("src/nativeforge/api/award_requirement_proof_routes.py").read_text(
        encoding="utf-8"
    )
    supersede_body = source.split("class SupersedeBody")[1].split("@router")[0]
    assert "event_type" not in supersede_body.split('"""')[2]


def test_a_proof_route_refuses_a_document_body(client, demo_session):
    award_id = _create_award(client, demo_session)
    requirement_id = _create_requirement(client, demo_session, award_id)
    response = client.post(
        f"{_base()}/requirements/{requirement_id}/proof-events",
        json={**PROOF_BODY, "object_key": "s3://nope"},
        headers=demo_session,
    )
    assert response.status_code == 422
    assert "document_body_storage_is_not_configured" in response.text


# ---------------------------------------------------------------------------
# document metadata, and no bytes
# ---------------------------------------------------------------------------


def test_document_metadata_attaches_without_a_body(client, demo_session):
    award_id = _create_award(client, demo_session)
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents",
        json=DOCUMENT_BODY,
        headers=demo_session,
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["metadata_only"] is True
    assert payload["object_store_configured"] is False
    assert payload["document_body_written"] is False


@pytest.mark.parametrize("field", sorted(BODY_STORAGE_FIELDS))
def test_a_document_body_is_refused_by_name(client, demo_session, field):
    award_id = _create_award(client, demo_session)
    response = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents",
        json={**DOCUMENT_BODY, field: "anything"},
        headers=demo_session,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "document_body_storage_is_not_configured"
    assert field in detail["fields"]
    assert detail["object_store_configured"] is False


def test_the_object_store_is_never_contacted():
    """Parsed: no route module reaches for a client, a bucket or a byte."""
    for relative in LANE_ROUTE_MODULES.values():
        source = Path(relative).read_text(encoding="utf-8")
        for forbidden in ("boto3", "s3_client", "put_object", "upload_file", "open("):
            assert forbidden not in source, (relative, forbidden)


def test_a_document_read_says_the_body_is_unavailable(client, demo_session):
    award_id = _create_award(client, demo_session)
    created = client.post(
        f"{_base()}/awarded-grants/{award_id}/documents",
        json=DOCUMENT_BODY,
        headers=demo_session,
    )
    document_id = created.json()["document_id"]
    read = client.get(f"{_base()}/documents/{document_id}", headers=demo_session)
    assert read.status_code == 200
    assert read.json()["body_available"] is False
    assert read.json()["metadata_only"] is True


# ---------------------------------------------------------------------------
# the end-to-end smoke and the readiness roll-up
# ---------------------------------------------------------------------------


def test_the_end_to_end_smoke_proves_every_lane(client, demo_session):
    result = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    assert result["end_to_end_proved"] is True
    assert result["blocked_lanes"] == []
    assert result["forged_header_refused"] is True
    assert result["document_body_refused"] is True
    assert result["caller_relabel_refused"] is True
    assert result["unsupported_requirement_stayed_unresolved"] is True
    assert route_smoke_invariant_failures(result) == []


def test_awarded_tracking_is_true_only_with_route_and_repository_proof(
    client, demo_session
):
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke, repository_proof=REPOSITORY_PROOF
    )
    assert readiness["awarded_operational_tracking"] is True
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert sorted(readiness["route_live_lanes"]) == sorted(LANE_ROUTE_MODULES)
    assert awarded_readiness_invariant_failures(readiness) == []


def test_awarded_tracking_is_false_without_a_route_smoke():
    readiness = build_awarded_operational_readiness(repository_proof=REPOSITORY_PROOF)
    assert readiness["awarded_operational_tracking"] is False
    assert len(readiness["blocked_lanes"]) == len(LANE_ROUTE_MODULES)
    assert awarded_readiness_invariant_failures(readiness) == []


def test_awarded_tracking_is_false_without_customer_persistence(client, demo_session):
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke,
        repository_proof=REPOSITORY_PROOF,
        customer_persistence_live=False,
    )
    assert readiness["awarded_operational_tracking"] is False
    assert "customer_persistence_is_not_live" in readiness["blocked_reasons"]


def test_production_awarded_tracking_stays_false(client, demo_session):
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke, repository_proof=REPOSITORY_PROOF
    )
    assert readiness["production_awarded_tracking"] is False
    assert readiness["customer_auth_live"] is False
    assert readiness["verified_operational_binding"] is False
    assert readiness["object_store_configured"] is False
    assert readiness["document_body_storage_ready"] is False


def test_metadata_readiness_does_not_require_an_object_store(client, demo_session):
    """Requiring one would make the lane permanently unreachable."""
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke,
        repository_proof=REPOSITORY_PROOF,
        object_store_configured=False,
    )
    assert readiness["awarded_operational_tracking"] is True
    assert readiness["document_metadata_readiness_requires_object_store"] is False


def test_a_forged_tracking_claim_fails_an_invariant():
    forged = {
        "awarded_operational_tracking": True,
        "scope": CONTROLLED_SCOPE,
        "customer_persistence_live": True,
        "end_to_end_proved": True,
        "lanes": [
            {"lane": "awarded_grants", "route_live": False, "repository_live": True}
        ],
        "blocked_lanes": ["awarded_grants"],
        "blocked_reasons": [],
        "not_approved": list(art.NOT_APPROVED),
    }
    fails = awarded_readiness_invariant_failures(forged)
    assert "tracking_with_a_blocked_lane" in fails
    assert "tracking_with_a_route_dead_lane:awarded_grants" in fails


def test_customer_auth_live_is_not_silently_made_true(client, demo_session):
    smoke = run_post_award_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    readiness = build_awarded_operational_readiness(
        route_smoke=smoke, repository_proof=REPOSITORY_PROOF
    )
    assert readiness["awarded_operational_tracking"] is True
    assert readiness["customer_auth_live"] is False


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifacts_regenerate_deterministically(tmp_path):
    art.write_awarded_artifacts(repo_root=tmp_path)
    written = {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / art.ARTIFACT_DIR).iterdir()
    }
    assert set(written) == set(art.ARTIFACT_FILES)

    again = art.build_awarded_artifacts()
    for name, body in written.items():
        assert body == again[name], name

    committed = Path(art.ARTIFACT_DIR)
    for name, body in written.items():
        assert (committed / name).read_text(encoding="utf-8") == body, name


def test_the_artifacts_carry_no_secret_or_cookie():
    files = art.build_awarded_artifacts()
    blob = "\n".join(files.values()).lower()
    for forbidden in ("gocspx-", "set-cookie:", "eyj", "@gmail.com", "nf_session="):
        assert forbidden not in blob, forbidden

    import re

    for field in art.CREDENTIAL_FIELDS:
        assert not re.search(rf'"{re.escape(field)}"\s*:\s*"', blob), field


def test_the_artifacts_record_a_measured_end_to_end():
    files = art.build_awarded_artifacts()
    smoke = json.loads(files["post_award_end_to_end_smoke.json"])
    assert smoke["end_to_end_proved"] is True
    assert smoke["blocked_lanes"] == []
    assert smoke["invariant_failures"] == []
    assert smoke["fake_users_created"] == 0
    assert smoke["fake_sessions_created"] == 0
    assert smoke["object_store_contacted"] is False
    assert smoke["document_body_written"] is False
    assert all(count == 0 for count in smoke["rows_left_live_per_table"].values())


def test_every_lane_has_its_own_artifact():
    files = art.build_awarded_artifacts()
    for lane, filename in art.LANE_FILES.items():
        payload = json.loads(files[filename])
        assert payload["lane"] == lane
        assert payload["route_operational"] is True
        assert payload["update_path_available"] is False
        assert payload["steps"] == {
            "created": True,
            "read_back": True,
            "cross_org_refused": True,
            "archived": True,
        }


def test_the_artifacts_do_not_claim_production():
    files = art.build_awarded_artifacts()
    readiness = json.loads(files["awarded_operational_readiness.json"])
    assert readiness["awarded_operational_tracking"] is True
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert readiness["production_awarded_tracking"] is False
    assert readiness["customer_auth_live"] is False
    assert readiness["verified_operational_binding"] is False
    assert readiness["object_store_configured"] is False
    assert readiness["invariant_failures"] == []


def test_the_artifact_invariants_hold(tmp_path):
    result = art.write_awarded_artifacts(repo_root=tmp_path)
    assert art.awarded_artifact_invariant_failures(result) == []
    assert result["file_count"] == len(art.ARTIFACT_FILES)
