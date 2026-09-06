"""The story card (E20-F05): the title, on screen while the narrator reads
it, as a channel card in the app's OWN design.

What it is: a rounded dark card in the middle of the frame, laid out top
to bottom the way a social post card is — a header row (an avatar circle,
the user's channel name beside it), the story title in the caption
preset's face sized by its length, and a meta row where a post card would
put its engagement. That row carries the story's DURATION, which the
narrate stage measured from the audio it produced: a real number the job
computed, placed exactly so the layout tempts nobody to fill it with an
invented one. It appears at 0 and leaves when the narrator finishes the
title — `title_end_sec` from the narrate checkpoint, never a fixed number
of seconds — and the one-word captions start on the first body word.

The avatar circle is the user's watermark PNG (E19-F02): the same file
the watermark import stored, resolved through render/watermark.py so the
card and the mark can never disagree about which file it is, and hashed
into the render fingerprint once, as the watermark. The picture itself is
overlaid by ffmpeg (render/story.py:avatar_vf — an ASS document cannot
carry an image) centre-cropped to a square behind a circular mask. No PNG
configured, or one that is missing, degrades to the channel's initial on
the preset's accent colour (§5.9): never a crash, never an empty circle.
No channel name and no picture, and the header row is simply absent.

What it is NOT, and this is a product constraint rather than a style
preference: it carries no other platform's logo or wordmark, no invented
username, and no vote, share, comment or view counts. A tool that draws
another platform's post frame with fabricated engagement numbers is a
fake-record generator. Every number on this card is one the job computed;
if the format ever seems to need another, the answer is no.

Like the ranking list (captions/ranking.py) and the burned title
(captions/title.py) it rides the caption document through `extra_styles`
/ `extra_events`, so the card costs no second subtitle pass and no
drawtext (which the resolved ffmpeg may lack — §5.7).

Geometry, in PlayRes units (1080x1920):

    +---------------------------------+  0
    |   +-------------------------+   |  PANEL_Y
    |   |  (o) channel name       |   |  header: AVATAR_D circle, name beside it
    |   |                         |   |
    |   |  The title, wrapped     |   |  title, left-aligned, sized by length
    |   |  over a few lines       |   |
    |   |  ---------------------  |   |  divider
    |   |  1:23                   |   |  meta row: the narration's duration
    |   +-------------------------+   |  PANEL_Y + PANEL_H
    +---------------------------------+  1920
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ass as ass_mod

CARD_VERSION = 2      # bumped when the drawing changes, so cached renders re-run

PANEL_X = 90
PANEL_W = ass_mod.PLAY_RES_X - 2 * PANEL_X
PANEL_Y = 560
PANEL_H = 800
PANEL_RADIUS = 40
PANEL_ALPHA = "&H26&"   # ASS alpha: 00 opaque → 0x26 is 85 % opaque black
INSET = 60             # from the panel's edge to everything inside it
AVATAR_D = 120         # the avatar circle's diameter
INITIAL_SIZE = 60      # the fallback initial inside it
NAME_SIZE = 44         # the channel name beside it
HEADER_GAP = 44        # from the header's bottom to the title's top
# The title in the caption face, sized by its length so an eighty-character
# title still fits three or four lines above the meta row.
TITLE_SIZE_SHORT = 76   # up to SHORT_CHARS
TITLE_SIZE_MID = 62     # up to MID_CHARS
TITLE_SIZE_LONG = 50    # beyond
SHORT_CHARS = 36
MID_CHARS = 72
META_H = 140           # the meta row's band at the bottom of the panel
DIVIDER_H = 2
META_SIZE = 40
DIM_ALPHA = "&H66&"    # 60 % opaque: the divider and the duration read as secondary
FADE_IN_MS = 160
FADE_OUT_MS = 220


@dataclass(frozen=True)
class Card:
    """What one story's card shows. `avatar` is the watermark PNG's path,
    "" for the initial fallback; `duration_sec` is the narration's length
    as narrate measured it, 0 for no meta row."""

    title: str
    end_sec: float
    channel: str = ""
    duration_sec: float = 0.0
    avatar: str = ""

    @property
    def has_header(self) -> bool:
        return bool(self.channel or self.avatar)


def title_size(title: str) -> int:
    n = len(title or "")
    if n <= SHORT_CHARS:
        return TITLE_SIZE_SHORT
    if n <= MID_CHARS:
        return TITLE_SIZE_MID
    return TITLE_SIZE_LONG


def duration_label(seconds: float) -> str:
    """m:ss, the way a player shows a length — the one number on the card."""
    whole = max(0, int(round(float(seconds or 0.0))))
    return f"{whole // 60}:{whole % 60:02d}"


def initial_of(channel: str) -> str:
    """The first letter or digit of the channel name, upper-cased — what
    fills the avatar circle when there is no picture. "" when the name has
    none, and then the circle is not drawn at all rather than drawn empty."""
    for ch in str(channel or ""):
        if ch.isalnum():
            return ch.upper()
    return ""


def avatar_box() -> tuple[int, int, int]:
    """(x, y, diameter) of the avatar circle, top-left corner — the one
    place its geometry lives, read by the ASS fallback here and by the
    ffmpeg overlay in render/story.py so the two land on the same pixels."""
    return PANEL_X + INSET, PANEL_Y + INSET, AVATAR_D


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


def circle(cx: int, cy: int, r: int) -> str:
    """An ASS drawing for a circle: four cubic quarter arcs with the usual
    0.5523 control-point factor — a real circle to the eye, unlike the
    corner-pinned curves rounded_rect uses, which would read as a squircle
    at this size."""
    k = int(round(0.5523 * r))
    return (
        f"m {cx + r} {cy} "
        f"b {cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r} "
        f"b {cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy} "
        f"b {cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r} "
        f"b {cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy}"
    )


def overlay_styles(preset: ass_mod.Preset) -> str:
    """The card's styles in the caption preset's face: the title (top-left,
    7, wrapped by libass between the panel's margins), the channel name and
    the duration (middle-left, 4), the initial (centred, 5), and a drawing
    style for the shapes — no font involved, everything set per event."""
    bold = -1 if preset.bold else 0
    m = PANEL_X + INSET
    text = f"{preset.primary},{preset.primary},{preset.outline_color},&H00000000"
    return (
        f"Style: StoryTitle,{preset.font},{TITLE_SIZE_SHORT},{text},{bold},0,0,0,100,100,0,0,1,3,0,7,{m},{m},0,1\n"
        f"Style: StoryName,{preset.font},{NAME_SIZE},{text},{bold},0,0,0,100,100,0,0,1,0,0,4,0,0,0,1\n"
        f"Style: StoryMeta,{preset.font},{META_SIZE},{text},0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1\n"
        f"Style: StoryInitial,{preset.font},{INITIAL_SIZE},{text},-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n"
        "Style: StoryShape,Inter,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,"
        "100,100,0,0,1,0,0,7,0,0,0,1\n"
    )


def overlay_events(preset: ass_mod.Preset, card: Card) -> str:
    """The Dialogue lines, 0 → end_sec, on layers above the captions (which
    do not exist during the card anyway): the panel, the header, the title,
    the meta row. All share one fade, so the card moves as one thing — the
    picture avatar is the exception, overlaid by ffmpeg and switched off
    when the fade-out begins (render/story.py says why)."""
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, card.end_sec))
    fade = f"\\fad({FADE_IN_MS},{FADE_OUT_MS})"
    shape = "\\an7\\pos(0,0)\\bord0\\shad0"
    lines = [
        f"Dialogue: 3,{start},{end},StoryShape,,0,0,0,"
        f"{{{shape}\\1c&H000000&\\1a{PANEL_ALPHA}{fade}\\p1}}"
        f"{rounded_rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H, PANEL_RADIUS)}{{\\p0}}\n"
    ]
    left = PANEL_X + INSET
    title_y = PANEL_Y + INSET
    if card.has_header:
        ax, ay, d = avatar_box()
        cx, cy, r = ax + d // 2, ay + d // 2, d // 2
        initial = initial_of(card.channel)
        if not card.avatar and initial:
            # No picture: the initial on the accent colour. With a picture
            # nothing is drawn here — ffmpeg puts the image on these pixels.
            lines.append(
                f"Dialogue: 4,{start},{end},StoryShape,,0,0,0,"
                f"{{{shape}\\1c{_rgb(preset.active)}\\1a&H00&{fade}\\p1}}{circle(cx, cy, r)}{{\\p0}}\n"
            )
            lines.append(
                f"Dialogue: 5,{start},{end},StoryInitial,,0,0,0,"
                f"{{\\an5\\pos({cx},{cy}){fade}}}{ass_mod._esc(initial)}\n"
            )
        if card.channel:
            lines.append(
                f"Dialogue: 5,{start},{end},StoryName,,0,0,0,"
                f"{{\\an4\\pos({ax + d + 28},{cy})\\q2{fade}}}{ass_mod._esc(card.channel)}\n"
            )
        title_y = ay + d + HEADER_GAP
    shown = ass_mod._esc(card.title.upper() if preset.uppercase else card.title)
    lines.append(
        f"Dialogue: 5,{start},{end},StoryTitle,,0,0,0,"
        f"{{\\an7\\pos({left},{title_y})\\q0\\fs{title_size(card.title)}{fade}}}{shown}\n"
    )
    if card.duration_sec > 0:
        meta_top = PANEL_Y + PANEL_H - META_H
        lines.append(
            f"Dialogue: 4,{start},{end},StoryShape,,0,0,0,"
            f"{{{shape}\\1c{_rgb(preset.primary)}\\1a{DIM_ALPHA}{fade}\\p1}}"
            f"{rounded_rect(left, meta_top, PANEL_W - 2 * INSET, DIVIDER_H, 0)}{{\\p0}}\n"
        )
        lines.append(
            f"Dialogue: 5,{start},{end},StoryMeta,,0,0,0,"
            f"{{\\an4\\pos({left},{meta_top + META_H // 2})\\alpha{DIM_ALPHA}{fade}}}"
            f"{duration_label(card.duration_sec)}\n"
        )
    return "".join(lines)


def overlay(preset: ass_mod.Preset, card: Card) -> tuple[str, str]:
    """(extra_styles, extra_events) for ass.build_ass — both empty when
    there is no title or no time to show it, so the document is then
    exactly a caption document."""
    if not card.title or card.end_sec <= 0:
        return "", ""
    return overlay_styles(preset), overlay_events(preset, card)
