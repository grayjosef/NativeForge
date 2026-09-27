"""Storing contacts and the submission route, and what supersedes what.

These run against the real schema, because the parts worth testing are the
ones the schema enforces: that a customer-provided contact can never claim to
be source-verified, that an amendment supersedes rather than deletes, and
that `verified` cannot be written without a route and a date.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa

from nativeforge.db.session import SessionLocal
from nativeforge.services import opportunity_apply_path_service as svc

ORIGINAL = """
SECTION IV. APPLICATION AND SUBMISSION INFORMATION

How to Apply

Submit through Grants.gov at https://www.grants.gov/apply no later than
11:59 PM ET on October 15, 2026.

SECTION VII. AGENCY CONTACTS

Program Contact
Jane Doe, Program Officer
jane.doe@hud.gov
(202) 555-0134
"""

AMENDED = """
AMENDMENT 2

How to Apply

Applications must now be emailed to grants@hud.gov by 5:00 PM ET on
November 1, 2026. Do not use the portal previously listed.

Program Contact
Robert Smith, Program Officer
robert.smith@hud.gov
"""


@pytest.fixture()
def org_and_spark():
    """A demo organization and one opportunity belonging to it."""
    org_id = uuid.uuid4()
    spark_id = uuid.uuid4()
    with SessionLocal() as session:
        conn = session.connection()
        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at)"
                " VALUES (:i, 'demo', 5, CURRENT_TIMESTAMP)"
            ),
            {"i": org_id.hex},
        )
        conn.execute(
            sa.text(
                "INSERT INTO nf_grant_sparks ("
                " id, organization_id, is_demo, source, source_id, agency,"
                " opportunity_title, award_type, match_required,"
                " match_waiver_available, indirect_cost_allowable,"
                " tribal_eligible, pipeline_stage"
                ") VALUES ("
                " :s, :o, 1, 'manual', :sid, 'HUD',"
                " 'Indian Community Development Block Grant', 'grant', 0,"
                " 0, 1, 1, 'new')"
            ),
            {"s": spark_id.hex, "o": org_id.hex, "sid": f"test-{spark_id}"},
        )
        session.commit()
    yield org_id, spark_id


def _record(org_id, spark_id, text, *, complete=True, doc="NOFO.pdf", reason="re-read"):
    with SessionLocal() as session:
        out = svc.record_extraction(
            connection=session.connection(),
            organization_id=org_id,
            is_demo=True,
            grant_spark_id=spark_id,
            notice_text=text,
            text_complete=complete,
            source_document=doc,
            reason=reason,
        )
        session.commit()
    return out


def _read(org_id, spark_id, **kw):
    with SessionLocal() as session:
        return svc.read_apply_path(
            connection=session.connection(),
            organization_id=org_id,
            grant_spark_id=spark_id,
            **kw,
        )


# --------------------------------------------------------------- writing


def test_a_notice_becomes_contacts_and_a_submission_path(org_and_spark):
    org_id, spark_id = org_and_spark
    out = _record(org_id, spark_id, ORIGINAL)
    assert out["contacts_written"] >= 1
    assert out["submission_written"] == 1
    assert out["submission_completeness"] == "verified"

    stored = _read(org_id, spark_id)
    program = [c for c in stored["contacts"] if c["role"] == "program"]
    assert program and program[0]["email"] == "jane.doe@hud.gov"
    assert stored["submission"]["portal_name"] == "Grants.gov"
    assert stored["submission"]["deadline_timezone"] == "ET"


def test_every_stored_fact_names_the_document_it_came_from(org_and_spark):
    org_id, spark_id = org_and_spark
    _record(org_id, spark_id, ORIGINAL, doc="NOFO-2026.pdf")
    stored = _read(org_id, spark_id)
    for contact in stored["contacts"]:
        assert contact["source_document"] == "NOFO-2026.pdf"
        assert contact["provenance_kind"] == "source_document"
    assert stored["submission"]["source_document"] == "NOFO-2026.pdf"


# ---------------------------------------------------------- supersession


def test_an_amendment_supersedes_rather_than_deletes(org_and_spark):
    """A customer who used the old address has to be able to see that.

    Finding the previous value silently gone tells them nothing, and leaves
    them assuming they submitted correctly.
    """
    org_id, spark_id = org_and_spark
    _record(org_id, spark_id, ORIGINAL)
    _record(org_id, spark_id, AMENDED, doc="Amendment-2.pdf", reason="amendment 2")

    current = _read(org_id, spark_id)
    assert current["submission"]["recipient_email"] == "grants@hud.gov"
    assert current["submission"]["method"] == "email"
    assert all(c["email"] != "jane.doe@hud.gov" for c in current["contacts"])

    history = _read(org_id, spark_id, include_superseded=True)
    old = [c for c in history["contacts"] if c["email"] == "jane.doe@hud.gov"]
    assert old, "the superseded contact must still be retrievable"
    assert old[0]["superseded"] is True


def test_the_current_read_shows_one_submission_path_not_two(org_and_spark):
    org_id, spark_id = org_and_spark
    _record(org_id, spark_id, ORIGINAL)
    _record(org_id, spark_id, AMENDED, doc="Amendment-2.pdf")
    stored = _read(org_id, spark_id)
    assert stored["submission"]["superseded"] is False
    assert "grants.gov" not in (stored["submission"]["submission_url"] or "").lower()


# ------------------------------------------------------------ provenance


def test_a_customer_contact_can_never_claim_to_be_source_verified(org_and_spark):
    """There is no parameter that would let it.

    A customer's private relationship with a program officer is theirs. It is
    not evidence about the opportunity, and only evidence can ever be promoted
    to something another organization sees.
    """
    org_id, spark_id = org_and_spark
    with SessionLocal() as session:
        result = svc.add_customer_contact(
            connection=session.connection(),
            organization_id=org_id,
            is_demo=True,
            grant_spark_id=spark_id,
            role="program",
            name="Someone We Know",
            email="known@agency.gov",
        )
        session.commit()
    assert result["written"] == 1

    stored = _read(org_id, spark_id)
    mine = [c for c in stored["contacts"] if c["email"] == "known@agency.gov"]
    assert mine[0]["provenance_kind"] == "customer_provided"


def test_a_customer_contact_with_no_way_to_reach_anybody_is_refused(org_and_spark):
    org_id, spark_id = org_and_spark
    with SessionLocal() as session:
        result = svc.add_customer_contact(
            connection=session.connection(),
            organization_id=org_id,
            is_demo=True,
            grant_spark_id=spark_id,
            name="A Name Alone",
        )
        session.commit()
    assert result["written"] == 0
    assert "contact_has_no_way_to_reach_anybody" in result["blocked_reasons"]


# -------------------------------------------------------------- closure


def test_a_partial_read_is_reported_as_one(org_and_spark):
    org_id, spark_id = org_and_spark
    out = _record(org_id, spark_id, ORIGINAL, complete=False)
    assert out["text_complete"] is False
    assert "text_was_not_known_to_be_complete" in out["notes"]


def test_a_notice_with_no_submission_section_stores_none_and_says_why(org_and_spark):
    org_id, spark_id = org_and_spark
    out = _record(org_id, spark_id, "This program supports Tribal housing.")
    assert out["submission_written"] == 0
    assert out["submission_completeness"] == "unclear"
    assert "no_submission_instructions_found" in out["completeness_reasons"]

    stored = _read(org_id, spark_id)
    assert stored["submission"] is None


# -------------------------------------------------------------- isolation


def test_one_organization_never_reads_another_ones_contacts(org_and_spark):
    """The read is scoped by organization, not only by opportunity.

    The opportunity id is a UUID and unguessable, which is not a boundary -
    it is an obstacle. The boundary is the organization predicate, and on
    PostgreSQL the row-level policy behind it.
    """
    org_id, spark_id = org_and_spark
    _record(org_id, spark_id, ORIGINAL)

    other_org = uuid.uuid4()
    with SessionLocal() as session:
        session.connection().execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at)"
                " VALUES (:i, 'demo', 5, CURRENT_TIMESTAMP)"
            ),
            {"i": other_org.hex},
        )
        session.commit()

    theirs = _read(other_org, spark_id)
    assert theirs["contacts"] == []
    assert theirs["submission"] is None
