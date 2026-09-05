"""What a render reads, loaded once, for either output unit.

Split out of render/stage.py when ranking mode (E18) arrived: the clip loop
and the montage (render/ranking.py) build every segment from exactly these
inputs and these two per-clip helpers, so they live in one place neither
path owns. stage.py keeps the checkpoint contract and the clip loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..jobs.queue import StageContext, StageError


@dataclass
class RenderInputs:
    """Everything a render of either shape reads from the prior stages."""

    media: str
    src_w: int
    src_h: int
    segments: list
    timeline: list
    rms: list
    grid: float
    clips: list[dict]
    trajectories: dict[str, str]
    clip_edits: dict
    captions_ok: bool
    emoji_ok: bool
    out_dir: Path


def load_inputs(ctx: StageContext, clip_edits: dict) -> RenderInputs:
    from ..captions import ass as ass_mod
    from . import ffmpeg_bin

    if not ffmpeg_bin.supports_captions():
        ctx.emit(-1, "No caption-capable ffmpeg found — fetching one…")
        if not ffmpeg_bin.ensure_capable(progress=lambda f, m: ctx.emit(f, m)):
            ctx.emit(-1, "Caption burning unavailable — rendering without captions.")

    prior = ctx.prior or {}
    ingest = prior.get("ingest")
    diarize = prior.get("diarize")
    events = prior.get("events")
    score = prior.get("score")
    camera = prior.get("camera")
    if not (ingest and diarize and events and score and camera):
        raise StageError("Render needs every prior stage output.", code="prior-stage-missing")

    probe = ingest["probe"]
    curves = json.loads(Path(events["curves_path"]).read_text(encoding="utf-8"))
    captions_ok = ffmpeg_bin.supports_captions()
    emoji_ok = ass_mod.emoji_probe() if captions_ok else False
    ctx.emit(-1, f"Emoji support: {'yes' if emoji_ok else 'no (dropping emoji)'}")
    out_dir = ctx.job_dir / "clips"
    out_dir.mkdir(exist_ok=True)
    return RenderInputs(
        media=ingest["media_path"],
        src_w=int(probe["width"]),
        src_h=int(probe["height"]),
        segments=diarize["segments"],
        timeline=events["timeline"],
        rms=curves["rms"],
        grid=float(curves["grid_sec"]),
        clips=score["clips"],
        trajectories=camera["trajectories"],
        clip_edits=clip_edits,
        captions_ok=captions_ok,
        emoji_ok=emoji_ok,
        out_dir=out_dir,
    )


def clip_captions(inputs: RenderInputs, start: float, end: float) -> tuple[list, list[dict]]:
    """Words and bus events inside one clip, in clip-relative time — the
    caption input a render of either shape builds its ASS from."""
    from ..captions import ass as ass_mod

    words = []
    for seg in inputs.segments:
        for w in seg.get("words", []):
            if start <= w["start"] < end:
                words.append(
                    ass_mod.Word(
                        text=w["word"],
                        start=round(w["start"] - start, 3),
                        end=round(min(w["end"], end) - start, 3),
                    )
                )
    ass_mod.mark_emphasis(words, inputs.rms, inputs.grid, clip_start=start)
    clip_events = [
        {
            "type": e["type"],
            "start": round(max(0.0, e["start"] - start), 3),
            "end": round(min(e["end"], end) - start, 3),
        }
        for e in inputs.timeline
        if e["end"] > start and e["start"] < end and e["type"] != "pause"
    ]
    return words, clip_events


def clip_transcript(inputs: RenderInputs, start: float, end: float) -> str:
    """The words spoken inside one clip, as plain text — what a moment's
    label (E18-F04) is grounded in. Same window rule as clip_captions, a
    word belongs to the clip its start falls in, so the label is asked
    about exactly the words the captions will show."""
    return " ".join(
        w["word"]
        for seg in inputs.segments
        for w in seg.get("words", [])
        if start <= w["start"] < end
    )


def clip_style(ctx: StageContext, edit: dict) -> dict:
    """The style overrides the batch paths CAN honour for one clip, so a
    restyle doesn't silently undo them. (The framing dial is baked into the
    trajectory by the camera stage, so a per-clip gameplay_amount is
    handled there, not here.)"""
    lufs = edit.get("lufs_target")
    peak = edit.get("true_peak_db")
    return {
        "preset": edit.get("caption_preset") or ctx.settings.caption_preset,
        "overrides": {
            **ctx.settings.captions.overrides,
            **(edit.get("caption_overrides") or {}),
        },
        "lufs": lufs if lufs is not None else ctx.settings.lufs_target,
        "true_peak": peak if peak is not None else ctx.settings.true_peak_db,
    }
