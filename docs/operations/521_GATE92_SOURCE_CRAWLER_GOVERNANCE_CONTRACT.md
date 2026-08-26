# 521 — Gate 92: source crawler governance contract

Nothing here crawls. `source_crawler_governance_service` declares the rules a
collector must satisfy *before* one is written, so the rules exist ahead of the
code that would break them. `evaluate_fetch_permission` answers "would this
fetch be permitted?" and reports `fetch_performed: False`, checked by an
invariant.

## User-agent

A descriptive NativeForge UA carrying a contact URL. **Never an AI-crawler UA.**

hud.gov's robots.txt names ClaudeBot, GPTBot, CCBot, Amazonbot,
Applebot-Extended, Bytespider, Google-Extended and meta-externalagent with
`Disallow: /`, and asserts content signals — including `ai-train=no` — as a
condition of access. Presenting one of those strings is simultaneously a robots
violation and a terms violation.

The forbidden list is matched as case-insensitive substrings rather than exact
strings, so a variant like `Mozilla/5.0 (compatible; GPTBot/1.1)` is caught. A
parametrized test walks every token in the list. Deny by default: an empty UA is
a violation, and a UA that does not identify NativeForge or carry a contact URL
is a violation.

## Pacing

No host in the entire research set publishes a `Crawl-delay`. Absence of a
declared floor is not permission for speed, so the floor is self-imposed:

```text
per-host concurrency          1
minimum request interval      5.0 seconds
```

An invariant fails any record relaxing either one.

## Site search is off-limits almost everywhere

`Disallow: /search/` is near-universal — sam.gov, ojp.gov, hud.gov, epa.gov,
energy.gov, grants.nih.gov, rd.usda.gov, bia.gov, with path-specific variants on
federalregister.gov and usaspending.gov. **A monitor that polls site-search URLs
violates robots on almost every agency host.** Poll sitemaps, listing pages,
feeds, or APIs instead.

## Circuit breaker, not retry

After five consecutive failures a source halts and pages a human.
`auto_retries_after_trip` is False and an invariant enforces it, along with the
requirement that a tripped breaker both halts the source and pages. Retrying
into a block is how access gets revoked permanently, and SAM.gov names that
consequence explicitly.

## Dead shells beat 404s

HUD's `/program_offices/public_indian_housing/ih` returns **HTTP 200 with valid
HTML and zero body content**, titled `25red-Indian Housing` with a blank meta
description — a half-migrated CMS. A monitor keyed on status code reports "no
change" there forever.

So liveness is decided on body hash and content length, never status alone:

```text
verdict                    condition
stale_redesign_artifact    title begins with a redesign prefix (25red-)
dead_shell                 HTTP 200 with a body under 512 bytes
live                       HTTP 200 with a real body
unknown                    anything else
```

Only a `live` page is `eligible_for_diff`, and a non-live page can never report
a content change — invariants enforce both. A test points the classifier at
HUD's actual shell and asserts it is flagged stale rather than unchanged.
`decided_on_status_alone` is False on every result.

## Blacklist

```text
scdmh.net       fetched and found to be a hijacked casino site
scdhec.gov      legacy; agency reorganized in 2024 into SC DES and SC DPH
cdc.gov/tribal/ serves 2016 Zika content; live material is at /healthy-tribes/
```

`scdmh.net` is blocked outright rather than deprioritized — the research pass
fetched it and found a hijacked domain, which is a security finding, not a
freshness one.

The CDC entry is a path-prefix block, not a host block: `cdc.gov/healthy-tribes/`
must remain reachable, and a test asserts that it does. Blocking the whole host
would have removed the tribal health lane along with the stale namespace.

Every blacklist entry carries its reason inline, so a future reader can tell
whether the block is still warranted rather than inheriting an unexplained
denial.
