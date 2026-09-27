"""Read the contacts and the submission route out of a funding notice.

Two questions follow "should we apply?", and NativeForge could answer neither:
*who do I deal with*, and *what exactly do I do next*. Both answers are
usually printed in the notice, under headings, and the customer was left to
find them by reading ninety pages.

## What this extracts, and what it refuses to

Addresses, phone numbers, portals and deadlines are matched with patterns.
Roles are not. A role is assigned only when the text says so - a heading, a
label, or a sentence naming the job - and is `unknown` otherwise. That
distinction is the whole point: a program officer who can say whether a
project is in scope is rarely the person who can unstick a portal upload, and
a product that routes a technical question to a program officer costs a
customer a week they did not have.

So an address found under no heading is recorded with `role="unknown"`, which
the interface shows as a contact whose job the notice did not state. That is
a worse answer than a classified one and a far better answer than a
confident wrong one.

## Why this is patterns rather than a model

The facts are short, formulaic and printed under conventional headings, so
patterns find most of them and - more importantly - *say where they found
them*. Every returned fact carries the section heading and the character
offset it came from, which is the property the evidence rules depend on. A
model that returned the same fields without provenance could not be checked,
and an extraction that cannot be checked cannot be relied on for a deadline.

## What absence means here

Nothing. This reads the text it is given. If a notice was read only in part,
or could not be read at all, the absence of a contact in this output is not
evidence that the notice names none - exactly as with requirements. Callers
pair the result with the document's closure state; `ExtractionResult.
text_complete` carries whether the caller believed it had the whole document,
so a downstream reader cannot accidentally treat a partial read as a full
one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------

#: Mirrors the CHECK constraint in migration 0068. Duplicated deliberately:
#: the database is the enforcement and this is the vocabulary the extractor
#: may produce, and a mismatch should fail loudly at insert rather than let
#: this module invent a role the schema has never heard of.
ROLES: tuple[str, ...] = (
    "program",
    "application_support",
    "grants_management",
    "submission_support",
    "financial",
    "award_decision",
    "general_office",
    "unknown",
)

METHODS: tuple[str, ...] = (
    "grants_gov",
    "agency_portal",
    "state_portal",
    "foundation_portal",
    "email",
    "mail",
    "invitation_only",
    "other",
    "unknown",
)

#: Phrases that name a role, longest first so "technical assistance" is not
#: matched by a shorter, more general rule earlier in the list.
#:
#: Ordering matters more than it looks: "grants management specialist" must
#: not be caught by the "program" rule because it contains "grant", and
#: "application technical support" must not be caught by "application".
ROLE_PHRASES: tuple[tuple[str, str], ...] = (
    ("grants management officer", "grants_management"),
    ("grants management specialist", "grants_management"),
    ("grants management", "grants_management"),
    ("grants officer", "grants_management"),
    ("technical assistance", "application_support"),
    ("technical support", "application_support"),
    ("technical questions", "application_support"),
    ("technical help", "application_support"),
    ("application support", "application_support"),
    ("application questions", "application_support"),
    ("submission support", "submission_support"),
    ("submission questions", "submission_support"),
    ("submission assistance", "submission_support"),
    ("award decision", "award_decision"),
    ("award questions", "award_decision"),
    ("award notification", "award_decision"),
    ("budget questions", "financial"),
    ("financial questions", "financial"),
    ("finance office", "financial"),
    ("budget officer", "financial"),
    ("program officer", "program"),
    ("program contact", "program"),
    ("program questions", "program"),
    ("programmatic questions", "program"),
    ("program manager", "program"),
    ("agency contact", "general_office"),
    ("general questions", "general_office"),
    ("for further information", "general_office"),
    ("for more information", "general_office"),
    ("contact information", "general_office"),
)

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

#: US-shaped numbers, which is what federal and Tribal notices print. A looser
#: pattern matched dollar figures and CFDA numbers.
PHONE_RE = re.compile(
    r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?:\s*(?:x|ext\.?)\s*\d{1,6})?",
    re.IGNORECASE,
)

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

#: A heading is a short line, so a paragraph mentioning "program contact" in
#: passing is not mistaken for a section about one.
MAX_HEADING_LENGTH = 90

#: How far after a heading a contact may appear and still be attributed to it.
#: Roughly a short paragraph; beyond that the text has moved on.
ROLE_WINDOW_CHARS = 420


@dataclass(frozen=True)
class Contact:
    """One person or office, and where the notice said it."""

    role: str
    name: str | None = None
    title: str | None = None
    office: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    source_section: str | None = None
    source_offset: int | None = None

    def reachable(self) -> bool:
        """Whether this is a contact at all.

        Mirrors the CHECK constraint: a heading with no address under it is a
        heading, and storing it would put a row that looks like an answer in
        front of somebody who needs one.
        """
        return any((self.email, self.phone, self.website, self.office))

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "title": self.title,
            "office": self.office,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
            "source_section": self.source_section,
            "source_offset": self.source_offset,
        }


@dataclass(frozen=True)
class SubmissionPath:
    """How an application reaches the funder."""

    method: str
    portal_name: str | None = None
    submission_url: str | None = None
    package_url: str | None = None
    recipient_email: str | None = None
    recipient_office: str | None = None
    #: The deadline as an instant, when the notice gives a date.
    #:
    #: Separate from `deadline_text`, which is the wording. "11:59 PM ET" is
    #: what the customer has to meet and what the interface shows; this is
    #: what a countdown and a sort order need, and a submission path cannot be
    #: called reliable without it - a portal with no date is most of the way
    #: to a missed deadline.
    deadline_at: datetime | None = None
    deadline_text: str | None = None
    deadline_timezone: str | None = None
    submission_format: str | None = None
    submission_instructions: str | None = None
    source_section: str | None = None
    source_offset: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "portal_name": self.portal_name,
            "submission_url": self.submission_url,
            "package_url": self.package_url,
            "recipient_email": self.recipient_email,
            "recipient_office": self.recipient_office,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "deadline_text": self.deadline_text,
            "deadline_timezone": self.deadline_timezone,
            "submission_format": self.submission_format,
            "submission_instructions": self.submission_instructions,
            "source_section": self.source_section,
            "source_offset": self.source_offset,
        }


@dataclass(frozen=True)
class ExtractionResult:
    contacts: tuple[Contact, ...] = ()
    submission: SubmissionPath | None = None
    #: Whether the caller believed it handed over the whole document. Carried
    #: through so a reader cannot mistake a partial read for a complete one -
    #: the absence of a contact means nothing when this is False.
    text_complete: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "contacts": [c.as_dict() for c in self.contacts],
            "submission": self.submission.as_dict() if self.submission else None,
            "text_complete": self.text_complete,
            "notes": list(self.notes),
        }


# --------------------------------------------------------------------------
# role attribution
# --------------------------------------------------------------------------


def _headings(text: str) -> list[tuple[int, str, str]]:
    """Every line that names a role, as (offset, heading text, role).

    A heading is a short line. Requiring shortness is what keeps a sentence
    that happens to contain "program contact" from turning the next four
    hundred characters into a program-contact section.
    """
    found: list[tuple[int, str, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and len(stripped) <= MAX_HEADING_LENGTH:
            lowered = stripped.lower()
            for phrase, role in ROLE_PHRASES:
                if phrase in lowered:
                    found.append((offset, stripped, role))
                    break
        offset += len(line)
    return found


def role_at(text: str, position: int) -> tuple[str, str | None]:
    """The role in force at a character position, and the heading that set it.

    The nearest preceding heading wins, and only within
    :data:`ROLE_WINDOW_CHARS`. Beyond that the document has moved on to
    something else and attributing an address to a heading a page earlier
    would be a guess dressed as a citation.
    """
    best: tuple[int, str, str] | None = None
    for offset, heading, role in _headings(text):
        if offset <= position and (best is None or offset > best[0]):
            best = (offset, heading, role)
    if best is None or position - best[0] > ROLE_WINDOW_CHARS:
        return "unknown", None
    return best[2], best[1]


# --------------------------------------------------------------------------
# contacts
# --------------------------------------------------------------------------

#: Addresses that belong to a portal's help desk rather than to this funding
#: programme. They are still worth recording - a customer stuck on an upload
#: needs them - but as application support, whatever heading they sit under.
SUPPORT_ADDRESS_HINTS = ("support@grants.gov", "grants.gov")


def extract_contacts(text: str) -> list[Contact]:
    """Every reachable contact in the text, with its role and its location."""
    if not text or not text.strip():
        return []

    by_key: dict[tuple[str, str], Contact] = {}

    for match in EMAIL_RE.finditer(text):
        email = match.group(0).rstrip(".,;:")
        role, heading = role_at(text, match.start())
        if any(hint in email.lower() for hint in SUPPORT_ADDRESS_HINTS):
            role = "application_support"
        phone = _phone_near(text, match.start())
        # Keyed on address and role so the same mailbox listed under two
        # headings stays two facts. It genuinely is two: the notice said that
        # address answers both kinds of question.
        by_key.setdefault(
            (email.lower(), role),
            Contact(
                role=role,
                email=email,
                phone=phone,
                name=_name_near(text, match.start()),
                title=_title_near(text, match.start()),
                office=_office_near(text, match.start()),
                source_section=heading,
                source_offset=match.start(),
            ),
        )

    # Phones with no address beside them are still a way to reach somebody.
    for match in PHONE_RE.finditer(text):
        phone = match.group(0).strip()
        if any(c.phone == phone for c in by_key.values()):
            continue
        role, heading = role_at(text, match.start())
        by_key.setdefault(
            (phone, role),
            Contact(
                role=role,
                phone=phone,
                name=_name_near(text, match.start()),
                source_section=heading,
                source_offset=match.start(),
            ),
        )

    return [c for c in by_key.values() if c.reachable()]


#: A personal name printed immediately before an address, as notices do:
#: "Jane Doe, Program Officer, jane.doe@agency.gov". Two or three capitalised
#: words, which is a convention rather than a rule, so a miss leaves the name
#: unset rather than guessing.
#: `[ \t]+` rather than `\s+`, deliberately: `\s` matches a newline, so the
#: pattern read across line breaks and matched "Program Contact\nJane",
#: swallowing the name it was looking for and leaving every contact nameless.
#: A person's name is on one line.
NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:[ \t]+[A-Z][a-z'.-]+){1,2})\b")

#: Words that make a capitalised phrase an office or a job rather than a
#: person. "Office of Native American Programs" matches the name pattern
#: perfectly and is not a name; the first version of this took the *last*
#: candidate before the address and returned exactly that, so every HUD
#: contact was called "Native American Programs".
NON_NAME_WORDS = frozenset(
    {
        "office",
        "offices",
        "program",
        "programs",
        "officer",
        "department",
        "bureau",
        "division",
        "branch",
        "agency",
        "administration",
        "service",
        "services",
        "support",
        "management",
        "specialist",
        "center",
        "centre",
        "affairs",
        "development",
        "grants",
        "grant",
        "applicant",
        "technical",
        "assistance",
        "contact",
        "contacts",
        "section",
        "attn",
    }
)


#: Every word that appears in a role phrase is also not a name.
#:
#: Derived rather than listed a second time. "Award Decisions" is a heading
#: and was being returned as a contact's name because neither word happened to
#: be in the hand-written list - and any new role phrase would have reopened
#: the same hole. A word this module uses to recognise a job is, by
#: construction, a word that describes a job.
_ROLE_WORDS = frozenset(
    word for phrase, _ in ROLE_PHRASES for word in phrase.lower().split()
)


def _looks_like_a_person(candidate: str) -> bool:
    words = {w.strip(".,").lower() for w in candidate.split()}
    return not (words & (NON_NAME_WORDS | _ROLE_WORDS))


def _block_before(text: str, position: int, max_chars: int = 400) -> str:
    """The contact block an address sits in: back to the last blank line.

    A fixed character window cut through words - 120 characters before a HUD
    address begins in the middle of "Jane", so the name pattern never matched
    it and every contact came back nameless. Notices separate contacts with
    blank lines, so the block is the unit that actually means something, and
    it starts where a person would say it starts.
    """
    start = max(0, position - max_chars)
    segment = text[start:position]
    boundary = segment.rfind("\n\n")
    return segment[boundary + 2 :] if boundary != -1 else segment


def _name_near(text: str, position: int) -> str | None:
    """The person's name printed before an address, when there is one.

    Takes the FIRST plausible candidate in the block rather than the nearest.
    Notices put the person first and the office last - "Jane Doe, Program
    Officer, Office of Native American Programs, jane.doe@hud.gov" - so the
    nearest capitalised phrase is reliably the office and the first is
    reliably the person.
    """
    for candidate in NAME_RE.findall(_block_before(text, position)):
        cleaned = candidate.strip()
        if _looks_like_a_person(cleaned):
            return cleaned
    return None


#: Job titles that follow a name after a comma, as notices print them.
TITLE_RE = re.compile(
    r",\s*((?:[A-Z][\w.-]*\s+){0,3}"
    r"(?:Officer|Specialist|Manager|Director|Coordinator|Administrator|Analyst))\b"
)

#: An office line: the organisational unit, which is worth keeping separately
#: because "who do I contact" and "which office handles this" are different
#: questions and a customer often needs the second when the first has moved on.
OFFICE_RE = re.compile(
    r"^\s*((?:[A-Z][\w.'-]*\s+){0,6}"
    r"(?:Office|Bureau|Division|Department|Branch|Administration|Center|Centre)"
    r"(?:\s+(?:of|for)\s+[\w\s'-]{2,60})?)\s*$",
    re.MULTILINE,
)


def _title_near(text: str, position: int) -> str | None:
    matches = TITLE_RE.findall(_block_before(text, position))
    return matches[-1].strip() if matches else None


def _office_near(text: str, position: int) -> str | None:
    matches = OFFICE_RE.findall(_block_before(text, position))
    return matches[-1].strip() if matches else None


def _phone_near(text: str, position: int) -> str | None:
    """The phone number in the same contact block as an address.

    Block-scoped, not a character window. A +/-160 character window reached
    across blank lines into the neighbouring contact, so the Grants.gov
    support address was given the program officer's direct line and the
    grants-management address was given the support desk's 1-800 number.
    Both wrong, and both the kind of wrong a customer only discovers by
    ringing the wrong person.
    """
    block_start = position - len(_block_before(text, position))
    block_end = text.find("\n\n", position)
    if block_end == -1:
        block_end = len(text)
    match = PHONE_RE.search(text[block_start:block_end])
    return match.group(0).strip() if match else None


# --------------------------------------------------------------------------
# submission path
# --------------------------------------------------------------------------

#: Recognised portals, matched against a URL's host. Host rather than the
#: whole string, so a notice that merely *mentions* grants.gov in prose does
#: not turn an agency portal into a Grants.gov submission.
PORTAL_HOSTS: tuple[tuple[str, str, str], ...] = (
    ("grants.gov", "grants_gov", "Grants.gov"),
    ("sam.gov", "agency_portal", "SAM.gov"),
    ("grantsolutions.gov", "agency_portal", "GrantSolutions"),
    ("egrants", "agency_portal", "eGrants"),
    ("justgrants.usdoj.gov", "agency_portal", "JustGrants"),
    ("fluidreview", "foundation_portal", "FluidReview"),
    ("submittable", "foundation_portal", "Submittable"),
)

SUBMISSION_HEADINGS = (
    "how to apply",
    "application submission",
    "submission instructions",
    "submitting an application",
    "method of submission",
    "where to submit",
    "application procedures",
)

#: Time zones a federal notice prints. The wording is kept as written, because
#: "11:59 PM ET" is the instruction the customer has to meet.
TZ_RE = re.compile(
    r"\b(\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?)?\s*)?"
    r"(ET|EST|EDT|CT|CST|CDT|MT|MST|MDT|PT|PST|PDT|AKST|AKDT|HST|UTC)\b",
    re.IGNORECASE,
)

#: The abbreviation a notice prints, mapped to the zone that resolves it.
#:
#: Via `zoneinfo` rather than a fixed offset table, because "ET" means EDT in
#: October and EST in December. A fixed -05:00 would put every autumn deadline
#: an hour late, which for a submission deadline is the whole ballgame.
TZ_ZONES: dict[str, str] = {
    "ET": "America/New_York",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CT": "America/Chicago",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MT": "America/Denver",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PT": "America/Los_Angeles",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "AKST": "America/Anchorage",
    "AKDT": "America/Anchorage",
    "HST": "Pacific/Honolulu",
    "UTC": "UTC",
}

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

DATE_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)

NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?", re.IGNORECASE)


def _parse_deadline(text: str, timezone_label: str | None) -> datetime | None:
    """The stated deadline as an instant, or None when the notice gives no date.

    None rather than a guess. A submission path whose date NativeForge
    invented is worse than one it admits it does not have: the customer would
    plan around it.
    """
    month_match = DATE_RE.search(text)
    if month_match:
        month = MONTHS.index(month_match.group(1).lower()) + 1
        day = int(month_match.group(2))
        year = int(month_match.group(3))
    else:
        numeric = NUMERIC_DATE_RE.search(text)
        if not numeric:
            return None
        month, day, year = (
            int(numeric.group(1)),
            int(numeric.group(2)),
            int(numeric.group(3)),
        )

    hour, minute = 23, 59
    time_match = TIME_RE.search(text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        meridiem = (time_match.group(3) or "").replace(".", "").lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

    zone = ZoneInfo(TZ_ZONES.get((timezone_label or "").upper(), "UTC"))
    try:
        return datetime(year, month, day, hour, minute, tzinfo=zone)
    except ValueError:
        # A date the notice states but the calendar does not have. Recording
        # nothing is the only honest option.
        return None


def extract_submission_path(text: str) -> SubmissionPath | None:
    """The route an application takes, or None when the text does not say."""
    if not text or not text.strip():
        return None

    section_offset, section_heading = _submission_section(text)
    scope = text[section_offset:] if section_offset is not None else text

    method = "unknown"
    portal_name: str | None = None
    submission_url: str | None = None

    for raw in URL_RE.finditer(scope):
        url = raw.group(0).rstrip(".,;:)")
        host = url.split("//", 1)[-1].split("/", 1)[0].lower()
        for needle, matched_method, label in PORTAL_HOSTS:
            if needle in host:
                method, portal_name, submission_url = matched_method, label, url
                break
        if submission_url:
            break

    recipient_email: str | None = None
    if submission_url is None:
        # Only inside a submission section: an address anywhere in a notice is
        # a contact, but an address under "how to apply" is a destination.
        if section_offset is not None:
            window = text[section_offset : section_offset + 900]
            found = EMAIL_RE.search(window)
            if found:
                recipient_email = found.group(0).rstrip(".,;:")
                method = "email"

    if method == "unknown" and _mentions_mail(scope):
        method = "mail"

    deadline_text: str | None = None
    timezone: str | None = None
    tz_match = TZ_RE.search(scope)
    if tz_match:
        deadline_text = tz_match.group(0).strip()
        timezone = tz_match.group(2).upper()
    deadline_at = _parse_deadline(scope, timezone)

    if method == "unknown" and not any(
        (portal_name, submission_url, recipient_email, deadline_text, deadline_at)
    ):
        return None

    return SubmissionPath(
        method=method,
        portal_name=portal_name,
        submission_url=submission_url,
        recipient_email=recipient_email,
        deadline_at=deadline_at,
        deadline_text=deadline_text,
        deadline_timezone=timezone,
        source_section=section_heading,
        source_offset=section_offset,
    )


MAIL_PHRASES = ("by mail", "mailed to", "postmarked", "hand delivery", "courier")


def _mentions_mail(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in MAIL_PHRASES)


def _submission_section(text: str) -> tuple[int | None, str | None]:
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and len(stripped) <= MAX_HEADING_LENGTH:
            lowered = stripped.lower()
            if any(h in lowered for h in SUBMISSION_HEADINGS):
                return offset, stripped
        offset += len(line)
    return None, None


# --------------------------------------------------------------------------
# completeness
# --------------------------------------------------------------------------


def assess_completeness(path: SubmissionPath | None) -> tuple[str, list[str]]:
    """Whether a customer may rely on this path, and what is missing.

    Stored rather than derived at read time, because it is a judgement over
    several fields and two surfaces deriving it independently would
    eventually disagree about the same row.

    A URL alone is not a submission path. Knowing the portal without knowing
    when it closes is most of the way to a missed deadline.
    """
    if path is None:
        return "unclear", ["no_submission_instructions_found"]

    reasons: list[str] = []
    has_route = bool(path.submission_url or path.recipient_email)
    # The parsed instant, not the wording. "11:59 PM ET" with no date is not
    # a deadline, and the CHECK constraint on the table agrees: it refuses to
    # store `verified` without one, which is how the two rules were found to
    # disagree - this said verified, the schema said no, and the schema was
    # right.
    has_deadline = path.deadline_at is not None

    if not has_route:
        reasons.append("no_portal_or_recipient_identified")
    if not has_deadline:
        reasons.append("no_submission_deadline_found")
    if path.method == "unknown":
        reasons.append("submission_method_not_stated")

    if has_route and has_deadline and path.method != "unknown":
        return "verified", reasons
    if has_route or has_deadline:
        return "partial", reasons
    return "unclear", reasons


def extract(text: str, *, text_complete: bool = False) -> ExtractionResult:
    """Everything this module can say about one notice's text."""
    contacts = extract_contacts(text)
    submission = extract_submission_path(text)
    completeness, reasons = assess_completeness(submission)

    notes: list[str] = [f"submission_completeness:{completeness}", *reasons]
    if not text_complete:
        # Said out loud, because it is the difference between "this notice
        # names no program officer" and "we have not read all of it".
        notes.append("text_was_not_known_to_be_complete")

    return ExtractionResult(
        contacts=tuple(contacts),
        submission=submission,
        text_complete=text_complete,
        notes=tuple(notes),
    )
