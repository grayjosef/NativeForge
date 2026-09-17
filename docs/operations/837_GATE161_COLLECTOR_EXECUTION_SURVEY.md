# 837 — Gate 161: what can already reach a host, and what is missing

Read-only survey. Every value was measured by parsing the code it describes.

Gate 161 is the first gate permitted to contain outbound-capable code, so the
first question is not *what should we build* but **exactly how much of this
already exists and where the network can currently be reached.**

## The egress surface, by AST

```text
files scanned                    1174
modules importing a network lib     8
unapproved                          0
approved                            8
enforcement report clean         True
```

Every one of the eight is on `hermetic_network_enforcement_service`'s
`APPROVED_NETWORK_SITES` list, which carries a reason and a named guard per
entry and has no wildcard.

```text
grants_gov_search_api_adapter_service      httpx            source collection
polite_http_fetch_service                  httpx            source collection
real_url_resolver_service                  httpx            source collection
oidc_token_verification_service            urllib.request   identity
oidc_provider_discovery_service            urllib.request   identity
oidc_token_exchange_client_service         httpx            identity
feedback_slack_alert_service               urllib.request   operational alert
gate37_production_grade_hardening_service  socket           127.0.0.1 only
```

## There are already two guards, and three source transports

```text
polite_http_fetch_service      live_network_guard_service.build_live_network_decision
real_url_resolver_service      live_network_guard_service.build_live_network_decision
grants_gov_search_api_adapter  hermetic_test_guard_service.assert_live_network_allowed
```

Gate 94B's `live_network_guard_service` is already the decision layer — "every
outbound request in `src/nativeforge` passes through here first. The guard
decides; it never fetches." It denies by default, derives its requirement set
from `purpose` and `collector_type`, and states that nobody self-exempts.

So the gap is **not** "adapters bypass a transport". It is narrower and more
precise: there are three source-collection transports under two different
guards, and no single boundary that a new execution envelope can be built
against.

## Every transport is already injectable

This is the measurement that shapes the whole gate:

```python
polite_http_get(url, ..., transport=None)
search_grants_gov_opportunities(source, http_post=None, fetch_mode=...)
resolve_url_real(url, ..., fetcher=None, ...)
```

Each takes an injected callable and falls back to an httpx default. The httpx
import is the **default implementation**, not the interface. That is already the
right shape, and Gate 161's transport should follow it rather than invent a
different one.

`polite_http_get` also already takes `terms_status`, `activation_status`,
`collector_status`, `credential_status` and `collector_type` — it composes the
guard's requirements rather than deciding for itself.

## The adapter layer does not touch the network

```text
real_tier1_live_fetch_service                  network imports: none  injected fetcher
tier1_batch_live_fetch_service                 network imports: none
tier2_state_batch_live_fetch_service           network imports: none
tier3_foundation_batch_live_fetch_service      network imports: none
staging_tier1_dry_fetch_service                network imports: none  injected fetcher
tier3_platform_fetch_dispatch_service          network imports: none
source_fetch_adapter_contract_service          network imports: none  injected fetcher
source_ingestion_tier1_federal_adapter_service network imports: none
```

Thirty-one adapter and fetch modules; none of them imports a network library.
The composition discipline already holds at that layer.

## Gates 156 to 160 import nothing network-capable

```text
source_collection_scheduler_loop_service          0
source_collection_worker_runtime_service          0
source_collection_orchestration_runtime_service   0
source_raw_payload_persistence_service            0
source_collection_raw_payload_repository          0
```

The whole runtime spine built in this block is inert. Gate 161 is where that
changes, and it changes by adding a boundary — not by adding an import to any of
those five.

## What is genuinely missing

```text
missing   a fixture-serving hermetic transport
          measured: zero modules named *transport*, zero that register a URL
          and return bytes. Every existing test injects an ad-hoc lambda.

missing   a single boundary a NEW execution envelope can be built against,
          composing Gate 94B's guard rather than adding a third guard

missing   a request builder. No module constructs a source request URL,
          method and query deterministically - each adapter does its own.

missing   execution attempt persistence. Gate 160 stores the RESPONSE; nothing
          records that an attempt was made, what transport served it, or what
          it refused.

missing   a definition of what execution proof requires. Gate 158 left
          `completed` unreachable precisely because nobody had written one.
```

## Could anything currently reach a live source by accident?

Measured: **no**, and for three independent reasons.

```text
1  the guard denies by default          allow_live_fetch=False, and every
                                        status defaults to its blocking member
2  zero sources are approved            activation_status is never
                                        activation_allowed for any source
3  the enforcement scan is clean        0 unapproved call sites over 1174 files
```

`polite_http_get` requires terms, activation, collector, robots and credential
to be affirmatively satisfied. With an empty allowlist the activation
requirement alone is unsatisfiable, so the live path is unreachable even if
somebody passed `allow_live_fetch=True`.

## The decision this gate must make about the three legacy transports

161C says a new transport should become "the single approved outbound
source-call chokepoint", and that adapters calling HTTP directly should be
refactored to compose it.

**Gate 161 does not refactor them.** The reasoning, stated rather than skipped:

```text
they are already guarded         two of three by Gate 94B, one by Gate 77B
they are already injectable      the httpx import is a default, not the
                                 interface
they are already enforced        the approved list names each one with a
                                 reason, and the scan proves nothing else
                                 reaches the network
they are not on the new path     the execution envelope does not call them
```

Rewriting three working, guarded, tested transports to route through a boundary
that has no live implementation would be a large change whose only effect today
is to move code. The risk is real and the benefit is deferred.

What Gate 161 does instead: the new boundary is the single chokepoint **for the
execution envelope**, the chokepoint verifier proves the envelope's modules
import nothing network-capable and that the approved list has not grown, and
Gate 162 — which decides what may go live — inherits a documented choice rather
than a silent one.

If Gate 162 or 163 routes a live source through the envelope, consolidating
`polite_http_fetch_service` behind the boundary becomes worth its risk, because
then it is on the path.

## What Gate 161 will build

```text
a transport boundary      protocol + dispatch, composing Gate 94B's guard.
                          Its LIVE implementation is policy-gated and has no
                          network import at all.
a hermetic transport      fixture responses: 200, 404, 429+Retry-After,
                          timeout, 5xx, malformed bytes. No socket, no DNS.
an execution policy       composing the guard, adding the hermetic/live
                          distinction
a request builder         deterministic, no credentials, URL fingerprinted
an execution service      job -> policy -> request -> transport -> Gate 160
an attempt record         migration 0047, if the survey of Gate 158/160
                          tables shows they cannot carry it
an execution proof        what a successful execution requires, and what
                          hermetic success does NOT imply
health + routes + chokepoint verifier + tests + artifacts + docs
```

## What it will not do

```text
contact a live source     live_transport_enabled = false, policy-gated
add to the approved list  the count stays 8
grow the guard            Gate 94B's decision is composed, not replaced
approve a source          zero, and Gate 162 owns that
accept a caller URL       the route builds its own request; no SSRF surface
```

**A hermetic execution is not a live execution.** The bytes come from a
registered fixture, and the proof this gate defines says so in its own field
names.
