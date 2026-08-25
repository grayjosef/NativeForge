"""Notice artifact model (Gate 82B).

Describes one primary-notice artifact - an HTML page, a PDF, a text file, a
recorded transport payload - before any text has been read out of it.

The model exists to make three things decidable rather than asserted:

  * **Was this fetched live?** ``is_live_fetch`` defaults to ``False`` and can
    only become true if the hermetic guard says live network is allowed. A
    caller cannot talk its way into a live label.
  * **Is this really a committed fixture?** ``is_recorded_fixture`` is checked
    against ``hermetic_test_guard_service.is_source_controlled``, so a caller
    claiming fixture status for a path outside the committed roots is
    contradicted by the filesystem rather than believed.
  * **Can text be read from it at all?** An unknown type or a missing file
    blocks extraction here, before an adapter is chosen.

What this module deliberately does **not** do: claim freshness, claim
eligibility, or open ``source_url`` / ``notice_url``. Those URLs are metadata.
Nothing here fetches.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nativeforge.services.hermetic_test_guard_service import (
    is_source_controlled,
    live_network_allowed,
)
from nativeforge.services.source_fetch_adapter_contract_service import (
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
)

SCHEMA_VERSION = "nf_notice_artifact_model_v1"

ARTIFACT_TYPES = frozenset(
    {
        "html",
        "pdf",
        "plain_text",
        "markdown",
        "json_recorded_transport",
        "unknown",
    }
)

# Types an adapter can actually read. Derived by difference so a type added
# later is unreadable until someone deliberately wires an adapter for it.
EXTRACTABLE_TYPES = ARTIFACT_TYPES - {"unknown"}

# Suffix hints. Only a hint: the artifact type may also be declared, and a
# declared type that disagrees with the suffix is recorded as a warning rather
# than silently resolved.
SUFFIX_TYPES: dict[str, str] = {
    ".html": "html",
    ".htm": "html",
    ".xhtml": "html",
    ".pdf": "pdf",
    ".txt": "plain_text",
    ".text": "plain_text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "json_recorded_transport",
}

# Leading bytes that identify a format regardless of what the name says.
_PDF_MAGIC = b"%PDF-"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def sniff_artifact_type(path: Path | str | None) -> str:
    """Infer a type from the path suffix. ``unknown`` when it cannot."""
    if not path:
        return "unknown"
    suffix = Path(str(path)).suffix.lower()
    return SUFFIX_TYPES.get(suffix, "unknown")


def content_hash_of(path: Path | str) -> str | None:
    """SHA-256 of the file, or None when it cannot be read."""
    try:
        data = Path(str(path)).read_bytes()
    except (OSError, ValueError):
        return None
    return hashlib.sha256(data).hexdigest()


def build_notice_artifact(
    *,
    artifact_id: str,
    source_id: str | None = None,
    notice_id: str | None = None,
    artifact_type: str | None = None,
    source_url: str | None = None,
    notice_url: str | None = None,
    local_path: str | None = None,
    content_hash: str | None = None,
    retrieved_at: str | None = None,
    recorded_at: str | None = None,
    declared_live_fetch: bool = False,
    require_hash: bool = False,
) -> dict[str, Any]:
    """Describe one artifact and decide whether text may be read from it.

    ``declared_live_fetch`` is a request, not a fact. It is only honoured when
    the hermetic guard permits live network; otherwise it is refused and
    recorded as a warning. That keeps the honest-labeling rule of Gate 77B and
    ``html_fetch_honest_labeling_guard_service`` true by construction rather
    than by discipline.
    """
    blocked_reasons: list[str] = []
    warnings: list[str] = []

    path = Path(local_path) if local_path else None
    exists = bool(path and path.is_file())

    sniffed = sniff_artifact_type(local_path)
    if artifact_type is None:
        resolved_type = sniffed
        if resolved_type == "unknown" and local_path:
            warnings.append(f"could_not_infer_artifact_type_from:{path.suffix or ''}")
    elif artifact_type not in ARTIFACT_TYPES:
        resolved_type = "unknown"
        warnings.append(f"unrecognised_declared_artifact_type:{artifact_type}")
    else:
        resolved_type = artifact_type
        if sniffed != "unknown" and sniffed != resolved_type:
            # Recorded, never silently resolved. A .pdf declared as plain_text
            # is either a mislabel or a mistake, and both deserve a human.
            warnings.append(
                f"declared_type_disagrees_with_suffix:{resolved_type}!={sniffed}"
            )

    # Magic bytes outrank both the suffix and the declaration.
    if exists and path is not None:
        try:
            head = path.open("rb").read(len(_PDF_MAGIC))
        except OSError:
            head = b""
        if head.startswith(_PDF_MAGIC) and resolved_type != "pdf":
            warnings.append(f"content_is_pdf_but_type_is:{resolved_type}")
            resolved_type = "pdf"

    if resolved_type == "unknown":
        blocked_reasons.append("unknown_artifact_type")

    if not local_path:
        blocked_reasons.append("missing_local_path")
    elif not exists:
        blocked_reasons.append("local_path_does_not_exist")

    # Live fetch is refused unless the guard allows it. Default is off.
    allow_live = live_network_allowed()
    is_live_fetch = bool(declared_live_fetch and allow_live)
    if declared_live_fetch and not allow_live:
        warnings.append("live_fetch_declared_but_refused_by_hermetic_guard")

    # Fixture status is checked, not believed.
    recorded = bool(local_path) and is_source_controlled(local_path)
    if recorded and is_live_fetch:
        # The two are mutually exclusive by definition.
        blocked_reasons.append("committed_fixture_cannot_be_a_live_fetch")

    resolved_hash = content_hash
    if exists and path is not None:
        actual = content_hash_of(path)
        if content_hash and actual and content_hash != actual:
            blocked_reasons.append("content_hash_mismatch")
        resolved_hash = content_hash or actual

    if not resolved_hash:
        if require_hash:
            blocked_reasons.append("missing_content_hash")
        else:
            warnings.append("no_content_hash_available")

    extractable = not blocked_reasons and resolved_type in EXTRACTABLE_TYPES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": resolved_type,
            "sniffed_type": sniffed,
            "source_id": source_id,
            "notice_id": notice_id,
            # Metadata only. Nothing in this package opens these.
            "source_url": source_url,
            "notice_url": notice_url,
            "local_path": str(local_path) if local_path else None,
            "local_path_exists": exists,
            "content_hash": resolved_hash,
            "retrieved_at": retrieved_at,
            "recorded_at": recorded_at,
            "is_recorded_fixture": recorded,
            "is_live_fetch": is_live_fetch,
            "fetch_mode": FETCH_MODE_LIVE if is_live_fetch else FETCH_MODE_FIXTURE,
            "extractable": extractable,
            # Filled in by an adapter, not here.
            "text_extracted": False,
            "text_extraction_method": None,
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
            # Boundaries this model never crosses.
            "freshness_claimed": False,
            "eligibility_claimed": False,
            "url_fetch_performed": False,
        }
    )


def artifact_invariant_failures(artifact: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if artifact.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    a_type = artifact.get("artifact_type")
    if a_type not in ARTIFACT_TYPES:
        fails.append(f"artifact_type_out_of_vocabulary:{a_type}")

    # Unknown type and missing path must block.
    if a_type == "unknown" and "unknown_artifact_type" not in (
        artifact.get("blocked_reasons") or []
    ):
        fails.append("unknown_artifact_type_did_not_block")
    if not artifact.get("local_path") and "missing_local_path" not in (
        artifact.get("blocked_reasons") or []
    ):
        fails.append("missing_local_path_did_not_block")

    # Anything blocked is not extractable.
    if artifact.get("blocked_reasons") and artifact.get("extractable"):
        fails.append("blocked_artifact_reported_as_extractable")
    if artifact.get("extractable") and a_type not in EXTRACTABLE_TYPES:
        fails.append(f"unextractable_type_reported_as_extractable:{a_type}")

    # Live fetch must never be claimed while the guard forbids it.
    if artifact.get("is_live_fetch") and not live_network_allowed():
        fails.append("live_fetch_claimed_while_hermetic_guard_forbids_it")
    if artifact.get("is_live_fetch") and artifact.get("is_recorded_fixture"):
        fails.append("artifact_claims_both_live_fetch_and_recorded_fixture")

    expected_mode = FETCH_MODE_LIVE if artifact.get("is_live_fetch") else (
        FETCH_MODE_FIXTURE
    )
    if artifact.get("fetch_mode") != expected_mode:
        fails.append("fetch_mode_disagrees_with_is_live_fetch")

    for forbidden in (
        "freshness_claimed",
        "eligibility_claimed",
        "url_fetch_performed",
    ):
        if artifact.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
