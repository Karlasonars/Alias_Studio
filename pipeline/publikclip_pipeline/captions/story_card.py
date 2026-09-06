"""The story card (E20-F05): the title, on screen while the narrator reads
it, in the app's OWN design.

What it is: a translucent dark panel in the middle third of the frame, a
thin accent rule across its top in the caption preset's active colour,
and the title centred inside it in the preset's face. It appears at 0
and leaves when the narrator finishes the title — that boundary is
`title_end_sec` from the narrate checkpoint, measured from the audio the
stage produced, never a fixed number of seconds — and the one-word
captions start on the first body word, after it.

What it is NOT, and this is a product constraint rather than a style
preference: it carries no other platform's chrome, no logo, no avatar, no
username, and no vote, share or comment counts. A tool that draws another
platform's post frame with invented engagement numbers is a fake-record
generator. If the format ever seems to need those, the answer is no.

Like the ranking list (captions/ranking.py) and the burned title
(captions/title.py) it rides the caption document through `extra_styles`
/ `extra_events`, so the card costs no second subtitle pass and no
drawtext (which the resolved ffmpeg may lack — §5.7).

Geometry, in PlayRes units (1080x1920):

    +---------------------------------+  0
    |                                 |
    |   +-------------------------+   |  PANEL_Y
    |   |=== accent rule ========|   |
    |   |                         |   |
    |   |     THE TITLE, WRAPPED  |   |  centre (540, 960)
    |   |                         |   |
    |   +-------------------------+   |  PANEL_Y + PANEL_H
    |                                 |
    +---------------------------------+  1920
"""

from __future__ import annotations

from . import ass as ass_mod

CARD_VERSION = 1      # bumped when the drawing changes, so cached renders re-run

PANEL_X = 90
PANEL_W = ass_mod.PLAY_RES_X - 2 * PANEL_X
PANEL_Y = 660
PANEL_H = 600
PANEL_RADIUS = 36
PANEL_ALPHA = "&H33&"   # ASS alpha: 00 opaque → 0x33 is 80 % opaque black
ACCENT_H = 8
TEXT_INSET = 60        # from the panel's edge to where the title may wrap
# The title in the caption face, sized by its length so an eighty-character
# title still fits three or four lines inside the panel.
TITLE_SIZE_SHORT = 76   # up to SHORT_CHARS
TITLE_SIZE_MID = 62     # up to MID_CHARS
TITLE_SIZE_LONG = 50    # beyond
SHORT_CHARS = 36
MID_CHARS = 72
FADE_IN_MS = 160
FADE_OUT_MS = 220


def title_size(title: str) -> int:
    n = len(title or "")
    if n <= SHORT_CHARS:
        return TITLE_SIZE_SHORT
    if n <= MID_CHARS:
        return TITLE_SIZE_MID
    return TITLE_SIZE_LONG


def _rgb(ass_color: str) -> str:
    """The BBGGRR part of an &HAABBGGRR preset colour, for a \\1c tag."""
    hex6 = (ass_color or "&H00FFFFFF").replace("&H", "").replace("&", "")[-6:]
    return f"&H{hex6}&"


def rounded_rect(x: int, y: int, w: int, h: int, r: int) -> str:
    """An ASS drawing (\\p1 commands) for a rectangle with rounded corners:
    straight edges with `l`, each corner a cubic `b` whose control points
    sit on the corner — a close-enough quarter circle for a UI panel."""
    r = max(0, min(r, w // 2, h // 2))
    x2, y2 = x + w, y + h
    return (
        f"m {x + r} {y} l {x2 - r} {y} b {x2} {y} {x2} {y} {x2} {y + r} "
        f"l {x2} {y2 - r} b {x2} {y2} {x2} {y2} {x2 - r} {y2} "
        f"l {x + r} {y2} b {x} {y2} {x} {y2} {x} {y2 - r} "
        f"l {x} {y + r} b {x} {y} {x} {y} {x + r} {y}"
    )


def overlay_styles(preset: ass_mod.Preset) -> str:
    """Two styles: the title (centre-aligned, 5, so one \\pos places it and
    libass wraps it between the margins) and a drawing style for the panel
    and the rule — no font involved, everything set per event."""
    bold = -1 if preset.bold else 0
    m = PANEL_X + TEXT_INSET
    return (
        f"Style: StoryTitle,{preset.font},{TITLE_SIZE_SHORT},{preset.primary},{preset.primary},"
        f"{preset.outline_color},&H00000000,{bold},0,0,0,100,100,0,0,1,3,0,5,{m},{m},0,1\n"
        "Style: StoryShape,Inter,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,"
        "100,100,0,0,1,0,0,7,0,0,0,1\n"
    )


def overlay_events(preset: ass_mod.Preset, title: str, end_sec: float) -> str:
    """Three Dialogue lines, 0 → end_sec, on layers above the captions (which
    do not exist during the card anyway): the panel, the accent rule, the
    title. All three share one fade, so the card moves as one thing."""
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, end_sec))
    fade = f"\\fad({FADE_IN_MS},{FADE_OUT_MS})"
    panel = rounded_rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H, PANEL_RADIUS)
    rule = rounded_rect(PANEL_X + PANEL_RADIUS, PANEL_Y, PANEL_W - 2 * PANEL_RADIUS, ACCENT_H, 0)
    shown = ass_mod._esc(title.upper() if preset.uppercase else title)
    return (
        f"Dialogue: 3,{start},{end},StoryShape,,0,0,0,"
        f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c&H000000&\\1a{PANEL_ALPHA}{fade}\\p1}}{panel}{{\\p0}}\n"
        f"Dialogue: 4,{start},{end},StoryShape,,0,0,0,"
        f"{{\\an7\\pos(0,0)\\bord0\\shad0\\1c{_rgb(preset.active)}\\1a&H00&{fade}\\p1}}{rule}{{\\p0}}\n"
        f"Dialogue: 5,{start},{end},StoryTitle,,0,0,0,"
        f"{{\\an5\\pos({ass_mod.PLAY_RES_X // 2},{PANEL_Y + PANEL_H // 2})\\q0"
        f"\\fs{title_size(title)}{fade}}}{shown}\n"
    )


def overlay(preset: ass_mod.Preset, title: str, end_sec: float) -> tuple[str, str]:
    """(extra_styles, extra_events) for ass.build_ass — both empty when
    there is no title or no time to show it, so the document is then
    exactly a caption document."""
    if not title or end_sec <= 0:
        return "", ""
    return overlay_styles(preset), overlay_events(preset, title, end_sec)
