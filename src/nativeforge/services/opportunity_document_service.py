"""Gate 175B/C/D/G: a document as versioned evidence about an opportunity.

NativeForge must not assume the landing page or the API record holds the
authoritative answer. It frequently does not. Eligibility lives on page 14 of
an attachment; the match requirement lives in an appendix; the FAQ published
three weeks later is what the programme officer will actually cite.

So a document is a first-class object with an identity, a lifecycle and a
version chain, and it points at a canonical opportunity - which nothing in the
repository did before this gate. `nf_award_documents` exists, holds 876
archived rows of `financial_report` and `award_letter`, and hangs off
`awarded_grant_id`: those are POST-AWARD compliance artifacts, a different
lifecycle stage, and reusing that table would file a funder's eligibility
language against a grant nobody has won.

**The state that matters most is `UNSUPPORTED`.** A scanned PDF with no text
layer, or a media type no parser handles, must never report "no requirements
found" - that is byte-identical to a NOFO which genuinely imposes none, and it
is the difference between "we could not read this" and "there is nothing to
read". `PARTIAL` carries the same weight for a document that parsed some
sections and not others.

**Identity is the bytes.** A document version is keyed by content hash, so the
same URL serving changed bytes is a NEW version, and the same bytes appearing
at a second URL is the SAME content with another location - which is what
stops an agency's mirror from looking like an amendment.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_opportunity_document_v1"

DOCUMENT_MODEL_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# 175C: document types
# --------------------------------------------------------------------

NOFO = "NOFO"
FOA = "FOA"
RFP = "RFP"
RFA = "RFA"
NOTICE = "NOTICE"
GUIDANCE = "GUIDANCE"
FAQ = "FAQ"
AMENDMENT = "AMENDMENT"
APPENDIX = "APPENDIX"
APPLICATION_INSTRUCTIONS = "APPLICATION_INSTRUCTIONS"
BUDGET = "BUDGET"
FORM = "FORM"
ATTACHMENT = "ATTACHMENT"
WEBPAGE = "WEBPAGE"
OTHER_DOCUMENT = "OTHER_DOCUMENT"

_SEED_DOCUMENT_TYPES: tuple[str, ...] = (
    NOFO,
    FOA,
    RFP,
    RFA,
    NOTICE,
    GUIDANCE,
    FAQ,
    AMENDMENT,
    APPENDIX,
    APPLICATION_INSTRUCTIONS,
    BUDGET,
    FORM,
    ATTACHMENT,
    WEBPAGE,
    OTHER_DOCUMENT,
)

_DOCUMENT_TYPES: dict[str, str] = {key: "seed" for key in _SEED_DOCUMENT_TYPES}


def document_types() -> tuple[str, ...]:
    return tuple(sorted(_DOCUMENT_TYPES))


def register_document_type(name: str, *, origin: str = "runtime") -> str:
    """Data-driven, like sectors. A funder inventing a document kind is a
    FACT, not an `OTHER_DOCUMENT`."""
    key = str(name or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not key:
        return OTHER_DOCUMENT
    _DOCUMENT_TYPES.setdefault(key, origin)
    return key


def reset_registered_document_types() -> None:
    for key in [k for k, origin in _DOCUMENT_TYPES.items() if origin != "seed"]:
        del _DOCUMENT_TYPES[key]


#: Types whose content can CHANGE what an earlier document said. An FAQ
#: clarifies; an amendment supersedes. Neither erases.
CLARIFYING_TYPES: frozenset[str] = frozenset({FAQ, GUIDANCE})
SUPERSEDING_TYPES: frozenset[str] = frozenset({AMENDMENT})

#: Types that routinely carry binding facts the landing page omits. Named so a
#: pipeline that only reads the record can be shown what it is missing.
AUTHORITATIVE_FOR_FACTS: frozenset[str] = frozenset(
    {NOFO, FOA, RFP, RFA, AMENDMENT, APPENDIX, APPLICATION_INSTRUCTIONS}
)

# --------------------------------------------------------------------
# 175D: document state
# --------------------------------------------------------------------

NOT_FETCHED = "NOT_FETCHED"
FETCHED = "FETCHED"
PARSE_PENDING = "PARSE_PENDING"
PARSED = "PARSED"
PARTIAL = "PARTIAL"
UNSUPPORTED = "UNSUPPORTED"
FAILED = "FAILED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

DOCUMENT_STATES: tuple[str, ...] = (
    NOT_FETCHED,
    FETCHED,
    PARSE_PENDING,
    PARSED,
    PARTIAL,
    UNSUPPORTED,
    FAILED,
    REVIEW_REQUIRED,
)

STATE_MEANINGS: dict[str, str] = {
    NOT_FETCHED: "we know this document exists and have not retrieved it",
    FETCHED: "the bytes are on file and nothing has read them yet",
    PARSE_PENDING: "queued for extraction",
    PARSED: "read end to end; an empty result here is a real finding",
    PARTIAL: (
        "some sections were read and some were not; an absent fact may be in "
        "the part we could not read"
    ),
    UNSUPPORTED: (
        "no parser handles this media type or the file has no text layer - "
        "this is NOT 'no requirements found'"
    ),
    FAILED: "extraction was attempted and errored",
    REVIEW_REQUIRED: "a human must read this one",
}

#: States in which an ABSENT fact means something. Everywhere else, absence is
#: our limitation rather than the funder's silence, and the distinction is the
#: single most important thing this module encodes.
ABSENCE_IS_MEANINGFUL: frozenset[str] = frozenset({PARSED})

#: States that cannot support any factual claim at all.
NO_FACTS_POSSIBLE: frozenset[str] = frozenset(
    {NOT_FETCHED, FETCHED, PARSE_PENDING, UNSUPPORTED, FAILED}
)

DOCUMENT_FIELDS: tuple[str, ...] = (
    "document_id",
    "canonical_id",
    "document_type",
    "title",
    "location_ref",
    "content_sha256",
    "media_type",
    "size_bytes",
    "page_count",
    "document_state",
    "extraction_method",
    "retrieved_at",
    "version_ordinal",
    "supersedes_document_id",
    "amended_by_document_id",
    "clarifies_document_id",
    "effective_date",
    "observed_at",
    "raw_payload_sha256",
    "source_id",
    "known_gaps",
    "model_version",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_document_id(*, canonical_id: Any, content_sha256: Any) -> str:
    """Identity is the CONTENT, not the URL.

    The same bytes at a second URL is one document with two locations; the
    same URL serving new bytes is a new document version. Keying on the URL
    would make an agency's mirror look like an amendment, and would make a
    silent re-publication invisible.
    """
    parts = [str(canonical_id or ""), str(content_sha256 or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_document(
    *,
    canonical_id: Any,
    document_type: str,
    content_sha256: Any,
    location_ref: Any = None,
    title: Any = None,
    media_type: Any = None,
    size_bytes: Any = None,
    page_count: Any = None,
    document_state: str = NOT_FETCHED,
    extraction_method: Any = None,
    retrieved_at: Any = None,
    version_ordinal: int = 1,
    supersedes_document_id: Any = None,
    amended_by_document_id: Any = None,
    clarifies_document_id: Any = None,
    effective_date: Any = None,
    observed_at: Any = None,
    raw_payload_sha256: Any = None,
    source_id: Any = None,
    known_gaps: list[str] | None = None,
) -> dict[str, Any]:
    """One document version."""
    state = str(document_state)
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_id": build_document_id(
                canonical_id=canonical_id, content_sha256=content_sha256
            ),
            "canonical_id": str(canonical_id) if canonical_id else None,
            "document_type": str(document_type),
            "title": str(title) if title else None,
            "location_ref": str(location_ref) if location_ref else None,
            "content_sha256": str(content_sha256) if content_sha256 else None,
            "media_type": str(media_type) if media_type else None,
            "size_bytes": int(size_bytes) if size_bytes is not None else None,
            "page_count": int(page_count) if page_count is not None else None,
            "document_state": state,
            "extraction_method": (
                str(extraction_method) if extraction_method else None
            ),
            "retrieved_at": retrieved_at,
            "version_ordinal": int(version_ordinal),
            "supersedes_document_id": (
                str(supersedes_document_id) if supersedes_document_id else None
            ),
            "amended_by_document_id": (
                str(amended_by_document_id) if amended_by_document_id else None
            ),
            "clarifies_document_id": (
                str(clarifies_document_id) if clarifies_document_id else None
            ),
            "effective_date": effective_date,
            "observed_at": observed_at,
            "raw_payload_sha256": (
                str(raw_payload_sha256) if raw_payload_sha256 else None
            ),
            "source_id": str(source_id) if source_id else None,
            "known_gaps": sorted(known_gaps or []),
            "model_version": DOCUMENT_MODEL_VERSION,
            # The two derived facts every consumer needs and nobody should
            # re-derive.
            "absence_is_meaningful": state in ABSENCE_IS_MEANINGFUL,
            "can_support_facts": state not in NO_FACTS_POSSIBLE,
        }
    )


def document_invariant_failures(document: dict[str, Any]) -> list[str]:
    """Refuse a document that cannot be traced or whose state lies."""
    failures: list[str] = []

    for field in DOCUMENT_FIELDS:
        if field not in document:
            failures.append(f"document_missing_field:{field}")

    kind = str(document.get("document_type") or "")
    if kind not in document_types():
        failures.append(f"document_type_outside_the_vocabulary:{kind or 'missing'}")

    state = str(document.get("document_state") or "")
    if state not in DOCUMENT_STATES:
        failures.append(f"document_state_outside_the_vocabulary:{state or 'missing'}")

    if not document.get("canonical_id"):
        failures.append("document_not_bound_to_a_canonical_opportunity")

    # A document that has been fetched has bytes. One that has not, has not.
    if state != NOT_FETCHED and not document.get("content_sha256"):
        failures.append(f"document_in_state_{state}_has_no_content_hash")
    if state == NOT_FETCHED and document.get("extraction_method"):
        failures.append("unfetched_document_claims_an_extraction_method")

    # The load-bearing one: a parsed state must have read something.
    if state == PARSED and not document.get("extraction_method"):
        failures.append("parsed_document_names_no_extraction_method")
    if state in {PARSED, PARTIAL} and not document.get("size_bytes"):
        failures.append(f"document_in_state_{state}_has_zero_source_bytes")

    if int(document.get("version_ordinal") or 0) < 1:
        failures.append("version_ordinal_is_not_a_version")

    # A supersession that points at itself is a cycle of length one.
    if document.get("supersedes_document_id") == document.get("document_id"):
        failures.append("document_supersedes_itself")
    if document.get("amended_by_document_id") == document.get("document_id"):
        failures.append("document_amends_itself")

    if document.get("absence_is_meaningful") and state not in ABSENCE_IS_MEANINGFUL:
        failures.append(f"state_{state}_claims_absence_is_meaningful")

    return sorted(set(failures))


def build_version_chain(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """175G: the amendment chain, and what it refuses to represent."""
    by_id = {str(d["document_id"]): d for d in documents}
    failures: list[str] = []

    # Supersession cycles. A chain that loops has no newest member, and a
    # "latest version" pointer over it would pick one arbitrarily.
    for document in documents:
        seen: set[str] = set()
        current = str(document["document_id"])
        while current and current in by_id:
            if current in seen:
                failures.append(f"supersession_cycle:{current}")
                break
            seen.add(current)
            current = str(by_id[current].get("supersedes_document_id") or "")

    # An amendment that names a predecessor nobody has.
    for document in documents:
        target = document.get("supersedes_document_id")
        if target and str(target) not in by_id:
            failures.append(f"amendment_references_missing_predecessor:{target}")
        clarified = document.get("clarifies_document_id")
        if clarified and str(clarified) not in by_id:
            failures.append(f"clarification_references_missing_document:{clarified}")

    superseded = {
        str(d["supersedes_document_id"])
        for d in documents
        if d.get("supersedes_document_id")
    }
    latest = [d for d in documents if str(d["document_id"]) not in superseded]

    # The "latest pointer is newest" check. Ordinals must agree with the chain.
    for document in documents:
        target = document.get("supersedes_document_id")
        if target and str(target) in by_id:
            predecessor = by_id[str(target)]
            if int(document["version_ordinal"]) <= int(predecessor["version_ordinal"]):
                failures.append(
                    f"successor_ordinal_not_newer:{document['document_id']}"
                )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_count": len(documents),
            "latest_document_ids": sorted(str(d["document_id"]) for d in latest),
            "latest_count": len(latest),
            "superseded_count": len(superseded),
            "clarification_count": sum(
                1 for d in documents if d.get("clarifies_document_id")
            ),
            "chain_failures": sorted(set(failures)),
            "chain_is_valid": not failures,
            # A clarification never removes what it clarifies.
            "clarifications_preserve_their_target": all(
                str(d["clarifies_document_id"]) in by_id
                for d in documents
                if d.get("clarifies_document_id")
            ),
        }
    )


def describe_document_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": DOCUMENT_MODEL_VERSION,
            "document_types": list(document_types()),
            "seed_document_type_count": len(_SEED_DOCUMENT_TYPES),
            "document_states": list(DOCUMENT_STATES),
            "document_fields": list(DOCUMENT_FIELDS),
            "every_state_has_a_meaning": set(STATE_MEANINGS) == set(DOCUMENT_STATES),
            "every_state_meaning_is_distinct": len(set(STATE_MEANINGS.values()))
            == len(DOCUMENT_STATES),
            "document_types_are_extensible": True,
            "identity_is_the_content_hash": True,
            # The rule this module exists for.
            "missing_parser_is_not_empty_truth": UNSUPPORTED
            not in ABSENCE_IS_MEANINGFUL,
            "partial_parse_is_not_empty_truth": PARTIAL not in ABSENCE_IS_MEANINGFUL,
            "absence_is_meaningful_only_when_parsed": sorted(ABSENCE_IS_MEANINGFUL),
            "states_that_support_no_facts": sorted(NO_FACTS_POSSIBLE),
            "clarifying_types": sorted(CLARIFYING_TYPES),
            "superseding_types": sorted(SUPERSEDING_TYPES),
            "authoritative_for_facts": sorted(AUTHORITATIVE_FOR_FACTS),
        }
    )
