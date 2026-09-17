"""Gate 162 verifier phase: the served surface has no mutation and takes no fact.

Read from the LIVE OpenAPI document on stdin, because what the app serves is
what a caller reaches. A route removed from the source but still mounted, or
mounted with a parameter the source does not show, is exactly the gap a
source-only check misses.

Writes nothing.
"""

from __future__ import annotations

import json
import sys

#: A parameter by any of these names would let a caller assert a fact or name
#: an address. Matched on whole `_`-separated words, never as substrings: a
#: field called `authorization_status` is a RESPONSE field and `limit` contains
#: no word here, while a substring test for `status` would flag both.
FACT_WORDS = {
    "approved",
    "approve",
    "allow",
    "allowed",
    "permit",
    "permitted",
    "override",
    "fact",
    "terms",
    "activation",
    "robots",
    "credential",
    "attribution",
    "decision",
    "authorize",
}

ADDRESS_WORDS = {
    "url",
    "uri",
    "endpoint",
    "host",
    "hostname",
    "address",
    "target",
    "callback",
    "redirect",
    "proxy",
}

out: dict[str, object] = {}
detail: list[str] = []

try:
    spec = json.load(sys.stdin)
except Exception as exc:  # noqa: BLE001 - a phase reports rather than raises
    detail.append(f"openapi_unreadable:{type(exc).__name__}")
    spec = {}

paths = {
    path: ops
    for path, ops in (spec.get("paths") or {}).items()
    if "source-authorization" in path
}

out["routes_are_registered"] = bool(len(paths) >= 4)
out["route_count"] = len(paths)
if not paths:
    detail.append("no source-authorization paths in the served schema")


def words(name: str) -> set[str]:
    return {part.lower() for part in str(name).replace("-", "_").split("_")}


mutating: list[str] = []
fact_params: list[str] = []
address_params: list[str] = []
bodies: list[str] = []

for path, ops in paths.items():
    for method, operation in ops.items():
        verb = method.upper()
        # THE check: no write verb anywhere on this surface.
        if verb in {"POST", "PUT", "PATCH", "DELETE"}:
            mutating.append(f"{verb} {path}")

        for parameter in operation.get("parameters") or []:
            name = parameter.get("name") or ""
            if words(name) & FACT_WORDS:
                fact_params.append(f"{verb} {path} ?{name}")
            if words(name) & ADDRESS_WORDS:
                address_params.append(f"{verb} {path} ?{name}")

        if operation.get("requestBody"):
            bodies.append(f"{verb} {path}")

out["no_mutation_endpoint_exists"] = not mutating
out["mutation_endpoints"] = len(mutating)
out["no_route_parameter_asserts_a_fact"] = not fact_params
out["no_route_parameter_names_an_address"] = not address_params
out["no_route_accepts_a_request_body"] = not bodies

if mutating:
    detail.append(f"mutating routes: {sorted(mutating)}")
if fact_params:
    detail.append(f"fact-shaped params: {sorted(fact_params)}")
if address_params:
    detail.append(f"address-shaped params: {sorted(address_params)}")
if bodies:
    detail.append(f"routes with bodies: {sorted(bodies)}")

# Every route must sit behind the demo session dependency, which shows up in
# the schema as an `nf_session` cookie parameter.
unguarded: list[str] = []
for path, ops in paths.items():
    for method, operation in ops.items():
        names = {p.get("name") for p in operation.get("parameters") or []}
        if "nf_session" not in names:
            unguarded.append(f"{method.upper()} {path}")
out["every_route_requires_a_session"] = not unguarded
if unguarded:
    detail.append(f"routes with no session parameter: {sorted(unguarded)}")

for key in (
    "routes_are_registered",
    "no_mutation_endpoint_exists",
    "no_route_parameter_asserts_a_fact",
    "no_route_parameter_names_an_address",
    "no_route_accepts_a_request_body",
    "every_route_requires_a_session",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
