# 530 — Gate 94A: live HTTP choke point survey

Gate 93 reported four live-HTTP call sites, one guarded. That count was low.
Gate 93 searched for `httpx`, and two more sites reach the network through
`urllib.request`.

**There are six egress call sites in `src/nativeforge`. One is guarded.**

## The six

```text
#  file:line                                        library          guarded
1  grants_gov_search_api_adapter_service.py:51      httpx            YES  (Gate 77B)
2  polite_http_fetch_service.py:49   robots.txt     httpx            no
3  polite_http_fetch_service.py:90   polite_http_get httpx           no
4  real_url_resolver_service.py:82   HEAD/GET       httpx            no
5  feedback_slack_alert_service.py:193  webhook POST urllib.request  no*
6  oidc_token_verification_service.py:358 JWKS GET  urllib.request   no
```

`*` #5 is gated by its own `off` / `dry_run` / `live` mode and a required
out-of-repo env webhook. That is a real gate, but it is a private one — it does
not consult, and is not visible to, any shared guard.

Sites 5 and 6 are **not** source collection. Slack is an operational alert, JWKS
is identity verification. Routing them through a guard whose vocabulary is
`terms_status` and `collector_status` would be wrong: those fields have no
meaning for a JWKS fetch. This is why the guard is built with a `purpose`
dimension rather than one flat rule set — with it, all six route through one
choke point without any of them being asked a question that does not apply.

## A defect in #6

```python
import urllib.request

try:
    with urllib.request.urlopen(  # noqa: S310 - https enforced below
        jwks_url, timeout=float(timeout_seconds)
    ) as resp:
        if not str(jwks_url).lower().startswith("https://"):
            return {... "reason": "insecure_scheme" ...}
        body = resp.read(1_000_000)
```

The comment says *"https enforced below"*. Below is **after the request has
gone out**. An `http://` JWKS URL is contacted over plaintext and only then
rejected, so the scheme check protects the response and not the request. For a
URL that comes from issuer configuration this is a live SSRF and
plaintext-contact surface.

The check has to move above the call. It is three lines and squarely in this
gate's subject.

## Not egress

```text
gate37_production_grade_hardening_service.py:68   socket -> 127.0.0.1:5175
```

A loopback port-availability probe for the preview server. It never leaves the
machine and is not a fetch. It is allowlisted with that reason rather than
ignored, so a future `socket` import somewhere else still trips the scanner.

```text
urllib.parse / urljoin / urlsplit / urlparse   10 modules, pure string parsing
urllib.robotparser.RobotFileParser             parses text, never fetches
```

`RobotFileParser` is worth being explicit about: it *can* fetch, via
`set_url()` + `read()`. This codebase only calls `rp.parse(lines)` on text it
already has, so the parser itself is inert — the fetch is call site #2.

## Two user-agent strings

```text
polite_http_fetch_service.USER_AGENT
  "NativeForge/1.0 (+https://github.com/grayjosef/NativeForge;
   grant-discovery; respectful-crawler)"

source_crawler_governance_service.NATIVEFORGE_USER_AGENT   (Gate 92)
  "NativeForgeBot/1.0 (+https://nativeforge.example/bot;
   grant discovery for tribal organizations)"
```

Both pass Gate 92's `user_agent_violations` — both identify NativeForge and
carry a URL — so this is a fork, not a violation. Which string a host sees
depends on which module made the call.

**The contact URLs are not equally good.** `nativeforge.example` is an RFC 2606
reserved domain: it resolves to nothing, so a host operator who wants to reach
us cannot. The GitHub URL is real and reachable. Gate 94C requires a contact
"if already available" — one is available, and it is the one Gate 92 did not
use.

So the canonical string keeps Gate 92's `NativeForgeBot/1.0` identity and takes
the polite fetcher's reachable contact. No test pins either literal
(`grep -rn` across `tests/` and `frontend/` returns nothing), so this is a
strengthening rather than a break.

## Robots handling: fail-open at three points

```python
def robots_allows_fetch(url: str) -> bool:
    rp = _robots_parser(url)
    if rp is None:
        return True          # <- 1. no parser => allowed
    return rp.can_fetch(USER_AGENT, url)

def _robots_parser(base_url):
    ...
    if resp.status_code >= 400:
        _robots_cache[dom] = None; return None     # <- 2. 4xx/5xx => allowed
    except Exception:
        _robots_cache[dom] = None; return None     # <- 3. timeout  => allowed
```

A host whose robots.txt times out, 500s, or is unreachable reads as fully
permissive. That is the opposite of every other decision in this campaign, and
it is the one most likely to matter: an agency host under load is exactly when
a crawler should back off, and is exactly when this returns `True`.

The three cases are also collapsed into one `None`, so a genuinely absent
robots.txt (a 404, which does conventionally mean "no restrictions") is
indistinguishable from a timeout. The repair needs to tell them apart rather
than flipping all three to deny.

## Rate limiting, blacklist, circuit breaker

```text
polite_http_fetch    DEFAULT_MIN_INTERVAL_SECONDS = 2.0   (Gate 92 floor: 5.0)
real_url_resolver    its own _enforce_rate_limit, separate module state
blacklist            none in either fetch path
circuit breaker      none in either fetch path
429 / 5xx backoff    none — a fixed pre-request sleep only, no response-driven backoff
```

Gate 92 defined the blacklist (`scdmh.net` — a hijacked casino domain —
`scdhec.gov`, `cdc.gov/tribal/*`) and the breaker in
`source_crawler_governance_service`. Neither fetch path calls it. The
governance contract and the code that fetches have never been introduced.

## `allow_live_fetch` defaults

```text
grants_gov_attachment_recoverable_reaudit_service.py:88   bool = True    <- open
grants_gov_eligibility_completeness_service.py:75         bool = False
grants_gov_eligibility_completeness_service.py:103        bool = False
```

The one `True` still lands on Gate 77B's guarded transport, so it cannot reach
the network today. The default is backwards regardless: a caller who forgets the
argument opts *into* live fetching.

## Live callers to protect

```text
polite_http_get (5):
  state_tribal_affairs_html_adapter_service.py:157, :192
  tier3_foundation_batch_live_fetch_service.py:73
  foundation_fluxx_embed_adapter_service.py:90
  foundation_html_listing_adapter_service.py:171

default_real_http_fetch (1, injectable):
  real_url_resolver_service.py:125   do_fetch = fetcher or default_real_http_fetch
```

Both have an injection seam already — `polite_http_get` is called directly, and
the resolver takes a `fetcher` parameter. The repair must keep the seam so
tests can inject a recorded transport, and make the *default* deny.

## Existing guard worth extending, not replacing

```python
hermetic_test_guard_service.assert_live_network_allowed(url=..., caller=...)
  raises LiveNetworkBlockedError unless
  NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1
```

It raises rather than returning a sentinel, on the stated reasoning that *"there
is no useful partial answer to a request we were not allowed to make, and a
silent empty result would be indistinguishable from a genuine no-results
response — which is exactly how the corpus fixture got overwritten with a
placeholder."*

That is the right shape. Gate 94's guard wraps it and must not weaken it: the
env flag stays authoritative for the Grants.gov path, and the new guard adds
requirements on top rather than offering an alternative route around it.

## What Gate 94 has to do

```text
1  one guard, purpose-aware, deny by default
2  one user-agent, with a reachable contact
3  robots fail-closed, distinguishing 404 from timeout
4  5.0s floor, blacklist and breaker consulted before the request
5  allow_live_fetch defaults False everywhere
6  move the OIDC scheme check above the request
7  a scanner that fails the build when a seventh call site appears
```

Item 7 is what keeps this gate from decaying: the survey above is a snapshot,
and a snapshot does not prevent the eighth call site.
