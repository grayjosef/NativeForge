# 525 — Gate 93B: source activation preflight contract

`source_activation_preflight_service` decides whether a source may be activated
for collection. It activates nothing and fetches nothing —
`activation_performed` and `fetch_performed` are `False` on every result, held
by invariants.

**No collectors were activated. No URLs were fetched. No live coverage is
claimed.**

## Deny by default, and "not checked" is not "fine"

`activation_blocked` is the starting position. Every requirement must be
*affirmatively* satisfied to move off it, and the allowed set is derived from
what passed — never computed by subtracting blockers from a permissive default.
This is the Gate 79B rule applied to activation.

An unrecognised status value resolves to the blocking member of its vocabulary.
A typo'd `terms_status` of `NO_REVIEW_REQUIRD` becomes `UNKNOWN` and blocks.

## Four statuses

```text
activation_allowed                every required precondition satisfied
activation_blocked                a named, fixable requirement is missing
activation_requires_human_review  a person must decide, not a rule
activation_unknown                nothing was supplied; nobody has asked yet
```

`activation_unknown` is separate from `activation_blocked` and neither permits
anything. The distinction is for the operator: blocked names a requirement you
can go satisfy, unknown names a question nobody has asked.

## Eight requirements

```text
terms_cleared         terms do not carry an unresolved obligation
legal_review          approved, where terms are not already clear
attribution           present and verbatim, where required
credential            held, for collector types that need one
raw_payload_storage   contract satisfied — universal, no exceptions
rate_limit_policy     declared — universal, no exceptions
user_agent_policy     declared, for anything that crawls a host
scheduler_policy      declared
```

An invariant asserts that `requirements_satisfied` and `requirements_missing`
together account for exactly these eight, so a requirement cannot be dropped
from the checklist silently.

## Human review outranks a satisfied checklist

`HUMAN_REVIEW_ONLY` produces `activation_requires_human_review` even when every
other requirement passes, because the requirement it fails is *"a rule may
decide this"*. A source whose terms permit only human access cannot be automated
by satisfying more automation preconditions. An invariant fails any result where
`human_review_required` coexists with `activation_allowed`.

## A collector type may not exempt itself

This one was a real defect, caught by the service's own smoke test before any
test file existed.

The first implementation treated `not_required` as satisfying every requirement.
So a `public_api_with_key` collector declaring `credential_status:
not_required`, and an `html_crawler` declaring `user_agent_status:
not_required`, both reached `activation_allowed`. SAM.gov cannot be a keyed API
whose credential is not required, and a crawler cannot be exempt from having a
user-agent policy — those requirements come from the collector type, not from
the row.

Now, where the collector type mandates a requirement, only the affirmative value
satisfies it (`present_and_valid`, `policy_declared`), and two invariants fail
any result where a credentialed collector or a crawler reached `allowed` without
one. `forbidden_ai_crawler` never satisfies a user-agent policy.

## Monitoring cannot start from unknown

`safe_to_schedule` requires `monitoring_status` to be affirmatively
`not_started`. A source whose current monitoring state we cannot describe is not
one we may schedule — starting a monitor on top of an unknown one is how you end
up with two.

## safe_to_fetch_now is always False

`safe_to_schedule` and `safe_to_fetch_now` are distinct answers because they
fail independently. In Gate 93 the second is a constant `False` regardless of
inputs, with an invariant enforcing it: nothing fetches in this gate, so a
preflight that could return `True` would be describing a capability that does
not exist.

## Tests

```text
preflight defaults to blocked
unrecognised status blocks rather than passes
TERMS_REVIEW_REQUIRED blocks
HUMAN_REVIEW_ONLY blocks automation and cannot be lifted
missing raw payload storage blocks
missing rate-limit policy blocks
credentialed collector cannot exempt itself      (parametrized, 2 types)
crawler cannot exempt itself from a UA policy    (parametrized, 3 types)
forbidden AI-crawler UA never satisfies
monitoring cannot start from unknown/running/scheduled
every requirement is accounted for
safe_to_fetch_now is never True
```
