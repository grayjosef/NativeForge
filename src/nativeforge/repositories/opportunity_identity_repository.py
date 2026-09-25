"""Persisting identity: blocking keys, relationships, candidates (Gate 169K-P).

Three stores, three jobs:

```text
blocking keys   put plausibly-related opportunities in one bucket
relationships   record what was decided, and by whom
candidates      hold what could not be decided without a human
```

## Candidate generation is a key lookup, never a scan

```python
SELECT canonical_id FROM nf_opportunity_blocking_keys
WHERE (key_kind, key_value) IN (this record's keys)
```

The index on `(key_kind, key_value)` makes that a seek per key. The candidate
set is therefore a function of how many opportunities share a bucket - not of
how many opportunities exist. Gate 169O measures that at 10,000 opportunities
rather than trusting the sentence above, and `CANDIDATE_CAP` bounds a
pathological bucket so one over-broad key cannot turn into a fleet scan by
accident.

## A merge is a row, so unmerging is deleting a row

Nothing here rewrites a `canonical_id`, moves an observation, or deletes a
version. `approve_merge` writes a SAME_AS relationship and designates a
primary for display; `revoke_relationship` marks it revoked with a signer and
a reason. Both canonical opportunities keep every observation, version and
provenance row they ever had, which is why Gate 169L can show that reversing a
merge loses nothing - there was never anywhere for the evidence to go.

## The database refuses what this module refuses

`record_relationship` will not write a fuzzy SAME_AS without a human
decision. Migration 0054's CHECK refuses the same thing at rest, so a future
caller who bypasses this module still cannot create one. Gate 164 established
the preference: make the bad state unrepresentable rather than detect it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_opportunity_identity_repository_v1"

CANONICAL = "nf_canonical_opportunities"
BLOCKING = "nf_opportunity_blocking_keys"
RELATIONSHIPS = "nf_opportunity_identity_relationships"
CANDIDATES = "nf_opportunity_identity_candidates"

#: A single blocking bucket wider than this is treated as non-discriminating
#: and truncated, with the truncation REPORTED. A key that matches thousands
#: of opportunities is not narrowing anything, and silently walking it would
#: reintroduce the scan this design exists to avoid.
CANDIDATE_CAP = 200

REVIEW_PENDING = "pending"
REVIEW_APPROVED_MERGE = "approved_merge"
REVIEW_REJECTED_MERGE = "rejected_merge"
REVIEW_MARKED_RELATED = "marked_related"
REVIEW_DEFERRED = "deferred"

REVIEW_STATES: tuple[str, ...] = (
    REVIEW_PENDING,
    REVIEW_APPROVED_MERGE,
    REVIEW_REJECTED_MERGE,
    REVIEW_MARKED_RELATED,
    REVIEW_DEFERRED,
)

#: The review actions Gate 169K names.
ACTION_APPROVE_MERGE = "APPROVE_MERGE"
ACTION_REJECT_MERGE = "REJECT_MERGE"
ACTION_MARK_RELATED = "MARK_RELATED"
ACTION_DEFER = "DEFER"

REVIEW_ACTIONS: dict[str, str] = {
    ACTION_APPROVE_MERGE: REVIEW_APPROVED_MERGE,
    ACTION_REJECT_MERGE: REVIEW_REJECTED_MERGE,
    ACTION_MARK_RELATED: REVIEW_MARKED_RELATED,
    ACTION_DEFER: REVIEW_DEFERRED,
}

DECIDED_DERIVED = "derived"
DECIDED_HUMAN = "human_review"

SETTLED_LAYERS: frozenset[str] = frozenset({"L1", "L2"})


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    joined = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _table(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


def _blocking_table() -> sa.Table:
    return _table(
        BLOCKING,
        sa.Column("canonical_id", sa.Text()),
        sa.Column("key_kind", sa.Text()),
        sa.Column("key_value", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _relationships_table() -> sa.Table:
    return _table(
        RELATIONSHIPS,
        sa.Column("relationship_id", sa.Text(), primary_key=True),
        sa.Column("from_canonical_id", sa.Text()),
        sa.Column("to_canonical_id", sa.Text()),
        sa.Column("relationship", sa.Text()),
        sa.Column("match_decision", sa.Text()),
        sa.Column("identity_layer", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("reasons_json", sa.Text()),
        sa.Column("decided_by", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("reviewer", sa.Text()),
        sa.Column("candidate_id", sa.Text()),
        sa.Column("primary_canonical_id", sa.Text()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", sa.Text()),
        sa.Column("revoked_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _candidates_table() -> sa.Table:
    return _table(
        CANDIDATES,
        sa.Column("candidate_id", sa.Text(), primary_key=True),
        sa.Column("canonical_a", sa.Text()),
        sa.Column("canonical_b", sa.Text()),
        sa.Column("proposed_relationship", sa.Text()),
        sa.Column("match_decision", sa.Text()),
        sa.Column("identity_layer", sa.Text()),
        sa.Column("confidence", sa.Float()),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("reasons_json", sa.Text()),
        sa.Column("review_state", sa.Text()),
        sa.Column("reviewed_by", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


# ------------------------------------------------------ blocking keys


def record_blocking_keys(
    *,
    connection: Any,
    canonical_id: Any,
    keys: list[dict[str, str]],
    now: Any = None,
) -> dict[str, Any]:
    """Register one opportunity's buckets. Idempotent on the primary key."""
    stamp = now or dt.datetime.now(dt.UTC)
    table = _blocking_table()
    key = str(canonical_id or "")
    if not key or not keys:
        return {"written": 0, "canonical_id": key or None}

    existing = {
        (str(row[0]), str(row[1]))
        for row in connection.execute(
            sa.select(table.c.key_kind, table.c.key_value).where(
                table.c.canonical_id == key
            )
        )
    }
    rows = [
        {
            "canonical_id": key,
            "key_kind": entry["key_kind"],
            "key_value": entry["key_value"],
            "created_at": stamp,
        }
        for entry in keys
        if (entry["key_kind"], entry["key_value"]) not in existing
    ]
    if rows:
        connection.execute(sa.insert(table), rows)
    return {"written": len(rows), "canonical_id": key}


def backfill_blocking_keys(
    *, connection: Any, limit: int = 100000, now: Any = None
) -> dict[str, Any]:
    """Register keys for canonical opportunities that have none.

    The write path builds keys when it CREATES an opportunity, which leaves
    every opportunity that existed before Gate 169 invisible to candidate
    generation - including the one real Grants.gov opportunity. Paying a read
    per observation to notice that would undo Gate 168's work, so the gap is
    closed by a backfill instead.

    Set-oriented and idempotent: it selects the canonical rows with no key and
    inserts in bulk, so running it twice writes nothing the second time.
    """
    from nativeforge.services.cross_source_identity_service import (
        build_blocking_keys,
        describe_identity,
    )

    stamp = now or dt.datetime.now(dt.UTC)
    blocking = _blocking_table()

    canonical = _table(
        CANONICAL,
        sa.Column("canonical_id", sa.Text()),
        sa.Column("normalized_opportunity_number", sa.Text()),
        sa.Column("doc_type", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("funder_agency_code", sa.Text()),
        sa.Column("funder_agency_name", sa.Text()),
        sa.Column("surrogate_opportunity_id", sa.Text()),
    )

    missing = (
        connection.execute(
            sa.select(canonical)
            .where(
                ~canonical.c.canonical_id.in_(
                    sa.select(blocking.c.canonical_id).distinct()
                )
            )
            .limit(limit)
        )
        .mappings()
        .all()
    )

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in missing:
        described = describe_identity(
            # The canonical row stores the NORMALIZED number, which
            # `normalize_opportunity_number` leaves unchanged - so passing it
            # back through is safe rather than double-normalizing.
            opportunity_number=row["normalized_opportunity_number"],
            doc_type=row["doc_type"],
            agency_code=row["funder_agency_code"],
            agency_name=row["funder_agency_name"],
            title=row["title"],
            source_record_id=row["surrogate_opportunity_id"],
        )
        for entry in build_blocking_keys(described):
            triple = (
                str(row["canonical_id"]),
                entry["key_kind"],
                entry["key_value"],
            )
            if triple in seen:
                continue
            seen.add(triple)
            rows.append(
                {
                    "canonical_id": str(row["canonical_id"]),
                    "key_kind": entry["key_kind"],
                    "key_value": entry["key_value"],
                    "created_at": stamp,
                }
            )

    if rows:
        connection.execute(sa.insert(blocking), rows)
        connection.commit()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "opportunities_without_keys": len(missing),
            "keys_written": len(rows),
            "is_idempotent": True,
        }
    )


def generate_candidates(
    *,
    connection: Any,
    keys: list[dict[str, str]],
    exclude_canonical_id: Any = None,
    cap: int = CANDIDATE_CAP,
) -> dict[str, Any]:
    """The bounded candidate set for one record.

    Returns the candidates AND the per-key bucket sizes, because "candidate
    generation is bounded" is only a claim until somebody can see how wide the
    widest bucket was.
    """
    from nativeforge.services.cross_source_identity_service import (
        GENERATIVE_KEY_KINDS,
    )

    table = _blocking_table()
    exclude = str(exclude_canonical_id or "")
    per_key: dict[str, int] = {}
    candidates: dict[str, list[str]] = {}
    truncated: list[str] = []
    skipped: list[str] = []

    for entry in keys or []:
        kind = entry["key_kind"]
        value = entry["key_value"]
        # Only selective keys generate candidates. A funder-and-year bucket
        # grows with the corpus, so walking it would be the fleet scan this
        # lookup exists to replace - measured at 201 candidates per probe on a
        # 10,000-opportunity graph before this restriction.
        if kind not in GENERATIVE_KEY_KINDS:
            skipped.append(kind)
            continue
        rows = (
            connection.execute(
                sa.select(table.c.canonical_id)
                .where(sa.and_(table.c.key_kind == kind, table.c.key_value == value))
                # One more than the cap, so truncation is detected rather than
                # inferred from a suspiciously round number.
                .limit(cap + 1)
            )
            .scalars()
            .all()
        )
        found = [str(r) for r in rows if str(r) != exclude]
        per_key[f"{kind}:{value[:24]}"] = len(found)
        if len(found) > cap:
            truncated.append(kind)
            found = found[:cap]
        for canonical_id in found:
            candidates.setdefault(canonical_id, []).append(kind)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_ids": sorted(candidates),
            "candidate_count": len(candidates),
            "matched_key_kinds_by_candidate": {
                k: sorted(set(v)) for k, v in sorted(candidates.items())
            },
            "bucket_sizes": per_key,
            "widest_bucket": max(per_key.values()) if per_key else 0,
            "keys_probed": len(per_key),
            "keys_supplied": len(keys or []),
            "non_generative_keys_skipped": sorted(set(skipped)),
            "truncated_key_kinds": sorted(set(truncated)),
            "cap": cap,
            "lookup_is_indexed_equality": True,
        }
    )


# ------------------------------------------------------ relationships


class IdentityWriteRefused(RuntimeError):
    """Raised instead of writing something the model must not contain."""

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


def record_relationship(
    *,
    connection: Any,
    from_canonical_id: Any,
    to_canonical_id: Any,
    relationship: Any,
    match_decision: Any,
    identity_layer: Any,
    evidence: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
    confidence: Any = None,
    decided_by: str = DECIDED_DERIVED,
    reviewer: Any = None,
    candidate_id: Any = None,
    primary_canonical_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Record one identity relationship. Refuses a fuzzy automatic merge.

    The refusal is duplicated in migration 0054's CHECK on purpose: this
    function is the path callers use, and the constraint is what protects the
    table from a caller who does not.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    left = str(from_canonical_id or "")
    right = str(to_canonical_id or "")
    layer = str(identity_layer or "")
    kind = str(relationship or "")

    refusals: list[str] = []
    if not left or not right:
        refusals.append("a_relationship_needs_two_opportunities")
    if left == right:
        refusals.append("an_opportunity_is_not_related_to_itself")
    if kind == "SAME_AS" and layer not in SETTLED_LAYERS:
        if decided_by != DECIDED_HUMAN:
            refusals.append(f"a_same_as_at_{layer}_requires_a_human_decision")
    if decided_by == DECIDED_HUMAN and not str(reviewer or "").strip():
        refusals.append("a_human_decision_must_name_the_human")
    if refusals:
        raise IdentityWriteRefused(sorted(set(refusals)))

    table = _relationships_table()
    relationship_id = _digest(left, right, kind)

    existing = (
        connection.execute(
            sa.select(table).where(table.c.relationship_id == relationship_id)
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "relationship_id": relationship_id,
                "written": False,
                "already_present": True,
                "revoked": existing["revoked_at"] is not None,
            }
        )

    connection.execute(
        sa.insert(table).values(
            relationship_id=relationship_id,
            from_canonical_id=left,
            to_canonical_id=right,
            relationship=kind,
            match_decision=str(match_decision or ""),
            identity_layer=layer,
            confidence=confidence,
            evidence_json=json.dumps(evidence or {}, sort_keys=True, default=str),
            reasons_json=json.dumps(sorted(reasons or []), sort_keys=True),
            decided_by=decided_by,
            decided_at=stamp,
            reviewer=str(reviewer) if reviewer else None,
            candidate_id=str(candidate_id) if candidate_id else None,
            primary_canonical_id=(
                str(primary_canonical_id) if primary_canonical_id else None
            ),
            created_at=stamp,
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "relationship_id": relationship_id,
            "written": True,
            "already_present": False,
            "relationship": kind,
            "identity_layer": layer,
            "decided_by": decided_by,
        }
    )


def revoke_relationship(
    *,
    connection: Any,
    relationship_id: Any,
    revoked_by: Any,
    reason: Any,
    now: Any = None,
) -> dict[str, Any]:
    """Reverse a relationship. Nothing is deleted and nothing moves.

    This is the whole of Gate 169L's unmerge: because a merge never rewrote a
    canonical id, reversing it cannot orphan an observation, a version, a
    provenance row or a tenant reference. The revocation is attributed,
    because an unmerge nobody signed is as unaccountable as a merge nobody
    signed.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    if not str(revoked_by or "").strip() or not str(reason or "").strip():
        raise IdentityWriteRefused(["a_revocation_must_name_who_and_why"])

    table = _relationships_table()
    result = connection.execute(
        sa.update(table)
        .where(
            sa.and_(
                table.c.relationship_id == str(relationship_id),
                table.c.revoked_at.is_(None),
            )
        )
        .values(
            revoked_at=stamp,
            revoked_by=str(revoked_by),
            revoked_reason=str(reason),
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "relationship_id": str(relationship_id),
            "revoked": int(result.rowcount or 0) == 1,
            "revoked_by": str(revoked_by),
            "reason": str(reason),
            "rows_deleted": 0,
            "evidence_moved": False,
        }
    )


# -------------------------------------------------------- candidates


def record_candidate(
    *,
    connection: Any,
    canonical_a: Any,
    canonical_b: Any,
    proposed_relationship: Any,
    match_decision: Any,
    identity_layer: Any,
    evidence: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
    confidence: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Queue a pair for human review. Changes no canonical identity.

    The pair is ORDERED before it is stored, so (A,B) and (B,A) are one
    candidate. Without that, two sources observed in either order produce two
    review items for one question.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    left, right = sorted([str(canonical_a or ""), str(canonical_b or "")])
    if not left or not right or left == right:
        raise IdentityWriteRefused(["a_candidate_needs_two_distinct_opportunities"])

    table = _candidates_table()
    kind = str(proposed_relationship or "")
    candidate_id = _digest(left, right, kind)

    existing = (
        connection.execute(sa.select(table).where(table.c.candidate_id == candidate_id))
        .mappings()
        .first()
    )
    if existing is not None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "written": False,
                "already_present": True,
                "review_state": existing["review_state"],
            }
        )

    connection.execute(
        sa.insert(table).values(
            candidate_id=candidate_id,
            canonical_a=left,
            canonical_b=right,
            proposed_relationship=kind,
            match_decision=str(match_decision or ""),
            identity_layer=str(identity_layer or ""),
            confidence=confidence,
            evidence_json=json.dumps(evidence or {}, sort_keys=True, default=str),
            reasons_json=json.dumps(sorted(reasons or []), sort_keys=True),
            review_state=REVIEW_PENDING,
            created_at=stamp,
        )
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "written": True,
            "already_present": False,
            "review_state": REVIEW_PENDING,
            "canonical_a": left,
            "canonical_b": right,
        }
    )


def resolve_candidate(
    *,
    connection: Any,
    candidate_id: Any,
    action: Any,
    reviewer: Any,
    notes: Any = None,
    primary_canonical_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """Apply a human decision to a candidate.

    `APPROVE_MERGE` writes the SAME_AS relationship the candidate proposed,
    carrying `decided_by=human_review` and the reviewer's name - which is the
    only way a probabilistic-layer merge can exist at all.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    name = str(action or "").strip().upper()
    if name not in REVIEW_ACTIONS:
        raise IdentityWriteRefused([f"unknown_review_action:{name or 'missing'}"])
    if not str(reviewer or "").strip():
        raise IdentityWriteRefused(["a_review_decision_must_name_the_reviewer"])

    table = _candidates_table()
    candidate = (
        connection.execute(
            sa.select(table).where(table.c.candidate_id == str(candidate_id))
        )
        .mappings()
        .first()
    )
    if candidate is None:
        raise IdentityWriteRefused([f"no_such_candidate:{candidate_id}"])

    state = REVIEW_ACTIONS[name]
    connection.execute(
        sa.update(table)
        .where(table.c.candidate_id == str(candidate_id))
        .values(
            review_state=state,
            reviewed_by=str(reviewer),
            reviewed_at=stamp,
            review_notes=str(notes) if notes else None,
        )
    )

    written: dict[str, Any] | None = None
    if name in (ACTION_APPROVE_MERGE, ACTION_MARK_RELATED):
        relationship = (
            str(candidate["proposed_relationship"])
            if name == ACTION_APPROVE_MERGE
            else "RELATED_TO"
        )
        try:
            reasons = json.loads(candidate["reasons_json"] or "[]")
        except Exception:  # noqa: BLE001
            reasons = []
        try:
            evidence = json.loads(candidate["evidence_json"] or "{}")
        except Exception:  # noqa: BLE001
            evidence = {}
        written = record_relationship(
            connection=connection,
            from_canonical_id=candidate["canonical_a"],
            to_canonical_id=candidate["canonical_b"],
            relationship=relationship,
            match_decision=candidate["match_decision"],
            identity_layer=candidate["identity_layer"],
            evidence=evidence,
            reasons=reasons,
            confidence=candidate["confidence"],
            decided_by=DECIDED_HUMAN,
            reviewer=str(reviewer),
            candidate_id=str(candidate_id),
            primary_canonical_id=primary_canonical_id or candidate["canonical_a"],
            now=stamp,
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": str(candidate_id),
            "action": name,
            "review_state": state,
            "reviewer": str(reviewer),
            "relationship_written": written,
        }
    )


# ------------------------------------------------------- reading


def describe_identity_graph(
    *, connection: Any, canonical_id: Any, include_revoked: bool = False
) -> dict[str, Any]:
    """Every relationship touching one opportunity, in both directions."""
    table = _relationships_table()
    key = str(canonical_id or "")
    where = sa.or_(table.c.from_canonical_id == key, table.c.to_canonical_id == key)
    if not include_revoked:
        where = sa.and_(where, table.c.revoked_at.is_(None))

    rows = [
        dict(row)
        for row in connection.execute(sa.select(table).where(where)).mappings().all()
    ]
    by_kind: dict[str, list[str]] = {}
    for row in rows:
        other = (
            row["to_canonical_id"]
            if row["from_canonical_id"] == key
            else row["from_canonical_id"]
        )
        by_kind.setdefault(str(row["relationship"]), []).append(str(other))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "canonical_id": key,
            "relationships": rows,
            "relationship_count": len(rows),
            "related_by_kind": {k: sorted(set(v)) for k, v in sorted(by_kind.items())},
            # What a customer may be told, kept separate from what is merely
            # proposed. Gate 169Q: a provisional merge is never settled truth.
            "settled_same_as": sorted(
                {
                    str(
                        row["to_canonical_id"]
                        if row["from_canonical_id"] == key
                        else row["from_canonical_id"]
                    )
                    for row in rows
                    if row["relationship"] == "SAME_AS"
                }
            ),
            "includes_revoked": include_revoked,
        }
    )


# --------------------------------------------------------------------
# Logical identity resolution
#
# L1 preserves source truth: a forecast and the posting it became are two
# rows, because overwriting one with the other would destroy the transition.
# The PRODUCT must still understand that they are one real opportunity.
#
# This is the single place that turns an L1 canonical_id into the logical
# opportunity a customer acts on. Thirty services reference canonical_id; none
# of them should learn to interpret a relationship graph, because thirty
# interpretations is thirty chances to disagree.
# --------------------------------------------------------------------

#: Relationships that mean "these are one opportunity, act on the primary".
#: RELATED_TO, RECURRENCE_OF and REPUBLISHED_FROM deliberately do NOT collapse:
#: last year's programme cycle is a different grant with a different deadline.
RESOLVING_RELATIONSHIPS: frozenset[str] = frozenset({"SAME_AS", "FORECAST_OF"})

#: Resolution outcomes.
RESOLVED_SELF = "SELF"
RESOLVED_TO_PRIMARY = "RESOLVED_TO_PRIMARY"
RESOLVED_UNRESOLVED = "UNRESOLVED"
RESOLVED_CONFLICT = "CONFLICT"

#: A chain longer than this is a graph problem, not a deep lineage.
_MAX_RESOLUTION_DEPTH = 8


def resolve_logical_canonical_ids(
    *, connection: Any, canonical_ids: Any
) -> dict[str, Any]:
    """Map each L1 canonical_id onto the logical opportunity it belongs to.

    Batched on purpose. A customer feed holding N opportunities must not issue
    N relationship queries, so this walks the graph in rounds - one query per
    round, and depth is 1 for every pair this system currently produces.

    Never guesses. A relationship that does not name its primary, a node with
    two different primaries, or a cycle all resolve to the node itself and are
    reported as failures rather than settled quietly.
    """
    table = _relationships_table()
    wanted = [str(c) for c in (canonical_ids or []) if str(c or "")]
    resolutions: dict[str, dict[str, Any]] = {
        key: {
            "canonical_id": key,
            "logical_canonical_id": key,
            "primary_canonical_id": None,
            "status": RESOLVED_SELF,
            "relationship": None,
            "reason": "no_relationship",
        }
        for key in wanted
    }
    failures: list[str] = []
    query_count = 0
    edges: dict[str, dict[str, Any]] = {}

    frontier = set(wanted)
    seen: set[str] = set()
    depth = 0
    while frontier and depth < _MAX_RESOLUTION_DEPTH:
        depth += 1
        seen |= frontier
        where = sa.and_(
            sa.or_(
                table.c.from_canonical_id.in_(sorted(frontier)),
                table.c.to_canonical_id.in_(sorted(frontier)),
            ),
            table.c.revoked_at.is_(None),
            table.c.relationship.in_(sorted(RESOLVING_RELATIONSHIPS)),
        )
        rows = connection.execute(sa.select(table).where(where)).mappings().all()
        query_count += 1

        next_frontier: set[str] = set()
        for row in rows:
            a = str(row["from_canonical_id"] or "")
            b = str(row["to_canonical_id"] or "")
            primary = str(row["primary_canonical_id"] or "")
            kind = str(row["relationship"] or "")
            if not primary:
                # A collapsing relationship that does not say which side is
                # current cannot be applied. Applying it would be a guess
                # about which record the customer should act on.
                failures.append(f"{kind.lower()}_without_primary:{a}|{b}")
                continue
            if primary not in (a, b):
                failures.append(f"primary_is_not_an_endpoint:{primary}")
                continue
            other = b if primary == a else a
            existing = edges.get(other)
            if existing and existing["primary"] != primary:
                # Two relationships disagree about where this record belongs.
                failures.append(
                    f"conflicting_primaries_for:{other}|{existing['primary']}|{primary}"
                )
                edges[other] = {"primary": other, "kind": kind, "conflict": True}
                continue
            edges[other] = {"primary": primary, "kind": kind, "conflict": False}
            if primary not in seen:
                next_frontier.add(primary)
        frontier = next_frontier

    if frontier:
        failures.append(f"resolution_depth_exceeded:{sorted(frontier)}")

    for key in wanted:
        hops = 0
        current = key
        chain: list[str] = [current]
        kind_used: str | None = None
        conflicted = False
        while current in edges and hops < _MAX_RESOLUTION_DEPTH:
            edge = edges[current]
            if edge.get("conflict"):
                conflicted = True
                break
            nxt = str(edge["primary"])
            kind_used = str(edge["kind"])
            if nxt == current:
                break
            if nxt in chain:
                failures.append(f"relationship_cycle:{'>'.join([*chain, nxt])}")
                conflicted = True
                break
            chain.append(nxt)
            current = nxt
            hops += 1

        if conflicted:
            resolutions[key].update(
                {
                    "status": RESOLVED_CONFLICT,
                    "logical_canonical_id": key,
                    "reason": "conflicting_or_cyclic_relationships",
                }
            )
        elif hops >= _MAX_RESOLUTION_DEPTH:
            failures.append(f"resolution_depth_exceeded:{key}")
            resolutions[key].update(
                {"status": RESOLVED_CONFLICT, "reason": "resolution_depth_exceeded"}
            )
        elif current != key:
            resolutions[key].update(
                {
                    "logical_canonical_id": current,
                    "primary_canonical_id": current,
                    "status": RESOLVED_TO_PRIMARY,
                    "relationship": kind_used,
                    "reason": f"resolved_via_{(kind_used or '').lower()}",
                }
            )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "resolutions": resolutions,
            "requested_count": len(wanted),
            "logical_count": len(
                {r["logical_canonical_id"] for r in resolutions.values()}
            ),
            "collapsed_count": sum(
                1 for r in resolutions.values() if r["status"] == RESOLVED_TO_PRIMARY
            ),
            # Reported so a caller can prove it is not doing N+1.
            "query_count": query_count,
            "invariant_failures": sorted(set(failures)),
        }
    )


def resolve_logical_canonical_id(
    *, connection: Any, canonical_id: Any
) -> dict[str, Any]:
    """Single-id convenience. Prefer the batch form inside a list read."""
    key = str(canonical_id or "")
    batch = resolve_logical_canonical_ids(connection=connection, canonical_ids=[key])
    resolution = dict(batch["resolutions"].get(key) or {})
    resolution["invariant_failures"] = batch["invariant_failures"]
    resolution["query_count"] = batch["query_count"]
    return _json_safe(resolution)


def list_pending_candidates(
    *, connection: Any, limit: int = 100
) -> list[dict[str, Any]]:
    """The review queue, highest confidence first."""
    table = _candidates_table()
    return [
        dict(row)
        for row in connection.execute(
            sa.select(table)
            .where(table.c.review_state == REVIEW_PENDING)
            .order_by(table.c.confidence.desc(), table.c.candidate_id)
            .limit(limit)
        )
        .mappings()
        .all()
    ]
