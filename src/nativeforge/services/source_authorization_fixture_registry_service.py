"""Synthetic sources, so the permitted branch is reachable (Gate 162G).

## Why this module has to exist

Gate 134F's rule: *an unreachable permitted branch makes a refusal
unfalsifiable.* If no source can ever be authorized, "every source is refused"
proves nothing — the code might refuse unconditionally and no test could tell.

So something must be able to reach `authorization_status=approved`. It must not
be one of the 177 real sources, because approving one of those is the single
thing Gate 162 is forbidden to do.

## Why it is not a parameter

The obvious implementation is a `registry_rows` argument on the resolver. That
would break the property the resolver is built on: no parameter can assert a
fact. Registry membership IS a fact — `source_registered` — so a caller who
could supply the registry could introduce a source and then record decisions
for it.

Instead these fixtures live in the repository, under a RESERVED prefix, and the
resolver consults them without being told to. `merge_fixture_rows` refuses any
id lacking the prefix and refuses to shadow a shipped registry id, so:

```text
a real source id          cannot appear here (prefix refused)
a fixture id              cannot collide with a real one (prefix reserved,
                          and shadowing is refused by name)
a caller                  cannot add one at runtime - there is no parameter
```

## What a fixture source proves, and what it does not

A fully-decided fixture source reaching `approved` proves the authorization
chain can say yes: the facts resolve, the guard is satisfied from records, and
the permitted branch is live code rather than dead code.

It proves nothing whatever about any real source. The fixture's terms decision
was signed by `reviewer:nf162-fixture`, its evidence fingerprint is of a string
in this file, and its URL resolves nowhere — `.invalid` is reserved by RFC 2606
precisely so it cannot exist.

And an authorized fixture source still cannot be called: Gate 161 built no live
transport, `live` is not in `DISPATCHABLE_KINDS`, and migration 0047's CHECK
constraints refuse a live attempt row. Authorization and capability stay
separate questions.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_source_authorization_fixture_registry_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Reserved. No shipped registry id uses it, and `merge_fixture_rows` refuses
#: any fixture id without it.
FIXTURE_PREFIX = "nf162.fixture."

#: The one fixture that exists to prove `approved` is reachable.
#:
#: `.invalid` is reserved by RFC 2606 and resolves nowhere, so even if every
#: refusal in the repository failed at once, a request built from this row
#: could not reach a host.
PERMITTABLE_FIXTURE = f"{FIXTURE_PREFIX}permittable"

#: A second fixture, identical in shape, that no decision will ever be recorded
#: for. Its job is to show that being a fixture is not itself permission - a
#: fixture with no decisions refuses exactly like a real source does.
UNDECIDED_FIXTURE = f"{FIXTURE_PREFIX}undecided"

FIXTURE_ROWS: dict[str, dict[str, Any]] = {
    PERMITTABLE_FIXTURE: {
        "seed_id": PERMITTABLE_FIXTURE,
        "canonical_source_id": f"nf:source:{PERMITTABLE_FIXTURE}",
        "source_name": "NF162 synthetic fixture (permittable)",
        "source_url": "https://fixtures.invalid/nf162/permittable",
        "tier": "fixture",
        "adapter_key": "nf162_fixture",
        "access_posture_hint": "public",
        "source_health_status": "healthy",
        "catalog_accounting_bucket": "fixture",
        "resolver_url_status": "resolved",
        "health_evidence": "fixture:declared_in_source_code",
        "fact_status": "synthetic_fixture",
    },
    UNDECIDED_FIXTURE: {
        "seed_id": UNDECIDED_FIXTURE,
        "canonical_source_id": f"nf:source:{UNDECIDED_FIXTURE}",
        "source_name": "NF162 synthetic fixture (never decided)",
        "source_url": "https://fixtures.invalid/nf162/undecided",
        "tier": "fixture",
        "adapter_key": "nf162_fixture",
        "access_posture_hint": "public",
        "source_health_status": "healthy",
        "catalog_accounting_bucket": "fixture",
        "resolver_url_status": "resolved",
        "health_evidence": "fixture:declared_in_source_code",
        "fact_status": "synthetic_fixture",
    },
}

FIXTURE_IDS: tuple[str, ...] = tuple(sorted(FIXTURE_ROWS))

REFUSE_NO_PREFIX = "fixture_id_lacks_the_reserved_prefix"
REFUSE_SHADOWS_REAL = "fixture_id_would_shadow_a_shipped_registry_source"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def is_fixture_source(source_id: Any) -> bool:
    """Whether this id belongs to the reserved fixture space.

    Prefix AND declared membership, both required. A prefix alone would let a
    caller name a real source `nf162.fixture.grants.gov`; declared membership
    alone would be a list somebody could grow without the prefix rule noticing.
    """
    text = str(source_id or "").strip()
    return text.startswith(FIXTURE_PREFIX) and text in FIXTURE_ROWS


def merge_fixture_rows(shipped: dict[str, Any]) -> dict[str, Any]:
    """Shipped registry plus fixtures. Refuses anything that could collide.

    Returns a NEW mapping; the shipped registry is never mutated. A fixture
    that lacks the prefix, or that would shadow a shipped id, is dropped and
    the reason is available from `describe_fixture_registry`.
    """
    merged = dict(shipped or {})
    for source_id, row in FIXTURE_ROWS.items():
        if not str(source_id).startswith(FIXTURE_PREFIX):
            continue
        if source_id in merged:
            # A fixture must never stand in front of a real source. If this
            # ever fires, the prefix has stopped being reserved.
            continue
        merged[source_id] = dict(row)
    return merged


def fixture_merge_refusals(shipped: dict[str, Any]) -> list[str]:
    """Why any fixture was dropped. Empty when the prefix is still reserved."""
    refusals: list[str] = []
    for source_id in FIXTURE_ROWS:
        if not str(source_id).startswith(FIXTURE_PREFIX):
            refusals.append(f"{REFUSE_NO_PREFIX}:{source_id}")
        if source_id in (shipped or {}):
            refusals.append(f"{REFUSE_SHADOWS_REAL}:{source_id}")
    return sorted(refusals)


def fixture_evidence_fingerprint(source_id: Any) -> str | None:
    """A fingerprint of a string in THIS FILE, not of any real document.

    A fixture's terms approval needs an evidence fingerprint because migration
    0048 refuses one without it. This makes that fingerprint obviously
    synthetic and traceable to source code rather than to a fetched page.
    """
    if not is_fixture_source(source_id):
        return None
    row = FIXTURE_ROWS[str(source_id)]
    seed = f"nf162-fixture-evidence:{row['source_url']}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def describe_fixture_registry(shipped: dict[str, Any] | None = None) -> dict[str, Any]:
    """What the fixture space is, for artifacts and verifiers."""
    shipped = shipped or {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "fixture_prefix": FIXTURE_PREFIX,
            "fixture_ids": list(FIXTURE_IDS),
            "fixture_count": len(FIXTURE_IDS),
            "permittable_fixture": PERMITTABLE_FIXTURE,
            "undecided_fixture": UNDECIDED_FIXTURE,
            "shipped_registry_count": len(shipped),
            "merged_count": len(merge_fixture_rows(shipped)),
            "merge_refusals": fixture_merge_refusals(shipped),
            "prefix_is_reserved": not any(
                str(key).startswith(FIXTURE_PREFIX) for key in shipped
            ),
            "no_fixture_shadows_a_real_source": not (
                set(FIXTURE_IDS) & set(shipped)
            ),
            "why_this_exists": (
                "an unreachable permitted branch makes a refusal "
                "unfalsifiable. Something must be able to reach approved, and "
                "it must not be one of the 177 real sources."
            ),
            "what_a_fixture_approval_proves": (
                "that the authorization chain can say yes - the facts resolve, "
                "the guard is satisfied from records, and the permitted branch "
                "is live code. It proves nothing about any real source."
            ),
            "what_it_still_cannot_do": (
                "an authorized fixture cannot be called. Gate 161 built no "
                "live transport, `live` is not dispatchable, and migration "
                "0047 refuses a live attempt row."
            ),
            "urls_resolve_nowhere": (
                "`.invalid` is reserved by RFC 2606 precisely so it cannot "
                "exist"
            ),
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def fixture_registry_invariant_failures(described: dict[str, Any]) -> list[str]:
    """Refuse a fixture registry that could touch a real source."""
    fails: list[str] = []

    if not described.get("fixture_ids"):
        fails.append("no_fixture_exists_so_approved_is_unreachable")
    for source_id in described.get("fixture_ids") or ():
        if not str(source_id).startswith(
            str(described.get("fixture_prefix") or "\x00")
        ):
            fails.append(f"a_fixture_without_the_reserved_prefix:{source_id}")

    if not described.get("prefix_is_reserved"):
        fails.append("the_shipped_registry_uses_the_fixture_prefix")
    if not described.get("no_fixture_shadows_a_real_source"):
        fails.append("a_fixture_shadows_a_real_source")
    if described.get("merge_refusals"):
        fails.append(f"fixtures_were_dropped:{described['merge_refusals']}")

    # The merge must ADD exactly the fixtures and nothing else.
    expected = int(described.get("shipped_registry_count") or 0) + len(
        described.get("fixture_ids") or ()
    )
    if int(described.get("merged_count") or 0) != expected:
        fails.append(
            f"merged_count_{described.get('merged_count')}_expected_{expected}"
        )

    # A fixture must be BOTH prefixed and declared. One alone is bypassable.
    if described.get("permittable_fixture") and not is_fixture_source(
        described["permittable_fixture"]
    ):
        fails.append("the_permittable_fixture_is_not_recognised_as_one")
    if is_fixture_source("nf162.fixture.grants.gov"):
        fails.append("a_prefixed_but_undeclared_id_was_accepted")
    if is_fixture_source("grants.gov"):
        fails.append("an_unprefixed_id_was_accepted")

    for flag in ("live_source_call", "source_monitoring_live"):
        if described.get(flag):
            fails.append(f"fixture_registry_claimed:{flag}")

    return sorted(set(fails))
