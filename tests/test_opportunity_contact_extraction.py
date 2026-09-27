"""Contacts and the submission route, read out of a notice.

The fixtures are shaped like the notices this runs against: headings, a
contact block, a "How to Apply" section. The cases that matter are the ones
where the right answer is to say less - an address under no heading keeps
`role="unknown"` rather than being promoted to program contact, and a portal
without a deadline is `partial` rather than `verified`.
"""

from __future__ import annotations

from nativeforge.services.opportunity_contact_extraction_service import (
    ROLES,
    assess_completeness,
    extract,
    extract_contacts,
    extract_submission_path,
    role_at,
)

NOTICE = """
DEPARTMENT OF HOUSING AND URBAN DEVELOPMENT
Indian Community Development Block Grant

SECTION I. PROGRAM DESCRIPTION

The purpose of this program is to support Tribal housing.

SECTION IV. APPLICATION AND SUBMISSION INFORMATION

How to Apply

Applications must be submitted electronically through Grants.gov at
https://www.grants.gov/web/grants/apply.html no later than 11:59 PM ET on
October 15, 2026. Paper applications will not be accepted.

SECTION VII. AGENCY CONTACTS

Program Contact
Jane Doe, Program Officer
Office of Native American Programs
jane.doe@hud.gov
(202) 555-0134

Technical Support
For problems with the Grants.gov system, contact Grants.gov Applicant Support
at support@grants.gov or 1-800-555-0199.

Grants Management
Robert Smith, Grants Management Specialist
robert.smith@hud.gov

General correspondence may be directed to onap@hud.gov.
"""


def _by_role(text: str) -> dict[str, list]:
    out: dict[str, list] = {}
    for contact in extract_contacts(text):
        out.setdefault(contact.role, []).append(contact)
    return out


# ------------------------------------------------------------- contacts


def test_a_program_officer_is_not_flattened_into_a_generic_contact():
    roles = _by_role(NOTICE)
    program = roles["program"]
    assert len(program) == 1
    contact = program[0]
    assert contact.email == "jane.doe@hud.gov"
    assert contact.name == "Jane Doe"
    assert contact.title == "Program Officer"
    assert contact.office == "Office of Native American Programs"
    assert contact.phone == "(202) 555-0134"


def test_the_office_is_not_mistaken_for_the_person():
    """ "Office of Native American Programs" matches the name pattern exactly.

    Taking the nearest capitalised phrase before the address returned it as
    the contact's name, so every HUD contact was called "Native American
    Programs". The person comes first in a notice and the office last.
    """
    contact = _by_role(NOTICE)["program"][0]
    assert contact.name == "Jane Doe"
    assert contact.name != contact.office


def test_a_name_is_not_read_across_a_line_break():
    """`\\s` matches a newline, which swallowed the name.

    The pattern matched "Program Contact\\nJane" as one candidate - filtered
    out as organisational - and the real name was never a candidate at all,
    so names came back None for every contact under a heading.
    """
    text = "Program Contact\nJane Doe, Program Officer\njane.doe@hud.gov\n"
    assert extract_contacts(text)[0].name == "Jane Doe"


def test_technical_support_is_distinguished_from_the_program_contact():
    """The person who explains scope is not the person who fixes an upload.

    Getting these the wrong way round costs a customer a week they do not
    have, which is why role is extracted rather than assumed.
    """
    roles = _by_role(NOTICE)
    support = roles["application_support"]
    assert any(c.email == "support@grants.gov" for c in support)
    assert all(c.email != "jane.doe@hud.gov" for c in support)


def test_grants_management_is_its_own_role():
    roles = _by_role(NOTICE)
    assert any(c.email == "robert.smith@hud.gov" for c in roles["grants_management"])


def test_an_address_under_no_heading_stays_unknown():
    """The refusal this module exists for.

    "General correspondence may be directed to onap@hud.gov" appears after
    the grants-management block, outside any role window. Attributing it to
    grants management because that heading came last would be an invention,
    and the customer would email the wrong office believing NativeForge had
    read the notice.
    """
    text = "Some prose.\n\nWrite to us at anybody@agency.gov if you like.\n"
    contacts = extract_contacts(text)
    assert len(contacts) == 1
    assert contacts[0].role == "unknown"
    assert contacts[0].source_section is None


def test_a_phone_is_not_borrowed_from_the_neighbouring_contact():
    """A character window reached across the blank line between blocks.

    The Grants.gov support address came back with the program officer's
    direct line, and grants management came back with the support desk's
    1-800 number. A customer only finds that out by ringing the wrong person.
    """
    roles = _by_role(NOTICE)
    program = roles["program"][0]
    support = [
        c for c in roles["application_support"] if c.email == "support@grants.gov"
    ]
    assert program.phone == "(202) 555-0134"
    assert support and support[0].phone != "(202) 555-0134"


def test_a_role_heading_is_never_returned_as_a_persons_name():
    """ "Award Decisions" is a heading. It was becoming a contact's name.

    Neither word was in the hand-written exclusion list, and any new role
    phrase would have reopened the hole - so the exclusions are derived from
    the role vocabulary itself.
    """
    text = "Award Decisions\n\nWrite to onap-awards@hud.gov with questions.\n"
    contact = extract_contacts(text)[0]
    assert contact.name is None
    assert contact.email == "onap-awards@hud.gov"


def test_every_role_produced_is_one_the_schema_accepts():
    for contact in extract_contacts(NOTICE):
        assert contact.role in ROLES


def test_a_heading_far_above_an_address_does_not_claim_it():
    """Role attribution has a range, and beyond it the document has moved on."""
    text = "Program Contact\n" + ("filler line\n" * 80) + "someone@agency.gov\n"
    contacts = extract_contacts(text)
    assert contacts[0].role == "unknown"


def test_a_long_sentence_mentioning_a_role_is_not_a_heading():
    """Otherwise a passing reference turns the next paragraph into a section."""
    text = (
        "Applicants who have questions should note that the program contact "
        "listed in a previous solicitation is no longer with the agency and "
        "should not be used for this competition.\n\nwrong@agency.gov\n"
    )
    assert role_at(text, text.index("wrong@"))[0] == "unknown"


def test_a_heading_with_no_address_produces_no_contact():
    """A row that looks like an answer is worse than no row."""
    assert extract_contacts("Program Contact\n\nTo be announced.\n") == []


def test_no_contacts_in_empty_text_rather_than_an_exception():
    assert extract_contacts("") == []
    assert extract_contacts("   \n  ") == []


# ----------------------------------------------------- submission path


def test_the_portal_the_deadline_and_the_timezone_come_out():
    path = extract_submission_path(NOTICE)
    assert path is not None
    assert path.method == "grants_gov"
    assert path.portal_name == "Grants.gov"
    assert "grants.gov/web/grants/apply" in (path.submission_url or "")
    assert path.deadline_timezone == "ET"
    assert "11:59" in (path.deadline_text or "")


def test_the_deadline_becomes_an_instant_in_the_funders_own_clock():
    """The wording is what the customer reads; the instant is what sorts.

    "ET" in October is EDT, which is UTC-4. A fixed -05:00 offset table would
    put every autumn deadline an hour late, and for a submission deadline an
    hour late is the whole thing.
    """
    path = extract_submission_path(NOTICE)
    assert path.deadline_at is not None
    assert (path.deadline_at.year, path.deadline_at.month, path.deadline_at.day) == (
        2026,
        10,
        15,
    )
    assert (path.deadline_at.hour, path.deadline_at.minute) == (23, 59)
    assert path.deadline_at.utcoffset().total_seconds() == -4 * 3600


def test_a_winter_deadline_in_the_same_zone_uses_standard_time():
    text = (
        "How to Apply\n\nSubmit at https://www.grants.gov/apply by 11:59 PM ET "
        "on January 15, 2027.\n"
    )
    path = extract_submission_path(text)
    assert path.deadline_at.utcoffset().total_seconds() == -5 * 3600


def test_a_time_with_no_date_yields_no_instant():
    """Rather than inventing one, which the customer would plan around."""
    text = "How to Apply\n\nApplications are due by 11:59 PM ET.\n"
    path = extract_submission_path(text)
    assert path is not None
    assert path.deadline_text is not None
    assert path.deadline_at is None


def test_a_mention_of_grants_gov_in_prose_is_not_a_submission_portal():
    """Matched on the URL's host, not on the word appearing somewhere.

    Plenty of notices name Grants.gov while directing applications elsewhere.
    """
    text = (
        "How to Apply\n\nThis program does not use Grants.gov. Email your "
        "application to apply@tribe.example by 5:00 PM MT on June 1, 2026.\n"
    )
    path = extract_submission_path(text)
    assert path is not None
    assert path.method == "email"
    assert path.recipient_email == "apply@tribe.example"


def test_an_address_outside_the_submission_section_is_not_a_destination():
    """A contact is not a place to send an application."""
    text = "Agency Contacts\n\nProgram Contact\njane@agency.gov\n"
    path = extract_submission_path(text)
    assert path is None or path.recipient_email is None


def test_mail_submission_is_recognised():
    text = "How to Apply\n\nApplications must be postmarked by June 1, 2026.\n"
    path = extract_submission_path(text)
    assert path is not None
    assert path.method == "mail"


def test_a_notice_that_says_nothing_yields_no_path():
    assert extract_submission_path("The program supports Tribal housing.") is None


# -------------------------------------------------------- completeness


def test_a_portal_and_a_deadline_is_verified():
    state, reasons = assess_completeness(extract_submission_path(NOTICE))
    assert state == "verified"
    assert reasons == []


def test_a_portal_without_a_deadline_is_only_partial():
    """A URL is not a submission path. This is most of the way to a miss."""
    text = "How to Apply\n\nApply at https://www.grants.gov/apply.\n"
    state, reasons = assess_completeness(extract_submission_path(text))
    assert state == "partial"
    assert "no_submission_deadline_found" in reasons


def test_nothing_found_is_unclear_and_says_so():
    state, reasons = assess_completeness(None)
    assert state == "unclear"
    assert reasons == ["no_submission_instructions_found"]


# ------------------------------------------------------------- closure


def test_a_partial_read_is_carried_through_to_the_result():
    """Absence proves nothing when the document was not fully read.

    Exactly the rule the requirement extractor follows. A caller that reads
    `contacts == []` needs to be able to tell "this notice names nobody" from
    "we did not read all of it", and the only place that distinction can come
    from is the caller's own knowledge of the document.
    """
    partial = extract(NOTICE, text_complete=False)
    assert partial.text_complete is False
    assert "text_was_not_known_to_be_complete" in partial.notes

    whole = extract(NOTICE, text_complete=True)
    assert whole.text_complete is True
    assert "text_was_not_known_to_be_complete" not in whole.notes


def test_the_result_serialises_without_losing_provenance():
    payload = extract(NOTICE, text_complete=True).as_dict()
    assert payload["submission"]["source_section"] == "How to Apply"
    for contact in payload["contacts"]:
        assert "source_section" in contact
        assert "source_offset" in contact
