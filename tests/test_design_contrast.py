"""Text contrast of the dashboard's colour tokens (docs/DESIGN.md): every text colour on every surface it sits on
is at least 4.5:1 (WCAG AA for normal text), in the light theme and in the dark theme."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "dashboard" / "style.css").read_text()

# (text token, background token): every pair the page actually draws
PAIRS = [
    ("ink", "bg"), ("ink", "surface"), ("ink", "thread"), ("ink", "accent-soft"),
    ("muted", "bg"), ("muted", "surface"), ("muted", "thread"),
    ("accent", "surface"), ("accent", "bg"), ("accent", "accent-soft"), ("on-accent", "accent"),
    ("applied", "surface"), ("applied", "applied-soft"),
    ("soon", "surface"), ("soon", "soon-soft"),
    ("test", "surface"), ("test", "test-soft"),
    ("danger", "surface"), ("danger", "danger-soft"),
    # chat bubbles: Ping's (left) and yours (right)
    ("ink", "bubble-ping"), ("muted", "bubble-ping"), ("accent", "bubble-ping"), ("soon", "bubble-ping"),
    ("test", "bubble-ping"), ("danger", "bubble-ping"), ("applied", "bubble-ping"),
    ("ink", "bubble-me"), ("muted", "bubble-me"), ("accent", "bubble-me"),
]


def _tokens(block: str) -> dict:
    return {k: v.lower() for k, v in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block)}


def themes() -> dict:
    light = _tokens(re.search(r":root\s*\{(.*?)\}", CSS, re.S).group(1))
    dark = _tokens(re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', CSS, re.S).group(1))
    system_dark = _tokens(re.search(r':root:not\(\[data-theme="light"\]\)\s*\{(.*?)\}', CSS, re.S).group(1))
    return {"light": light, "dark": dark, "system dark": system_dark}


def luminance(hex_: str) -> float:
    def ch(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(hex_[i:i + 2]) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_every_text_pair_meets_4_5_to_1():
    bad = []
    for name, t in themes().items():
        for fg, bg in PAIRS:
            assert fg in t and bg in t, f"{name}: token --{fg} or --{bg} missing"
            r = ratio(t[fg], t[bg])
            if r < 4.5:
                bad.append(f"{name}: --{fg} {t[fg]} on --{bg} {t[bg]} = {r:.2f}")
    assert not bad, "\n".join(bad)


def test_dark_follows_the_system_and_the_toggle_the_same_way():
    t = themes()
    assert t["dark"] == t["system dark"]
