"""The interface's secondary text must stay readable.

`--nf-faint` was #7e8a82, which measures 3.21:1 against the page ground. It
carries the eyebrow above every page title, every metric's explanatory note,
the workflow step summaries, the deadline dates and the muted badges - 23
failing elements on the workspace alone, from one token. Restraint had become
invisibility.

Nothing caught it. Component tests render and assert that text is present,
and text at 3.2:1 is present. It took measuring the rendered page in a
browser, and a colour token is exactly the kind of thing that drifts back the
next time somebody decides a grey looks heavy.

## Why this lives in the Python suite

It belongs beside the stylesheet, and the first attempt put it there - a
vitest file reading `index.css`. Two bundler problems followed: `node:fs`
type-checks only with node type definitions this project does not install,
and a `?raw` import resolves to an empty string because vitest stubs CSS out
by default, so every token silently "went missing" and thirteen tests failed
for the wrong reason.

Reading a file is not worth a dependency or a bundler workaround. Here it is
four lines and runs with everything else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CSS_PATH = Path(__file__).resolve().parents[1] / "frontend" / "src" / "index.css"

#: The ink scale, darkest first.
INK = ("--nf-text", "--nf-muted", "--nf-muted2", "--nf-faint")

#: Every surface those tokens are drawn on. Measured against all three rather
#: than against white alone: the page ground is the harder one and it is where
#: the eyebrow and the quiet notes actually sit.
GROUNDS = ("--nf-page", "--nf-card", "--nf-card-muted")

#: WCAG AA for body text. These tokens carry sentences, not decoration.
MINIMUM_RATIO = 4.5


def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


#: How many `var()` hops to follow before giving up. The brand layer is one
#: hop today; the cap stops a cycle from hanging the suite.
_MAX_INDIRECTION = 8


def _token(name: str) -> str:
    """Resolve a token to a hex literal, following `var()` indirection.

    The brand work put a palette layer underneath these names, so the ground
    tokens stopped being hex and became aliases:

    ```css
    --nf-page: var(--nf-bg-primary);
    --nf-card: var(--nf-surface);
    ```

    The first version of this reader matched a hex literal only, so it raised
    "token not found" for every ground and took thirteen contrast assertions
    down with it. That failure looked like a palette regression and was not
    one - and worse, while it stood, the ratios were never measured at all.
    A readability test that cannot find the colours is not a passing test or a
    failing one; it is an absent one.
    """
    css = _css()
    seen: set[str] = set()
    current = name
    for _ in range(_MAX_INDIRECTION):
        if current in seen:
            raise AssertionError(f"token {name} resolves in a cycle at {current}")
        seen.add(current)
        match = re.search(
            rf"{re.escape(current)}:\s*([^;]+);",
            css,
        )
        if match is None:
            raise AssertionError(f"token {current} not found in {CSS_PATH.name}")
        value = match.group(1).strip()
        if value.startswith("#"):
            return value
        alias = re.fullmatch(r"var\(\s*(--[a-zA-Z0-9-]+)\s*\)", value)
        if alias is None:
            raise AssertionError(
                f"token {current} is {value!r}, which is neither a hex colour "
                "nor a plain var() alias this reader can follow"
            )
        current = alias.group(1)
    raise AssertionError(f"token {name} exceeded {_MAX_INDIRECTION} var() hops")


def _rgb(value: str) -> tuple[int, int, int]:
    raw = value.lstrip("#")
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _luminance(value: str) -> float:
    channels = []
    for component in _rgb(value):
        scaled = component / 255
        channels.append(
            scaled / 12.92 if scaled <= 0.03928 else ((scaled + 0.055) / 1.055) ** 2.4
        )
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(a: str, b: str) -> float:
    first, second = _luminance(a), _luminance(b)
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("ink", INK)
@pytest.mark.parametrize("ground", GROUNDS)
def test_every_ink_token_is_readable_on_every_ground(ink: str, ground: str) -> None:
    ratio = _contrast(_token(ink), _token(ground))
    assert ratio >= MINIMUM_RATIO, (
        f"{ink} on {ground} is {ratio:.2f}:1, below {MINIMUM_RATIO}"
    )


#: How far apart two adjacent ink levels must be, as a luminance ratio.
SEPARATION = 1.3


def test_the_four_levels_stay_distinguishable_from_each_other() -> None:
    """A repair that moved everything equally would pass and be useless.

    An early attempt did exactly that: it pushed `--nf-faint` until it cleared
    the contrast floor and left it a hair from `--nf-muted2`, so the hierarchy
    the levels exist to express disappeared instead.

    The direction is read from the palette rather than assumed. This scale was
    authored for dark ink on a light page, where each level is LIGHTER than the
    last; the product now paints light ink on a dark shell, where the same
    hierarchy runs the other way. Hard-coding "lighter" asserted the theme, not
    the property - and it broke on a legitimate redesign while the thing worth
    protecting, four steps you can actually tell apart, still held.
    """
    levels = [_luminance(_token(name)) for name in INK]
    descending = levels[-1] < levels[0]

    for index in range(1, len(levels)):
        previous, current = levels[index - 1], levels[index]
        if descending:
            assert current < previous, (
                f"{INK[index]} is not dimmer than {INK[index - 1]} on a dark "
                "shell, so the ink scale is not monotonic"
            )
            brighter, dimmer = previous, current
        else:
            assert current > previous, (
                f"{INK[index]} is not lighter than {INK[index - 1]} on a light "
                "page, so the ink scale is not monotonic"
            )
            brighter, dimmer = current, previous

        assert brighter > dimmer * SEPARATION, (
            f"{INK[index]} and {INK[index - 1]} are too close to tell apart"
        )


def test_the_token_reader_actually_finds_something() -> None:
    """Falsifies the whole file.

    Every assertion above is vacuous if `_token` silently returned a
    default - which is precisely what happened when the first version read
    the stylesheet through a bundler that stubbed it out.
    """
    assert len(_css()) > 1000
    assert _token("--nf-text").startswith("#")
    with pytest.raises(AssertionError):
        _token("--nf-not-a-real-token")
