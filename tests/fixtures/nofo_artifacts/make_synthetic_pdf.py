"""Generate the minimal synthetic PDF fixture (Gate 82E).

Committed alongside the binary it produces so the fixture is auditable and
reproducible - a committed binary nobody can regenerate is a committed binary
nobody can check.

Standard library only. No external tools, no PDF dependency. Run from the repo
root:

    python tests/fixtures/nofo_artifacts/make_synthetic_pdf.py

The output is a valid one-page PDF whose visible text is the synthetic banner.
It exists so tests can exercise real-file paths - magic-byte detection, and the
``parser_unavailable`` refusal against an actual PDF rather than a stand-in.
Its text is never read: no PDF backend is installed.
"""

from __future__ import annotations

from pathlib import Path

LINES = [
    "SYNTHETIC TEST FIXTURE - NOT A REAL NOTICE",
    "Written for NativeForge Gate 82 adapter tests.",
    "No real opportunity, agency, programme or deadline.",
    "No opportunity number is claimed.",
]


def build_pdf(lines: list[str]) -> bytes:
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for line in lines:
        escaped = line.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        text_ops.append(f"({escaped}) Tj")
        text_ops.append("T*")
    text_ops.append("ET")
    content = "\n".join(text_ops).encode("ascii")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode("ascii") + b" 0 obj\n" + body + b"\nendobj\n"

    xref_at = len(out)
    count = len(objects) + 1
    out += b"xref\n0 " + str(count).encode("ascii") + b"\n"
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        b"trailer\n<< /Size "
        + str(count).encode("ascii")
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref_at).encode("ascii")
        + b"\n%%EOF\n"
    )
    return bytes(out)


if __name__ == "__main__":
    target = Path(__file__).with_name("synthetic_notice.pdf")
    target.write_bytes(build_pdf(LINES))
    print(f"wrote {target} ({target.stat().st_size} bytes)")
