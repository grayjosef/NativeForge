"""Render the raster brand assets from the SVG sources.

Rasters are DERIVED, never hand-edited: the SVG is the source of truth, so a
change to the mark cannot leave a stale favicon behind claiming to be the
brand. Re-run this after touching nf-icon.svg or nf-mark.svg.

Only the sizes that actually have a consumer are produced. A folder of
seventeen icon sizes nobody references is not thoroughness, it is clutter
that will drift.
"""

import pathlib

import cairosvg

BRAND = pathlib.Path("/home/josefgray/projects/nativeforge/frontend/public/brand")

#: (source, output, size) - each one has a named consumer.
TARGETS = [
    # Browser tab, for the browsers that still want PNG.
    ("nf-icon.svg", "favicon-32.png", 32),
    ("nf-icon.svg", "favicon-16.png", 16),
    # iOS home screen. 180 is the size Apple actually asks for.
    ("nf-icon.svg", "apple-touch-icon.png", 180),
    # Android / PWA manifest.
    ("nf-icon.svg", "icon-192.png", 192),
    ("nf-icon.svg", "icon-512.png", 512),
]

for source, out, size in TARGETS:
    cairosvg.svg2png(
        url=str(BRAND / source),
        write_to=str(BRAND / out),
        output_width=size,
        output_height=size,
    )
    print(f"  {out:<26} {size}x{size}")

# Social card. Built from the full mark on a forge-green field, because the
# flat app icon looks like a placeholder at 1200x630.
OG = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#04301D"/>
      <stop offset="1" stop-color="#011A10"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <g transform="translate(110 176) scale(4.35)">
    __MARK__
  </g>
  <text x="432" y="300" fill="#EDEBE8" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="76" font-weight="700" letter-spacing="-2">NativeForge</text>
  <text x="436" y="350" fill="#7FB89A" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="27" letter-spacing="0.4">Grant intelligence for Tribal governments</text>
  <rect x="436" y="378" width="78" height="4" rx="2" fill="#C7781A"/>
</svg>"""

mark = (BRAND / "nf-mark.svg").read_text(encoding="utf-8")
inner = mark.split(">", 1)[1].rsplit("</svg>", 1)[0]
cairosvg.svg2png(
    bytestring=OG.replace("__MARK__", inner).encode("utf-8"),
    write_to=str(BRAND / "og-card.png"),
    output_width=1200,
    output_height=630,
)
print(f"  {'og-card.png':<26} 1200x630")
print("rasters rebuilt from SVG source")
