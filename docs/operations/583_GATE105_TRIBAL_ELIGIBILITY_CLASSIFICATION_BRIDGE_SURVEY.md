# 583 — Gate 105A: Tribal eligibility classification bridge survey

Surveyed before changing any code. Every claim below was reproduced by running
the tree, not by reading it.

## Where the canonical pattern lives

`src/nativeforge/services/real_grant_classification_input_adapter_service.py:11`

```python
_TRIBAL_TYPE_RE = re.compile(
    r"native american tribal|federally recognized tribe|indian tribe|tribal government",
    re.IGNORECASE,
)
```

Four alternatives. It is the classification lane's definition of "this source
text names a Tribal applicant type", and it drives
`derive_explicit_source_evidence` and `adapt_grant_to_classification_input`.

## Who bridges it, and who shadows it

```text
tribal_grant_eligibility_reingest_service.py:57   imports it, uses it        OK
mixed_corpus_grant_field_derivation_service.py:13 imports it...
mixed_corpus_grant_field_derivation_service.py:24 ...then shadows it        DEFECT
```

Two consumers, one correct. The mixed-corpus module imports the canonical name
on line 13 and rebinds the same name on line 24 to a narrower local regex:

```python
_TRIBAL_TYPE_RE = re.compile(
    r"native american tribal|federally recognized tribe",
    re.IGNORECASE,
)
```

The import is then dead. The module **looks** bridged at the top of the file and
is not, which is why this survived review — the reader's eye stops at line 13.
Ruff reports it as F811.

Both use sites take the shadow:

```text
:84  tribal_type_present, matched against synopsis applicantTypes[].description
:114 the tribal_eligible refinement, matched against eligibility_text
```

## What the shadow misses

Reproduced at phrase level:

```text
phrase                                  canonical  shadow
"Eligible: any Indian tribe"                 yes      no
"Open to tribal governments"                 yes      no
"Indian Tribes"                              yes      no
"Tribal governments"                         yes      no
"federally recognized Indian Tribe"          yes      no
"Federally recognized tribe only"            yes     yes
"Native American tribal organization"        yes     yes
"Open to state governments and universities"  no      no
"Nonprofits having a 501(c)(3) status"        no      no
""                                            no      no
```

Five of seven positives missed. The two it catches are the two the *structured*
Grants.gov taxonomy label happens to contain, which is exactly why the corpus
never exposed it — see below.

## Failure mode: under-detection only, never fabrication

The shadow's alternation is a strict subset of the canonical one. A subset
pattern can only produce fewer matches, so the defect can only fail to notice
Tribal eligibility. It cannot invent it.

Confirmed empirically as well as structurally: re-deriving the whole corpus with
the canonical pattern removed **zero** positives and added three. Nothing the
narrow pattern called Tribal stopped being Tribal.

This is the safe direction, and it is still wrong. Under-detecting Tribal
eligibility in a Native-relevant grant platform means a genuinely eligible
opportunity is scored as if applicant types exclude Tribes.

## Affected surface

```text
applicant_types_include_tribal   directly derived from the shadowed pattern
tribe_eligible_broad             consumes tribal_type_present
```

Those feed classification input, which feeds tenant matching and therefore digest
candidate quality.

**Not** affected: deadlines, deadline provenance, reporting burden, allowability.
Those lanes never touch this pattern, so Gate 104's digest semantics are
untouched by the fix beyond receiving better-classified input.

## Fixture and count impact

Measured by re-deriving the real corpus twice, once per pattern:

```text
rows re-derived:                        57
rows changed by the fix:                 3
field changed:  applicant_types_include_tribal  False -> True
rows:  nf14-mixed-edge-10, nf14-mixed-label_spread-14, nf14-mixed-label_spread-15
positives removed by the fix:            0
```

All three already carried `tribal_eligible: True` while their eligibility text
named Indian tribes or tribal governments, and the derived field nevertheless
said applicant types do not include Tribal. They were self-contradictory records.

### A first measurement of this was wrong, and the correction matters

`build_mixed_real_corpus()` defaults to `use_cached_manifest=True`. The first
probe called it with defaults, got the committed manifest back, and reported zero
impact. The pattern was never re-evaluated. Re-run with
`use_cached_manifest=False`, the true impact is the three rows above.

That is worth recording because it is also the reason the defect went unnoticed
for so long: **everything downstream reads the cached manifest, so nothing in the
tree ever executes this code path.**

### The committed corpus fixture is not regenerated in this gate

`fixtures/real_grants_corpus/nf14_mixed_corpus.json` is tracked, is covered by
Gate 89 provenance attestation, and holds the stale `False` for those three rows.

It is *not* safely owned by this lane, and the survey disproves ownership rather
than assuming it. No script or test in the repository calls
`build_mixed_corpus_manifest()`, and the committed file **already** diverges from
what current code produces, before any Gate 105 change:

```text
nf13-real-fed-025   applicant_types_include_tribal   committed != fresh
nf13-real-fed-025   eligibility_text                 committed != fresh
```

Regenerating the manifest here would silently absorb that unrelated pre-existing
drift into a Gate 105 commit and rewrite an attested corpus fixture. So the
fixture is left alone, the divergence is recorded, and regenerating it under
proper provenance is handed to a follow-up gate.

Consequence stated plainly: **this gate fixes the classifier, not the cached
corpus.** Downstream consumers reading the cached manifest see no change today.

## Which tests covered it

None. Direct references to `mixed_corpus_grant_field_derivation_service` outside
`src/` are zero.

Transitive coverage exists via `mixed_corpus_builder_service` in
`test_sprint332`, `test_sprint334`, `test_sprint339`, `test_gate78`,
`test_gate79`, `test_gate85` and `test_gate89` — but every one of them consumes
the cached manifest, so none of them ever ran the shadowed pattern. Coverage that
never executes the line is not coverage.

## Which tests are missing

```text
phrase-level bridge equivalence: canonical positive => mixed-corpus positive
a guard that fails if the module rebinds a canonical name again
direct derivation tests that bypass the manifest cache
non-Tribal and empty text stay non-Tribal
evidence boundaries preserved at the tenant/digest surface
```

Gate 105B–105F add these.
