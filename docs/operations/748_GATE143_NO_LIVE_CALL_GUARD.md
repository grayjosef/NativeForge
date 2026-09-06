# 748 — Gate 143: the no-live-call guard

```bash
bash scripts/verify_nativeforge_no_live_source_calls.sh
```

## It proves a negative by reading, not by calling

A verifier that proved "no live calls" by making one would be answering a
different question. This one parses source with `ast` and reads the scheduler's
own derived runtime mode. **It makes zero network calls itself**, and says so in
its own output.

## Five things it checks

```text
1. Gate 94's choke point scan is clean          1088 files, 0 unapproved
2. no monitoring module imports a network client parsed, not searched
3. no collector is running                       runtime mode, worker, jobs
4. no registry source is cleared for collection  0 of 177
5. the evaluation itself contacted nothing       network_calls: 0
```

If any fails, it names the offender by **file and module**, so a failure points
at something to open rather than at a count.

## `urllib.parse` is not a network client

The first version of the import detector collapsed every import to its
top-level package, so `from urllib.parse import urlsplit` read as `urllib` and
flagged this gate's own allowlist — which parses a URL string and opens nothing.

`hermetic_network_enforcement_service` already draws the line:

```text
NETWORK_URLLIB_SUBMODULES  urllib.request  urllib.error
INERT_URLLIB_SUBMODULES    urllib.parse    urllib.robotparser
NETWORK_HTTP_SUBMODULES    http.client     http.server  http.cookiejar
```

So `_is_network_module` asks that module rather than keeping a second list that
could disagree. Two answers to one question is the shape Gate 114 spent a gate
collapsing, and a probe that cannot tell `urlsplit` from `urlopen` is the
name-versus-capability defect again.

A test proves the detector still catches a real one: it writes `import httpx`
into a temporary copy of a monitoring module and asserts the finding. A detector
that returns nothing because it looks at nothing is useless, and that test is
what stops this one becoming that.

## What "no collector is running" means here

Read from `source_scheduler_readiness_service`, which derives it rather than
asserting it:

```text
runtime_mode              dry_run_in_process
runtime_executes_jobs     false
background_worker         absent
periodic_trigger          absent
persistent_backend        absent
production_raw_payload_store  absent
scheduler_runtime         absent
```

Gate 99D already tightened that check once: it used to ask whether a scheduler
package was installed, which `dry_run_in_process` passed. It now asks about the
**mode**.

## Current result

```text
RESULT=PASS
no_live_source_call_path_is_active=true
chokepoint_clean=true
files_scanned=1088
unapproved_call_sites=0
collectors_activated=0
source_monitoring_live=false
sources_cleared_for_collection=0
network_calls_by_this_verifier=0
```

## What it does not prove

```text
that no live call could ever be added        a future gate can add one
that a source is unreachable                 unknown, and not asked
that terms forbid collection                 unknown, and that is the point
```

It proves that **right now, in this checkout, nothing can reach a grant
source** — which is the claim Gate 143 needed and the one it can support.
