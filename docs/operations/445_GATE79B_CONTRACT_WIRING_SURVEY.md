# 445 — Gate 79B-A: Contract wiring survey

## Lane vocabularies found

Four now, counting the canonical one Gate 79 added.

| Where | Constant | Values | Level |
| --- | --- | --- | --- |
| `opportunity_funding_lane_service` | `FUNDING_LANES` | `sc_state`, `federal`, `federal_pass_through`, `federal_sc_relevant`, `local_regional`, `foundation`, `corporate`, `unknown` | **canonical, opportunity** |
| `sc_native_routing_service` | `FUNDING_LANES` | `sc_state`, `federal_sc_relevant`, `local_regional`, `foundation`, `unknown` | opportunity |
| `native_opportunity_discovery_service` | `LANES` | `federal`, `state`, `local`, `private`, `unknown` | opportunity |
| `sc_state_source_lane_service` / `federal_source_lane_service` | hardcoded `"lane"` strings | `sc_state` / `federal` | **source** |

The two source-level strings are **correct as they stand**. An SC agency page is
an SC source; a federal agency page is a federal source. Gate 79's correction was
never about source lane — it was that an opportunity must not inherit it.

## Scorer / coverage services found

`ls | grep quality` returns seven services. Only one scores opportunity coverage:

| Service | Role |
| --- | --- |
| **`opportunity_discovery_quality_service`** | **Gate 54 scorer — the wiring target** |
| `discovery_quality_service` | discovery-run quality, not opportunity coverage |
| `discovery_source_quality_service` | per-source signals |
| `eligibility_evidence_quality_service` | placeholder-text detection |
| `real_url_quality_service`, `source_ingestion_url_quality_service` | URL hygiene |
| `source_quality_operator_actions` | operator actions |

**`opportunity_source_quality_service.py` named in the gate brief does not
exist.** The Gate 54 scorer is `opportunity_discovery_quality_service`.

Its counting rule, verbatim:

```python
eligibility_evidenced = sum(
    1 for o in opportunities
    if o.get("eligibility_evidence")
    and o.get("eligibility_state") in {"eligible", "possibly_eligible"}
    and not o.get("duplicate_of")
)
```

Also counts `sc_count` and `federal_count` from `funding_geography`, which is a
**geography** field, not a funding lane — a separate axis that Gate 79B does not
touch.

## Eligibility vocabularies found

| Where | Values |
| --- | --- |
| `sc_native_routing_service.ELIGIBILITY_STATES` | `eligible`, `possibly_eligible`, `not_eligible`, `unknown` |
| `federal_native_eligibility_service.ELIGIBILITY_STATES` | same four |
| `eligibility_exclusion_evidence_service.RESULT_STATES` | six, incl. `excluded_by_evidence`, `not_supported_by_evidence`, `human_review_required` |

`not_eligible` remains present in the older two and remains **unreachable** —
`federal_native_eligibility_service` hardcodes `not_eligible_asserted: False`
with an invariant.

## The structural mismatch

**Exclusion is per applicant class. The Gate 54 scorer is per opportunity.**

One opportunity can be `eligible` for a federally recognized tribe and
`excluded_by_evidence` for a state-recognized one — the NACTEP case. A single
`eligibility_state` on the opportunity cannot express that, and collapsing it
would lose whichever half was dropped.

So coverage counting has to become **class-aware**, or it will keep counting an
opportunity as eligible coverage for a customer it excludes.

## Safe wiring points

All additive and keyword-only, so every existing call site and test keeps
working:

1. `sc_native_routing_service.route_sc_opportunity(..., canonical_funding_lane=None)`
   — when supplied, project via `sc_routing_lane()` and record the projection.
2. `native_opportunity_discovery_service.build_native_opportunity_record(...,
   canonical_funding_lane=None, exclusion_result=None)` — project via
   `discovery_lane()`; surface `excluded_classes`.
3. `opportunity_discovery_quality_service.build_discovery_quality_score(...,
   applicant_class=None)` — when supplied, exclude opportunities excluded for
   that class from eligible coverage and count them as negative intelligence.

No import cycles: neither Gate 79 service imports any of these three.

## Unsafe wiring points — deliberately not touched

- **Deleting either old lane vocabulary.** Both are pinned by existing tests
  (`test_gate78`, `test_gate76`) that assert their exact membership. Removing
  them is a separate breaking change; Gate 79B bridges instead.
- **Changing `funding_geography`.** It is a geography axis, not a funding lane.
  Conflating them would recreate the very confusion Gate 79 fixed.
- **Making `not_eligible` reachable.** Out of scope and forbidden.
- **Hiding excluded opportunities.** They are useful negative intelligence.
- **The hermetic Grants.gov guard and the corpus write-back guards.** Untouched.
- **Source-level lane strings.** Correct as they are.

## What the lossy projection costs

`federal_pass_through` has no equivalent in either old vocabulary:

```text
→ sc_native_routing_service:  federal_sc_relevant   (only federal member)
→ native_opportunity_discovery_service: federal
```

Both land on federal. Neither lands on a state value, which is the property that
matters. The loss is that pass-through becomes indistinguishable from ordinary
federal money *in the old views only* — the canonical record retains it.
