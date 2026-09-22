# Gate 171E — Live Source Authorization Packets

**Status: awaiting explicit human approval. No request has been issued to either host.**

Funding-source network requests during Gate 171 so far: **0**, measured in every
phase. The repository's live source-network history is unchanged since Gate 163:
one robots GET and one Search2 POST, both to a single already-authorized host.

---

## How to read the fact classes

Every fact below carries one of three labels, and the distinction is the whole
point of this document.

| label | meaning |
|---|---|
| **ESTABLISHED** | derived from a row, a file or a decision already in this repository |
| **PROPOSED** | written down so it can be approved or corrected — *not* verified here |
| **UNKNOWN** | not established, and **not establishable without a request** |

Nothing has been inferred about terms, robots or access. Those facts require
contacting the host, which is exactly what this checkpoint governs, so for both
sources they are UNKNOWN and stay UNKNOWN until after approval.

---

## SOURCE #2 — document / HTML family

| field | value | class |
|---|---|---|
| `SOURCE_ID` | `nf-seed-2026-html-bia-program-page` | PROPOSED |
| `SOURCE_NAME` | BIA program page — Tribal Tourism Grant Program (TTGP) | ESTABLISHED (registry row) |
| `AUTHORITY` | Bureau of Indian Affairs, U.S. Department of the Interior | ESTABLISHED |
| `BASE_URL` | `https://www.bia.gov/service/grants/ttgp/apply-ttgp-grant` | ESTABLISHED (registry row) |
| `ADAPTER_KEY` | `bia_program_page_html` | ESTABLISHED (built this gate) |
| `TRANSPORT_METHOD` | `GET` | PROPOSED |
| `REQUEST_SHAPE` | `GET <base_url>`, header `Accept: text/html`, no query, no body | PROPOSED |
| `AUTH_REQUIRED` | no | PROPOSED |
| `CREDENTIAL_REQUIRED` | no | PROPOSED |
| `TERMS_FACTS` | **UNKNOWN** — no terms review on file for this source | UNKNOWN |
| `ROBOTS_FACTS` | **UNKNOWN** — `bia.gov` robots.txt has never been fetched | UNKNOWN |
| `RATE_LIMIT_FACTS` | **UNKNOWN** published; adapter self-imposes 1 request/run, ≥24h between runs, honors `Retry-After`, abandons on 429 | PROPOSED |
| `ATTRIBUTION_REQUIRED` | yes — "Source: Bureau of Indian Affairs, U.S. Department of the Interior" | PROPOSED |
| `EXPECTED_RESPONSE_TYPE` | `text/html` | PROPOSED |
| `PAGINATION_MODEL` | `single_document` — one page, no cursor | ESTABLISHED (descriptor) |
| `MAXIMUM_FIRST_REQUEST_SCOPE` | **exactly 1 GET**, 1 page, ≤1 record, crawl depth **0** | ESTABLISHED (descriptor bounds) |

**WHY THIS SOURCE.** BIA is the most Native-authoritative publisher in the
registered corpus — 6 of 40 rows, more than any other host, and the only
publisher whose entire remit is tribal government. It is a materially different
workload from Grants.gov: one HTML document, no query protocol, link extraction
instead of record arrays.

**KNOWN_OVERLAP_EXPECTATION.** Plausible but **not assumed**. BIA programs
appear in Grants.gov, so an assistance-listing or opportunity-number match is
possible. Gate 171J explicitly permits `REAL_OVERLAP_OBSERVED=false`, and no
second request will be made to hunt for one.

**UNKNOWNs.** Terms. Robots. Published rate limits. Whether the page carries a
deadline in a structurally readable form — the adapter deliberately does **not**
pattern-match dates out of prose, so it may legitimately report a record with no
deadline rather than a guessed one.

**ALTERNATE #2:** IHS — Tribal Management Grant, `https://www.ihs.gov/ODSCT/tmg/`
(ESTABLISHED registry row). Same shape, different publisher, so it hedges
publisher-specific robots/terms risk rather than program risk.

---

## SOURCE #3 — API / paginated / structured family

| field | value | class |
|---|---|---|
| `SOURCE_ID` | `nf-seed-2026-api-federal-register-documents` | PROPOSED |
| `SOURCE_NAME` | Federal Register — documents | ESTABLISHED (`fed.federal_register.notices`) |
| `AUTHORITY` | Office of the Federal Register, National Archives (NARA) | ESTABLISHED |
| `BASE_URL` | `https://www.federalregister.gov` | **ESTABLISHED** (code seed catalog) |
| endpoint path | `/api/v1/documents.json` | **PROPOSED — NOT verified by this repository** |
| `ADAPTER_KEY` | `federal_register_documents_json` | ESTABLISHED (built this gate) |
| `TRANSPORT_METHOD` | `GET` | PROPOSED |
| `REQUEST_SHAPE` | `per_page=20`, `page=1`, `order=newest`, `conditions[type][]=NOTICE`, `fields[]=document_number,title,type,publication_date,agencies,html_url,comments_close_on` | **PROPOSED** |
| `AUTH_REQUIRED` | no | PROPOSED |
| `CREDENTIAL_REQUIRED` | no | PROPOSED |
| `TERMS_FACTS` | **UNKNOWN** — catalog classes it `public_api`; that is a classification, not a terms review | UNKNOWN |
| `ROBOTS_FACTS` | **UNKNOWN** — `federalregister.gov` robots.txt has never been fetched | UNKNOWN |
| `RATE_LIMIT_FACTS` | **UNKNOWN** published; adapter self-imposes 1 request/run, ≥1h between runs, honors `Retry-After`, abandons on 429 | PROPOSED |
| `ATTRIBUTION_REQUIRED` | yes — "Source: Office of the Federal Register, NARA" | PROPOSED |
| `EXPECTED_RESPONSE_TYPE` | `application/json` | PROPOSED |
| `PAGINATION_MODEL` | `page_number`; continuation read from `next_page_url`, **believed only through the cursor** | ESTABLISHED (descriptor) |
| `MAXIMUM_FIRST_REQUEST_SCOPE` | **exactly 1 GET**, 1 page, ≤20 records | ESTABLISHED (descriptor bounds) |

**WHY THIS SOURCE.** The repository's own federal seed catalog names it, with
the rationale that it is the *"authoritative channel for funding notices,
deadline extensions and amendments"* and the evidence source behind the Gate 76
freshness rules. That makes it the one candidate whose value is specifically
Gate 170's: **a second, independent witness to a deadline moving.** It is also
the only API-shaped candidate available — the 40-row database registry contains
**zero**, every row being `check_method='web_page'`.

An independent corroboration: Gate 169's identity layer already lists
`federal_register` as one of the three agency-code namespaces a crosswalk must
reconcile. The identity substrate was built expecting this namespace.

**KNOWN_OVERLAP_EXPECTATION.** Higher than source #2. Agencies publish funding
notices in the Federal Register that also appear on Grants.gov, so an
opportunity-number or agency+title match is realistic. Still not assumed.

**UNKNOWNs.** Terms. Robots. Published rate limits. **The exact endpoint path,
parameter names and response envelope** — all PROPOSED from general knowledge,
none verified here. `read_records` is therefore a *hypothesis* and its
conformance report says so (`fixtures_are_real: false`).

**ALTERNATE #3:** SAM.gov assistance listings, `https://sam.gov/`
(ESTABLISHED catalog entry, `public_api`). **Weaker alternate, and the reason is
disqualifying-adjacent**: SAM.gov API access requires a registered API key, so
`CREDENTIAL_REQUIRED=true` and it would need a credential decision this gate has
not prepared.

---

## What is already built, behind the boundary

| | |
|---|---|
| 171A survey | 40 registry rows + 6 code-catalog seeds classified, 0 network attempts |
| 171C generic contract | `SourceDescriptor`, `RawEvidenceEnvelope`, `PageCursor`, `SourceRecord`, `DocumentReference`, `CollectionOutcome` — 6 new, 4 reused |
| 171D conformance harness | 14 checks, both adapters **conformant** against synthetic fixtures |
| 171Q genericity audit | `generic_layer_source_leaks=0`, `identity_branches=0`, scanner proven falsifiable |

Both adapters **refuse to build a request when handed no authorization** — that
is one of the 14 conformance checks, and it is checked by calling them with
`authorization=None` and requiring an exception.

---

## Required approval

```text
SOURCE_2_LIVE_FETCH_APPROVAL_REQUIRED=true
SOURCE_3_LIVE_FETCH_APPROVAL_REQUIRED=true
```

Nothing in the Gate 171 prompt constitutes approval of these specific
identities. On explicit approval of the exact source identities above, the
authorized sequence is, per source, in order:

1. **171F** record the decisions through the Gate 166 authority model
2. **171G** minimum robots/access preflight — **one** request per host
3. **171H / 171I** **one** bounded collection request per source

That is a maximum of **4 requests total**, 2 per host, and no others.
