# Gates 156–161 — where the source collection runtime stands

The block's stated intent: *build the runtime machinery required for source
collection while keeping every live-source path hermetic and inactive.* Six
gates in, that is where it is.

## The four facts the block exists to keep apart

```text
runtime exists              YES     scheduler, worker, job store,
                                    orchestration, payload store, envelope
collection is approved      no      zero approved sources
source terms are approved   no      171 terms-blocked, 6 human-review-blocked
live monitoring is active   no      source_monitoring_live = false
```

Gate 161 is the gate where the first row became most dangerous. The runtime can
now build a request, send it, store the response and prove it happened. Only
the injected transport separates that from collection — which is why this gate
spent as much effort on measuring the separation as on building the machinery.

**Runtime existence does not imply live monitoring.** Six gates of machinery
and the last three rows are unchanged.

## What each gate contributed

```text
156   the survey. What existed, what did not
157   the worker: claim, decide, record, release. Executes nothing
158   the job store: a durable lifecycle, `completed` unreachable
159   orchestration: periodic, duplicate-suppressed, missed-window recovery
160   the payload store: exact bytes, hashed twice, replayable
161   the envelope: request -> transport -> payload -> proof, hermetic only
```

Each reused the one before rather than growing a parallel copy. There is one
job store, one lease system, one retry schedule, one payload store, one
orchestration owner — and Gate 161 added no second anything.

## The counters, across the block

```text
collectors_invoked          0
live_source_calls           0
network_calls               0
urls_fetched                0
dns_resolved                false
credentials_required        false
emails_sent                 0
object_store_calls          0
jobs_completed              0
approved_source_count       0
customer_data_persisted     false
real_org_touched            false
source_monitoring_live      false
```

`raw_payloads_written` is the one counter that moved, and only under the
hermetic handler. It is no longer a hardcoded zero, because Gate 160 stores
real bytes and a counter forced to zero next to a row that exists is a claim
rather than a count. What replaced the zero is an agreement check: it must
equal what the hermetic path reports persisting, cannot exceed the executions
that produced it, and must be zero under any handler but the hermetic one.

## The recurring defect, and its count

Substring-versus-meaning, now **fourteen** occurrences across the campaign.
Gate 161 contributed one — and two of a related shape.

The rule, unchanged: *every time a check asks "does this text appear" when it
means "does this happen", it eventually matches the sentence explaining why it
must not.* The fix is always the same: parse it, resolve the dotted path, or
measure the behaviour.

Gate 161's three, all self-inflicted and all caught before commit:

**A computed measurement thrown away.** `sorted(_called_name_paths(tree))[:0]
or []` — an empty list dressed up as a measurement, written inside the module
whose purpose is catching exactly that. Replaced with a real question: does the
module that should route through the boundary actually call it?

**A green check with the wrong cause.** The health lane asked
`not hermetic.get("reaches_a_host")` against a module that reported
`can_reach_a_host`. The key was absent, `.get` returned `None`, and `not None`
reported a pass. One name for one fact now, and the lane indexes rather than
gets, so a missing key raises instead of passing.

**A determinism test that could not detect non-determinism.** The artifact
builder wrote `list()` of two frozensets, so every rebuild in a new process
produced different bytes — and the test compared two calls in ONE process,
where set iteration order is stable. It now runs the builder in a separate
process with a different `PYTHONHASHSEED`, which is the thing that actually
varies.

All three are the same underlying error: **checking the easy thing that
correlates with the thing you meant.**

## What still blocks a live source call

```text
no live transport implementation   nothing here can open a socket for a source
zero approved sources              177 known, 0 approved
no source terms approval           a human decides
no activation                      Gate 162 owns it
```

Plus the four structural stops in doc 838, three of which take no caller input
at all.

## Owners for 162–165

```text
162   activation and the allowlist. The first gate permitted to grant
      permission. It will deliberately satisfy the live network guard - that
      is the design - and will still meet three further refusals it must
      remove on purpose rather than by accident
163   the first approved live source
164-165  unallocated
```

## The one sentence to carry forward

Gate 161 built the machine that could call a source and proved, by parsing its
own imports, that it cannot. Gate 162 is where somebody decides it may — and
the proof standard it will be held to was written here, before there was
anything to authorise.
