"""Deterministic image safety boundary, applied BEFORE any expensive decode.

Ported from ContractForge at commit ``10dcc5ba``, where it is the guard that
turns OCR from a denial-of-service surface into a bounded operation. The
mechanism is copied; the ContractForge call sites it names are not ours.

THE HOLE THIS CLOSES
--------------------
NativeForge fetches opportunity attachments from federal publishers - agency
portals, Grants.gov, program office pages - so the bytes are untrusted input
from the open internet. A fetch-size cap bounds the ENCODED body. It does not
bound the DECODED image, and that is the whole decompression-bomb problem: a
25 MB PNG can legally decode to billions of pixels, because PNG's filters make
a monochrome gigapixel canvas compress to a few kilobytes.

Two failure shapes matter, and the second is worse:

* Unbounded decode. ``.convert("RGB")`` allocates 3 bytes per pixel, so a
  178-megapixel image is 534 MB of resident memory before Tesseract starts.
* SILENT unbounded decode. ContractForge's image path wrapped the whole
  operation in ``except Exception: return ""``, so a bomb did not merely go
  unbounded - it went unreported, and the caller recorded the document as
  containing no text. For NativeForge that is the cardinal sin: an unread
  document must never become evidence of absence.

Pillow's own protection is not sufficient. ``MAX_IMAGE_PIXELS`` defaults to
~89 million and only raises above **twice** that; between the two it emits a
``DecompressionBombWarning``, and a warning is not an error. So ~178 megapixels
passes by default, warns into a log nobody reads, and allocates half a gigabyte.

WHY HEADER INSPECTION IS SAFE
-----------------------------
``Image.open()`` is lazy: it parses the header and populates ``size``, ``format``
and ``mode`` without decoding pixel data. So the dimensions can be read, and the
pixel count refused, before a single row is decompressed. That is the entire
mechanism — check the declared geometry, then decide.

The bounds are checked in cheapest-first order (bytes, then dimensions, then
pixels, then frames) so a pathological file is refused by the cheapest test that
can refuse it.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not suppress warnings and call that security, and it does not silently
downscale a too-large image — a caller that received a quietly resampled image
would report OCR results for content the customer did not upload. It refuses, with
a reason, and the caller decides what to tell the customer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Any

logger = logging.getLogger(__name__)

#: Formats the OCR paths can actually read. An extension or declared MIME outside
#: this set is refused rather than handed to a parser to find out.
SUPPORTED_IMAGE_FORMATS: frozenset[str] = frozenset(
    {"PNG", "JPEG", "TIFF", "WEBP", "BMP", "GIF"}
)


@dataclass(frozen=True, slots=True)
class ImageBounds:
    """Limits applied before decode.

    Defaults are sized against real customer documents rather than against a
    guess: a 600-dpi scan of US Letter is ~5,100 x 6,600 = 34 megapixels, and a
    phone photograph of a document is ~12 megapixels. 80 megapixels leaves
    generous headroom over both while capping the RGB allocation at ~240 MB, and
    ``max_dimension`` catches the pathological-aspect-ratio case (1 x 500,000,000)
    that a pixel count alone would let through at low totals.
    """

    #: Encoded size. A second line of defence: the upload route already refuses
    #: larger bodies, but OCR also runs against downloaded attachments, which
    #: arrive through a different path with a different limit.
    max_encoded_bytes: int = 25 * 1024 * 1024
    #: Decoded pixels. THE bomb bound.
    max_pixels: int = 80_000_000
    #: Single-axis cap, so an extreme aspect ratio cannot pass on total alone.
    max_dimension: int = 30_000
    #: Multi-frame formats (animated GIF, multi-page TIFF). Each frame decodes
    #: separately, so frames multiply the cost the pixel bound was protecting.
    max_frames: int = 20


class ImageRejected(Exception):
    """An image was refused before decode. Carries a machine-readable reason.

    ``reason`` is a stable token for logs and tests; ``detail`` is the
    customer-safe sentence. They are separate because the token must never drift
    when the wording improves, and the wording must never leak internals.
    """

    def __init__(
        self, reason: str, detail: str, *, measured: dict[str, Any] | None = None
    ) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail
        self.measured = measured or {}


@dataclass(frozen=True, slots=True)
class ImageProbe:
    """What the header said, without decoding."""

    format: str | None
    width: int
    height: int
    frames: int
    encoded_bytes: int

    @property
    def pixels(self) -> int:
        return self.width * self.height * max(1, self.frames)


def probe_image(data: bytes) -> ImageProbe:
    """Read geometry from the header. Decodes nothing.

    Raises :class:`ImageRejected` when the header itself cannot be parsed, which
    covers empty payloads and non-image files.

    IT DOES NOT DETECT TRUNCATION, and that is worth stating plainly because it is
    easy to assume otherwise. A PNG truncated to its first 60 bytes still carries a
    valid signature and IHDR, so ``open()`` succeeds and reports the declared
    geometry; the missing pixel data only surfaces during decode. That is safe —
    the declared geometry is what the bounds are checked against, so a truncated
    bomb is still refused on geometry — but a truncated *ordinary* image reaches
    the decoder and fails there. Callers must therefore still handle decode
    failure; the guard bounds resource use, it does not certify the file.
    """
    if not data:
        raise ImageRejected("image_empty", "The file is empty.")

    from PIL import Image, UnidentifiedImageError

    # Make OUR bound authoritative for the header probe.
    #
    # Pillow's MAX_IMAGE_PIXELS raises from open() above 2x its limit (~178M) and
    # only warns between 89M and 178M. Both thresholds are arbitrary relative to
    # ours, and letting Pillow decide first produced two different code paths with
    # different error reasons and incomplete measurements — a 400-megapixel bomb
    # reported no pixel count at all, because Pillow raised before we could read
    # the geometry.
    #
    # This is NOT "suppress the warning and call it security". Parsing a header is
    # cheap and allocates no pixel buffer, so it is safe to read the declared
    # geometry of any image; the refusal then comes from guard_image()'s explicit,
    # deterministic, fully-measured check. The limit is restored in `finally`, so
    # Pillow's backstop still protects any decode path that does not come through
    # here.
    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        with Image.open(BytesIO(data)) as im:
            # ``n_frames`` is lazy on some plugins and absent on others; a
            # single-frame default is the safe reading, and the frame bound below
            # is what actually protects the multi-frame case.
            frames = int(getattr(im, "n_frames", 1) or 1)
            return ImageProbe(
                format=im.format,
                width=int(im.width),
                height=int(im.height),
                frames=frames,
                encoded_bytes=len(data),
            )
    except UnidentifiedImageError as exc:
        raise ImageRejected(
            "image_unreadable",
            "This file is not an image we can read.",
        ) from exc
    except Image.DecompressionBombError as exc:
        # Defence in depth. With MAX_IMAGE_PIXELS lifted above, this should not
        # normally fire — but if the restore above ever fails, or a plugin raises
        # it independently, the bomb must still be labelled as a bomb rather than
        # as a malformed file, which would send a reader hunting corruption.
        raise ImageRejected(
            "image_pixel_budget_exceeded",
            "This image would use too much memory to process.",
            measured={"encoded_bytes": len(data), "source": "pillow_bomb_error"},
        ) from exc
    except ImageRejected:
        raise
    except Exception as exc:
        # A header that raises anything else is malformed. Refusing here is the
        # point: the alternative is letting a broken decoder run.
        raise ImageRejected(
            "image_malformed",
            "This image appears to be damaged or incomplete.",
        ) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit


def guard_image(data: bytes, bounds: ImageBounds | None = None) -> ImageProbe:
    """Probe and enforce. Returns the probe when the image is acceptable.

    Cheapest check first, so a pathological file is refused by the cheapest test
    that can refuse it.
    """
    limits = bounds or ImageBounds()

    if len(data) > limits.max_encoded_bytes:
        raise ImageRejected(
            "image_too_many_bytes",
            "This file is larger than we can process.",
            measured={"encoded_bytes": len(data), "limit": limits.max_encoded_bytes},
        )

    probe = probe_image(data)

    if probe.format and probe.format.upper() not in SUPPORTED_IMAGE_FORMATS:
        raise ImageRejected(
            "image_unsupported_format",
            f"We cannot read {probe.format} images yet.",
            measured={"format": probe.format},
        )

    if probe.width <= 0 or probe.height <= 0:
        raise ImageRejected(
            "image_zero_dimension",
            "This image reports no width or height.",
            measured={"width": probe.width, "height": probe.height},
        )

    if probe.width > limits.max_dimension or probe.height > limits.max_dimension:
        raise ImageRejected(
            "image_dimension_exceeded",
            "This image is too large in one direction for us to process.",
            measured={
                "width": probe.width,
                "height": probe.height,
                "limit": limits.max_dimension,
            },
        )

    if probe.frames > limits.max_frames:
        raise ImageRejected(
            "image_too_many_frames",
            "This image has more pages than we can process at once.",
            measured={"frames": probe.frames, "limit": limits.max_frames},
        )

    if probe.pixels > limits.max_pixels:
        # The decompression bomb. Refused on DECLARED geometry, before decode.
        raise ImageRejected(
            "image_pixel_budget_exceeded",
            "This image would use too much memory to process.",
            measured={
                "pixels": probe.pixels,
                "limit": limits.max_pixels,
                "width": probe.width,
                "height": probe.height,
                "frames": probe.frames,
                "encoded_bytes": probe.encoded_bytes,
            },
        )

    return probe


def log_rejection(exc: ImageRejected, *, context: str) -> None:
    """Structured record of a refusal.

    Logs the REASON and the measurements, never the bytes and never the filename
    — a filename is customer content and a rejection log is a wide audience.
    """
    logger.warning(
        "image_rejected",
        extra={"reason": exc.reason, "context": context, "measured": exc.measured},
    )


#: Bounds for the PDF-page rasterisation path, which is a different shape of the
#: same risk: a page with an enormous MediaBox rendered at scale 2.0 allocates a
#: bitmap nobody bounded. Expressed as a pixel budget per page so the caller can
#: reduce the render scale instead of failing, which keeps a legitimate
#: large-format document readable.
PDF_PAGE_PIXEL_BUDGET = 40_000_000


def safe_render_scale(
    page_width_pt: float, page_height_pt: float, requested_scale: float
) -> float:
    """Largest scale at or below ``requested_scale`` that stays inside the budget.

    Returns the requested scale unchanged for an ordinary page. A 200-inch-wide
    plan sheet gets a reduced scale rather than a refusal: OCR on a downscaled
    engineering drawing is worth more than an exception, and unlike the image
    path there is no risk of misattributing content, because the caller asked for
    a rasterisation in the first place.
    """
    if requested_scale <= 0:
        return 0.0
    w = max(1.0, float(page_width_pt))
    h = max(1.0, float(page_height_pt))
    projected = w * requested_scale * h * requested_scale
    if projected <= PDF_PAGE_PIXEL_BUDGET:
        return requested_scale
    # scale^2 * area = budget  ->  scale = sqrt(budget / area)
    return max(0.1, (PDF_PAGE_PIXEL_BUDGET / (w * h)) ** 0.5)
