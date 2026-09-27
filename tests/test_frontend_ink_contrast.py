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


def _token(name: str) -> str:
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{3,8}})\s*;", _css())
    if match is None:
        raise AssertionError(f"token {name} not found in {CSS_PATH.name}")
    return match.group(1)


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


def test_the_four_levels_stay_distinguishable_from_each_other() -> None:
    """A repair that darkened everything equally would pass and be useless.

    The first attempt at the fix did exactly that: it pushed `--nf-faint`
    until it cleared the floor and left it a hair from `--nf-muted2`, so the
    hierarchy the levels exist to express disappeared instead.
    """
    levels = [_luminance(_token(name)) for name in INK]
    for index in range(1, len(levels)):
        assert levels[index] > levels[index - 1], (
            f"{INK[index]} is not lighter than {INK[index - 1]}"
        )
        assert levels[index] > levels[index - 1] * 1.3, (
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
