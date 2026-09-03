"""Gate 140: the tenant digest and source watchlist, behind an authenticated org.

Gate 104 built every component of a digest — snapshots, change detection,
per-item explanations, suppression, a weekly-default builder — and wired none of
them. `ready_for_demo_preview` was true for thirty-six gates with nothing able
to ask for a preview, and `tenant_digest_operational` was a literal `False` in
six places that no service derived.

This gate wired them. Everything below is about whether they can be used
wrongly.

The claims the gate is forbidden from making get their own tests and their own
reachable branches:

```text
watching a source is not monitoring it
a preview is not a delivery
an unknown eligibility stays unknown
an unverified deadline is reported as unverified, never inferred
a suppression hides a view and deletes nothing
a suppression with no audit event is refused
```
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.api.post_award_common import CALLER_MAY_NOT_SET, FIXTURE_FACT_STATUS
from nativeforge.main import create_app
from nativeforge.services import tenant_digest_artifact_gate140_service as art
from nativeforge.services import tenant_pursuit_suppression_repository_service as supp
from nativeforge.services import tenant_source_watchlist_service as wl
from nativeforge.services.tenant_digest_operational_readiness_service import (
    CONTROLLED_SCOPE,
    LANE_ROUTE_MODULES,
    NOT_APPROVED,
    build_tenant_digest_readiness,
    detect_route_module,
    tenant_digest_readiness_invariant_failures,
)
from nativeforge.services.tenant_digest_route_smoke_service import (
    FEDERAL_SOURCE_ID,
    MISLABELLED_FIXTURE_ID,
    SC_SOURCE_ID,
    UNKNOWN_SOURCE_ID,
    run_tenant_digest_route_smoke,
    tenant_digest_route_smoke_invariant_failures,
)
from nativeforge.services.tenant_nofo_digest_service import (
    DAILY_NOT_ENABLED,
    DEFAULT_CADENCE,
    DIGEST_ITEM_FIELDS,
    NO_PROFILE,
    UNRESOLVED_STATUSES,
    build_org_digest_preview,
    digest_preview_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d140"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

FIXTURE_SOURCE = "nf-fixture-gate140-source"


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


def _seed_profile(organization_id: str, frequency: str = DEFAULT_CADENCE) -> None:
    """A tenant profile, so the digest has a cadence to read."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.services.tenant_profile_repository_service import (
        upsert_tenant_profile,
    )

    with SessionLocal() as session:
        result = upsert_tenant_profile(
            connection=session.connection(),
            organization_id=organization_id,
            tenant_id_label=f"t-{organization_id[:8]}",
            customer_org_id_label=f"c-{organization_id[:8]}",
            recognition_status="federally_recognized",
            recognition_status_fact_status="demo_fixture",
            operating_states=["SC"],
            operating_states_fact_status="demo_fixture",
            applicant_classes=["federally_recognized_tribe"],
            applicant_classes_fact_status="demo_fixture",
            digest_frequency=frequency,
            profile_status="active",
            is_demo=True,
        )
        assert result["rows_written"] == 1, result["blocked_reasons"]
        session.commit()


def _clear(organization_id: str) -> None:
    """Nothing live for this organization, so each test starts from the same place."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        for table in (
            "nf_source_watchlist_entries",
            "nf_tenant_pursuit_suppressions",
            "nf_tenant_beta_profiles",
        ):
            session.execute(
                sa.text(f"DELETE FROM {table} WHERE organization_id = :o"),
                {"o": uuid.UUID(organization_id).hex},
            )
        session.commit()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    _clear(DEMO)
    _clear(OTHER)
    _seed_profile(DEMO)
    yield soh.session_headers(uuid.UUID(DEMO))
    _clear(DEMO)
    _clear(OTHER)


def _add_source(client, headers, **overrides):
    body = {
        "source_id": FEDERAL_SOURCE_ID,
        "watchlist_source": "registry_entry",
        "source_name": "Aid to Tribal Government Services",
        "jurisdiction": "federal",
        **overrides,
    }
    return client.post(f"{_base()}/source-watchlist", json=body, headers=headers)


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
    detected = detect_route_module("tenant_digest", repo_root=tmp_path)
    assert detected["route_module_available"] is False
    assert "route_module_does_not_exist" in detected["blocked_reasons"]


def test_the_route_module_detector_rejects_an_unknown_lane():
    detected = detect_route_module("not_a_lane")
    assert detected["route_module_available"] is False
    assert detected["blocked_reasons"] == ["lane_not_recognised:not_a_lane"]


def test_no_real_organization_route_was_built():
    """A real-org path would reach an organization nobody authorized."""
    for relative in LANE_ROUTE_MODULES.values():
        source = Path(relative).read_text(encoding="utf-8")
        assert "require_real_org_session" not in source, relative
        assert "/v1/nf/real/orgs" not in source, relative
        assert REAL not in source, relative


def test_both_routers_are_mounted():
    paths = create_app().openapi()["paths"]
    for path, methods in (
        (f"{_base('{org_id}')}/source-watchlist", {"get", "post"}),
        (f"{_base('{org_id}')}/source-watchlist/{{entry_id}}", {"get"}),
        (f"{_base('{org_id}')}/digest", {"get"}),
        (f"{_base('{org_id}')}/digest/readiness", {"get"}),
        (f"{_base('{org_id}')}/digest/cadence", {"post"}),
        (f"{_base('{org_id}')}/digest/suppress", {"post"}),
        (f"{_base('{org_id}')}/digest/lift", {"post"}),
    ):
        assert path in paths, path
        assert methods <= set(paths[path]), (path, sorted(paths[path]))


# ---------------------------------------------------------------------------
# failing closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_base()}/source-watchlist"),
        ("POST", f"{_base()}/source-watchlist"),
        ("GET", f"{_base()}/source-watchlist/{uuid.uuid4()}"),
        ("POST", f"{_base()}/source-watchlist/{uuid.uuid4()}/archive"),
        ("GET", f"{_base()}/digest"),
        ("GET", f"{_base()}/digest/readiness"),
        ("POST", f"{_base()}/digest/cadence"),
        ("POST", f"{_base()}/digest/suppress"),
        ("POST", f"{_base()}/digest/lift"),
    ],
)
def test_every_route_refuses_an_unauthenticated_caller(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_a_forged_dev_header_authorizes_nothing(client):
    response = client.get(
        f"{_base()}/digest", headers=soh.forged_header_only(uuid.UUID(DEMO))
    )
    assert response.status_code == 401


def test_the_dev_header_is_not_a_parameter_on_any_route():
    for relative in LANE_ROUTE_MODULES.values():
        source = Path(relative).read_text(encoding="utf-8")
        assert "X-NF-Org-Id" not in source, relative


def test_a_session_for_another_organization_cannot_read_this_one(client, demo_session):
    soh.ensure_member(OTHER)
    other = soh.session_headers(uuid.UUID(OTHER))
    for path in (f"{_base()}/source-watchlist", f"{_base()}/digest"):
        assert client.get(path, headers=other).status_code in {403, 404}, path


# ---------------------------------------------------------------------------
# the watchlist
# ---------------------------------------------------------------------------


def test_a_registry_source_can_be_watched_and_read_back(client, demo_session):
    created = _add_source(client, demo_session)
    assert created.status_code == 201, created.text
    entry_id = created.json()["entry_id"]

    listed = client.get(f"{_base()}/source-watchlist", headers=demo_session)
    assert listed.status_code == 200
    assert listed.json()["rows_read"] == 1
    assert listed.json()["active_count"] == 1

    one = client.get(f"{_base()}/source-watchlist/{entry_id}", headers=demo_session)
    assert one.status_code == 200
    assert one.json()["source_id"] == FEDERAL_SOURCE_ID


def test_a_registry_source_id_nobody_issued_is_refused(client, demo_session):
    """The catalogue is checked, not the caller's word for it."""
    refused = _add_source(client, demo_session, source_id=UNKNOWN_SOURCE_ID)
    assert refused.status_code in {400, 422}
    assert "source_id_is_not_in_the_source_registry" in json.dumps(refused.json())


def test_the_registry_the_check_reads_is_not_empty():
    """The check swallowed a wrong function name once and refused everything.

    `known_registry_source_ids` returned an empty set from a bare `except`,
    which made every `registry_entry` claim unwatchable while looking like a
    working guard.
    """
    known = wl.known_registry_source_ids()
    assert len(known) > 100
    assert FEDERAL_SOURCE_ID in known
    assert SC_SOURCE_ID in known


def test_a_fixture_source_must_carry_the_fixture_prefix(client, demo_session):
    refused = _add_source(
        client,
        demo_session,
        source_id=MISLABELLED_FIXTURE_ID,
        watchlist_source="controlled_fixture",
    )
    assert refused.status_code in {400, 422}
    assert "fixture" in json.dumps(refused.json()).lower()


def test_a_prefixed_fixture_source_is_accepted(client, demo_session):
    """Otherwise the fixture branch is unreachable and the prefix rule untested."""
    created = _add_source(
        client,
        demo_session,
        source_id=FIXTURE_SOURCE,
        watchlist_source="controlled_fixture",
    )
    assert created.status_code == 201, created.text


def test_a_tenant_requested_source_is_stored_for_human_review(client, demo_session):
    """Refusing it outright would push tenants into mislabelling."""
    created = _add_source(
        client,
        demo_session,
        source_id="https://example.invalid/a-grants-page",
        watchlist_source="tenant_requested",
    )
    assert created.status_code == 201, created.text
    assert created.json()["human_review_required"] is True


@pytest.mark.parametrize("field", sorted(CALLER_MAY_NOT_SET))
def test_a_caller_may_not_relabel_a_watchlist_write(client, demo_session, field):
    refused = _add_source(client, demo_session, **{field: "verified"})
    assert refused.status_code in {400, 422}
    assert field in json.dumps(refused.json())


def test_watching_is_not_monitoring(client, demo_session):
    """The whole reason this gate may not claim source monitoring."""
    created = _add_source(client, demo_session)
    assert created.json()["source_monitoring_live"] is False

    one = client.get(
        f"{_base()}/source-watchlist/{created.json()['entry_id']}",
        headers=demo_session,
    )
    assert one.json()["source_monitoring_live"] is False
    assert one.json()["last_checked_at"] is None

    listed = client.get(f"{_base()}/source-watchlist", headers=demo_session)
    for entry in listed.json()["entries"]:
        assert entry["source_monitoring_live"] is False
        assert entry["last_checked_at"] is None


def test_archiving_stops_the_watching_and_keeps_the_row(client, demo_session):
    entry_id = _add_source(client, demo_session).json()["entry_id"]
    archived = client.post(
        f"{_base()}/source-watchlist/{entry_id}/archive", headers=demo_session
    )
    assert archived.status_code == 200
    assert archived.json()["rows_deleted"] == 0

    active = client.get(f"{_base()}/source-watchlist", headers=demo_session)
    assert active.json()["rows_read"] == 0

    everything = client.get(
        f"{_base()}/source-watchlist?include_archived=true", headers=demo_session
    )
    assert entry_id in {e["entry_id"] for e in everything.json()["entries"]}


def test_one_live_entry_per_organization_and_source(client, demo_session):
    assert _add_source(client, demo_session).status_code == 201
    again = _add_source(client, demo_session)
    assert again.status_code in {400, 422}
    assert "already_watches_this_source" in json.dumps(again.json())


def test_another_organization_cannot_read_or_archive_this_entry(client, demo_session):
    entry_id = _add_source(client, demo_session).json()["entry_id"]
    soh.ensure_member(OTHER)
    other = soh.session_headers(uuid.UUID(OTHER))

    assert (
        client.get(
            f"{_base(OTHER)}/source-watchlist/{entry_id}", headers=other
        ).status_code
        == 404
    )
    assert client.post(
        f"{_base(OTHER)}/source-watchlist/{entry_id}/archive", headers=other
    ).status_code in {400, 404, 422}

    still_live = client.get(f"{_base()}/source-watchlist", headers=demo_session)
    assert still_live.json()["active_count"] == 1


# ---------------------------------------------------------------------------
# the digest, weekly by default
# ---------------------------------------------------------------------------


def test_the_weekly_digest_needs_no_setting_at_all(client, demo_session):
    response = client.get(f"{_base()}/digest", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cadence"] == "weekly"
    assert body["default_cadence"] == "weekly"
    assert body["daily_alerts_enabled"] is False
    assert body["items_total"] >= 1


def test_a_preview_is_not_a_delivery(client, demo_session):
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    assert body["delivery_status"] == "preview_only"
    assert body["email_delivery_live"] is False
    assert body["emails_sent"] == 0
    assert body["source_monitoring_live"] is False
    assert body["live_source_coverage"] is False
    assert body["candidate_provenance"] == "labelled_fixture_snapshots"


def test_every_item_carries_every_declared_field(client, demo_session):
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    for item in body["items"]:
        missing = [field for field in DIGEST_ITEM_FIELDS if field not in item]
        assert not missing, (item["opportunity_id"], missing)


def test_an_unresolved_eligibility_stays_unresolved(client, demo_session):
    """Rounding one of these up is the fabrication the contract exists to stop."""
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    unresolved = [
        item
        for item in body["items"]
        if item["eligibility_status"] in UNRESOLVED_STATUSES
    ]
    assert unresolved, "the fixture set no longer exercises an unresolved item"
    assert body["items_with_unresolved_eligibility"] == len(unresolved)
    for item in unresolved:
        assert item["recommended_action"] == "review_eligibility_with_a_human"


def test_an_unverified_deadline_is_reported_not_inferred(client, demo_session):
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    assert body["items_with_unverified_deadlines"] >= 1
    for item in body["items"]:
        if not item["due_date_verified"]:
            assert item["due_date_status"] in {"unknown", "needs_human_review"} or (
                item["due_date_status"] != "verified"
            )
        if item["due_date_verified"]:
            assert item["due_date"], item["opportunity_id"]


def test_no_recommended_action_is_ever_apply(client, demo_session):
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    for item in body["items"]:
        assert "apply" not in item["recommended_action"]


def test_a_caveat_is_not_a_blocker(client, demo_session):
    """A digest with unverified deadlines is produced AND says so.

    Folding the builder's content caveats into `blocked_reasons` made a working
    digest report itself blocked - the same wrong-list mistake Gate 138F made,
    and it would have made "blocked" mean nothing here too.
    """
    body = client.get(f"{_base()}/digest", headers=demo_session).json()
    assert body["caveats"], "a digest with unverified deadlines must say so"


def test_an_unrecognised_cadence_is_refused(client, demo_session):
    refused = client.get(f"{_base()}/digest?cadence=hourly", headers=demo_session)
    assert refused.status_code == 422
    assert "cadence_not_recognised" in json.dumps(refused.json())


def test_a_digest_without_a_profile_is_refused(client, demo_session):
    _clear(DEMO)
    refused = client.get(f"{_base()}/digest", headers=demo_session)
    assert refused.status_code == 422
    assert NO_PROFILE in json.dumps(refused.json())


# ---------------------------------------------------------------------------
# daily is optional and off
# ---------------------------------------------------------------------------


def test_daily_is_refused_until_the_profile_enables_it(client, demo_session):
    refused = client.get(f"{_base()}/digest?cadence=daily", headers=demo_session)
    assert refused.status_code == 422
    assert DAILY_NOT_ENABLED in json.dumps(refused.json())


def test_daily_works_once_the_tenant_enables_it(client, demo_session):
    enabled = client.post(
        f"{_base()}/digest/cadence",
        json={"digest_frequency": "daily"},
        headers=demo_session,
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["daily_alerts_enabled"] is True

    daily = client.get(f"{_base()}/digest?cadence=daily", headers=demo_session)
    assert daily.status_code == 200, daily.text
    assert daily.json()["cadence"] == "daily"
    assert daily.json()["daily_alerts_enabled"] is True


def test_disabling_daily_puts_the_refusal_back(client, demo_session):
    """The permitted branch and the refusal must both stay reachable."""
    client.post(
        f"{_base()}/digest/cadence",
        json={"digest_frequency": "daily"},
        headers=demo_session,
    )
    client.post(
        f"{_base()}/digest/cadence",
        json={"digest_frequency": "weekly"},
        headers=demo_session,
    )
    refused = client.get(f"{_base()}/digest?cadence=daily", headers=demo_session)
    assert refused.status_code == 422
    assert DAILY_NOT_ENABLED in json.dumps(refused.json())


def test_a_cadence_change_keeps_the_rest_of_the_profile(client, demo_session):
    """A cadence change is not a reason to lose a tenant's recognition status."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.services.tenant_profile_repository_service import (
        get_tenant_profile,
    )

    client.post(
        f"{_base()}/digest/cadence",
        json={"digest_frequency": "daily"},
        headers=demo_session,
    )
    with SessionLocal() as session:
        after = get_tenant_profile(
            connection=session.connection(), organization_id=DEMO
        )
    assert after["recognition_status"] == "federally_recognized"
    assert after["operating_states"] == ["SC"]
    assert after["digest_frequency"] == "daily"


def test_a_cadence_change_for_an_organization_with_no_profile_is_refused(
    client, demo_session
):
    _clear(DEMO)
    refused = client.post(
        f"{_base()}/digest/cadence",
        json={"digest_frequency": "daily"},
        headers=demo_session,
    )
    assert refused.status_code == 404
    assert NO_PROFILE in json.dumps(refused.json())


# ---------------------------------------------------------------------------
# suppression
# ---------------------------------------------------------------------------


def _first_item(client, headers) -> str:
    body = client.get(f"{_base()}/digest", headers=headers).json()
    return body["items"][0]["opportunity_id"]


def test_a_suppression_hides_the_item_and_deletes_nothing(client, demo_session):
    before = client.get(f"{_base()}/digest", headers=demo_session).json()
    target = before["items"][0]["opportunity_id"]

    suppressed = client.post(
        f"{_base()}/digest/suppress",
        json={
            "opportunity_id": target,
            "suppression_reason": "pursuit_started",
            "pursuit_record_id": "pursuit-gate140",
        },
        headers=demo_session,
    )
    assert suppressed.status_code == 201, suppressed.text
    assert suppressed.json()["rows_deleted"] == 0
    assert suppressed.json()["opportunity_deleted"] is False
    assert suppressed.json()["source_history_preserved"] is True

    after = client.get(f"{_base()}/digest", headers=demo_session).json()
    assert after["items_total"] == before["items_total"]
    assert after["items_visible"] == before["items_visible"] - 1
    assert target not in {item["opportunity_id"] for item in after["items"]}
    assert target in {item["opportunity_id"] for item in after["suppressed_items"]}


def test_a_suppression_carries_a_real_audit_event(client, demo_session):
    """The contract refuses a suppression with no audit evidence, and it is right.

    A suppression nobody can trace is a way for things to quietly stop
    appearing, so the route appends a real `nf_audit_events` row and passes its
    id rather than minting one and hoping.
    """
    from nativeforge.db.session import SessionLocal

    target = _first_item(client, demo_session)
    response = client.post(
        f"{_base()}/digest/suppress",
        json={
            "opportunity_id": target,
            "suppression_reason": "pursuit_started",
            "pursuit_record_id": "pursuit-gate140",
        },
        headers=demo_session,
    )
    assert response.status_code == 201, response.text
    audit_id = uuid.UUID(response.json()["audit_event_id"])

    with SessionLocal() as session:
        found = session.execute(
            sa.text("SELECT COUNT(*) FROM nf_audit_events WHERE id = :i"),
            {"i": audit_id.hex},
        ).scalar_one()
        stored = supp.list_suppressions(
            connection=session.connection(), organization_id=DEMO
        )
    assert found == 1
    assert stored["suppressions"][0]["audit_event_id"] == str(audit_id)


def test_the_suppression_contract_refuses_a_suppression_with_no_audit_event():
    """The reachable refusal behind the route's audit append."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        refused = supp.record_suppression(
            connection=session.connection(),
            organization_id=DEMO,
            opportunity_id="nf-fixture-no-audit",
            suppression_reason="pursuit_started",
            pursuit_record_id="pursuit-gate140",
            audit_event_id=None,
            fact_status=FIXTURE_FACT_STATUS,
            is_demo=True,
        )
    assert refused["rows_written"] == 0
    assert any("audit" in reason for reason in refused["blocked_reasons"])


def test_a_suppression_reason_that_needs_a_pursuit_gets_one():
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        refused = supp.record_suppression(
            connection=session.connection(),
            organization_id=DEMO,
            opportunity_id="nf-fixture-no-pursuit",
            suppression_reason="pursuit_started",
            pursuit_record_id=None,
            audit_event_id=str(uuid.uuid4()),
            fact_status=FIXTURE_FACT_STATUS,
            is_demo=True,
        )
    assert refused["rows_written"] == 0
    assert refused["blocked_reasons"]


def test_lifting_a_suppression_brings_the_item_back(client, demo_session):
    target = _first_item(client, demo_session)
    client.post(
        f"{_base()}/digest/suppress",
        json={
            "opportunity_id": target,
            "suppression_reason": "pursuit_started",
            "pursuit_record_id": "pursuit-gate140",
        },
        headers=demo_session,
    )
    lifted = client.post(
        f"{_base()}/digest/lift",
        json={"opportunity_id": target},
        headers=demo_session,
    )
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["rows_deleted"] == 0

    after = client.get(f"{_base()}/digest", headers=demo_session).json()
    assert target in {item["opportunity_id"] for item in after["items"]}


def test_a_suppression_is_org_scoped(client, demo_session):
    target = _first_item(client, demo_session)
    client.post(
        f"{_base()}/digest/suppress",
        json={
            "opportunity_id": target,
            "suppression_reason": "pursuit_started",
            "pursuit_record_id": "pursuit-gate140",
        },
        headers=demo_session,
    )

    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        mine = supp.list_suppressions(
            connection=session.connection(), organization_id=DEMO
        )
        theirs = supp.list_suppressions(
            connection=session.connection(), organization_id=OTHER
        )
    assert mine["rows_read"] == 1
    assert theirs["rows_read"] == 0


def test_the_preserved_flags_are_not_optional():
    """A CHECK, so a caller cannot store a suppression that lost the provenance."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        with pytest.raises(Exception):  # noqa: B017 - dialect-specific error type
            session.execute(
                sa.text(
                    "INSERT INTO nf_tenant_pursuit_suppressions "
                    "(id, organization_id, is_demo, opportunity_id, "
                    "suppression_status, suppression_reason, "
                    "source_history_preserved, provenance_preserved, "
                    "visible_in_pipeline, visible_in_awarded_workspace, "
                    "fact_status, suppressed_at, created_at) VALUES "
                    "(:i, :o, 1, 'nf-fixture-x', 'suppressed_from_new_digest', "
                    "'pursuit_started', 0, 1, 1, 0, 'demo_fixture', "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"i": uuid.uuid4().hex, "o": uuid.UUID(DEMO).hex},
            )
        session.rollback()


# ---------------------------------------------------------------------------
# the service layer, without a request
# ---------------------------------------------------------------------------


def test_a_digest_refuses_a_substitute_anchor():
    """`tenant_id` is not authority. Gates 110-113 exist for this substitution."""
    for key in ("tenant_id", "customer_org_id", "organization_profile_id"):
        preview = build_org_digest_preview(organization_id=DEMO, **{key: "something"})
        assert f"not_an_anchor_for_a_digest:{key}" in preview["blocked_reasons"]


def test_a_digest_without_an_anchor_is_refused():
    preview = build_org_digest_preview(organization_id=None)
    assert "digest_without_an_organization_id_anchor" in preview["blocked_reasons"]


def test_a_refused_digest_does_not_fail_the_caveat_invariant():
    """A refused digest never reached the builder, so it has no caveats to report.

    Demanding them made a correct refusal fail an invariant, which would have
    made every refusal look like a bug.
    """
    preview = build_org_digest_preview(organization_id=None)
    assert preview["blocked_reasons"]
    assert digest_preview_invariant_failures(preview) == []


def test_the_digest_scope_is_the_controlled_one():
    preview = build_org_digest_preview(organization_id=DEMO)
    assert preview["scope"] == CONTROLLED_SCOPE


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def test_readiness_is_true_when_the_smoke_proves_it(client, demo_session):
    soh.ensure_member(OTHER)
    smoke = run_tenant_digest_route_smoke(
        client=client,
        organization_id=DEMO,
        other_organization_id=OTHER,
        session_headers=demo_session,
    )
    assert smoke["blocked_reasons"] == [], smoke["blocked_reasons"]
    assert smoke["end_to_end_completed"] is True
    assert tenant_digest_route_smoke_invariant_failures(smoke) == []

    readiness = build_tenant_digest_readiness(
        route_smoke=smoke, customer_persistence_live=True, profile_available=True
    )
    assert readiness["tenant_digest_operational"] is True
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert readiness["blocked_reasons"] == []
    assert tenant_digest_readiness_invariant_failures(readiness) == []


def test_readiness_is_false_with_no_smoke():
    readiness = build_tenant_digest_readiness(
        customer_persistence_live=True, profile_available=True
    )
    assert readiness["tenant_digest_operational"] is False
    assert readiness["scope"] == "none"
    assert "no_route_smoke_was_supplied" in readiness["blocked_reasons"]
    assert tenant_digest_readiness_invariant_failures(readiness) == []


def test_readiness_is_false_without_customer_persistence():
    """A digest that cannot be persisted is not operational for anybody."""
    readiness = build_tenant_digest_readiness(
        route_smoke={"watchlist_route_operational": True},
        customer_persistence_live=False,
        profile_available=True,
    )
    assert readiness["tenant_digest_operational"] is False
    assert "customer_persistence_is_not_live" in readiness["blocked_reasons"]


def test_readiness_is_false_without_a_profile():
    readiness = build_tenant_digest_readiness(
        route_smoke={"watchlist_route_operational": True},
        customer_persistence_live=True,
        profile_available=False,
    )
    assert readiness["tenant_digest_operational"] is False
    assert NO_PROFILE in readiness["blocked_reasons"]


def test_readiness_is_false_when_a_route_module_is_absent(tmp_path):
    readiness = build_tenant_digest_readiness(
        route_smoke={"watchlist_route_operational": True},
        customer_persistence_live=True,
        profile_available=True,
        repo_root=tmp_path,
    )
    assert readiness["tenant_digest_operational"] is False
    assert any("route_module_does_not_exist" in r for r in readiness["blocked_reasons"])


def test_monitoring_and_email_are_not_required_for_a_preview():
    """Requiring either would make the lane unreachable.

    Gate 134F's lesson: an unsatisfiable conjunct makes every refusal above it
    unfalsifiable, because nothing can ever reach the permitted branch.
    """
    readiness = build_tenant_digest_readiness(
        customer_persistence_live=True, profile_available=True
    )
    assert readiness["source_monitoring_required_for_preview"] is False
    assert readiness["email_required_for_preview"] is False


@pytest.mark.parametrize(
    "field",
    [
        "source_monitoring_live",
        "email_delivery_available",
        "live_source_coverage",
        "live_grant_sources_called",
        "production_tenant_digest",
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "real_customer_data_written",
        "real_organization_touched",
    ],
)
def test_readiness_never_claims(field):
    readiness = build_tenant_digest_readiness(
        customer_persistence_live=True, profile_available=True
    )
    assert readiness[field] is False


def test_readiness_names_what_it_does_not_approve():
    readiness = build_tenant_digest_readiness()
    assert set(NOT_APPROVED) <= set(readiness["not_approved"])


def test_the_readiness_invariants_catch_a_forged_result():
    forged = build_tenant_digest_readiness(
        route_smoke={"watchlist_route_operational": True},
        customer_persistence_live=False,
        profile_available=False,
    )
    forged["tenant_digest_operational"] = True
    forged["source_monitoring_live"] = True
    failures = tenant_digest_readiness_invariant_failures(forged)
    assert "claimed:source_monitoring_live" in failures
    assert "operational_alongside_blockers" in failures


def test_the_smoke_invariants_catch_a_suppression_with_no_audit():
    forged = {
        "end_to_end_completed": False,
        "authenticated_run": True,
        "suppression_proved": True,
        "suppression_audit_backed": False,
    }
    assert "suppression_without_audit_evidence" in (
        tenant_digest_route_smoke_invariant_failures(forged)
    )


# ---------------------------------------------------------------------------
# the readiness route
# ---------------------------------------------------------------------------


def test_the_readiness_route_reports_what_is_and_is_not_ready(client, demo_session):
    response = client.get(f"{_base()}/digest/readiness", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile_available"] is True
    assert body["source_monitoring_live"] is False
    assert body["email_delivery_available"] is False
    assert body["production_tenant_digest"] is False
    assert body["source_monitoring_required_for_preview"] is False


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_tenant_digest_artifacts(repo_root=tmp_path)
    assert art.tenant_digest_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_tenant_digest_artifacts()
    second = art.build_tenant_digest_artifacts()
    assert first == second


def test_the_artifact_proves_the_digest_is_operational():
    files = art.build_tenant_digest_artifacts()
    readiness = json.loads(files["tenant_digest_operational_readiness.json"])
    end_to_end = json.loads(files["tenant_digest_end_to_end_smoke.json"])
    assert readiness["tenant_digest_operational"] is True
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert readiness["invariant_failures"] == []
    assert end_to_end["end_to_end_completed"] is True
    assert end_to_end["invariant_failures"] == []
    assert end_to_end["every_stored_row_is_fixture_labelled"] is True


def test_the_artifact_claims_nothing_it_may_not():
    files = art.build_tenant_digest_artifacts()
    weekly = json.loads(files["weekly_digest_preview_smoke.json"])
    watchlist = json.loads(files["source_watchlist_route_smoke.json"])
    assert weekly["source_monitoring_live"] is False
    assert weekly["email_delivery_live"] is False
    assert weekly["emails_sent"] == 0
    assert weekly["improvement_claims"] == []
    assert watchlist["watching_is_not_monitoring"] is True
    assert watchlist["collectors_activated"] == 0
    assert watchlist["rows_for_the_real_organization"] == 0


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = Path(art.ARTIFACT_DIR)
    files = art.build_tenant_digest_artifacts()
    for name, body in files.items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name


def test_no_artifact_mentions_the_real_organization():
    for body in art.build_tenant_digest_artifacts().values():
        # Named once, in the survey, as the organization no route reaches.
        assert body.count(REAL) <= 1
