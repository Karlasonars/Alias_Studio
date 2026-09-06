"""The story card (E20-F05): the title, on screen while the narrator reads
it, as a channel card in the app's OWN design.

What it is: an opaque WHITE rounded card with a soft shadow, in the middle
of the frame, laid out top to bottom the way a social post card is — a
header row (a large avatar circle, the user's channel name in bold beside
it), the story title in near-black in the caption preset's face, sentence
case whatever the preset says, sized by its length, and a bottom row where
a post card would put its engagement: a bare heart glyph on the left, a
bare share glyph beside it, and the story's DURATION on the right, which
the narrate stage measured from the audio it produced. Opaque and white on
purpose: the format this imitates works because the card sits on top of a
busy background and wins; the translucent dark panel this replaced read as
a murky slide over bright footage. It appears at 0 and leaves when the
narrator finishes the title — `title_end_sec` from the narrate
checkpoint, never a fixed number of seconds — and the one-word captions
start on the first body word.

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
    |   |  The title, wrapped     |   |  title, left-aligned, sentence case, sized by length
    |   |  over a few lines       |   |
    |   |                         |   |
    |   |  ♥  ➦             1:23  |   |  bottom row: bare glyphs, the narration's duration
    |   +-------------------------+   |  PANEL_Y + PANEL_H
    +---------------------------------+  1920
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ass as ass_mod

CARD_VERSION = 4      # bumped when the drawing changes, so cached renders re-run

PANEL_X = 90
PANEL_W = ass_mod.PLAY_RES_X - 2 * PANEL_X
PANEL_Y = 540
PANEL_H = 840
PANEL_RADIUS = 48
CARD_FILL = "&HFFFFFF&"     # BBGGRR: white, and opaque — the card must win over the video
INK = "&H1A1A1A&"           # near-black text
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
# The title in the caption face, sized by its length so an eighty-character
# title still fits three or four lines above the bottom row.
TITLE_SIZE_SHORT = 76   # up to SHORT_CHARS
TITLE_SIZE_MID = 62     # up to MID_CHARS
TITLE_SIZE_LONG = 50    # beyond
SHORT_CHARS = 36
MID_CHARS = 72
META_H = 150            # the bottom row's band
GLYPH = 44              # the heart's and the share glyph's height
GLYPH_GAP = 44          # between the two glyphs
META_SIZE = 40          # the duration
FADE_IN_MS = 160
FADE_OUT_MS = 220


@dataclass(frozen=True)
class Card:
    """What one story's card shows. `avatar` is the avatar PNG's path, ""
    for the initial fallback; `duration_sec` is the narration's length as
    narrate measured it, 0 for no bottom row."""

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
    near-black ink, no outline — the title (top-left, 7, wrapped by libass
    between the panel's margins), the channel name (bold, middle-left, 4),
    the duration (middle-right, 6), the initial (centred, 5, white on the
    accent circle), and a drawing style for the shapes — no font involved,
    everything set per event."""
    m = PANEL_X + INSET

    def colours(tag_colour: str) -> str:
        # A \1c tag colour (&HBBGGRR&) as the style's four colour fields:
        # primary and secondary in that ink, outline and back black — with
        # the AA byte a style line needs and a tag does not.
        ink = "&H00" + tag_colour[2:-1]
        return f"{ink},{ink},&H00000000,&H00000000"

    return (
        f"Style: StoryTitle,{preset.font},{TITLE_SIZE_SHORT},{colours(INK)},0,0,0,0,100,100,0,0,1,0,0,7,{m},{m},0,1\n"
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


def overlay_events(preset: ass_mod.Preset, card: Card) -> str:
    """The Dialogue lines, 0 → end_sec, on layers above the captions (which
    do not exist during the card anyway): the shadow, the card, the
    header, the title, the bottom row. All share one fade, so the card
    moves as one thing — the picture avatar is the exception, overlaid by
    ffmpeg and switched off when the fade-out begins (render/story.py says
    why)."""
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
    title_y = PANEL_Y + INSET
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
        title_y = ay + d + HEADER_GAP
    # Sentence case, whatever the preset's `uppercase` says: the reference
    # reads like a post because it is written like one; caps reads like a
    # banner. The captions keep the preset's case — this is the card's.
    lines.append(_dialogue(
        5, start, end, "StoryTitle", "title",
        f"{{\\an7\\pos({left},{title_y})\\q0\\bord0\\shad0\\fs{title_size(card.title)}{fade}}}"
        f"{ass_mod._esc(card.title)}",
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
