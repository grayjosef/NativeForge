"""Gate 152: audit replay, the evidence ledger, and the guard that did not guard.

Gate 151 added `digest_id_names_no_persisted_digest` to the wrong list. It
appeared in the result and gated nothing, because `record_delivery_intent`
writes on `decision["storage_allowed"]`, which `prepare_delivery_intent`
computes from its own blockers and cannot know about persistence - it takes no
connection, deliberately.

It shipped looking correct because Gate 151's verifier exercised
`digest_record_exists` directly rather than driving the write path, and it
briefly read green here for a second reason: an invalid recipient fingerprint
was refusing the write on unrelated grounds. Every enforcement test below uses a
VALID fingerprint, so the digest linkage is the only thing that can refuse.

The other half of this gate is that a replay must never manufacture what it
cannot find. The 85 legacy intents stay `legacy_gap`.
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

from nativeforge.domain.enums import AuditAction
from nativeforge.main import create_app
from nativeforge.repositories.audit_events import append_org_audit_event
from nativeforge.repositories.tenant_digest_records_repository import (
    TABLE_NAME,
    payload_sha256,
)
from nativeforge.services import (
    audit_replay_artifact_gate152_service as art,
)
from nativeforge.services.audit_replay_readiness_service import (
    CONDITIONS,
    build_audit_replay_readiness,
    readiness_invariant_failures,
)
from nativeforge.services.audit_replay_service import (
    find_legacy_gaps,
    replay_delivery_intent,
    replay_digest,
    replay_invariant_failures,
)
from nativeforge.services.digest_delivery_dry_run_queue_service import (
    record_delivery_intent,
)
from nativeforge.services.evidence_ledger_service import (
    EVIDENCE_TYPES,
    build_evidence_ledger,
    ledger_invariant_failures,
)
from nativeforge.services.evidence_status_vocabulary_service import (
    ATTESTED,
    BLOCKED,
    EVIDENCE_STATUSES,
    HASH_VERIFIED,
    LEGACY_GAP,
    LINKED_RECORD_FOUND,
    MISSING_RECORD,
    NON_PROVING_STATUSES,
    PROVING_STATUSES,
    UNKNOWN,
    build_vocabulary,
    is_proof,
    normalize,
    vocabulary_invariant_failures,
    weakest,
)
from nativeforge.services.tenant_digest_persistence_service import persist_digest
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER = "cccccccc-dddd-eeee-ffff-000000000152"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

#: A valid fingerprint on every enforcement call. The earlier false green came
#: from an invalid one refusing the write for an unrelated reason.
VALID_FINGERPRINT = "a" * 32


def _digest(digest_id: str) -> dict:
    return {
        "digest_id": digest_id,
        "tenant_id": "nf-test-gate152",
        "cadence": "weekly",
        "period_start": "2026-09-07",
        "period_end": "2026-09-13",
        "digest_period_key": "2026-09-07..2026-09-13",
        "snapshot_ids": ["nf-test-gate152-snapshot"],
        "items_total": 5,
        "items_visible": 3,
        "items_suppressed": 2,
        "items_human_review": 1,
        "items_with_unverified_deadlines": 1,
        "items_with_unknown_reporting_burden": 2,
        "caveats": ["deadline_unverified"],
        "blocked_reasons": ["items_suppressed:2"],
        "delivery_status": "preview_only",
    }


def _intent_kwargs(**overrides) -> dict:
    kwargs = dict(
        organization_id=DEMO,
        cadence="weekly",
        recipient_fingerprint=VALID_FINGERPRINT,
        recipient_domain="example.invalid",
        recipient_source="controlled_fixture",
        recipient_verified=True,
        items_total=5,
        items_visible=3,
        digest_deliverable=True,
        is_demo=True,
        fact_status="demo_fixture",
    )
    kwargs.update(overrides)
    return kwargs


@pytest.fixture
def connection(db_session):
    return db_session.connection()


@pytest.fixture
def db_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_org(DEMO, "demo")
    with SessionLocal() as session:
        yield session
        session.rollback()


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


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/audit-replay"


# ---------------------------------------------------------------------------
# the vocabulary
# ---------------------------------------------------------------------------


def test_ten_statuses_are_defined():
    assert len(EVIDENCE_STATUSES) == 10
    vocabulary = build_vocabulary()
    assert vocabulary["status_count"] == 10
    assert vocabulary_invariant_failures(vocabulary) == []


def test_the_vocabulary_is_deterministic():
    assert build_vocabulary() == build_vocabulary()


def test_only_three_statuses_are_proof():
    assert PROVING_STATUSES == {ATTESTED, HASH_VERIFIED, LINKED_RECORD_FOUND}
    for status in NON_PROVING_STATUSES:
        assert not is_proof(status), status


@pytest.mark.parametrize("status", sorted(NON_PROVING_STATUSES))
def test_a_gap_or_unknown_is_never_proof(status):
    """`unknown` and `legacy_gap` are the two most likely to be skimmed past."""
    assert not is_proof(status)


def test_a_chain_is_as_good_as_its_weakest_link():
    assert weakest([HASH_VERIFIED, LINKED_RECORD_FOUND]) == LINKED_RECORD_FOUND
    assert weakest([HASH_VERIFIED, LEGACY_GAP]) == LEGACY_GAP
    assert weakest([ATTESTED, UNKNOWN]) == UNKNOWN


def test_an_empty_chain_is_unknown_not_attested():
    """Nothing examined is not the same as nothing wrong."""
    assert weakest([]) == UNKNOWN


def test_the_vocabulary_is_closed():
    """A closed vocabulary that emits an outside value is not closed."""
    assert normalize("made_up") == BLOCKED
    assert normalize(None) == BLOCKED
    assert weakest(["made_up"]) in EVIDENCE_STATUSES


def test_every_status_says_what_would_make_it_proof():
    definitions = build_vocabulary()["definitions"]
    for status in EVIDENCE_STATUSES:
        assert definitions[status]["becomes_proof_when"].strip()


# ---------------------------------------------------------------------------
# the guard that did not guard
# ---------------------------------------------------------------------------


def test_an_intent_naming_an_unpersisted_digest_is_refused_end_to_end(connection):
    """Gate 151's blocker reported and did not block. This drives the write."""
    result = record_delivery_intent(
        connection=connection,
        digest_id="nf-test-gate152-never-persisted",
        digest_period_key="2026-01-01..2026-01-07",
        require_persisted_digest=True,
        **_intent_kwargs(),
    )
    assert result["rows_written"] == 0
    assert result["storage_allowed"] is False
    assert "digest_id_names_no_persisted_digest" in result["blocked_reasons"]


def test_the_refusal_is_not_caused_by_the_fingerprint(connection):
    """The earlier green was an invalid fingerprint refusing for another reason.

    Same call, same valid fingerprint, with the digest persisted: it writes. So
    the fingerprint cannot be what refused the case above.
    """
    digest_id = "nf-test-gate152-" + ("w" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    result = record_delivery_intent(
        connection=connection,
        digest_id=digest_id,
        digest_period_key="2026-09-07..2026-09-13",
        require_persisted_digest=True,
        **_intent_kwargs(),
    )
    assert result["rows_written"] == 1
    assert result["storage_allowed"] is True
    assert result["blocked_reasons"] == []
    assert result["digest_record_persisted"] is True


def test_storage_allowed_agrees_with_the_blocker_list(connection):
    """Three fields, and all three must say the same thing.

    The reported `storage_allowed` came from `**decision`, computed before the
    digest linkage was known - so it could read True beside a blocker and
    rows_written 0.
    """
    refused = record_delivery_intent(
        connection=connection,
        digest_id="nf-test-gate152-absent",
        digest_period_key="2026-03-01..2026-03-07",
        require_persisted_digest=True,
        **_intent_kwargs(),
    )
    assert refused["storage_allowed"] is bool(refused["rows_written"])
    assert refused["storage_allowed"] is not bool(refused["blocked_reasons"])


def test_enforcement_off_still_writes(connection):
    """Gate 142's callers pass no persisted digest and are correct as written."""
    result = record_delivery_intent(
        connection=connection,
        digest_id="nf-test-gate152-legacy-shape",
        digest_period_key="2026-04-01..2026-04-07",
        require_persisted_digest=False,
        **_intent_kwargs(recipient_fingerprint="b" * 32),
    )
    assert result["rows_written"] == 1
    assert result["digest_record_persisted"] is False
    assert result["digest_linkage_enforced"] is False


# ---------------------------------------------------------------------------
# replay
# ---------------------------------------------------------------------------


def test_a_persisted_digest_replays_with_its_hash(connection):
    digest_id = "nf-test-gate152-" + ("h" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    result = replay_digest(
        connection=connection, organization_id=DEMO, digest_id=digest_id
    )
    assert result["found"] is True
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["digest_record"] == LINKED_RECORD_FOUND
    assert links["payload_hash"] == HASH_VERIFIED
    assert replay_invariant_failures(result) == []


def test_a_tampered_payload_fails_verification(connection):
    digest_id = "nf-test-gate152-" + ("t" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    connection.execute(
        sa.text(
            f"UPDATE {TABLE_NAME} SET payload_sha256 = :bad "
            "WHERE organization_id = :o AND digest_id = :d"
        ),
        {"bad": "0" * 64, "o": uuid.UUID(DEMO).hex, "d": digest_id},
    )
    result = replay_digest(
        connection=connection, organization_id=DEMO, digest_id=digest_id
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["payload_hash"] != HASH_VERIFIED
    assert result["evidence_status"] in NON_PROVING_STATUSES


def test_a_digest_with_no_delivery_intent_is_reported_honestly(connection):
    digest_id = "nf-test-gate152-" + ("n" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    result = replay_digest(
        connection=connection, organization_id=DEMO, digest_id=digest_id
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["delivery_intent"] == "not_replayable"
    assert "delivery_intent" in result["evidence_gaps"]


def test_a_missing_digest_is_not_fabricated(connection):
    result = replay_digest(
        connection=connection, organization_id=DEMO, digest_id="z" * 60
    )
    assert result["found"] is False
    assert result.get("record") is None
    assert result["evidence_fabricated"] is False
    assert result["evidence_status"] == MISSING_RECORD


def test_a_fully_linked_intent_replays_every_link(connection, db_session):
    digest_id = "nf-test-gate152-" + ("f" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    event = append_org_audit_event(
        db_session,
        organization_id=uuid.UUID(DEMO),
        is_demo=True,
        action=AuditAction.digest_delivery_intent_recorded,
        payload={"fixture": "gate152"},
        actor_id=None,
    )
    db_session.flush()

    intent_id = uuid.uuid4()
    record_delivery_intent(
        connection=connection,
        intent_id=intent_id,
        digest_id=digest_id,
        digest_period_key="2026-09-07..2026-09-13",
        require_persisted_digest=True,
        audit_event_id=str(event.id),
        **_intent_kwargs(),
    )

    result = replay_delivery_intent(
        connection=connection, organization_id=DEMO, intent_id=str(intent_id)
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["delivery_intent"] == LINKED_RECORD_FOUND
    assert links["digest_record"] == LINKED_RECORD_FOUND
    assert links["payload_hash"] == HASH_VERIFIED
    assert links["audit_event"] == LINKED_RECORD_FOUND
    assert result["evidence_status"] in PROVING_STATUSES
    assert replay_invariant_failures(result) == []


def test_a_dangling_audit_event_id_is_reported_as_missing(connection):
    """The negative case, kept here rather than in the verifier's happy path.

    A verifier that referenced a random audit id would be manufacturing a
    broken link and then congratulating itself for detecting it.
    """
    digest_id = "nf-test-gate152-" + ("d" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    intent_id = uuid.uuid4()
    record_delivery_intent(
        connection=connection,
        intent_id=intent_id,
        digest_id=digest_id,
        digest_period_key="2026-09-07..2026-09-13",
        require_persisted_digest=True,
        audit_event_id=str(uuid.uuid4()),
        **_intent_kwargs(),
    )
    result = replay_delivery_intent(
        connection=connection, organization_id=DEMO, intent_id=str(intent_id)
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["audit_event"] == MISSING_RECORD
    assert "audit_event" in result["evidence_gaps"]
    assert result["evidence_status"] in NON_PROVING_STATUSES


def test_a_legacy_intent_is_a_legacy_gap_not_a_missing_record(
    connection, db_session
):
    """It is not wrong; it was un-storable at the time.

    The intent gets a real audit event so the digest link is the only
    non-proving one. Without it the audit link reads `unknown`, which ranks
    WORSE than `legacy_gap` and would dominate the chain - the weakest-link
    rule working correctly, and not what this test is about.
    """
    event = append_org_audit_event(
        db_session,
        organization_id=uuid.UUID(DEMO),
        is_demo=True,
        action=AuditAction.digest_delivery_intent_recorded,
        payload={"fixture": "gate152-legacy"},
        actor_id=None,
    )
    db_session.flush()

    intent_id = uuid.uuid4()
    record_delivery_intent(
        connection=connection,
        intent_id=intent_id,
        digest_id="nf-test-gate152-legacy",
        digest_period_key="2026-05-01..2026-05-07",
        require_persisted_digest=False,
        audit_event_id=str(event.id),
        **_intent_kwargs(recipient_fingerprint="c" * 32),
    )
    result = replay_delivery_intent(
        connection=connection, organization_id=DEMO, intent_id=str(intent_id)
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["digest_record"] == LEGACY_GAP
    assert links["audit_event"] == LINKED_RECORD_FOUND
    assert result["evidence_status"] == LEGACY_GAP


def test_an_unknown_link_outranks_a_legacy_gap(connection):
    """An intent naming no audit event is `unknown`, which is weaker still.

    Ranking `unknown` below every gap is deliberate: a chain must not read
    green, or even amber, through a link nobody determined.
    """
    intent_id = uuid.uuid4()
    record_delivery_intent(
        connection=connection,
        intent_id=intent_id,
        digest_id="nf-test-gate152-nounknown",
        digest_period_key="2026-07-01..2026-07-07",
        require_persisted_digest=False,
        **_intent_kwargs(recipient_fingerprint="e" * 32),
    )
    result = replay_delivery_intent(
        connection=connection, organization_id=DEMO, intent_id=str(intent_id)
    )
    links = {link["link"]: link["status"] for link in result["links"]}
    assert links["digest_record"] == LEGACY_GAP
    assert links["audit_event"] == UNKNOWN
    assert result["evidence_status"] == UNKNOWN


def test_cross_org_replay_is_refused_indistinguishably(connection):
    digest_id = "nf-test-gate152-" + ("x" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    theirs = replay_digest(
        connection=connection, organization_id=OTHER, digest_id=digest_id
    )
    absent = replay_digest(
        connection=connection, organization_id=OTHER, digest_id="q" * 60
    )
    assert theirs["found"] is False
    assert theirs["blocked_reasons"] == absent["blocked_reasons"]


def test_the_real_organization_is_refused_by_name(connection):
    result = replay_digest(
        connection=connection, organization_id=REAL, digest_id="z" * 60
    )
    assert "real_organization_refused_by_name" in result["blocked_reasons"]
    assert result["real_organization_touched"] is False


def test_a_replay_writes_nothing_on_any_branch(connection):
    for result in (
        replay_digest(connection=connection, organization_id=DEMO, digest_id="z" * 60),
        replay_delivery_intent(
            connection=connection, organization_id=DEMO, intent_id=str(uuid.uuid4())
        ),
        replay_digest(connection=connection, organization_id=REAL, digest_id="z" * 60),
    ):
        assert result["rows_written"] == 0
        assert result["evidence_fabricated"] is False
        assert result["email_sent"] is False
        assert result["live_source_called"] is False
        assert result["object_store_contacted"] is False


def test_the_invariants_catch_a_forged_attestation(connection):
    result = replay_digest(
        connection=connection, organization_id=DEMO, digest_id="z" * 60
    )
    result["evidence_status"] = ATTESTED
    failures = replay_invariant_failures(result)
    assert "evidence_status_is_not_the_weakest_link" in failures


# ---------------------------------------------------------------------------
# the evidence ledger
# ---------------------------------------------------------------------------


def test_the_ledger_carries_all_three_evidence_types(connection, db_session):
    digest_id = "nf-test-gate152-" + ("l" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    event = append_org_audit_event(
        db_session,
        organization_id=uuid.UUID(DEMO),
        is_demo=True,
        action=AuditAction.digest_delivery_intent_recorded,
        payload={"fixture": "gate152"},
        actor_id=None,
    )
    db_session.flush()
    record_delivery_intent(
        connection=connection,
        digest_id=digest_id,
        digest_period_key="2026-09-07..2026-09-13",
        require_persisted_digest=True,
        audit_event_id=str(event.id),
        **_intent_kwargs(),
    )

    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=300
    )
    assert set(ledger["by_type"]) <= set(EVIDENCE_TYPES)
    for evidence_type in EVIDENCE_TYPES:
        assert evidence_type in ledger["by_type"], evidence_type
    assert ledger_invariant_failures(ledger) == []


def test_every_ledger_entry_carries_its_limitations(connection):
    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=50
    )
    for entry in ledger["entries"]:
        assert entry["replay_limitations"], entry["record_id"]


def test_the_ledger_hash_agrees_with_the_repository(connection):
    """A raw JSON column read returns a str on SQLite; only the typed path parses.

    The first version hashed the raw value and reported a sound digest as
    `missing_record` - a false negative in an audit ledger.
    """
    digest_id = "nf-test-gate152-" + ("j" * 20)
    persist_digest(
        connection=connection,
        organization_id=DEMO,
        digest=_digest(digest_id),
        org_is_demo=True,
    )
    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=300
    )
    entry = next(
        e for e in ledger["entries"] if e["record_id"] == digest_id
    )
    assert entry["evidence_status"] == HASH_VERIFIED


def test_the_ledger_overall_status_is_the_weakest_entry(connection):
    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=300
    )
    assert ledger["overall_status"] == weakest(
        [entry["evidence_status"] for entry in ledger["entries"]]
    )


def test_the_ledger_names_what_it_excludes():
    from nativeforge.services.evidence_ledger_service import EXCLUDED_SOURCES

    sources = {entry["source"] for entry in EXCLUDED_SOURCES}
    assert "nf_award_requirement_proof_events" in sources
    for entry in EXCLUDED_SOURCES:
        assert entry["why"].strip()


def test_the_ledger_refuses_the_real_organization(connection):
    ledger = build_evidence_ledger(connection=connection, organization_id=REAL)
    assert ledger["entries"] == []
    assert "real_organization_refused_by_name" in ledger["blocked_reasons"]


def test_the_ledger_exposes_no_address_or_subject(connection):
    ledger = build_evidence_ledger(
        connection=connection, organization_id=DEMO, limit=300
    )
    assert ledger["leaked_shapes"] == []
    body = json.dumps(ledger, default=str)
    assert not ADDRESS_SHAPE.search(body)
    assert not SUBJECT_SHAPE.search(body)


# ---------------------------------------------------------------------------
# legacy gaps
# ---------------------------------------------------------------------------


def test_legacy_gaps_are_counted_and_not_backfilled(connection):
    gaps = find_legacy_gaps(connection=connection, organization_id=DEMO)
    assert gaps["backfilled"] is False
    assert gaps["why_not_backfilled"].strip()
    assert gaps["legacy_gap_count"] >= 0


def test_a_gap_count_above_zero_reads_legacy_gap(connection):
    record_delivery_intent(
        connection=connection,
        digest_id="nf-test-gate152-gapmaker",
        digest_period_key="2026-06-01..2026-06-07",
        require_persisted_digest=False,
        **_intent_kwargs(recipient_fingerprint="d" * 32),
    )
    gaps = find_legacy_gaps(connection=connection, organization_id=DEMO)
    assert gaps["legacy_gap_count"] >= 1
    assert gaps["evidence_status"] == LEGACY_GAP


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def test_readiness_is_true_when_every_condition_is_met():
    readiness = build_audit_replay_readiness(
        tenant_digest_persistence_live=True,
        digest_hash_verification_works=True,
        delivery_intent_linkage_works=True,
        legacy_gaps_reported=True,
        evidence_ledger_generates=True,
        cross_org_replay_refused=True,
        legacy_gap_count=85,
        legacy_gaps_backfilled=False,
    )
    assert readiness["audit_replay_ready"] is True
    assert readiness["production_audit_ready"] is False
    assert readiness_invariant_failures(readiness) == []


@pytest.mark.parametrize("condition", sorted(CONDITIONS))
def test_removing_any_condition_blocks_the_lane(condition):
    kwargs = {
        "tenant_digest_persistence_live": True,
        "digest_hash_verification_works": True,
        "delivery_intent_linkage_works": True,
        "legacy_gaps_reported": True,
        "evidence_ledger_generates": True,
        "cross_org_replay_refused": True,
    }
    kwargs[condition] = False
    readiness = build_audit_replay_readiness(**kwargs)
    assert readiness["audit_replay_ready"] is False
    assert condition in readiness["conditions_missing"]


def test_a_backfill_fails_the_lane_rather_than_passing_it():
    """Reporting a gap is a condition. Hiding one is a failure."""
    readiness = build_audit_replay_readiness(
        tenant_digest_persistence_live=True,
        digest_hash_verification_works=True,
        delivery_intent_linkage_works=True,
        legacy_gaps_reported=True,
        evidence_ledger_generates=True,
        cross_org_replay_refused=True,
        legacy_gaps_backfilled=True,
    )
    assert readiness["audit_replay_ready"] is False
    assert "legacy_gaps_were_backfilled" in readiness["blockers"]


def test_production_audit_readiness_is_never_true():
    for backfilled in (True, False):
        readiness = build_audit_replay_readiness(legacy_gaps_backfilled=backfilled)
        assert readiness["production_audit_ready"] is False


def test_readiness_is_not_a_parameter():
    signature = inspect.signature(build_audit_replay_readiness)
    assert "audit_replay_ready" not in signature.parameters
    assert "production_audit_ready" not in signature.parameters


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["readiness", "ledger", "digest/abc", "delivery-intent/abc"]
)
def test_every_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/ledger",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_the_lane(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    data = body.get("data", body)
    assert data["audit_replay_ready"] is True
    assert data["production_audit_ready"] is False
    assert data["legacy_gaps_backfilled"] is False


def test_the_ledger_route_reports_gaps(client, demo_session):
    body = client.get(f"{_base()}/ledger", headers=demo_session).json()
    data = body.get("data", body)
    assert data["legacy_gaps_backfilled"] is False
    assert data["evidence_fabricated"] is False
    assert data["overall_status"] in EVIDENCE_STATUSES


def test_a_missing_digest_route_is_404_not_a_fabrication(client, demo_session):
    response = client.get(f"{_base()}/digest/{'z' * 60}", headers=demo_session)
    assert response.status_code == 404


def test_the_routes_are_get_only():
    from nativeforge.api import audit_replay_routes as routes

    methods = set()
    for route in routes.router.routes:
        methods |= set(getattr(route, "methods", set()))
    assert methods == {"GET"}


def test_no_route_leaks_a_shape(client, demo_session):
    for path in ("readiness", "ledger"):
        raw = client.get(f"{_base()}/{path}", headers=demo_session).text
        assert not ADDRESS_SHAPE.search(raw)
        assert not SUBJECT_SHAPE.search(raw)
        assert "nf_session=" not in raw


def test_no_real_organization_route_was_built():
    from nativeforge.api import audit_replay_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    assert "/v1/nf/real" not in Path(routes.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_audit_replay_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.audit_replay_artifact_invariant_failures(result) == []


def test_the_artifact_is_deterministic():
    assert art.build_audit_replay_artifacts() == art.build_audit_replay_artifacts()


def test_the_artifact_reads_no_database():
    builder = art.build_audit_replay_artifacts
    assert inspect.signature(builder).parameters == {}


def test_the_artifacts_record_the_enforcement_defect():
    files = art.build_audit_replay_artifacts()
    survey = json.loads(files[art.SURVEY_FILE])
    assert survey["gate_151_defect"]["reported_without_enforcing"] is True
    assert survey["gate_151_defect"]["fixed_in_gate"] == "152"


def test_the_artifacts_record_the_legacy_gaps_unbackfilled():
    files = art.build_audit_replay_artifacts()
    gaps = json.loads(files[art.GAPS_FILE])
    assert gaps["backfilled"] is False
    assert gaps["why_not_backfilled"].strip()


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_audit_replay_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_audit_replay_artifacts().items():
        assert (directory / name).read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# nothing else moved
# ---------------------------------------------------------------------------


def test_no_real_organization_digest_or_intent_exists(connection):
    for table, column in (
        (TABLE_NAME, "organization_id"),
        ("nf_digest_delivery_intents", "organization_id"),
    ):
        count = connection.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {column} = :o"),
            {"o": uuid.UUID(REAL).hex},
        ).scalar()
        assert count == 0, table


def test_nothing_was_sent(connection):
    sent = connection.execute(
        sa.text(
            "SELECT COALESCE(SUM(emails_sent), 0) FROM nf_digest_delivery_intents"
        )
    ).scalar()
    contacted = connection.execute(
        sa.text(
            "SELECT count(*) FROM nf_digest_delivery_intents "
            "WHERE provider_contacted = 1"
        )
    ).scalar()
    assert sent == 0
    assert contacted == 0


def test_the_payload_hash_helper_is_stable():
    payload = {"b": 2, "a": 1}
    assert payload_sha256(payload) == payload_sha256({"a": 1, "b": 2})
