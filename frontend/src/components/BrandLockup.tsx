export type BrandMode = "full" | "compact" | "emblem";

export interface BrandLockupProps {
  /** Rendered height of the artwork in pixels. Width follows the artwork. */
  size?: number;
  /**
   * Which lockup to draw. Omit it and the component chooses from `size`,
   * which is what keeps a caller from asking for a wordmark too small to read.
   */
  mode?: BrandMode;
  /** Deprecated alias for `mode="emblem"`. */
  markOnly?: boolean;
  /** Deprecated alias for `mode="full"`. */
  withTagline?: boolean;
  /**
   * Omit the visually hidden name because the caller already provides one.
   *
   * The shell heading carries the product name; a second hidden name on the
   * lockup announced "NativeForge NativeForge". The hidden name stays on by
   * default: a lockup standing alone must still be announced.
   */
  decorative?: boolean;
  className?: string;
  /**
   * Height-driven is the default so a caller cannot stretch the artwork.
   * Width-driven is for surfaces that already cap the lockup in CSS (sign-in).
   * `size` still governs automatic mode selection even when width drives.
   */
  fit?: "height" | "width";
}

/**
 * The NativeForge lockup, drawn from the canonical brand kit.
 *
 * ## Three modes, because one piece of artwork cannot do three jobs
 *
 * ```text
 * full     960x287 emblem + wordmark + tagline   sign-in, hero
 * compact  720x175 emblem + wordmark             expanded sidebar, headers
 * emblem   256x219 mark alone                    collapsed rail, favicon, tight
 * ```
 *
 * ## Why a size floor, and not just smaller CSS
 *
 * The wordmark is bevelled, outlined artwork, not text. At `height: 32` the
 * 720x175 lockup renders about 132px wide - a 5.5x downscale - and the anvil
 * turns to mush while the wordmark becomes an illegible smear. That is what
 * the onboarding card was showing.
 *
 * Shrinking artwork does not make a smaller logo; it makes a worse one. So
 * below `MIN_WORDMARK_HEIGHT` this component stops drawing the wordmark and
 * draws the emblem instead, which is a MARK and stays legible small because
 * it was designed to. A caller asking for a tiny lockup gets the right logo
 * for that size rather than a crushed version of the wrong one.
 *
 * An explicit `mode` is still honoured. The floor governs the automatic
 * choice, which is the one that silently goes wrong.
 *
 * ## Why this is artwork rather than styled text
 *
 * An earlier version set the wordmark as live text: two coloured spans, one
 * steel and one forge green. The canonical kit's wordmark is not reproducible
 * that way - its bevelling, metallic gradient and outline are the identity,
 * not decoration applied to it.
 *
 * What was kept from the text version is the accessible name. An `alt` on a
 * decorative-looking mark is easy to lose in a refactor, and the name is the
 * part that must not drift.
 *
 * ## One asset for both themes
 *
 * The wordmark is silver and green over dark outlines, which holds on ivory
 * and on the deep forge ground alike. The tagline is the exception: it is set
 * in the kit's navy and goes muddy on a dark field, so `full` belongs on light
 * surfaces like sign-in, not in application chrome.
 */

/** Below this the wordmark is no longer legible, so it is not drawn. */
export const MIN_WORDMARK_HEIGHT = 40;

/** Below this even the tagline line in `full` stops being readable. */
export const MIN_TAGLINE_HEIGHT = 72;

const ART: Record<BrandMode, { src: string; w: number; h: number }> = {
  // Clean lockup already in the repo. The chat-imported kit copies damage
  // the FIND. PURSUE. GOVERN. tagline, so they are not what the product draws.
  full: { src: "/brand/nf-lockup.png", w: 960, h: 287 },
  compact: { src: "/brand/nf-lockup-notag.png", w: 720, h: 175 },
  emblem: { src: "/brand/nf-emblem.png", w: 256, h: 219 },
};

export function resolveBrandMode(
  size: number,
  requested?: BrandMode,
): BrandMode {
  if (requested) return requested;
  if (size >= MIN_TAGLINE_HEIGHT) return "full";
  if (size >= MIN_WORDMARK_HEIGHT) return "compact";
  return "emblem";
}

export function BrandLockup({
  size = 44,
  mode,
  markOnly = false,
  withTagline = false,
  decorative = false,
  className = "",
  fit = "height",
}: BrandLockupProps) {
  const requested: BrandMode | undefined = mode
    ? mode
    : markOnly
      ? "emblem"
      : withTagline
        ? "full"
        : undefined;

  const resolved = resolveBrandMode(size, requested);
  const art = ART[resolved];

  return (
    <span
      className={`nf-lockup ${className}`.trim()}
      data-brand-mode={resolved}
      data-mark-only={resolved === "emblem"}
      data-tagline={resolved === "full"}
    >
      <img
        className="nf-lockup-art"
        src={art.src}
        width={art.w}
        height={art.h}
        // Height drives it and width stays `auto` in CSS, so the intrinsic
        // ratio is preserved and the artwork can never be stretched. Width
        // fit omits the inline height so a CSS width cap can own the box.
        style={fit === "height" ? { height: size } : undefined}
        alt=""
        aria-hidden
        draggable={false}
        decoding="async"
      />
      {decorative ? null : <span className="nf-visually-hidden">NativeForge</span>}
    </span>
  );
}
