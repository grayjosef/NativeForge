"""Which attribution notice a source owes, by adapter (Gate 166I).

Gate 166's genericity scan found a real factory blocker, not a naming problem:

```python
# source_authorization_fact_resolver_service._resolve_attribution
from nativeforge.services.grants_gov_attribution_service import (
    MANIFEST_BLOCK_KEY, MANIFEST_NOTICE_KEY, build_attribution_contract,
)
```

`ATTRIBUTION_TEXT` there is the verbatim Grants.gov notice, compared with `==`.
So the GENERIC fact resolver verified every source's recorded notice against
**Grants.gov's** string. Source #2 - with its own publisher, its own terms and
its own required wording - would have had its correct notice rejected for not
being Grants.gov's, and no amount of signing decisions would have fixed it.

That is the sort of leak the campaign is built to find: nothing was wrong
today, because there is only one source; everything would be wrong on the day
the gate exists to enable.

## The same pattern the capability layer already uses

`source_collector_capability_service.ADAPTER_CAPABILITIES` resolves an adapter
by `adapter_key` from the source's own catalog row. This is that table for
attribution. The resolver stops importing a publisher-specific module and looks
up the contract belonging to the source in front of it.

Grants.gov's behaviour is **unchanged**: the same module, the same verbatim
constant, the same character-for-character comparison. What changed is that a
second source can declare its own, and a source that declares none is answered
by its terms decision rather than by a foreign publisher's string.

## Declaring a contract is not satisfying one

A descriptor names where the required text lives. It never asserts that the
text was published. The notice recorded on the activation is still verified
character-for-character, and one edited character still returns `missing`.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_attribution_contract_v1"

#: adapter_key -> where that publisher's required notice and verifier live.
#:
#: Keyed by `adapter_key` from the catalog row, so adding source #2 is a row
#: plus an entry here - never an edit to the generic resolver.
ATTRIBUTION_CONTRACTS: dict[str, dict[str, str]] = {
    "grants_gov_search2": {
        "module": "nativeforge.services.grants_gov_attribution_service",
        "builder": "build_attribution_contract",
        "manifest_block_constant": "MANIFEST_BLOCK_KEY",
        "manifest_notice_constant": "MANIFEST_NOTICE_KEY",
        # Where the required TEXT lives. Declared rather than assumed: callers
        # previously reached for a constant literally named ATTRIBUTION_TEXT,
        # which worked only while one adapter existed and its module happened
        # to use that name. A module serving two adapters cannot.
        "text_constant": "ATTRIBUTION_TEXT",
        "publisher": "Grants.gov",
        "why": "the Grants.gov API Terms & Conditions require a verbatim notice",
    },
    # Gate 171. The first two rows added by a gate other than the one that
    # built this table, which is the test it was written for: a source
    # declaring its own required text, with no edit to the generic resolver.
    "bia_program_page_html": {
        "module": "nativeforge.services.source_adapters.gate171_attribution",
        "builder": "build_bia_attribution_contract",
        "manifest_block_constant": "BIA_MANIFEST_BLOCK_KEY",
        "manifest_notice_constant": "BIA_MANIFEST_NOTICE_KEY",
        "text_constant": "BIA_ATTRIBUTION_TEXT",
        "publisher": "Bureau of Indian Affairs",
        "why": (
            "the operator's activation recorded attribution as required for "
            "this source, so the notice is owed and must be verbatim"
        ),
    },
    "federal_register_documents_json": {
        "module": "nativeforge.services.source_adapters.gate171_attribution",
        "builder": "build_federal_register_attribution_contract",
        "manifest_block_constant": "FEDERAL_REGISTER_MANIFEST_BLOCK_KEY",
        "manifest_notice_constant": "FEDERAL_REGISTER_MANIFEST_NOTICE_KEY",
        "text_constant": "FEDERAL_REGISTER_ATTRIBUTION_TEXT",
        "publisher": "Office of the Federal Register",
        "why": (
            "the operator's activation recorded attribution as required for "
            "this source, so the notice is owed and must be verbatim"
        ),
    },
}

#: The surfaces a notice may be declared on. Carried here so the resolver does
#: not name a publisher's module to learn them.
DECLARED_SURFACES: tuple[str, ...] = ("runtime_payload", "service_constant")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def contract_for_adapter(adapter_key: Any) -> dict[str, str] | None:
    """The attribution contract for this adapter, or None if it declares one.

    None means "this adapter has no publisher-specific attribution contract",
    which is not the same as "attribution is not required" - that answer comes
    from the terms decision and is not this module's to give.
    """
    key = str(adapter_key or "").strip()
    return dict(ATTRIBUTION_CONTRACTS[key]) if key in ATTRIBUTION_CONTRACTS else None


def verify_recorded_notice(
    *, adapter_key: Any = None, notice: Any = None
) -> dict[str, Any]:
    """Is the recorded notice this adapter's required text, verbatim?

    Returns a verdict; raises nothing. An adapter with no declared contract
    returns `no_contract_declared` rather than a pass - a source whose terms
    demand attribution and whose adapter declares no required text has an
    unsatisfiable requirement, and saying so is better than inventing one.
    """
    contract = contract_for_adapter(adapter_key)
    if contract is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "adapter_key": str(adapter_key or "") or None,
                "result": "no_contract_declared",
                "attribution_is_customer_visible": False,
                "attribution_status": None,
                "evidence_ref": (
                    "source_attribution_contract_service:no_contract_declared"
                ),
            }
        )

    if not notice:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "adapter_key": str(adapter_key or "") or None,
                "result": "missing",
                "attribution_is_customer_visible": False,
                "attribution_status": None,
                "evidence_ref": f"{contract['module']}:no_notice_recorded",
            }
        )

    try:
        module = __import__(contract["module"], fromlist=["*"])
        build = getattr(module, contract["builder"])
        block_key = getattr(module, contract["manifest_block_constant"])
        notice_key = getattr(module, contract["manifest_notice_constant"])
    except Exception as exc:  # noqa: BLE001 - an unresolvable contract verifies nothing
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "adapter_key": str(adapter_key or "") or None,
                "result": "contract_unresolvable",
                "attribution_is_customer_visible": False,
                "attribution_status": None,
                "evidence_ref": f"{contract['module']}:{type(exc).__name__}",
            }
        )

    try:
        verdict = build(
            trust_manifest={block_key: {notice_key: notice}},
            # `runtime_payload` is the surface the manifest represents.
            # `service_constant` is declared too but is NOT customer visible
            # on its own, which is the bar that matters.
            surfaces_present=list(DECLARED_SURFACES),
        )
    except Exception as exc:  # noqa: BLE001 - an unverifiable notice is not one
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "adapter_key": str(adapter_key or "") or None,
                "result": "verification_failed",
                "attribution_is_customer_visible": False,
                "attribution_status": None,
                "evidence_ref": f"{contract['module']}:{type(exc).__name__}",
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": str(adapter_key or "") or None,
            "result": "verified",
            "attribution_is_customer_visible": bool(
                verdict.get("attribution_is_customer_visible")
            ),
            "attribution_status": verdict.get("attribution_status"),
            "publisher": contract.get("publisher"),
            "evidence_ref": (
                f"{contract['module']}:verified_verbatim:runtime_payload"
            ),
        }
    )


def describe_contracts() -> dict[str, Any]:
    """Which adapters declare an attribution contract. Names no source id."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapters_with_contracts": sorted(ATTRIBUTION_CONTRACTS),
            "contract_count": len(ATTRIBUTION_CONTRACTS),
            "keyed_by": "adapter_key from the source catalog row",
            "declaring_is_not_satisfying": (
                "a descriptor names where the required text lives; the notice "
                "recorded on the activation is still verified verbatim"
            ),
        }
    )
