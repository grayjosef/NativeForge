export interface BrandLockupProps {
  /** Rendered height of the lockup in pixels. Width follows the artwork. */
  size?: number;
  /** Show the emblem alone, without the wordmark (tight headers, avatars). */
  markOnly?: boolean;
  /** Include the "Find. Pursue. Govern." tagline. Light surfaces only. */
  withTagline?: boolean;
  className?: string;
}

/**
 * The NativeForge lockup, drawn from the canonical brand kit.
 *
 * ## Why this is artwork rather than styled text
 *
 * An earlier version set the wordmark as live text: two coloured spans, one
 * steel and one forge green. That was the right call while the identity was a
 * flat mark, and it bought crisp scaling and theme response for free.
 *
 * The canonical kit's wordmark is not reproducible that way. Its bevelling,
 * metallic gradient and outline are the identity, not decoration applied to
 * it, and approximating them with a web font would ship something that is
 * recognisably not the logo. So the artwork is the artwork.
 *
 * ## What was kept from the text version
 *
 * The accessible name. Colouring two halves of a word needs two elements, and
 * two elements make assistive technology announce "Native Forge" with a
 * boundary the product does not have. The fix then was a visually hidden span
 * carrying the real name; the same span survives here, because an `alt` on a
 * decorative-looking mark is easy to lose in a later refactor and the name is
 * the part that must not drift.
 *
 * ## One asset for both themes
 *
 * The wordmark is silver and green over dark outlines, which holds on ivory
 * and on the deep forge ground alike, so there is no dark-mode variant to
 * keep in sync. The tagline is the exception: it is set in the kit's navy and
 * goes muddy on a dark field, so it is opt in and belongs on light surfaces
 * like sign-in, not in application chrome.
 */
export function BrandLockup({
  size = 36,
  markOnly = false,
  withTagline = false,
  className = "",
}: BrandLockupProps) {
  const src = markOnly
    ? "/brand/nf-emblem.png"
    : withTagline
      ? "/brand/nf-lockup.png"
      : "/brand/nf-lockup-notag.png";

  return (
    <span
      className={`nf-lockup ${className}`.trim()}
      data-mark-only={markOnly}
      data-tagline={withTagline}
    >
      <img
        className="nf-lockup-art"
        src={src}
        style={{ height: size }}
        alt=""
        aria-hidden
        draggable={false}
      />
      <span className="nf-visually-hidden">NativeForge</span>
    </span>
  );
}
