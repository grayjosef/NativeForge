"""Gate 132G: two activation gates that were literals, measured instead.

## What was wrong

```python
# auth0_live_validation_runner_service, before this gate
callback_session_validated = False          # a literal
def run_auth0_live_validation(*, org_binding_passed: bool = False, ...)
```

`callback_session_validated` was assigned `False` and never assigned anything
else. `org_binding_passed` was a parameter no caller ever passed. Both fed
`build_customer_auth_activation_gate`, both were therefore false in every
environment for every reason and for none.

That was honest while nothing could satisfy them. Gate 132 satisfied them - a
real callback validated a real state, verified a real ID token, and a verified
claim resolved to an `organization_id` through a membership row - and a literal
that outlives the thing it described is the defect this campaign keeps finding.
A constant frozen in one gate becomes a lie in the next.

## Derived from rows, or not at all

```text
org_binding_passed            an identity row, and a membership row anchored on
                              organization_id that resolves for that identity
callback_session_validated    the above, plus a consumed redirect state - a row
                              that was issued by /login and spent by /callback
```

`callback_session_validated` is the stricter of the two on purpose. A membership
can be created by a script; a consumed state can only be produced by a redirect
that came back. The pair is what "a real callback validated a session" means in
facts that survive the process that observed them.

## No connection, no evidence

Without a connection every field is false and `no_connection_supplied` is the
reason. That is not a fallback - it is what keeps
`build_customer_auth_activation_gate` deterministic for the artifacts it feeds.
An artifact whose contents depend on the rows in the developer's local database
is an artifact nobody else can regenerate, which is the objection the gate
service already records about shelling out to `systemctl`.

So the routes pass their session and answer honestly; artifact generation passes
nothing and stays reproducible. The two numbers differing is the point, and the
artifacts record both.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_customer_auth_binding_evidence_v1"

IDENTITY_TABLE = "nf_identities"
MEMBERSHIP_TABLE = "nf_org_memberships"
REDIRECT_STATE_TABLE = "nf_auth_redirect_states"

EVIDENCE_FIELDS: tuple[str, ...] = (
    "schema_version",
    "connection_supplied",
    "identity_rows",
    "active_membership_rows",
    "consumed_redirect_state_rows",
    "resolvable_identities",
    "org_binding_passed",
    "callback_session_validated",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_binding_evidence(*, connection: Any = None) -> dict[str, Any]:
    """Measure the two gates. Deny by default."""
    from nativeforge.services.identity_org_session_resolution_service import (
        resolve_session_organization,
    )

    blocked_reasons: list[str] = []

    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "connection_supplied": False,
                "identity_rows": 0,
                "active_membership_rows": 0,
                "consumed_redirect_state_rows": 0,
                "resolvable_identities": 0,
                "org_binding_passed": False,
                "callback_session_validated": False,
                "blocked_reasons": ["no_connection_supplied"],
            }
        )

    identity_rows = 0
    membership_rows = 0
    consumed_states = 0
    resolvable = 0
    # Separate from `blocked_reasons` on purpose. A redirect-state table this
    # caller cannot read says nothing about whether an identity resolves to an
    # organization, and folding the two together made an absent table block a
    # gate it has no bearing on. Each gate is blocked by its own failures.
    binding_blockers: list[str] = []

    try:
        identity_ids = [
            row["id"]
            for row in connection.execute(
                sa.text(f"SELECT id FROM {IDENTITY_TABLE} WHERE disabled_at IS NULL")
            ).mappings()
        ]
        identity_rows = len(identity_ids)
    except Exception:
        blocked_reasons.append("identity_table_unreadable")
        binding_blockers.append("identity_table_unreadable")
        identity_ids = []

    try:
        membership_rows = int(
            connection.execute(
                sa.text(
                    f"SELECT COUNT(*) FROM {MEMBERSHIP_TABLE} "
                    "WHERE state = 'active' AND revoked_at IS NULL"
                )
            ).scalar_one()
        )
    except Exception:
        blocked_reasons.append("membership_table_unreadable")
        binding_blockers.append("membership_table_unreadable")

    try:
        # A state row that was spent. Only a callback can spend one, so this is
        # the half a script cannot manufacture.
        consumed_states = int(
            connection.execute(
                sa.text(
                    f"SELECT COUNT(*) FROM {REDIRECT_STATE_TABLE} "
                    "WHERE consumed_at IS NOT NULL"
                )
            ).scalar_one()
        )
    except Exception:
        blocked_reasons.append("redirect_state_table_unreadable")

    for identity_id in identity_ids:
        try:
            result = resolve_session_organization(
                connection=connection, identity_id=identity_id
            )
        except Exception:
            blocked_reasons.append("resolution_unavailable")
            binding_blockers.append("resolution_unavailable")
            break
        if result["organization_id_resolved"]:
            resolvable += 1

    org_binding_passed = bool(
        resolvable and identity_rows and membership_rows and not binding_blockers
    )
    callback_session_validated = bool(org_binding_passed and consumed_states)

    if not resolvable:
        blocked_reasons.append("no_identity_resolves_to_an_organization")
    if not consumed_states:
        blocked_reasons.append("no_redirect_state_has_been_consumed")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "connection_supplied": True,
            "identity_rows": identity_rows,
            "active_membership_rows": membership_rows,
            "consumed_redirect_state_rows": consumed_states,
            "resolvable_identities": resolvable,
            "org_binding_passed": org_binding_passed,
            "callback_session_validated": callback_session_validated,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def evidence_invariant_failures(evidence: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if evidence.get("org_binding_passed") and not evidence.get("connection_supplied"):
        fails.append("org_binding_passed_without_reading_anything")
    if evidence.get("org_binding_passed") and not evidence.get("resolvable_identities"):
        fails.append("org_binding_passed_without_a_resolvable_identity")
    if evidence.get("org_binding_passed") and not evidence.get(
        "active_membership_rows"
    ):
        fails.append("org_binding_passed_without_an_active_membership")
    if evidence.get("callback_session_validated") and not evidence.get(
        "org_binding_passed"
    ):
        fails.append("callback_session_validated_without_an_org_binding")
    if evidence.get("callback_session_validated") and not evidence.get(
        "consumed_redirect_state_rows"
    ):
        # The half a script cannot manufacture. Without it this gate would be
        # satisfiable by inserting two rows.
        fails.append("callback_session_validated_without_a_consumed_state")

    return fails
