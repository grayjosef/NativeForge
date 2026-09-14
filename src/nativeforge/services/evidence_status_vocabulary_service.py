"""Gate 152B: the words a replay may use about a piece of evidence.

## Status is per link, not per record

Gate 152A's measurement is why. Every one of the 85 delivery intents is
simultaneously:

```text
its audit link     linked_record_found    the event resolves, 85 of 85
its digest link    legacy_gap             the record was never written
```

A single status per record would have to pick one and would be wrong about the
other. So a replay returns a chain of links, each carrying its own status, and a
record's overall status is **derived from the weakest link** rather than
asserted alongside it.

## Six of these ten are not proof

```text
proof         attested, hash_verified, linked_record_found
not proof     legacy_gap, missing_record, not_attributable,
              not_replayable, not_attestable, unknown, blocked
```

`unknown` and `legacy_gap` are the two a reader is most likely to skim past as
though they were mild versions of "fine". They are not: an unknown link proves
nothing, and a legacy gap is a record that can never be produced. Both are
ranked below every proving status so the weakest-link rule puts them on top.

## Nothing here claims production or legal standing

Every status is scoped to `controlled_dev_demo`. "Attested" means this system
can find the record and check it against its own hash, not that it would satisfy
an auditor or a court.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_evidence_status_vocabulary_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

ATTESTED = "attested"
HASH_VERIFIED = "hash_verified"
LINKED_RECORD_FOUND = "linked_record_found"
LEGACY_GAP = "legacy_gap"
MISSING_RECORD = "missing_record"
NOT_ATTRIBUTABLE = "not_attributable"
NOT_REPLAYABLE = "not_replayable"
NOT_ATTESTABLE = "not_attestable"
UNKNOWN = "unknown"
BLOCKED = "blocked"

#: Every status, in the order they are ranked below.
EVIDENCE_STATUSES: tuple[str, ...] = (
    ATTESTED,
    HASH_VERIFIED,
    LINKED_RECORD_FOUND,
    LEGACY_GAP,
    MISSING_RECORD,
    NOT_ATTRIBUTABLE,
    NOT_REPLAYABLE,
    NOT_ATTESTABLE,
    UNKNOWN,
    BLOCKED,
)

#: The three that assert something was shown to be so. Everything else is a
#: reason a replay could not.
PROVING_STATUSES: frozenset[str] = frozenset(
    {ATTESTED, HASH_VERIFIED, LINKED_RECORD_FOUND}
)

#: Never proof, however a summary phrases it.
NON_PROVING_STATUSES: frozenset[str] = frozenset(EVIDENCE_STATUSES) - PROVING_STATUSES

#: Lower is stronger. A chain's status is the weakest link's, so a single
#: `legacy_gap` outranks any number of `hash_verified` links above it.
STATUS_RANK: dict[str, int] = {
    ATTESTED: 0,
    HASH_VERIFIED: 1,
    LINKED_RECORD_FOUND: 2,
    LEGACY_GAP: 3,
    MISSING_RECORD: 4,
    NOT_ATTRIBUTABLE: 5,
    NOT_REPLAYABLE: 6,
    NOT_ATTESTABLE: 7,
    UNKNOWN: 8,
    BLOCKED: 9,
}

#: What each status means, and - for the ones that are not proof - what would
#: have to change for it to become proof. `never` is an honest answer and the
#: right one for three of them.
STATUS_DEFINITIONS: dict[str, dict[str, Any]] = {
    ATTESTED: {
        "means": "the record was found and every check on it passed",
        "is_proof": True,
        "becomes_proof_when": "already is, within controlled_dev_demo",
    },
    HASH_VERIFIED: {
        "means": (
            "the stored payload hash equals a hash recomputed over the stored "
            "payload"
        ),
        "is_proof": True,
        "becomes_proof_when": "already is",
    },
    LINKED_RECORD_FOUND: {
        "means": "the record this one points at exists and is readable",
        "is_proof": True,
        "becomes_proof_when": "already is",
    },
    LEGACY_GAP: {
        "means": (
            "the record predates the table that would have held it. It is not "
            "wrong, it was un-storable at the time."
        ),
        "is_proof": False,
        "becomes_proof_when": (
            "never, for this record. The digest it referred to cannot be "
            "reconstructed and regenerating one would produce a different "
            "digest for the same period."
        ),
    },
    MISSING_RECORD: {
        "means": "the record should exist and does not",
        "is_proof": False,
        "becomes_proof_when": "the record is written by the path that owes it",
    },
    NOT_ATTRIBUTABLE: {
        "means": "nothing records who or what this came from",
        "is_proof": False,
        "becomes_proof_when": "an actor or source is recorded at write time",
    },
    NOT_REPLAYABLE: {
        "means": (
            "the event did not happen, so there is nothing to replay - a "
            "delivery that was never sent has no delivery to attest"
        ),
        "is_proof": False,
        "becomes_proof_when": "the capability is activated and the event occurs",
    },
    NOT_ATTESTABLE: {
        "means": (
            "this system cannot speak to it at all, in this scope. Production "
            "and legal standing are the usual subjects."
        ),
        "is_proof": False,
        "becomes_proof_when": "never, in controlled_dev_demo",
    },
    UNKNOWN: {
        "means": "nobody has determined it",
        "is_proof": False,
        "becomes_proof_when": (
            "somebody determines it. An unknown link proves nothing and is "
            "ranked below every gap so a chain cannot read green through one."
        ),
    },
    BLOCKED: {
        "means": "a refusal stopped the replay before it could look",
        "is_proof": False,
        "becomes_proof_when": "the refusal clears",
    },
}

#: Claims this vocabulary never supports.
NOT_CLAIMED: tuple[str, ...] = (
    "legal_grade_audit",
    "production_audit_ready",
    "delivery_occurred",
    "tenant_read_the_digest",
    "real_customer_evidence",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def is_proof(status: str) -> bool:
    """Only three statuses assert anything. The rest are reasons."""
    return str(status or "").strip().lower() in PROVING_STATUSES


def rank(status: str) -> int:
    """Unknown names rank worst, so an unrecognised status cannot read green."""
    return STATUS_RANK.get(str(status or "").strip().lower(), STATUS_RANK[BLOCKED])


def normalize(status: Any) -> str:
    """Map anything outside the vocabulary onto `blocked`.

    The vocabulary is closed, and a closed vocabulary that can emit a value
    outside itself is not closed: a caller indexing `STATUS_DEFINITIONS` with
    the result would raise. An unrecognised status is treated as a refusal
    because it is one - the replay could not say what it meant.
    """
    candidate = str(status or "").strip().lower()
    return candidate if candidate in STATUS_RANK else BLOCKED


def weakest(statuses: Any) -> str:
    """A chain is as good as its worst link, and no better.

    An empty chain is `unknown` rather than `attested`: nothing examined is not
    the same as nothing wrong.
    """
    candidates = [normalize(s) for s in (statuses or [])]
    if not candidates:
        return UNKNOWN
    return max(candidates, key=rank)


def build_vocabulary() -> dict[str, Any]:
    """The whole vocabulary, deterministic and free of any measurement."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "statuses": list(EVIDENCE_STATUSES),
            "status_count": len(EVIDENCE_STATUSES),
            "proving_statuses": sorted(PROVING_STATUSES),
            "non_proving_statuses": sorted(NON_PROVING_STATUSES),
            "definitions": {
                name: dict(entry) for name, entry in STATUS_DEFINITIONS.items()
            },
            "rank": dict(STATUS_RANK),
            "status_is_per_link_not_per_record": True,
            "why": (
                "every one of the 85 delivery intents has an audit link that "
                "resolves and a digest link that never will. One status per "
                "record would have to pick one and be wrong about the other."
            ),
            "chain_status_rule": "the weakest link, never an average",
            "empty_chain_is": UNKNOWN,
            "not_claimed": list(NOT_CLAIMED),
        }
    )


def vocabulary_invariant_failures(vocabulary: dict[str, Any]) -> list[str]:
    """Refuse a vocabulary that lost a status or promoted a non-proof."""
    fails: list[str] = []

    declared = list(vocabulary.get("statuses") or [])
    missing = set(EVIDENCE_STATUSES) - set(declared)
    if missing:
        fails.append(f"statuses_lost:{sorted(missing)}")
    if len(declared) != len(set(declared)):
        fails.append("statuses_declared_twice")

    definitions = vocabulary.get("definitions") or {}
    for name in EVIDENCE_STATUSES:
        entry = definitions.get(name) or {}
        if not entry.get("means"):
            fails.append(f"status_without_a_meaning:{name}")
        if not entry.get("becomes_proof_when"):
            fails.append(f"status_without_a_remedy:{name}")
        if bool(entry.get("is_proof")) != (name in PROVING_STATUSES):
            fails.append(f"is_proof_disagrees_with_the_set:{name}")

    proving = set(vocabulary.get("proving_statuses") or [])
    if proving != PROVING_STATUSES:
        fails.append("proving_set_changed")
    if proving & NON_PROVING_STATUSES:
        fails.append("a_non_proving_status_was_promoted")

    ranks = vocabulary.get("rank") or {}
    for name in PROVING_STATUSES:
        for other in NON_PROVING_STATUSES:
            if ranks.get(name, 0) >= ranks.get(other, 0):
                fails.append(f"a_proving_status_ranks_no_better_than:{other}")
                break

    if vocabulary.get("empty_chain_is") != UNKNOWN:
        fails.append("an_empty_chain_does_not_read_unknown")

    return sorted(set(fails))
