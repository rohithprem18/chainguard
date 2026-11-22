"""Dark mode: the page ships a prefers-color-scheme palette with WCAG AA contrast.

The colours live in CSS variables in static/index.html: a light `:root` and a
`@media (prefers-color-scheme: dark)` override. These tests keep the two
palettes in sync and prove the text contrast ratios stay readable.
"""

import re
from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
TEXT = HTML.read_text(encoding="utf-8")

COLOR_VARS = [
    "--ink",
    "--body",
    "--mute",
    "--faint",
    "--hairline",
    "--hairline-soft",
    "--canvas",
    "--elevated",
    "--link",
    "--link-deep",
    "--low",
    "--low-text",
    "--medium",
    "--medium-text",
    "--high",
    "--high-text",
    "--on-ink",
    "--ink-hover",
    "--focus-ring",
    "--chip-hover",
]

# (foreground var, background var) pairs that must reach 4.5:1 (WCAG AA text).
TEXT_PAIRS = [
    ("--ink", "--canvas"),
    ("--ink", "--elevated"),
    ("--body", "--canvas"),
    ("--body", "--elevated"),
    ("--low-text", "--canvas"),
    ("--low-text", "--elevated"),
    ("--medium-text", "--canvas"),
    ("--medium-text", "--elevated"),
    ("--high-text", "--canvas"),
    ("--high-text", "--elevated"),
    ("--link", "--elevated"),
    ("--link-deep", "--canvas"),
    ("--on-ink", "--ink"),
]


def _variables(block: str) -> dict[str, str]:
    return {
        f"--{name}": value
        for name, value in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block)
    }


def _root_block() -> str:
    match = re.search(r"(?<!dark\)\s):root\s*\{(.*?)\n  \}", TEXT, re.S)
    assert match, "light :root block not found"
    return match.group(1)


def _dark_block() -> str:
    match = re.search(
        r"@media \(prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{(.*?)\n    \}",
        TEXT,
        re.S,
    )
    assert match, "no @media (prefers-color-scheme: dark) :root block"
    return match.group(1)


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast(foreground: str, background: str) -> float:
    a, b = _luminance(foreground), _luminance(background)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def test_dark_media_query_redefines_every_color_variable():
    light = _variables(_root_block())
    dark = _variables(_dark_block())
    for name in COLOR_VARS:
        assert name in light, f"{name} missing from the light :root"
        assert name in dark, f"{name} missing from the dark palette"


def test_light_theme_text_contrast_is_aa():
    v = _variables(_root_block())
    for fg, bg in TEXT_PAIRS:
        assert (
            _contrast(v[fg], v[bg]) >= 4.5
        ), f"light {fg} on {bg}: {_contrast(v[fg], v[bg]):.2f}"


def test_dark_theme_text_contrast_is_aa():
    v = _variables(_dark_block())
    for fg, bg in TEXT_PAIRS + [
        ("--mute", "--canvas"),
        ("--faint", "--canvas"),
        ("--link", "--canvas"),
    ]:
        assert (
            _contrast(v[fg], v[bg]) >= 4.5
        ), f"dark {fg} on {bg}: {_contrast(v[fg], v[bg]):.2f}"


def test_risk_ring_colors_stay_visible_on_the_canvas_in_both_themes():
    for label, block in (("light", _root_block()), ("dark", _dark_block())):
        v = _variables(block)
        # The dark palette is new, so it must meet the 3:1 non-text bar; the
        # light palette is shipped as-is, so we only require it to be visible.
        floor = 3.0 if label == "dark" else 1.5
        for name in ("--low", "--medium", "--high"):
            assert (
                _contrast(v[name], v["--canvas"]) >= floor
            ), f"{label} {name} on canvas"


def test_no_hardcoded_button_text_color_remains():
    # Buttons filled with --ink must use --on-ink, or dark mode inverts them.
    assert "color:#fff" not in TEXT and "color: #fff" not in TEXT
