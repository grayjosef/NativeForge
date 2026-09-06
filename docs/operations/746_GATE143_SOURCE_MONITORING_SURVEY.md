# 746 — Gate 143A: what source monitoring already is, and what is missing

Survey before implementation. Nothing was built while writing this. **No live
source was called at any point in producing it.**

## Why `source_monitoring_live` is currently false

Derived, in `source_scheduler_readiness_service`, from four conjuncts:

```text
runtime_mode in LIVE_RUNTIME_MODES     dry_run_in_process        FAILS
background_worker_available            absent                    FAILS
periodic_trigger_available             absent                    FAILS
persistent_backend_live                absent                    FAILS
```

Five components missing:

```text
background_worker  periodic_trigger  persistent_backend
production_raw_payload_store  scheduler_runtime
```

That flag has never been a lie. It reports an absence, and a comment in the
module records that Gate 99D tightened it once already — the test moved from
"is a scheduler package installed" to "what MODE is it in", because
`dry_run_in_process` was passing a check that meant to ask about production.

## What already exists, and it is a great deal

Gates 90–101 built most of the machinery this gate needs to *reason about*:

```text
live_network_guard_service                the permission model: terms,
                                          activation, collector, robots,
                                          credentials, attribution, rate limits
hermetic_network_enforcement_service      Gate 94's choke point scanner
source_terms_review_queue_service         the five blocked items, by name
source_ingestion_seed_schema_service      177 registry rows
external_source_registry_import_service   the DB registry
source_scheduler_readiness_service        the four conjuncts above
polite_http_fetch_service                 rate limits, user agent
nativeforge_user_agent_service            the canonical UA
raw_payload_body_store_contract_service   where bytes would land (Gate 97)
source_schedule_decision_service          when a check would be due
```

`live_network_guard_service` already carries the exact vocabulary Gate 143 was
asked to enforce:

```text
TERMS_BLOCKING       TERMS_REVIEW_REQUIRED  UNKNOWN
TERMS_HUMAN_ONLY     HUMAN_REVIEW_ONLY
TERMS_NON_BLOCKING   NO_REVIEW_REQUIRED  ATTRIBUTION_REQUIRED
ACTIVATION_SATISFYING     activation_allowed
COLLECTOR_SATISFYING      active
ROBOTS_SATISFYING         allowed  absent
CREDENTIAL_SATISFYING     present_and_valid  not_required
ATTRIBUTION_SATISFYING    present_and_verbatim  not_required
```

So this gate does **not** invent a second permission model. It builds the thing
that is missing: something that walks the registry rows and asks that guard
about each one, and a readiness roll-up that names what activation still needs.

## What the registry actually contains

`fixtures/source_ingestion/NF_SOURCE_SEED_2026.csv`, 177 rows:

```text
tier                 1: 61      2: 51      3: 65
adapter_key          grants_gov_federal 61   state_portal_generic 51
                     foundation_org_page 65
access_posture_hint  public 127   login 37   members 13
source_health_status healthy 122  attention_needed 47  degraded 3  failing 5
resolver_url_status  resolved 136  login 36  dead 5
```

Columns: `seed_id`, `canonical_source_id`, `source_name`, `source_url`, `tier`,
`adapter_key`, `access_posture_hint`, `source_health_status`,
`catalog_accounting_bucket`, `resolver_url_status`, `health_evidence`.

**There is no `terms_status` column.** That is the finding that shapes 143B: a
row's terms status is not in the registry, so an allowlist cannot read one off
and must treat its absence as `UNKNOWN` — which `live_network_guard_service`
already classifies as **blocking**. Deny by default falls out of the data rather
than having to be imposed on it.

The DB registry `nf_opportunity_sources` (40 rows) carries operational columns —
`check_method`, `check_interval_days`, `last_check_status`,
`consecutive_failure_count`, `source_health_status` — and also no terms column.

## Which sources are blocked, and by what

`source_terms_review_queue_service` produces five items, all
`automation_blocked`:

```text
SAM-CREDENTIAL-ROLE          credential_and_role_required
                             scraping prohibited; API key AND a SAM role needed
SPA-TERMS-GRANTS-GOV         terms_text_unretrievable, human_review_only
SPA-TERMS-REGULATIONS-GOV    terms_text_unretrievable, human_review_only
SPA-TERMS-USASPENDING        terms_text_unretrievable, human_review_only
SPA-TERMS-REPORTER-NIH       terms_text_unretrievable, human_review_only
```

The four SPA items are worth reading carefully. Those terms pages are
client-rendered and served **no policy text** to the research pass. The queue
seeds them regardless of what the registry says, because their absence from the
registry's risk columns is precisely the problem — nobody knows what those terms
say, and "we could not read them" is not "they permit this".

## Source classes, as they stand

```text
Grants.gov      61 seed rows use adapter_key grants_gov_federal, and the
                grants.gov terms page itself is HUMAN_REVIEW_ONLY. Attribution
                is a live_network_guard concern (ATTRIBUTION_REQUIRED) and is
                preserved, not weakened.
SAM.gov         ZERO seed rows. The only SAM item is the credential/role review
                entry. No SAM call is possible from this registry and none is
                attempted.
SC / state      51 rows on state_portal_generic. 36 rows resolve to a login
                page, which is not a public source.
foundations     65 rows on foundation_org_page. Terms unknown for all of them.
fixture         nf-fixture-* ids, hermetic only, and never a real host.
unknown         anything not in the 177 — refused by id.
```

## Does an approved-source allowlist exist?

No. `live_network_guard_service` decides about **one fetch** given facts a
caller supplies; nothing walks the registry and produces the set of sources that
would pass. That is 143B.

## Does a collector activation path exist?

No, and the absence is layered:

```text
scheduler_runtime           absent
background_worker           absent
periodic_trigger            absent
persistent_backend          absent
production_raw_payload_store absent
COLLECTOR_SATISFYING        {"active"} — nothing is
ACTIVATION_SATISFYING       {"activation_allowed"} — nothing is
```

## Does the choke point prevent accidental egress?

`hermetic_network_enforcement_service.scan_for_network_call_sites()` runs clean
right now:

```text
findings              0
unapproved_count      0
clean                 True
invariant failures    none
```

It parses `services/` with `ast` for network imports and call sites against an
approved-site list. That is the mechanism Gate 143E must extend rather than
duplicate — a second scanner would be a second answer to one question.

## Can the tenant watchlist reference monitorable sources?

Yes, since Gate 140. `nf_source_watchlist_entries.source_id` is checked against
the same 177 registry ids, and every watchlist response already carries
`source_monitoring_live: false` and `last_checked_at: null` per entry. Gate 140
documented the distinction this gate has to hold: **watching is not
monitoring.**

So the join Gate 143 can make honestly is: for a source a tenant is watching,
say *what would block monitoring it* — without checking it.

## What a safe preflight can prove without live calls

```text
a source id is or is not in the registry
its access posture, health and resolver status
what its terms status is — and that UNKNOWN is blocking
whether it needs a credential nobody has
whether a human must look first
what a collector config would still be missing
that no live-call path is active anywhere in the service tree
```

What it cannot prove:

```text
that a source is reachable
that its terms permit collection
that robots.txt allows it
that a credential works
that a rate limit is respected in practice
anything about content
```

So a passing preflight may set `source_monitoring_preflight_ready` and may
never set `source_monitoring_live`. Same separation Gate 141 made between
`hermetic_fake_verified` and `production_verified`, and Gate 142 between
`email_delivery_readiness` and `email_delivery`.

## Exact activation blockers remaining

```text
terms review              5 queue items, all automation_blocked, 4 human-only
terms status per row      ABSENT from the registry, so UNKNOWN, so blocking
SAM.gov                   API key AND a role approval — neither exists
Grants.gov attribution    ATTRIBUTION_REQUIRED must be present and verbatim
robots.txt                never fetched, so unknown, so blocking
scheduler runtime         absent
background worker         absent
periodic trigger          absent
persistent backend        absent
production raw payload store  absent (Gate 141: object_store_configured false)
per-source activation approval  nothing is activation_allowed
```

## What this gate will and will not do

Will:

```text
build an allowlist that walks the registry and classifies every row
build a collector configuration preflight, names not values
build a readiness roll-up naming source_monitoring_preflight_ready
extend the choke point into a no-live-call VERIFIER
add readiness routes behind the demo org session, if they refuse safely
keep source_monitoring_live false, and fail an invariant if a preflight sets it
```

Will not:

```text
call a live source
activate a collector
scrape anything
fetch robots.txt
call SAM.gov or Grants.gov
bypass TERMS_REVIEW_REQUIRED or HUMAN_REVIEW_ONLY
fix a URL from memory
claim live coverage
add a dependency or touch uv.lock
```
