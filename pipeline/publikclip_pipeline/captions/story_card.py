"""The story card (E20-F05): the title and the story's opening lines, on
screen while the narrator reads the title, as a channel card in the app's
OWN design.

What it is: an opaque WHITE rounded card with a soft shadow, in the middle
of the frame, laid out top to bottom the way a social post card is — a
header row (a large avatar circle, the user's channel name in bold beside
it), one text block in near-black in the caption preset's face — the story
title in bold, sentence case whatever the preset says, sized by its length,
and directly under it the story's opening text in the same face, flowing
down until the card's usable height runs out — and a bottom row where a
post card would put its engagement: a bare heart glyph on the left, a bare
share glyph beside it, and the story's DURATION on the right, which the
narrate stage measured from the audio it produced. Opaque and white on
purpose: the format this imitates works because the card sits on top of a
busy background and wins; the translucent dark panel this replaced read as
a murky slide over bright footage. It appears at 0 and leaves when the
narrator finishes the title — `title_end_sec` from the narrate
checkpoint, never a fixed number of seconds — and the one-word captions
start on the first body word.

The body is the hook. The format fills its card with text: a wall of
story the viewer starts reading before deciding whether to swipe, and a
card that is mostly empty white throws that away. So the block fills the
space between the header and the bottom row — the card does NOT grow to
fit the story, and its time on screen stays the narration's — and where
the story is longer than the space, it is cut at a WORD boundary and ends
with an ellipsis: never mid-word, never mid-character, never a line into
the bottom row. The text is the job's own story.txt, which the narrate
stage already hashes into its fingerprint, so an edited story reaches the
card through the cascade (§4 rule 2) and needs no key of its own here.
Knowing where the space runs out before ffmpeg draws anything is the
whole trick, and it is why the card breaks its own lines (`\\q2` plus
`\\N`, never libass's `\\q0`) with the face's real advance widths through
captions/font_metrics.py — an ASS font size is a line pitch there, not an
em, and that module says why. The body's ink is a shade lighter than the
title's and its weight is the preset's own: the bundled faces are one
weight each, so asking libass for a lighter one would give a machine with
that face installed a different card from a machine without it.

The avatar circle is the user's own avatar PNG (`story.avatar`, E20-F06):
a picture of its own, imported through the watermark's import helper into
its own folder and hashed into the render fingerprint on its own — NOT the
watermark, which E20-F05 reused for a few days and which is a mark in a
corner, not a round logo. The picture itself is overlaid by ffmpeg
(render/story.py:avatar_vf — an ASS document cannot carry an image)
centre-cropped to a square behind a circular mask. No avatar, or one that
is missing, degrades to the channel's initial on the preset's accent
colour (§5.9): never a crash, never an empty circle, and never the
watermark. No channel name and no picture, and the header row is simply
absent.

What it is NOT, and this is a product constraint rather than a style
preference: it carries no other platform's logo or wordmark, no invented
username, no verified badge, no award icons, and no vote, share, comment
or view counts. The line the bottom row walks: a bare glyph is decoration
and claims nothing; a glyph with a number beside it — "99+", "1.2k", a
digit — claims how people responded, and a verified badge claims a
platform vouched for this account. Both would be false on a card the app
draws for its own user. A tool that draws another platform's post frame
with fabricated engagement is a fake-record generator. Every number on
this card is one the job computed; if the format ever seems to need
another, the answer is no — not as a setting, not as a lookalike glyph.

Like the ranking list (captions/ranking.py) and the burned title
(captions/title.py) it rides the caption document through `extra_styles`
/ `extra_events`, so the card costs no second subtitle pass and no
drawtext (which the resolved ffmpeg may lack — §5.7). The glyphs are ASS
drawings, not font glyphs: the bundled faces are not guaranteed to carry
a heart, and a drawing is the same on every machine.

Geometry, in PlayRes units (1080x1920):

    +---------------------------------+  0
    |   +-------------------------+   |  PANEL_Y
    |   |  (O)  Channel name      |   |  header: AVATAR_D circle, bold name beside it
    |   |                         |   |
    |   |  The title, wrapped     |   |  the block: title, bold, sized by length,
    |   |  over a few lines       |   |    lines broken here from the face's own widths;
    |   |  Then the story's own   |   |    TITLE_BODY_GAP under it the body at BODY_SIZE,
    |   |  opening lines, down    |   |    flowing to the bottom row's band and cut at a
    |   |  to where the space…    |   |    word with an ellipsis when the story is longer
    |   |  ♥  ➦             1:23  |   |  bottom row: bare glyphs, the narration's duration
    |   +-------------------------+   |  PANEL_Y + PANEL_H
    +---------------------------------+  1920
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import ass as ass_mod
from . import font_metrics

CARD_VERSION = 5      # bumped when the drawing changes, so cached renders re-run

PANEL_X = 90
PANEL_W = ass_mod.PLAY_RES_X - 2 * PANEL_X
PANEL_Y = 540
PANEL_H = 840
PANEL_RADIUS = 48
CARD_FILL = "&HFFFFFF&"     # BBGGRR: white, and opaque — the card must win over the video
INK = "&H1A1A1A&"           # near-black text
BODY_INK = "&H333333&"      # the body, a shade lighter than the title so the title leads
INK_SOFT = "&H666666&"      # the duration, quieter than the title
INITIAL_INK = "&HFFFFFF&"   # the initial, white on the accent circle
# The soft shadow that lifts the card off the video: the panel's own shape,
# black at 40 % under a blur, drawn a little lower on the layer beneath.
SHADOW_OFFSET = 14
SHADOW_BLUR = 18
SHADOW_ALPHA = "&H99&"      # ASS alpha: 00 opaque → 0x99 is 60 % transparent
INSET = 64                  # from the panel's edge to everything inside it
AVATAR_D = 160              # the avatar circle's diameter — the header is the identity
INITIAL_SIZE = 76           # the fallback initial inside it
NAME_SIZE = 56              # the channel name beside it, bold
NAME_GAP = 32               # between the circle and the name
HEADER_GAP = 40             # from the header's bottom to the title's top
# The title in the caption face, sized by its length so a long title still
# leaves body lines under it — and never smaller than the channel name
# beside the avatar: on the reference the title is the biggest text on the
# card. These are ASS sizes, i.e. line pitches (font_metrics says why): 84
# draws Inter at a 69 px em, about a phone's headline.
TITLE_SIZE_SHORT = 84   # up to SHORT_CHARS: two lines
TITLE_SIZE_MID = 70     # up to MID_CHARS: three
TITLE_SIZE_LONG = 58    # beyond: four for a hundred and ten characters, in every face
SHORT_CHARS = 36
MID_CHARS = 72
# The body under it: 54 draws Inter at a 45 px em, a phone's own body text
# size on a 1080-wide frame, and gives a two-line title four lines of story
# under a full header; the gap is about half a body line, as on a post.
BODY_SIZE = 54
TITLE_BODY_GAP = 24
META_H = 150            # the bottom row's band — the block never enters it
GLYPH = 44              # the heart's and the share glyph's height
GLYPH_GAP = 44          # between the two glyphs
META_SIZE = 40          # the duration
FADE_IN_MS = 160
FADE_OUT_MS = 220


@dataclass(frozen=True)
class Card:
    """What one story's card shows. `avatar` is the avatar PNG's path, ""
    for the initial fallback; `duration_sec` is the narration's length as
    narrate measured it, 0 for no bottom row; `body` is the story's text
    after its title, as story.txt holds it, "" for a title-only story."""

    title: str
    end_sec: float
    channel: str = ""
    duration_sec: float = 0.0
    avatar: str = ""
    body: str = ""

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


_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def paragraphs(body: str) -> list[str]:
    """The body as paragraphs for the block: a blank line separates them
    and each starts on a new line; a lone line break inside one is a
    space, so a story typed one sentence per line flows as prose."""
    return [" ".join(p.split()) for p in _PARAGRAPH_BREAK.split(body or "") if p.strip()]


def text_top(card: Card) -> int:
    """The block's first row: under the header when there is one, else at
    the panel's inset."""
    if card.has_header:
        _, ay, d = avatar_box()
        return ay + d + HEADER_GAP
    return PANEL_Y + INSET


def block_floor() -> int:
    """The row the block may reach and never cross: the bottom row's band."""
    return PANEL_Y + PANEL_H - META_H


@dataclass(frozen=True)
class Layout:
    """Where the text block lands: the title's size and its lines as the
    card breaks them, the body's lines under it, whether either was cut
    short, and the rows they occupy — what the events draw and what a
    test checks without rendering. `body_y` is 0 when there is no body."""

    title_size: int
    title_lines: tuple[str, ...]
    title_truncated: bool
    body_lines: tuple[str, ...]
    body_truncated: bool
    top: int
    body_y: int
    bottom: int
    floor: int


def layout(preset: ass_mod.Preset, card: Card) -> Layout:
    """Break the title and the body into the lines the card draws, with
    the preset face's real widths and libass's line pitch, inside the
    panel's insets and above the bottom row. The title takes what it
    needs (cut with an ellipsis only if it alone overflows the block);
    the body gets every whole line left under it and is cut at a word
    when the story is longer than that — no line ever starts below the
    floor, and a body with no whole line of room is simply absent."""
    metrics = font_metrics.for_preset(preset)
    width = PANEL_W - 2 * INSET
    top, floor = text_top(card), block_floor()
    size = title_size(card.title)
    title_pitch = metrics.pitch(size)
    room = max(0, floor - top)
    title_lines, title_cut = font_metrics.fit(
        metrics, size, [" ".join(str(card.title or "").split())], width, int(room // title_pitch),
    )
    bottom = int(round(top + len(title_lines) * title_pitch))
    body_lines: tuple[str, ...] = ()
    body_cut, body_y = False, 0
    paras = paragraphs(card.body)
    if paras and not title_cut:
        body_pitch = metrics.pitch(BODY_SIZE)
        start = int(round(top + len(title_lines) * title_pitch + (TITLE_BODY_GAP if title_lines else 0)))
        lines, body_cut = font_metrics.fit(
            metrics, BODY_SIZE, paras, width, int(max(0, floor - start) // body_pitch),
        )
        if lines:
            body_lines, body_y = tuple(lines), start
            bottom = int(round(start + len(lines) * body_pitch))
    return Layout(
        title_size=size, title_lines=tuple(title_lines), title_truncated=title_cut,
        body_lines=body_lines, body_truncated=body_cut,
        top=top, body_y=body_y, bottom=bottom, floor=floor,
    )


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


def _path(points: list[tuple[str, list[tuple[float, float]]]], x: int, y: int, s: float) -> str:
    """An ASS drawing from (command, points) pairs on a 32-unit grid,
    scaled to `s` px and placed at (x, y). Integers only: the drawing
    grammar allows decimals but a rounded grid renders the same everywhere."""
    out: list[str] = []
    for cmd, pts in points:
        out.append(cmd)
        for px, py in pts:
            out.append(f"{x + int(round(px * s / 32))} {y + int(round(py * s / 32))}")
    return " ".join(out)


def heart(x: int, y: int, s: int = GLYPH) -> str:
    """A filled heart in an s×s box at (x, y): two lobes of cubic arcs
    meeting at the bottom point. Solid, at the weight of the reference's
    icon, and carrying NOTHING beside it — see the module docstring."""
    return _path(
        [
            ("m", [(16, 29)]),
            ("b", [(16, 29), (2, 20), (2, 10)]),
            ("b", [(2, 5), (6, 2), (10, 2)]),
            ("b", [(13, 2), (15, 4), (16, 6)]),
            ("b", [(17, 4), (19, 2), (22, 2)]),
            ("b", [(26, 2), (30, 5), (30, 10)]),
            ("b", [(30, 20), (16, 29), (16, 29)]),
        ],
        x, y, s,
    )


def share(x: int, y: int, s: int = GLYPH) -> str:
    """A filled forward arrow in an s×s box at (x, y): an arrow head on
    the right with a curved tail sweeping down to the left — the share
    glyph a post card carries, solid, and likewise bare."""
    return _path(
        [
            ("m", [(18, 3)]),
            ("l", [(31, 14), (18, 25), (18, 19)]),
            ("b", [(11, 18), (5, 22), (1, 29)]),
            ("b", [(2, 19), (8, 10), (18, 9)]),
            ("l", [(18, 3)]),
        ],
        x, y, s,
    )


def overlay_styles(preset: ass_mod.Preset) -> str:
    """The card's styles in the caption preset's face, on the white card:
    near-black ink, no outline — the title (top-left, 7, its lines broken
    by `layout`), the body under it (7, a shade lighter), the channel name
    (bold, middle-left, 4), the duration (middle-right, 6), the initial
    (centred, 5, white on the accent circle), and a drawing style for the
    shapes — no font involved, everything set per event. The title and the
    body carry the preset's own weight: the bundled faces are one weight
    each (Inter Bold, two display blacks), so `-1` on a black face would
    only make libass fake a heavier one, and `0` on Inter would let a
    machine with Inter Regular installed draw a different card."""
    m = PANEL_X + INSET
    weight = -1 if preset.bold else 0

    def colours(tag_colour: str) -> str:
        # A \1c tag colour (&HBBGGRR&) as the style's four colour fields:
        # primary and secondary in that ink, outline and back black — with
        # the AA byte a style line needs and a tag does not.
        ink = "&H00" + tag_colour[2:-1]
        return f"{ink},{ink},&H00000000,&H00000000"

    return (
        f"Style: StoryTitle,{preset.font},{TITLE_SIZE_SHORT},{colours(INK)},{weight},0,0,0,100,100,0,0,1,0,0,7,{m},{m},0,1\n"
        f"Style: StoryBody,{preset.font},{BODY_SIZE},{colours(BODY_INK)},{weight},0,0,0,100,100,0,0,1,0,0,7,{m},{m},0,1\n"
        f"Style: StoryName,{preset.font},{NAME_SIZE},{colours(INK)},-1,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1\n"
        f"Style: StoryMeta,{preset.font},{META_SIZE},{colours(INK_SOFT)},0,0,0,0,100,100,0,0,1,0,0,6,0,0,0,1\n"
        f"Style: StoryInitial,{preset.font},{INITIAL_SIZE},{colours(INITIAL_INK)},-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n"
        "Style: StoryShape,Inter,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,"
        "100,100,0,0,1,0,0,7,0,0,0,1\n"
    )


def _dialogue(layer: int, start: str, end: str, style: str, name: str, body: str) -> str:
    """One event. `name` rides the ASS Name (actor) field, which renderers
    ignore: it says what the event IS — panel, heart, duration — so a test
    can find a part by what it is rather than by its position or its
    coordinates, and so a reader of the document can too."""
    return f"Dialogue: {layer},{start},{end},{style},{name},0,0,0,{body}\n"


def _lines(lines: tuple[str, ...]) -> str:
    """Lines as one ASS text: each escaped, joined by the hard break the
    events' `\\q2` honours — the card's breaks, never libass's."""
    return "\\N".join(ass_mod._esc(line) for line in lines)


def overlay_events(preset: ass_mod.Preset, card: Card) -> str:
    """The Dialogue lines, 0 → end_sec, on layers above the captions (which
    do not exist during the card anyway): the shadow, the card, the
    header, the title and the body under it, the bottom row. All share
    one fade, so the card moves as one thing — the picture avatar is the
    exception, overlaid by ffmpeg and switched off when the fade-out
    begins (render/story.py says why)."""
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, card.end_sec))
    fade = f"\\fad({FADE_IN_MS},{FADE_OUT_MS})"
    shape = "\\an7\\bord0\\shad0"
    panel = rounded_rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H, PANEL_RADIUS)
    lines = [
        _dialogue(
            2, start, end, "StoryShape", "shadow",
            f"{{{shape}\\pos(0,{SHADOW_OFFSET})\\1c&H000000&\\1a{SHADOW_ALPHA}\\blur{SHADOW_BLUR}{fade}\\p1}}"
            f"{panel}{{\\p0}}",
        ),
        _dialogue(
            3, start, end, "StoryShape", "panel",
            f"{{{shape}\\pos(0,0)\\1c{CARD_FILL}\\1a&H00&{fade}\\p1}}{panel}{{\\p0}}",
        ),
    ]
    left = PANEL_X + INSET
    right = PANEL_X + PANEL_W - INSET
    if card.has_header:
        ax, ay, d = avatar_box()
        cx, cy, r = ax + d // 2, ay + d // 2, d // 2
        initial = initial_of(card.channel)
        if not card.avatar and initial:
            # No picture: the initial on the accent colour. With a picture
            # nothing is drawn here — ffmpeg puts the image on these pixels.
            lines.append(_dialogue(
                4, start, end, "StoryShape", "avatar",
                f"{{{shape}\\pos(0,0)\\1c{_rgb(preset.active)}\\1a&H00&{fade}\\p1}}{circle(cx, cy, r)}{{\\p0}}",
            ))
            lines.append(_dialogue(
                5, start, end, "StoryInitial", "initial",
                f"{{\\an5\\pos({cx},{cy})\\bord0\\shad0{fade}}}{ass_mod._esc(initial)}",
            ))
        if card.channel:
            lines.append(_dialogue(
                5, start, end, "StoryName", "name",
                f"{{\\an4\\pos({ax + d + NAME_GAP},{cy})\\q2\\bord0\\shad0{fade}}}{ass_mod._esc(card.channel)}",
            ))
    # Sentence case, whatever the preset's `uppercase` says: the reference
    # reads like a post because it is written like one; caps reads like a
    # banner. The captions keep the preset's case — this is the card's.
    # The lines are the card's own (\q2 + \N): it must know where the title
    # ends to put the body directly under it, and where the body ends to
    # keep it out of the bottom row.
    block = layout(preset, card)
    lines.append(_dialogue(
        5, start, end, "StoryTitle", "title",
        f"{{\\an7\\pos({left},{block.top})\\q2\\bord0\\shad0\\fs{block.title_size}{fade}}}"
        f"{_lines(block.title_lines)}",
    ))
    if block.body_lines:
        lines.append(_dialogue(
            5, start, end, "StoryBody", "body",
            f"{{\\an7\\pos({left},{block.body_y})\\q2\\bord0\\shad0{fade}}}{_lines(block.body_lines)}",
        ))
    if card.duration_sec > 0:
        row_y = PANEL_Y + PANEL_H - META_H // 2
        glyph_y = row_y - GLYPH // 2
        # Two bare glyphs and one real number. Nothing may ever sit beside
        # a glyph: the drawing IS the whole event, and the row's only text
        # is the duration, right-aligned away from them.
        lines.append(_dialogue(
            4, start, end, "StoryShape", "heart",
            f"{{{shape}\\pos(0,0)\\1c{INK}\\1a&H00&{fade}\\p1}}{heart(left, glyph_y)}{{\\p0}}",
        ))
        lines.append(_dialogue(
            4, start, end, "StoryShape", "share",
            f"{{{shape}\\pos(0,0)\\1c{INK}\\1a&H00&{fade}\\p1}}{share(left + GLYPH + GLYPH_GAP, glyph_y)}{{\\p0}}",
        ))
        lines.append(_dialogue(
            5, start, end, "StoryMeta", "duration",
            f"{{\\an6\\pos({right},{row_y})\\bord0\\shad0{fade}}}{duration_label(card.duration_sec)}",
        ))
    return "".join(lines)


def overlay(preset: ass_mod.Preset, card: Card) -> tuple[str, str]:
    """(extra_styles, extra_events) for ass.build_ass — both empty when
    there is no title or no time to show it, so the document is then
    exactly a caption document."""
    if not card.title or card.end_sec <= 0:
        return "", ""
    return overlay_styles(preset), overlay_events(preset, card)
