"""Gate 141: drive the document routes and report what each proved.

Not a description of the routes — a client that calls them.

```text
create a document REFERENCE against an award
read it back, anchored on organization_id
list the award's documents
read it as another organization                  -> nothing
ask what body storage is available               -> nothing, and why
ask to store its bytes                           -> refused, by name
archive it                                       -> the row stays
```

Plus the refusals, which are the part worth proving:

```text
unauthenticated on every route              401
a forged X-NF-Org-Id                        401, the header is not a parameter
a caller setting is_demo or fact_status     400, named
a caller sending object_key / content / bytes  422, body storage is not configured
a caller naming the object key on the body route  422, named
```

The client is injectable so this runs against a `TestClient` in the suite and
against the live app in the verifier, with the same code deciding what passed.

No object store is contacted, no body bytes are sent, and no real file is read.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_document_storage_route_smoke_v1"

#: A fixture award, in the repository's own vocabulary. Nothing is extracted
#: from a document and no date is inferred.
#: `award_number` is filled in per run by `_award_body()`. One live award per
#: organization and number is a partial unique index, so a fixed number makes
#: this smoke pass exactly once against a persistent database - the same defect
#: Gate 138 found with a fixed persistence seed.
AWARD_BODY: dict[str, Any] = {
    "award_number": None,
    "award_title": "Gate 141 fixture award",
    "funder_name": "Gate 141 fixture funder",
    "award_status": "active_award",
    "award_amount": "1000.00",
    "award_currency": "USD",
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
    "awarded_at": "2026-01-01",
    "active_obligation_status": "no_obligations_established",
    "requirements_extraction_status": "not_attempted",
}

#: A document REFERENCE. Every field describes where a document is said to be,
#: and none of them is or names its bytes.
DOCUMENT_BODY: dict[str, Any] = {
    "document_kind": "award_letter",
    # "reference_recorded", not "stored": "stored" is the one status that
    # asserts bytes exist somewhere, and in this deployment they do not.
    "document_status": "reference_recorded",
    "document_title": "Gate 141 fixture award letter",
    "document_description": "A reference. The bytes live nowhere.",
    "document_source": "human_entered",
    "document_source_ref": "gate141-fixture-reference",
    "retention_class": "retain_7_days",
}

#: Fields whose presence means a caller is trying to store a file. Each must be
#: refused by name.
BODY_STORAGE_PROBES: tuple[str, ...] = (
    "object_key",
    "object_bucket",
    "content",
    "body",
    "bytes",
    "sha256_digest",
    "content_length",
)

#: A fixed entry id for the unauthenticated probes. Fixed rather than random,
#: because these end up in a committed artifact.
ANONYMOUS_ID = "00000000-0000-0000-0000-000000000141"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _award_body() -> dict[str, Any]:
    """The fixture award, with a number nothing else is using."""
    return {**AWARD_BODY, "award_number": f"NF-G141-{uuid.uuid4().hex[:8].upper()}"}


def _base(organization_id: str) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


def _status(response: Any) -> int:
    return int(response.status_code)


def _body(response: Any) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body is itself the finding
        return {}
    return payload if isinstance(payload, dict) else {}


def _reason_text(response: Any) -> str:
    return json.dumps(_body(response).get("detail", ""))


def run_document_storage_route_smoke(
    *,
    client: Any,
    organization_id: str,
    other_organization_id: str,
    session_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Drive every document route. ``client`` is any object with `.request`."""
    org = str(organization_id)
    other = str(other_organization_id)
    headers = dict(session_headers or {})
    base = _base(org)

    blocked: list[str] = []
    notes: list[str] = []
    proved: dict[str, bool] = {
        "unauthenticated_refused": False,
        "forged_header_refused": False,
        "metadata_route_operational": False,
        "org_scoped_read_write_proved": False,
        "cross_org_refused": False,
        "caller_supplied_fields_refused": False,
        "body_storage_fields_refused": False,
        "body_storage_readiness_route_operational": False,
        "unconfigured_blocker_correct": False,
        "caller_supplied_object_key_refused": False,
        "archive_preserves_the_row": False,
    }

    def mark(key: str, value: bool, why: str) -> None:
        proved[key] = bool(value)
        if not value:
            blocked.append(why)

    # -- 1. unauthenticated, on every route --------------------------------
    anonymous: tuple[tuple[str, str], ...] = (
        ("GET", f"{base}/awarded-grants/{ANONYMOUS_ID}/documents"),
        ("POST", f"{base}/awarded-grants/{ANONYMOUS_ID}/documents"),
        ("GET", f"{base}/documents/{ANONYMOUS_ID}"),
        ("POST", f"{base}/documents/{ANONYMOUS_ID}/archive"),
        ("GET", f"{base}/documents/{ANONYMOUS_ID}/body-storage"),
        ("POST", f"{base}/documents/{ANONYMOUS_ID}/body"),
    )
    anonymous_results: list[dict[str, Any]] = []
    for method, path in anonymous:
        response = client.request(method, path, json={} if method == "POST" else None)
        anonymous_results.append(
            {"method": method, "path": path, "status": _status(response)}
        )
        if _status(response) != 401:
            blocked.append(f"unauthenticated_got_{_status(response)}:{method} {path}")
    proved["unauthenticated_refused"] = not any(
        r["status"] != 401 for r in anonymous_results
    )

    forged = client.request(
        "GET",
        f"{base}/documents/{ANONYMOUS_ID}/body-storage",
        headers={"X-NF-Org-Id": org},
    )
    mark(
        "forged_header_refused",
        _status(forged) == 401,
        f"forged_header_got_{_status(forged)}",
    )

    if not headers:
        return _summary(proved, blocked, notes, anonymous_results, end_to_end=False)

    # -- 2. an award to hang a document on ----------------------------------
    award = client.request(
        "POST", f"{base}/awarded-grants", json=_award_body(), headers=headers
    )
    if _status(award) != 201:
        blocked.append(f"award_create_got_{_status(award)}:{_reason_text(award)}")
        return _summary(proved, blocked, notes, anonymous_results, end_to_end=False)
    award_id = _body(award)["award_id"]

    # -- 3. the document reference ------------------------------------------
    created = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/documents",
        json=DOCUMENT_BODY,
        headers=headers,
    )
    if _status(created) != 201:
        blocked.append(
            f"document_create_got_{_status(created)}:{_reason_text(created)}"
        )
        _cleanup_award(client, base, award_id, headers, notes)
        return _summary(proved, blocked, notes, anonymous_results, end_to_end=False)
    document_id = _body(created)["document_id"]

    read = client.request("GET", f"{base}/documents/{document_id}", headers=headers)
    listed = client.request(
        "GET", f"{base}/awarded-grants/{award_id}/documents", headers=headers
    )
    mark(
        "metadata_route_operational",
        _status(read) == 200 and _status(listed) == 200,
        f"metadata_read_back_failed:{_status(read)}/{_status(listed)}",
    )
    if _body(created).get("object_store_configured"):
        blocked.append("document_create_claimed_object_store_configured")

    # -- 4. another organization sees none of it ----------------------------
    cross_read = client.request(
        "GET", f"{_base(other)}/documents/{document_id}", headers=headers
    )
    cross_list = client.request(
        "GET", f"{_base(other)}/awarded-grants/{award_id}/documents", headers=headers
    )
    mark(
        "cross_org_refused",
        _status(cross_read) in {403, 404} and _status(cross_list) in {403, 404},
        f"cross_org_got_{_status(cross_read)}/{_status(cross_list)}",
    )
    mark(
        "org_scoped_read_write_proved",
        bool(proved["metadata_route_operational"] and proved["cross_org_refused"]),
        "org_scoping_was_not_proved_on_both_sides",
    )

    # -- 5. a caller may not relabel the write ------------------------------
    relabel = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/documents",
        json={**DOCUMENT_BODY, "is_demo": False, "fact_status": "verified"},
        headers=headers,
    )
    mark(
        "caller_supplied_fields_refused",
        _status(relabel) in {400, 422} and "is_demo" in _reason_text(relabel),
        f"caller_relabel_got_{_status(relabel)}",
    )

    # -- 6. a caller may not send a file ------------------------------------
    field_refusals: dict[str, Any] = {}
    for field in BODY_STORAGE_PROBES:
        response = client.request(
            "POST",
            f"{base}/awarded-grants/{award_id}/documents",
            # A NAME, never content. Nothing here is a file and nothing is read
            # from disk.
            json={**DOCUMENT_BODY, field: "gate141-probe"},
            headers=headers,
        )
        refused = _status(response) == 422 and (
            "document_body_storage_is_not_configured" in _reason_text(response)
        )
        field_refusals[field] = {"status": _status(response), "refused": refused}
        if not refused:
            blocked.append(f"body_field_not_refused:{field}:{_status(response)}")
    mark(
        "body_storage_fields_refused",
        all(entry["refused"] for entry in field_refusals.values()),
        "a_body_storage_field_was_not_refused",
    )

    # -- 7. the body storage readiness route --------------------------------
    readiness = client.request(
        "GET", f"{base}/documents/{document_id}/body-storage", headers=headers
    )
    readiness_body = _body(readiness)
    mark(
        "body_storage_readiness_route_operational",
        _status(readiness) == 200
        and "body_storage_available" in readiness_body
        and "preflight_state" in readiness_body,
        f"body_storage_readiness_got_{_status(readiness)}",
    )
    for claim in ("body_storage_available", "object_store_configured"):
        if readiness_body.get(claim):
            blocked.append(f"body_storage_readiness_claimed:{claim}")
    if readiness_body.get("production_storage"):
        blocked.append("body_storage_readiness_claimed:production_storage")

    # -- 8. the body route, which refuses -----------------------------------
    stored = client.request(
        "POST",
        f"{base}/documents/{document_id}/body",
        json={"content_type": "application/pdf"},
        headers=headers,
    )
    stored_reason = _reason_text(stored)
    mark(
        "unconfigured_blocker_correct",
        _status(stored) == 422
        and "document_body_storage_is_not_configured" in stored_reason
        and '"object_store_configured": false' in stored_reason.lower(),
        f"body_route_got_{_status(stored)}:{stored_reason[:120]}",
    )

    named_key = client.request(
        "POST",
        f"{base}/documents/{document_id}/body",
        json={"content_type": "application/pdf", "object_key": "anywhere/i/like"},
        headers=headers,
    )
    mark(
        "caller_supplied_object_key_refused",
        _status(named_key) == 422
        and "caller_supplied_object_keys_are_not_accepted" in _reason_text(named_key),
        f"caller_named_key_got_{_status(named_key)}",
    )

    # -- 9. archive keeps the row -------------------------------------------
    archived = client.request(
        "POST", f"{base}/documents/{document_id}/archive", headers=headers
    )
    mark(
        "archive_preserves_the_row",
        _status(archived) == 200 and not _body(archived).get("document_body_written"),
        f"archive_got_{_status(archived)}",
    )
    _cleanup_award(client, base, award_id, headers, notes)

    return _summary(proved, blocked, notes, anonymous_results, end_to_end=True)


def _cleanup_award(
    client: Any, base: str, award_id: str, headers: dict[str, str], notes: list[str]
) -> None:
    """Archive the fixture award, so this smoke can be re-run.

    `json={}` is not decoration: the archive route declares a required
    `ArchiveBody`, and posting without one returns 422 and leaves the award
    live - which made the second run of this smoke fail on a unique index.
    """
    response = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/archive",
        json={},
        headers=headers,
    )
    if _status(response) not in {200, 404}:
        notes.append(f"award_cleanup_got_{_status(response)}")


def _summary(
    proved: dict[str, bool],
    blocked: list[str],
    notes: list[str],
    anonymous_results: list[dict[str, Any]],
    *,
    end_to_end: bool,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **proved,
            "end_to_end_completed": bool(end_to_end and not blocked),
            "authenticated_run": end_to_end,
            "unauthenticated_probes": anonymous_results,
            "body_bytes_not_required": True,
            "notes": sorted(set(notes)),
            # Constants. Nothing in this smoke can set any of them.
            "external_object_store_contacted": False,
            "network_calls_to_object_storage": 0,
            "body_bytes_sent": 0,
            "body_bytes_written": 0,
            "real_customer_files_read": 0,
            "real_customer_files_hashed": 0,
            "credential_values_sent": False,
            "secrets_exposed": False,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def document_storage_route_smoke_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    """What must never be true of a document storage route smoke result."""
    fails: list[str] = []

    if result.get("end_to_end_completed"):
        for key in (
            "unauthenticated_refused",
            "forged_header_refused",
            "metadata_route_operational",
            "org_scoped_read_write_proved",
            "cross_org_refused",
            "caller_supplied_fields_refused",
            "body_storage_fields_refused",
            "body_storage_readiness_route_operational",
            "unconfigured_blocker_correct",
            "caller_supplied_object_key_refused",
            "archive_preserves_the_row",
        ):
            if not result.get(key):
                fails.append(f"end_to_end_without:{key}")
        if result.get("blocked_reasons"):
            fails.append("end_to_end_alongside_blockers")

    # Metadata must never come to depend on the store it does not need.
    if result.get("metadata_route_operational") and not result.get(
        "body_bytes_not_required"
    ):
        fails.append("metadata_started_requiring_body_bytes")

    for field in (
        "external_object_store_contacted",
        "credential_values_sent",
        "secrets_exposed",
        "real_customer_data_written",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in (
        "network_calls_to_object_storage",
        "body_bytes_sent",
        "body_bytes_written",
        "real_customer_files_read",
        "real_customer_files_hashed",
    ):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    return fails
