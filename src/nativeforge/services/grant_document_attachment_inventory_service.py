"""Grant document attachment inventory (Gate 91F).

Lists the agency documents attached to an opportunity or an awarded grant,
*before* anything tries to read them.

## Inventory is not parsing, and not clearance

Three separate facts, three separate fields, because collapsing them is how a
listed document becomes a read one:

``parse_status``            has anything tried to parse it?
``text_extraction_status``  did text come out?
``terms_status``            are we allowed to retrieve it at all?

A document can be inventoried, blocked on terms, and never parsed. That is a
normal state and the inventory says so rather than looking incomplete.

## No download in this gate

Nothing is fetched. ``retrieval_method`` records how a document *came to be*
local - and in this gate the only honest value is ``local_fixture``. A row with
a ``source_url`` and no ``local_path`` is inventoried as
``not_retrieved``: we know it exists, we have not got it.

## Hash everything local

Every local file is hashed with SHA-256 via
``notice_artifact_model_service.content_hash_of``. The hash is what makes an
extraction reproducible and what proves a fixture has not drifted - the same
role fixture hashing plays in Gates 85-90.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.notice_artifact_model_service import (
    content_hash_of,
    sniff_artifact_type,
)

SCHEMA_VERSION = "nf_grant_document_attachment_inventory_v1"

DOCUMENT_TYPES = frozenset(
    {
        "NOFO",
        "amendment",
        "application_instructions",
        "budget_instructions",
        "terms_and_conditions",
        "assurances",
        "reporting_guidance",
        "closeout_guidance",
        "award_package",
        "portal_instruction",
        "appendix",
        "unknown",
    }
)

# Document types that speak to post-award obligations. Used to prioritise
# extraction, never to skip the others.
POST_AWARD_DOCUMENT_TYPES = frozenset(
    {
        "terms_and_conditions",
        "reporting_guidance",
        "closeout_guidance",
        "award_package",
        "assurances",
    }
)

# Types that describe what must be submitted *with an application*. Kept
# distinct because an application requirement is not a post-award obligation.
APPLICATION_DOCUMENT_TYPES = frozenset(
    {"application_instructions", "budget_instructions"}
)

OWNER_TYPES = frozenset({"opportunity", "awarded_grant", "source", "unknown"})

RETRIEVAL_METHODS = frozenset(
    {"local_fixture", "recorded_transport", "not_retrieved", "unknown"}
)

PARSE_STATUSES = frozenset({"not_attempted", "parsed", "blocked", "unsupported"})

TEXT_EXTRACTION_STATUSES = frozenset(
    {"not_attempted", "extracted", "parser_unavailable", "manual_review_required",
     "blocked"}
)

TERMS_STATUSES = frozenset(
    {"NO_REVIEW_REQUIRED", "TERMS_REVIEW_REQUIRED", "HUMAN_REVIEW_ONLY", "UNKNOWN"}
)

EVIDENCE_ROLES = frozenset(
    {
        "primary_notice",
        "amendment_evidence",
        "post_award_terms",
        "application_instruction",
        "supporting_appendix",
        "unknown",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _evidence_role_for(document_type: str) -> str:
    if document_type == "NOFO":
        return "primary_notice"
    if document_type == "amendment":
        return "amendment_evidence"
    if document_type in POST_AWARD_DOCUMENT_TYPES:
        return "post_award_terms"
    if document_type in APPLICATION_DOCUMENT_TYPES:
        return "application_instruction"
    if document_type == "appendix":
        return "supporting_appendix"
    return "unknown"


def build_document_inventory_entry(
    *,
    document_id: str,
    owner_type: str,
    owner_id: str,
    document_type: str | None = None,
    filename: str | None = None,
    source_url: str | None = None,
    local_path: str | Path | None = None,
    content_type: str | None = None,
    retrieved_at: str | None = None,
    retrieval_method: str | None = None,
    terms_status: str = "UNKNOWN",
) -> dict[str, Any]:
    """Inventory one document. Reads the file only to hash and size it."""
    blocked: list[str] = []

    dtype = document_type if document_type in DOCUMENT_TYPES else "unknown"
    if document_type and document_type not in DOCUMENT_TYPES:
        blocked.append(f"unrecognised_document_type:{document_type}")

    otype = owner_type if owner_type in OWNER_TYPES else "unknown"
    if owner_type not in OWNER_TYPES:
        blocked.append(f"unrecognised_owner_type:{owner_type}")
    if not str(owner_id or "").strip():
        blocked.append("no_owner_id")

    path = Path(local_path) if local_path else None
    exists = bool(path and path.is_file())

    if exists:
        hash_sha256 = content_hash_of(path)
        size_bytes = path.stat().st_size
        method = retrieval_method or "local_fixture"
        artifact_type = sniff_artifact_type(path)
    else:
        hash_sha256 = None
        size_bytes = None
        method = retrieval_method or "not_retrieved"
        artifact_type = "unknown"
        if local_path:
            blocked.append("local_path_does_not_exist")
        else:
            # Known to exist upstream, not held here. Not an error.
            blocked.append("not_retrieved_no_download_in_this_gate")

    if method not in RETRIEVAL_METHODS:
        blocked.append(f"unrecognised_retrieval_method:{method}")
        method = "unknown"

    terms = terms_status if terms_status in TERMS_STATUSES else "UNKNOWN"
    if terms != "NO_REVIEW_REQUIRED":
        blocked.append(f"terms_status:{terms}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_id": document_id,
            "owner_type": otype,
            "owner_id": owner_id,
            "document_type": dtype,
            "filename": filename or (path.name if path else None),
            "source_url": source_url,
            "local_path": str(path) if path else None,
            "content_type": content_type,
            "artifact_type": artifact_type,
            "hash_sha256": hash_sha256,
            "size_bytes": size_bytes,
            "retrieved_at": retrieved_at,
            "retrieval_method": method,
            "terms_status": terms,
            # Three separate facts, never merged.
            "parse_status": "not_attempted",
            "text_extraction_status": "not_attempted",
            "evidence_role": _evidence_role_for(dtype),
            "is_post_award_document": dtype in POST_AWARD_DOCUMENT_TYPES,
            "is_application_document": dtype in APPLICATION_DOCUMENT_TYPES,
            "blocked_reasons": blocked,
            # Constants for this gate.
            "downloaded": False,
            "network_access_performed": False,
            "fabricated": False,
        }
    )


def build_document_inventory(
    *, documents: list[dict[str, Any]]
) -> dict[str, Any]:
    entries = [build_document_inventory_entry(**d) for d in documents]

    by_type: dict[str, int] = {}
    for entry in entries:
        by_type[entry["document_type"]] = by_type.get(entry["document_type"], 0) + 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "document_count": len(entries),
            "documents": entries,
            "by_document_type": dict(sorted(by_type.items())),
            "hashed_count": sum(1 for e in entries if e["hash_sha256"]),
            "post_award_document_count": sum(
                1 for e in entries if e["is_post_award_document"]
            ),
            "application_document_count": sum(
                1 for e in entries if e["is_application_document"]
            ),
            "not_retrieved_count": sum(
                1 for e in entries if e["retrieval_method"] == "not_retrieved"
            ),
            "parsed_count": 0,
            "downloads_performed": 0,
            "network_access_performed": False,
            "fabricated": False,
        }
    )


def inventory_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    single = "document_id" in result
    entries = [result] if single else (result.get("documents") or [])

    if not single:
        if result.get("downloads_performed"):
            fails.append("inventory_performed_a_download")
        if result.get("network_access_performed") is not False:
            fails.append("inventory_performed_network_access")
        if result.get("parsed_count"):
            fails.append("inventory_claimed_a_parse")

    for entry in entries:
        did = entry.get("document_id")
        if not did:
            fails.append("document_without_id")
        if entry.get("document_type") not in DOCUMENT_TYPES:
            fails.append(f"document_type_out_of_vocabulary:{did}")
        if entry.get("owner_type") not in OWNER_TYPES:
            fails.append(f"owner_type_out_of_vocabulary:{did}")
        if not entry.get("owner_id"):
            fails.append(f"document_without_owner:{did}")
        if entry.get("retrieval_method") not in RETRIEVAL_METHODS:
            fails.append(f"retrieval_method_out_of_vocabulary:{did}")
        if entry.get("terms_status") not in TERMS_STATUSES:
            fails.append(f"terms_status_out_of_vocabulary:{did}")
        if entry.get("evidence_role") not in EVIDENCE_ROLES:
            fails.append(f"evidence_role_out_of_vocabulary:{did}")
        if entry.get("downloaded") is not False:
            fails.append(f"document_marked_downloaded:{did}")

        # A local file must be hashed; hashing is what makes it evidence.
        if entry.get("local_path") and entry.get("retrieval_method") != "not_retrieved":
            if not entry.get("hash_sha256"):
                fails.append(f"local_document_without_hash:{did}")

        # Inventory must never imply a parse succeeded.
        if entry.get("parse_status") not in PARSE_STATUSES:
            fails.append(f"parse_status_out_of_vocabulary:{did}")
        if entry.get("text_extraction_status") not in TEXT_EXTRACTION_STATUSES:
            fails.append(f"text_extraction_status_out_of_vocabulary:{did}")

        # A post-award document and an application document are different
        # things and must not both be true.
        if entry.get("is_post_award_document") and entry.get(
            "is_application_document"
        ):
            fails.append(f"document_is_both_post_award_and_application:{did}")

    return fails
