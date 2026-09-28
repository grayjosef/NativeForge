"""Individual pursuit command center: derived workflow and tenant-private memory."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.db.session import SessionLocal
from nativeforge.main import create_app
from nativeforge.services import funder_interaction_service as ixn
from nativeforge.services import opportunity_apply_path_service as apply_svc
from nativeforge.services.pursuit_command_center_service import (
    assemble_command_center,
    extract_engagement_facts,
)
from tests import session_org_helper as soh

NOTICE = """
SECTION IV. APPLICATION AND SUBMISSION INFORMATION

Questions must be submitted no later than October 1, 2026.
Send questions to questions@hud.gov. A webinar will be held.

Submit through Grants.gov at https://www.grants.gov/apply no later than
11:59 PM ET on October 15, 2026.

SECTION VII. AGENCY CONTACTS

Program Contact
Jane Doe, Program Officer
jane.doe@hud.gov
(202) 555-0134
"""


def _insert_spark(org_id, *, source="manual", agency="HUD", title="ICDBG", text=""):
    spark_id = uuid.uuid4()
    with SessionLocal() as session:
        conn = session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO nf_grant_sparks ("
                " id, organization_id, is_demo, source, source_id, agency,"
                " opportunity_title, award_type, match_required,"
                " match_waiver_available, indirect_cost_allowable,"
                " tribal_eligible, pipeline_stage, raw_nofo_text"
                ") VALUES ("
                " :s, :o, 1, :src, :sid, :agency,"
                " :title, 'grant', 0, 0, 1, 1, 'new', :text)"
            ),
            {
                "s": spark_id.hex,
                "o": org_id.hex,
                "src": source,
                "sid": f"test-{spark_id}",
                "agency": agency,
                "title": title,
                "text": text,
            },
        )
        session.commit()
    return spark_id


def _insert_pursuit(org_id, spark_id, *, status="active"):
    pursuit_id = uuid.uuid4()
    with SessionLocal() as session:
        conn = session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO nf_grant_pursuits ("
                " id, organization_id, grant_spark_id, is_demo, status"
                ") VALUES (:p, :o, :s, 1, :st)"
            ),
            {
                "p": pursuit_id.hex,
                "o": org_id.hex,
                "s": spark_id.hex,
                "st": status,
            },
        )
        session.commit()
    return pursuit_id


def _insert_task(org_id, pursuit_id, title, status="pending"):
    task_id = uuid.uuid4()
    with SessionLocal() as session:
        conn = session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO nf_pursuit_tasks ("
                " id, organization_id, grant_pursuit_id, is_demo, title, status, sort_order"
                ") VALUES (:t, :o, :p, 1, :title, :st, 0)"
            ),
            {
                "t": task_id.hex,
                "o": org_id.hex,
                "p": pursuit_id.hex,
                "title": title,
                "st": status,
            },
        )
        session.commit()
    return task_id


def _center(org_id, spark_id):
    with SessionLocal() as session:
        return assemble_command_center(
            session=session, organization_id=org_id, grant_spark_id=spark_id
        )


@pytest.fixture()
def org():
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


def test_engagement_facts_do_not_invent_deadlines():
    assert extract_engagement_facts("") == []
    facts = extract_engagement_facts(NOTICE)
    kinds = {f["kind"] for f in facts}
    assert "questions_due" in kinds
    assert "webinar" in kinds
    assert "question_submission_method" in kinds


def test_discovered_opportunity_does_not_show_pursuit_progress(org):
    spark_id = _insert_spark(org, text=NOTICE)
    body = _center(org, spark_id)
    assert body["mode"] == "discovered"
    assert body["workflow"]["shown"] is False
    assert body["workflow"]["current_stage_id"] is None
    assert body["pursuit"] is None


def test_starting_a_pursuit_initializes_active_workflow(org):
    spark_id = _insert_spark(org)
    assert _center(org, spark_id)["mode"] == "discovered"
    _insert_pursuit(org, spark_id)
    body = _center(org, spark_id)
    assert body["mode"] == "active_pursuit"
    assert body["workflow"]["shown"] is True
    assert body["pursuit"]["status"] == "active"


def test_two_pursuits_keep_independent_workflow_state(org):
    a = _insert_spark(org, title="Alpha")
    b = _insert_spark(org, title="Beta")
    pa = _insert_pursuit(org, a)
    _insert_pursuit(org, b)
    _insert_task(org, pa, "Draft narrative", status="blocked")
    left = _center(org, a)
    right = _center(org, b)
    assert left["open_work"]["blocked_count"] == 1
    assert right["open_work"]["blocked_count"] == 0
    assert left["workflow"]["current_stage_id"] != right["workflow"][
        "current_stage_id"
    ] or (left["open_work"]["blockers"][0]["title"] == "Draft narrative")


def test_reload_reconstructs_the_same_derived_state(org):
    spark_id = _insert_spark(org)
    _insert_pursuit(org, spark_id)
    first = _center(org, spark_id)
    second = _center(org, spark_id)
    assert first["mode"] == second["mode"]
    assert (
        first["workflow"]["current_stage_id"] == second["workflow"]["current_stage_id"]
    )
    assert first["opportunity"]["id"] == second["opportunity"]["id"]


def test_uploaded_and_discovered_opportunities_share_the_command_center(org):
    uploaded = _insert_spark(org, source="manual", title="Upload")
    discovered = _insert_spark(org, source="grants_gov", title="Discovery")
    _insert_pursuit(org, uploaded)
    _insert_pursuit(org, discovered)
    u = _center(org, uploaded)
    d = _center(org, discovered)
    assert u["schema_version"] == d["schema_version"]
    assert {s["id"] for s in u["workflow"]["stages"]} == {
        s["id"] for s in d["workflow"]["stages"]
    }
    assert u["opportunity"]["source"] == "manual"
    assert d["opportunity"]["source"] == "grants_gov"


def test_contacts_render_when_present_and_honestly_when_missing(org):
    named = _insert_spark(org, text=NOTICE)
    empty = _insert_spark(org, title="Silent", text="")
    with SessionLocal() as session:
        apply_svc.record_extraction(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=named,
            notice_text=NOTICE,
            text_complete=False,
            source_document="NOFO.pdf",
        )
        session.commit()
    has = _center(org, named)
    missing = _center(org, empty)
    assert has["contacts"]["items"]
    assert has["contacts"]["items"][0]["role"] == "program"
    assert has["contacts"]["items"][0]["provenance_kind"] == "source_document"
    assert missing["contacts"]["items"] == []
    assert "not yet read" in missing["contacts"]["empty_message"].lower()


def test_question_deadline_comes_from_authoritative_text(org):
    spark_id = _insert_spark(org, text=NOTICE)
    facts = {
        f["kind"]: f for f in _center(org, spark_id)["question_intelligence"]["facts"]
    }
    assert facts["questions_due"]["value"] == "October 1, 2026"


def test_interaction_persists_on_the_correct_pursuit(org):
    spark_id = _insert_spark(org, agency="HUD")
    other = _insert_spark(org, agency="EPA", title="Other")
    pursuit_id = _insert_pursuit(org, spark_id)
    with SessionLocal() as session:
        written = ixn.record_interaction(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            grant_pursuit_id=pursuit_id,
            funder_agency="HUD",
            interaction_type="question_submitted",
            subject="Match waiver",
            notes="Asked whether in-kind counts.",
            owner_label="Jordan",
        )
        session.commit()
    assert written["written"] == 1
    mine = _center(org, spark_id)["interactions"]
    theirs = _center(org, other)["interactions"]
    assert len(mine) == 1
    assert mine[0]["subject"] == "Match waiver"
    assert mine[0]["grant_pursuit_id"] == str(pursuit_id)
    assert theirs == []


def test_open_work_associates_with_the_correct_pursuit(org):
    a = _insert_spark(org, title="A")
    b = _insert_spark(org, title="B")
    pa = _insert_pursuit(org, a)
    pb = _insert_pursuit(org, b)
    _insert_task(org, pa, "A only")
    _insert_task(org, pb, "B only", status="done")
    assert [t["title"] for t in _center(org, a)["open_work"]["tasks"]] == ["A only"]
    assert _center(org, b)["open_work"]["open_count"] == 0


def test_institutional_memory_is_same_funder_same_tenant(org):
    first = _insert_spark(org, agency="HUD", title="FY25")
    second = _insert_spark(org, agency="HUD", title="FY26")
    _insert_pursuit(org, first)
    with SessionLocal() as session:
        apply_svc.add_customer_contact(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=first,
            role="program",
            name="Prior Officer",
            email="prior@hud.gov",
        )
        session.commit()
    memory = _center(org, second)["institutional_memory"]
    assert memory["prior_pursuits"]
    assert memory["prior_pursuits"][0]["title"] == "FY25"
    assert any(c["email"] == "prior@hud.gov" for c in memory["prior_contacts"])


def test_tenant_cannot_read_another_tenants_relationship_intelligence():
    soh.ensure_signing_key()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    soh.ensure_org(org_a, "demo")
    soh.ensure_org(org_b, "demo")
    soh.ensure_member(org_a)
    headers_a = soh.session_headers(org_a)
    headers_b = soh.session_headers(org_b)
    spark = _insert_spark(org_a, text=NOTICE)
    with SessionLocal() as session:
        ixn.record_interaction(
            connection=session.connection(),
            organization_id=org_a,
            is_demo=True,
            grant_spark_id=spark,
            funder_agency="HUD",
            interaction_type="email",
            notes="Private to A",
        )
        session.commit()
    client = TestClient(create_app(), raise_server_exceptions=False)
    path = f"/v1/nf/demo/orgs/{org_a}/grant-sparks/{spark}/command-center"
    mine = client.get(path, headers=headers_a)
    theirs = client.get(path, headers=headers_b)
    assert mine.status_code == 200
    assert any(i["notes"] == "Private to A" for i in mine.json()["interactions"])
    assert theirs.status_code == 403
    foreign = client.get(
        f"/v1/nf/demo/orgs/{org_b}/grant-sparks/{spark}/command-center",
        headers=headers_b,
    )
    assert foreign.status_code == 404


def test_extracted_notice_without_contacts_is_honest(org):
    notice = (
        "Submit through Grants.gov at https://www.grants.gov/apply "
        "no later than 11:59 PM ET on October 15, 2026."
    )
    spark_id = _insert_spark(org, title="No names", text=notice)
    with SessionLocal() as session:
        apply_svc.record_extraction(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            notice_text=notice,
            text_complete=False,
            source_document="NOFO.pdf",
        )
        session.commit()
    body = _center(org, spark_id)
    assert body["contacts"]["extraction_performed"] is True
    assert body["contacts"]["items"] == []
    assert (
        "no grant contact information was identified"
        in body["contacts"]["empty_message"].lower()
    )


def test_multiple_contacts_keep_distinct_roles(org):
    spark_id = _insert_spark(org, text=NOTICE)
    with SessionLocal() as session:
        apply_svc.record_extraction(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            notice_text=NOTICE,
            text_complete=False,
            source_document="NOFO.pdf",
        )
        apply_svc.add_customer_contact(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            role="grants_management",
            name="Grants Desk",
            email="grants@hud.gov",
        )
        session.commit()
    items = _center(org, spark_id)["contacts"]["items"]
    roles = {c["role"] for c in items}
    assert "program" in roles
    assert "grants_management" in roles
    assert len(items) >= 2


def test_interaction_keeps_contact_and_follow_up(org):
    spark_id = _insert_spark(org, text=NOTICE)
    pursuit_id = _insert_pursuit(org, spark_id)
    with SessionLocal() as session:
        apply_svc.add_customer_contact(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            role="program",
            name="Jane Doe",
            email="jane.doe@hud.gov",
        )
        session.commit()
        contact_id = _center(org, spark_id)["contacts"]["items"][0]["id"]
        written = ixn.record_interaction(
            connection=session.connection(),
            organization_id=org,
            is_demo=True,
            grant_spark_id=spark_id,
            grant_pursuit_id=pursuit_id,
            contact_id=contact_id,
            funder_agency="HUD",
            interaction_type="question_submitted",
            status="awaiting_reply",
            subject="Match",
            follow_up_at="2026-10-02",
        )
        session.commit()
    assert written["written"] == 1
    row = _center(org, spark_id)["interactions"][0]
    assert row["contact_id"] == contact_id
    assert row["funder_agency"] == "HUD"
    assert row["grant_pursuit_id"] == str(pursuit_id)
    assert row["follow_up_at"].startswith("2026-10-02")
    assert row["status"] == "awaiting_reply"


def test_http_records_interaction_on_the_command_center():
    soh.ensure_signing_key()
    org_id = uuid.uuid4()
    soh.ensure_org(org_id, "demo")
    soh.ensure_member(org_id)
    headers = soh.session_headers(org_id)
    spark = _insert_spark(org_id, text=NOTICE)
    _insert_pursuit(org_id, spark)
    client = TestClient(create_app(), raise_server_exceptions=False)
    posted = client.post(
        f"/v1/nf/demo/orgs/{org_id}/grant-sparks/{spark}/interactions",
        headers=headers,
        json={
            "interaction_type": "email",
            "subject": "Pre-application call",
            "notes": "They confirmed tribal match waiver.",
            "owner_label": "Jordan",
        },
    )
    assert posted.status_code == 201
    body = posted.json()
    assert body["mode"] == "active_pursuit"
    assert body["interactions"][0]["subject"] == "Pre-application call"
    again = client.get(
        f"/v1/nf/demo/orgs/{org_id}/grant-sparks/{spark}/command-center",
        headers=headers,
    )
    assert again.status_code == 200
    assert again.json()["interactions"][0]["notes"] == (
        "They confirmed tribal match waiver."
    )
