# Opportunity Value Intelligence V1 (HABEAS DATA)

**Doctrine:** No material intelligence claim without retrievable evidence.

## Metric

**Known active opportunity value** — the sum of deterministic monetary observations attached to canonical opportunities whose lifecycle is active/open, using methodology `nativeforge.opportunity_value.v1`.

This is not “total available funding” unless source semantics support that; V1 uses conservative selection from `funding_amount_min` / `funding_amount_max` on the canonical graph with current field provenance.

## Active semantics

Included lifecycle states on `nf_canonical_opportunities.lifecycle_state`:

- `posted`
- `amended`
- `forecasted`

Excluded: `closed`, `awarded`, `archived`, `unknown`.

## Value selection

| Condition | Aggregate contribution |
|-----------|------------------------|
| min = max | Point estimate (once) |
| min < max | Min only (program floor) |
| min only | Min (floor) |
| max only | **UNKNOWN** (ceiling ≠ program total) |
| neither | UNKNOWN |
| field conflicts | CONFLICTING (excluded) |

UNKNOWN contributes **zero** to totals; it does not mean the opportunity is worth $0.

## Currency

V1 assumes USD when amounts exist (no currency column on graph). Unlike currencies are not silently converted; expose `totals_by_currency` grouped.

## Deduplication

One row per `canonical_id` in the aggregate query — no second dedupe engine.

## Provenance chain

Hero / public API → aggregate service → canonical opportunity → current `nf_opportunity_field_provenance` rows for funding fields → source observation / payload SHA.

Operator trace: `GET /backend/opportunity-value/provenance/{canonical_id}`.

## Refresh

Public endpoint uses a short in-process TTL cache (120s). Authoritative state updates when ingestion/projection refreshes canonical rows and provenance.

## Public API

`GET /api/public/opportunity-value/active` — public-safe fields only (no per-opportunity list, no tenant data).

## V1.1 enrichment (Grants.gov detail)

Parser/enrichment version: `nf_grants_gov_synopsis_funding_v1` (aggregate methodology unchanged: `nativeforge.opportunity_value.v1`).

Synopsis field mapping:

| Source field | Canonical | Aggregate (V1) |
|--------------|-----------|----------------|
| `estimatedFunding` | min = max (program total point) | KNOWN point |
| `awardFloor` + `awardCeiling` | min / max | KNOWN floor (range) |
| `awardFloor` only | min | KNOWN floor |
| `awardCeiling` only | *(absent)* | UNKNOWN |
| `numberOfAwards` | metadata only | never multiplied |

Operator bounded run: `POST /backend/opportunity-value/enrichment/grants-gov-active?dry_run=false&limit=N` or `scripts/run_grants_gov_active_funding_enrichment.py --apply --limit N`.

## Limitations (V1)

- Eligibility-value breakdown deferred (Gate 174 funnel → V2).
- Native-relevant value subset when current Gate 173 assessments exist.
- Blocked-value-by-reason not fabricated; seam documented in service payload.
- NOFO/document funding (Gate 175 pilot) not wired to canonical provenance in V1.1.

## Operator diagnostics

`GET /backend/opportunity-value/diagnostics`
