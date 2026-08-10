# Checkpoint — Operator Surfacing Sprints 001–010

**Block:** NF Operator Surfacing Block — NM/WA classify+match review visibility
**Status:** green; continuing

## Delivered
- Operator report schema contract and required fields
- Empty conservative row template with next-check when human review required
- Row validation (no final claim; next-check required)
- Readiness→classification mapping
- Row mapper from review items (missing data, blockers, provenance, confidence)
- Offline fixture inspect for NM/WA

## Invariants held
- No classify+match logic changes
- No live ingestion / source activation
- Unknowns remain visible fields on report rows
