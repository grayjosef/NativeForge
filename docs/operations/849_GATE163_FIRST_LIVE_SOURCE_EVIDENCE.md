# 849 — Gate 163: the first live source collection, and what each fact is

Twelve separate facts. They are separate because collapsing any two of them is
how a system comes to claim more than it knows — and one of them is a defect in
this gate's own evidence capture.

## 1. Source authorization

`nf-seed-2026-api-grants-gov-search2`, added to the registry because none of
the 177 existing rows had host `api.grants.gov`: all six grants.gov rows were
individual opportunity pages, not the API.

MAYHEM recorded terms, human review and activation through the repository's own
decision model. Each is signed — `reviewed_by` and `reviewed_at` — and
migration 0048 makes an approved decision without a signer unwritable. Nothing
infers any of them from the registry row existing.

Activation joins on the stable `source_id` that migration 0049 added, never on
the display name `source_name`. A fact arriving through the legacy name join is
a named invariant failure.

## 2. Robots preflight

One bounded GET to `https://api.grants.gov/robots.txt`, under a
`robots_preflight` warrant: path exactly `/robots.txt`, method GET, no
live-fetch opt-in required, and no authority to collect anything.

Preflight permission and collection permission are different warrants. A
preflight warrant presented for `search2` is refused, and that refusal is
proven.

## 3. The RFC 9309 `unavailable` verdict

The preflight returned **403** with 42 bytes,
`{"message":"Missing Authentication Token"}`, sha256
`f249b63cb2fcb66b47e86f906c98f8fd912e82dd035b4e53d7e72fc1960cfd16`.

The parser had mapped every status at or above 400 to `unreachable`, which
blocks collection. RFC 9309 §2.3.1 makes 4xx **"unavailable"** — crawlers MAY
access — and reserves `unreachable` for 5xx and network failure. The verdict
was re-derived from the stored bytes and status; nothing was refetched and the
403 is preserved exactly as it arrived.

RFC 9309 §2 also says robots.txt rules are not a form of access authorization,
and this repository agrees. The 403 means the robots protocol adds no
restriction for this authority. It is not permission to collect.

Robots evidence is keyed per authority — scheme, host, port — as the RFC scopes
it.

## 4. Runtime readiness

Measured in the process that dispatched, not inherited from a verifier run.
Three of the four required lanes are unexercised rather than broken when read
cold: `build_raw_payload_health` takes no connection and "reports the lane from
results somebody else measured", so a cold call reports `table_exists` unmet
while the table holds rows.

`source_runtime_lane_exerciser_service` performs the real operations —
a claim and a refused duplicate and a reclaim after lease expiry, an idempotent
enqueue re-read on a *new* connection, a payload round-trip with a refused
conflict and a refused oversize and a detected tamper — then cleans up by its
own fixture ids and counts what it removed. 6 rows created, 6 cleaned, residue
0.

It commits, because `survives_restart` cannot be produced inside a transaction
that is rolled back. A savepoint would have turned that condition into
something nothing measures.

## 5. Source-specific live-fetch opt-in

A third `decision_kind` in the decision table, not a flag. It inherits 0048's
constraints, so an opt-in nobody signed cannot be written. The unique index is
`(organization_id, source_id, decision_kind)`: opting in a second source means
a second row and a second signature. There is no shape in this schema that
opts in "everything authorized", which matters because 178 registry rows are
one terms decision away from being authorized.

Recorded for exactly one source.

## 6. The request warrant

`warrant_kind = source_collection`, which requires everything the preflight
required plus the attribution fact, the robots fact and the live-fetch opt-in.

The transport carried:

```json
{
  "authorized_source_id": "nf-seed-2026-api-grants-gov-search2",
  "authorized_host": "api.grants.gov",
  "warrant_kind": "source_collection",
  "legacy_env_flag_required": false
}
```

`ENV_ALLOW_LIVE_NETWORK` was absent from the process and is not what permitted
the request. Gate 77B stayed enforced and became authorization-aware.

## 7. The actual live collection

One POST to `https://api.grants.gov/v1/api/search2`.

```json
{"keyword": "tribal", "oppStatuses": "posted|forecasted", "rows": 1}
```

`rows: 1` because one record proves the path. The adapter's own body builder
would have used the source's display name — "Grants.gov Search2 API" — as the
keyword, which proves transport and finds nothing a Tribe could apply for.

No redirects, no cookies, no credentials, no retries, bounded timeout, one
host closed over at construction. `fetchOpportunity` was not called. No second
request was made and no second source was contacted.

## 8. Raw evidence

11131 bytes, persisted exactly as received.

```text
payload id   c35bbe3c1a84b1f42362ed65c114e44838d14758a274c994fe144732b310c4ec
sha256       eb4cc7cb76d278b9f4ab9aad7375ed0481faa6ff5827786452dc74491c0f1712
```

Hash verified on write and re-verified on readback. Response headers persisted
through the safe-header filter; the URL is fingerprinted and discarded, because
query strings carry api keys.

## 9. Execution proof

One attempt row, `transport_kind = live`, `live_source_call = 1`,
`authorized_source_id` present, `execution_proof_available = 1`, linked to the
payload by hash.

Recording it required converting the attempt repository, which refused every
live attempt regardless of authorization — with `live_source_call = False`
hardcoded under the comment "Never anything else. The database refuses it",
which stopped being true at migration 0050. The two halves of its own "two
refusals for one fact" pair had drifted: the CHECK permitted an authorized live
row and the repository refused every live row.

## 10. Normalization

One opportunity, from the one response:

```text
number      O-BJA-2026-172662
title       U.S. Department of Justice FY26 Coordinated Tribal Assistance
            Solicitation
agency      USDOJ-OJP-BJA
open date   07/24/2026
```

317 opportunities matched; 1 was requested and 1 was returned. No second
request was made to retrieve any of the others.

## 11. Attribution

The terms decision carries guard status `ATTRIBUTION_REQUIRED`, and the
attribution fact resolves to `present_and_verbatim` — verified against the
required notice text rather than assumed from the source's identity. Output
from this source may not reach a customer surface without it.

## 12. The HTTP transport-status capture defect

**HTTP status: UNKNOWN / not captured.**

Transport status was not captured by the first-live runner because it read the
wrong response field. The boundary returns `status_code` and `bytes_received`
at the top level; the runner read `response_status` and `body_size_bytes`. No
second request was made. The application-level response reported
`errorcode = 0` and `msg = "Webservice Succeeds"`, but HTTP status remains
UNKNOWN.

The two names failed differently, and the second is the more instructive one.
`response_status` does not exist in the result at all. `body_size_bytes` *does*
exist — nested under `request`, where it describes the REQUEST body — so
reading it at the top level found nothing while looking like a perfectly
plausible key. A name that is real somewhere else in the same structure is
harder to catch than one that is simply wrong.

These are separate facts and are recorded separately:

```text
HTTP status                  UNKNOWN / not captured
application errorcode        0
application message          "Webservice Succeeds"
```

The status is **not** backfilled as 200. `errorcode: 0` is an application fact
and an HTTP status is a transport fact; inferring one from the other is exactly
the declared-versus-derived defect this campaign exists to remove. Recovering
it would need a second request, which this gate forbids.

The runner is fixed for future calls. The first call's record keeps
`http_status = NULL`, because that is what was observed.

This is an evidence-quality defect, not grounds for a refetch.

## What the ten world-state layers became

"Nothing live has ever happened" was encoded in ten places. Each became "this
can only happen under the authorized condition", and none was weakened to
generic nonzero acceptance:

```text
1  four CHECK constraints (0047)   a live row must NAME its authorization
2  health lanes (158/160/161)      no UNAUTHORIZED fetch occurred
3  a chokepoint finding            no live dispatch without a policy
4  verifier assertions             no UNAPPROVED real source has a decision
5  repository payload invariants   unauthorized_live_rows, not any live row
6  Gate 77B's environment flag     authorization-aware, flag still enforced
7  the transport boundary          a live dispatch must name its authorization
8  the attempt repository          an authorized live attempt is recordable
9  the envelope hermetic invariant every attempt is hermetic OR authorized live
10 the attempt counters            unauthorized_live_attempts, and three more
```

Layer 9 was the one that mattered most, because the Gate 162 synthetic fixture
derives its own `collector_status` and `runtime_status` from that lane — so one
unconvertible invariant made a *fixture's* permitted branch unreachable, which
is the same defect in the opposite direction.
