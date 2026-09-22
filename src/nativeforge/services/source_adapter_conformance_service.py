"""Gate 171D: one conformance harness every adapter has to pass.

The alternative to this module is a per-adapter test file, and the thing wrong
with that is not effort - it is that the second adapter's tests get written by
reading the first adapter's tests, so whatever the first one got wrong becomes
the house style. A harness that takes an adapter and a bag of fixture bytes
asks every adapter the same questions in the same order.

## What it can and cannot prove

It proves BEHAVIOUR against bytes the caller supplies. It cannot prove that
those bytes resemble what the source really returns - only a real collection
does that, and until one happens the adapter's `read_records` is a hypothesis.
The harness says which of the two it is via `fixtures_are_real`, because a
conformance report over invented bytes that does not say so is the more
dangerous kind of green.

## No network, structurally

This module imports no transport. It is handed bytes. An adapter that needs a
socket to be conformance-tested is an adapter that cannot be tested before it
is authorized, which is the wrong way round.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_adapter_contract_service import (
    SUPPORTED_MEDIA_TYPES,
    CollectionOutcome,
    PageCursor,
    RawEvidenceEnvelope,
    SourceDescriptor,
    adapter_contract_failures,
    cursor_failures,
    descriptor_failures,
    document_failures,
    evidence_failures,
    outcome_failures,
    record_failures,
)

SCHEMA_VERSION = "nf_source_adapter_conformance_v1"

#: The thirteen properties Gate 171D names, plus the two the campaign has
#: learned to check: that the report says whether its fixtures were real, and
#: that an adapter cannot reach the graph.
CONFORMANCE_CHECKS = (
    "descriptor_validates",
    "authorization_binding_enforced",
    "request_construction_deterministic",
    "response_validation_rejects_wrong_media_type",
    "pagination_is_bounded",
    "retry_semantics_declared",
    "rate_limit_semantics_declared",
    "evidence_envelope_deterministic",
    "normalization_produces_records",
    "record_identity_stable",
    "provenance_fields_declared",
    "malformed_response_refused_not_crashed",
    "no_secret_leakage",
    "no_direct_canonical_writes",
)

#: Strings that must never appear in anything an adapter hands back. A
#: credential in a record is a credential in the evidence store.
SECRET_MARKERS = (
    "authorization",
    "api_key",
    "apikey",
    "x-api-key",
    "bearer ",
    "password",
    "secret",
    "token=",
    "cookie",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _serialize(value: Any) -> str:
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except Exception:  # noqa: BLE001
        return str(value)


class _Refused(RuntimeError):
    """Raised by a fake authorization to prove the adapter asked for one."""


def run_adapter_conformance(
    *,
    module: Any,
    ok_bytes: bytes,
    malformed_bytes: bytes,
    empty_bytes: bytes = b"",
    second_page_bytes: bytes | None = None,
    media_type: str | None = None,
    fixtures_are_real: bool = False,
    authorization: Any = None,
) -> dict[str, Any]:
    """Run one adapter through every conformance check.

    Returns a report rather than raising, so a failing adapter produces a
    named failure list instead of a traceback that says only where it gave up.
    """
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "adapter_key": str(getattr(module, "ADAPTER_KEY", "")),
        "fixtures_are_real": bool(fixtures_are_real),
        "checks": {},
        "failures": [],
        "notes": [],
    }
    checks: dict[str, bool] = {}
    failures: list[str] = []

    def fail(name: str, reason: str) -> None:
        checks[name] = False
        failures.append(f"{name}:{reason}")

    # ---- 0. structural: the adapter cannot reach the graph ---------
    structural = adapter_contract_failures(module)
    checks["no_direct_canonical_writes"] = not any(
        f.startswith("adapter_imports_a_writer") for f in structural
    )
    if structural:
        failures.extend(structural)

    if not all(hasattr(module, a) for a in ("build_descriptor", "build_request")):
        report["checks"] = checks
        report["failures"] = sorted(set(failures))
        report["conformant"] = False
        report["notes"].append("adapter_is_missing_required_callables")
        return _json_safe(report)

    # ---- 1. descriptor ---------------------------------------------
    try:
        descriptor: SourceDescriptor = module.build_descriptor()
        problems = descriptor_failures(descriptor)
        checks["descriptor_validates"] = not problems
        failures.extend(problems)
    except Exception as exc:  # noqa: BLE001
        fail("descriptor_validates", f"{type(exc).__name__}")
        report["checks"] = checks
        report["failures"] = sorted(set(failures))
        report["conformant"] = False
        return _json_safe(report)

    # ---- 2. authorization binding ----------------------------------
    #
    # An adapter that will build a request without being handed an
    # authorization is an adapter that can be driven by anything that can
    # call a function. The check is that it REFUSES, not that it warns.
    try:
        module.build_request(descriptor=descriptor, authorization=None, cursor=None)
        fail("authorization_binding_enforced", "built_a_request_without_one")
    except Exception:  # noqa: BLE001
        checks["authorization_binding_enforced"] = True

    # ---- 3. request construction is deterministic ------------------
    try:
        cursor_a = PageCursor(
            max_pages=descriptor.max_pages, max_records=descriptor.max_records
        )
        cursor_b = PageCursor(
            max_pages=descriptor.max_pages, max_records=descriptor.max_records
        )
        first = module.build_request(
            descriptor=descriptor, authorization=authorization, cursor=cursor_a
        )
        second = module.build_request(
            descriptor=descriptor, authorization=authorization, cursor=cursor_b
        )
        same = (
            getattr(first, "method", None) == getattr(second, "method", None)
            and getattr(first, "url", None) == getattr(second, "url", None)
            and getattr(first, "body_bytes", None)
            == getattr(second, "body_bytes", None)
        )
        checks["request_construction_deterministic"] = bool(same)
        if not same:
            failures.append("request_construction_deterministic:two_calls_differ")
        # A request that carries a credential in the URL is a credential in
        # every log line that records the URL.
        url_text = str(getattr(first, "url", "")).lower()
        if any(marker in url_text for marker in SECRET_MARKERS):
            failures.append("no_secret_leakage:credential_in_request_url")
    except Exception as exc:  # noqa: BLE001
        fail("request_construction_deterministic", type(exc).__name__)

    # ---- 4. response validation ------------------------------------
    declared = tuple(descriptor.expected_media_types)
    wrong = next(
        (m for m in SUPPORTED_MEDIA_TYPES if m not in declared),
        "application/octet-stream",
    )
    try:
        module.read_records(
            descriptor=descriptor, body_bytes=ok_bytes, media_type=wrong, cursor=None
        )
        fail("response_validation_rejects_wrong_media_type", "accepted_it")
    except Exception:  # noqa: BLE001
        checks["response_validation_rejects_wrong_media_type"] = True

    # ---- 5/8/9/10/11. the happy path over supplied bytes -----------
    effective_media = media_type or (declared[0] if declared else None)
    records: list[Any] = []
    try:
        cursor = PageCursor(
            max_pages=descriptor.max_pages, max_records=descriptor.max_records
        )
        records = list(
            module.read_records(
                descriptor=descriptor,
                body_bytes=ok_bytes,
                media_type=effective_media,
                cursor=cursor,
            )
        )
        checks["normalization_produces_records"] = bool(records)
        if not records:
            failures.append("normalization_produces_records:none_from_ok_fixture")

        again = list(
            module.read_records(
                descriptor=descriptor,
                body_bytes=ok_bytes,
                media_type=effective_media,
                cursor=PageCursor(
                    max_pages=descriptor.max_pages,
                    max_records=descriptor.max_records,
                ),
            )
        )
        stable = [r.source_record_id for r in records] == [
            r.source_record_id for r in again
        ]
        checks["record_identity_stable"] = stable
        if not stable:
            failures.append("record_identity_stable:ids_changed_between_reads")

        declared_fields = all(bool(r.supported_fields) for r in records)
        checks["provenance_fields_declared"] = declared_fields
        for record in records:
            failures.extend(record_failures(record))
            failures.extend(
                document_failures(
                    list(record.documents), max_depth=descriptor.max_crawl_depth
                )
            )

        # Secret leakage, over everything the adapter handed back.
        blob = _serialize([r.fields for r in records]).lower()
        leaked = [m for m in SECRET_MARKERS if m in blob]
        checks["no_secret_leakage"] = not leaked and (
            checks.get("no_secret_leakage", True) is not False
        )
        if leaked:
            failures.append(f"no_secret_leakage:{sorted(leaked)}")
    except Exception as exc:  # noqa: BLE001
        fail("normalization_produces_records", type(exc).__name__)

    # ---- evidence envelope determinism -----------------------------
    envelope_one = RawEvidenceEnvelope.for_body(
        source_id=descriptor.source_id,
        adapter_key=descriptor.adapter_key,
        request_method=descriptor.transport_method,
        request_url_fingerprint="fp",
        retrieved_at="2026-01-01T00:00:00Z",
        body_bytes=ok_bytes,
        media_type=effective_media,
    )
    envelope_two = RawEvidenceEnvelope.for_body(
        source_id=descriptor.source_id,
        adapter_key=descriptor.adapter_key,
        request_method=descriptor.transport_method,
        request_url_fingerprint="fp",
        retrieved_at="2026-01-01T00:00:00Z",
        body_bytes=ok_bytes,
        media_type=effective_media,
    )
    checks["evidence_envelope_deterministic"] = (
        envelope_one.content_sha256 == envelope_two.content_sha256
        and not evidence_failures(envelope_one)
    )
    failures.extend(evidence_failures(envelope_one))

    # ---- 5. pagination is bounded ----------------------------------
    #
    # Driven with a source that always claims there is more. A bounded
    # adapter stops anyway; an unbounded one would run until this loop's own
    # guard stops it, which is what the guard is for.
    cursor = PageCursor(
        max_pages=descriptor.max_pages, max_records=descriptor.max_records
    )
    pages = 0
    page_bytes = [ok_bytes, second_page_bytes or ok_bytes]
    while pages < int(descriptor.max_pages) + 5:
        body = page_bytes[min(pages, len(page_bytes) - 1)]
        try:
            page_records = list(
                module.read_records(
                    descriptor=descriptor,
                    body_bytes=body,
                    media_type=effective_media,
                    cursor=cursor,
                )
            )
        except Exception:  # noqa: BLE001
            page_records = []
        cursor.observe_page(
            content_sha256=RawEvidenceEnvelope.for_body(
                source_id=descriptor.source_id,
                adapter_key=descriptor.adapter_key,
                request_method=descriptor.transport_method,
                request_url_fingerprint="fp",
                retrieved_at="2026-01-01T00:00:00Z",
                body_bytes=body,
            ).content_sha256,
            record_count=len(page_records),
        )
        pages += 1
        if not cursor.should_continue(source_says_more=True):
            break
    bounded = cursor.terminated_because is not None and pages <= int(
        descriptor.max_pages
    ) + 1
    checks["pagination_is_bounded"] = bounded
    if not bounded:
        failures.append(
            f"pagination_is_bounded:ran_{pages}_pages_reason_{cursor.terminated_because}"
        )
    failures.extend(cursor_failures(cursor))

    # ---- 6/7. retry and rate-limit semantics -----------------------
    #
    # Declared, not inferred. An adapter that does not say what it does on a
    # 429 has not decided, and "has not decided" becomes "hammers the source"
    # at fleet scale.
    retry = getattr(module, "RETRY_POLICY", None)
    rate = getattr(module, "RATE_LIMIT_POLICY", None)
    checks["retry_semantics_declared"] = isinstance(retry, dict) and bool(retry)
    checks["rate_limit_semantics_declared"] = isinstance(rate, dict) and bool(rate)
    if not checks["retry_semantics_declared"]:
        failures.append("retry_semantics_declared:no_RETRY_POLICY")
    if not checks["rate_limit_semantics_declared"]:
        failures.append("rate_limit_semantics_declared:no_RATE_LIMIT_POLICY")

    # ---- 12. malformed and empty bodies ----------------------------
    malformed_ok = True
    for name, body in (("malformed", malformed_bytes), ("empty", empty_bytes)):
        try:
            result = list(
                module.read_records(
                    descriptor=descriptor,
                    body_bytes=body,
                    media_type=effective_media,
                    cursor=None,
                )
            )
            # Returning nothing is a fine answer. Returning records from
            # garbage is not.
            if result and name == "malformed":
                malformed_ok = False
                failures.append("malformed_response_refused_not_crashed:invented_rows")
        except (ValueError, TypeError, KeyError):
            pass  # a named refusal is the other acceptable answer
        except Exception as exc:  # noqa: BLE001
            malformed_ok = False
            failures.append(
                f"malformed_response_refused_not_crashed:{name}:{type(exc).__name__}"
            )
    checks["malformed_response_refused_not_crashed"] = malformed_ok

    for name in CONFORMANCE_CHECKS:
        checks.setdefault(name, False)

    report["checks"] = dict(sorted(checks.items()))
    report["failures"] = sorted(set(failures))
    report["conformant"] = all(checks.values()) and not report["failures"]
    report["records_read_from_fixture"] = len(records)
    if not fixtures_are_real:
        report["notes"].append(
            "fixtures_are_synthetic: read_records is a hypothesis about this "
            "source until a real collection confirms the response shape"
        )
    return _json_safe(report)


def conformance_invariant_failures(report: dict[str, Any]) -> list[str]:
    """Refuse a report that claims more than it measured."""
    failures: list[str] = []
    checks = dict(report.get("checks") or {})
    for name in CONFORMANCE_CHECKS:
        if name not in checks:
            failures.append(f"conformance_check_not_measured:{name}")
    if report.get("conformant") and report.get("failures"):
        failures.append("conformant_while_naming_failures")
    if report.get("conformant") and not all(checks.values()):
        failures.append("conformant_with_an_unmet_check")
    if report.get("conformant") and not report.get("fixtures_are_real"):
        # Not a defect - a limit. It is recorded so nobody reads a synthetic
        # green as a live one.
        failures.append("conformant_against_synthetic_fixtures_only")
    return sorted(set(failures))


def build_collection_outcome(
    *,
    descriptor: SourceDescriptor,
    records: list[Any],
    evidence: list[RawEvidenceEnvelope],
    requests_issued: int,
    cursor: PageCursor,
    refusals: tuple[str, ...] = (),
) -> tuple[CollectionOutcome, list[str]]:
    """Assemble an outcome and check it in one step, so neither is skipped."""
    outcome = CollectionOutcome(
        source_id=descriptor.source_id,
        adapter_key=descriptor.adapter_key,
        records=tuple(records),
        evidence=tuple(evidence),
        requests_issued=int(requests_issued),
        pages_fetched=int(cursor.page_index),
        terminated_because=str(
            cursor.terminated_because or "source_reported_last_page"
        ),
        refusals=tuple(refusals),
        cursor_state=cursor.describe(),
    )
    return outcome, outcome_failures(outcome, descriptor)
