# Phase 1 collector readiness

The five Phase 1 sources and what each one still needs before it may collect. **Nothing here collects.**

```text
collectors_active: false
monitors_active: false
live_fetch_performed: false
live_source_coverage: false
```

## Activation matrix

| Source | Collector | Missing preconditions |
| --- | --- | --- |
| `grants_gov_daily_extract` | `not_active` | `activation_preflight_pass`, `grants_gov_attribution`, `raw_payload_store`, `retention_alert_policy` |
| `grants_gov_search2_fetch` | `not_active` | `activation_preflight_pass`, `grants_gov_attribution`, `raw_payload_store`, `amendment_materiality_policy` |
| `federal_register_api` | `not_active` | `activation_preflight_pass`, `raw_payload_store`, `polling_cadence_policy`, `public_inspection_handling` |
| `sam_assistance_listings_api` | `not_active` | `activation_preflight_pass`, `raw_payload_store`, `api_key`, `role_and_rate_limit_policy`, `no_scraping_ack` |
| `usaspending_api_v2` | `not_active` | `activation_preflight_pass`, `raw_payload_store`, `prior_award_only_classification` |

0 of 5 sources may fetch now. 0 may schedule a monitor. 0 may surface customer data.

## Grants.gov attribution

The Grants.gov API terms require this notice to appear prominently within the application:

> This product uses the Grants.gov API but is not endorsed or certified by the U.S. Department of Health and Human Services.

Status: `present_and_verbatim`. Customer-visible surfaces: `runtime_payload`. A copy in documentation or a Python constant does not count - the notice has to reach a browser.

## Terms and legal review queue

| Risk type | Items |
| --- | --- |
| `credential_and_role_required` | 1 |
| `human_review_only` | 62 |
| `login_required` | 0 |
| `terms_review_required` | 118 |
| `terms_text_unretrievable` | 4 |

**185 items, all `pending`.** 0 approved. Every item blocks automation for its source until a person resolves it. The four client-rendered terms pages are queued explicitly: no policy text was ever retrieved from them, and an unread policy nobody is tracking looks exactly like one that was read and cleared.

## Raw payload store

16 required fields, and the store is **not implemented**. It is a required precondition for all five sources because a collector that does not retain its evidence produces records nobody can later distinguish from invention - which is the position Gates 87 to 89 spent four gates measuring from the other end.

