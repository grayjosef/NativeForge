# 537 — Gate 95D: secret scan and redaction contract

**Secret scan and redaction are required before promotion.** No collectors were
activated, no live fetch occurred, no source monitoring started. This does not
change Baseline X live coverage.

## Why

Gate 89 found a 143-character HS256 JWT committed inside
`fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json`, tracked
since 2026-06-20 and not gitignored. Nobody put it there deliberately — it
arrived inside a recorded API response and was committed along with it.

Raw API responses are where the next one arrives: a pre-signed URL, a session
token echoed in a body, an `Authorization` header captured beside the request.
**A store that keeps response bodies without scanning them is a machine for
committing credentials.**

## The Gate 89 fixture is the proving case, not the subject

This gate does **not** modify that fixture. Mutating a committed transport
artifact is its own action needing its own approval, and doing it as a side
effect of building a scanner would destroy the only evidence of what the corpus
actually contained.

Instead the scanner is proved against it two ways:

1. It was run against the real file during the survey. It reports
   `findings_blocked`, one `jwt_token` finding, location `body` — and prints no
   value.
2. A test reconstructs the same *shape* locally (a JWT nested in an opportunity
   payload) with a synthetic token and asserts the scanner catches it.

A separate test asserts the fixture is still present and unmodified.

## Ten finding kinds

```text
jwt_token           authorization_header   bearer_token
access_token        refresh_token          client_secret
api_key             password               private_key
session_cookie
```

Detected in the body by pattern, and in headers by name — a header's name is
what says whether its value is a secret.

## Findings never carry the value

```json
{"kind": "access_token", "location": "body", "match_length": 24,
 "fingerprint": "ded96e00"}
```

`fingerprint` is the first 8 hex of a SHA-256 of the matched text: enough to
tell two findings apart or to confirm a redaction changed something, not enough
to reconstruct the secret.

An invariant fails any finding carrying a string field longer than 16 characters
outside the three allowed keys — so a future edit that helpfully includes "the
offending value" fails the suite rather than shipping.

## Benign values are not findings

`{"password": "n/a"}`, `{"api_key": "none"}`, and empty values scan clean. A
scanner that flags those buries the real findings in noise, and a noisy scanner
gets ignored — which is the same outcome as not having one.

## Redaction preserves structure

```text
{"access_token":"<secret>"}   ->   {"access_token":"[REDACTED]"}
Authorization: Bearer <token> ->   Authorization: Bearer [REDACTED]
```

The key survives, and so does the surrounding JSON. A reviewer can still see
that the response *had* an `access_token` and where — which is the thing worth
knowing.

## The redacted hash must differ

`hash_changed` is reported, and an invariant fails a result claiming
`redaction_status: completed` without it. **Same hash after redaction means
nothing was redacted**, and a redaction that silently did nothing is worse than
none: it produces a record asserting the payload is clean.

## Re-scan, do not assume

`scan_and_redact` scans, redacts, then **scans the redacted body again** and
reports `residual_findings`. A pattern that matched is not proof that the
substitution removed it. `safe_to_store` requires the second scan to come back
clean, and the local store performs the same re-check before writing rather than
trusting its caller.
