# 551 — Gate 98C: source circuit breaker

`src/nativeforge/services/source_circuit_breaker_service.py`

Computes a source's circuit status from its recent check outcomes. It decides;
it never fetches and never performs a probe.

## What was there before: four counters, two thresholds, no owner

Gate 98A read every failure-counting site in the repository:

```text
1  source_crawler_governance_service.CIRCUIT_BREAKER_CONSECUTIVE_FAILURES = 5
   Gate 92's policy. Consulted by live_network_guard_service before a request.

2  source_freshness_service:242    if failure_count >= 3
   Derives source_health_status. A different threshold.

3  discovery_source_quality_service:581    >= 3
   A third site, same value as (2), independently written.

4  polite_http_fetch_service._consecutive_failures: dict[str, int]
   Per-process, in memory, keyed by domain, lost on restart.
```

Four places count and two disagree. A source can be "unhealthy" at 3 by the
freshness derivation while the network guard still permits requests until 5.

None of them is a breaker. A counter tells you how many times something failed;
a breaker decides whether to try again, and that needs states and a clock.

Gate 98 does not delete the other four — that is a refactor with its own
regression surface, recorded in doc 553 as a follow-up. It defines the one state
machine a scheduler consults, and it bridges Gate 92's threshold rather than
declaring a fifth.

## Five states

```text
closed       normal. Checks may be scheduled.
open         threshold reached. Nothing scheduled until cooldown elapses.
half_open    cooldown elapsed. ONE probe is permitted, not a resumption.
manual_hold  a person stopped this source. No automation lifts it.
unknown      the inputs do not describe a state. Blocks.
```

Defaults: threshold 5 consecutive failures (bridged from Gate 92), cooldown
3600 seconds.

## half_open is the point

An open breaker whose cooldown expires does not return to normal — it gets one
attempt. Resuming at full rate into a host that was failing is how a temporary
block becomes a permanent one, and SAM.gov names that consequence explicitly.

`single_probe_only` is derived from the status, and an invariant fails any
half-open result that does not carry it.

## The decision ladder

```text
1   manual_override == hold        -> manual_hold     blocks
1b  manual_override unrecognised   -> unknown         blocks
2   failure count unreadable       -> unknown         blocks
2b  failure count negative         -> unknown         blocks
3   failures < threshold           -> closed          permits
4   threshold reached, cooldown not derivable -> open blocks
4b  threshold reached, cooldown elapsed       -> half_open  one probe
4c  threshold reached, cooldown running       -> open blocks
```

Step 1b was added mid-gate. The first version normalised an unrecognised
override to `unknown` and then fell through to the failure-count branch, so a
source carrying `manual_override_status = "whatever"` with a healthy counter
came back `closed` and permitting. A value nobody defined is somebody's intent
this code cannot read, and reading it as permission is the defect this campaign
exists to remove. An *absent* override is different, and resolves to `none`.

## A cooldown that cannot be measured has not elapsed

`_elapsed_seconds` returns `None` when either timestamp is missing, unparseable,
or when one is naive and the other aware. In every such case the circuit stays
`open` with `cooldown_not_derivable`. Comparing a naive timestamp to an aware one
would mean inventing a timezone to get an answer.

## manual_hold outranks everything

A person who stopped a source did so for a reason no counter knows. Cooldown does
not lift it, a success does not lift it, and two invariants fail any result where
automation reopened it or permitted scheduling through it.

## Constants held by invariants

```text
probe_performed   false
fetch_performed   false
check_executed    false
```

`half_open` reports that a probe *would* be permitted. Performing one is a
scheduler's business, and there is no scheduler.
