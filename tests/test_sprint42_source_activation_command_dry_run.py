"""Sprint 42: Activation command dry-run (no execution)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    FundingDomain,
    OpportunitySourceType,
    SourceHealthStatus,
    SourcePriorityLevel,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.discovery_operator_workbench_service import (
    build_operator_decision_pack,
)
from nativeforge.services.discovery_source_quality_service import (
    build_discovery_source_quality,
)
from nativeforge.services.source_activation_command_dry_run_service import (
    SCHEMA_VERSION as DRY_SCHEMA,
)
from nativeforge.services.source_activation_command_dry_run_service import (
    build_source_activation_command_dry_run,
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _post_source(
    client: TestClient,
    oid: uuid.UUID,
    *,
    name: str,
    source_type: str,
    **extra: object,
) -> str:
    payload: dict[str, object] = {
        "source_name": name,
        "source_type": source_type,
        "scope_global": True,
        "priority_level": SourcePriorityLevel.medium.value,
    }
    payload.update(extra)
    return client.post(
        f"/v1/nf/demo/orgs/{oid}/discovery/sources",
        json=payload,
        headers=_hdr(oid),
    ).json()["id"]


def _seed_diverse_registry(client_nf: TestClient, oid: uuid.UUID) -> None:
    _post_source(
        client_nf,
        oid,
        name="Fed Broad",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.education.value],
    )
    _post_source(
        client_nf,
        oid,
        name="Fed Native Specific",
        source_type=OpportunitySourceType.federal.value,
        funding_domains_json=[FundingDomain.language_culture.value],
    )
    _post_source(
        client_nf,
        oid,
        name="Tribal Gov",
        source_type=OpportunitySourceType.tribal.value,
    )
    _post_source(
        client_nf,
        oid,
        name="State Local",
        source_type=OpportunitySourceType.state.value,
        native_relevance_notes="Native communities statewide",
    )
    _post_source(
        client_nf,
        oid,
        name="University",
        source_type=OpportunitySourceType.university.value,
    )
    _post_source(
        client_nf,
        oid,
        name="AK Native",
        source_type=OpportunitySourceType.nonprofit.value,
        covered_states_json=["AK"],
        applicant_types_json=["alaska_native_corporation"],
    )
    _post_source(
        client_nf,
        oid,
        name="Foundation",
        source_type=OpportunitySourceType.foundation.value,
    )
    _post_source(
        client_nf,
        oid,
        name="Corporate Phil",
        source_type=OpportunitySourceType.corporate.value,
    )


def _commands_by_lane(dry: dict[str, object], lane: str) -> list[dict[str, object]]:
    return [c for c in dry["dry_run_commands"] if c["lane"] == lane]


def _expected_cmd_id(organization_id: str, artifact_id: str, candidate_id: str) -> str:
    payload = "|".join(
        (organization_id, artifact_id, candidate_id, DRY_SCHEMA)
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return f"nf_src_act_cmd_dry_v1_{digest[:24]}"


def test_empty_critical_org_command_dry_run_zeros(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    assert dry["schema_version"] == DRY_SCHEMA
    cp = dry["command_posture"]
    assert cp["source_quality_posture"] == "critical"
    assert dry["dry_run_commands"]
    assert cp["signed_approval_count"] == 0
    assert cp["executable_command_count"] == 0
    assert cp["actual_activation_count"] == 0
    assert cp["actual_database_write_count"] == 0
    gb = dry["global_command_boundary"]
    assert gb["signed_approval_count"] == 0
    assert gb["executable_command_count"] == 0
    assert gb["actual_activation_count"] == 0
    assert gb["actual_database_write_count"] == 0


def test_federal_native_specific_ready_after_signature_not_executable(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed Seed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    fed = _commands_by_lane(dry, "federal_native_specific")
    ready = [
        r
        for r in fed
        if r["approval_status"] == "unsigned_conditionally_ready"
        and r["command_status"] == "dry_run_ready_after_signature"
    ]
    assert ready
    for r in ready:
        assert r["dry_run_boundary"]["may_execute_command_now"] is False
        assert r["dry_run_boundary"]["requires_signed_human_approval"] is True
        assert r["should_create_action"] is False


def test_broad_native_eligible_review_required(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Keyword Native",
        source_type=OpportunitySourceType.private.value,
        native_relevance_notes="native community keyword",
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    broad = _commands_by_lane(dry, "general_broad_with_native_eligibility")
    assert broad
    for row in broad:
        assert row["command_status"] in (
            "dry_run_blocked_unsigned_approval",
            "dry_run_not_ready",
            "dry_run_blocked_missing_evidence",
        )
        blocker_blob = " ".join(row["unresolved_blockers"]).lower()
        assert (
            "broad_native_catalog_eligibility_requires_explicit_human_confirmation"
            in blocker_blob
        )


def test_keyword_paths_not_ready_acknowledgment(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Keyword Native",
        source_type=OpportunitySourceType.private.value,
        native_relevance_notes="native community keyword",
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    broad = _commands_by_lane(dry, "general_broad_with_native_eligibility")
    for r in broad:
        if r["approval_status"] == "unsigned_not_ready":
            misses = " ".join(r["missing_pre_execution_requirements"]).lower()
            assert "keyword" in misses or "not_confirmed_eligible" in misses


def test_foundation_corporate_university_keeps_review_requirements(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    for i in range(4):
        _post_source(
            client_nf,
            oid,
            name=f"Fed Only {i}",
            source_type=OpportunitySourceType.federal.value,
        )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    for lane in (
        "foundation_native_serving",
        "corporate_philanthropy",
        "university_research",
    ):
        rows = _commands_by_lane(dry, lane)
        assert rows
        r0 = rows[0]
        miss_blob = " ".join(r0["missing_pre_execution_requirements"]).lower()
        fields_blob = json.dumps(r0["required_signed_approval_fields"]).lower()
        status = str(r0["command_status"])
        assert status in (
            "dry_run_blocked_legal_tos",
            "dry_run_blocked_missing_evidence",
            "dry_run_blocked_unsigned_approval",
            "dry_run_not_ready",
        )
        assert (
            r0["proposed_active_source_record_snapshot"].get(
                "proposed_collection_method"
            )
            == "manual_review_only"
            or status == "dry_run_blocked_legal_tos"
        )
        assert "legal_tos_acknowledgment" in fields_blob or "legal_tos" in miss_blob


def test_strong_posture_conservative_language(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    future = datetime.now(UTC) + timedelta(days=30)
    with SessionLocal() as s:
        rows = ods.list_sources(s, org_id=oid, org_type="demo")
        for r in rows:
            r.source_health_status = SourceHealthStatus.healthy.value
            r.last_checked_at = datetime.now(UTC)
            r.next_check_due_at = future
        s.commit()
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    if sq["posture"] != "strong":
        pytest.skip("fixture did not reach strong posture in this environment")

    dry = sq["source_activation_command_dry_run"]
    blob = dry["summary"].lower() + json.dumps(dry["command_batches"]).lower()
    assert "urgent activation" not in blob


def test_global_command_boundary_denies_execution_surfaces(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    gb = sq["source_activation_command_dry_run"]["global_command_boundary"]
    assert gb["command_dry_run_only"] is True
    assert gb["signed_approval_count"] == 0
    assert gb["executable_command_count"] == 0
    assert gb["actual_activation_count"] == 0
    assert gb["actual_database_write_count"] == 0
    assert gb["may_execute_commands_now"] is False
    assert gb["may_persist_approvals_now"] is False
    assert gb["may_activate_sources_now"] is False
    assert gb["may_write_database_rows_now"] is False
    assert gb["may_scrape_now"] is False
    assert gb["may_ingest_now"] is False
    assert gb["may_call_external_apis_now"] is False
    assert gb["may_create_ledger_actions_now"] is False


def test_every_command_dry_run_flags_and_should_create_action_false(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _seed_diverse_registry(client_nf, oid)

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    for c in dry["dry_run_commands"]:
        db = c["dry_run_boundary"]
        assert db["command_is_dry_run_only"] is True
        assert db["may_execute_command_now"] is False
        assert db["may_persist_approval_now"] is False
        assert db["may_activate_source_now"] is False
        assert db["may_write_database_rows_now"] is False
        assert db["may_start_ingestion_now"] is False
        assert c["can_become_active_source"] is False
        assert c["should_create_action"] is False

    for b in dry["command_batches"]["ordered_batches"]:
        assert b["dry_run_only"] is True
        assert b["should_create_action"] is False


def test_proposed_snapshot_dry_run_not_persisted(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    c0 = sq["source_activation_command_dry_run"]["dry_run_commands"][0]
    snap = c0["proposed_active_source_record_snapshot"]
    assert snap["proposed_activation_mode"] == "future_human_approved_only"
    assert c0["dry_run_only"] is True


def test_dry_run_command_id_deterministic(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    ha = sq["source_human_approval_artifact"]
    org_s = str(oid)
    by_cid_a = {a["candidate_id"]: a for a in ha["approval_artifacts"]}

    for c in dry["dry_run_commands"]:
        cid = str(c["candidate_id"])
        aid = str(by_cid_a[cid]["approval_artifact_id"])
        assert c["dry_run_command_id"] == _expected_cmd_id(org_s, aid, cid)


def test_payload_json_serializable(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    json.dumps(sq["source_activation_command_dry_run"])


def test_source_quality_includes_activation_command_dry_run(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dr = sq["source_activation_command_dry_run"]
    assert dr["schema_version"] == DRY_SCHEMA


def test_cross_org_isolation_activation_command_dry_run(
    client_nf: TestClient,
) -> None:
    oid_a = uuid.uuid4()
    oid_b = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid_a, org_type="demo"))
        s.add(Organization(id=oid_b, org_type="demo"))
        s.commit()

    client_nf.post(
        f"/v1/nf/demo/orgs/{oid_a}/discovery/sources",
        json={
            "source_name": "ORG_A_ONLY",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": False,
            "priority_level": SourcePriorityLevel.medium.value,
        },
        headers=_hdr(oid_a),
    )

    with SessionLocal() as s:
        sq_b = build_discovery_source_quality(s, org_id=oid_b, org_type="demo")

    blob = json.dumps(sq_b["source_activation_command_dry_run"])
    assert "ORG_A_ONLY" not in blob


def test_no_delete_remove_shrink_language_in_dry_run(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    for i in range(5):
        _post_source(
            client_nf,
            oid,
            name=f"Fed Dup {i}",
            source_type=OpportunitySourceType.federal.value,
        )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    blob = json.dumps(sq["source_activation_command_dry_run"]).lower()
    assert "delete" not in blob and "remove" not in blob and "shrink" not in blob


def test_standalone_build_without_embedded_human_approval_artifact(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    sq2 = dict(sq)
    del sq2["source_human_approval_artifact"]
    dry = build_source_activation_command_dry_run(sq2)
    assert dry["schema_version"] == DRY_SCHEMA


def test_workbench_source_quality_includes_activation_command_dry_run(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        pack = build_operator_decision_pack(s, org_id=oid, org_type="demo")

    sq = pack["source_quality"]
    assert "source_activation_command_dry_run" in sq


def test_rollback_plan_on_every_command(
    client_nf: TestClient,
) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    _post_source(
        client_nf,
        oid,
        name="Fed",
        source_type=OpportunitySourceType.federal.value,
    )

    with SessionLocal() as s:
        sq = build_discovery_source_quality(s, org_id=oid, org_type="demo")

    dry = sq["source_activation_command_dry_run"]
    for c in dry["dry_run_commands"]:
        rp = c["rollback_plan"]
        assert rp["disable_active_source_required"] is True
        assert rp["rollback_test_required_before_activation"] is True
