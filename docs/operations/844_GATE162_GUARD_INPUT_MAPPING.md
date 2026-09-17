# Gate 162 — the guard input mapping

How `build_live_network_decision`'s inputs are earned from records.

## Before: two of ten

`build_live_network_decision` takes 18 inputs, of which ten are the per-source
statuses that decide permission. `evaluate_source` produces 24 fields. They
overlapped on **two**.

```text
the guard wants            the registry produced
-----------------------    ----------------------------------------
source_id         HAVE     source_id
terms_status      HAVE     terms_status  (= "UNKNOWN" for all 177)
activation_status MISSING  activation_approved   (a bool, different name)
collector_status  MISSING  collector_activated   (a bool, different name)
credential_status MISSING  credential_required   (a bool, different name)
robots_status     MISSING  robots_fetched        (a bool, different name)
rate_limit_status MISSING  —
user_agent_status MISSING  —
attribution_status MISSING —
collector_type    MISSING  —
```

Fed only what the registry could answer, the guard reported
`requirements_satisfied: 2 of 10` and eight blocked reasons. The names were
different, the shapes were different (booleans versus status vocabularies), and
four inputs had no counterpart at all.

## After: every status input resolved from a record

```text
guard input          fact                 source of truth
------------------   ------------------   --------------------------------
terms_status         terms_status         nf_source_authorization_decisions
                                          [decision_kind=terms]
activation_status    activation_status    nf_active_opportunity_sources
                                          .activation_approved_*
collector_status     collector_status     phase1_collector_activation_policy
                                          _service (fixtures: the Gate 161
                                          envelope health lane)
robots_status        robots_status        UNRESOLVABLE for a real source
credential_status    credential_status    registry access_posture_hint
rate_limit_status    rate_limit_status    live_network_guard_service's own
                                          MIN_REQUEST_INTERVAL_SECONDS and
                                          PER_HOST_CONCURRENCY
user_agent_status    user_agent_status    canonical_user_agent, compared
attribution_status   attribution_status   derived from the terms decision
```

Plus three facts the guard does not take as input but authorization requires:
`source_registered`, `human_review_status` and `runtime_status`.

## The vocabularies are READ, never restated

`source_authorization_fact_model_service` imports `ALL_TERMS_STATUSES`,
`TERMS_NON_BLOCKING`, `ACTIVATION_STATUSES`, `ACTIVATION_SATISFYING`,
`COLLECTOR_STATUSES`, `ROBOTS_SATISFYING` and the rest directly from the guard.
It declares none of them.

A second copy of a vocabulary is a second thing to drift. The gate's tests
assert set equality between the model's declared vocabulary and the guard's, so
a change on either side that is not mirrored fails rather than silently
diverging.

## Derivation strengths, and why they are visible

```text
recorded_decision   a human signed a row. THE ONLY authorizing strength
recorded_registry   a curated file the repository ships
measured_runtime    observed at call time from live state
declared_policy     a constant this repository declares about itself
unresolvable        cannot be answered without doing the thing we are asking
                    permission for
```

Flattening these would make the resolver look stronger than it is.
`rate_limit_status` is satisfied by a constant in the guard — genuinely a
policy this repository declares about itself, and genuinely weaker evidence
than a reviewer's signature. Saying so is the point.

## An unresolved input is WITHHELD, never defaulted

```python
guard_kwargs[guard_input] = (
    fact["value"] if fact["fact_status"] == FACT_RECORDED else None
)
```

A fact that is not `recorded` contributes `None`, and the guard refuses on its
own terms. Supplying a permitting default for an unresolved fact is the single
thing this module exists to prevent, and
`the_guard_allowed_with_N_inputs_withheld` fails if the guard ever permits
while any input was withheld.

## `robots_status` is unresolvable on purpose

Knowing whether robots.txt permits a path requires **fetching robots.txt**,
which is the live HTTP call we are asking permission to make. Gate 162 cannot
make one, so every real source refuses on it.

For a synthetic fixture on a `.invalid` host it resolves to `absent`, because
RFC 2606 guarantees that host cannot exist and therefore serves no robots
file — derivable without a request. The guard's own `ROBOTS_SATISFYING`
includes `absent` for exactly this case.

The first draft returned `unresolvable` for every source, which left `approved`
unreachable for all of them and every refusal in the gate unfalsifiable.

## `attribution_status` is downstream of terms

The first draft called `grants_gov_output_may_be_customer_visible()` with no
arguments, caught the `TypeError`, and reported `missing` for every source — a
refusal that had nothing to do with attribution. That function also asks a
different question: whether a *rendered surface* carries the verbatim notice,
checked at render time against a trust manifest.

Whether a source *demands* attribution is part of what a reviewer decides when
they read its terms — `ATTRIBUTION_REQUIRED` is a member of the guard's own
terms vocabulary. So:

```text
terms says NO_REVIEW_REQUIRED    -> not_required     (satisfies the guard)
terms says ATTRIBUTION_REQUIRED  -> missing          (a render-time fact
                                                      nobody has recorded)
no terms decision                -> missing          (unknown whether required)
```

Which makes attribution strictly downstream of terms, and correct: nobody can
say whether a source demands attribution until somebody has read the document.
It inherits the terms reviewer's signature too — a fact that inherits a
decision's authority must inherit its attribution.

## Which lanes a collection actually needs

`runtime_status` is not one question. 162F asked which lanes the authorization
guard requires and the honest answer is "not all six":

```text
REQUIRED_FOR_COLLECTION   worker, job store, payload store, execution envelope
REQUIRED_FOR_MONITORING   those four, plus scheduler and orchestration
```

A one-shot operator-triggered collection is a legitimate shape and does not use
a scheduler. Requiring one would make the first live source depend on machinery
it never touches. For a hermetic fixture, only the envelope lane applies.

## The repair to the stale derivation

`phase1_collector_activation_policy_service` reported
`scheduler_runtime_available: False`. Measured, the cause was not what the name
suggests:

```text
source_scheduler_readiness_service says
    scheduler_runtime_available    True
    background_worker_available    FALSE   <- this one
    periodic_trigger_available     False
    scheduler_package_installed    False

and phase1 computes the AND of the first two
```

Gate 98E's detector looks for a third-party scheduler package and a broker. The
runtime Gates 157–161 built is in-process. The detector was never taught that
this counts, so it answers a question about celery and phase1 read it as a
question about whether work can run.

`source_runtime_readiness_fact_service` composes the six lanes' own health
services instead — each of which OBSERVES evidence: rows in tables, restart
proofs, hashes that verify. Not module presence: a file on disk is not a
runtime, and the gate's tests assert the derivation calls no `exists`,
`is_file` or `glob`.

A lane can therefore report `not_ready` from a process that has not exercised
it, which is correct rather than a bug — it is reporting that it cannot see the
evidence from there. `conditions_not_met` says which evidence is absent, so
"not ready" is never a bare no.

## A note recorded in passing

`source_collection_worker_health_service` reports `worker_runtime_ready: False`
with **no** `conditions_not_met` — a bare refusal nobody can diagnose. Gate 162
surfaces it through a fallback `why` rather than hiding it, and does not fix it:
the instruction was to compose existing systems, not to reopen Gate 157. Worth
fixing when Gate 157's health service is next touched.
