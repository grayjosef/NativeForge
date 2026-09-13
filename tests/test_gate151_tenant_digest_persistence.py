"""Gate 151: the digest a delivery intent names, stored and readable back.

Gate 150 measured the gap: 71 delivery intents, all 71 naming a digest, and zero
of those digests stored anywhere. A tenant asking what NativeForge told them
before a missed deadline got an intent that could say a digest was queued and
nothing that could say what was in it.

Most of what follows proves the record keeps the parts an audit needs — the
counts that must agree, the human-review count, the unverified deadlines, the
suppressions — and refuses the parts it must never hold: a recipient, a rendered
body, a caller-supplied label.
"""

from __future__ import annotations

import inspect
import json
import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.repositories.tenant_digest_records_repository import (
    CALLER_MAY_NOT_SET,
    FORBIDDEN_PAYLOAD_FIELDS,
    TABLE_NAME,
    archive_digest_record,
    get_digest_record,
    insert_digest_record,
    list_digest_records,
    payload_sha256,
    repository_invariant_failures,
)
from nativeforge.services.tenant_digest_persistence_readiness_service import (
    CONDITIONS,
    MUST_STAY_FALSE,
    build_digest_persistence_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.tenant_digest_persistence_service import (
    CONTROLLED_SCOPE,
    persist_digest,
    persistence_invariant_failures,
    read_digest,
    verify_rendering,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d151"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _digest(**overrides):
    """A digest shaped as the builder produces one."""
    base = {
        "digest_id": "a" * 64,
        "tenant_id": "fixture-tenant",
        "cadence": "weekly",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "digest_period_key": "2026-09-07..2026-09-13",
        "snapshot_ids": ["nf-fixture-snapshot-1"],
        "items_total": 6,
        "items_visible": 4,
        "items_suppressed": 2,
        "items_human_review": 1,
        "items_with_unverified_deadlines": 2,
        "items_with_unknown_reporting_burden": 3,
        "caveats": ["deadline_unverified", "eligibility_unresolved"],
        "blocked_reasons": ["items_suppressed:2"],
        "delivery_status": "preview_only",
    }
    base.update(overrides)
    return base


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/digest"


def _session():
    from nativeforge.db.session import SessionLocal

    return SessionLocal()


def _clear(organization_id: str) -> None:
    with _session() as session:
        session.execute(
            sa.text(f"DELETE FROM {TABLE_NAME} WHERE organization_id = :o"),
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
    yield soh.session_headers(uuid.UUID(DEMO))
    _clear(DEMO)
    _clear(OTHER)


@pytest.fixture
def connection():
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    _clear(DEMO)
    _clear(OTHER)
    with _session() as session:
        yield session.connection()
        session.rollback()
    _clear(DEMO)
    _clear(OTHER)


# ---------------------------------------------------------------------------
# the table exists
# ---------------------------------------------------------------------------


def test_the_digest_records_table_exists():
    from nativeforge.db.session import engine

    assert TABLE_NAME in sa.inspect(engine).get_table_names()


def test_the_table_has_no_recipient_or_body_column():
    """A column that does not exist cannot be filled by a later mistake."""
    from nativeforge.db.session import engine

    columns = {c["name"] for c in sa.inspect(engine).get_columns(TABLE_NAME)}
    for forbidden in (
        "recipient",
        "recipient_email",
        "email",
        "address",
        "rendered_body",
        "body",
        "html",
        "document_body",
    ):
        assert forbidden not in columns


def test_the_table_keeps_every_honesty_count():
    from nativeforge.db.session import engine

    columns = {c["name"] for c in sa.inspect(engine).get_columns(TABLE_NAME)}
    for required in (
        "items_total",
        "items_visible",
        "items_suppressed",
        "items_unchanged",
        "items_human_review",
        "items_with_unverified_deadlines",
        "items_with_unknown_reporting_burden",
        "caveats_json",
        "blocked_reasons",
    ):
        assert required in columns


# ---------------------------------------------------------------------------
# the round trip
# ---------------------------------------------------------------------------


def test_a_digest_persists_and_reads_back(connection):
    written = insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    assert written["rows_written"] == 1
    assert repository_invariant_failures(written) == []

    got = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    assert got["rows_read"] == 1
    assert got["record"]["digest_id"] == "a" * 64


def test_the_payload_hash_is_stable(connection):
    insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["payload_sha256"] == payload_sha256(record["digest_payload_json"])


def test_the_hash_is_stable_over_key_order():
    forward = {"a": 1, "b": [2, 3], "c": {"d": 4}}
    reversed_order = {"c": {"d": 4}, "b": [2, 3], "a": 1}
    assert payload_sha256(forward) == payload_sha256(reversed_order)


def test_a_different_payload_hashes_differently():
    assert payload_sha256({"a": 1}) != payload_sha256({"a": 2})


def test_the_counts_survive_the_round_trip(connection):
    insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["items_total"] == 6
    assert record["items_visible"] == 4
    assert record["items_suppressed"] == 2
    assert record["items_unchanged"] == 0
    assert record["items_total"] >= record["items_visible"] + record["items_suppressed"]


def test_unknown_and_the_caveats_survive_the_round_trip(connection):
    """A record that dropped these would let a digest look more certain later."""
    insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["items_human_review"] == 1
    assert record["items_with_unverified_deadlines"] == 2
    assert record["items_with_unknown_reporting_burden"] == 3
    assert "deadline_unverified" in record["caveats_json"]
    assert "items_suppressed:2" in record["blocked_reasons"]
    assert record["human_review_required"] is True


def test_the_suppressed_items_are_counted_not_dropped(connection):
    insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["items_suppressed"] == 2
    assert record["digest_payload_json"]["items_suppressed"] == 2


def test_persisting_the_same_period_twice_is_refused(connection):
    first = insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    assert first["rows_written"] == 1
    second = insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    assert second["rows_written"] == 0
    assert "digest_already_persisted_for_this_period" in second["blocked_reasons"]


def test_counts_that_disagree_are_refused_before_the_database(connection):
    result = insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(items_total=1),
        org_is_demo=True,
    )
    assert result["rows_written"] == 0
    assert "item_counts_do_not_agree" in result["blocked_reasons"]


# ---------------------------------------------------------------------------
# what may not be stored
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(FORBIDDEN_PAYLOAD_FIELDS))
def test_a_payload_carrying_a_recipient_or_a_body_is_refused(connection, field):
    result = insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(**{field: "x"}),
        org_is_demo=True,
    )
    assert result["rows_written"] == 0
    assert f"payload_field_refused:{field}" in result["blocked_reasons"]


@pytest.mark.parametrize("field", sorted(CALLER_MAY_NOT_SET))
def test_a_caller_cannot_set_the_labelling(connection, field):
    result = insert_digest_record(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
        **{field: "whatever"},
    )
    assert result["rows_written"] == 0
    assert f"caller_may_not_set:{field}" in result["blocked_reasons"]


def test_the_labelling_is_derived_from_the_organization(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["is_demo"] is True
    assert record["fact_status"] == "demo_fixture"


def test_the_record_states_the_capabilities_were_off(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    record = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]
    assert record["email_delivery_live"] is False
    assert record["source_monitoring_live"] is False
    assert record["delivery_status"] != "sent"


def test_the_real_organization_is_refused_by_name(connection):
    result = insert_digest_record(
        connection=connection,
        organization_id=REAL,
        digest=_digest(),
        org_is_demo=False,
    )
    assert result["rows_written"] == 0
    assert "real_organization_refused_by_name" in result["blocked_reasons"]


# ---------------------------------------------------------------------------
# cross-org
# ---------------------------------------------------------------------------


def test_a_cross_org_read_is_refused(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    got = get_digest_record(
        connection=connection, organization_id=OTHER, digest_id="a" * 64
    )
    assert got["rows_read"] == 0
    assert "no_digest_record_for_this_organization" in got["blocked_reasons"]


def test_the_refusal_is_the_same_as_for_a_digest_that_does_not_exist(connection):
    """A different answer would confirm it exists."""
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    theirs = get_digest_record(
        connection=connection, organization_id=OTHER, digest_id="a" * 64
    )
    absent = get_digest_record(
        connection=connection, organization_id=OTHER, digest_id="z" * 64
    )
    assert theirs["blocked_reasons"] == absent["blocked_reasons"]


def test_a_cross_org_list_returns_nothing(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    assert list_digest_records(connection=connection, organization_id=OTHER)[
        "records"
    ] == []


def test_a_cross_org_archive_is_refused(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    result = archive_digest_record(
        connection=connection, organization_id=OTHER, digest_id="a" * 64
    )
    assert result["archived"] is False
    assert result["rows_written"] == 0


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


def test_an_archived_digest_stays_readable_by_id(connection):
    """An audit of a missed deadline needs the digest current at the time."""
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    archived = archive_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    assert archived["archived"] is True

    got = get_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    assert got["rows_read"] == 1
    assert got["record"]["archived_at"] is not None


def test_an_archived_digest_drops_out_of_the_live_list(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    archive_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    live = list_digest_records(connection=connection, organization_id=DEMO)
    assert live["records"] == []
    everything = list_digest_records(
        connection=connection, organization_id=DEMO, include_archived=True
    )
    assert len(everything["records"]) == 1


def test_archiving_twice_is_refused(connection):
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    archive_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    again = archive_digest_record(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    assert again["archived"] is False
    assert "no_live_digest_record_for_this_organization" in again["blocked_reasons"]


# ---------------------------------------------------------------------------
# the persistence service
# ---------------------------------------------------------------------------


def test_the_service_persists_and_reports_the_hash(connection):
    result = persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
    )
    assert result["persisted"] is True
    assert len(result["payload_sha256"]) == 64
    assert result["rendered_body_stored"] is False
    assert result["recipient_stored"] is False
    assert persistence_invariant_failures(result) == []


def test_the_service_refuses_a_digest_missing_a_required_field(connection):
    result = persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest={k: v for k, v in _digest().items() if k != "digest_id"},
        org_is_demo=True,
    )
    assert result["persisted"] is False
    assert "digest_missing_field:digest_id" in result["blocked_reasons"]


def test_the_service_refuses_a_payload_that_leaks_a_shape(connection):
    result = persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(tenant_id="somebody@example.org"),
        org_is_demo=True,
    )
    assert result["persisted"] is False
    assert "digest_payload_leaked:email_address" in result["blocked_reasons"]


def test_the_service_refuses_a_scope_it_does_not_serve(connection):
    result = persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(),
        org_is_demo=True,
        scope="production",
    )
    assert result["persisted"] is False
    assert any("scope_not_permitted" in r for r in result["blocked_reasons"])


def test_the_service_reads_back_with_the_hash_checked(connection):
    persist_digest(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    result = read_digest(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )
    assert result["found"] is True
    assert result["payload_hash_verified"] is True


def test_a_rendering_can_be_verified_against_the_stored_payload(connection):
    persist_digest(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    record = read_digest(
        connection=connection, organization_id=DEMO, digest_id="a" * 64
    )["record"]

    matching = verify_rendering(record=record)
    assert matching["verified"] is True
    assert matching["body_stored"] is False

    tampered = verify_rendering(record=record, rendered_from={"not": "the digest"})
    assert tampered["verified"] is False
    assert "payload_hash_mismatch" in tampered["blocked_reasons"]


def test_persisted_is_not_a_parameter():
    signature = inspect.signature(persist_digest)
    assert "persisted" not in signature.parameters
    assert "payload_sha256" not in signature.parameters


# ---------------------------------------------------------------------------
# delivery intent linkage
# ---------------------------------------------------------------------------


def test_the_queue_can_say_whether_the_digest_it_names_exists(connection):
    """The question Gate 150 could not answer."""
    from nativeforge.services.digest_delivery_dry_run_queue_service import (
        digest_record_exists,
    )

    assert (
        digest_record_exists(
            connection=connection, organization_id=DEMO, digest_id="a" * 64
        )
        is False
    )
    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    assert (
        digest_record_exists(
            connection=connection, organization_id=DEMO, digest_id="a" * 64
        )
        is True
    )


def test_the_linkage_check_is_org_scoped(connection):
    from nativeforge.services.digest_delivery_dry_run_queue_service import (
        digest_record_exists,
    )

    insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    assert (
        digest_record_exists(
            connection=connection, organization_id=OTHER, digest_id="a" * 64
        )
        is False
    )


def test_the_linkage_check_answers_false_rather_than_raising():
    """An absent table or connection is an environment fact, not a defect.

    It must answer False, not raise: a delivery intent recorded against an
    older database should get "no persisted digest", not a stack trace.
    """
    from nativeforge.services.digest_delivery_dry_run_queue_service import (
        digest_record_exists,
    )

    assert (
        digest_record_exists(connection=None, organization_id=DEMO, digest_id="x")
        is False
    )
    assert (
        digest_record_exists(connection=None, organization_id=None, digest_id=None)
        is False
    )


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def test_the_lane_is_live_with_every_condition_met():
    readiness = build_digest_persistence_readiness(
        **{name: True for name in CONDITIONS}
    )
    assert readiness["tenant_digest_persistence_live"] is True
    assert readiness["blockers"] == []
    assert readiness_invariant_failures(readiness) == []


@pytest.mark.parametrize("condition", sorted(CONDITIONS))
def test_removing_any_condition_blocks_the_lane(condition):
    supplied = {name: True for name in CONDITIONS}
    supplied[condition] = False
    readiness = build_digest_persistence_readiness(**supplied)
    assert readiness["tenant_digest_persistence_live"] is False
    assert f"condition_not_met:{condition}" in readiness["blockers"]


@pytest.mark.parametrize(
    "capability",
    ["email_delivery", "source_monitoring_live", "object_store_configured"],
)
def test_a_capability_being_on_blocks_the_lane(capability):
    readiness = build_digest_persistence_readiness(
        **{name: True for name in CONDITIONS}, **{capability: True}
    )
    assert readiness["tenant_digest_persistence_live"] is False
    assert f"must_be_false_but_is_true:{capability}" in readiness["blockers"]


@pytest.mark.parametrize(
    "counter", ["live_source_calls", "emails_sent", "object_store_calls"]
)
def test_contacting_anything_blocks_the_lane(counter):
    readiness = build_digest_persistence_readiness(
        **{name: True for name in CONDITIONS}, **{counter: 1}
    )
    assert readiness["tenant_digest_persistence_live"] is False
    assert f"something_was_contacted:{counter}" in readiness["blockers"]


def test_production_digest_persistence_is_never_true():
    for supplied in ({}, {name: True for name in CONDITIONS}):
        readiness = build_digest_persistence_readiness(**supplied)
        assert readiness["production_digest_persistence"] is False
        assert readiness["production_is_never_computed"] is True


def test_the_invariants_catch_a_forged_lane():
    readiness = build_digest_persistence_readiness()
    readiness["tenant_digest_persistence_live"] = True
    failures = readiness_invariant_failures(readiness)
    assert "live_alongside_blockers" in failures
    assert any(f.startswith("live_without:") for f in failures)


def test_every_condition_names_its_evidence():
    readiness = build_digest_persistence_readiness()
    for name in CONDITIONS:
        assert readiness["condition_evidence"][name].strip()


def test_the_lane_says_what_it_does_not_mean():
    readiness = build_digest_persistence_readiness(
        **{name: True for name in CONDITIONS}
    )
    joined = " ".join(readiness["what_this_does_not_mean"]).lower()
    assert "sent" in joined
    assert "live source" in joined
    assert "production" in joined


def test_the_must_stay_false_list_covers_the_three_capabilities():
    for name in ("email_delivery", "source_monitoring_live", "object_store_configured"):
        assert name in MUST_STAY_FALSE


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


def test_the_routes_refuse_an_unauthenticated_caller(client):
    assert client.post(f"{_base()}/persist", json={}).status_code == 401
    assert client.get(f"{_base()}/records").status_code == 401
    assert client.get(f"{_base()}/records/abc").status_code == 401
    assert client.post(f"{_base()}/records/abc/archive").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/records",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_persist_route_refuses_a_caller_supplied_label(client, demo_session):
    response = client.post(
        f"{_base()}/persist", headers=demo_session, json={"is_demo": False}
    )
    assert response.status_code == 422
    assert "caller_may_not_set" in json.dumps(response.json())


def test_the_records_route_is_org_scoped(client, demo_session):
    response = client.get(f"{_base(OTHER)}/records", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_a_missing_record_is_a_404(client, demo_session):
    response = client.get(f"{_base()}/records/{'z' * 64}", headers=demo_session)
    assert response.status_code == 404


def test_no_route_leaks_a_shape(client, demo_session):
    raw = client.get(f"{_base()}/records", headers=demo_session).text
    assert not ADDRESS_SHAPE.search(raw)
    assert not SUBJECT_SHAPE.search(raw)
    assert "nf_session=" not in raw


def test_no_real_organization_route_was_built():
    from nativeforge.api import tenant_digest_persistence_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    assert "/v1/nf/real" not in Path(routes.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# nothing is contacted
# ---------------------------------------------------------------------------


def test_no_module_in_this_gate_imports_a_mail_or_http_library():
    for path in (
        REPO_ROOT / "src/nativeforge/repositories/tenant_digest_records_repository.py",
        REPO_ROOT / "src/nativeforge/services/tenant_digest_persistence_service.py",
        REPO_ROOT
        / "src/nativeforge/services/tenant_digest_persistence_readiness_service.py",
    ):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("smtplib", "sendgrid", "requests", "httpx", "boto3"):
            assert forbidden not in source, path.name


def test_the_repository_reports_contacting_nothing(connection):
    result = insert_digest_record(
        connection=connection, organization_id=DEMO, digest=_digest(), org_is_demo=True
    )
    for flag in (
        "email_sent",
        "provider_contacted",
        "live_source_called",
        "object_store_contacted",
        "document_body_written",
        "real_organization_touched",
    ):
        assert result[flag] is False


def test_the_real_organization_has_no_digest_record():
    from nativeforge.db.session import engine

    with engine.connect() as conn:
        count = conn.execute(
            sa.text(
                f"SELECT count(*) FROM {TABLE_NAME} WHERE organization_id = :o"
            ),
            {"o": uuid.UUID(REAL).hex},
        ).scalar()
    assert count == 0


def test_no_tenant_supplied_digest_record_exists():
    """Gate 148's boundary: customer data needs a consent that does not exist."""
    from nativeforge.db.session import engine

    with engine.connect() as conn:
        count = conn.execute(
            sa.text(
                f"SELECT count(*) FROM {TABLE_NAME} "
                "WHERE fact_status = 'tenant_supplied'"
            )
        ).scalar()
    assert count == 0


def test_the_controlled_scope_is_the_only_one_served():
    assert CONTROLLED_SCOPE == "controlled_dev_demo"
