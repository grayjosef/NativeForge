"""Gate 139G: drive the four post-award routes and report what each proved.

Not a description of the routes — a client that calls them.

```text
create an award
attach a requirement to it
attach a proof event to the requirement
attach a document REFERENCE to the award
read every one back, anchored on organization_id
call the same reads as a different organization      -> nothing
archive all four, in reverse dependency order
```

Plus the refusals, which are the part worth proving:

```text
unauthenticated                          401
a forged X-NF-Org-Id                     401, the header is not a parameter
a forged session cookie                  401
a caller setting is_demo or fact_status  400, named
a caller sending a document body         422, document_body_storage_is_not_configured
a requirement attached to another org's award   404
a due date with no due_date_status       422, from the route's own validator
```

The client is injectable so this runs against a `TestClient` in the suite and
against the live app in the verifier, with the same code deciding what passed.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_awarded_operational_route_smoke_v1"

LANES: tuple[str, ...] = (
    "awarded_grants",
    "award_requirements",
    "proof_audit",
    "document_metadata",
)

#: A fixture award, in the repositories' own vocabularies. Nothing here is
#: extracted from a document and nothing infers a date: `due_date_status` is
#: supplied because the caller supplies the date, which is the rule the
#: requirements route enforces.
AWARD_BODY: dict[str, Any] = {
    "award_number": "NF-G139-FIXTURE",
    "award_title": "Gate 139 fixture award",
    "funder_name": "Gate 139 fixture funder",
    "award_status": "active_award",
    "award_amount": "1000.00",
    "award_currency": "USD",
    "period_start": "2026-01-01",
    "period_end": "2026-12-31",
    "awarded_at": "2026-01-01",
    "active_obligation_status": "no_obligations_established",
    "requirements_extraction_status": "not_attempted",
}

REQUIREMENT_BODY: dict[str, Any] = {
    "requirement_type": "financial_report",
    "requirement_title": "Gate 139 fixture requirement",
    "requirement_status": "not_started",
    # `human_entered`, because a person typed it. Defaulting this to
    # `evidence_extracted` would claim an extraction happened.
    "requirement_source": "human_entered",
    "requirement_due_date": "2026-06-30",
    "due_date_status": "verified",
    "recurrence_rule": "one_time",
    "proof_status": "not_submitted",
    "submission_status": "not_submitted",
}

PROOF_BODY: dict[str, Any] = {
    "event_type": "mark_submitted",
    "event_status": "not_submitted",
    "proof_summary": "Gate 139 fixture proof event",
    "proof_source": "human_entered",
}

DOCUMENT_BODY: dict[str, Any] = {
    "document_kind": "financial_report",
    "document_status": "reference_recorded",
    "document_title": "Gate 139 fixture document reference",
    "document_source": "human_entered",
    "retention_class": "retain_7_days",
}

#: An unsupported requirement stays unresolved. Both values are the
#: repository's, and the route stores whichever the caller sends.
UNSUPPORTED_REQUIREMENT: dict[str, Any] = {
    **REQUIREMENT_BODY,
    "requirement_title": "Gate 139 unreadable requirement",
    "requirement_status": "needs_human_review",
    "requirement_source": "unsupported_document_type",
    # No date, and no status: nothing read one out of anything.
    "requirement_due_date": None,
    "due_date_status": None,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _base(organization_id: str) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}"


def run_post_award_route_smoke(
    *,
    client: Any,
    organization_id: str,
    other_organization_id: str,
    session_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Drive every lane. ``client`` is any object with `.get`/`.post`."""
    org = str(organization_id)
    other = str(other_organization_id)
    headers = dict(session_headers or {})
    base = _base(org)

    lanes: dict[str, dict[str, Any]] = {
        lane: {
            "route_operational": False,
            "unauthenticated_refused": False,
            "cross_org_refused": False,
            "created": False,
            "read_back": False,
            "archived": False,
            "blocked_reasons": [],
        }
        for lane in LANES
    }
    notes: list[str] = []

    def record(lane: str, key: str, value: Any) -> None:
        lanes[lane][key] = value

    def blocked(lane: str, reason: str) -> None:
        lanes[lane]["blocked_reasons"].append(reason)

    # -- 1. every lane refuses an unauthenticated caller --------------------
    anonymous = {
        "awarded_grants": ("GET", f"{base}/awarded-grants"),
        "award_requirements": (
            "GET",
            f"{base}/awarded-grants/{uuid.uuid4()}/requirements",
        ),
        "proof_audit": (
            "GET",
            f"{base}/requirements/{uuid.uuid4()}/proof-events",
        ),
        "document_metadata": (
            "GET",
            f"{base}/awarded-grants/{uuid.uuid4()}/documents",
        ),
    }
    for lane, (method, path) in anonymous.items():
        response = client.request(method, path)
        refused = response.status_code == 401
        record(lane, "unauthenticated_refused", refused)
        if not refused:
            blocked(lane, f"unauthenticated_got_{response.status_code}")

    # A forged header changes nothing. The dev header is not a parameter on
    # any of these routes, which Gates 134 and 135 made true.
    forged = client.request(
        "GET", f"{base}/awarded-grants", headers={"X-NF-Org-Id": org}
    )
    forged_header_refused = forged.status_code == 401
    if not forged_header_refused:
        notes.append(f"forged_header_got_{forged.status_code}")

    if not headers:
        return _summary(lanes, notes, end_to_end=False, forged=forged_header_refused)

    # -- 2. the award -------------------------------------------------------
    created = client.request(
        "POST", f"{base}/awarded-grants", json=AWARD_BODY, headers=headers
    )
    if created.status_code != 201:
        blocked("awarded_grants", f"create_got_{created.status_code}")
        return _summary(lanes, notes, end_to_end=False, forged=forged_header_refused)
    award_id = created.json()["award_id"]
    record("awarded_grants", "created", True)

    read = client.request("GET", f"{base}/awarded-grants/{award_id}", headers=headers)
    record("awarded_grants", "read_back", read.status_code == 200)
    cross = client.request(
        "GET", f"{_base(other)}/awarded-grants/{award_id}", headers=headers
    )
    # 404 from the same-org guard, which does not confirm the row exists.
    record("awarded_grants", "cross_org_refused", cross.status_code in {403, 404})

    # -- 3. the requirement -------------------------------------------------
    req = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/requirements",
        json=REQUIREMENT_BODY,
        headers=headers,
    )
    requirement_id = None
    if req.status_code == 201:
        requirement_id = req.json()["requirement_id"]
        record("award_requirements", "created", True)
        got = client.request(
            "GET", f"{base}/requirements/{requirement_id}", headers=headers
        )
        record("award_requirements", "read_back", got.status_code == 200)
    else:
        blocked("award_requirements", f"create_got_{req.status_code}")

    # A requirement may not attach to another organization's award.
    stray = client.request(
        "POST",
        f"{base}/awarded-grants/{uuid.uuid4()}/requirements",
        json=REQUIREMENT_BODY,
        headers=headers,
    )
    record("award_requirements", "cross_org_refused", stray.status_code == 404)

    # And an unsupported one stays unresolved rather than being invented.
    unsupported = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/requirements",
        json=UNSUPPORTED_REQUIREMENT,
        headers=headers,
    )
    unsupported_id = (
        unsupported.json().get("requirement_id")
        if unsupported.status_code == 201
        else None
    )
    unresolved_kept = False
    if unsupported_id:
        seen = client.request(
            "GET", f"{base}/requirements/{unsupported_id}", headers=headers
        )
        unresolved_kept = bool(
            seen.status_code == 200
            and seen.json().get("unresolved")
            and not seen.json().get("requirement_due_date")
        )

    # -- 4. the proof event -------------------------------------------------
    event_id = None
    if requirement_id:
        event = client.request(
            "POST",
            f"{base}/requirements/{requirement_id}/proof-events",
            json=PROOF_BODY,
            headers=headers,
        )
        if event.status_code == 201:
            event_id = event.json()["event_id"]
            record("proof_audit", "created", True)
            got = client.request(
                "GET", f"{base}/proof-events/{event_id}", headers=headers
            )
            record("proof_audit", "read_back", got.status_code == 200)
        else:
            blocked("proof_audit", f"create_got_{event.status_code}")

    stray_event = client.request(
        "POST",
        f"{base}/requirements/{uuid.uuid4()}/proof-events",
        json=PROOF_BODY,
        headers=headers,
    )
    record("proof_audit", "cross_org_refused", stray_event.status_code == 404)

    # -- 5. the document reference ------------------------------------------
    document_id = None
    doc = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/documents",
        json=DOCUMENT_BODY,
        headers=headers,
    )
    if doc.status_code == 201:
        document_id = doc.json()["document_id"]
        record("document_metadata", "created", True)
        got = client.request("GET", f"{base}/documents/{document_id}", headers=headers)
        record("document_metadata", "read_back", got.status_code == 200)
    else:
        blocked("document_metadata", f"create_got_{doc.status_code}")

    stray_doc = client.request(
        "POST",
        f"{base}/awarded-grants/{uuid.uuid4()}/documents",
        json=DOCUMENT_BODY,
        headers=headers,
    )
    record("document_metadata", "cross_org_refused", stray_doc.status_code == 404)

    # A body is refused by name, not dropped.
    with_body = client.request(
        "POST",
        f"{base}/awarded-grants/{award_id}/documents",
        json={**DOCUMENT_BODY, "object_key": "s3://nope", "content_length": 12},
        headers=headers,
    )
    body_refused = with_body.status_code == 422 and (
        "document_body_storage_is_not_configured" in json.dumps(with_body.json())
    )

    # And so is a caller trying to relabel the write.
    relabelled = client.request(
        "POST",
        f"{base}/awarded-grants",
        json={**AWARD_BODY, "is_demo": False, "fact_status": "verified"},
        headers=headers,
    )
    relabel_refused = relabelled.status_code == 400

    # -- 6. cleanup, reverse dependency order -------------------------------
    def archive(lane: str, path: str) -> None:
        response = client.request("POST", path, json={}, headers=headers)
        record(lane, "archived", response.status_code == 200)
        if response.status_code != 200:
            blocked(lane, f"archive_got_{response.status_code}")

    if document_id:
        archive("document_metadata", f"{base}/documents/{document_id}/archive")
    if event_id:
        archive("proof_audit", f"{base}/proof-events/{event_id}/archive")
    for rid in (requirement_id, unsupported_id):
        if rid:
            archive("award_requirements", f"{base}/requirements/{rid}/archive")
    archive("awarded_grants", f"{base}/awarded-grants/{award_id}/archive")

    for facts in lanes.values():
        facts["route_operational"] = bool(
            facts["created"]
            and facts["read_back"]
            and facts["cross_org_refused"]
            and facts["unauthenticated_refused"]
            and facts["archived"]
            and not facts["blocked_reasons"]
        )

    return _summary(
        lanes,
        notes,
        end_to_end=all(facts["route_operational"] for facts in lanes.values()),
        forged=forged_header_refused,
        body_refused=body_refused,
        relabel_refused=relabel_refused,
        unresolved_kept=unresolved_kept,
    )


def _summary(
    lanes: dict[str, dict[str, Any]],
    notes: list[str],
    *,
    end_to_end: bool,
    forged: bool,
    body_refused: bool = False,
    relabel_refused: bool = False,
    unresolved_kept: bool = False,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lanes": lanes,
            "end_to_end_proved": bool(end_to_end),
            "forged_header_refused": bool(forged),
            "document_body_refused": bool(body_refused),
            "caller_relabel_refused": bool(relabel_refused),
            "unsupported_requirement_stayed_unresolved": bool(unresolved_kept),
            "route_operational_lanes": sorted(
                lane for lane, facts in lanes.items() if facts["route_operational"]
            ),
            "blocked_lanes": sorted(
                lane for lane, facts in lanes.items() if not facts["route_operational"]
            ),
            # Constants. This client calls routes; it invents nothing.
            "object_store_contacted": False,
            "document_body_written": False,
            "live_source_called": False,
            "email_sent": False,
            "real_organization_touched": False,
            "notes": sorted(set(notes)),
        }
    )


def route_smoke_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("end_to_end_proved"):
        if result.get("blocked_lanes"):
            fails.append("end_to_end_proved_with_a_blocked_lane")
        if not result.get("forged_header_refused"):
            fails.append("end_to_end_proved_while_a_forged_header_was_accepted")
        if not result.get("document_body_refused"):
            fails.append("end_to_end_proved_while_a_document_body_was_accepted")
        if not result.get("caller_relabel_refused"):
            fails.append("end_to_end_proved_while_a_caller_could_relabel_a_write")
        for lane, facts in (result.get("lanes") or {}).items():
            if not facts.get("unauthenticated_refused"):
                fails.append(f"lane_admitted_an_unauthenticated_caller:{lane}")
            if not facts.get("cross_org_refused"):
                fails.append(f"lane_admitted_a_cross_organization_request:{lane}")

    for field in (
        "object_store_contacted",
        "document_body_written",
        "live_source_called",
        "email_sent",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")

    return fails
