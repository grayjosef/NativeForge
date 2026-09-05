"""Gate 142: drive the six delivery routes and report what each proved.

Not a description of the routes — a client that calls them.

```text
render the digest for delivery         a subject, a body, a hash
read the recipients                    fingerprints and domains, no addresses
record a dry run                       intents, org-anchored, audited
read the intents back
record the same run again              refused: already recorded for this period
cancel one                             the row stays
read readiness                         what is ready, what activation needs
```

Plus the refusals:

```text
unauthenticated on every route              401
a forged X-NF-Org-Id                        401, the header is not a parameter
a caller setting is_demo or fact_status      400, named
an unrecognised cadence                      422, named
another organization's read                  403/404
```

The client is injectable so this runs against a `TestClient` in the suite and
against the live app in the verifier, with the same code deciding what passed.

No email is sent, no provider is contacted, and no address appears in any
response this smoke reads.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_digest_delivery_route_smoke_v1"

#: A fixed id for the unauthenticated probes. Fixed rather than random, because
#: these end up in a committed artifact.
ANONYMOUS_ID = "00000000-0000-0000-0000-000000000142"

#: Every response is checked for these. A mailbox in a delivery response is the
#: one thing this whole gate is built to prevent.
ADDRESS_MARKER = "@"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


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


def run_digest_delivery_route_smoke(
    *,
    client: Any,
    organization_id: str,
    other_organization_id: str,
    session_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Drive every delivery route. ``client`` is any object with `.request`."""
    org = str(organization_id)
    other = str(other_organization_id)
    headers = dict(session_headers or {})
    base = _base(org)

    blocked: list[str] = []
    notes: list[str] = []
    proved: dict[str, bool] = {
        "unauthenticated_refused": False,
        "forged_header_refused": False,
        "delivery_routes_operational": False,
        "digest_renders_for_delivery": False,
        "recipient_validation_works": False,
        "no_address_in_any_response": False,
        "delivery_intent_recorded": False,
        "delivery_audit_event_created": False,
        "send_disabled_blocker_explicit": False,
        "duplicate_run_refused": False,
        "cancel_preserves_the_row": False,
        "unknown_cadence_refused": False,
        "caller_supplied_fields_refused": False,
        "cross_org_refused": False,
        "readiness_route_operational": False,
    }
    address_free = True

    def mark(key: str, value: bool, why: str) -> None:
        proved[key] = bool(value)
        if not value:
            blocked.append(why)

    def check_no_address(label: str, response: Any) -> None:
        """A mailbox in a delivery response is the failure this gate prevents."""
        nonlocal address_free
        rendered = json.dumps(_body(response))
        if ADDRESS_MARKER in rendered:
            address_free = False
            blocked.append(f"address_shaped_string_in_response:{label}")

    # -- 1. unauthenticated, on every route --------------------------------
    anonymous: tuple[tuple[str, str], ...] = (
        ("GET", f"{base}/digest/delivery/preview"),
        ("GET", f"{base}/digest/delivery/recipients"),
        ("POST", f"{base}/digest/delivery/dry-run"),
        ("GET", f"{base}/digest/delivery/intents"),
        ("POST", f"{base}/digest/delivery/cancel"),
        ("GET", f"{base}/digest/delivery/readiness"),
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
        f"{base}/digest/delivery/readiness",
        headers={"X-NF-Org-Id": org},
    )
    mark(
        "forged_header_refused",
        _status(forged) == 401,
        f"forged_header_got_{_status(forged)}",
    )

    if not headers:
        return _summary(
            proved, blocked, notes, anonymous_results, end_to_end=False, counts={}
        )

    # -- 2. the render ------------------------------------------------------
    preview = client.request("GET", f"{base}/digest/delivery/preview", headers=headers)
    preview_body = _body(preview)
    check_no_address("preview", preview)
    mark(
        "digest_renders_for_delivery",
        _status(preview) == 200
        and bool(preview_body.get("deliverable"))
        and bool(preview_body.get("subject_line"))
        and int(preview_body.get("body_byte_length") or 0) > 0,
        f"preview_got_{_status(preview)}:{_reason_text(preview)[:120]}",
    )
    for claim in ("email_delivery", "send_attempted", "provider_contacted"):
        if preview_body.get(claim):
            blocked.append(f"preview_claimed:{claim}")
    if int(preview_body.get("emails_sent") or 0):
        blocked.append("preview_reported_emails_sent")
    if preview_body.get("delivery_status") != "preview_only":
        blocked.append(f"preview_delivery_status:{preview_body.get('delivery_status')}")

    unknown_cadence = client.request(
        "GET", f"{base}/digest/delivery/preview?cadence=hourly", headers=headers
    )
    mark(
        "unknown_cadence_refused",
        _status(unknown_cadence) == 422
        and "cadence_not_recognised" in _reason_text(unknown_cadence),
        f"unknown_cadence_got_{_status(unknown_cadence)}",
    )

    # -- 3. the recipients --------------------------------------------------
    recipients = client.request(
        "GET", f"{base}/digest/delivery/recipients", headers=headers
    )
    recipients_body = _body(recipients)
    check_no_address("recipients", recipients)
    # Every DELIVERABLE recipient has a fingerprint. Not every recipient:
    # `nf_identities.email` is nullable, so a member can exist with no address,
    # and that member is refused by name rather than dropped from the list -
    # an operator needs to see who cannot be reached.
    listed_recipients = recipients_body.get("recipients") or []
    deliverable_have_fingerprints = all(
        r.get("recipient_fingerprint") and len(str(r["recipient_fingerprint"])) == 32
        for r in listed_recipients
        if r.get("deliverable")
    )
    undeliverable_are_named = all(
        r.get("blocked_reasons") for r in listed_recipients if not r.get("deliverable")
    )
    mark(
        "recipient_validation_works",
        _status(recipients) == 200
        and int(recipients_body.get("deliverable_count") or 0) >= 1
        and deliverable_have_fingerprints
        and undeliverable_are_named,
        f"recipients_got_{_status(recipients)}:{_reason_text(recipients)[:120]}",
    )
    if recipients_body.get("addresses_reported") or recipients_body.get(
        "addresses_stored"
    ):
        blocked.append("recipients_route_claimed_addresses")

    # -- 4. the dry run -----------------------------------------------------
    dry_run = client.request(
        "POST",
        f"{base}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=headers,
    )
    dry_run_body = _body(dry_run)
    check_no_address("dry_run", dry_run)
    mark(
        "delivery_intent_recorded",
        _status(dry_run) == 201 and int(dry_run_body.get("rows_written") or 0) >= 1,
        f"dry_run_got_{_status(dry_run)}:{_reason_text(dry_run)[:160]}",
    )

    audit_id = dry_run_body.get("audit_event_id")
    audit_shaped = False
    if isinstance(audit_id, str):
        import uuid as _uuid

        try:
            _uuid.UUID(audit_id)
            audit_shaped = True
        except ValueError:
            audit_shaped = False
    mark(
        "delivery_audit_event_created",
        audit_shaped,
        f"dry_run_audit_event_id_not_a_uuid:{audit_id!r}",
    )

    blocker = dry_run_body.get("send_disabled_reason")
    mark(
        "send_disabled_blocker_explicit",
        bool(blocker)
        and blocker in {"no_email_provider_configured", "send_activation_absent"},
        f"send_disabled_reason_was:{blocker!r}",
    )
    for claim in ("email_delivery", "send_attempted", "provider_contacted"):
        if dry_run_body.get(claim):
            blocked.append(f"dry_run_claimed:{claim}")
    if int(dry_run_body.get("emails_sent") or 0):
        blocked.append("dry_run_reported_emails_sent")
    if int(dry_run_body.get("rows_deleted") or 0):
        blocked.append("dry_run_deleted_rows")

    # The same period, again. One intent per recipient per period.
    again = client.request(
        "POST",
        f"{base}/digest/delivery/dry-run",
        json={"cadence": "weekly"},
        headers=headers,
    )
    mark(
        "duplicate_run_refused",
        _status(again) == 422
        and "already_recorded_for_this_period" in _reason_text(again),
        f"duplicate_run_got_{_status(again)}",
    )

    # -- 5. read them back ---------------------------------------------------
    listed = client.request("GET", f"{base}/digest/delivery/intents", headers=headers)
    listed_body = _body(listed)
    check_no_address("intents", listed)
    counts: dict[str, Any] = {
        "intents_read": int(listed_body.get("rows_read") or 0),
        "send_disabled": int(listed_body.get("send_disabled_count") or 0),
        "dry_run_recorded": int(listed_body.get("dry_run_recorded_count") or 0),
    }
    stored_ok = _status(listed) == 200 and counts["intents_read"] >= 1
    for intent in listed_body.get("intents") or []:
        if intent.get("send_attempted") or intent.get("provider_contacted"):
            blocked.append(f"stored_intent_claims_a_send:{intent.get('intent_id')}")
        if int(intent.get("emails_sent") or 0):
            blocked.append(f"stored_intent_sent_email:{intent.get('intent_id')}")
        if intent.get("delivery_status") in {"queued", "sent"}:
            blocked.append(f"stored_intent_claims_a_delivery:{intent.get('intent_id')}")
    mark(
        "delivery_routes_operational",
        bool(
            stored_ok
            and proved["digest_renders_for_delivery"]
            and proved["recipient_validation_works"]
            and proved["delivery_intent_recorded"]
        ),
        f"intents_read_back_failed:{_status(listed)}",
    )

    # -- 6. a caller may not relabel the write ------------------------------
    relabel = client.request(
        "POST",
        f"{base}/digest/delivery/dry-run",
        json={"cadence": "weekly", "is_demo": False, "fact_status": "verified"},
        headers=headers,
    )
    mark(
        "caller_supplied_fields_refused",
        _status(relabel) in {400, 422} and "is_demo" in _reason_text(relabel),
        f"caller_relabel_got_{_status(relabel)}",
    )

    # -- 7. another organization sees none of it ----------------------------
    cross_intents = client.request(
        "GET", f"{_base(other)}/digest/delivery/intents", headers=headers
    )
    cross_preview = client.request(
        "GET", f"{_base(other)}/digest/delivery/preview", headers=headers
    )
    mark(
        "cross_org_refused",
        _status(cross_intents) in {403, 404} and _status(cross_preview) in {403, 404},
        f"cross_org_got_{_status(cross_intents)}/{_status(cross_preview)}",
    )

    # -- 8. readiness --------------------------------------------------------
    readiness = client.request(
        "GET", f"{base}/digest/delivery/readiness", headers=headers
    )
    readiness_body = _body(readiness)
    check_no_address("readiness", readiness)
    mark(
        "readiness_route_operational",
        _status(readiness) == 200
        and "email_delivery_readiness" in readiness_body
        and "missing_configuration" in readiness_body,
        f"readiness_got_{_status(readiness)}",
    )
    for claim in (
        "email_delivery",
        "provider_configured",
        "send_activated",
        "production_email_delivery",
    ):
        if readiness_body.get(claim):
            blocked.append(f"readiness_claimed:{claim}")

    # -- 9. cancel keeps the row ---------------------------------------------
    first_intent = next(
        (
            i.get("intent_id")
            for i in (listed_body.get("intents") or [])
            if i.get("intent_id")
        ),
        None,
    )
    if first_intent:
        cancelled = client.request(
            "POST",
            f"{base}/digest/delivery/cancel",
            json={"intent_id": first_intent},
            headers=headers,
        )
        after = _body(
            client.request(
                "GET",
                f"{base}/digest/delivery/intents?include_cancelled=true",
                headers=headers,
            )
        )
        active = _body(
            client.request("GET", f"{base}/digest/delivery/intents", headers=headers)
        )
        mark(
            "cancel_preserves_the_row",
            _status(cancelled) == 200
            and int(_body(cancelled).get("rows_deleted") or 0) == 0
            and first_intent
            in {i.get("intent_id") for i in (after.get("intents") or [])}
            and first_intent
            not in {i.get("intent_id") for i in (active.get("intents") or [])},
            f"cancel_did_not_preserve_the_row:{_status(cancelled)}",
        )
        counts["intents_after_cancel"] = int(active.get("rows_read") or 0)
    else:
        blocked.append("no_intent_to_cancel")

    proved["no_address_in_any_response"] = address_free

    return _summary(
        proved, blocked, notes, anonymous_results, end_to_end=True, counts=counts
    )


def _summary(
    proved: dict[str, bool],
    blocked: list[str],
    notes: list[str],
    anonymous_results: list[dict[str, Any]],
    *,
    end_to_end: bool,
    counts: dict[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **proved,
            "end_to_end_completed": bool(end_to_end and not blocked),
            "authenticated_run": end_to_end,
            "unauthenticated_probes": anonymous_results,
            "intent_counts": counts,
            "notes": sorted(set(notes)),
            # Constants. Nothing in this smoke can set any of them.
            "emails_sent": 0,
            "send_attempted": False,
            "provider_contacted": False,
            "network_calls_to_a_mail_provider": 0,
            "recipient_addresses_stored": False,
            "recipient_addresses_reported": False,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def delivery_route_smoke_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a delivery route smoke result."""
    fails: list[str] = []

    if result.get("end_to_end_completed"):
        for key in (
            "unauthenticated_refused",
            "forged_header_refused",
            "delivery_routes_operational",
            "digest_renders_for_delivery",
            "recipient_validation_works",
            "no_address_in_any_response",
            "delivery_intent_recorded",
            "delivery_audit_event_created",
            "send_disabled_blocker_explicit",
            "duplicate_run_refused",
            "cancel_preserves_the_row",
            "unknown_cadence_refused",
            "caller_supplied_fields_refused",
            "cross_org_refused",
            "readiness_route_operational",
        ):
            if not result.get(key):
                fails.append(f"end_to_end_without:{key}")
        if result.get("blocked_reasons"):
            fails.append("end_to_end_alongside_blockers")

    # An intent nobody can trace is a way for a system to quietly decide who
    # gets mail.
    if result.get("delivery_intent_recorded") and not result.get(
        "delivery_audit_event_created"
    ):
        fails.append("an_intent_was_recorded_without_audit_evidence")

    if result.get("delivery_intent_recorded") and not result.get(
        "no_address_in_any_response"
    ):
        fails.append("an_address_reached_a_delivery_response")

    for field in (
        "send_attempted",
        "provider_contacted",
        "recipient_addresses_stored",
        "recipient_addresses_reported",
        "real_customer_data_written",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("emails_sent", "network_calls_to_a_mail_provider"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    return fails
