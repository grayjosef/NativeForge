"""Gate 140G: drive the eight tenant digest routes and report what each proved.

Not a description of the routes — a client that calls them.

```text
add a federal registry source to the watchlist
add a South Carolina registry source
both are archived at the end, because one live entry per source is an index
read the watchlist back, anchored on organization_id
read one entry by id
ask for the weekly digest                        -> the default, no setting
ask for the daily digest                         -> refused, not enabled
enable daily on the profile
ask for the daily digest again                   -> produced
suppress one opportunity                          -> an audit row, then a suppression
ask for the digest again                          -> the item moved, not vanished
lift the suppression                              -> it comes back
archive a watchlist entry                         -> the row stays
```

Plus the refusals, which are the part worth proving:

```text
unauthenticated on every route            401
a forged X-NF-Org-Id                      401, the header is not a parameter
a caller setting is_demo or fact_status   400, named
a registry source id that is not in the registry   400, named
a controlled_fixture id without the prefix         400, named
an unrecognised cadence                            422, named
reading another organization's watchlist  -> zero rows, never a leak
```

The client is injectable so this runs against a `TestClient` in the suite and
against the live app in the verifier, with the same code deciding what passed.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

SCHEMA_VERSION = "nf_tenant_digest_route_smoke_v1"

#: A real federal source id from the seed catalogue this repository ships.
#: Watching it is a statement of interest. Nothing here fetches it.
FEDERAL_SOURCE_ID = "nf-seed-2026-fed-001"

#: A real South Carolina source id, because doc 570's beta lane is SC-first.
SC_SOURCE_ID = "nf-seed-2026-st-041"

#: A registry id nobody issued, used to prove the registry check bites.
UNKNOWN_SOURCE_ID = "nf-seed-2026-fed-999999"

#: A fixture id missing the `nf-fixture-` prefix, to prove the prefix bites.
MISLABELLED_FIXTURE_ID = "totally-a-fixture-honest"

#: A fixed entry id for the unauthenticated probes. Fixed rather than random
#: because the probes end up in a committed artifact: a fresh uuid4 per run made
#: the same measurement produce different bytes, and the probe's claim is "any
#: entry id is refused before anything is looked up", which one id proves as
#: well as a new one.
ANONYMOUS_ENTRY_ID = "00000000-0000-0000-0000-000000000140"


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
    """The refusal reasons, flattened to one searchable string.

    Flattened rather than indexed, because three guards shape a refusal
    differently - `detail.error`, `detail.blocked_reasons`, `detail.reasons` -
    and asserting on a shape would make the smoke pass or fail on which guard
    fired rather than on whether the right thing was refused.
    """
    return json.dumps(_body(response).get("detail", ""))


def run_tenant_digest_route_smoke(
    *,
    client: Any,
    organization_id: str,
    other_organization_id: str,
    session_headers: dict[str, str] | None = None,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Drive every route. ``client`` is any object with `.request`."""
    org = str(organization_id)
    other = str(other_organization_id)
    headers = dict(session_headers or {})
    base = _base(org)

    blocked: list[str] = []
    notes: list[str] = []
    proved: dict[str, bool] = {
        "unauthenticated_refused": False,
        "forged_header_refused": False,
        "watchlist_route_operational": False,
        "watchlist_registry_check_enforced": False,
        "watchlist_fixture_prefix_enforced": False,
        "watchlist_caller_supplied_fields_refused": False,
        "watchlist_archive_preserves_the_row": False,
        "digest_preview_operational": False,
        "weekly_default_proved": False,
        "daily_refused_before_opt_in": False,
        "daily_setting_proved": False,
        "unknown_cadence_refused": False,
        "suppression_proved": False,
        "suppression_audit_backed": False,
        "suppression_preserves_the_opportunity": False,
        "suppression_lift_proved": False,
        "cross_org_refused": False,
        "readiness_route_operational": False,
    }

    def mark(key: str, value: bool, why: str) -> None:
        proved[key] = bool(value)
        if not value:
            blocked.append(why)

    # -- 1. unauthenticated, on every route --------------------------------
    anonymous: tuple[tuple[str, str], ...] = (
        ("GET", f"{base}/source-watchlist"),
        ("POST", f"{base}/source-watchlist"),
        ("GET", f"{base}/source-watchlist/{ANONYMOUS_ENTRY_ID}"),
        ("POST", f"{base}/source-watchlist/{ANONYMOUS_ENTRY_ID}/archive"),
        ("GET", f"{base}/digest"),
        ("GET", f"{base}/digest/readiness"),
        ("POST", f"{base}/digest/cadence"),
        ("POST", f"{base}/digest/suppress"),
        ("POST", f"{base}/digest/lift"),
    )
    anonymous_results: list[dict[str, Any]] = []
    for method, path in anonymous:
        response = client.request(method, path, json={} if method == "POST" else None)
        refused = _status(response) == 401
        anonymous_results.append(
            {"method": method, "path": path, "status": _status(response)}
        )
        if not refused:
            blocked.append(f"unauthenticated_got_{_status(response)}:{method} {path}")
    proved["unauthenticated_refused"] = not any(
        r["status"] != 401 for r in anonymous_results
    )

    # A forged dev header authorizes nothing. It is not a parameter on any of
    # these routes, which is why it cannot become one by being sent.
    forged = client.request(
        "GET", f"{base}/source-watchlist", headers={"X-NF-Org-Id": org}
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

    # -- 2. the watchlist ---------------------------------------------------
    federal = client.request(
        "POST",
        f"{base}/source-watchlist",
        json={
            "source_id": FEDERAL_SOURCE_ID,
            "watchlist_source": "registry_entry",
            "source_name": "Aid to Tribal Government Services",
            "jurisdiction": "federal",
            "program_area": "tribal_government_operations",
        },
        headers=headers,
    )
    if _status(federal) != 201:
        blocked.append(f"watchlist_add_got_{_status(federal)}:{_reason_text(federal)}")
        return _summary(
            proved, blocked, notes, anonymous_results, end_to_end=False, counts={}
        )
    entry_id = _body(federal)["entry_id"]
    if _body(federal).get("source_monitoring_live"):
        blocked.append("watchlist_add_claimed_source_monitoring_live")

    sc = client.request(
        "POST",
        f"{base}/source-watchlist",
        json={
            "source_id": SC_SOURCE_ID,
            "watchlist_source": "registry_entry",
            "source_name": "South Carolina Commission for Minority Affairs",
            "jurisdiction": "SC",
        },
        headers=headers,
    )
    if _status(sc) != 201:
        blocked.append(f"watchlist_add_sc_got_{_status(sc)}:{_reason_text(sc)}")
    sc_entry_id = _body(sc).get("entry_id")

    listed = client.request("GET", f"{base}/source-watchlist", headers=headers)
    read_one = client.request(
        "GET", f"{base}/source-watchlist/{entry_id}", headers=headers
    )
    mark(
        "watchlist_route_operational",
        _status(listed) == 200
        and _status(read_one) == 200
        and int(_body(listed).get("rows_read") or 0) >= 1
        and _body(read_one).get("source_id") == FEDERAL_SOURCE_ID,
        f"watchlist_read_back_failed:{_status(listed)}/{_status(read_one)}",
    )

    # A registry claim is checked against the shipped catalogue.
    unknown = client.request(
        "POST",
        f"{base}/source-watchlist",
        json={"source_id": UNKNOWN_SOURCE_ID, "watchlist_source": "registry_entry"},
        headers=headers,
    )
    mark(
        "watchlist_registry_check_enforced",
        _status(unknown) in {400, 422}
        and "source_id_is_not_in_the_source_registry" in _reason_text(unknown),
        f"unknown_registry_source_got_{_status(unknown)}:{_reason_text(unknown)}",
    )

    mislabelled = client.request(
        "POST",
        f"{base}/source-watchlist",
        json={
            "source_id": MISLABELLED_FIXTURE_ID,
            "watchlist_source": "controlled_fixture",
        },
        headers=headers,
    )
    mark(
        "watchlist_fixture_prefix_enforced",
        _status(mislabelled) in {400, 422}
        and "fixture" in _reason_text(mislabelled).lower(),
        f"mislabelled_fixture_got_{_status(mislabelled)}",
    )

    supplied = client.request(
        "POST",
        f"{base}/source-watchlist",
        json={
            "source_id": "nf-fixture-g140-supplied",
            "watchlist_source": "controlled_fixture",
            "is_demo": False,
            "fact_status": "verified",
        },
        headers=headers,
    )
    mark(
        "watchlist_caller_supplied_fields_refused",
        _status(supplied) in {400, 422} and "is_demo" in _reason_text(supplied),
        f"caller_supplied_fields_got_{_status(supplied)}",
    )

    # -- 3. the weekly digest, with no setting at all -----------------------
    weekly = client.request("GET", f"{base}/digest", headers=headers)
    weekly_body = _body(weekly)
    mark(
        "digest_preview_operational",
        _status(weekly) == 200 and int(weekly_body.get("items_total") or 0) >= 1,
        f"weekly_digest_got_{_status(weekly)}:{_reason_text(weekly)}",
    )
    mark(
        "weekly_default_proved",
        weekly_body.get("cadence") == "weekly"
        and weekly_body.get("default_cadence") == "weekly"
        and weekly_body.get("daily_alerts_enabled") is False,
        f"weekly_was_not_the_default:{weekly_body.get('cadence')}",
    )
    for claim in (
        "source_monitoring_live",
        "live_source_coverage",
        "email_delivery_live",
    ):
        if weekly_body.get(claim):
            blocked.append(f"digest_claimed:{claim}")
    if weekly_body.get("delivery_status") != "preview_only":
        blocked.append(f"delivery_status:{weekly_body.get('delivery_status')}")
    if weekly_body.get("candidate_provenance") != "labelled_fixture_snapshots":
        blocked.append(
            f"candidate_provenance:{weekly_body.get('candidate_provenance')}"
        )

    unknown_cadence = client.request(
        "GET", f"{base}/digest?cadence=hourly", headers=headers
    )
    mark(
        "unknown_cadence_refused",
        _status(unknown_cadence) == 422
        and "cadence_not_recognised" in _reason_text(unknown_cadence),
        f"unknown_cadence_got_{_status(unknown_cadence)}",
    )

    # -- 4. daily, which is optional and off ---------------------------------
    daily_before = client.request(
        "GET", f"{base}/digest?cadence=daily", headers=headers
    )
    mark(
        "daily_refused_before_opt_in",
        _status(daily_before) == 422
        and "has_not_enabled_it" in _reason_text(daily_before),
        f"daily_before_opt_in_got_{_status(daily_before)}",
    )

    enabled = client.request(
        "POST",
        f"{base}/digest/cadence",
        json={"digest_frequency": "daily"},
        headers=headers,
    )
    daily_after = client.request("GET", f"{base}/digest?cadence=daily", headers=headers)
    daily_body = _body(daily_after)
    mark(
        "daily_setting_proved",
        _status(enabled) == 200
        and _body(enabled).get("daily_alerts_enabled") is True
        and _status(daily_after) == 200
        and daily_body.get("cadence") == "daily"
        and daily_body.get("daily_alerts_enabled") is True,
        f"daily_after_opt_in_got_{_status(enabled)}/{_status(daily_after)}",
    )
    # Back to weekly, so this smoke can be re-run and so nothing is left
    # asking for a daily alert nobody can deliver.
    restored = client.request(
        "POST",
        f"{base}/digest/cadence",
        json={"digest_frequency": "weekly"},
        headers=headers,
    )
    if _status(restored) != 200:
        notes.append(f"cadence_restore_got_{_status(restored)}")

    # -- 5. suppression ------------------------------------------------------
    target = opportunity_id or next(
        (
            item.get("opportunity_id")
            for item in (weekly_body.get("items") or [])
            if item.get("opportunity_id")
        ),
        None,
    )
    counts: dict[str, Any] = {
        "visible_before": int(weekly_body.get("items_visible") or 0),
        "total_before": int(weekly_body.get("items_total") or 0),
    }
    if target is None:
        blocked.append("no_digest_item_to_suppress")
    else:
        suppressed = client.request(
            "POST",
            f"{base}/digest/suppress",
            json={
                "opportunity_id": target,
                "suppression_reason": "pursuit_started",
                "pursuit_record_id": f"pursuit-g140-{uuid.uuid4().hex[:8]}",
            },
            headers=headers,
        )
        suppress_body = _body(suppressed)
        mark(
            "suppression_proved",
            _status(suppressed) == 201
            and int(suppress_body.get("rows_written") or 0) == 1,
            f"suppress_got_{_status(suppressed)}:{_reason_text(suppressed)}",
        )
        # The audit id is reported, and it is a uuid rather than a placeholder.
        audit_id = suppress_body.get("audit_event_id")
        audit_shaped = False
        if isinstance(audit_id, str):
            try:
                uuid.UUID(audit_id)
                audit_shaped = True
            except ValueError:
                audit_shaped = False
        mark(
            "suppression_audit_backed",
            audit_shaped,
            f"suppression_audit_event_id_not_a_uuid:{audit_id!r}",
        )
        if int(suppress_body.get("rows_deleted") or 0):
            blocked.append("suppression_deleted_rows")

        after = client.request("GET", f"{base}/digest", headers=headers)
        after_body = _body(after)
        counts.update(
            {
                "visible_after": int(after_body.get("items_visible") or 0),
                "suppressed_after": int(after_body.get("items_suppressed") or 0),
                "total_after": int(after_body.get("items_total") or 0),
            }
        )
        visible_ids = {
            item.get("opportunity_id") for item in (after_body.get("items") or [])
        }
        suppressed_ids = {
            item.get("opportunity_id")
            for item in (after_body.get("suppressed_items") or [])
        }
        mark(
            "suppression_preserves_the_opportunity",
            _status(after) == 200
            and target not in visible_ids
            and target in suppressed_ids
            # The total is unchanged: the item MOVED, it did not vanish.
            and counts["total_after"] == counts["total_before"]
            and counts["visible_after"] == counts["visible_before"] - 1,
            "suppression_changed_the_total_instead_of_moving_one_item:"
            f"{counts.get('total_before')}->{counts.get('total_after')}",
        )

        lifted = client.request(
            "POST",
            f"{base}/digest/lift",
            json={"opportunity_id": target},
            headers=headers,
        )
        restored_digest = _body(
            client.request("GET", f"{base}/digest", headers=headers)
        )
        mark(
            "suppression_lift_proved",
            _status(lifted) == 200
            and int(_body(lifted).get("rows_written") or 0) == 1
            and target
            in {
                item.get("opportunity_id")
                for item in (restored_digest.get("items") or [])
            },
            f"lift_got_{_status(lifted)}:{_reason_text(lifted)}",
        )

    # -- 6. readiness --------------------------------------------------------
    readiness = client.request("GET", f"{base}/digest/readiness", headers=headers)
    readiness_body = _body(readiness)
    mark(
        "readiness_route_operational",
        _status(readiness) == 200 and "tenant_digest_operational" in readiness_body,
        f"readiness_got_{_status(readiness)}",
    )
    for claim in (
        "source_monitoring_live",
        "email_delivery_available",
        "production_tenant_digest",
    ):
        if readiness_body.get(claim):
            blocked.append(f"readiness_claimed:{claim}")

    # -- 7. another organization sees none of it ----------------------------
    cross_watchlist = client.request(
        "GET", f"{_base(other)}/source-watchlist", headers=headers
    )
    cross_entry = client.request(
        "GET", f"{_base(other)}/source-watchlist/{entry_id}", headers=headers
    )
    cross_digest = client.request("GET", f"{_base(other)}/digest", headers=headers)
    # 403/404 from the same-org guard, which does not confirm the row exists.
    mark(
        "cross_org_refused",
        _status(cross_watchlist) in {403, 404}
        and _status(cross_entry) in {403, 404}
        and _status(cross_digest) in {403, 404},
        "cross_org_reads_were_not_refused:"
        f"{_status(cross_watchlist)}/{_status(cross_entry)}/{_status(cross_digest)}",
    )

    # -- 8. archiving stops the watching and keeps the row ------------------
    archived = client.request(
        "POST", f"{base}/source-watchlist/{entry_id}/archive", headers=headers
    )
    still_there = client.request(
        "GET",
        f"{base}/source-watchlist?include_archived=true",
        headers=headers,
    )
    active_only = client.request("GET", f"{base}/source-watchlist", headers=headers)
    mark(
        "watchlist_archive_preserves_the_row",
        _status(archived) == 200
        and int(_body(archived).get("rows_deleted") or 0) == 0
        and _status(still_there) == 200
        and entry_id
        in {
            entry.get("entry_id") for entry in (_body(still_there).get("entries") or [])
        }
        and entry_id
        not in {
            entry.get("entry_id") for entry in (_body(active_only).get("entries") or [])
        },
        f"archive_did_not_preserve_the_row:{_status(archived)}",
    )

    if sc_entry_id:
        cleanup = client.request(
            "POST",
            f"{base}/source-watchlist/{sc_entry_id}/archive",
            headers=headers,
        )
        if _status(cleanup) != 200:
            notes.append(f"sc_entry_cleanup_got_{_status(cleanup)}")

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
            "item_counts": counts,
            "notes": sorted(set(notes)),
            # Constants. Nothing in this smoke can set any of them.
            "live_grant_sources_called": False,
            "network_calls_to_grant_sources": 0,
            "emails_sent": 0,
            "collectors_activated": 0,
            "object_store_calls": 0,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def tenant_digest_route_smoke_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a tenant digest route smoke result."""
    fails: list[str] = []

    if result.get("end_to_end_completed"):
        for key in (
            "unauthenticated_refused",
            "forged_header_refused",
            "watchlist_route_operational",
            "watchlist_registry_check_enforced",
            "watchlist_fixture_prefix_enforced",
            "watchlist_caller_supplied_fields_refused",
            "watchlist_archive_preserves_the_row",
            "digest_preview_operational",
            "weekly_default_proved",
            "daily_refused_before_opt_in",
            "daily_setting_proved",
            "unknown_cadence_refused",
            "suppression_proved",
            "suppression_audit_backed",
            "suppression_preserves_the_opportunity",
            "suppression_lift_proved",
            "cross_org_refused",
            "readiness_route_operational",
        ):
            if not result.get(key):
                fails.append(f"end_to_end_without:{key}")
        if result.get("blocked_reasons"):
            fails.append("end_to_end_alongside_blockers")

    # A suppression that survived while its audit evidence did not would be
    # exactly the untraceable disappearance this gate refuses.
    if result.get("suppression_proved") and not result.get("suppression_audit_backed"):
        fails.append("suppression_without_audit_evidence")

    for field in (
        "live_grant_sources_called",
        "real_customer_data_written",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in (
        "network_calls_to_grant_sources",
        "emails_sent",
        "collectors_activated",
        "object_store_calls",
    ):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    if not result.get("authenticated_run") and result.get("suppression_proved"):
        fails.append("suppression_proved_without_an_authenticated_run")

    return fails
