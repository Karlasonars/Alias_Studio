"""The ranking list overlay (E18-F03): a title and a numbered list 1..N that
lives at the top of the frame for the whole montage and fills in as the
viewer watches.

Why it is ASS and not a second filter pass: during one segment the list is
STATIC — the entries already played, the one playing now, the ones still to
come — so it can ride that segment's own caption document through the one
subtitles burn the segment gets anyway. The montage is then a remux of the
segments (render/renderer.py:concat_copy), and the overlay costs no second
encode. The reveal in play order is what makes the format work (D-17): the
list starts as numbers only and a pre-filled list kills the hook.

Geometry, in PlayRes units (1080x1920, one unit per output pixel):

    +---------------------------------+  0
    |          top safe zone          |  TOP_SAFE_PX (captions/ass.py)
    |  TOP 5                          |  band.top          } TITLE_LINE
    |  1                              |                    }
    |  2                              |                    } N x band.line_h
    |  ...                            |                    }
    +---------------------------------+  band.bottom
    |            picture              |  letterbox bar ends at pad_y
    |            ...                  |
    |          [captions]             |  preset.margin_v from the bottom
    +---------------------------------+  1920

The band is sized from the letterbox bar the framing dial leaves at the top
(render.renderer.letterbox_geometry): at gameplay framing a 16:9 source has a
656 px bar, room for 8 entries. At podcast framing the crop fills the canvas
and there is NO bar; the list is then drawn over the picture behind a
translucent backing band (`boxed`). That deliberately breaks the letter of
E18-F03 ("not over video content") to keep its intent (readable on any
background) — owner's decision, 2026-09-03: cropping the picture to
manufacture a bar was rejected because at podcast framing the crop is full
source height at y=0 and a wide shot can carry the face low enough to lose
it. One band for the whole montage, computed from the TIGHTEST bar among its
segments, so the list never moves at a cut.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ass as ass_mod

TITLE_SIZE = 64        # font size of the "TOP N" line
TITLE_LINE = 80        # its line height
LINE_MAX = 70          # entry line height when the bar has room
LINE_MIN = 44          # below this the digits stop being readable at phone size
LINE_BOXED = 60        # over the picture: as compact as it can stay readable
BAND_GAP = 24          # breathing room between the last entry and the picture
NUMBER_COLUMN = 90     # where an entry's text will start, right of its number
# 55 % opaque black behind the list when it sits over the picture. ASS alpha
# runs the other way (00 = opaque), so 0x73 is 45 % transparent.
BOX_ALPHA = "&H73&"
REVEAL_FADE_MS = 240   # the entry that just started fades in, nothing else moves


@dataclass(frozen=True)
class Band:
    top: int          # y of the title line
    line_h: int       # height of one entry line
    count: int        # entries (N)
    boxed: bool       # True: no bar to sit in, drawn over the picture on a backing band

    @property
    def entries_top(self) -> int:
        return self.top + TITLE_LINE

    @property
    def bottom(self) -> int:
        return self.entries_top + self.count * self.line_h + BAND_GAP

    def entry_y(self, row: int) -> int:
        return self.entries_top + row * self.line_h


def band_for(bars: list[int], count: int) -> Band:
    """Where the list goes, given the top letterbox bar of every segment.

    `bars` are the pad_y values (0 where a segment has no bar). The tightest
    one decides: the list is identical on every segment, so it must fit the
    segment with the least room. The line height shrinks from LINE_MAX
    toward LINE_MIN to fit more entries into a shorter bar; when even the
    floor does not fit, the list is drawn over the picture instead
    (`boxed`) — the module docstring says why that is the chosen degradation.
    """
    count = max(1, int(count))
    bar = min(bars) if bars else 0
    available = bar - ass_mod.TOP_SAFE_PX - TITLE_LINE - BAND_GAP
    line = min(LINE_MAX, available // count) if available > 0 else 0
    if line >= LINE_MIN:
        return Band(top=ass_mod.TOP_SAFE_PX, line_h=line, count=count, boxed=False)
    return Band(top=ass_mod.TOP_SAFE_PX, line_h=LINE_BOXED, count=count, boxed=True)


def play_order(count: int) -> list[int]:
    """Rank positions (0 = rank 1) in the order they play: a countdown, rank
    N first and rank 1 last. The list therefore fills from the bottom up and
    the top slot is the last reveal — the genre's hook, and what "reveal in
    play order, not 1 to N" (D-17) implies. One pure function, not a
    setting: flipping to source-time order is a one-line change here."""
    return list(range(max(0, int(count)) - 1, -1, -1))


def title_for(count: int) -> str:
    return f"TOP {int(count)}"


def overlay_styles(preset: ass_mod.Preset, band: Band) -> str:
    """The [V4+ Styles] lines the overlay needs, in the caption preset's
    face and colours so the list matches the captions' brand. Top-left
    aligned (7): an event's own MarginV is then its distance from the top,
    so every line is placed by margin and no \\pos arithmetic is needed."""
    bold = -1 if preset.bold else 0
    entry_size = max(24, int(band.line_h * 0.8))
    m = ass_mod.SIDE_MARGIN
    common = f"{preset.primary},{preset.primary},{preset.outline_color},&H00000000,{bold},0,0,0,100,100,0,0,1"
    return (
        f"Style: RankTitle,{preset.font},{TITLE_SIZE},{common},{preset.outline},0,7,{m},{m},0,1\n"
        f"Style: RankEntry,{preset.font},{entry_size},{common},{preset.outline},0,7,{m},{m},0,1\n"
        # The backing band: a drawing, so no font is involved and one shape
        # covers the whole list instead of a box per line.
        "Style: RankBand,Inter,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,"
        "100,100,0,0,1,0,0,7,0,0,0,1\n"
    )


def overlay_events(
    preset: ass_mod.Preset,
    band: Band,
    play_index: int,
    duration: float,
) -> str:
    """The Dialogue lines for ONE segment: the title, the backing band when
    there is no bar, and every entry 1..N in the state it has during this
    segment — played (primary colour), playing now (the preset's active
    colour, faded in at the segment start), or still to come (dimmed, digits
    only). `play_index` is this segment's position in play order, 0-based.

    Entry text (the label, E18-F04) is not in this version: the reveal is
    the number lighting up. The text column is reserved (NUMBER_COLUMN) so
    labels can arrive without moving the numbers.
    """
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, duration))
    order = play_order(band.count)
    lines: list[str] = []
    if band.boxed:
        h = band.bottom
        lines.append(
            f"Dialogue: 0,{start},{end},RankBand,,0,0,0,"
            f"{{\\an7\\pos(0,0)\\1c&H000000&\\1a{BOX_ALPHA}\\bord0\\shad0\\p1}}"
            f"m 0 0 l {ass_mod.PLAY_RES_X} 0 l {ass_mod.PLAY_RES_X} {h} l 0 {h}{{\\p0}}\n"
        )
    title = title_for(band.count)
    lines.append(
        f"Dialogue: 2,{start},{end},RankTitle,,0,0,{band.top},"
        f"{ass_mod._esc(title.upper() if preset.uppercase else title)}\n"
    )
    for row in range(band.count):
        position = order.index(row)
        if position < play_index:
            tags = f"{{\\c{preset.primary}}}"
        elif position == play_index:
            tags = f"{{\\c{preset.active}\\fad({REVEAL_FADE_MS},0)}}"
        else:
            tags = f"{{\\c{preset.primary}\\alpha&H80&}}"
        lines.append(
            f"Dialogue: 2,{start},{end},RankEntry,,0,0,{band.entry_y(row)},{tags}{row + 1}\n"
        )
    return "".join(lines)
