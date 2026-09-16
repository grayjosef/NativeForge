"""Safe response metadata (Gate 160F).

## An allowlist, by header NAME, not a scan for suspicious text

```text
allowlist   a header is kept because it is on a list of headers we understand
denylist    a header is kept because nothing on a list of bad words matched it
```

The second is how a credential in a header nobody anticipated gets stored. A new
provider invents `X-Acme-Session`, no pattern matches it, and it is persisted
forever. The first refuses it by default, which is the correct behaviour for a
header nobody has looked at.

So the decision is made by **normalized header name membership**, and the result
records which rule fired for every header — kept, refused as credential-bearing,
or refused as simply unrecognised. Those last two are deliberately different:
one is a known danger, the other is an unknown, and an operator reading the
report should be able to tell them apart.

## Why name classification and not a substring scan

This campaign has hit substring-vs-meaning eight times. A scan for `"token"` in
a header name matches `X-RateLimit-Token-Bucket`; a scan for `"key"` matches
`X-Cache-Key`. Neither is a credential, and both would be refused by a naive
scan while a real credential named `X-Acme-Session` sailed through.

Name membership is exact. The `CREDENTIAL_HEADERS` set exists so a refusal can
say *this is a known credential header* rather than *something about this string
looked alarming* — but it is not what keeps unknown headers out. The allowlist
is. `CREDENTIAL_HEADERS` only improves the explanation.

## Values are inspected too, but only as a second line

A header on the allowlist could still carry a credential if a provider does
something strange — `Cache-Control: private, key=abc123`. So allowed values are
checked against the body secret scanner's own findings, and a finding refuses
the header rather than redacting it. Redaction would store a mutilated value
that is neither the truth nor absent.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_response_metadata_filter_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: THE list. A response header is persisted only if its normalized name is
#: here. Everything else is refused, including headers nobody has classified.
#:
#: Each entry is here because a collector would actually need it:
#:   content-type    how to interpret the bytes
#:   content-length  whether the body is complete
#:   etag            whether the source changed since last time
#:   last-modified   likewise, for sources without an ETag
#:   date            when the origin generated the response
#:   cache-control   whether a re-fetch would even reach the origin
#:   retry-after     how long to wait before the next attempt
#:   content-language / content-encoding  how to decode
#:   the ratelimit-* family              whether the next attempt is safe
ALLOWED_RESPONSE_HEADERS: frozenset[str] = frozenset(
    {
        "content-type",
        "content-length",
        "content-language",
        "content-encoding",
        "etag",
        "last-modified",
        "date",
        "cache-control",
        "expires",
        "age",
        "vary",
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "ratelimit-limit",
        "ratelimit-remaining",
        "ratelimit-reset",
    }
)

#: Known credential-bearing headers. NOT the thing that keeps unknown headers
#: out - the allowlist does that. This set exists so a refusal can say WHICH
#: kind of refusal it is, which matters when somebody reads the report.
CREDENTIAL_HEADERS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "www-authenticate",
        "proxy-authenticate",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "auth-token",
        "x-access-token",
        "access-token",
        "x-csrf-token",
        "x-xsrf-token",
        "x-session-id",
        "x-session-token",
        "x-amz-security-token",
        "x-goog-iam-authorization-token",
        "authentication-info",
    }
)

KEPT = "kept"
REFUSED_CREDENTIAL = "refused_known_credential_header"
REFUSED_UNRECOGNISED = "refused_not_on_the_allowlist"
REFUSED_VALUE = "refused_value_looked_like_a_credential"
REFUSED_OVERSIZE = "refused_header_value_too_long"

DECISIONS: tuple[str, ...] = (
    KEPT,
    REFUSED_CREDENTIAL,
    REFUSED_UNRECOGNISED,
    REFUSED_VALUE,
    REFUSED_OVERSIZE,
)

#: A header value longer than this is refused rather than stored. Real values
#: for allowlisted headers are short; a very long one is either a bug or
#: something being smuggled through a field nobody expected to be large.
MAX_HEADER_VALUE_LENGTH = 1024

#: The most headers one response may contribute. A response with hundreds of
#: headers is refused wholesale rather than filtered one by one.
MAX_HEADERS = 64


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def normalize_header_name(name: Any) -> str:
    """Lowercased and stripped. HTTP header names are case-insensitive."""
    return str(name or "").strip().lower()


def classify_header(name: Any, value: Any = None) -> dict[str, Any]:
    """Decide one header, by name first and value second."""
    normalized = normalize_header_name(name)
    text = "" if value is None else str(value)

    if not normalized:
        return {
            "name": None,
            "normalized": "",
            "decision": REFUSED_UNRECOGNISED,
            "why": "a header with no name cannot be classified",
        }

    # Name first. A known credential header is refused by name whatever its
    # value happens to look like.
    if normalized in CREDENTIAL_HEADERS:
        return {
            "name": str(name),
            "normalized": normalized,
            "decision": REFUSED_CREDENTIAL,
            "why": "this header carries credentials by definition",
        }

    # Then the allowlist. Anything not on it is refused - including headers
    # nobody has classified, which is the point.
    if normalized not in ALLOWED_RESPONSE_HEADERS:
        return {
            "name": str(name),
            "normalized": normalized,
            "decision": REFUSED_UNRECOGNISED,
            "why": (
                "not on the allowlist. A header nobody has looked at is "
                "refused by default rather than kept because no pattern "
                "matched it."
            ),
        }

    if len(text) > MAX_HEADER_VALUE_LENGTH:
        return {
            "name": str(name),
            "normalized": normalized,
            "decision": REFUSED_OVERSIZE,
            "why": f"value is {len(text)} characters, over "
            f"{MAX_HEADER_VALUE_LENGTH}",
        }

    # Allowlisted, and now the value. A credential in an allowlisted header is
    # unusual but not impossible, and the body scanner already knows the
    # shapes. A finding refuses the header rather than redacting it: a
    # redacted value is neither the truth nor absent.
    finding = _value_looks_like_a_credential(text)
    if finding:
        return {
            "name": str(name),
            "normalized": normalized,
            "decision": REFUSED_VALUE,
            "why": f"the value matched a credential shape: {finding}",
        }

    return {
        "name": str(name),
        "normalized": normalized,
        "decision": KEPT,
        "why": "on the allowlist, value inspected and clean",
    }


def _value_looks_like_a_credential(value: str) -> str | None:
    """Ask the body secret scanner, rather than inventing a second set of rules.

    Composed on purpose: Gate 95D already knows what a JWT, a bearer token and
    a private key look like, and two copies of those patterns would drift.
    """
    if not value.strip():
        return None
    try:
        from nativeforge.services.raw_payload_secret_scan_service import (
            scan_payload_for_secrets,
        )
    except ImportError:  # pragma: no cover - the scanner is part of the repo
        return None

    try:
        result = scan_payload_for_secrets(body=value)
    except Exception:  # noqa: BLE001 - a scanner failure must not admit a value
        # Fail closed. That is right for safety and wrong for diagnosis: Gate
        # 160 called this with the wrong keyword, every call raised, and every
        # allowlisted header was refused with a plausible-looking reason. The
        # test that catches it is the one asserting a SAFE header survives.
        return "scanner_failed_so_the_value_is_refused"

    findings = result.get("findings") or []
    if findings:
        kinds = sorted({str(f.get("kind") or "unknown") for f in findings})
        return ",".join(kinds)
    return None


def filter_response_metadata(
    *, headers: Any = None, max_headers: int = MAX_HEADERS
) -> dict[str, Any]:
    """Keep only what the allowlist permits, and say what happened to the rest."""
    if headers is None:
        supplied: list[tuple[Any, Any]] = []
    elif isinstance(headers, dict):
        supplied = list(headers.items())
    elif isinstance(headers, list | tuple):
        supplied = [
            (pair[0], pair[1])
            for pair in headers
            if isinstance(pair, list | tuple) and len(pair) == 2
        ]
    else:
        supplied = []

    blocked: list[str] = []
    if headers is not None and not isinstance(headers, dict | list | tuple):
        blocked.append("headers_are_not_a_mapping_or_pairs")
    if len(supplied) > int(max_headers):
        blocked.append(f"too_many_headers:{len(supplied)}>{int(max_headers)}")
        supplied = []

    decisions = [classify_header(name, value) for name, value in supplied]

    kept: dict[str, str] = {}
    for decision, (_name, value) in zip(decisions, supplied, strict=False):
        if decision["decision"] == KEPT:
            kept[decision["normalized"]] = str(value)

    by_decision = {
        name: sum(1 for d in decisions if d["decision"] == name)
        for name in DECISIONS
    }

    refused_names = sorted(
        d["normalized"] for d in decisions if d["decision"] != KEPT
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "usable": not blocked,
            "blocked_reasons": sorted(blocked),
            "safe_headers": dict(sorted(kept.items())),
            "safe_header_count": len(kept),
            "headers_supplied": len(supplied),
            "headers_refused": len(supplied) - len(kept),
            "by_decision": by_decision,
            # Names only, never values. Reporting the value of a refused
            # header would defeat refusing it.
            "refused_header_names": refused_names,
            "decisions": decisions,
            "allowlist": sorted(ALLOWED_RESPONSE_HEADERS),
            "known_credential_headers": sorted(CREDENTIAL_HEADERS),
            "policy": "allowlist_by_header_name",
            "max_header_value_length": MAX_HEADER_VALUE_LENGTH,
            "max_headers": int(max_headers),
            # The four this gate is required to refuse, checked by membership
            # rather than by hoping the allowlist happens to exclude them.
            "refuses_authorization": "authorization" not in
            ALLOWED_RESPONSE_HEADERS,
            "refuses_cookie": "cookie" not in ALLOWED_RESPONSE_HEADERS,
            "refuses_set_cookie": "set-cookie" not in ALLOWED_RESPONSE_HEADERS,
            "refuses_api_key": "x-api-key" not in ALLOWED_RESPONSE_HEADERS,
        }
    )


def metadata_filter_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Refuse a filter result that kept something it should not have."""
    fails: list[str] = []

    safe = result.get("safe_headers") or {}

    # Nothing kept may be a known credential header, or off the allowlist.
    for name in safe:
        normalized = normalize_header_name(name)
        if normalized in CREDENTIAL_HEADERS:
            fails.append(f"kept_a_credential_header:{normalized}")
        if normalized not in ALLOWED_RESPONSE_HEADERS:
            fails.append(f"kept_a_header_off_the_allowlist:{normalized}")
        if normalized != str(name):
            fails.append(f"kept_a_header_under_an_unnormalized_name:{name}")

    # The allowlist and the credential set must not overlap, or a header would
    # be both permitted and known-dangerous.
    overlap = ALLOWED_RESPONSE_HEADERS & CREDENTIAL_HEADERS
    if overlap:
        fails.append(f"the_allowlist_contains_a_credential_header:{sorted(overlap)}")

    # The counts must account for every supplied header.
    decisions = result.get("decisions") or []
    by_decision = result.get("by_decision") or {}
    if by_decision and sum(by_decision.values()) != len(decisions):
        fails.append("by_decision_does_not_account_for_every_header")
    if result.get("safe_header_count") != len(safe):
        fails.append("safe_header_count_disagrees_with_the_kept_headers")
    supplied = int(result.get("headers_supplied") or 0)
    if decisions and supplied != len(decisions):
        fails.append("headers_supplied_disagrees_with_the_decisions")
    if supplied and int(result.get("headers_refused") or 0) != supplied - len(safe):
        fails.append("headers_refused_does_not_account_for_the_difference")

    for decision in decisions:
        if decision.get("decision") not in DECISIONS:
            fails.append(f"decision_outside_vocabulary:{decision.get('decision')}")
        if not str(decision.get("why") or "").strip():
            fails.append(f"decision_without_a_reason:{decision.get('normalized')}")

    # The four required refusals, asserted rather than assumed.
    for flag in (
        "refuses_authorization",
        "refuses_cookie",
        "refuses_set_cookie",
        "refuses_api_key",
    ):
        if flag in result and not result.get(flag):
            fails.append(f"policy_broken:{flag}")

    if result.get("policy") not in (None, "allowlist_by_header_name"):
        fails.append(f"unexpected_policy:{result.get('policy')}")

    return sorted(set(fails))
