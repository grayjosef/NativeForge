"""Prove the managed runtime, from inside it.

Two things cannot be established from a developer machine, and both had been
asserted rather than measured:

1. That the MANAGED database refuses the wrong tenant. Migrations running
   there proves the policies were created; it does not prove they hold. A
   verifier that passes against a local container proves the verifier works,
   not that production does.

2. That OCR executes in the image that is actually deployed. The build log
   showing `apt-get install tesseract-ocr` proves a package was fetched. It
   does not prove the binary runs, the language data is present, or the
   extraction contract survives the runtime - and a missing engine is exactly
   the condition that once made a scanned document look empty.

This runs as a one-shot command in the deployed image, on the provider's
private network, and prints a receipt. It creates nothing that outlives it
beyond the disposable tenant rows the isolation gate manages itself.

It is NOT an endpoint. Nothing here is reachable from the internet.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/src")

FIXTURES = Path("/app/fixtures/document_ocr")
DECISIVE = "eligible applicants"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  {name:<52} {'PASS' if ok else 'FAIL'} {detail}", flush=True)


# ─────────────────────────── database ────────────────────────────────────


def verify_database() -> None:
    print("=== MANAGED POSTGRESQL ===", flush=True)
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        record("DATABASE_URL present", False)
        return

    libpq = url.replace("postgresql+psycopg://", "postgresql://")
    import psycopg

    with psycopg.connect(libpq, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SHOW server_version")
        version = cur.fetchone()[0]
        cur.execute("SELECT version_num FROM alembic_version")
        head = cur.fetchone()[0]
        cur.execute("SELECT current_user, session_user")
        current_user, _ = cur.fetchone()
        cur.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        is_super, bypasses = cur.fetchone()
        cur.execute(
            """
            SELECT count(*) FILTER (WHERE true),
                   count(*) FILTER (WHERE c.relrowsecurity),
                   count(*) FILTER (WHERE c.relforcerowsecurity),
                   count(*) FILTER (WHERE pg_get_userbyid(c.relowner) = current_user)
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind = 'r'
               AND EXISTS (SELECT 1 FROM information_schema.columns col
                            WHERE col.table_schema = 'public'
                              AND col.table_name = c.relname
                              AND col.column_name = 'organization_id')
            """
        )
        tenant_tables, rls, force, owned = cur.fetchone()
        cur.execute(
            "SELECT count(*) FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'"
        )
        policies = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r'"
        )
        public_tables = cur.fetchone()[0]

    print(f"  server_version      {version}")
    print(f"  migration_head      {head}")
    print(f"  runtime_role        {current_user}")
    print(f"  public_tables       {public_tables}")
    print(f"  tenant_tables       {tenant_tables}")
    print(f"  rls / force         {rls} / {force}")
    print(f"  policies            {policies}")
    print(f"  tenant tables owned {owned}")
    print()

    record("migration head is 0067", str(head) == "0067", f"head={head}")
    record("every tenant table has RLS", rls == tenant_tables, f"{rls}/{tenant_tables}")
    record(
        "every tenant table FORCEs RLS",
        force == tenant_tables,
        f"{force}/{tenant_tables}",
    )
    # Reported honestly rather than asserted: Railway hands out one role, and
    # whether it is a superuser is a fact about the managed service, not
    # something this script can wish away.
    record("runtime role is not a superuser", is_super is False, f"rolsuper={is_super}")
    record(
        "runtime role cannot bypass RLS", bypasses is False, f"rolbypassrls={bypasses}"
    )
    if owned:
        print(f"  NOTE: runtime role owns {owned} tenant tables - FORCE RLS is what")
        print("        keeps ownership from becoming an exemption.")
    print()

    print("=== ADVERSARIAL MATRIX (managed database) ===", flush=True)
    gate = Path("/app/scripts/check_postgres_tenant_isolation.py")
    if not gate.is_file():
        record("isolation gate present in image", False)
        return
    proc = subprocess.run(
        [sys.executable, str(gate)],
        env={**os.environ, "DATABASE_URL": libpq},
        capture_output=True,
        text=True,
    )
    for line in proc.stdout.splitlines():
        if line.strip():
            print(f"  {line}")
    record(
        "adversarial isolation matrix", proc.returncode == 0, f"exit={proc.returncode}"
    )


# ───────────────────────────── OCR ───────────────────────────────────────


def verify_ocr() -> None:
    print()
    print("=== OCR IN THE DEPLOYED IMAGE ===", flush=True)

    import pytesseract

    from nativeforge.services.document_extraction_service import (
        extract_image_bytes,
        extract_pdf_bytes,
    )
    from nativeforge.services.document_ocr_engine_service import (
        OcrLimits,
        tesseract_version,
    )

    version = tesseract_version()
    langs = pytesseract.get_languages(config="")
    poppler = subprocess.run(["which", "pdftotext"], capture_output=True, text=True)

    print(f"  tesseract           {version}")
    print(f"  languages           {langs}")
    print(f"  poppler pdftotext   {poppler.stdout.strip() or 'ABSENT'}")
    print()

    record("tesseract executable present", bool(version), str(version))
    record("english language data present", "eng" in langs)
    record("poppler present", poppler.returncode == 0)

    def run(name: str, limits: OcrLimits | None = None):
        data = (FIXTURES / name).read_bytes()
        if name.endswith(".pdf"):
            return extract_pdf_bytes(data, limits)
        return extract_image_bytes(data, limits)

    r = run("native_text.pdf")
    record(
        "native PDF extracted without OCR",
        r.status == "EXTRACTED" and r.measured["pages_ocr"] == 0,
        f"{r.status} ocr_pages={r.measured['pages_ocr']}",
    )

    r = run("scanned_decisive_page7.pdf")
    confidences = [p.ocr_confidence for p in r.pages if p.ocr_confidence]
    mean = sum(confidences) / len(confidences) if confidences else 0.0
    record(
        "page-7 decisive eligibility found",
        r.status == "EXTRACTED" and r.pages_unread == 0 and DECISIVE in r.text.lower(),
        f"{r.status} unread={r.pages_unread} conf={mean:.1f}",
    )

    r = run("mixed_native_and_scan.pdf")
    record(
        "mixed document routed per page",
        r.extraction_method == "mixed_pdf" and DECISIVE in r.text.lower(),
        f"native={r.measured['pages_native']} ocr={r.measured['pages_ocr']}",
    )

    r = run("blank_scan.png")
    record(
        "blank scan is EMPTY_CONFIRMED and may prove absence",
        r.status == "EMPTY_CONFIRMED" and r.absence_is_meaningful is True,
        r.status,
    )

    r = run("corrupt.pdf")
    record(
        "corrupt document FAILED and may NOT prove absence",
        r.status == "FAILED" and r.absence_is_meaningful is False,
        r.status,
    )

    r = run("scanned_decisive_page7.pdf", OcrLimits(max_ocr_pages=5))
    record(
        "budget exhaustion is PARTIAL, not silent truncation",
        r.status == "PARTIAL"
        and r.pages_unread > 0
        and r.absence_is_meaningful is False,
        f"{r.status} unread={r.pages_unread} absence={r.absence_is_meaningful}",
    )

    try:
        OcrLimits(ocr_timeout_seconds=0)
        record("a zero OCR timeout is refused", False, "ACCEPTED")
    except ValueError:
        record("a zero OCR timeout is refused", True)


# ────────────────────── document closure cases ───────────────────────────


def verify_closure() -> None:
    print()
    print("=== DOCUMENT CLOSURE ===", flush=True)

    from nativeforge.services.document_extraction_service import extract_pdf_bytes
    from nativeforge.services.document_ocr_engine_service import OcrLimits

    # CASE A: the landing text is insufficient; the attachment decides.
    attachment = extract_pdf_bytes(
        (FIXTURES / "scanned_decisive_page7.pdf").read_bytes()
    )
    record(
        "CASE A decisive evidence comes from the attachment",
        DECISIVE in attachment.text.lower() and attachment.absence_is_meaningful,
        f"{attachment.status}",
    )

    # CASE B: a material attachment is unresolved. Nothing may conclude.
    unresolved = extract_pdf_bytes(
        (FIXTURES / "scanned_decisive_page7.pdf").read_bytes(),
        OcrLimits(max_ocr_pages=5),
    )
    record(
        "CASE B unresolved material document forbids a final negative",
        unresolved.absence_is_meaningful is False and unresolved.pages_unread > 0,
        f"{unresolved.status} unread={unresolved.pages_unread}",
    )

    # The invariant, over everything read in this run.
    from nativeforge.services.opportunity_document_service import ABSENCE_IS_MEANINGFUL

    record(
        "canonical contract unchanged: only PARSED proves absence",
        ABSENCE_IS_MEANINGFUL == frozenset({"PARSED"}),
        str(sorted(ABSENCE_IS_MEANINGFUL)),
    )


def main() -> int:
    print("NativeForge managed runtime verification", flush=True)
    print(f"  NF_APP_ENV   {os.environ.get('NF_APP_ENV', '(unset)')}")
    print(f"  NF_GIT_SHA   {os.environ.get('NF_GIT_SHA', '(unset)')}")
    print()
    try:
        verify_database()
    except Exception as exc:  # noqa: BLE001
        record("database verification completed", False, f"{type(exc).__name__}: {exc}")
    try:
        verify_ocr()
        verify_closure()
    except Exception as exc:  # noqa: BLE001
        record("ocr verification completed", False, f"{type(exc).__name__}: {exc}")

    failed = [n for n, ok, _ in results if not ok]
    print()
    print(
        f"checks={len(results)} passed={len(results) - len(failed)} failed={len(failed)}"
    )
    for name in failed:
        print(f"  FAILED: {name}")
    print("MANAGED_RUNTIME_VERIFICATION=" + ("PASS" if not failed else "FAIL"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
