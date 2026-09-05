"""Clip renderer: one ffmpeg filter_complex per clip.

The sendcmd architecture (vendored from mutonby/openshorts punch_in.py +
reframe_v2.py, MIT): the director's per-frame trajectory array becomes a
deduped sendcmd command file driving a labeled crop filter — hard cuts are
just discontinuities in the same array, pans are smooth regions, punch-ins
already live in the w/h values. One decode, one encode:

    sendcmd → crop@c → scale 1080x1920 → subtitles burn → loudnorm

Deduping to change-points matters: a 45 s clip at 25 fps is 1125 frames and
writing every parameter every frame slows the filter measurably (openshorts'
own comment). Even dimensions everywhere — x264/NVENC reject odd ones.

Encoder tiers follow openshorts ffmpeg_utils.py: try hardware
(h264_videotoolbox on macOS), fall back to libx264, mapping quality between
CRF and the hardware encoder's bitrate model.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from . import ffmpeg_bin

OUT_W = 1080
OUT_H = 1920
X264_CRF = 19
VT_BITRATE = "10M"
# Blur strength for the letterbox fill. High enough that the background reads
# as texture rather than a second, confusing copy of the shot.
BLUR_SIGMA = 22

_vt_checked: bool | None = None


def videotoolbox_available() -> bool:
    """Probe once: encode 0.2 s of black through h264_videotoolbox."""
    global _vt_checked
    if _vt_checked is None:
        proc = subprocess.run(
            [
                ffmpeg_bin.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "color=black:s=320x240:d=0.2",
                "-c:v", "h264_videotoolbox", "-f", "null", "-",
            ],
            capture_output=True, timeout=60,
        )
        _vt_checked = proc.returncode == 0
    return _vt_checked


def crop_boxes(frames: list[list[float]], src_w: int, src_h: int) -> list[tuple[int, int, int, int]]:
    """Director frames [x, y, w, h] → even-int (w, h, x, y) crop boxes,
    clamped in-bounds (openshorts crop_boxes rounding rules)."""
    boxes: list[tuple[int, int, int, int]] = []
    for x, y, w, h in frames:
        wi = max(2, min(int(w) - int(w) % 2, src_w))
        hi = max(2, min(int(h) - int(h) % 2, src_h))
        xi = max(0, min(int(round(x)), src_w - wi))
        yi = max(0, min(int(round(y)), src_h - hi))
        boxes.append((wi, hi, xi - xi % 2, yi - yi % 2))
    return boxes


def sendcmd_lines(boxes: list[tuple[int, int, int, int]], fps: float, target: str = "crop@c") -> list[str]:
    """Per-frame w/h/x/y commands, deduped to change-points (openshorts)."""
    lines: list[str] = []
    prev: tuple[int, int, int, int] | None = None
    for i, box in enumerate(boxes):
        if box == prev:
            continue
        t = i / fps
        w, h, x, y = box
        pw, ph, px, py = prev if prev else (None, None, None, None)
        if w != pw:
            lines.append(f"{t:.4f} {target} w {w};")
        if h != ph:
            lines.append(f"{t:.4f} {target} h {h};")
        if x != px:
            lines.append(f"{t:.4f} {target} x {x};")
        if y != py:
            lines.append(f"{t:.4f} {target} y {y};")
        prev = box
    return lines


def _q(path: str) -> str:
    """ffmpeg filter-option quoting: single quotes make the value literal;
    an embedded quote closes, escapes, reopens ('\\'').

    Windows adds two wrinkles the mac path never sees: backslash is
    ffmpeg's escape character even inside quotes (av_get_token), and the
    drive-letter colon reads as an option separator on some parse levels.
    Forward slashes (fine for libass and every filter) plus an escaped
    colon is the canonical portable form: 'C\\:/Users/…/clip.ass'."""
    text = str(path)
    if os.name == "nt":
        text = text.replace("\\", "/").replace(":", "\\:")
    return "'" + text.replace("'", "'\\''") + "'"


@lru_cache(maxsize=1)
def _available_encoders() -> frozenset[str]:
    try:
        proc = subprocess.run(
            [ffmpeg_bin.ffmpeg(), "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    return frozenset(
        line.split()[1]
        for line in proc.stdout.splitlines()
        if line.startswith(" V") and len(line.split()) > 1
    )


# Hardware encoders in preference order, each with the flags that keep it
# quality-targeted rather than a bitrate guess (so output stays close to the
# x264 baseline). Probed in order; the first that actually encodes wins.
_HW_ENCODERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("h264_videotoolbox", ("-b:v", VT_BITRATE, "-allow_sw", "1")),
    ("h264_nvenc", ("-preset", "p5", "-rc", "vbr", "-cq", str(X264_CRF), "-b:v", "0")),
    ("h264_amf", ("-quality", "balanced", "-rc", "cqp", "-qp_i", str(X264_CRF),
                  "-qp_p", str(X264_CRF))),
    ("h264_qsv", ("-global_quality", str(X264_CRF))),
)


@lru_cache(maxsize=None)
def encoder_works(name: str, args: tuple[str, ...] = ()) -> bool:
    """Actually encode a few frames through this encoder.

    Being listed by `ffmpeg -encoders` is not the same as being usable, and
    the difference is not academic: h264_nvenc is compiled into every BtbN
    build and lists fine, then refuses to open when the driver's NVENC API
    is older than the build wants ("Required: 13.1 Found: 13.0"). QuickSync
    lists on machines with no Intel GPU and fails to create a session. Both
    would surface as a failed render halfway through a job, long after the
    user flipped the setting — so pay a fraction of a second here instead.

    Probed at the real output size: some encoders only fail on particular
    dimensions or alignments.
    """
    try:
        proc = subprocess.run(
            [
                ffmpeg_bin.ffmpeg(), "-hide_banner", "-v", "error", "-y",
                "-f", "lavfi", "-i", f"testsrc2=size={OUT_W}x{OUT_H}:rate=30:duration=0.2",
                "-c:v", name, *args, "-pix_fmt", "yuv420p", "-f", "null", "-",
            ],
            capture_output=True, timeout=120,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def video_encoder_args(hardware: bool) -> list[str]:
    """Encoder flags for one clip.

    x264 at CRF 19 is the reference path and stays the default: hardware
    encoders are dramatically faster but produce different bits, so switching
    silently would change every existing render. When `hardware` is on, the
    best accelerator that actually works on this machine wins; when none do,
    this quietly returns the x264 path rather than failing the render.
    """
    if hardware:
        for name, args in _HW_ENCODERS:
            if encoder_works(name, args):
                return ["-c:v", name, *args]
    elif encoder_works("h264_videotoolbox", _HW_ENCODERS[0][1]):
        # macOS has always used VideoToolbox as its baseline.
        return ["-c:v", "h264_videotoolbox", *_HW_ENCODERS[0][1]]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(X264_CRF)]


def hardware_encoder_name(hardware: bool = True) -> str:
    """Which accelerator would actually be used, '' for none. For the
    settings panel, so 'hardware encoding' can say what it resolved to
    instead of leaving the user guessing why nothing got faster."""
    if not hardware:
        return ""
    for name, args in _HW_ENCODERS:
        if encoder_works(name, args):
            return name
    return ""


def letterbox_geometry(content_w: float, content_h: float) -> tuple[int, int] | None:
    """(scaled_h, pad_y) when this crop needs bars, else None.

    One place for the arithmetic so the black-bar and blurred-bar paths can
    never disagree about where the image sits.
    """
    if not (content_w and content_h):
        return None
    scaled_h = content_h * (OUT_W / content_w)
    scaled_h = max(2, int(round(scaled_h / 2)) * 2)  # even, for x264/NVENC
    if scaled_h >= OUT_H:
        return None
    return scaled_h, (OUT_H - scaled_h) // 2


def scale_pad_vf(content_w: float, content_h: float, fill: str = "black") -> list[str]:
    """Scale-to-width + fill-to-height -vf fragment for a crop window whose
    aspect ratio doesn't match 9:16 (the gameplay end of the framing dial —
    see camera.director._resolve_content_box).

    `fill` chooses what occupies the bars: "black", or "blur" for a
    zoomed, blurred copy of the same frame. Blur costs a second scale plus a
    gaussian per frame, which is why it is opt-in rather than the default.

    Degenerates to the original single scale (no bars, no extra filters)
    whenever the content already fills the canvas, so gameplay_amount=0 has
    zero rendering regression either way.
    """
    geometry = letterbox_geometry(content_w, content_h)
    if geometry is None:
        return [f"scale={OUT_W}:{OUT_H}:flags=lanczos"]
    scaled_h, pad_y = geometry

    if fill != "blur":
        return [
            f"scale={OUT_W}:{scaled_h}:flags=lanczos",
            f"pad={OUT_W}:{OUT_H}:0:{pad_y}:color=black",
        ]

    # The background is the SAME frame blown up to cover the canvas and
    # blurred, so the bars carry the shot's own colour and motion instead of
    # two dead black slabs. force_original_aspect_ratio=increase + crop is
    # what makes it cover rather than letterbox a second time.
    #
    # Returned as ONE element with internal ';' on purpose: both callers join
    # this list with ',' into a single filtergraph, and ',' chains filters
    # while ';' separates labelled chains. Splitting these across list
    # elements would produce ",[lb_bg]scale..." — a syntax error. The labels
    # are prefixed lb_ so they cannot collide with the per-clip edit graph's
    # own [vc]/[vb]/[ov*] labels.
    return [
        f"split=2[lb_a][lb_b]"
        f";[lb_a]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase"
        f",crop={OUT_W}:{OUT_H},gblur=sigma={BLUR_SIGMA}[lb_bg]"
        f";[lb_b]scale={OUT_W}:{scaled_h}:flags=lanczos[lb_fg]"
        f";[lb_bg][lb_fg]overlay=0:{pad_y}"
    ]


def render_clip(
    media_path: str,
    out_path: Path,
    clip_start: float,
    clip_end: float,
    trajectory: dict,
    ass_path: Path | None,
    fonts_dir: Path | None,
    lufs: float = -14.0,
    true_peak: float = -1.0,
    src_w: int = 1920,
    src_h: int = 1080,
    timeout: float = 1800.0,
    hardware_encode: bool = False,
    letterbox_fill: str = "black",
    edge_fade_s: float = 0.0,
    overlay_vf: str = "",
) -> None:
    """One clip, one ffmpeg run.

    `edge_fade_s` fades the audio in and out over that many seconds at each
    end. Zero (the default) adds no filter at all, so a standalone clip's
    command line is byte-identical to what it always was; the ranking
    montage (render/ranking.py) sets it because a hard cut mid-waveform
    clicks, and in a montage the click is followed by more audio instead
    of the end of the file.

    `overlay_vf` is a ready filter fragment spliced after the scale/pad and
    BEFORE the caption burn, so captions draw over whatever it adds — the
    watermark (render/watermark.py). Empty, the default, adds nothing."""
    duration = clip_end - clip_start
    boxes = crop_boxes(trajectory["frames"], src_w, src_h)
    if not boxes:
        boxes = [(src_h * 9 // 16 // 2 * 2, src_h - src_h % 2, 0, 0)]
    fps = float(trajectory.get("fps", 25))

    cmd_path = out_path.with_suffix(".cmd")
    cmd_path.write_text("\n".join(sendcmd_lines(boxes, fps)) + "\n", encoding="utf-8")

    w0, h0, x0, y0 = boxes[0]
    vf_parts = [
        f"sendcmd=f={_q(cmd_path)}",
        f"crop@c=w={w0}:h={h0}:x={x0}:y={y0}",
        *scale_pad_vf(
            trajectory.get("content_w", 0), trajectory.get("content_h", 0), letterbox_fill
        ),
        "setsar=1",
    ]
    if overlay_vf:
        vf_parts.append(overlay_vf)
    if ass_path is not None:
        sub = f"subtitles=filename={_q(ass_path)}"
        if fonts_dir is not None:
            sub += f":fontsdir={_q(fonts_dir)}"
        vf_parts.append(sub)

    vcodec = video_encoder_args(hardware_encode)

    af_parts = [f"loudnorm=I={lufs}:TP={true_peak}:LRA=11"]
    if edge_fade_s > 0:
        fade = min(edge_fade_s, duration / 2)
        af_parts.append(f"afade=t=in:st=0:d={fade:.3f}")
        af_parts.append(f"afade=t=out:st={max(0.0, duration - fade):.3f}:d={fade:.3f}")

    args = [
        ffmpeg_bin.ffmpeg(), "-y", "-v", "error",
        "-ss", f"{clip_start:.3f}", "-t", f"{duration:.3f}",
        "-i", media_path,
        "-vf", ",".join(vf_parts),
        "-af", ",".join(af_parts),
        *vcodec,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-map_metadata", "-1",  # metadata scrub (openshorts ffmpeg_utils)
        str(out_path),
    ]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    cmd_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Render failed: {(proc.stderr or '')[-800:]}")


def concat_copy(parts: list[Path], out_path: Path, timeout: float = 600.0) -> None:
    """Join already-rendered segments into one file without re-encoding.

    The concat demuxer plus `-c copy` is a remux: every segment keeps the
    single encode it got from render_clip, so the montage carries no second
    lossy generation (E18-F02: it must not look worse than the clips it is
    made of). This is only valid because every segment of one job comes out
    of render_clip with one argument set — same encoder flags, 1080x1920,
    setsar=1, yuv420p, aac 192k at 48 kHz, fps inherited from the one
    source — and each starts on its own keyframe. Measured before this was
    written: frame counts concatenate exactly, and the audio runs one AAC
    frame (21.3 ms) long regardless of segment count, which is tail padding,
    not drift.

    The list file uses forward slashes and the demuxer's own quoting
    (single quotes, an embedded quote closes-escapes-reopens), the same
    portable form _q uses for filter options; `-safe 0` is needed because
    absolute paths are "unsafe" to the demuxer by default."""
    list_path = out_path.with_suffix(".concat.txt")
    lines = []
    for part in parts:
        text = str(part).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{text}'")
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = [
        ffmpeg_bin.ffmpeg(), "-y", "-v", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        str(out_path),
    ]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    list_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Concat failed: {(proc.stderr or '')[-800:]}")


def verify_output(out_path: Path, expected_duration: float) -> dict:
    """Post-render sanity: exists, has both streams, duration within 1.5 s."""
    proc = subprocess.run(
        [
            ffmpeg_bin.ffprobe(), "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(out_path),
        ],
        capture_output=True, text=True, timeout=120,
    )
    import json

    info = json.loads(proc.stdout or "{}")
    streams = info.get("streams", [])
    has_v = any(s.get("codec_type") == "video" for s in streams)
    has_a = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(info.get("format", {}).get("duration", 0.0))
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    return {
        "ok": has_v and has_a and abs(duration - expected_duration) < 1.5,
        "duration": duration,
        "width": video.get("width"),
        "height": video.get("height"),
    }
