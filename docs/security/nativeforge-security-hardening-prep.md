# NativeForge security hardening prep

This document lists areas to audit in a future dedicated security pass using the external security report (not speculative rewrites).

## Audit backlog

- **Authentication and RBAC**: verify enforcement on demo vs real planes, operator surfaces, and pursuit mutations.
- **Tenant isolation**: confirm org-scoped queries and demo isolation rules cannot leak across org boundaries.
- **Data sovereignty controls**: review storage locations, export paths, and retention for tribal-sensitive artifacts.
- **Audit log integrity**: ensure audit events are append-only from application layers and tamper-evident where required.
- **CORS and security headers**: validate production header sets and allowed origins against deployment topology.
- **Dependency scanning**: integrate SBOM / CVE scanning on Python and npm lockfiles in CI.
- **Input validation**: extend schema validation for uploads, large payloads, and discovery intake batches.
- **Rate limiting**: protect expensive discovery and intake endpoints from abuse.
- **Secrets handling**: scan for accidental secrets; verify settings load only from approved env and vault paths.
- **Export and delete controls**: verify authorized actors for exports and destructive operations.
- **AI and customer data**: enforce prohibition on training or retention of customer content in third-party AI services.

## Notes

- This evening’s changes focused on structure, tests, and offline connector spine; they do not replace a formal security review.
