"""Award document store persistence validation (Gate 127D).

Is a stored document reference fit to act on — without inventing a document, a
location, a proof, or a Tribe's permission to see it.

## Metadata is not content

```text
sha256_digest   64 hex characters describing a file this service never opened
content_length  how many bytes that file has, according to whoever said so
content_type    what kind of file it is, according to the same
object_key      where it would be, if there were anywhere
```

Every one of them is a claim somebody made about a document. None is evidence
the document exists, and `content_verified` is a constant `False`: verifying a
digest means reading bytes, and this service reads none.

## object_key is refused unless a store exists

```text
object_store_configured false  ->  object_key must be absent
object_store_configured true   ->  object_key may name a location
```

The flag is bridged from `detect_body_store_mode()` rather than accepted from a
caller, so a row cannot claim a store into existence. It reports `unconfigured`
today, which means every document this repository can currently describe is a
reference and nothing more.

A key with no store is a path into nothing, and downstream it reads as "the file
is at this location".

## Four things a document does not imply

```text
a reference is not a document       nothing has been read
a document is not a submission      somebody has to file it
a document is not an accepted proof a funder has to accept it
a document is not customer-visible  somebody has to decide that
```

`customer_visible` is the one worth dwelling on. It is never derived — not from
upload status, not from a digest, not from the document being the Tribe's own.
A default of true shows a draft to the wrong person exactly once, and the
default is false with an invariant behind it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.raw_payload_body_store_contract_service import (
    BODY_STORE_MODES,
    PRODUCTION_CAPABLE_MODES,
    detect_body_store_mode,
)
from nativeforge.services.raw_payload_store_contract_service import RETENTION_POLICIES
from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    FACT_STATUSES,
    UNESTABLISHED_FACT_STATUSES,
)

SCHEMA_VERSION = "nf_award_document_store_persistence_validation_v1"

# New in Gate 127. Nothing existing describes a Tribe's own filing, so these are
# named as added rather than bridged - the way Gate 126 named its four new event
# types.
DOCUMENT_KINDS = frozenset(
    {
        "award_letter",
        "award_terms",
        "financial_report",
        "narrative_report",
        "performance_report",
        "audit_report",
        "match_documentation",
        "invoice_or_receipt",
        "board_or_council_resolution",
        "correspondence",
        "closeout_package",
        "other",
        "unknown",
    }
)

DOCUMENT_STATUSES = frozenset(
    {
        "reference_recorded",
        "awaiting_upload",
        "stored",
        "superseded",
        "withdrawn",
        "needs_human_review",
        "unknown",
    }
)

# The one status that asserts bytes exist somewhere.
STORED_STATUSES = frozenset({"stored"})

DOCUMENT_SOURCES = frozenset(
    {
        "tenant_supplied",
        "human_entered",
        "evidence_extracted",
        "system_generated",
        "unsupported_document_type",
        "needs_human_review",
        "unknown",
    }
)

# Sources nobody has established.
UNESTABLISHED_SOURCES = frozenset(
    {"unknown", "needs_human_review", "unsupported_document_type"}
)

# Gate 96's retention vocabulary, imported so the bridge is a fact not a copy.
RETENTION_CLASSES = RETENTION_POLICIES

# The three relationship columns. All optional, at least one required, none an
# authority.
RELATIONSHIP_FIELDS: tuple[str, ...] = (
    "awarded_grant_id",
    "award_requirement_id",
    "proof_event_id",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")

VALIDATION_FIELDS: tuple[str, ...] = (
    "document_kind_valid",
    "document_status_valid",
    "document_title_present",
    "relationship_present",
    "object_reference_consistent",
    "object_store_configured_consistent",
    "content_metadata_valid",
    "sha256_digest_valid",
    "retention_class_valid",
    "legal_hold_consistent",
    "customer_visible_consistent",
    "fact_status_valid",
    "human_review_required",
    "unknowns_labelled",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def detect_object_store_configured() -> bool:
    """Is there anywhere for a document's bytes to live?

    Asked of `detect_body_store_mode()` rather than answered again here. That
    detector already exists, already reports `unconfigured`, and already knows
    which modes count as production-capable. Writing a second one would be a
    second answer to one question - the shape Gate 114 spent a whole gate
    collapsing and Gate 126 hit again with two names for one module.

    It serves raw source payloads today and an award document is a different
    corpus, but "is object storage configured" is not a per-corpus question.
    """
    return bool(detect_body_store_mode() in PRODUCTION_CAPABLE_MODES)


def validate_award_document(
    *,
    document_kind: Any = None,
    document_status: Any = None,
    document_title: Any = None,
    document_description: Any = None,
    document_source: Any = None,
    document_source_ref: Any = None,
    awarded_grant_id: Any = None,
    award_requirement_id: Any = None,
    proof_event_id: Any = None,
    object_store_provider: Any = None,
    object_bucket: Any = None,
    object_key: Any = None,
    object_version: Any = None,
    content_type: Any = None,
    content_length: Any = None,
    sha256_digest: Any = None,
    retention_class: Any = None,
    legal_hold: bool = False,
    customer_visible: bool = False,
    fact_status: Any = None,
    object_store_configured: bool | None = None,
) -> dict[str, Any]:
    """Is this document reference fit to be stored and acted on? Deny by default.

    ``object_store_configured`` is injectable so the permitted branch is
    reachable in a test. Left as ``None`` it is measured, and it measures false.
    """
    blocked_reasons: list[str] = []
    refused_claims: list[str] = []
    unknown_fields: list[str] = []

    store_configured = (
        detect_object_store_configured()
        if object_store_configured is None
        else bool(object_store_configured)
    )

    # -- the title, the one thing that cannot be unknown ---------------------
    title = str(document_title or "").strip()
    document_title_present = bool(title)
    if not document_title_present:
        blocked_reasons.append("document_without_a_title")

    # -- what kind of document -----------------------------------------------
    kind = str(document_kind or "unknown").strip().lower()
    document_kind_valid = kind in DOCUMENT_KINDS
    if not document_kind_valid:
        blocked_reasons.append(f"document_kind_not_recognised:{kind}")
    if kind == "unknown":
        unknown_fields.append("document_kind")
        # Never guessed from the title or the content type. "Report.pdf" could
        # be financial, narrative or performance, and the three have different
        # retention.
        blocked_reasons.append("document_kind_unestablished_and_never_inferred")

    # -- where it is in its own lifecycle ------------------------------------
    status = str(document_status or "unknown").strip().lower()
    document_status_valid = status in DOCUMENT_STATUSES
    if not document_status_valid:
        blocked_reasons.append(f"document_status_not_recognised:{status}")
    if status == "unknown":
        unknown_fields.append("document_status")

    # -- where it came from ---------------------------------------------------
    source = str(document_source or "unknown").strip().lower()
    document_source_valid = source in DOCUMENT_SOURCES
    if not document_source_valid:
        blocked_reasons.append(f"document_source_not_recognised:{source}")
    if source in UNESTABLISHED_SOURCES:
        unknown_fields.append("document_source")

    # -- what it is attached to ----------------------------------------------
    relationships = {
        "awarded_grant_id": str(awarded_grant_id or "").strip() or None,
        "award_requirement_id": str(award_requirement_id or "").strip() or None,
        "proof_event_id": str(proof_event_id or "").strip() or None,
    }
    relationship_present = any(relationships.values())
    if not relationship_present:
        # A document attached to nothing is a file in a drawer nobody can find.
        blocked_reasons.append("document_without_any_relationship")

    # -- where the bytes would be, if there were anywhere --------------------
    key = str(object_key or "").strip()
    bucket = str(object_bucket or "").strip()
    provider = str(object_store_provider or "").strip()
    version = str(object_version or "").strip()

    object_reference_consistent = True
    if key and not store_configured:
        object_reference_consistent = False
        blocked_reasons.append("object_key_without_a_configured_object_store")
    if bucket and not store_configured:
        object_reference_consistent = False
        blocked_reasons.append("object_bucket_without_a_configured_object_store")
    if provider and not store_configured:
        object_reference_consistent = False
        blocked_reasons.append("object_store_provider_without_a_configured_store")
    if version and not key:
        object_reference_consistent = False
        blocked_reasons.append("object_version_without_an_object_key")

    object_store_configured_consistent = bool(store_configured or not key)

    if status in STORED_STATUSES and not (store_configured and key):
        # `stored` asserts bytes exist somewhere, which requires somewhere.
        blocked_reasons.append("stored_status_without_a_location")

    metadata_only = not key

    # -- metadata ABOUT a document nobody here has opened --------------------
    length = content_length
    content_metadata_valid = True
    if length not in (None, ""):
        try:
            length = int(length)
        except (TypeError, ValueError):
            length = None
            content_metadata_valid = False
            blocked_reasons.append("content_length_is_not_an_integer")
        if isinstance(length, int) and length < 0:
            content_metadata_valid = False
            blocked_reasons.append("content_length_is_negative")
    else:
        length = None

    digest = str(sha256_digest or "").strip().lower()
    sha256_digest_valid = True
    if digest and not _SHA256.match(digest):
        sha256_digest_valid = False
        blocked_reasons.append("sha256_digest_is_not_sha256_shaped")

    # A digest on a metadata-only row is legitimate: a Tribe handing over a
    # file and its SHA-256 is exactly how you would later verify it, once there
    # is somewhere to verify it against.
    #
    # The first version refused the row, which made the ordinary
    # metadata-plus-digest case permanently un-storable and put
    # `document_ready_for_reference` out of reach for it. What is dangerous is
    # not recording the digest; it is a reader taking it for verification. So
    # the state is derived and reported, and `content_verified` stays a
    # constant `False` with an invariant behind it.
    digest_is_unverified = bool(digest and metadata_only)

    # -- how long it is kept --------------------------------------------------
    retention = str(retention_class or "").strip().lower()
    retention_class_valid = retention in RETENTION_CLASSES
    if not retention_class_valid:
        blocked_reasons.append(f"retention_class_not_recognised:{retention or 'none'}")

    # -- who may move it, and who may see it ---------------------------------
    hold = bool(legal_hold)
    visible = bool(customer_visible)

    # -- the fact status behind all of it ------------------------------------
    fact = str(fact_status or "unknown").strip().lower()
    fact_status_valid = fact in FACT_STATUSES
    if not fact_status_valid:
        blocked_reasons.append(f"fact_status_not_recognised:{fact}")
    facts_established = fact in ACTIONABLE_FACT_STATUSES
    fact_status_supports_visibility = fact not in UNESTABLISHED_FACT_STATUSES
    if fact in UNESTABLISHED_FACT_STATUSES:
        unknown_fields.append("fact_status")

    customer_visible_consistent = True
    if visible and not fact_status_supports_visibility:
        # Showing a Tribe a document nobody has established as theirs is how the
        # wrong file ends up in front of the wrong government.
        customer_visible_consistent = False
        blocked_reasons.append("customer_visible_on_an_unestablished_fact_status")

    # -- derived, so the invariants have something of their own to read ------
    # A legal hold and an archive are mutually exclusive states, and this
    # service never archives, so `legal_hold_consistent` is about the pair a
    # caller supplied rather than about anything here.
    legal_hold_consistent = True
    archivable = not hold

    document_is_stored = bool(status in STORED_STATUSES and store_configured and key)
    document_is_metadata_only = bool(metadata_only)

    unknowns_labelled = True
    human_review_required = bool(
        unknown_fields
        or blocked_reasons
        or refused_claims
        or not facts_established
        or hold
    )

    document_ready_for_reference = bool(
        document_title_present
        and document_kind_valid
        and kind != "unknown"
        and document_status_valid
        and document_source_valid
        and source not in UNESTABLISHED_SOURCES
        and relationship_present
        and object_reference_consistent
        and content_metadata_valid
        and sha256_digest_valid
        and retention_class_valid
        and facts_established
        and not blocked_reasons
        and not refused_claims
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_kind": kind,
            "document_kind_valid": document_kind_valid,
            "document_status": status,
            "document_status_valid": document_status_valid,
            "document_title_present": document_title_present,
            "document_title": title or None,
            "document_description": str(document_description or "") or None,
            "document_source": source,
            "document_source_valid": document_source_valid,
            "document_source_ref": str(document_source_ref or "") or None,
            **relationships,
            "relationship_present": relationship_present,
            "relationship_count": sum(1 for v in relationships.values() if v),
            # Measured, not asserted, and injectable so the branch is reachable.
            "object_store_configured": store_configured,
            "object_store_provider": provider or None,
            "object_bucket": bucket or None,
            "object_key": key or None,
            "object_version": version or None,
            "object_reference_consistent": object_reference_consistent,
            "object_store_configured_consistent": object_store_configured_consistent,
            "content_type": str(content_type or "") or None,
            "content_length": length,
            "content_metadata_valid": content_metadata_valid,
            "sha256_digest": digest or None,
            "sha256_digest_valid": sha256_digest_valid,
            # A digest nobody has checked against any bytes. Reported, never
            # refused, and never read as verification.
            "digest_is_unverified": digest_is_unverified,
            "retention_class": retention or None,
            "retention_class_valid": retention_class_valid,
            "legal_hold": hold,
            "legal_hold_consistent": legal_hold_consistent,
            "archivable": archivable,
            "customer_visible": visible,
            "customer_visible_consistent": customer_visible_consistent,
            "fact_status": fact,
            "fact_status_valid": fact_status_valid,
            "facts_established": facts_established,
            "fact_status_supports_visibility": fact_status_supports_visibility,
            # Derived. The invariants read these.
            "document_is_stored": document_is_stored,
            "document_is_metadata_only": document_is_metadata_only,
            "unknowns_labelled": unknowns_labelled,
            "unknown_fields": sorted(set(unknown_fields)),
            "refused_claims": sorted(set(refused_claims)),
            "human_review_required": human_review_required,
            "document_ready_for_reference": document_ready_for_reference,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants. Nothing here reads a document, contacts a store,
            # infers a submission, or decides what a Tribe may see.
            "document_content_read": False,
            "object_store_contacted": False,
            "content_verified": False,
            "storage_inferred_from_object_key": False,
            "content_inferred_from_metadata": False,
            "submission_inferred_from_document": False,
            "acceptance_inferred_from_document": False,
            "visibility_inferred_from_upload": False,
            "fabricated": False,
        }
    )


def validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this validation must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in (
        "document_content_read",
        "object_store_contacted",
        "content_verified",
        "storage_inferred_from_object_key",
        "content_inferred_from_metadata",
        "submission_inferred_from_document",
        "acceptance_inferred_from_document",
        "visibility_inferred_from_upload",
        "fabricated",
    ):
        if result.get(field):
            failures.append(f"validation_claimed_{field}")

    # Two derived values compared against each other, which is the only kind
    # that can fail without ordinary bad input reaching it.
    if result.get("document_is_stored") and result.get("document_is_metadata_only"):
        failures.append("a_document_was_both_stored_and_metadata_only")

    # A digest is never verification, whatever else is true of the row.
    if result.get("digest_is_unverified") and result.get("content_verified"):
        failures.append("an_unverified_digest_was_reported_as_verified")

    # Everything below is guarded on `storable`. A caller supplying an
    # `object_key` with no store is bad input, which `blocked_reasons` names;
    # an unguarded invariant reading it would fire on that input, which is the
    # validation-rule-misnamed shape Gate 124D shipped three of and Gate 126
    # found five more of.
    storable = not result.get("blocked_reasons") and not result.get("refused_claims")
    if storable and result.get("object_key"):
        if not result.get("object_store_configured"):
            failures.append("a_storable_object_key_without_a_configured_store")
    if storable and result.get("document_is_stored"):
        if not result.get("object_key"):
            failures.append("a_storable_stored_document_without_a_location")
    if storable and result.get("document_status") == "stored":
        if not result.get("document_is_stored"):
            failures.append("a_storable_stored_document_did_not_derive_as_stored")
    if storable and result.get("customer_visible"):
        if not result.get("customer_visible_consistent"):
            failures.append("a_storable_document_was_visible_inconsistently")

    if result.get("document_ready_for_reference"):
        for conjunct in (
            "document_title_present",
            "document_kind_valid",
            "document_status_valid",
            "document_source_valid",
            "relationship_present",
            "object_reference_consistent",
            "content_metadata_valid",
            "sha256_digest_valid",
            "retention_class_valid",
            "facts_established",
        ):
            if not result.get(conjunct):
                failures.append(f"ready_for_reference_without:{conjunct}")
        if result.get("blocked_reasons"):
            failures.append("ready_for_reference_with_blocked_reasons")
        if result.get("refused_claims"):
            failures.append("ready_for_reference_with_refused_claims")

    if result.get("unknown_fields") and not result.get("human_review_required"):
        failures.append("unknown_fields_without_human_review")

    if result.get("refused_claims") and not result.get("human_review_required"):
        failures.append("a_refused_claim_without_human_review")

    if result.get("legal_hold") and result.get("archivable"):
        failures.append("a_document_under_legal_hold_was_archivable")

    if not result.get("unknowns_labelled"):
        failures.append("an_unknown_was_not_labelled")

    return sorted(set(failures))


def vocabulary_invariant_failures() -> list[str]:
    """The bridges must stay bridges."""
    failures: list[str] = []
    if set(RETENTION_CLASSES) != set(RETENTION_POLICIES):
        failures.append("retention_class_forked_from_retention_policies")
    if not PRODUCTION_CAPABLE_MODES <= BODY_STORE_MODES:
        failures.append("production_capable_modes_left_the_body_store_vocabulary")
    if detect_object_store_configured() and detect_body_store_mode() not in (
        PRODUCTION_CAPABLE_MODES
    ):
        failures.append("object_store_configured_disagrees_with_the_body_store_mode")
    return sorted(failures)


def build_validation_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them established."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = validate_award_document(**case["document"])
        rows.append(
            {
                "case": case["case"],
                "document_kind": result["document_kind"],
                "document_status": result["document_status"],
                "document_source": result["document_source"],
                "relationship_present": result["relationship_present"],
                "relationship_count": result["relationship_count"],
                "object_store_configured": result["object_store_configured"],
                "object_key_present": bool(result["object_key"]),
                "object_reference_consistent": result["object_reference_consistent"],
                "document_is_stored": result["document_is_stored"],
                "document_is_metadata_only": result["document_is_metadata_only"],
                "content_metadata_valid": result["content_metadata_valid"],
                "sha256_digest_valid": result["sha256_digest_valid"],
                "digest_is_unverified": result["digest_is_unverified"],
                "retention_class": result["retention_class"],
                "legal_hold": result["legal_hold"],
                "archivable": result["archivable"],
                "customer_visible": result["customer_visible"],
                "fact_status": result["fact_status"],
                "facts_established": result["facts_established"],
                "document_ready_for_reference": result["document_ready_for_reference"],
                "human_review_required": result["human_review_required"],
                "unknown_fields": result["unknown_fields"],
                "refused_claims": result["refused_claims"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": validation_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "ready_count": sum(1 for r in rows if r["document_ready_for_reference"]),
            "stored_count": sum(1 for r in rows if r["document_is_stored"]),
            "metadata_only_count": sum(
                1 for r in rows if r["document_is_metadata_only"]
            ),
            "customer_visible_count": sum(1 for r in rows if r["customer_visible"]),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
            "vocabulary_invariant_failures": vocabulary_invariant_failures(),
            "object_store_contacted": False,
            "document_content_read": False,
            "fabricated": False,
        }
    )
