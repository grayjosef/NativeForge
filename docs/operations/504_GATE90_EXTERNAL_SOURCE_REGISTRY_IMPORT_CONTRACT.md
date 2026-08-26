# 504 — Gate 90B/90C: external source registry import contract

`external_source_registry_import_service` (`nf_external_source_registry_import_v1`)
parses the source-discovery CSV into validated registry seed entries.
`external_source_registry_seed_service` turns those into registry objects
without activating anything.

## What this registry is

**A seed registry, not live coverage.** 55 candidate sources, imported from a
committed CSV. Nothing was fetched, nothing is being watched, and no scraper
exists yet.

```text
sources imported          55
sources monitored          0
URLs fetched during import 0
```

## The four separations

Being in the registry answers exactly one question — *is this somewhere we might
look?* Everything else is a separate status field, and each stays independent
so a later reader cannot collapse them:

| Field | Question | Value on every row |
| --- | --- | --- |
| `registry_status` | is it on our list? | `seed_imported` |
| `monitoring_status` | are we watching it? | `not_started` |
| `terms_status` | are we allowed to watch it? | varies |
| `eligibility_status` | can a customer apply? | `NOT_DETERMINED_BY_REGISTRY` |
| `allowability_status` | can an award buy software? | `NOT_DETERMINED_BY_REGISTRY` |

**Source inclusion is not eligibility.** The `eligibility_classes` column is the
dossier's summary of what a program family generally contemplates. The live NOFO
controls, and the registry says so on every row.

**Source inclusion is not allowability.** Same field, same rule.

## Validation

The import is all-or-nothing. A registry that is half-valid is a registry whose
blockers might be in the missing half.

- **Exact column set**, in order. A renamed or missing column is refused, not
  worked around.
- **Required non-blank:** `source_id`, `source_name`,
  `federal_or_state_or_private`, `priority_tier`.
- **Closed vocabularies:** `priority_tier` ∈ Tier 1–4;
  `federal_or_state_or_private` ∈ federal/state/private; `monitoring_method` and
  `robots_or_terms_risk` against their frozensets.
- **Tri-state fields:** `has_api`, `has_rss_or_email`, `requires_login` accept
  `Yes` / `No` / `UNKNOWN` / `Varies` / `API key` and nothing else.
- **Duplicate `source_id`** → refused.
- **A state row with no `state_if_applicable`** → refused. It could not be
  filtered, so it would be visible to every customer — the exact leak Gate 90D
  exists to prevent.
- **A federal row carrying a state** → also refused. That is the same failure in
  the other direction: silently narrowing a nationally available source.

## UNKNOWN is preserved literally

23 cells read `UNKNOWN` and are carried through as the string — never coerced to
`False`, `None`, or a default:

```text
10  state_recognition_supported
 8  has_rss_or_email
 5  has_api
```

The 10 `state_recognition_supported: UNKNOWN` cells are the most important. They
sit beside `federal_recognition_required: No` on all 10 SC rows, and the pairing
means *this program does not require federal recognition* and **nothing** about
whether a state-recognized tribe qualifies. Reading `No` + `UNKNOWN` as
"state-recognized tribes are eligible" would be exactly the collapse Gates 78–79
built guards against.

An unknown capability is not an absent one. This campaign spent four gates on a
field that meant less than it looked like.

## Capability is not approval

`has_api: Yes` says an API exists. It does not say NativeForge may call it.

```text
API-capable sources   5
API-approved sources  0
```

4 of the 5 API-capable rows carry `API_TERMS` obligations. The two facts live in
separate fields (`api_capable`, `api_approved`) and an invariant holds the
approved count at zero.

## Terms status, and why login outranks risk

`terms_status` is derived from the risk bucket **and** the login requirement,
with login resolved first:

```text
HUMAN_REVIEW_ONLY      risk is HUMAN_REVIEW_ONLY, or requires_login = Yes
TERMS_REVIEW_REQUIRED  requires_login in {Varies, API key}, or the risk bucket says so
ATTRIBUTION_REQUIRED   risk is API_TERMS - an obligation to implement, not a blocker
UNKNOWN                risk is UNKNOWN
NO_REVIEW_REQUIRED     everything else
```

The ordering matters and getting it wrong was a real defect caught by a test.
`FED-SIMPLER` carries `requires_login: API key` with `robots_or_terms_risk:
API_TERMS`. Checking the risk bucket first classified it as attribution-only and
therefore clear for automation — but a source needing an API key requires
somebody to obtain and own a credential, which is a decision, not an
implementation detail. Login now resolves first.

Current distribution:

```text
NO_REVIEW_REQUIRED     42
TERMS_REVIEW_REQUIRED   9
ATTRIBUTION_REQUIRED    3
HUMAN_REVIEW_ONLY       1
```

**13 of 55 sources carry an obligation or a blocker**, and 1 (`SC-SCORF`, an
authenticated state portal) may never be automated.

## Why the seed layer does not reuse `build_source_record`

Gate 76's `source_registry_service` has `PROMOTION_STATUSES` including
`approved_for_monitoring` and `monitoring`. Projecting 55 unreviewed external
rows through it would put them one field away from a status they have not
earned.

So the seed layer **bridges** rather than forks — the campaign's standard answer,
applied where the existing vocabulary is too permissive to adopt wholesale.
Every seed carries:

```text
gate76_promotion_status     = "discovered"    weakest member of PROMOTION_STATUSES
gate76_robots_terms_status  = "unreviewed"    weakest member of ROBOTS_TERMS_STATUSES
```

Both are asserted against the imported frozensets by an invariant, so a rename
upstream fails here rather than drifting. A further invariant proves no seed can
carry a value in `MONITORING_STATUSES`.

## Which Tier 1 sources to implement first

Of 33 Tier 1 rows, these carry `low` terms risk and no login — buildable after a
robots check and nothing more:

```text
FED-FR         Federal Register (documented public API)
DOI-BIA-GRANTS HHS-ANA  HHS-IHS  HHS-SAMHSA
USDA-RD  USDA-RECONNECT  USDA-NIFA
HUD-ONAP  HUD-IHBG  DOC-EDA  DOC-NTIA  DOE-INDIAN
EPA-TRIBAL  EPA-GAP  EPA-EN
DOJ-TRIBAL  DOJ-OVW  FEMA-THSGP  CISA-SLCGP
DOT-GRANTS  ED-OIE  DOL-DINAP  NIH-GUIDE (RSS)
```

`FED-GRANTS` (Grants.gov) needs an attribution decision rather than a legal
review — its terms permit search and retrieval with attribution.

**Blocked despite Tier 1:** `FED-SAM-AL` and `NAT-ATC`. NAT-ATC is the
highest-value Native-specific aggregator in the registry, and it is
`scraper_difficulty: high`, JavaScript-driven, with `has_api: UNKNOWN`. It is
the single most valuable blocked source and the best candidate for the first
terms review.

## Invariants

`import_invariant_failures` and `seed_invariant_failures` enforce, among others:

- `urls_fetched` is 0; `network_access_performed`, `monitoring_started`,
  `live_coverage_claimed`, `source_monitoring_claimed` are all `False`
- every row is `seed_imported` / `not_started`
- no row asserts eligibility or allowability
- no duplicate `source_id`
- no state row without a state, no federal row with one
- no seed reaches a Gate 76 monitoring status
- `api_approved_count` and `monitored_count` are 0

A test also greps the import service for every HTTP client, so the no-fetch
guarantee is structural rather than a promise.
