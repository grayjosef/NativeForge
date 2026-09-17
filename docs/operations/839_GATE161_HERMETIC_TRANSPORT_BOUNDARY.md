# Gate 161 — the transport boundary

How "this code cannot reach a host" became a fact a parser can check.

## The shape

```text
execute_request(request=..., transport_kind=..., transport=..., policy=...)
```

`transport` is a callable, handed in. The boundary module imports no network
library, so there is no import to intercept and nothing for a caller to
substitute — the question "could this reach a host" reduces to "does this file
import something that can", which `ast` answers exactly.

That is stronger than a chokepoint callers must remember to route through. A
chokepoint you can go around is a convention; a module with no socket in it is
a fact.

## Why injection rather than a mock

A mock replaces behaviour at runtime, and whether it was actually installed is
a question about the test harness. An injected transport is a parameter: the
signature says the dependency comes from outside, and
`source_collection_execution_chokepoint_service` checks that the parameter is
still there.

The three legacy transports were already injectable — `polite_http_get(...,
transport=None)`, `search_grants_gov_opportunities(..., http_post=None)`,
`resolve_url_real(..., fetcher=None)`. Gate 161 did not invent the pattern; it
made the absence of an import the thing being measured.

## What the boundary enforces

```text
method              GET, HEAD, POST only
request headers     an allowlist by NAME
                    (user-agent, accept, accept-encoding, accept-language,
                     if-none-match, if-modified-since, content-type)
response size       1 MiB, refused AT the boundary
transport kind      hermetic dispatches; live is named so refusing it is
                    expressible, and is not in DISPATCHABLE_KINDS
```

A refused header is refused by name and its value appears nowhere in the
result. Gate 160 settled that query strings carry API keys; the same reasoning
applies to headers, and the request description carries a sha256 fingerprint of
the URL rather than the URL.

## Outcomes

```text
response_received                  a response arrived
response_received_malformed_body   bytes arrived that no parser accepts
timeout                            no answer in time
connection_failed                  including: nobody registered this URL
refused_before_dispatch            the policy, the kind, or the request
```

`response_received_malformed_body` is a RESPONSE, not a failure. The
distinction exists because treating unparseable bytes as a transport failure
would discard the only copy of what arrived, and "we got something and could
not read it" is a different operational problem from "we got nothing".

## The hermetic registry

`HermeticTransportRegistry` holds URL → canned response. It serves 200, 404,
429 with `Retry-After`, 5xx, a timeout, and a body that is deliberately not
valid UTF-8 and contains a null byte. An unregistered URL returns
`connection_failed`, which is what a fixture registry should say about an
address it has never heard of — not an exception, and not a silent empty
success.

`register_ok` attaches a `Set-Cookie` on purpose, so the metadata filter is
exercised in the refusing direction every time the happy path runs. Gate 160's
lesson: a filter that refuses everything passes every refusal test.

Both modules parse THEMSELVES for network imports and report the result.
`describe_boundary()` and `describe_hermetic_transport()` both answer
`reaches_a_host`, which is one name for one fact — they did not, and the
health lane read the missing key, got `None`, and reported a pass on `not
None` until they were reconciled.

## The measurement, and its falsifiability

`scan_execution_chokepoint()` walks `ast.Import` / `ast.ImportFrom` nodes and
resolves dotted callee paths from `Name`/`Attribute` nodes. Never `ast.unparse`,
whose output for `str(expected_sha256 or '').lower` contains `sha256` — which is
how Gate 160 turned a fixed substring check back into a substring check.

Never a substring search at all, and that is itself measured by parsing this
module rather than asserted in prose.

The scan is shown to FAIL: the verifier and the test suite each copy the tree,
write a real `import httpx` into an envelope module, delete another, and require
both findings. A scan that cannot go red has not verified the green.
