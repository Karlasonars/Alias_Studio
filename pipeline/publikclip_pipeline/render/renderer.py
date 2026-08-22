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


def scale_pad_vf(content_w: float, content_h: float) -> list[str]:
    """Scale-to-width + center-pad-to-height -vf fragment for a crop window
    whose aspect ratio doesn't match 9:16 (the gameplay end of the framing
    dial — see camera.director._resolve_content_box). Degenerates to the
    original single scale (no pad, no new filter) whenever content is
    already 9:16-or-narrower, so gameplay_amount=0 has zero rendering
    regression."""
    if content_w and content_h:
        scaled_h = content_h * (OUT_W / content_w)
        scaled_h = max(2, int(round(scaled_h / 2)) * 2)  # even, for x264/NVENC
        if scaled_h < OUT_H:
            pad_y = (OUT_H - scaled_h) // 2
            return [
                f"scale={OUT_W}:{scaled_h}:flags=lanczos",
                f"pad={OUT_W}:{OUT_H}:0:{pad_y}:color=black",
            ]
    return [f"scale={OUT_W}:{OUT_H}:flags=lanczos"]


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
) -> None:
    duration = clip_end - clip_start
    boxes = crop_boxes(trajectory["frames"], src_w, src_h)
    if not boxes:
        boxes = [(src_h * 9 // 16 // 2 * 2, src_h - src_h % 2, 0, 0)]
    fps = float(trajectory.get("fps", 25))

    cmd_path = out_path.with_suffix(".cmd")
    cmd_path.write_text("\n".join(sendcmd_lines(boxes, fps)) + "\n")

    w0, h0, x0, y0 = boxes[0]
    vf_parts = [
        f"sendcmd=f={_q(cmd_path)}",
        f"crop@c=w={w0}:h={h0}:x={x0}:y={y0}",
        *scale_pad_vf(trajectory.get("content_w", 0), trajectory.get("content_h", 0)),
        "setsar=1",
    ]
    if ass_path is not None:
        sub = f"subtitles=filename={_q(ass_path)}"
        if fonts_dir is not None:
            sub += f":fontsdir={_q(fonts_dir)}"
        vf_parts.append(sub)

    vcodec = video_encoder_args(hardware_encode)

    args = [
        ffmpeg_bin.ffmpeg(), "-y", "-v", "error",
        "-ss", f"{clip_start:.3f}", "-t", f"{duration:.3f}",
        "-i", media_path,
        "-vf", ",".join(vf_parts),
        "-af", f"loudnorm=I={lufs}:TP={true_peak}:LRA=11",
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
