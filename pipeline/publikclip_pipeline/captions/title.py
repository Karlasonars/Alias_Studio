"""The burned title (E19-F01): the title variant the user marked in the
editor, burned into the clip for its whole length.

Two owner decisions shape it. The text is the variant the user picks IN
THE EDITOR — no automatic choice, and a clip with nothing marked renders
without one: the user sees what will be written before it happens. And it
stays for the WHOLE clip, not the opening seconds: a title that vanishes
after three seconds is a hook card, and this is not that.

It is a style, not a structure: the render stage reproduces it from the
clip's edit exactly as it reproduces `caption_preset`, so a job-level
restyle keeps it (E19-F01's last criterion) instead of adopting the
editor's file. Both render paths — the stage's clip loop and the editor's
single-clip render — build the two ASS lines through `overlay` below and
splice them into the same caption document (§5.8: one resolution, not two
copies). Ranking videos never carry it; they have their own title.

Geometry, in PlayRes units: top-centre (alignment 8) with the top safe
zone (captions/ass.py:TOP_SAFE_PX) as its margin, so it clears the
platform's top bar exactly as the ranking list does, inside the SIDE_MARGIN
the captions use, and it wraps (\\q0 — the document's WrapStyle is 2, no
wrapping, which is right for four-word captions and wrong for an
eighty-character title). Captions sit `margin_v` from the bottom; nothing
here reaches them.
"""

from __future__ import annotations

import re

from . import ass as ass_mod

# The title in the caption face at a fraction of the caption size, clamped:
# a title is read once and can be smaller than a caption, but below TITLE_MIN
# it stops being legible at phone size, and above TITLE_MAX three lines of an
# eighty-character title reach the middle of the frame.
TITLE_SCALE = 0.8
TITLE_MIN = 40
TITLE_MAX = 64

_WS = re.compile(r"\s+")


def burned_title(edit) -> str:
    """The text one clip burns, or "" for none. Reads a raw edit dict (the
    stage, which never imports the editing package) or a ClipEdit (the
    editor's path) — the one place the field is interpreted, so the two
    paths cannot disagree about what "nothing marked" means (whitespace is
    nothing)."""
    if isinstance(edit, dict):
        raw = edit.get("burned_title")
    else:
        raw = getattr(edit, "burned_title", "")
    return _WS.sub(" ", str(raw or "")).strip()


def title_size(preset: ass_mod.Preset) -> int:
    return max(TITLE_MIN, min(TITLE_MAX, int(round(preset.size * TITLE_SCALE))))


def overlay_styles(preset: ass_mod.Preset) -> str:
    """The [V4+ Styles] line: the caption preset's face, colours, outline and
    shadow, so the title matches the captions' brand; top-centre aligned
    with TOP_SAFE_PX as its distance from the top."""
    bold = -1 if preset.bold else 0
    m = ass_mod.SIDE_MARGIN
    return (
        f"Style: BurnTitle,{preset.font},{title_size(preset)},{preset.primary},{preset.primary},"
        f"{preset.outline_color},&H96000000,{bold},0,0,0,100,100,0,0,1,"
        f"{preset.outline},{preset.shadow},8,{m},{m},{ass_mod.TOP_SAFE_PX},1\n"
    )


def overlay_events(preset: ass_mod.Preset, text: str, duration: float) -> str:
    """One Dialogue line spanning the whole clip. Layer 2, above the captions
    and tags, though the two never share a pixel."""
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, duration))
    shown = ass_mod._esc(text.upper() if preset.uppercase else text)
    return f"Dialogue: 2,{start},{end},BurnTitle,,0,0,0,{{\\q0}}{shown}\n"


def overlay(preset: ass_mod.Preset, text: str, duration: float) -> tuple[str, str]:
    """(extra_styles, extra_events) for ass.build_ass — both empty when there
    is nothing to burn, so an unmarked clip's document is byte-identical to
    what it was before this module existed."""
    if not text:
        return "", ""
    return overlay_styles(preset), overlay_events(preset, text, duration)
