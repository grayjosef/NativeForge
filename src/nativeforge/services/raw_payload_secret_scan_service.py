"""Raw payload secret scan and redaction (Gate 95D).

Detects credential-shaped content in a raw source response and blocks promotion
until it is redacted. It reports **what kind** of finding and **where**, never
the value.

## Why this is not optional

Gate 89 found a 143-character HS256 JWT committed inside
``fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json``, tracked
since 2026-06-20 and not gitignored. Nobody put it there deliberately - it
arrived inside a recorded API response and was committed with it.

Raw API responses are exactly where the next one arrives: a pre-signed URL, a
session token echoed in a body, an ``Authorization`` header captured alongside
the request. A store that keeps response bodies without scanning them is a
machine for committing credentials.

That fixture is **not modified by this gate** - doing so is a separate,
explicitly approved action. It is the scanner's proving case instead: a test
builds a payload of the same shape locally and asserts the scanner catches it.

## Never print the value

``finding`` carries ``kind``, ``location``, ``match_length`` and a
``fingerprint`` - the first 8 hex of a SHA-256 of the matched text. The
fingerprint is enough to tell two findings apart or to confirm a redaction
changed something; it is not enough to reconstruct the secret.

An invariant checks that no field of a finding contains the matched text, so a
future edit that helpfully includes "the offending value" fails the suite.

## Redaction preserves structure

``[REDACTED]`` replaces the value, not the key and not the surrounding JSON. A
reviewer can still see that the response *had* an ``access_token`` field and
where - which is the thing worth knowing - without the token being there.

The redacted body hashes differently from the original by construction, and an
invariant asserts it. Same hash after redaction means nothing was redacted.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SCHEMA_VERSION = "nf_raw_payload_secret_scan_v1"

REDACTION_PLACEHOLDER = "[REDACTED]"

SCAN_STATUSES = frozenset({"pending", "clean", "findings_blocked", "failed"})
# Affirmative: only `clean` permits promotion. `pending` is not a pass.
SCAN_SATISFYING = frozenset({"clean"})

FINDING_KINDS = frozenset(
    {
        "jwt_token",
        "authorization_header",
        "bearer_token",
        "access_token",
        "refresh_token",
        "client_secret",
        "api_key",
        "password",
        "private_key",
        "session_cookie",
        "url_query_credential",
    }
)

# Key names whose *value* is a secret. Matched case-insensitively against JSON
# keys, form fields, and header names.
SECRET_KEY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("access_token", r"access[_-]?token"),
    ("refresh_token", r"refresh[_-]?token"),
    ("client_secret", r"client[_-]?secret"),
    ("api_key", r"(?:api[_-]?key|apikey|x[_-]?api[_-]?key|subscription[_-]?key)"),
    ("password", r"(?:password|passwd|pwd)"),
    ("private_key", r"private[_-]?key"),
    ("session_cookie", r"(?:set-cookie|session[_-]?id|sessionid|jsessionid|phpsessid)"),
    ("authorization_header", r"authorization"),
)

# Query-parameter names that are credentials *in a URL* and nowhere else.
#
# Gate 98D found the hole these close: an error message reading
# `GET https://host/v1/x?api_key=... failed` kept its key, because the
# `key=value` form below is anchored `^...$` and only ever matched a whole line.
# A URL sits mid-sentence, so it never matched.
#
# These are deliberately *not* in SECRET_KEY_PATTERNS. `token` and `sig` as JSON
# field names are usually pagination cursors - Grants.gov returns one on every
# page - and treating those as secrets would set `findings_blocked` on every
# payload and stop promotion entirely. As a URL query parameter the same name is
# a credential. The distinction is the position, so the pattern carries it.
URL_QUERY_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "url_query_credential",
        r"(?:x-amz-signature|x-amz-credential|x-amz-security-token|"
        r"signature|sig|sas|token|api[_-]?token|auth|access[_-]?key|secret)",
    ),
)

# Value characters permitted in a query-string credential: everything up to the
# next parameter, whitespace, or a quote/bracket that would end the URL.
_URL_QUERY_VALUE = r"[^&\s\"'<>\\\]})]{4,}"

# A JWT: three base64url segments, and a header segment that starts `eyJ`
# because `{"` base64url-encodes to `eyJ`.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")

# `Bearer <token>` in a header or body.
_BEARER_RE = re.compile(r"\b[Bb]earer\s+([A-Za-z0-9._\-+/=]{16,})")

# PEM blocks.
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
)

# `"key": "value"` / `key=value` where the key looks secret. The value group is
# what gets redacted; the key survives.
def _key_value_regexes() -> list[tuple[str, re.Pattern[str]]]:
    out: list[tuple[str, re.Pattern[str]]] = []
    for kind, key_pattern in SECRET_KEY_PATTERNS:
        out.append(
            (
                kind,
                re.compile(
                    rf'("(?:{key_pattern})"\s*:\s*")([^"]{{4,}})(")',
                    re.IGNORECASE,
                ),
            )
        )
        out.append(
            (
                kind,
                re.compile(
                    rf"^((?:{key_pattern})\s*[:=]\s*)(\S{{4,}})$",
                    re.IGNORECASE | re.MULTILINE,
                ),
            )
        )
        # The same key name inside a URL query string, which the anchored form
        # above cannot reach.
        out.append(
            (
                kind,
                re.compile(
                    rf"([?&](?:{key_pattern})=)({_URL_QUERY_VALUE})",
                    re.IGNORECASE,
                ),
            )
        )
    for kind, key_pattern in URL_QUERY_SECRET_PATTERNS:
        out.append(
            (
                kind,
                re.compile(
                    rf"([?&](?:{key_pattern})=)({_URL_QUERY_VALUE})",
                    re.IGNORECASE,
                ),
            )
        )
    return out


_KEY_VALUE_REGEXES = _key_value_regexes()

# A value this short or this shaped is not a credential. Keeps the scanner from
# flagging `"password": "n/a"` and burying real findings in noise.
_BENIGN_VALUES = frozenset(
    {
        "",
        "null",
        "none",
        "n/a",
        "na",
        "true",
        "false",
        "unknown",
        "redacted",
        REDACTION_PLACEHOLDER.lower(),
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _fingerprint(value: str) -> str:
    """8 hex of SHA-256. Enough to compare, not enough to reconstruct."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def body_hash(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _is_benign(value: str) -> bool:
    stripped = value.strip().strip("\"'")
    return stripped.lower() in _BENIGN_VALUES or len(stripped) < 4


def _finding(kind: str, *, location: str, matched: str) -> dict[str, Any]:
    """A finding never carries the value it found."""
    return {
        "kind": kind,
        "location": location,
        "match_length": len(matched),
        "fingerprint": _fingerprint(matched),
    }


def scan_payload_for_secrets(
    *, body: Any = None, headers: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Scan a response body and headers. Returns findings without values."""
    text = str(body or "")
    findings: list[dict[str, Any]] = []

    for match in _JWT_RE.finditer(text):
        findings.append(
            _finding("jwt_token", location="body", matched=match.group(0))
        )

    for match in _BEARER_RE.finditer(text):
        findings.append(
            _finding("bearer_token", location="body", matched=match.group(1))
        )

    for match in _PRIVATE_KEY_RE.finditer(text):
        findings.append(
            _finding("private_key", location="body", matched=match.group(0))
        )

    for kind, pattern in _KEY_VALUE_REGEXES:
        for match in pattern.finditer(text):
            value = match.group(2)
            if _is_benign(value):
                continue
            findings.append(
                _finding(kind, location="body", matched=value)
            )

    # Headers are scanned by name: the name says whether the value is a secret.
    for raw_name, raw_value in (headers or {}).items():
        name = str(raw_name)
        value = str(raw_value)
        lowered = name.lower()
        for kind, key_pattern in SECRET_KEY_PATTERNS:
            if re.fullmatch(key_pattern, lowered) and not _is_benign(value):
                findings.append(
                    _finding(kind, location=f"header:{name}", matched=value)
                )
                break
        else:
            if _JWT_RE.search(value):
                findings.append(
                    _finding("jwt_token", location=f"header:{name}", matched=value)
                )
            elif _BEARER_RE.search(value):
                findings.append(
                    _finding("bearer_token", location=f"header:{name}", matched=value)
                )

    # Deduplicate: the same value found twice by two patterns is one finding.
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for finding in findings:
        key = (finding["kind"], finding["location"], finding["fingerprint"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)

    unique.sort(key=lambda f: (f["location"], f["kind"], f["fingerprint"]))

    by_kind = {kind: 0 for kind in sorted(FINDING_KINDS)}
    for finding in unique:
        by_kind[finding["kind"]] += 1

    status = "findings_blocked" if unique else "clean"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scan_status": status,
            "clean": not unique,
            "finding_count": len(unique),
            "findings": unique,
            "by_kind": by_kind,
            "body_hash": body_hash(text),
            "secret_values_included": False,
            "fabricated": False,
        }
    )


def redact_payload(*, body: Any = None) -> dict[str, Any]:
    """Replace secret values with a placeholder, preserving structure."""
    original = str(body or "")
    redacted = original
    replacements = 0

    def _sub_group2(match: re.Match[str]) -> str:
        nonlocal replacements
        if _is_benign(match.group(2)):
            return match.group(0)
        replacements += 1
        tail = (
            match.group(3)
            if match.lastindex and match.lastindex >= 3
            else ""
        )
        return f"{match.group(1)}{REDACTION_PLACEHOLDER}{tail}"

    for _kind, pattern in _KEY_VALUE_REGEXES:
        redacted, _ = pattern.subn(_sub_group2, redacted)

    def _sub_whole(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return REDACTION_PLACEHOLDER

    redacted, n = _JWT_RE.subn(_sub_whole, redacted)
    redacted, n = _PRIVATE_KEY_RE.subn(_sub_whole, redacted)

    def _sub_bearer(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return match.group(0).replace(match.group(1), REDACTION_PLACEHOLDER)

    redacted, n = _BEARER_RE.subn(_sub_bearer, redacted)

    original_hash = body_hash(original)
    redacted_hash = body_hash(redacted)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "redaction_status": "completed" if replacements else "not_required",
            "replacements": replacements,
            "redacted_body": redacted,
            "original_body_hash": original_hash,
            "redacted_body_hash": redacted_hash,
            # A redaction that did not change the hash redacted nothing.
            "hash_changed": redacted_hash != original_hash,
            "placeholder": REDACTION_PLACEHOLDER,
            "secret_values_included": False,
            "fabricated": False,
        }
    )


def scan_and_redact(
    *, body: Any = None, headers: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Scan, redact if needed, and re-scan to prove the redaction worked."""
    first = scan_payload_for_secrets(body=body, headers=headers)
    if first["clean"]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scan_status": "clean",
                "redaction_status": "not_required",
                "initial_findings": 0,
                "residual_findings": 0,
                "redacted_body": str(body or ""),
                "original_body_hash": first["body_hash"],
                "redacted_body_hash": first["body_hash"],
                "hash_changed": False,
                "safe_to_store": True,
                "secret_values_included": False,
                "fabricated": False,
            }
        )

    redaction = redact_payload(body=body)
    # Re-scan rather than assume: a pattern that matched may not have redacted.
    second = scan_payload_for_secrets(body=redaction["redacted_body"], headers=None)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scan_status": "clean" if second["clean"] else "findings_blocked",
            "redaction_status": redaction["redaction_status"],
            "initial_findings": first["finding_count"],
            "residual_findings": second["finding_count"],
            "residual_kinds": sorted({f["kind"] for f in second["findings"]}),
            "redacted_body": redaction["redacted_body"],
            "original_body_hash": redaction["original_body_hash"],
            "redacted_body_hash": redaction["redacted_body_hash"],
            "hash_changed": redaction["hash_changed"],
            "safe_to_store": second["clean"],
            "secret_values_included": False,
            "fabricated": False,
        }
    )


def secret_scan_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if result.get("secret_values_included") is not False:
        fails.append("result_claimed_to_include_secret_values")

    status = result.get("scan_status")
    if status is not None and status not in SCAN_STATUSES:
        fails.append("scan_status_out_of_vocabulary")

    for finding in result.get("findings") or []:
        kind = finding.get("kind")
        if kind not in FINDING_KINDS:
            fails.append(f"finding_kind_out_of_vocabulary:{kind}")
        if not finding.get("location"):
            fails.append("finding_without_a_location")
        # A finding must not carry the value. Fingerprint is 8 hex; a field
        # longer than that is the value creeping back in.
        fingerprint = str(finding.get("fingerprint") or "")
        if len(fingerprint) != 8:
            fails.append("finding_fingerprint_is_not_8_hex")
        for key, value in finding.items():
            if key in {"kind", "location", "fingerprint"}:
                continue
            if isinstance(value, str) and len(value) > 16:
                fails.append(f"finding_field_may_contain_a_secret_value:{key}")

    # `clean` is derived, never asserted beside the findings.
    if "clean" in result and result.get("clean") != (not result.get("findings")):
        fails.append("clean_flag_disagrees_with_findings")
    if status == "clean" and result.get("findings"):
        fails.append("clean_status_with_findings")

    # A redaction that changed nothing did not redact.
    if result.get("redaction_status") == "completed" and not result.get(
        "hash_changed"
    ):
        fails.append("redaction_completed_without_a_hash_change")
    if result.get("safe_to_store") and result.get("residual_findings"):
        fails.append("safe_to_store_with_residual_findings")

    return fails
