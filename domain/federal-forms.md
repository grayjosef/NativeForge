# Federal Forms and Autofill Mapping

Distilled from source report Section 6. M0 supports SF-424 preview only.

## Forms to support (priority order)

| Form | Purpose | M0 | M1 | M2 |
|---|---|---|---|---|
| SF-424 | Application for Federal Assistance (cover sheet) | **Preview from profile** | Submit-ready | — |
| SF-424A | Budget Information — Non-Construction | — | Autofill + template | — |
| SF-424B | Assurances — Non-Construction | — | Pre-certify in profile | — |
| SF-424C | Budget Information — Construction | — | — | Autofill |
| SF-424D | Assurances — Construction | — | — | Pre-certify |
| SF-LLL | Disclosure of Lobbying Activities | — | Pre-certify in profile | — |
| SF-425 | Federal Financial Report (FFR) | — | Post-award template | — |
| Project Abstract | Summary of proposed project | — | AI-assisted draft | — |
| Budget Narrative | Justification of all line items | — | AI-assisted draft | — |
| Key Contacts Form | Points of contact | — | Autofill from profile | — |
| Indirect Cost Rate Agreement | IDC documentation | Store in profile | — | — |
| Tribal Resolution | Governing body authorization | — | Template library | — |
| Civil Rights Assurance (SF-424B Item 5) | Non-discrimination certification | — | Pre-certify | — |
| Logic Model | Theory of change diagram | — | AI-assisted template | — |
| Work Plan | Activity timeline | — | Template | — |
| Evaluation Plan | How outcomes will be measured | — | Template | — |
| Letters of Support | Partner endorsements | — | Template | — |
| MOU/MOA Template | Formal partner agreements | — | — | Template |
| Data Management Plan | Data collection and protection plan | — | — | Template |

## SF-424 → entity profile field mapping (M0)

This is the table that drives the M0 autofill. Every mapped field has an AI badge in the UI; every package goes through the review-gate state machine before "final."

| SF-424 field | Profile path | Notes |
|---|---|---|
| 1. Type of Submission | (manual; defaults to "Application") | |
| 2. Type of Application | (manual; user picks New / Continuation / Revision) | |
| 5a. Federal Entity Identifier | (manual; from the NOFO if known) | |
| 5b. Federal Award Identifier | (blank for new applications) | |
| 6. Date Received | (auto-set on submission) | |
| 7. State Application Identifier | (not applicable for tribal applicants typically) | |
| 8a. Legal Name | `tribal_profile.legal_name` | Must match SAM.gov exactly |
| 8b. Employer/Taxpayer ID | `tribal_profile.ein` | |
| 8c. UEI | `tribal_profile.uei` | |
| 8d. Address | `tribal_profile.physical_address.{street, city, county, state, zip}` | |
| 8e. Organizational Unit | (manual or from profile if stored per program) | |
| 8f. Name and contact information of person to be contacted | `tribal_profile.grants_manager` | |
| 9. Type of Applicant | derived from `tribal_profile.entity_type` | mapping table below |
| 10. Name of Federal Agency | from Spark | |
| 11. Catalog of Federal Domestic Assistance | `spark.cfda_assistance_listing` | |
| 12. Funding Opportunity Number | `spark.opportunity_number` | |
| 13. Competition Identification Number | from Spark if present | |
| 14. Areas Affected by Project | (manual or from profile if stored per program) | |
| 15. Descriptive Title of Applicant's Project | (manual per application) | |
| 16. Congressional Districts | `tribal_profile.congressional_district_house` and `..._senate` | |
| 17. Proposed Project Start/End | (manual per application) | |
| 18. Estimated Funding | (manual per application; total = sum of subfields) | |
| 19. Subject to State EO 12372 review | derived from state | |
| 20. Is the Applicant Delinquent on Any Federal Debt | `tribal_profile.debarment_certification` (inverted) | |
| 21. Authorized Representative | `tribal_profile.authorized_representative` | Signature block; not auto-signed |

### Type of Applicant mapping (field 9)

| `entity_type` value | SF-424 Type of Applicant code |
|---|---|
| `federally_recognized_tribe` | F: Native American Tribal Government (Federally Recognized) |
| `tribal_government` | F (typically); G if state-recognized |
| `tribal_nonprofit` | M: Nonprofit with 501(c)(3) status |
| `tribal_college` | H: Public/State Controlled Institution of Higher Education (varies — confirm per institution) |
| `alaska_native_corp` | I: Private Institution of Higher Education (varies — confirm per ANC) |
| `native_hawaiian_org` | M: Nonprofit (varies — confirm per org) |
| `native_nonprofit` | M: Nonprofit |

Mappings marked "varies" are flagged for human review at autofill time. The product never silently picks a code where ambiguity exists.

## Implementation notes

- The fillable SF-424 PDF template is published by GSA. Pin the version in the repo as a fixture; treat as immutable until a deliberate version bump.
- PDF generation uses field-level mapping (not OCR or layout-based filling) to avoid pixel drift.
- Every autofilled field renders with an AI badge in the preview UI.
- The signature block (field 21) is **never auto-signed**. The reviewer transitions the package to `reviewed`; the admin transitions to `approved`. Submission generates the final PDF for human signature outside the system, or via DocuSign integration in M1+.

## What M0 explicitly does not do

- Submit to Grants.gov. The product generates the PDF and tracks the package; submission is manual via the Grants.gov portal.
- Fill SF-424A (budget). Budget development is M1.
- Pre-certify SF-424B assurances. Storing the certifications in profile is M1.
- Generate tribal resolution drafts. M1.
