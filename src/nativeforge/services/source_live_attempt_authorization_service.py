"""Is ONE recorded live attempt validly authorized? (Gate 163)

Gates 156-162 encoded "nothing live has ever happened" in nine layers. Eight
were converted as the gate progressed; the ninth was
`some_attempt_was_not_hermetic`, which went false the moment a real authorized
collection was recorded.

Converting it needs a question nothing could previously ask, because no live
attempt could previously exist: *is this particular live row one the campaign
authorized?* This module answers it, and it is the ONLY place that answers it -
the attempt counter and the execution-envelope health lane both call it, so
"authorized" cannot come to mean two different things in two places.

## Structural, not arithmetic

The tempting implementation is `live_attempts - 1`, or "the count we expected
minus the one we know about". That is not a check: it would pass for any second
live row, from any source, at any host. Every linkage below is resolved from
the row and from recorded evidence.

```text
transport_is_live                 the row says live
authorized_source_id_present      it names an authorization
source_is_in_the_authorized_set   that name is one this campaign authorized
source_id_matches_authorization   the row's source and its authorization agree
authorization_is_approved         the recorded facts resolve to approved,
                                  which requires signed terms, human review
                                  and activation
live_fetch_opt_in_exists          a signed per-source opt-in
request_authority_matches         the request fingerprint is the fingerprint
                                  of the authorized source's own endpoint
proof_linkage_is_valid            a claimed proof has a persisted payload and
                                  a hash
```

## `live` is never sufficient on its own

A row being live is the thing that needs justifying, not the justification. An
attempt that is live and fails any linkage above is UNAUTHORIZED, and the
counters that must stay zero are the unauthorized ones.

## The authority check without storing a URL

The attempt row carries `request_url_fingerprint`, never the URL - query
strings carry api keys. So "did this request go to the authorized authority"
is answered by recomputing the fingerprint of the registry's declared
`source_url` and comparing. A request to a different host produces a different
fingerprint, which is the property the host check needs.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_live_attempt_authorization_v1"

LIVE = "live"
HERMETIC = "hermetic"

#: Every linkage a live attempt must satisfy. Named so a refusal says which
#: one failed rather than reporting a bare false.
REQUIRED_LINKAGES: tuple[str, ...] = (
    "transport_is_live",
    "authorized_source_id_present",
    "source_is_in_the_authorized_set",
    "source_id_matches_authorization",
    "authorization_is_approved",
    "live_fetch_opt_in_exists",
    "request_authority_matches",
    "proof_linkage_is_valid",
)

NOT_IMPLIED: tuple[str, ...] = (
    "a live transport kind is not an authorization",
    "an authorized_source_id that names nothing recorded is not an authorization",
    "this reads recorded evidence; it permits no request",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def classify_live_attempt(
    attempt: dict[str, Any] | None = None,
    *,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Classify one attempt row. Returns the linkages, never a bare boolean."""
    row = attempt or {}
    measured: dict[str, bool] = dict.fromkeys(REQUIRED_LINKAGES, False)
    notes: dict[str, Any] = {}

    kind = str(row.get("transport_kind") or "").strip().lower()
    measured["transport_is_live"] = kind == LIVE

    if kind != LIVE:
        # Not a live attempt at all. Hermetic rows are not classified here and
        # are not unauthorized; the caller separates the two.
        return _result(row=row, measured=measured, notes=notes, is_live=False)

    source_id = str(row.get("source_id") or "").strip()
    authorized_id = str(row.get("authorized_source_id") or "").strip()
    measured["authorized_source_id_present"] = bool(authorized_id)
    measured["source_id_matches_authorization"] = bool(
        source_id and authorized_id and source_id == authorized_id
    )

    # Gate 166B: derived from the signed rows, not from a constant. Without a
    # connection nothing can be derived and nothing is authorized - which is
    # the same answer the constant gave for an unknown id, reached honestly.
    try:
        from nativeforge.services.source_authority_service import (
            derive_authorized_source_ids,
        )

        derived = derive_authorized_source_ids(
            connection=connection, organization_id=organization_id
        )
        measured["source_is_in_the_authorized_set"] = authorized_id in derived
        notes["authorized_set"] = sorted(derived)
        notes["authorized_set_derived_from"] = (
            "nf_source_authorization_decisions + nf_active_opportunity_sources"
        )
    except Exception as exc:  # noqa: BLE001 - an underivable set authorizes nothing
        notes["authorized_set_error"] = type(exc).__name__

    # A claimed proof needs a persisted payload and a hash. Checked from the
    # row, because a proof that names no bytes is not a proof.
    claims_proof = bool(row.get("execution_proof_available"))
    measured["proof_linkage_is_valid"] = bool(
        not claims_proof
        or (row.get("raw_payload_persisted") and row.get("raw_payload_sha256"))
    )

    # The remaining three need recorded evidence, so they need a connection.
    # Without one nothing is verifiable and nothing is authorized.
    if connection is None or not authorized_id:
        notes["unverifiable"] = (
            "no connection supplied"
            if connection is None
            else ("no authorized_source_id on the row")
        )
        return _result(row=row, measured=measured, notes=notes, is_live=True)

    # The three signed decisions, read DIRECTLY from the decision table.
    #
    # An earlier version asked `authorize_source_for_live_access`, which
    # resolves eleven facts - one of which is `collector_status`, which asks
    # the capability service, which builds the execution-envelope health,
    # which reads `count_attempts`, which is where this classifier is called
    # from. That recursion hung rather than crashing: a hang in a counter that
    # health lanes call on every read.
    #
    # Reading the decisions directly is cycle-free and closer to the evidence.
    # It deliberately does not re-ask the resolver: whether the runtime can
    # operate right NOW is a different question from whether the decisions
    # behind this recorded attempt were signed.
    try:
        from nativeforge.repositories.source_authorization_decision_repository import (
            HUMAN_REVIEW,
            TERMS,
            get_decision,
        )

        unsigned: list[str] = []
        for kind in (TERMS, HUMAN_REVIEW):
            found = get_decision(
                connection=connection,
                organization_id=organization_id,
                source_id=authorized_id,
                decision_kind=kind,
            )
            entry = found.get("decision") or {}
            if not (
                entry.get("decision") == "approved"
                and entry.get("reviewed_by")
                and entry.get("reviewed_at")
            ):
                unsigned.append(kind)

        # Activation is an ACTIVATION ROW, not a decision kind: Gate 162 put it
        # in `nf_active_opportunity_sources` with its own approver and artifact.
        activation_signed = _activation_is_signed(
            connection=connection,
            organization_id=organization_id,
            source_id=authorized_id,
        )
        if not activation_signed:
            unsigned.append("activation")

        measured["authorization_is_approved"] = not unsigned
        notes["decision_facts_signed"] = not unsigned
        if unsigned:
            notes["unsigned_or_missing_decisions"] = sorted(unsigned)
    except Exception as exc:  # noqa: BLE001
        notes["authorization_error"] = type(exc).__name__

    try:
        from nativeforge.services.source_live_fetch_opt_in_service import (
            is_live_fetch_opted_in,
        )

        measured["live_fetch_opt_in_exists"] = bool(
            is_live_fetch_opted_in(
                connection=connection,
                organization_id=organization_id,
                source_id=authorized_id,
            )
        )
    except Exception as exc:  # noqa: BLE001
        notes["opt_in_error"] = type(exc).__name__

    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )
        from nativeforge.services.source_raw_payload_persistence_service import (
            fingerprint_url,
        )

        declared = str(
            (load_registry_rows().get(authorized_id) or {}).get("source_url") or ""
        )
        expected = fingerprint_url(declared)
        observed = str(row.get("request_url_fingerprint") or "").strip()
        measured["request_authority_matches"] = bool(
            expected and observed and expected == observed
        )
        notes["request_fingerprint_matches_the_declared_endpoint"] = bool(
            expected and observed and expected == observed
        )
        if expected and observed and expected != observed:
            notes["fingerprint_mismatch"] = True
    except Exception as exc:  # noqa: BLE001
        notes["authority_error"] = type(exc).__name__

    return _result(row=row, measured=measured, notes=notes, is_live=True)


def _activation_is_signed(
    *, connection: Any, organization_id: Any, source_id: str
) -> bool:
    """Is there an activation row for this source, signed and attributable?

    Joined on the STABLE `source_id` that migration 0049 added, never on the
    display name: Gate 163A made a fact arriving through the legacy name join
    a named invariant failure.
    """
    try:
        import sqlalchemy as sa

        row = (
            connection.execute(
                sa.text(
                    "SELECT activation_approved_by, activation_approved_at, "
                    "activation_approval_artifact_id "
                    "FROM nf_active_opportunity_sources "
                    "WHERE organization_id = :org AND source_id = :src"
                ),
                {
                    "org": str(organization_id).replace("-", ""),
                    "src": str(source_id),
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            # Postgres stores the uuid with dashes; sqlite without. Try both
            # rather than reporting "no activation" because the key format
            # differed.
            row = (
                connection.execute(
                    sa.text(
                        "SELECT activation_approved_by, activation_approved_at, "
                        "activation_approval_artifact_id "
                        "FROM nf_active_opportunity_sources "
                        "WHERE source_id = :src"
                    ),
                    {"src": str(source_id)},
                )
                .mappings()
                .first()
            )
        if row is None:
            return False
        return bool(
            row["activation_approved_by"]
            and row["activation_approved_at"]
            and row["activation_approval_artifact_id"]
        )
    except Exception:  # noqa: BLE001 - an unreadable activation is not one
        return False


def _result(
    *,
    row: dict[str, Any],
    measured: dict[str, bool],
    notes: dict[str, Any],
    is_live: bool,
) -> dict[str, Any]:
    unmet = sorted(name for name in REQUIRED_LINKAGES if not measured[name])
    authorized = is_live and not unmet
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "attempt_id": row.get("attempt_id"),
            "source_id": row.get("source_id"),
            "transport_kind": row.get("transport_kind"),
            "is_live": bool(is_live),
            "authorized": bool(authorized),
            # A live row that is not authorized. The counter that must stay
            # zero counts exactly these.
            "unauthorized": bool(is_live and not authorized),
            "measured": measured,
            "required_linkages": list(REQUIRED_LINKAGES),
            "unmet_linkages": unmet,
            "notes": notes,
            "live_is_not_sufficient": (
                "a live transport kind is the thing that needs justifying, "
                "not the justification"
            ),
            "not_implied": list(NOT_IMPLIED),
        }
    )


def classify_live_attempts(
    attempts: list[dict[str, Any]] | None = None,
    *,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Classify many, and report the three counts the lanes need."""
    rows = list(attempts or [])
    classified = [
        classify_live_attempt(
            row, connection=connection, organization_id=organization_id
        )
        for row in rows
    ]
    live = [entry for entry in classified if entry["is_live"]]
    authorized = [entry for entry in live if entry["authorized"]]
    unauthorized = [entry for entry in live if entry["unauthorized"]]

    # The named sub-counts FIX 3 asks for, each derived from the linkage that
    # failed rather than from a difference of totals.
    unsigned = [
        entry
        for entry in live
        if not entry["measured"].get("authorization_is_approved")
    ]
    mismatched = [
        entry
        for entry in live
        if not entry["measured"].get("source_id_matches_authorization")
        or not entry["measured"].get("request_authority_matches")
    ]
    outside = [
        entry
        for entry in live
        if not entry["measured"].get("source_is_in_the_authorized_set")
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "attempts_classified": len(classified),
            "live_attempts": len(live),
            "authorized_live_attempts": len(authorized),
            "unauthorized_live_attempts": len(unauthorized),
            "unsigned_live_attempts": len(unsigned),
            "source_mismatch_live_attempts": len(mismatched),
            "live_rows_outside_authorized_set": len(outside),
            "authorized_attempt_ids": sorted(
                str(entry["attempt_id"]) for entry in authorized
            ),
            "unauthorized_attempt_ids": sorted(
                str(entry["attempt_id"]) for entry in unauthorized
            ),
            "unauthorized_detail": [
                {
                    "attempt_id": entry["attempt_id"],
                    "source_id": entry["source_id"],
                    "unmet_linkages": entry["unmet_linkages"],
                }
                for entry in unauthorized
            ],
        }
    )


def live_attempt_invariant_failures(summary: dict[str, Any]) -> list[str]:
    """The safety properties, after the world-state conversion.

    `live_attempts == 0` was the pre-live assertion. These are what replaced
    it, and none of them is satisfied by a nonzero live count alone.
    """
    fails: list[str] = []

    if summary.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for counter in (
        "unauthorized_live_attempts",
        "unsigned_live_attempts",
        "source_mismatch_live_attempts",
        "live_rows_outside_authorized_set",
    ):
        value = int(summary.get(counter) or 0)
        if value:
            fails.append(f"{counter}={value}")

    # authorized + unauthorized must account for every live attempt, or one of
    # them is being computed rather than classified.
    live = int(summary.get("live_attempts") or 0)
    authorized = int(summary.get("authorized_live_attempts") or 0)
    unauthorized = int(summary.get("unauthorized_live_attempts") or 0)
    if authorized + unauthorized != live:
        fails.append(
            f"live_attempts_unaccounted_for:{authorized}+{unauthorized}!={live}"
        )

    # An unauthorized count with no detail is one nobody can act on.
    if unauthorized and not summary.get("unauthorized_detail"):
        fails.append("unauthorized_live_attempts_without_detail")

    return sorted(set(fails))
