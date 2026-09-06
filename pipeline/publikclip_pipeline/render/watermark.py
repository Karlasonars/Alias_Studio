"""The watermark (E19-F02): the channel mark on every output file — clips
and ranking videos alike — bottom centre.

Where it sits comes from renderer.letterbox_geometry, never from a guessed
offset: where the framing leaves a bottom bar tall enough, the mark is
centred in the bar and opaque; where there is no bar (the podcast end of
the dial) or the bar is too thin to hold it, the mark sits on the bottom of
the picture at reduced opacity. Either way its top edge stays below the
captions' anchor (`preset.margin_v` from the bottom, CAPTION_GAP away) — a
watermark over a subtitle is worse than none — and when the captions sit
so low that no room is left, the clip renders without it and says so.

Two kinds, one placement:

- an image: a PNG, overlaid by ffmpeg through the `movie` source filter
  inside the graph both render paths already build, BEFORE the caption
  burn, so the captions draw over it. No second `-i`: a simple `-vf` graph
  has exactly one input, and the stage's render is `-vf`. The fragment's
  labels are `wm_`-prefixed — the blur fill owns `lb_*` and the editor's
  graph owns [vc]/[vb]/[ov*]/[vo*]/[vf] — and it composes with both.
- a word: burned through the same ASS document as the captions, in the
  caption preset's face. NOT drawtext: that needs libfreetype, which the
  resolved ffmpeg may not have (§5.7 — listed is not usable, as NVENC
  taught), and a font path inside a filter option on Windows is its own
  escaping problem. libass and the bundled fonts are already probed for the
  captions; the word rides that.

The file's CONTENT is in the render fingerprint (sha256 of the bytes), not
only its path: a logo replaced under the same name would otherwise keep
the old logo in every finished clip, silently — §4 rule 1 exactly. A hash
rather than size+mtime because mtime is not identity on Windows: a copy, a
sync tool or a checkout rewrites it without changing a byte and would
re-render an hour of clips for nothing, while the same bytes under a new
mtime hash the same. The PNG is small and the hash is taken once per stage
start.

A missing or unreadable file renders the clip without a mark, with a line
in the log (§5.9); the fingerprint records "missing", so the render is
redone once the file is back.
"""

from __future__ import annotations

import hashlib
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..captions import ass as ass_mod
from . import renderer

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

IMAGE_WIDTH_FRAC = 0.22   # the logo's width as a fraction of the frame width
IMAGE_MAX_HEIGHT = 240    # and never taller than this, whatever its aspect
TEXT_SIZE = 44            # the word, in PlayRes px
TEXT_LINE = 1.2           # libass line height over font size, near enough for placement
BAR_PAD = 24              # a bar must hold the mark with this much air above and below
PICTURE_MARGIN = 120      # from the bottom edge when the mark sits on the picture
PICTURE_OPACITY = 0.6     # over the picture: reduced, so it reads as a mark, not a sticker
CAPTION_GAP = 24          # the mark's top edge stays this far below the caption anchor
EDGE_MIN = 16             # and its bottom edge this far above the frame edge, or no mark


class WatermarkError(ValueError):
    """A file the import refuses: unreadable, or not a PNG."""


@dataclass(frozen=True)
class Mark:
    kind: str          # "image" | "text"
    path: str = ""     # image: the PNG as the job stores it
    width: int = 0     # image: the PNG's own pixels, from its header
    height: int = 0
    text: str = ""     # text: the word


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    width: int
    height: int
    opacity: float
    in_bar: bool

    @property
    def margin_v(self) -> int:
        """ASS MarginV for alignment 2: the mark's bottom edge from the frame's."""
        return renderer.OUT_H - (self.y + self.height)


@dataclass(frozen=True)
class Composed:
    """What one render adds for the mark: a -vf fragment (image) or two ASS
    fragments (text). All empty when there is no mark or no room, so a
    render without one is byte-identical to a render before this existed."""

    vf: str = ""
    styles: str = ""
    events: str = ""


def png_size(data: bytes | None) -> tuple[int, int] | None:
    """(width, height) from the IHDR chunk, or None for anything that is not
    a PNG. Eight signature bytes, a length, "IHDR", then two big-endian
    unsigned ints — no image library needed to know whether ffmpeg's movie
    filter will accept the file."""
    if not data or len(data) < 24:
        return None
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return (width, height) if width and height else None


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _text(settings) -> str:
    return " ".join(str(settings.watermark.text or "").split())


def fingerprint(settings) -> dict:
    """What the render checkpoint stores and artifacts_ok compares: the
    image's path AND its content hash, or the word, or {} — the factory
    shape, which is also what every checkpoint from before the setting
    existed reads as (§4 rule 3: nothing on disk re-renders when the
    feature arrives)."""
    image = str(settings.watermark.image or "").strip()
    if image:
        data = _read(Path(image))
        digest = hashlib.sha256(data).hexdigest() if data is not None else "missing"
        return {"kind": "image", "path": image, "sha256": digest}
    text = _text(settings)
    if text:
        return {"kind": "text", "text": text}
    return {}


def resolve(settings, say: Callable[[str], None] | None = None) -> Mark | None:
    """The mark this job renders with, or None. The image wins when set; a
    set image that is missing or not a PNG means NO mark (never a silent
    fall-through to the word — the user asked for the logo), said once
    through `say`."""
    image = str(settings.watermark.image or "").strip()
    if image:
        data = _read(Path(image))
        size = png_size(data)
        if size is None:
            if say:
                why = "missing" if data is None else "not a PNG"
                say(f"Watermark image {Path(image).name} is {why} — rendering without a watermark.")
            return None
        return Mark("image", path=image, width=size[0], height=size[1])
    text = _text(settings)
    if text:
        return Mark("text", text=text)
    return None


def place(
    mark: Mark, content_w: float, content_h: float, caption_margin_v: int
) -> Placement | None:
    """Where the mark goes on the 1080x1920 canvas for one clip's framing.
    None when the captions leave no room under them."""
    if mark.kind == "image":
        w = int(round(renderer.OUT_W * IMAGE_WIDTH_FRAC))
        h = int(round(w * mark.height / mark.width))
        if h > IMAGE_MAX_HEIGHT:
            h = IMAGE_MAX_HEIGHT
            w = int(round(h * mark.width / mark.height))
        w, h = max(2, w - w % 2), max(2, h - h % 2)  # even, like every other dimension
    else:
        w, h = 0, int(round(TEXT_SIZE * TEXT_LINE))
    geometry = renderer.letterbox_geometry(content_w, content_h)
    if geometry is not None and geometry[1] >= h + 2 * BAR_PAD:
        pad_y = geometry[1]
        y = (renderer.OUT_H - pad_y) + (pad_y - h) // 2
        opacity, in_bar = 1.0, True
    else:
        y = renderer.OUT_H - PICTURE_MARGIN - h
        opacity, in_bar = PICTURE_OPACITY, False
    # Never over the captions: alignment 2 anchors their bottom edge at
    # margin_v from the frame's, and every line grows upward from there.
    floor = renderer.OUT_H - int(caption_margin_v) + CAPTION_GAP
    y = max(y, floor)
    if y + h > renderer.OUT_H - EDGE_MIN:
        return None
    return Placement(
        x=(renderer.OUT_W - w) // 2, y=y, width=w, height=h, opacity=opacity, in_bar=in_bar
    )


def image_vf(mark: Mark, placement: Placement) -> str:
    """The graph fragment that overlays the PNG: loaded by the `movie` source
    filter (one frame, which `overlay` repeats — its default eof_action —
    for every frame of the clip), scaled to the placement, faded through
    its alpha when it sits on the picture. Starts with a filter and ends
    unlabelled, so a ','-joined chain continues on either side: `null`
    carries the chain's current frame into the [wm_base] label."""
    chain = (
        f"movie=filename={renderer._q(mark.path)}"  # noqa: SLF001 — the one portable quoting
        f",scale={placement.width}:{placement.height}:flags=lanczos,format=rgba"
    )
    if placement.opacity < 1.0:
        chain += f",colorchannelmixer=aa={placement.opacity:.2f}"
    return (
        f"null[wm_base];{chain}[wm_src];"
        f"[wm_base][wm_src]overlay=x={placement.x}:y={placement.y}"
    )


def text_ass(
    mark: Mark, placement: Placement, preset: ass_mod.Preset, duration: float
) -> tuple[str, str]:
    """The word as (style line, dialogue line) for ass.build_ass: bottom-
    centre (alignment 2) with the placement's MarginV, white in the caption
    face with the preset's outline colour so it reads on any background,
    the ASS alpha carrying the placement's opacity (00 is opaque there)."""
    bold = -1 if preset.bold else 0
    m = ass_mod.SIDE_MARGIN
    alpha = f"&H{int(round((1.0 - placement.opacity) * 255)):02X}&"
    style = (
        f"Style: Watermark,{preset.font},{TEXT_SIZE},&H00FFFFFF,&H00FFFFFF,"
        f"{preset.outline_color},&H00000000,{bold},0,0,0,100,100,0,0,1,2,0,2,"
        f"{m},{m},{placement.margin_v},1\n"
    )
    start, end = ass_mod._fmt_time(0.0), ass_mod._fmt_time(max(0.04, duration))
    event = (
        f"Dialogue: 0,{start},{end},Watermark,,0,0,0,"
        f"{{\\alpha{alpha}\\q2}}{ass_mod._esc(mark.text)}\n"
    )
    return style, event


def compose(
    mark: Mark | None,
    content_w: float,
    content_h: float,
    preset: ass_mod.Preset,
    duration: float,
    say: Callable[[str], None] | None = None,
) -> Composed:
    """Everything one render adds for the mark, from one clip's framing and
    caption preset. The single function all three callers use — the
    stage's clip loop, the ranking segments and the editor's render — so
    the mark cannot land in two places for the same clip (§5.8)."""
    if mark is None:
        return Composed()
    placement = place(mark, content_w, content_h, preset.margin_v)
    if placement is None:
        if say:
            say(
                "The captions sit too low to leave room for the watermark — "
                "rendering this clip without it."
            )
        return Composed()
    if mark.kind == "image":
        return Composed(vf=image_vf(mark, placement))
    styles, events = text_ass(mark, placement, preset, duration)
    return Composed(styles=styles, events=events)


_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def safe_stem(name: str) -> str:
    stem = _UNSAFE.sub("_", name).strip("_")[:40]
    return stem or "watermark"


def import_image(src: Path) -> Path:
    """Copy a chosen PNG into PUBLIKCLIP_HOME/watermarks and return the
    stored path — what the deck sends as the job's `watermark.image`.
    Named by the source's stem plus eight hex of its content hash: the
    same bytes import to the same path, a changed logo to a new one, and
    nothing the user has on disk is referenced afterwards."""
    data = _read(src)
    if data is None:
        raise WatermarkError(f"cannot read {src.name}")
    if png_size(data) is None:
        raise WatermarkError(f"{src.name} is not a PNG image")
    dest_dir = config.watermarks_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{safe_stem(src.stem)}-{hashlib.sha256(data).hexdigest()[:8]}.png"
    if not dest.exists():
        tmp = dest.with_suffix(".png.tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)
    return dest
