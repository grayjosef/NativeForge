# 440 — Gate 79A: SC contract correction survey

Two corrections were requested. The survey found the first is worse than
reported and the second is precisely as reported.

## Where funding lane is currently source-level

**Hardcoded, at both source services:**

```text
sc_state_source_lane_service.py:265     "lane": "sc_state"
sc_state_source_lane_service.py:307     invariant: lane must == "sc_state"
federal_source_lane_service.py:275      "lane": "federal"
federal_source_lane_service.py:316      invariant: lane must == "federal"
```

A source record's lane is a constant of the module that built it. That is
correct *for a source* — an SC agency page is an SC source — but nothing derives
an **opportunity's** funding lane from evidence.

## Where opportunity lane is currently represented

Two places, with **different vocabularies**:

| Service | Constant | Values |
| --- | --- | --- |
| `sc_native_routing_service` | `FUNDING_LANES` | `sc_state`, `federal_sc_relevant`, `local_regional`, `foundation`, `unknown` |
| `native_opportunity_discovery_service` | `LANES` | `federal`, `state`, `local`, `private`, `unknown` |

**So there are already three lane vocabularies** — the two above plus the
hardcoded source-level strings. They disagree on names (`sc_state` vs `state`,
`foundation` vs `private`) and on membership (`sc_native_routing_service` has no
plain `federal` at all; `native_opportunity_discovery_service` has no
SC-relevance concept).

That is a larger defect than "lane is source-level". Gate 79 must not add a
**fourth** vocabulary; it must add the canonical opportunity-level one and bridge
both existing sets explicitly, the way Gate 76 bridged source types and Gate 78
bridged recognition routes.

## Where federal pass-through can be expressed

**Nowhere.** No service has any concept of money that is federally funded and
state-administered.

Consequence for the five sources Gate 78R identified:

| Source | Federal programme | Federal funder | Lane today |
| --- | --- | --- | --- |
| SCEMD | HMGP, 75/25 cost share | FEMA | would be `sc_state` |
| SCOR | CDBG-MIT; Solar for All | HUD; EPA | would be `sc_state` |
| SCDES | §319 Nonpoint Source | EPA | would be `sc_state` |
| SC Housing | LIHTC | Treasury/IRS | would be `sc_state` |
| SCDE | mixed federal/state/private on one page | various | would be `sc_state` |

Every one of these would be filed as pure South Carolina state funding today,
because the source page is on an SC agency domain and an SC agency administers
it. `sc_native_routing_service` even *blocks* an `sc_state` lane record that names
a `federal_agency` — so the honest representation is currently rejected as
invalid.

That inverts the failure Gate 78 was designed to prevent. Gate 78 stopped federal
opportunities being relabelled as state ones by *geography*; it does not stop it
happening by *administration*.

## Where eligibility unknown is represented

`ELIGIBILITY_STATES = {eligible, possibly_eligible, not_eligible, unknown}`,
defined twice — in `sc_native_routing_service` and
`federal_native_eligibility_service`, with `native_opportunity_discovery_service`
importing the latter.

## Whether exclusion evidence exists

**No.** `grep -rniE "exclud"` across the discovery services returns nothing.

More interestingly, **`not_eligible` is a vocabulary value that nothing can
produce**. `federal_native_eligibility_service` hardcodes
`not_eligible_asserted: False` and its invariant fails any other value:

```python
if result.get("not_eligible_asserted") is not False:
    fails.append("forbidden_claim:not_eligible_asserted")
```

That was the right call — the module has no path to assert universal
ineligibility, and Gate 77's doc 425 explains why: asserting ineligibility on no
grounds discourages a real applicant.

But it leaves a real gap. When a NOFO says *"Federally recognized Indian tribes,
tribal organizations, Alaska Native entities, and eligible BIE-funded schools"*,
that is not silence about state-recognized tribes — it is an enumerated,
exclusive list they are not on. The product can currently only say `unknown`,
which is less than the evidence supports and less than a grant office needs.

## Gaps

1. No opportunity-level funding-lane classifier driven by funding-origin
   evidence.
2. No `federal_pass_through` concept.
3. Three disagreeing lane vocabularies.
4. `sc_state` + `federal_agency` is actively rejected, so pass-through cannot be
   expressed even informally.
5. No mixed-funding representation.
6. No exclusion-evidence model; `not_eligible` is unreachable by design and
   should stay that way.
7. No applicant-class granularity — the existing tiers are three
   (`federally_recognized_tribal_government`, `state_recognized_tribe`,
   `native_nonprofit`), with no `tribal_organization`, `bie_funded_school`,
   `native_business` or `native_individual`.

## Naming divergences to bridge, not fork

| Gate 79 asks | Exists | Where |
| --- | --- | --- |
| `federally_recognized_tribe` | `federally_recognized_tribal_government` | `federal_native_eligibility_service` |
| `sc_state` | `state` | `native_opportunity_discovery_service` |
| `foundation` | `private` | `native_opportunity_discovery_service` |
| `federal` | *(absent)* | `sc_native_routing_service` |

## What Gate 79 must not do

- Must not weaken `forbidden_claim:not_eligible_asserted`. `excluded_by_evidence`
  is a **different, narrower** claim: this programme's cited text excludes this
  applicant class. Universal ineligibility stays unassertable.
- Must not touch the hermetic Grants.gov or corpus write-back guards.
- Must not claim live SC coverage. Gate 78R produced research, not coverage.
