"""Mission Control: org-wide work intelligence from canonical pursuit records."""

from __future__ import annotations

import uuid

import pytest
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.db.session import SessionLocal
from nativeforge.main import create_app
from nativeforge.services import funder_interaction_service as ixn
from nativeforge.services.dev_org_membership_bootstrap_service import MEMBERSHIPS
from nativeforge.services.mission_control_service import assemble_mission_control
from nativeforge.services.pursuit_command_center_service import assemble_command_center
from tests import session_org_helper as soh

NOTICE = """
Questions must be submitted no later than October 1, 2026.
Send questions to questions@hud.gov.
"""


def _org():
    org_id = uuid.uuid4()
    with SessionLocal() as session:
        session.connection().execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at)"
                " VALUES (:i, 'demo', 5, CURRENT_TIMESTAMP)"
            ),
            {"i": org_id.hex},
        )
        session.commit()
    return org_id


def _spark(org_id, *, title="Grant", agency="HUD", deadline=None, text=""):
    spark_id = uuid.uuid4()
    with SessionLocal() as session:
        session.connection().execute(
            sa.text(
                "INSERT INTO nf_grant_sparks ("
                " id, organization_id, is_demo, source, source_id, agency,"
                " opportunity_title, award_type, match_required,"
                " match_waiver_available, indirect_cost_allowable,"
                " tribal_eligible, pipeline_stage, raw_nofo_text,"
                " application_deadline"
                ") VALUES ("
                " :s, :o, 1, 'manual', :sid, :agency,"
                " :title, 'grant', 0, 0, 1, 1, 'new', :text, :deadline)"
            ),
            {
                "s": spark_id.hex,
                "o": org_id.hex,
                "sid": f"mc-{spark_id}",
                "agency": agency,
                "title": title,
                "text": text,
                "deadline": deadline,
            },
        )
        session.commit()
    return spark_id


def _pursuit(org_id, spark_id):
    pursuit_id = uuid.uuid4()
    with SessionLocal() as session:
        session.connection().execute(
            sa.text(
                "INSERT INTO nf_grant_pursuits ("
                " id, organization_id, grant_spark_id, is_demo, status"
                ") VALUES (:p, :o, :s, 1, 'active')"
            ),
            {"p": pursuit_id.hex, "o": org_id.hex, "s": spark_id.hex},
        )
        session.commit()
    return pursuit_id


def _task(org_id, pursuit_id, title, status="pending", due_at=None):
    task_id = uuid.uuid4()
    with SessionLocal() as session:
        session.connection().execute(
            sa.text(
                "INSERT INTO nf_pursuit_tasks ("
                " id, organization_id, grant_pursuit_id, is_demo, title, status,"
                " sort_order, due_at"
                ") VALUES (:t, :o, :p, 1, :title, :st, 0, :due)"
            ),
            {
                "t": task_id.hex,
                "o": org_id.hex,
                "p": pursuit_id.hex,
                "title": title,
                "st": status,
                "due": due_at,
            },
        )
        session.commit()
    return task_id


def _mc(org_id):
    with SessionLocal() as session:
        return assemble_mission_control(session=session, organization_id=org_id)


def test_empty_organization_is_caught_without_urgency():
    org_id = _org()
    body = _mc(org_id)
    assert body["empty"] is True
    assert body["caught_up"] is False
    assert body["metrics"]["active_pursuits"] == 0
    assert body["open_work"] == []


def test_two_pursuits_aggregate_independently():
    org_id = _org()
    a = _spark(org_id, title="Alpha")
    b = _spark(org_id, title="Beta")
    pa = _pursuit(org_id, a)
    pb = _pursuit(org_id, b)
    _task(org_id, pa, "Draft Alpha", status="blocked")
    _task(org_id, pb, "Call Beta")
    body = _mc(org_id)
    assert body["metrics"]["active_pursuits"] == 2
    assert body["metrics"]["blocked"] == 1
    titles = {c["title"] for c in body["active_pursuits"]}
    assert titles == {"Alpha", "Beta"}
    blocked = [w for w in body["open_work"] if w["attention"] == "blocked"]
    assert blocked[0]["opportunity_title"] == "Alpha"
    other = [w for w in body["open_work"] if w["opportunity_title"] == "Beta"]
    assert other and other[0]["title"] == "Call Beta"


def test_completed_task_leaves_the_open_queue():
    org_id = _org()
    spark = _spark(org_id)
    pursuit = _pursuit(org_id, spark)
    _task(org_id, pursuit, "Done item", status="done")
    _task(org_id, pursuit, "Still open")
    body = _mc(org_id)
    open_titles = [w["title"] for w in body["open_work"] if w["kind"] == "task"]
    assert "Still open" in open_titles
    assert "Done item" not in open_titles


def test_overdue_and_future_due_dates():
    org_id = _org()
    spark = _spark(org_id)
    pursuit = _pursuit(org_id, spark)
    past = datetime.now(tz=UTC) - timedelta(days=3)
    future = datetime.now(tz=UTC) + timedelta(days=4)
    _task(org_id, pursuit, "Late", due_at=past)
    _task(org_id, pursuit, "Soon", due_at=future)
    body = _mc(org_id)
    by_title = {w["title"]: w for w in body["open_work"] if w["kind"] == "task"}
    assert by_title["Late"]["attention"] == "overdue"
    assert by_title["Soon"]["attention"] == "due_soon"


def test_application_deadline_and_question_window():
    org_id = _org()
    due = datetime.now(tz=UTC) + timedelta(days=12)
    spark = _spark(org_id, deadline=due, text=NOTICE)
    _pursuit(org_id, spark)
    body = _mc(org_id)
    kinds = {d["kind"] for d in body["deadlines"]}
    assert "application_deadline" in kinds
    assert any(w["kind"] == "deadline" for w in body["open_work"])


def test_awaiting_reply_is_waiting_work():
    org_id = _org()
    spark = _spark(org_id)
    _pursuit(org_id, spark)
    with SessionLocal() as session:
        ixn.record_interaction(
            connection=session.connection(),
            organization_id=org_id,
            is_demo=True,
            grant_spark_id=spark,
            funder_agency="HUD",
            interaction_type="question_submitted",
            status="awaiting_reply",
            subject="Match waiver",
            follow_up_at=(datetime.now(tz=UTC) - timedelta(days=1)).isoformat(),
        )
        session.commit()
    body = _mc(org_id)
    assert body["metrics"]["awaiting_response"] >= 1
    assert any(w["kind"] == "follow_up" for w in body["waiting"])


def test_workspace_and_command_center_share_current_stage():
    org_id = _org()
    spark = _spark(org_id)
    _pursuit(org_id, spark)
    with SessionLocal() as session:
        mc = assemble_mission_control(session=session, organization_id=org_id)
        cc = assemble_command_center(
            session=session, organization_id=org_id, grant_spark_id=spark
        )
    card = next(c for c in mc["active_pursuits"] if c["grant_spark_id"] == str(spark))
    assert card["current_stage_id"] == cc["workflow"]["current_stage_id"]
    assert {s["id"] for s in card["stages"]} == {
        s["id"] for s in cc["workflow"]["stages"]
    }


def test_direct_destinations_are_real_views():
    org_id = _org()
    spark = _spark(org_id)
    pursuit = _pursuit(org_id, spark)
    _task(org_id, pursuit, "Work")
    body = _mc(org_id)
    views = {w["view"] for w in body["open_work"]}
    assert views <= {"pursuits", "documents", "trust", "organization", "opportunities"}


def test_tenant_cannot_read_another_orgs_mission_control():
    soh.ensure_signing_key()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    soh.ensure_org(org_a, "demo")
    soh.ensure_org(org_b, "demo")
    soh.ensure_member(org_a)
    soh.ensure_member(org_b)
    spark = _spark(org_a, title="Secret")
    _pursuit(org_a, spark)
    client = TestClient(create_app(), raise_server_exceptions=False)
    mine = client.get(
        f"/v1/nf/demo/orgs/{org_a}/mission-control",
        headers=soh.session_headers(org_a),
    )
    theirs = client.get(
        f"/v1/nf/demo/orgs/{org_a}/mission-control",
        headers=soh.session_headers(org_b),
    )
    assert mine.status_code == 200
    assert any(c["title"] == "Secret" for c in mine.json()["active_pursuits"])
    assert theirs.status_code == 403


def test_foreign_owner_is_refused(monkeypatch: pytest.MonkeyPatch):
    soh.ensure_signing_key()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    monkeypatch.setenv("NF_DEMO_ORG_IDS", f"{org_a},{org_b}")
    from nativeforge.lib.settings import get_settings

    get_settings.cache_clear()
    soh.ensure_org(org_a, "demo")
    soh.ensure_org(org_b, "demo")
    soh.ensure_member(org_a)
    ident_b = soh.ensure_member(org_b)

    with SessionLocal() as session:
        row = (
            session.connection()
            .execute(
                sa.select(MEMBERSHIPS.c.id).where(
                    MEMBERSHIPS.c.organization_id == org_b,
                    MEMBERSHIPS.c.identity_id == uuid.UUID(str(ident_b)),
                )
            )
            .first()
        )
    assert row is not None
    spark = _spark(org_a)
    pursuit = _pursuit(org_a, spark)
    client = TestClient(create_app(), raise_server_exceptions=False)
    posted = client.post(
        f"/v1/nf/demo/orgs/{org_a}/pursuits/{pursuit}/tasks",
        headers=soh.session_headers(org_a),
        json={"title": "Cross-tenant owner", "owner_membership_id": str(row[0])},
    )
    assert posted.status_code == 422


def test_aggregation_uses_one_query_per_table():
    org_id = _org()
    body = _mc(org_id)
    counts = body["queries"]
    assert counts["pursuits"] == 1
    assert counts["tasks"] == 1
    assert counts["interactions"] == 1
    assert all(v == 1 for v in counts.values())


def test_foreign_org_pursuits_are_absent_from_the_read_model():
    mine = _org()
    other = _org()
    _pursuit(other, _spark(other, title="Other tenant"))
    _pursuit(mine, _spark(mine, title="Ours"))
    titles = {c["title"] for c in _mc(mine)["active_pursuits"]}
    assert titles == {"Ours"}


def test_package_pending_review_is_needs_review():
    from nativeforge.db.models import NfFormPackage, NfReviewArtifact

    org_id = _org()
    spark = _spark(org_id)
    pursuit = _pursuit(org_id, spark)
    art_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(
            NfReviewArtifact(
                id=art_id,
                organization_id=org_id,
                is_demo=True,
                artifact_type="sf424",
                review_status="pending_review",
            )
        )
        session.add(
            NfFormPackage(
                id=uuid.uuid4(),
                organization_id=org_id,
                grant_pursuit_id=pursuit,
                review_artifact_id=art_id,
                is_demo=True,
                package_engine="test",
                sf424_preview={},
                input_digest="a" * 64,
            )
        )
        session.commit()
    body = _mc(org_id)
    assert body["metrics"]["needs_review"] >= 1
    assert any(w["kind"] == "review" for w in body["reviews"])
    assert any(w["view"] == "trust" for w in body["reviews"])


def test_caught_up_when_canonical_work_is_complete():
    from nativeforge.db.models import (
        NfFormPackage,
        NfNofoExtractionRun,
        NfReviewArtifact,
        NfSparkRequirement,
        NfSparkScore,
        NfTribalProfile,
    )
    from nativeforge.domain.enums import (
        RecommendationTier,
        SparkRequirementKind,
        TribalEntityType,
    )

    org_id = _org()
    due = datetime.now(tz=UTC) + timedelta(days=40)
    spark = _spark(org_id, deadline=due)
    pursuit = _pursuit(org_id, spark)
    _task(org_id, pursuit, "Done item", status="done")
    run_id = uuid.uuid4()
    art_id = uuid.uuid4()
    with SessionLocal() as session:
        session.add(
            NfTribalProfile(
                id=uuid.uuid4(),
                organization_id=org_id,
                is_demo=True,
                legal_name="Test Nation",
                entity_type=TribalEntityType.federally_recognized_tribe.value,
            )
        )
        session.add(
            NfNofoExtractionRun(
                id=run_id,
                organization_id=org_id,
                grant_spark_id=spark,
                is_demo=True,
                extractor_engine="test",
                source_text_digest="b" * 64,
                nofo_summary="summary",
                structured_requirements={},
                checklist_snapshot=[],
            )
        )
        session.add(
            NfSparkRequirement(
                id=uuid.uuid4(),
                organization_id=org_id,
                grant_spark_id=spark,
                extraction_run_id=run_id,
                is_demo=True,
                requirement_type=SparkRequirementKind.form.value,
                label="SF-424",
            )
        )
        session.add(
            NfSparkScore(
                id=uuid.uuid4(),
                organization_id=org_id,
                grant_spark_id=spark,
                is_demo=True,
                scorer_engine="test",
                dimension_scores={},
                weights_used={},
                composite=80,
                recommendation=RecommendationTier.pursue.value,
                explanation_text="fit",
            )
        )
        session.add(
            NfReviewArtifact(
                id=art_id,
                organization_id=org_id,
                is_demo=True,
                artifact_type="sf424",
                review_status="approved",
            )
        )
        session.add(
            NfFormPackage(
                id=uuid.uuid4(),
                organization_id=org_id,
                grant_pursuit_id=pursuit,
                review_artifact_id=art_id,
                is_demo=True,
                package_engine="test",
                sf424_preview={},
                input_digest="c" * 64,
            )
        )
        session.commit()
    body = _mc(org_id)
    assert body["empty"] is False
    assert body["caught_up"] is True
    assert body["open_work"] == []
    assert body["next_deadline"] is not None
