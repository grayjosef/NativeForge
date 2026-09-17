"""Gate 161 verifier phase: what the SERVED schema exposes.

Reads the live OpenAPI document from stdin rather than the source, because what
the app serves is what a caller reaches. A route removed from the source but
still mounted, or mounted with a parameter the source does not show, is exactly
the gap a source-only check misses.

Writes nothing.
"""

from __future__ import annotations

import json
import sys

#: A parameter by any of these names would let a caller name an address.
#: Matched on whole `_`-separated words, not as substrings: `limit` contains no
#: word here, and a field called `cultural_url_note` would be caught by a
#: substring test for `url` while `nurls` would not be.
ADDRESS_WORDS = {
    "url",
    "urls",
    "uri",
    "endpoint",
    "host",
    "hostname",
    "address",
    "target",
    "location",
    "callback",
    "redirect",
    "fetch",
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
    if "collector-execution" in path
}

out["routes_are_registered"] = bool(len(paths) >= 3)
if not paths:
    detail.append("no collector-execution paths in the served schema")

offending: list[str] = []
for path, ops in paths.items():
    for method, operation in ops.items():
        for parameter in operation.get("parameters") or []:
            name = str(parameter.get("name") or "")
            words = {
                part
                for chunk in name.replace("-", "_").split("_")
                for part in [chunk.lower()]
            }
            if words & ADDRESS_WORDS:
                offending.append(f"{method.upper()} {path} ?{name}")

        # A request body is a way to supply one too, so its schema properties
        # are checked by the same rule rather than trusted to be harmless.
        body = operation.get("requestBody") or {}
        for media in (body.get("content") or {}).values():
            schema = media.get("schema") or {}
            for prop in (schema.get("properties") or {}):
                words = {
                    part
                    for chunk in str(prop).replace("-", "_").split("_")
                    for part in [chunk.lower()]
                }
                if words & ADDRESS_WORDS:
                    offending.append(f"{method.upper()} {path} body.{prop}")

out["no_route_takes_a_url_parameter"] = not offending
if offending:
    detail.append(f"address-shaped parameters: {sorted(set(offending))}")

smoke = [ops for path, ops in paths.items() if path.endswith("/smoke")]
out["the_smoke_takes_no_request_body"] = bool(
    smoke and not (smoke[0].get("post") or {}).get("requestBody")
)
if not smoke:
    detail.append("no smoke route in the served schema")

for key in (
    "routes_are_registered",
    "no_route_takes_a_url_parameter",
    "the_smoke_takes_no_request_body",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
