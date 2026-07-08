"""
app/ui/theme.py -- Design tokens and formatting helpers.

Single source of truth for all colors and fonts.
No CTk imports -- this is pure data.
"""
from __future__ import annotations

# ---- Color palette (Modern Teal Dark) ----
BG_COLOR    = "#0f0f10"
SURFACE     = "#16161a"
SURFACE_L   = "#202026"
SURFACE_H   = "#2a2a33"
OUTLINE     = "#3f3f4c"
PRIMARY     = "#4891A1"
PRIMARY_HOV = "#3a7683"
ON_SURF     = "#e8e8ea"
ON_SURF_M   = "#8b8b99"
ERROR       = "#f87171"
SUCCESS     = "#4ade80"
WARNING     = "#fbbf24"

# ---- Typography ----
FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_BOLD   = ("Segoe UI", 11, "bold")
FONT_BODY   = ("Segoe UI", 11)
FONT_SMALL  = ("Segoe UI", 10)
FONT_LABEL  = ("Segoe UI", 10, "bold")
FONT_MONO   = ("Consolas", 9)
FONT_COUNT  = ("Segoe UI", 15, "bold")
FONT_NUM    = ("Segoe UI", 12, "bold")


# ---- Formatting helpers ----

def fmt(s: int) -> str:
    """Format seconds as HH:MM:SS."""
    s = max(0, s)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def fmt_short(s: int) -> str:
    """Format seconds as human-readable string, e.g. '2h 30m'."""
    s = max(0, s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if sec:
        parts.append(f"{sec}s")
    return " ".join(parts) if parts else "0s"
