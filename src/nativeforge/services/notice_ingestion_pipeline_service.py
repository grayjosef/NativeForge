"""Notice ingestion pipeline (Gate 82F).

Runs one artifact all the way to a cited, per-class eligibility answer:

```text
artifact -> text adapter -> nofo_text_extraction_service
         -> nofo_eligibility_parser_service
         -> nofo_amendment_detector_service
```

The pipeline owns three responsibilities the individual services deliberately do
not:

  * **Refusing early.** An unknown artifact type or a failed adapter stops here.
    Gate 81 is never handed text that an adapter could not vouch for, because a
    blocked adapter returning ``""`` would otherwise reach the parser as
    "a notice with no eligibility section" rather than "a notice we could not
    read".
  * **Carrying provenance.** Artifact id, hash, path, type and extraction method
    travel with the parse result, so an exclusion can be traced back to the file
    it came from and not merely to a string.
  * **Keeping confidences apart.** The adapter has a confidence (did we read the
    document correctly). Gate 81B has a parser confidence (did we find the
    sections). Neither is an eligibility confidence, and this module never
    combines them into one number.

## The span caveat

Gate 81 returns character offsets into the **adapter output**, not into the
original artifact. For plain text the two coincide. For HTML and PDF they do
not, and there is no honest mapping back to a byte offset in the source file
without a much heavier parser than this project has. Every result therefore
carries ``spans_relative_to: "adapter_text"``, and the adapter text is returned
alongside so a quote can always be resolved against the exact string it indexes.

Nothing here fetches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.html_notice_text_adapter_service import (
    extract_html_notice_text,
)
from nativeforge.services.nofo_amendment_detector_service import detect_notice_status
from nativeforge.services.nofo_eligibility_parser_service import (
    parse_nofo_eligibility,
)
from nativeforge.services.nofo_text_extraction_service import extract_nofo_text
from nativeforge.services.notice_artifact_model_service import (
    EXTRACTABLE_TYPES,
    build_notice_artifact,
)
from nativeforge.services.pdf_notice_text_adapter_service import (
    extract_pdf_notice_text,
)

SCHEMA_VERSION = "nf_notice_ingestion_pipeline_v1"
PIPELINE_VERSION = "gate82_v1"

PIPELINE_STATUSES = frozenset({"ingested", "blocked"})

# Keys a recorded transport payload may carry its notice text under, most
# specific first. Anything else blocks rather than guessing at a field.
RECORDED_TEXT_KEYS: tuple[str, ...] = (
    "notice_text",
    "raw_text",
    "text",
    "body",
    "content",
)

# Adapter confidences that mean a human should look before anything is shown to
# a customer.
LOW_CONFIDENCES = frozenset({"none", "low"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def extract_plain_text_notice(
    *,
    local_path: str | Path,
    artifact_id: str | None = None,
    artifact_type: str = "plain_text",
) -> dict[str, Any]:
    """Read a text or markdown notice verbatim.

    No transformation at all. Markdown is left as-is: its headings are already
    line-initial, which is exactly what Gate 81 section detection wants, and
    rewriting them would only risk losing one.
    """
    blocked_reasons: list[str] = []
    text = ""
    try:
        text = Path(str(local_path)).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError) as exc:
        blocked_reasons.append(f"could_not_read_local_path:{type(exc).__name__}")

    if not blocked_reasons and not text.strip():
        blocked_reasons.append("empty_text_file")

    status = "blocked" if blocked_reasons else "extracted"
    return _json_safe(
        {
            "schema_version": "nf_plain_text_notice_adapter_v1",
            "adapter_version": PIPELINE_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "extraction_status": status,
            "text": "" if blocked_reasons else text,
            "text_chars": 0 if blocked_reasons else len(text),
            "text_extraction_method": None if blocked_reasons else "verbatim_read",
            "adapter_confidence": "none" if blocked_reasons else "high",
            "extraction_uncertain": bool(blocked_reasons),
            "human_review_required": bool(blocked_reasons),
            "blocked_reasons": blocked_reasons,
            "warnings": [],
            "url_fetch_performed": False,
            "eligibility_claimed": False,
            "freshness_claimed": False,
        }
    )


def extract_recorded_transport_notice(
    *,
    local_path: str | Path,
    artifact_id: str | None = None,
) -> dict[str, Any]:
    """Read notice text out of a recorded transport JSON payload."""
    blocked_reasons: list[str] = []
    warnings: list[str] = []
    text = ""
    key_used: str | None = None

    try:
        payload = json.loads(
            Path(str(local_path)).read_text(encoding="utf-8", errors="replace")
        )
    except (OSError, ValueError) as exc:
        blocked_reasons.append(f"could_not_read_recorded_transport:{type(exc).__name__}")
        payload = None

    if isinstance(payload, dict):
        # A recorded payload that claims a live fetch is mislabeled, and Gate
        # 77B's honest-labeling rule says so.
        if payload.get("real_fetch") is True:
            warnings.append("recorded_payload_claims_real_fetch")
        for key in RECORDED_TEXT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                key_used = key
                break
        if key_used is None:
            blocked_reasons.append("no_text_field_in_recorded_transport")
    elif payload is not None:
        blocked_reasons.append("recorded_transport_is_not_an_object")

    status = "blocked" if blocked_reasons else "extracted"
    return _json_safe(
        {
            "schema_version": "nf_recorded_transport_notice_adapter_v1",
            "adapter_version": PIPELINE_VERSION,
            "artifact_id": artifact_id,
            "artifact_type": "json_recorded_transport",
            "extraction_status": status,
            "text": "" if blocked_reasons else text,
            "text_chars": 0 if blocked_reasons else len(text),
            "text_extraction_method": (
                None if blocked_reasons else f"recorded_field:{key_used}"
            ),
            "adapter_confidence": "none" if blocked_reasons else "high",
            "extraction_uncertain": bool(blocked_reasons),
            "human_review_required": bool(blocked_reasons),
            "blocked_reasons": blocked_reasons,
            "warnings": warnings,
            "url_fetch_performed": False,
            "eligibility_claimed": False,
            "freshness_claimed": False,
        }
    )


def run_text_adapter(
    artifact: dict[str, Any], **adapter_kwargs: Any
) -> dict[str, Any]:
    """Dispatch one artifact to the adapter for its type."""
    a_type = artifact.get("artifact_type")
    path = artifact.get("local_path")
    artifact_id = artifact.get("artifact_id")

    if a_type == "html":
        return extract_html_notice_text(
            local_path=path, artifact_id=artifact_id, **adapter_kwargs
        )
    if a_type == "pdf":
        return extract_pdf_notice_text(
            local_path=path, artifact_id=artifact_id, **adapter_kwargs
        )
    if a_type in {"plain_text", "markdown"}:
        return extract_plain_text_notice(
            local_path=path, artifact_id=artifact_id, artifact_type=a_type
        )
    if a_type == "json_recorded_transport":
        return extract_recorded_transport_notice(
            local_path=path, artifact_id=artifact_id
        )
    raise ValueError(f"no adapter for artifact type: {a_type}")


def ingest_notice_artifact(
    *,
    artifact_id: str,
    local_path: str | Path | None = None,
    artifact_type: str | None = None,
    source_id: str | None = None,
    notice_id: str | None = None,
    source_url: str | None = None,
    notice_url: str | None = None,
    content_hash: str | None = None,
    retrieved_at: str | None = None,
    recorded_at: str | None = None,
    title: str | None = None,
    agency: str | None = None,
    posted_date: str | None = None,
    close_date: str | None = None,
    amendment_date: str | None = None,
    version: str | int | None = None,
    evidence_reference: str | None = None,
    adapter_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one artifact end to end and return the ingested notice record."""
    artifact = build_notice_artifact(
        artifact_id=artifact_id,
        source_id=source_id,
        notice_id=notice_id,
        artifact_type=artifact_type,
        source_url=source_url,
        notice_url=notice_url,
        local_path=str(local_path) if local_path else None,
        content_hash=content_hash,
        retrieved_at=retrieved_at,
        recorded_at=recorded_at,
    )

    if artifact["blocked_reasons"] or artifact["artifact_type"] not in (
        EXTRACTABLE_TYPES
    ):
        return _blocked(
            artifact,
            None,
            ["artifact_blocked:" + r for r in artifact["blocked_reasons"]]
            or ["artifact_not_extractable"],
        )

    adapter = run_text_adapter(artifact, **(adapter_kwargs or {}))

    if adapter["extraction_status"] != "extracted" or not str(
        adapter.get("text") or ""
    ).strip():
        # Never hand Gate 81 an empty string. "We could not read it" and "it has
        # no eligibility section" are different answers and must stay different.
        return _blocked(
            artifact,
            adapter,
            ["text_extraction_failed:" + adapter["extraction_status"]]
            + ["adapter:" + r for r in (adapter.get("blocked_reasons") or [])],
        )

    text = adapter["text"]
    resolved_notice_id = notice_id or artifact_id

    extraction = extract_nofo_text(
        notice_id=resolved_notice_id,
        source_id=source_id,
        source_url=source_url,
        notice_url=notice_url,
        title=title,
        agency=agency,
        posted_date=posted_date,
        close_date=close_date,
        amendment_date=amendment_date,
        version=version,
        raw_text=text,
        retrieved_at=retrieved_at,
    )

    parsed = parse_nofo_eligibility(
        opportunity_id=resolved_notice_id,
        extraction=extraction,
        raw_text=text,
        evidence_reference=evidence_reference,
    )

    detection = detect_notice_status(
        notice_id=resolved_notice_id,
        raw_text=text,
        extraction=extraction,
        notice_url=notice_url,
        declared_version=version,
        amendment_date=amendment_date,
    )

    # Two different adapter concerns, kept apart: the adapter may be confident
    # it read the document correctly and still have found something worth a
    # human look, such as hidden text it deliberately excluded.
    low_confidence = adapter.get("adapter_confidence") in LOW_CONFIDENCES
    flagged = bool(adapter.get("extraction_uncertain"))
    review_reasons: list[str] = []
    if low_confidence:
        review_reasons.append(
            f"adapter_low_confidence:{adapter.get('adapter_confidence')}"
        )
    elif flagged:
        review_reasons.append("adapter_flagged_uncertainty")
    if adapter.get("warnings"):
        review_reasons.extend(f"adapter_warning:{w}" for w in adapter["warnings"])
    if parsed.get("human_review_required"):
        review_reasons.append("parser_requires_review")
    if detection.get("human_review_required"):
        review_reasons.append("notice_status_requires_review")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "artifact_id": artifact_id,
            "notice_id": resolved_notice_id,
            "pipeline_status": "ingested",
            "artifact": artifact,
            "adapter": {
                k: v for k, v in adapter.items() if k != "text"
            },
            # The exact string every span below indexes into.
            "adapter_text": text,
            "adapter_text_chars": len(text),
            "spans_relative_to": "adapter_text",
            "text_extraction_method": adapter.get("text_extraction_method"),
            "extraction": extraction,
            "eligibility": parsed,
            "amendment": detection,
            # Carried up for convenience; the authoritative copies are above.
            "excluded_classes": parsed.get("excluded_classes") or [],
            "eligible_classes": parsed.get("eligible_classes") or [],
            "notice_status": detection.get("notice_status"),
            "is_current_notice": detection.get("is_current_notice"),
            # Three separate questions, never merged into one number.
            "adapter_confidence": adapter.get("adapter_confidence"),
            "parser_confidence": extraction.get("parser_confidence"),
            "eligibility_confidence": extraction.get("eligibility_confidence"),
            "human_review_required": bool(review_reasons),
            "review_reasons": review_reasons,
            # Boundaries.
            "adapter_confidence_used_as_eligibility_confidence": False,
            "url_fetch_performed": False,
            "live_coverage_claimed": False,
            "source_monitored": False,
            "freshness_claimed": False,
        }
    )


def _blocked(
    artifact: dict[str, Any],
    adapter: dict[str, Any] | None,
    reasons: list[str],
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "artifact_id": artifact.get("artifact_id"),
            "notice_id": artifact.get("notice_id"),
            "pipeline_status": "blocked",
            "artifact": artifact,
            "adapter": (
                {k: v for k, v in adapter.items() if k != "text"} if adapter else None
            ),
            "adapter_text": "",
            "adapter_text_chars": 0,
            "spans_relative_to": "adapter_text",
            "text_extraction_method": None,
            "extraction": None,
            "eligibility": None,
            "amendment": None,
            "excluded_classes": [],
            "eligible_classes": [],
            "notice_status": "unknown",
            "is_current_notice": False,
            "adapter_confidence": (
                adapter.get("adapter_confidence") if adapter else "none"
            ),
            "parser_confidence": "none",
            "eligibility_confidence": "none",
            "human_review_required": True,
            "review_reasons": reasons,
            "adapter_confidence_used_as_eligibility_confidence": False,
            "url_fetch_performed": False,
            "live_coverage_claimed": False,
            "source_monitored": False,
            "freshness_claimed": False,
        }
    )


def pipeline_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = result.get("pipeline_status")
    if status not in PIPELINE_STATUSES:
        fails.append(f"unknown_pipeline_status:{status}")

    if status == "blocked":
        if not result.get("review_reasons"):
            fails.append("blocked_without_a_reason")
        if result.get("excluded_classes") or result.get("eligible_classes"):
            fails.append("blocked_pipeline_produced_eligibility_answers")
        if not result.get("human_review_required"):
            fails.append("blocked_pipeline_without_human_review")

    if status == "ingested":
        if not str(result.get("adapter_text") or "").strip():
            fails.append("ingested_without_adapter_text")
        if not result.get("extraction"):
            fails.append("ingested_without_an_extraction")
        if not result.get("eligibility"):
            fails.append("ingested_without_an_eligibility_parse")
        if not result.get("text_extraction_method"):
            fails.append("ingested_without_an_extraction_method")

        # Spans must index the string we actually return.
        text_len = len(result.get("adapter_text") or "")
        for mention in (result.get("eligibility") or {}).get("class_mentions") or []:
            end = mention.get("end")
            if not isinstance(end, int) or end > text_len:
                fails.append("span_outside_adapter_text")
                break

    # Eligibility confidence is never borrowed from the adapter.
    if result.get("eligibility_confidence") not in {"none", "low", "medium", "high"}:
        fails.append("eligibility_confidence_out_of_vocabulary")
    if (
        result.get("adapter_confidence") in {"high", "medium"}
        and result.get("eligibility_confidence") != "none"
    ):
        fails.append("eligibility_confidence_borrowed_from_the_adapter")

    if result.get("spans_relative_to") != "adapter_text":
        fails.append("span_basis_not_declared_as_adapter_text")

    # An artifact that claims a live fetch cannot pass through this pipeline.
    artifact = result.get("artifact") or {}
    if artifact.get("is_live_fetch"):
        fails.append("pipeline_ingested_a_live_fetched_artifact")

    for forbidden in (
        "adapter_confidence_used_as_eligibility_confidence",
        "url_fetch_performed",
        "live_coverage_claimed",
        "source_monitored",
        "freshness_claimed",
    ):
        if result.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")

    return fails
