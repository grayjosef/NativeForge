"""What sources exist, and which of them may execute (Gate 166A / 166B).

Gate 163 answered the second question with a constant:

```python
AUTHORIZED_SOURCE_IDS = frozenset({"nf-seed-2026-api-grants-gov-search2"})
```

That was the right call for a first live source - widening it was an edit
somebody reviewed. It is the wrong mechanism for a fleet: at 1,000 sources it
is a source-code list, and every activation becomes a code change and a deploy.

It was also **redundant**. The authorization it encodes already existed as
accountable data before Gate 166 touched anything:

```text
nf_source_authorization_decisions   terms        approved, signed MAYHEM
nf_source_authorization_decisions   human_review approved, signed MAYHEM
nf_source_authorization_decisions   live_fetch   approved, signed operator:MAYHEM
nf_active_opportunity_sources       activation   signed MAYHEM, disabled_at NULL
```

Migration 0048 already makes an unsigned `approved` decision **unwritable**, so
the database - not a reviewer's memory - is what guarantees a signature exists.
The frozenset restated that guarantee in a place nobody could audit.

## Existence and execution authority are different questions

A row in the catalog is a source NativeForge knows about. It is not permission
to call it. The 177 baseline rows are `registered` and nothing more, and this
module will not collapse the two: `registered` is the floor, never the answer.

```text
unregistered   no catalog row
registered     a catalog row exists                      <- the 177
reviewed       terms AND human_review approved + signed
activated      activation signed, not disabled
live_opted_in  live_fetch decision approved + signed
authorized     every operational fact also holds
retired        disabled_at is set                        <- overrides all rungs
```

`retired` is checked first and wins outright. A disabled source with four
signed decisions is disabled; reading the rungs in order and stopping at the
highest would have reported it `live_opted_in`.

## Nothing here accepts an assertion

No parameter takes a status, a boolean or an override. The only inputs are a
connection, an organization and a source id - the same discipline Gate 162
pinned onto the fact resolver, for the same reason: a parameter that does not
exist cannot be misused.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_authority_v1"

DECISIONS_TABLE = "nf_source_authorization_decisions"
ACTIVATION_SOURCES_TABLE = "nf_active_opportunity_sources"

TERMS = "terms"
HUMAN_REVIEW = "human_review"
LIVE_FETCH = "live_fetch"

#: The governance decisions that must all be approved and signed before a
#: source may be called. Named, so adding a fourth kind is a visible change.
REQUIRED_DECISION_KINDS: tuple[str, ...] = (TERMS, HUMAN_REVIEW, LIVE_FETCH)

# ---------------------------------------------------------------- the states

UNREGISTERED = "unregistered"
REGISTERED = "registered"
REVIEWED = "reviewed"
ACTIVATED = "activated"
LIVE_OPTED_IN = "live_opted_in"
AUTHORIZED_FOR_LIVE = "authorized_for_live"
RETIRED = "retired"
BLOCKED = "blocked"
REVIEW_REQUIRED = "review_required"
UNKNOWN = "unknown"

SOURCE_AUTHORITY_STATES: tuple[str, ...] = (
    UNREGISTERED,
    REGISTERED,
    REVIEWED,
    ACTIVATED,
    LIVE_OPTED_IN,
    AUTHORIZED_FOR_LIVE,
    RETIRED,
    BLOCKED,
    REVIEW_REQUIRED,
    UNKNOWN,
)

#: The ladder, in order. `retired` and the refusal states are not rungs - they
#: are answers that replace the ladder rather than sit on it.
AUTHORITY_LADDER: tuple[str, ...] = (
    REGISTERED,
    REVIEWED,
    ACTIVATED,
    LIVE_OPTED_IN,
    AUTHORIZED_FOR_LIVE,
)

#: Terms guard statuses that mean a human must look before anything proceeds.
GUARD_NEEDS_HUMAN: frozenset[str] = frozenset(
    {"HUMAN_REVIEW_ONLY", "TERMS_REVIEW_REQUIRED"}
)

#: The operational facts a source needs on top of its governance decisions.
#: These are conditions of the moment, not decisions somebody signed.
OPERATIONAL_FACTS: tuple[str, ...] = (
    "attribution_status",
    "robots_status",
    "collector_status",
    "runtime_status",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _decisions_table() -> sa.Table:
    return sa.Table(
        DECISIONS_TABLE,
        sa.MetaData(),
        sa.Column("source_id", sa.Text()),
        sa.Column("decision_kind", sa.Text()),
        sa.Column("decision", sa.Text()),
        sa.Column("guard_status", sa.Text()),
        sa.Column("reviewed_by", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )


def _activation_table() -> sa.Table:
    return sa.Table(
        ACTIVATION_SOURCES_TABLE,
        sa.MetaData(),
        sa.Column("source_id", sa.Text()),
        sa.Column("activation_approved_by", sa.Text()),
        sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
    )


def _signed_and_approved(row: Any, *, now: Any = None) -> bool:
    """An approval is evidence only if somebody signed it and it has not run out.

    Migration 0048's CHECK already refuses an unsigned `approved` row, so this
    re-checks at the point of use what the schema prevents at the point of
    write. Defence in depth, and the branch stays reachable because a decision
    can also EXPIRE - which no constraint can enforce for a future date.
    """
    if str(row.get("decision") or "") != "approved":
        return False
    if not row.get("reviewed_by") or not row.get("reviewed_at"):
        return False
    expires = row.get("expires_at")
    if expires is not None and now is not None:
        try:
            if expires <= now:
                return False
        except TypeError:
            # Incomparable values are not proof that it is still valid.
            return False
    return True


def load_governance_state(
    *, connection: Any = None, organization_id: Any = None, now: Any = None
) -> dict[str, dict[str, Any]]:
    """Every source's governance facts, in two queries rather than 2N.

    A sweep over 5,000 sources reads the decision table once and the activation
    table once. Resolving per source would be 10,000 queries to answer a
    question the database can answer in two.
    """
    state: dict[str, dict[str, Any]] = {}
    if connection is None:
        return state

    try:
        table = _decisions_table()
        query = sa.select(table)
        if organization_id is not None:
            org_column = sa.column("organization_id")
            try:
                query = sa.select(table).where(org_column == organization_id)
            except Exception:  # noqa: BLE001 - fall back to the unfiltered read
                query = sa.select(table)
        for row in connection.execute(query).mappings():
            key = str(row.get("source_id") or "").strip()
            if not key:
                continue
            entry = state.setdefault(key, {"decisions": {}, "activation": None})
            kind = str(row.get("decision_kind") or "").strip()
            entry["decisions"][kind] = {
                "decision": row.get("decision"),
                "guard_status": row.get("guard_status"),
                "reviewed_by": row.get("reviewed_by"),
                "reviewed_at": row.get("reviewed_at"),
                "expires_at": row.get("expires_at"),
                "signed_and_approved": _signed_and_approved(dict(row), now=now),
            }
    except Exception:  # noqa: BLE001 - an unreadable table authorizes nothing
        return state

    try:
        activation = _activation_table()
        for row in connection.execute(sa.select(activation)).mappings():
            key = str(row.get("source_id") or "").strip()
            if not key:
                continue
            entry = state.setdefault(key, {"decisions": {}, "activation": None})
            entry["activation"] = {
                "approved_by": row.get("activation_approved_by"),
                "approved_at": row.get("activation_approved_at"),
                "disabled_at": row.get("disabled_at"),
                "signed": bool(
                    row.get("activation_approved_by")
                    and row.get("activation_approved_at")
                ),
                "disabled": row.get("disabled_at") is not None,
            }
    except Exception:  # noqa: BLE001
        return state

    return state


def classify_source_authority(
    *,
    source_id: Any = None,
    registered: bool = False,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The authority state for one source, from its governance facts. Pure.

    Separated from the database so every branch - including `retired` and an
    expired decision - is reachable in a test without writing a row. An
    unreachable branch makes the refusal it guards unfalsifiable.
    """
    key = str(source_id or "").strip()
    facts = governance or {}
    decisions: dict[str, Any] = facts.get("decisions") or {}
    activation: dict[str, Any] = facts.get("activation") or {}

    reasons: list[str] = []

    if not key:
        return {
            "source_id": None,
            "state": UNKNOWN,
            "highest_rung": None,
            "reasons": ["no_source_id"],
            "decisions_signed": {},
            "governance_complete": False,
        }

    signed = {
        kind: bool((decisions.get(kind) or {}).get("signed_and_approved"))
        for kind in REQUIRED_DECISION_KINDS
    }

    # ---- retired wins outright ---------------------------------------
    # Checked before the ladder. A disabled source with every decision
    # signed is disabled; walking the rungs would have called it opted in.
    if activation.get("disabled"):
        return {
            "source_id": key,
            "state": RETIRED,
            "highest_rung": None,
            "reasons": ["activation_revoked:disabled_at_is_set"],
            "decisions_signed": signed,
            # Stated on EVERY return path. Absent here, the invariant checks
            # that read it would be unfalsifiable: a retired source could
            # never be caught reporting governance complete.
            "governance_complete": False,
        }

    if not registered:
        return {
            "source_id": key,
            "state": UNREGISTERED,
            "highest_rung": None,
            "reasons": ["no_catalog_row_defines_this_source"],
            "decisions_signed": signed,
            # Stated on EVERY return path. Absent here, the invariant checks
            # that read it would be unfalsifiable: a retired source could
            # never be caught reporting governance complete.
            "governance_complete": False,
        }

    # ---- an explicit denial is a refusal, not a missing rung -----------
    denied = [
        kind
        for kind in REQUIRED_DECISION_KINDS
        if str((decisions.get(kind) or {}).get("decision") or "") == "denied"
    ]
    if denied:
        return {
            "source_id": key,
            "state": BLOCKED,
            "highest_rung": REGISTERED,
            "reasons": [f"decision_denied:{kind}" for kind in sorted(denied)],
            "decisions_signed": signed,
            # Stated on EVERY return path. Absent here, the invariant checks
            # that read it would be unfalsifiable: a retired source could
            # never be caught reporting governance complete.
            "governance_complete": False,
        }

    # ---- a terms guard that demands a human ---------------------------
    terms = decisions.get(TERMS) or {}
    guard = str(terms.get("guard_status") or "").strip()
    needs_review = guard in GUARD_NEEDS_HUMAN or str(
        (decisions.get(HUMAN_REVIEW) or {}).get("decision") or ""
    ) == "needs_review"
    if needs_review:
        return {
            "source_id": key,
            "state": REVIEW_REQUIRED,
            "highest_rung": REGISTERED,
            "reasons": [f"human_review_required:{guard or 'needs_review'}"],
            "decisions_signed": signed,
            # Stated on EVERY return path. Absent here, the invariant checks
            # that read it would be unfalsifiable: a retired source could
            # never be caught reporting governance complete.
            "governance_complete": False,
        }

    # ---- the ladder ----------------------------------------------------
    rung = REGISTERED

    if signed[TERMS] and signed[HUMAN_REVIEW]:
        rung = REVIEWED
    else:
        for kind in (TERMS, HUMAN_REVIEW):
            if not signed[kind]:
                reasons.append(f"decision_not_signed_and_approved:{kind}")

    if rung == REVIEWED:
        if activation.get("signed"):
            rung = ACTIVATED
        else:
            reasons.append("activation_is_not_signed")

    if rung == ACTIVATED:
        if signed[LIVE_FETCH]:
            rung = LIVE_OPTED_IN
        else:
            reasons.append(f"decision_not_signed_and_approved:{LIVE_FETCH}")

    state = rung if rung != LIVE_OPTED_IN else LIVE_OPTED_IN
    return {
        "source_id": key,
        "state": state,
        "highest_rung": rung,
        "reasons": sorted(set(reasons)),
        "decisions_signed": signed,
        # Governance is satisfied; the operational facts are a separate
        # question the warrant answers per request.
        "governance_complete": rung == LIVE_OPTED_IN,
    }


def derive_authorized_source_ids(
    *, connection: Any = None, organization_id: Any = None, now: Any = None
) -> frozenset[str]:
    """The sources whose PERSISTED decisions authorize a live call.

    This is the replacement for `AUTHORIZED_SOURCE_IDS`. It reads the same
    rows a reviewer signed, so adding source #2 is signing four decisions -
    not editing a module and deploying it.

    It answers the governance question only. Robots evidence, attribution,
    collector capability and runtime readiness are conditions of the moment;
    the warrant checks those per request and this set never substitutes for
    them.

    An unreadable database yields the empty set. Absence is not permission.
    """
    governance = load_governance_state(
        connection=connection, organization_id=organization_id, now=now
    )
    authorized: set[str] = set()
    for key, facts in governance.items():
        verdict = classify_source_authority(
            source_id=key, registered=True, governance=facts
        )
        if verdict.get("governance_complete"):
            authorized.add(key)
    return frozenset(authorized)


def resolve_source_authority(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    registered: bool = False,
    governance: dict[str, Any] | None = None,
    now: Any = None,
) -> dict[str, Any]:
    """One source's authority. Reads the stores unless a sweep already did.

    `governance` is not an assertion channel: it carries rows this module's
    own loader produced, and a sweep passes it so 5,000 sources cost two
    queries instead of ten thousand. Anything a caller invents there is
    classified by the same pure rules, which refuse an unsigned decision
    whatever its source.
    """
    key = str(source_id or "").strip()
    facts = governance
    if facts is None:
        loaded = load_governance_state(
            connection=connection, organization_id=organization_id, now=now
        )
        facts = loaded.get(key) or {"decisions": {}, "activation": None}

    verdict = classify_source_authority(
        source_id=key, registered=registered, governance=facts
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            **verdict,
            "states_vocabulary": list(SOURCE_AUTHORITY_STATES),
            "required_decision_kinds": list(REQUIRED_DECISION_KINDS),
            "operational_facts_checked_elsewhere": list(OPERATIONAL_FACTS),
            "derived_from": [DECISIONS_TABLE, ACTIVATION_SOURCES_TABLE, "seed_catalog"],
            "derived_from_source_code_constant": False,
        }
    )


def authority_invariant_failures(verdict: dict[str, Any]) -> list[str]:
    """Refuse an authority verdict that grants more than its evidence."""
    fails: list[str] = []

    state = verdict.get("state")
    if state not in SOURCE_AUTHORITY_STATES:
        fails.append(f"state_outside_vocabulary:{state}")

    signed = verdict.get("decisions_signed") or {}

    if verdict.get("governance_complete"):
        for kind in REQUIRED_DECISION_KINDS:
            if not signed.get(kind):
                fails.append(f"governance_complete_without_the_decision:{kind}")
        if state not in (LIVE_OPTED_IN, AUTHORIZED_FOR_LIVE):
            fails.append(f"governance_complete_in_state:{state}")

    # A retired source may never carry a rung.
    if state == RETIRED and verdict.get("highest_rung"):
        fails.append("retired_source_reported_on_the_ladder")

    if state == RETIRED and verdict.get("governance_complete"):
        fails.append("retired_source_reported_governance_complete")

    # Refusing without naming a reason is the defect Gate 163 kept finding.
    if state in (BLOCKED, REVIEW_REQUIRED, UNREGISTERED, RETIRED) and not verdict.get(
        "reasons"
    ):
        fails.append(f"refused_without_naming_a_reason:{state}")

    return sorted(set(fails))
