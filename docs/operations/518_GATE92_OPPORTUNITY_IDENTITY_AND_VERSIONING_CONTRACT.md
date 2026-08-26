# 518 — Gate 92: opportunity identity and versioning contract

Federal grant data has no single global identifier. Identity is therefore
layered, and each layer exists because a naive scheme loses a record the layer
above it cannot see.

## L1 — opportunity identity

Primary key is the normalized `opportunityNumber`: uppercase, whitespace and
hyphens stripped. It is the human-facing, cross-source-quotable key. The numeric
`opportunityId` is a surrogate — stable, and the required input to
`fetchOpportunity`, but agencies do not publish it. Both are stored; neither
alone is sufficient.

`opportunityTitle` is never a key. It is 255 free-text characters an agency may
edit at will, and an invariant fails any L1 or L2 record that carries it as a
key field.

### The composite is mandatory

```text
key = (normalized_opportunity_number, doc_type)   doc_type in {forecast, synopsis}
```

**A forecast and the synopsis it becomes share the same opportunity number.**
Keying on the number alone silently merges them and destroys the forecasted →
posted transition — which is precisely the event a Tribe that saw the forecast
has been waiting for. An invariant fails a key without a doc_type component.

## L2 — versions are immutable rows

```text
version_key = (opportunity_id, doc_type, revision)
```

A revision change writes a new row. Nothing is updated in place, because the
previous version is the evidence that a change happened. The extract's own
`Version` field ("Forecast X" / "Synopsis X") is retained for cross-checking,
never for keying.

## L3 — cross-source joins

**ALN is many-to-many.** A single opportunity can carry several, so it is a
relation, never a scalar column. ALNs are validated against the documented
`NN.XXX` format and a malformed value is reported as malformed rather than
corrected — guessing at an intended value is fabrication.

**Agency identity spans three non-matching namespaces**: Grants.gov
`agencyCode` / `topAgencyCode`; Federal Register `agencies[].slug` +
`parent_id`; and SAM's FPDS codes for Department/Agency with AAC codes for
Office. The contract requires an explicit crosswalk table and sets
`agency_matched_by_name: False`, which an invariant enforces. String-matching
agency names across three namespaces produces wrong joins that look right.

Also in this layer: Federal Register document number (globally unique and
immutable — preferred over `citation`, which is page-based and can collide with
corrections) and docket ID for the Regulations.gov join.

## L4 — fuzzy fallback, quarantined

Sources with no identifier at all — BIA news, HUD Exchange, DOE tables, NSPIRES
— get:

```text
SHA-256(normalized_agency + normalized_title + earliest_deadline_date)
```

This key is **provisional**. It carries `is_provisional: True` and
`must_promote_to_l1_when_number_found: True`, both checked by invariants.
Agency pages routinely announce an opportunity days before — or instead of — a
Grants.gov posting, so an L4 record is a placeholder waiting for its real
identity, not a parallel identity system.

The secondary near-match pass (normalized title similarity plus deadline within
3 days) is a **candidate generator**. `near_match_auto_merges` is False, and an
invariant fails any record where it is not: two grants that look similar are not
evidence that they are the same grant.
