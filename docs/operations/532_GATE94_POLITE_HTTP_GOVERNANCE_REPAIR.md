# 532 — Gate 94D/E: polite HTTP and resolver governance repair

**Before Gate 94, three of four known live-HTTP call sites bypassed every
guard.** After Gate 94, all live HTTP paths are deny-by-default, robots failures
fail closed, and a single NativeForge user-agent is enforced. No collectors were
activated, no live coverage is claimed, and source monitoring remains zero.

## polite_http_fetch_service, before and after

```text
                       before                     after
guard                  none                       live_network_guard_service
allow_live_fetch       n/a — always on            False by default
min interval           2.0s                       5.0s (Gate 92 floor)
user-agent             its own string             the one canonical string
robots unavailable     fetch permitted            fetch refused
robots 404             fetch permitted            fetch permitted (unchanged)
blacklist              not consulted              consulted before the request
circuit breaker        none                       consulted before the request
429/5xx backoff        none                       exponential, 30s → 900s cap
```

Five callers inherited the old behaviour:

```text
state_tribal_affairs_html_adapter_service.py:157, :192
tier3_foundation_batch_live_fetch_service.py:73
foundation_fluxx_embed_adapter_service.py:90
foundation_html_listing_adapter_service.py:171
```

All five are now inert by default. That is the intended outcome, not a
side-effect: five call sites were reaching the network with no guard, and the
correct resting state for each is refusal until someone opts it in deliberately.

## The robots fail-open, and why the fix is not "deny everything"

The old code collapsed four outcomes into one `None` and returned `True` for all
of them:

```python
if rp is None:
    return True          # missing, 4xx, 5xx, timeout — all "allowed"
```

A host whose robots.txt timed out read as fully permissive. That is exactly
backwards: a host under load is when a crawler should back off.

The repair distinguishes them rather than flipping them all to deny:

```text
allowed       200, and the rules permit this path
disallowed    200, and the rules forbid it
absent        404 — a real answer, conventionally "no restrictions"
fetch_failed  timeout, 5xx, connection error — we do not know
```

Denying on a 404 would have been the easy version and would have blocked most of
the 381-source registry for no reason. A 404 robots.txt is a host saying it has
no rules, not a host failing to answer.

## The floor is a floor

```python
interval = max(float(min_interval_seconds), MIN_REQUEST_INTERVAL_SECONDS)
```

A caller may be slower than 5.0s. It cannot be faster. The old parameter let a
caller pass anything, and the module's own default was already below Gate 92's
floor.

## Test seams preserved

`polite_http_get` keeps its signature and return shape and gains a `transport`
parameter; `resolve_url_real` keeps its `fetcher` parameter. Nothing was
removed — the functionality is guarded, not deleted.

An **injected transport is exempt from the guard**, deliberately. A recorded
transport reaches no network, and requiring permission to call one would only
push tests into setting `allow_live_fetch=True`, which is the opposite of what
this gate is for. The guard protects the real transport; the seam bypasses the
transport entirely.

## real_url_resolver_service

`allow_live_fetch` defaults to `False`; live resolution passes the guard as
`source_discovery`; the canonical user-agent is presented on the wire. Robots is
not consulted per-path here because the resolver checks whether a URL is alive
rather than crawling a site's content — the host blacklist and disallowed-path
rules still apply through the guard's `host_permitted` requirement.

## Two fixes outside the two named modules

**The OIDC scheme check ran after the request.**

```python
with urllib.request.urlopen(  # noqa: S310 - https enforced below
    jwks_url, timeout=...
) as resp:
    if not str(jwks_url).lower().startswith("https://"):
        return {... "insecure_scheme" ...}
```

"Below" was after the connection opened. An `http://` JWKS URL was contacted in
plaintext and only then rejected, so the check protected the response and not
the request. The check now runs before the call, and
`network_access_attempted` reports `False` for a rejected scheme — which is now
true.

**`allow_live_fetch: bool = True`** in
`grants_gov_attachment_recoverable_reaudit_service` is now `False`. Gate 77B's
guard stood behind it either way, but a default-open network parameter is the
wrong shape regardless: a caller who forgets the argument should not opt into
live fetching.

## One user-agent, with a reachable contact

```text
NativeForgeBot/1.0 (+https://github.com/grayjosef/NativeForge;
                    grant discovery for tribal organizations)
```

Gate 92's string pointed at `nativeforge.example` — an RFC 2606 reserved domain
that resolves to nothing. A contact nobody can reach is decoration; the point of
putting it in the UA is that an operator who wants us to stop has somewhere to
go. The canonical string keeps Gate 92's `NativeForgeBot` identity and takes the
polite fetcher's real contact.

`nativeforge_user_agent_service` now owns both the string and the
forbidden-token list, and `source_crawler_governance_service` imports them. That
reverses the original direction on purpose: while governance owned the string, a
second one could live in a fetcher without governance knowing — which is exactly
what happened.

## The scanner is what keeps this from decaying

`hermetic_network_enforcement_service` parses every file under
`src/nativeforge` and fails the suite on an unapproved network import, an
`allow_live_fetch` default of `True`, or a second user-agent definition.

```text
files scanned            885
network call sites         6
approved                   6
unapproved                 0
findings                   0
```

The approved list names each module, why it may reach the network, and which
guard it routes through. There is no naming convention that grants an
exemption — a convention is something a new file can satisfy by accident.

Three tests plant a violation in a temp tree and assert the scanner catches it,
so a clean report means the scan works rather than that it found nothing.
