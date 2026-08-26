# 505 — Gate 90D: customer state filtering contract

`customer_state_source_filter_service` (`nf_customer_state_source_filter_v1`)
decides which registry sources a customer may see, so a state source reaches
only customers who actually operate in that state.

## The failure this prevents

**Every state row in the current seed is South Carolina.** All 10 of them.

If the filter defaults open, a customer in Oklahoma is shown SC broadband and SC
emergency-management programmes they cannot apply to — and the SC pilot
vocabulary, validated only for SC, starts spreading into states where it was
never checked. Gates 78 and 79 spent considerable effort keeping SC recognition
rules from generalising; a leaky source filter would undo that from the other
end.

## Deny by default

A state-scoped source becomes visible by **matching**, never by failing to be
excluded:

| Scope | Visibility |
| --- | --- |
| `federal_all_customers` | visible to everyone |
| `private_unscoped` | visible to everyone |
| `state_scoped` | visible only if the source's state is in the customer's operating states |
| anything else | **blocked** — an unclassified scope is not a cleared one |

## Operating state, not mailing address

The dossier is explicit (§8.1): resolve operating state(s), service area and
lands — do not use a mailing address.

This service takes an explicit `operating_states` list and **has no address
field at all**, so there is nothing to accidentally fall back to. `mailing_address_used`
is a constant `False` with an invariant behind it, and a test greps the source
for the word.

## Missing state blocks, it does not open

A customer with no declared operating state sees **zero** state sources, not all
of them. `None`, `[]` and `""` are all treated as undeclared.

That is the safe direction: an unknown customer geography is a reason to show
less, not more.

## Measured behaviour

| Customer | Visible | Blocked | State sources visible |
| --- | --- | --- | --- |
| SC | 55 | 0 | 10 |
| SC + NC | 55 | 0 | 10 |
| OK | 45 | 10 | **0** |
| NM / WA / CA / NY | 45 | 10 | **0** |
| no declared state | 45 | 10 | **0** |

Federal sources hold at 43 across every case — a state filter must not narrow
national coverage.

## Blocked reasons are stated, never implied

Every blocked source carries one of a closed set:

```text
state_not_in_customer_operating_states
customer_has_no_declared_operating_state
source_state_unknown
unrecognised_state_scope
```

An invariant fails if a source is blocked without a reason, or with a reason
outside the vocabulary. Another fails if any source appears in both the visible
and blocked lists — nothing may be silently dropped.

## Visibility is not eligibility

A visible source means *this is somewhere you might look*. It does not mean the
customer qualifies. `eligibility_status` rides through untouched at
`NOT_DETERMINED_BY_REGISTRY`, and `visibility_is_not_eligibility` is a constant
`True` on every result.

This matters most for the SC rows. All 10 carry
`federal_recognition_required: No` with `state_recognition_supported: UNKNOWN`.
An SC customer sees them. That says nothing about whether a state-recognized
tribe or a Native nonprofit may apply — the live notice decides, and the registry
records `UNKNOWN` rather than guessing.

## The leakage test

`test_no_sc_source_leaks_to_a_non_sc_customer` iterates OK, NM, WA, CA and NY,
asserts zero state sources visible in each, and runs the invariant checker on
every result. The invariant itself independently re-derives the leak condition,
so the test would fail even if the filter and its own reported counts agreed
with each other wrongly.
