# 575 — Gate 103F: software / capacity allowability review contract

`src/nativeforge/services/software_capacity_allowability_review_service.py`

Assesses whether software, grant administration, compliance, reporting, data
infrastructure or capacity-development costs **may be** allowable under a given
opportunity.

## Six labels, and what they may rest on

```text
clearly_allowable      the source text names this cost type as allowable
likely_allowable       the source text names a close category
possibly_allowable     the source text is permissive but not specific
not_indicated          the source says nothing either way
likely_not_allowable   the source text excludes this cost type
requires_human_review  consequential, contested, or self-assessed
```

**No label above `not_indicated` may be reached without evidence.** Evidence is a
quote or a reference from the opportunity's own text, carried on the result. An
assessment with no evidence becomes `not_indicated`, never a hopeful
`possibly_allowable`, and an invariant fails any affirmative label whose evidence
list is empty.

The permitted wording is *may be allowable* / *appears potentially allowable* /
*requires human review* / *not indicated*. `PROHIBITED_CLAIMS` blocks "this cost
is allowable", "NativeForge is always grant-funded", "guaranteed allowable" and
"always allowable", and an invariant scans the rendered wording for them.

## The self-assessment cap

**When the assessed cost is NativeForge itself, the label is capped at
`requires_human_review` regardless of how strong the evidence is.**

A tool telling a customer that buying the tool is grant-allowable has an obvious
incentive problem. A self-assessment that can only ever return "ask a human" is
defensible; one that can return "clearly allowable" is not, however good the
citation.

The cap is applied last and never lifted. The pre-cap label is retained as
`uncapped_label` so nothing is hidden — a reviewer can see that the evidence
would have supported `clearly_allowable` and that the cap is a policy choice
rather than a weak finding. An invariant fails any self-assessed result that
escaped it, and a parametrised test walks all six starting labels.

This is the one place in Gate 103 that **removes** a capability rather than
adding one, and it was a recommendation carried forward from doc 570 rather than
something the brief demanded.

### It is driven by the flag, not the cost type

`is_nativeforge_itself` is explicit. A cost type of `software_license` does not
trigger the cap on its own — a tenant may legitimately assess some other vendor's
software, and capping that would make the feature useless for the case it is
actually for. Cost types NativeForge could plausibly be produce a
`confirm_vendor_is_not_nativeforge` prompt for the caller, not an automatic cap.

## Bridged from Gate 92, not forked

`nativeforge_software_allowability_source_service` already classifies **sources**
— *does this funding source ever allow software costs?* This service answers a
different question — *may this cost type be allowable under this opportunity?* —
and the vocabularies differ:

```text
source-level (Gate 92)    review-level (here)
clearly_allowable      -> clearly_allowable
likely_allowable       -> likely_allowable
sometimes_allowable    -> possibly_allowable
unclear                -> requires_human_review
unlikely_allowable     -> likely_not_allowable
unknown                -> not_indicated
```

`SOURCE_CLASS_TO_REVIEW_LABEL` holds the mapping explicitly. Gate 92's service is
**not modified** — 55 registry rows and its own tests depend on its classes, and
a test asserts its vocabulary is unchanged.

`bridge_coverage_gaps()` reports any Gate 92 class with no mapping, so drift
between the two is detectable rather than silently landing on human review. A
test asserts the bridge covers every source class, and a mutation dropping one
was caught.
