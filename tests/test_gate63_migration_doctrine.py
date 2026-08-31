"""Tests: Gate 63 migration doctrine.

Replaces the brittle "no alembic revision beyond 0019" campaign freeze guards
retired in this gate.

The old guards asserted that a specific *file* did not exist, which made every
future approved migration break a closed campaign's tests. These assert the
properties that actually matter and that stay true as the schema evolves:

  * the migration graph has exactly one head
  * that head is the documented current head
  * the approved Gate 62 migrations exist
  * revision ids are unique
  * the Postgres RLS proof harness exists and is documented
  * SQLite compatibility is documented

When a migration is approved and added, exactly one constant here changes, and
the change is deliberate rather than collateral damage.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "alembic" / "versions"
DOCS = ROOT / "docs" / "operations"

# The current documented head. Update deliberately, with a docs/operations entry.
#
# Gate 96 re-pinned 0027 -> 0028 for nf_raw_source_payloads (source-response
# evidence metadata). Documented in docs/operations/541_GATE96_NF_RAW_SOURCE_
# PAYLOADS_SCHEMA.md. The migration adds a metadata table only; it is not a
# production storage claim, and doc 544 records that production raw payload
# storage remains unavailable because no body store is configured.
#
# Gate 113 re-pinned 0028 -> 0029 for nf_tenant_customer_org_bindings, the
# tenant/customer-org identity binding store. Documented in
# docs/operations/618_GATE113_IDENTITY_BINDING_STORE_SCHEMA.md. The table is
# created empty and stays empty: doc 620 records that creating it permitted no
# storage, because Gate 110's three refusals - no customer auth to supply a
# verifier, no customer persistence to write into, no verified binding to
# store - are untouched by a CREATE TABLE.
#
# Gate 119 re-pinned 0029 -> 0030 for nf_auth_redirect_states, where a redirect
# state and its PKCE verifier live between /login and /callback. Documented in
# docs/operations/649_GATE119_REDIRECT_STATE_TABLE.md. The table stores two
# sha256 digests and never a raw state or verifier, carries no organization_id
# and no RLS - it is created before anybody is authenticated, so there is no
# organization to scope it to, and nf_identities (0023) is the precedent. It is
# created empty and stays empty: doc 651 records that /login still refuses while
# no provider is configured, so nothing writes a row.
#
# Gate 123 re-pinned 0030 -> 0031 for nf_tenant_beta_profiles, the tenant
# behaviour profile. Documented in
# docs/operations/665_GATE123_TENANT_PROFILE_REPOSITORY_CONTRACT.md. It is a
# different object from nf_tribal_profiles (0003), which is the
# grant-application identity - Gate 123A found the two share not one column.
# The table is created empty and stays empty: doc 667 records that a production
# write needs customer_auth_live and a verified operational binding, and both
# are false.
# Gate 124 re-pinned 0031 -> 0032 for nf_awarded_grants, where an awarded
# grant lives. Documented in
# docs/operations/669_GATE124_AWARDED_GRANTS_REPOSITORY_CONTRACT.md. It is not
# a pursuit table: nf_grant_sparks (0004), nf_grant_pursuits (0007) and
# nf_spark_requirements (0005) are all pursuit-side, and Gate 91's separation
# is what keeps an award out of them. The table is created empty and stays
# empty: doc 671 records that a production write needs customer_auth_live and a
# verified operational binding, and both are false.
# Gate 125 re-pinned 0032 -> 0033 for nf_award_requirements, the other half
# of awarded tracking. Documented in
# docs/operations/673_GATE125_AWARD_REQUIREMENTS_REPOSITORY_CONTRACT.md. It is
# not nf_spark_requirements (0005), which is pursuit-side - what a NOFO asks of
# an applicant before they apply. The table is created empty and stays empty:
# doc 675 records that a production write needs customer_auth_live and a
# verified operational binding, and both are false.
CURRENT_HEAD = "0033"

# Migrations added by the approved Gate 62 storage path.
GATE62_MIGRATIONS = ("0023", "0024", "0025", "0026", "0027")

RLS_PROOF_SCRIPT = ROOT / "scripts" / "verify_nativeforge_rls_isolation.sh"


def _revision_ids() -> dict[str, str]:
    """Map migration filename -> declared revision id."""
    out: dict[str, str] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        m = re.search(r'^revision(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', text, re.M)
        if m:
            out[path.name] = m.group(1)
    return out


def _down_revisions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        m = re.search(
            r"^down_revision(?::[^=]+)?\s*=\s*(?:['\"]([^'\"]+)['\"]|None)", text, re.M
        )
        if m:
            out[path.name] = m.group(1)
    return out


def test_revision_ids_are_unique() -> None:
    """A duplicate revision id silently forks the graph."""
    ids = list(_revision_ids().values())
    assert ids, "no revision ids parsed — is alembic/versions populated?"
    dupes = {r for r in ids if ids.count(r) > 1}
    assert not dupes, f"duplicate revision ids: {sorted(dupes)}"


def test_migration_graph_has_exactly_one_head() -> None:
    """Exactly one revision must not be referenced as anyone's down_revision."""
    ids = set(_revision_ids().values())
    downs = {d for d in _down_revisions().values() if d}
    heads = ids - downs
    assert len(heads) == 1, f"expected a single head, found: {sorted(heads)}"


def test_current_head_is_documented_value() -> None:
    ids = set(_revision_ids().values())
    downs = {d for d in _down_revisions().values() if d}
    head = (ids - downs).pop()
    assert head == CURRENT_HEAD, (
        f"migration head is {head!r} but CURRENT_HEAD is {CURRENT_HEAD!r}. "
        "If a migration was approved, update CURRENT_HEAD and add a "
        "docs/operations entry."
    )


def test_alembic_agrees_on_the_head() -> None:
    """Cross-check the parsed graph against alembic itself."""
    try:
        result = subprocess.run(
            ["alembic", "heads"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:  # pragma: no cover
        pytest.skip(f"alembic CLI unavailable: {type(e).__name__}")
    if result.returncode != 0:  # pragma: no cover
        pytest.skip(f"alembic heads failed: {result.stderr[:200]}")
    assert f"{CURRENT_HEAD} (head)" in result.stdout


@pytest.mark.parametrize("rev", GATE62_MIGRATIONS)
def test_gate62_approved_migrations_exist(rev: str) -> None:
    """0023-0027 were approved by MAYHEM_APPROVES_NATIVEFORGE_PROD_STORAGE_GATE61."""
    matches = list(VERSIONS.glob(f"{rev}_*.py"))
    assert matches, f"migration {rev} not found"


def test_identities_and_memberships_migrations_define_their_tables() -> None:
    ident = (VERSIONS / "0023_nf_identities.py").read_text(encoding="utf-8")
    assert "nf_identities" in ident
    assert "uq_nf_identities_issuer_subject" in ident, (
        "identity must be unique on (issuer, subject), not email"
    )

    mem = (VERSIONS / "0024_nf_org_memberships.py").read_text(encoding="utf-8")
    assert "nf_org_memberships" in mem

    # Untrusted sources must not be storable at all. Check the TRUSTED_SOURCES
    # tuple specifically rather than the whole file: the migration deliberately
    # *names* the untrusted sources in a comment explaining their exclusion, so
    # a raw substring search would flag its own documentation.
    m = re.search(r"TRUSTED_SOURCES\s*=\s*\(([^)]*)\)", mem, re.S)
    assert m, "TRUSTED_SOURCES tuple not found in 0024"
    trusted = {v.strip().strip("\"'") for v in m.group(1).split(",") if v.strip()}
    assert trusted == {
        "verified_directory",
        "operator_approved",
        "org_owner_approved",
    }, f"unexpected trusted membership sources: {sorted(trusted)}"
    for untrusted in ("client_header", "dev_header", "cloudflare_access"):
        assert untrusted not in trusted, (
            f"{untrusted} must not be an allowed membership_source"
        )


def test_rls_migration_is_postgres_guarded() -> None:
    """RLS DDL must no-op on SQLite, which is the local test path."""
    rls = (VERSIONS / "0027_rls_membership_authority.py").read_text(encoding="utf-8")
    assert "postgresql" in rls
    assert "ROW LEVEL SECURITY" in rls


def test_rls_proof_harness_exists_and_is_documented() -> None:
    assert RLS_PROOF_SCRIPT.is_file(), "RLS proof script missing"
    body = RLS_PROOF_SCRIPT.read_text(encoding="utf-8")
    # The proof must cover the cross-org denial and the owner-bypass caveat.
    assert "cross_org_read_returns_zero_rows" in body
    assert "app_role_not_superuser" in body
    assert "app_role_owns_no_tables" in body

    proof_doc = DOCS / "389_GATE62_RLS_ISOLATION_PROOF.md"
    assert proof_doc.is_file(), "RLS proof doc 389 missing"


def test_sqlite_compatibility_asymmetry_is_documented() -> None:
    """The seat-cap CHECK is Postgres-only; that must not be silent."""
    mig = (VERSIONS / "0025_organizations_enrichment.py").read_text(encoding="utf-8")
    assert "postgresql" in mig
    assert "NotImplementedError" in mig or "SQLite" in mig, (
        "the Postgres-only constraint asymmetry must be explained in the migration"
    )
    doc = DOCS / "390_GATE62_MIGRATIONS_0023_0027.md"
    assert doc.is_file(), "migration doc 390 missing"


def test_no_migration_uses_postgres_only_now_function_literal() -> None:
    """Regression guard for the Gate 62 bug that broke 98 tests.

    `sa.text("now()")` is PostgreSQL-only and fails on SQLite with
    "unknown function: now()". Use sa.func.now(), which renders per-dialect.
    """
    offenders = []
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r'sa\.text\(\s*["\']now\(\)["\']\s*\)', text):
            offenders.append(path.name)
    assert not offenders, (
        "these migrations use the Postgres-only now() literal instead of "
        f"sa.func.now(): {offenders}"
    )
