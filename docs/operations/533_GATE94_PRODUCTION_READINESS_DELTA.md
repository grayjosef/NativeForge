# 533 — Gate 94: production readiness delta

Supersedes doc 529 (Gate 93) as the current readiness position.

## Readiness is unchanged

| | Gate 93 | Gate 94 |
| --- | --- | --- |
| controlled customer pilot | NO_GO | NO_GO |
| production rollout | NO_GO | NO_GO |
| login live | no | no |
| production storage | no | no |
| customer persistence | no | no |
| pen-test passed | no | no |
| live source coverage | none | none |
| sources monitored | 0 | 0 |
| collectors live | 0 | 0 |
| crawler live | 0 | 0 |

**No collectors were activated. No URLs were fetched. No live coverage is
claimed. Source monitoring remains zero.**

## Baseline X untouched

```text
total_records                 185
recorded_verified_records      18
live_records                    0
monitored_sources               0
baseline_quality_score     0.0865
improvement_claim_allowed   false
```

## What changed

Gate 93 could say only that accidental *Phase 1 collector* activation was
impossible. It could not say that arbitrary live HTTP was impossible, and doc
529 said so plainly. **Gate 94 makes the codebase-wide claim true.**

```text
before                                    after
6 egress call sites, 1 guarded            6 of 6 through one guard
2 user-agent strings                      1, with a reachable contact
robots timeout => fetch permitted         robots timeout => fetch refused
2.0s interval in the fetcher              5.0s floor, clamped
blacklist defined, never consulted        consulted before every request
breaker defined, never consulted          consulted before every request
1 allow_live_fetch default True           0
OIDC scheme checked after the request     checked before it
no scan; a 7th site would go unnoticed    885 files scanned every suite run
```

## The count was wrong, and that is the lesson

Gate 93 reported four call sites. It searched for `httpx`. Two more reached the
network through `urllib.request` — a Slack webhook and an OIDC JWKS fetch — and
neither appeared in that survey.

A hand-written survey is a snapshot of what the author thought to look for. The
scanner in this gate is the durable version: it parses every file under
`src/nativeforge` on every suite run, and three tests plant violations in a temp
tree to prove a clean report means the scan works rather than that it found
nothing.

## One security defect found and fixed

The OIDC JWKS fetch executed `urllib.request.urlopen(jwks_url)` and *then*
checked whether the URL was https, with a comment reading "https enforced
below". Below was after the connection opened, so an `http://` JWKS URL was
contacted in plaintext and only then rejected — the check protected the response
and not the request. Moved above the call.

## What is still not true

- Nothing collects. All five Phase 1 sources remain `not_active`, and the guard
  now refuses their requests on top of that.
- Five `polite_http_get` callers are inert by default and need deliberate
  opt-in, which none of them has.
- The guard decides; no scheduler calls it, because there is no scheduler.
- `identity_verification` and `operational_alert` requests are permitted when
  configured — those are infrastructure paths, not source collection, and they
  are what the `purpose` dimension exists to keep separate. Both kept their own
  deny-by-default flags (`allow_network=False`, `force_dry_run=True`) *and* now
  pass the shared guard, so neither one is trusted on its own say-so.

## Blockers before Phase 1 collection can begin

Unchanged from doc 529, minus item 2, which this gate closed:

```text
1  raw payload store implementation      required by all five sources
2  SAM.gov API key + role                10/day without it is unusable
3  185 queue items reviewed              148 terms + 62 human-only + 4 SPA + 1 SAM
4  four SPA terms pages read by a human  "no terms found" is not "no terms exist"
5  Simpler.Grants.gov tribal enum        undocumented; needs the live Swagger
6  scheduler + breaker wiring            the breaker is now consulted by the
                                         guard; nothing schedules yet
```

## Carried forward unresolved

`docs/operations/502_GATE89_COMPLETED_CORPUS_PROVENANCE_ATTESTATION_DRAFT.md`
remains untracked by design, still awaiting approval of a filled attestation.
Gate 94 did not touch it.
