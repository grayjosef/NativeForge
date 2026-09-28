"""Cut the brand assets out of the canonical brand kit.

Assets are DERIVED, never hand-edited. The kit board at
``brand/nativeforge-brand-kit.webp`` is the source of truth, so a change to
the identity cannot leave a stale favicon behind claiming to be the brand.
Re-run this after replacing the board.

The previous version rendered these from ``nf-icon.svg`` with cairosvg. That
mark is superseded, and the SVGs are gone: the kit arrived as a single raster
board carrying every lockup, so each asset is a crop of the artwork rather
than a redraw of it. Nothing here alters the identity.

## Why the background is flood filled rather than keyed

The wordmark's "Native" is silver through white and the anvil carries bright
specular highlights. Keying every white pixel punches holes straight through
both. Every element on the board is closed by a dark outline, so a flood fill
inwards from the four corners removes the page and stops at those outlines,
leaving interior whites intact.

## Why the icons come from the large emblem

The board has its own icon row, about 110px tall. Upscaling that to a 512px
app icon gives a soft, artefacted mark. The emblem inside the primary lockup
is roughly 440x375, so every icon size is a downscale instead: sharper at
every size, and the same artwork.

## Why there is no SVG favicon

There was one, and it outranked every PNG beside it. Browsers prefer an SVG
icon, so the tab kept showing the superseded mark however many PNG sizes were
regenerated. A stale vector that outranks every correct raster is worse than
no vector at all.
"""

import pathlib

from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARD = ROOT / "brand/nativeforge-brand-kit.webp"
OUT = ROOT / "frontend/public/brand"

#: The dark forge ground the board uses behind its app icon.
TILE = (10, 32, 24)

#: Crops measured from the board. Keyed by output name so a mis-measured
#: region shows up as one wrong asset rather than a silent shift in all of
#: them.
REGIONS = {
    "lockup": (150, 20, 1570, 420),
    "emblem": (150, 20, 610, 400),
    "stacked": (755, 440, 1100, 680),
    "mono-dark": (1245, 838, 1400, 935),
    "mono-light": (1420, 838, 1570, 935),
}

#: Display widths at 2x device pixel ratio. The full-resolution crops are far
#: larger than anything renders, and the header lockup loads on every page.
WIDTHS = {
    "nf-lockup-notag.png": 720,
    "nf-lockup.png": 960,
    "nf-lockup-stacked.png": 480,
    "nf-emblem.png": 256,
}


def cut_background(img: Image.Image, tolerance: int = 26) -> Image.Image:
    img = img.convert("RGBA")
    flat = img.convert("RGB")
    w, h = img.size
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(flat, seed, (255, 0, 255), thresh=tolerance)
    src, out = flat.load(), img.copy()
    dst = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y] == (255, 0, 255):
                dst[x, y] = (0, 0, 0, 0)
    return out


def trim(img: Image.Image, pad: int = 6) -> Image.Image:
    box = img.getbbox()
    if box:
        img = img.crop(box)
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    out.paste(img, (pad, pad))
    return out


def contain(img: Image.Image, box: int, inset: float) -> Image.Image:
    target = box * inset
    scale = min(target / img.width, target / img.height)
    return img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
        Image.LANCZOS,
    )


# Product teal (--nf-teal). Flat ink only: the tagline pixels change color
# and keep their alpha. Nothing else in the lockup is touched.
TAGLINE_TEAL = (63, 156, 143)
PUBLISHED_LOCKUP = (960, 287)


def dark_field_lockup(lockup: Image.Image) -> Image.Image:
    """FIND. PURSUE. GOVERN. in teal, for the midnight shell.

    The kit sets that line in navy, which disappears on the product field.
    This recolors only those ink pixels on the published 960×287 lockup.
    A different size is refused so a crop change cannot paint the wordmark.
    """
    img = lockup.convert("RGBA")
    if img.size != PUBLISHED_LOCKUP:
        width = PUBLISHED_LOCKUP[0]
        if img.width != width:
            img = img.resize(
                (width, round(img.height * width / img.width)), Image.LANCZOS
            )
    if img.size != PUBLISHED_LOCKUP:
        raise SystemExit(
            f"dark lockup expects {PUBLISHED_LOCKUP[0]}x{PUBLISHED_LOCKUP[1]}, got {img.size}"
        )
    out = img.copy()
    src, dst = img.load(), out.load()
    w, h = img.size
    y0, y1 = 242, 268
    x0, x1 = 350, 940
    for y in range(y0, y1):
        for x in range(x0, min(x1, w)):
            r, g, b, a = src[x, y]
            if a < 12:
                continue
            if g > 70 and g > r and g > b:
                continue
            if r > 70 and r > g and r > b:
                continue
            if r < 90 and g < 90 and b < 120 and (b + 15 >= g) and max(r, g, b) < 100:
                dst[x, y] = (*TAGLINE_TEAL, a)
    return out


def save(img: Image.Image, name: str) -> None:
    width = WIDTHS.get(name)
    if width and img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    path = OUT / name
    img.save(path, optimize=True)
    print(f"  {name:<26} {img.width:>4}x{img.height:<4} {path.stat().st_size:>7,} bytes")


def main() -> None:
    if not BOARD.is_file():
        raise SystemExit(f"brand board not found: {BOARD}")
    OUT.mkdir(parents=True, exist_ok=True)
    board = Image.open(BOARD).convert("RGBA")
    print(f"board {BOARD.name} {board.size}")

    emblem = trim(cut_background(board.crop(REGIONS["emblem"])))
    lockup = trim(cut_background(board.crop(REGIONS["lockup"])))

    save(emblem.copy(), "nf-emblem.png")
    save(lockup.copy(), "nf-lockup.png")
    # Same crop as nf-lockup.png. Only the tagline ink is teal.
    published = Image.open(OUT / "nf-lockup.png")
    dark = dark_field_lockup(published)
    save(dark, "nf-lockup-dark.png")
    save(trim(cut_background(board.crop(REGIONS["stacked"]))), "nf-lockup-stacked.png")
    for key in ("mono-dark", "mono-light"):
        save(trim(cut_background(board.crop(REGIONS[key]))), f"nf-emblem-{key}.png")

    # The tagline is set in the kit's navy and goes muddy on a dark field, so
    # application chrome uses a lockup without it.
    notag = lockup.crop((0, 0, lockup.width, round(lockup.height * 0.80)))
    save(trim(notag), "nf-lockup-notag.png")

    # Tiled icons. The emblem is inset rather than bled to the edges so the
    # maskable variant survives a circular crop.
    for size, name in ((512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")):
        tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(tile).rounded_rectangle(
            (0, 0, size - 1, size - 1), radius=round(size * 0.22), fill=(*TILE, 255)
        )
        mark = contain(emblem, size, 0.74)
        tile.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
        save(tile, name)

    # Small favicons carry no tile. Sharpened because the anvil's inner
    # detail mushes below 32px otherwise.
    for size in (32, 16):
        mark = contain(emblem, size, 1.0)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
        save(canvas.filter(ImageFilter.UnsharpMask(radius=0.6, percent=110)), f"favicon-{size}.png")

    og = Image.new("RGBA", (1200, 630), (*TILE, 255))
    art = contain(lockup, 900, 1.0)
    if art.height > 300:
        art = contain(lockup, 300, 1.0)
    og.alpha_composite(art, ((1200 - art.width) // 2, (630 - art.height) // 2 - 10))
    og.convert("RGB").save(OUT / "og-card.png", quality=92, optimize=True)
    print(f"  {'og-card.png':<26} 1200x630  {(OUT / 'og-card.png').stat().st_size:>7,} bytes")


if __name__ == "__main__":
    main()
