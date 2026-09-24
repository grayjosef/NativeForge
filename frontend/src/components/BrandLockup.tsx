export interface BrandLockupProps {
  /** Rendered size of the mark in pixels. The wordmark scales with it. */
  size?: number;
  /** Hide the wordmark and show the mark alone (tight headers, avatars). */
  markOnly?: boolean;
  className?: string;
}

/**
 * The NativeForge lockup: the mark, then the wordmark.
 *
 * The wordmark is live text rather than an image on purpose. It stays crisp
 * at any zoom, it inherits the theme (steel "Native" against forge-green
 * "Forge", both re-keyed in dark mode), and it is selectable and searchable.
 * An SVG wordmark would have needed an embedded font to render the same
 * everywhere: a large file and a licence question in exchange for nothing.
 *
 * ## Why the name is duplicated
 *
 * Colouring two halves of a word differently needs two elements, and two
 * elements make the accessible name "Native Forge" rather than "NativeForge"
 * — assistive technology inserts a boundary between them. The product is not
 * called Native Forge, and a test asserting the heading name caught it.
 *
 * So the split spans are decorative and hidden from the accessibility tree,
 * and one visually hidden span carries the real name. The visible text stays
 * text; only its announcement is corrected.
 *
 * The mark is `<img>` rather than inline SVG so the browser caches one copy
 * across every place the lockup appears.
 */
export function BrandLockup({
  size = 36,
  markOnly = false,
  className = "",
}: BrandLockupProps) {
  return (
    <span className={`nf-lockup ${className}`.trim()} data-mark-only={markOnly}>
      <img
        className="nf-lockup-mark"
        src="/brand/nf-mark.svg"
        width={size}
        height={size}
        alt=""
        aria-hidden
        draggable={false}
      />
      {markOnly ? null : (
        <span className="nf-lockup-word" style={{ fontSize: size * 0.72 }} aria-hidden>
          <span className="nf-lockup-native">Native</span>
          <span className="nf-lockup-forge">Forge</span>
        </span>
      )}
      <span className="nf-visually-hidden">NativeForge</span>
    </span>
  );
}
