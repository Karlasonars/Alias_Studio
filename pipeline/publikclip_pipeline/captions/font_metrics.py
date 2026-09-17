"""Font metrics for laying text out the way libass will draw it.

Why this exists: the story card (captions/story_card.py) fills its card
with the story's opening text and must stop at a word boundary BEFORE the
bottom row — which means knowing, before ffmpeg runs, how many lines a
paragraph takes and where each line breaks. libass answers that only by
rendering, so the card measures with the numbers libass measures with:
the advance widths in the face's own `hmtx` table, scaled the way libass
scales a face for an ASS font size.

That scaling is the part worth writing down, because it is not what a
CSS or Word font size means. libass (ass_font.c:ass_face_set_size) sizes
a face so that its OS/2 usWinAscent + usWinDescent equals the ASS font
size, and takes a line's ascent and descent from those same two numbers
(ass_font_get_asc_desc — "VSFilter uses metrics from the OS/2 table"):
an ASS size is a LINE PITCH, not an em, and a line advances by exactly
the size in every face. What differs between faces is the em: Inter
Bold's win height is 1.21 em, so `\\fs54` draws Inter at a 44.6 px em;
Archivo Black's is 1.347 em, so the same `\\fs54` draws it at a 40 px em
with the same 54 px between lines. One font unit is `size × hhea height
/ (win height × face height)` px — FreeType scales the face so that its
own ascender − descender (the OS/2 typo values when the face asks for
them with fsSelection bit 7, the hhea values otherwise) spans `size ×
hhea height / win height`, which is libass's request — and the win box
at that scale is the line. The first draft of this module advanced lines
by the hhea height instead, and the pixel test caught Archivo Black's
lines landing 10 px apart from where they were measured, six lines deep
into the bottom row. Kerning is not applied: the caption document sets
no `Kerning: yes`, so libass leaves HarfBuzz's `kern` feature off, and
ligatures only ever make a line narrower than the sum of its advances —
the safe direction for a line that must fit.

The reader is deliberately minimal — the table directory, `head`, `hhea`,
`OS/2`, `hmtx` and one Unicode `cmap` subtable (format 12, else 4) —
because the faces it reads are the three bundled OFL fonts and nothing
else. A preset whose `font_file` is missing or unreadable degrades to a
generic estimate (§5.9), never to a crash; the card then merely measures
a little wide and ends a line early.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import ass as ass_mod

# What a character the face cannot map is assumed to advance, in em, and
# what an unreadable face is assumed to be: a wide text face, so a line
# measured with the guess is never narrower than libass's fallback glyph
# would make it.
FALLBACK_ADVANCE_EM = 0.65
_FALLBACK_UPM = 1000
_FALLBACK_HEIGHT = 1200


@dataclass(frozen=True)
class Metrics:
    """One face's numbers, in font units, plus the scale libass applies."""

    units_per_em: int
    hhea_height: int            # hhea ascender − descender
    face_height: int            # what FreeType calls ascender − descender (typo when asked, else hhea)
    win_height: int             # usWinAscent + usWinDescent — what an ASS font size IS
    advances: tuple[int, ...]   # hmtx advance per glyph id; ids past the end take the last
    cmap: dict[int, int]        # code point → glyph id
    real: bool = True           # False for the estimate that stands in for an unreadable face

    def unit_px(self, size: float) -> float:
        """Pixels per font unit at ASS size `size`, as libass scales it."""
        return float(size) * self.hhea_height / (self.win_height * self.face_height)

    def pitch(self, size: float) -> float:
        """What libass advances between two lines at ASS size `size`: the
        win box at that scale — the size itself, for a face whose typo
        and hhea heights agree, which every bundled face's do."""
        return self.win_height * self.unit_px(size)

    def advance(self, ch: str) -> int:
        gid = self.cmap.get(ord(ch))
        if gid is None:
            return int(round(FALLBACK_ADVANCE_EM * self.units_per_em))
        if gid >= len(self.advances):
            return self.advances[-1] if self.advances else int(round(FALLBACK_ADVANCE_EM * self.units_per_em))
        return self.advances[gid]

    def width(self, text: str, size: float) -> float:
        """The advance width of `text` on one line at ASS size `size`, px."""
        return sum(self.advance(ch) for ch in text) * self.unit_px(size)


FALLBACK = Metrics(
    units_per_em=_FALLBACK_UPM, hhea_height=_FALLBACK_HEIGHT, face_height=_FALLBACK_HEIGHT,
    win_height=_FALLBACK_HEIGHT, advances=(), cmap={}, real=False,
)


def _signed16(value: int) -> int:
    # libass reads usWinAscent/Descent through a (short) cast — "sometimes
    # used for signed values despite unsigned in spec" — so this does too.
    return value - 0x10000 if value >= 0x8000 else value


def _format4(data: bytes, off: int) -> dict[int, int]:
    seg_x2 = struct.unpack(">H", data[off + 6:off + 8])[0]
    seg = seg_x2 // 2
    ends = struct.unpack(f">{seg}H", data[off + 14:off + 14 + seg_x2])
    starts = struct.unpack(f">{seg}H", data[off + 16 + seg_x2:off + 16 + 2 * seg_x2])
    deltas = struct.unpack(f">{seg}h", data[off + 16 + 2 * seg_x2:off + 16 + 3 * seg_x2])
    range_base = off + 16 + 3 * seg_x2
    range_offsets = struct.unpack(f">{seg}H", data[range_base:range_base + seg_x2])
    out: dict[int, int] = {}
    for i in range(seg):
        for code in range(starts[i], min(ends[i], 0xFFFE) + 1):
            if range_offsets[i] == 0:
                gid = (code + deltas[i]) & 0xFFFF
            else:
                at = range_base + 2 * i + range_offsets[i] + 2 * (code - starts[i])
                gid = struct.unpack(">H", data[at:at + 2])[0]
                if gid:
                    gid = (gid + deltas[i]) & 0xFFFF
            if gid:
                out[code] = gid
    return out


def _format12(data: bytes, off: int) -> dict[int, int]:
    n_groups = struct.unpack(">I", data[off + 12:off + 16])[0]
    out: dict[int, int] = {}
    for g in range(n_groups):
        at = off + 16 + 12 * g
        start, end, gid = struct.unpack(">III", data[at:at + 12])
        for code in range(start, min(end, 0x10FFFF) + 1):
            out[code] = gid + (code - start)
    return out


def _cmap(data: bytes, off: int) -> dict[int, int]:
    """The face's Unicode mapping: a full-range format 12 subtable when
    the face has one, else the BMP format 4 one."""
    n = struct.unpack(">H", data[off + 2:off + 4])[0]
    chosen: tuple[int, int] | None = None
    for i in range(n):
        platform, encoding, sub = struct.unpack(">HHI", data[off + 4 + 8 * i:off + 12 + 8 * i])
        if not (platform == 0 or (platform == 3 and encoding in (1, 10))):
            continue
        fmt = struct.unpack(">H", data[off + sub:off + sub + 2])[0]
        if fmt == 12:
            chosen = (12, off + sub)
            break
        if fmt == 4 and chosen is None:
            chosen = (4, off + sub)
    if chosen is None:
        raise ValueError("no Unicode cmap subtable")
    return _format12(data, chosen[1]) if chosen[0] == 12 else _format4(data, chosen[1])


def read(path: Path) -> Metrics:
    """The metrics of one TrueType file. Raises on anything it cannot
    read — `load` turns that into the fallback."""
    data = path.read_bytes()
    if data[:4] == b"ttcf":
        raise ValueError("font collections are not supported")
    n_tables = struct.unpack(">H", data[4:6])[0]
    tables: dict[str, int] = {}
    for i in range(n_tables):
        rec = 12 + 16 * i
        tag = data[rec:rec + 4].decode("latin-1")
        tables[tag] = struct.unpack(">I", data[rec + 8:rec + 12])[0]
    head, hhea, hmtx, cmap = (tables[t] for t in ("head", "hhea", "hmtx", "cmap"))
    upm = struct.unpack(">H", data[head + 18:head + 20])[0]
    asc, desc = struct.unpack(">hh", data[hhea + 4:hhea + 8])
    n_metrics = struct.unpack(">H", data[hhea + 34:hhea + 36])[0]
    raw = struct.unpack(f">{2 * n_metrics}H", data[hmtx:hmtx + 4 * n_metrics])
    advances = raw[0::2]  # (advanceWidth, lsb) pairs; only the advances matter here
    hhea_height = asc - desc
    face_height, win_height = hhea_height, hhea_height
    if "OS/2" in tables:
        os2 = tables["OS/2"]
        selection = struct.unpack(">H", data[os2 + 62:os2 + 64])[0]
        typo_asc, typo_desc = struct.unpack(">hh", data[os2 + 68:os2 + 72])
        win_asc, win_desc = (_signed16(v) for v in struct.unpack(">HH", data[os2 + 74:os2 + 78]))
        if selection & 0x80 and typo_asc - typo_desc > 0:   # USE_TYPO_METRICS
            face_height = typo_asc - typo_desc
        if win_asc + win_desc > 0:
            win_height = win_asc + win_desc
    if upm <= 0 or hhea_height <= 0 or face_height <= 0 or not advances:
        raise ValueError("unusable font metrics")
    return Metrics(
        units_per_em=upm, hhea_height=hhea_height, face_height=face_height,
        win_height=win_height, advances=tuple(advances), cmap=_cmap(data, cmap),
    )


@lru_cache(maxsize=8)
def load(font_file: str) -> Metrics:
    """The metrics of a bundled face by its file name (a preset's
    `font_file`), read once per process. FALLBACK for a file that is
    missing or not a TrueType font the reader understands."""
    try:
        return read(ass_mod.FONTS_DIR / str(font_file or ""))
    except (OSError, ValueError, KeyError, IndexError, struct.error):
        return FALLBACK


def for_preset(preset: ass_mod.Preset) -> Metrics:
    return load(preset.font_file)


# ---------------------------------------------------------------------------
# Wrapping and fitting


@dataclass(frozen=True)
class Token:
    """A word on a line — or, when a word is wider than the line, one
    piece of it. `cut` marks a piece that continues on the next line, so
    a truncation never ends on one."""

    text: str
    cut: bool = False


def _pieces(metrics: Metrics, size: float, word: str, max_width: float) -> list[Token]:
    """A word as tokens: itself, or — when it is wider than a whole line —
    the character-greedy pieces that each fit one, every piece but the
    last marked `cut`."""
    if metrics.width(word, size) <= max_width:
        return [Token(word)]
    pieces: list[str] = []
    current = ""
    for ch in word:
        if current and metrics.width(current + ch, size) > max_width:
            pieces.append(current)
            current = ""
        current += ch
    pieces.append(current)
    return [Token(p, cut=i < len(pieces) - 1) for i, p in enumerate(pieces)]


def wrap(metrics: Metrics, size: float, text: str, max_width: float) -> list[list[Token]]:
    """Greedy word wrap of one paragraph at ASS size `size` into lines no
    wider than `max_width` px — the same first-fit rule libass applies
    before it evens a `\\q0` paragraph out, so the line count matches."""
    space = metrics.width(" ", size)
    lines: list[list[Token]] = []
    line: list[Token] = []
    used = 0.0
    for word in text.split():
        for token in _pieces(metrics, size, word, max_width):
            width = metrics.width(token.text, size)
            if line and used + space + width > max_width:
                lines.append(line)
                line, used = [], 0.0
            used += (space if line else 0.0) + width
            line.append(token)
            if token.cut:
                lines.append(line)
                line, used = [], 0.0
    if line:
        lines.append(line)
    return lines


def _join(line: list[Token]) -> str:
    return " ".join(t.text for t in line)


ELLIPSIS = "…"
_TRAILING = ".,;:"   # punctuation an ellipsis replaces rather than follows


def fit(
    metrics: Metrics, size: float, paragraphs: list[str], max_width: float, max_lines: int,
) -> tuple[list[str], bool]:
    """The lines of `paragraphs` (each starting on a new line) that fit in
    `max_lines`, and whether anything was left out. When something was,
    the last kept line ends with an ellipsis and at a WORD boundary:
    never mid-word, never on a piece of a split word, and measured so
    the ellipsis itself fits the width. Nothing fits: ([], True)."""
    lines = [line for p in paragraphs for line in wrap(metrics, size, p, max_width)]
    if not lines:
        return [], False
    if len(lines) <= max_lines:
        return [_join(line) for line in lines], False
    kept = [list(line) for line in lines[:max(0, max_lines)]]
    while kept:
        last = kept[-1]
        if not last:
            kept.pop()
            continue
        if last[-1].cut:
            last.pop()      # a piece of a word: back up to where the word began
            continue
        head = _join(last[:-1])
        tail = last[-1].text.rstrip(_TRAILING) or last[-1].text
        candidate = (f"{head} {tail}" if head else tail) + ELLIPSIS
        if metrics.width(candidate, size) <= max_width:
            return [_join(line) for line in kept[:-1]] + [candidate], True
        last.pop()
    return [], True
