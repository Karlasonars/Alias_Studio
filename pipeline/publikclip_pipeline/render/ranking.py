"""Ranking mode of the render stage (E18-F02): ONE vertical file from the
top-N finalists, played back to back as a countdown under the numbered
list of captions/ranking.py.

Shape: every segment is rendered exactly as a standalone clip would be —
the same render_clip, the same trajectory, captions and letterbox fill —
with the list for that segment spliced into its own caption document, and
the segments are then joined by a remux (renderer.concat_copy). The video
is encoded once; the montage carries no second lossy generation, which is
E18-F02's "must not look worse than the clips it is made of".

What this deliberately does not do: adopt editor-reshaped clips. The batch
path keeps an editor's file for a structurally-edited clip; a montage
cannot, because the segment needs the list burned in. Such a segment
renders from job settings and the stage says so. No per-clip files survive:
the segment files are the concat inputs and are deleted once the montage
verifies (D-17: one format, not both). The caption documents stay, as they
do for clips.

Moment labels (E18-F04): before the segment loop, every moment gets the
one to three words that sit next to its number, from copywriting/labels.py
— one LLM call per moment, burned into the segment's caption document
with the rest of the list. Labels are an OUTPUT of the render, not a
setting of it: generated once, kept on the checkpoint (`ranking.labels`),
reused verbatim by every later render of the same moment, and never part
of artifacts_ok — a model's word choice must not invalidate a render, and
the same job re-rendered must burn the same words. See moment_labels.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..captions import ass as ass_mod
from ..captions import ranking as overlay
from ..copywriting import labels as labels_mod
from ..jobs.queue import StageContext, StageError
from ..scoring import llm as llm_mod
from . import renderer
from .inputs import RenderInputs, clip_captions, clip_style, clip_transcript
from .stage import _fills_for, _has_structural_edits, _previous_render

MONTAGE_NAME = "ranking.mp4"
SEGMENT_NAME = "ranking_seg_{:02d}"
# A hard cut mid-waveform clicks; in a montage the click is followed by more
# audio rather than the end of the file. Short enough to be inaudible as a
# fade, long enough to take the edge off the discontinuity.
EDGE_FADE_S = 0.015


def _fmt_total(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def ranked_clips(clips: list[dict], trajectories: dict[str, str], count: int) -> list[int]:
    """Clip indices of the top N, rank order. score["clips"] is already
    sorted by score, so rank is position — but only clips the camera pass
    produced a trajectory for can be rendered, so those are what rank."""
    have = [
        i for i in range(len(clips))
        if trajectories.get(str(i)) and Path(trajectories[str(i)]).exists()
    ]
    return have[: max(0, int(count))]


# A stored label is reused only for the SAME moment. Clip indices are
# positions in score.json, and a scoring re-run can put a different moment
# at the same position; reusing by index alone would burn the old moment's
# words onto the new one's pictures, silently. Bounds identify the moment,
# with the tolerance _has_structural_edits already uses for "same bounds".
MOMENT_TOLERANCE_S = 0.05


def _same_moment(stored: object, clip: dict) -> bool:
    try:
        return (
            isinstance(stored, dict)
            and bool(stored.get("text"))
            and abs(float(stored["start"]) - float(clip["start"])) <= MOMENT_TOLERANCE_S
            and abs(float(stored["end"]) - float(clip["end"])) <= MOMENT_TOLERANCE_S
        )
    except (KeyError, TypeError, ValueError):
        return False


def moment_labels(
    ctx: StageContext, inputs: RenderInputs, ranked: list[int]
) -> tuple[dict[str, dict | None], dict[str, str]]:
    """The label per moment, keyed by clip index like `fills`: an entry
    {text, grounded_in, start, end}, or None for a moment without one.
    Second value: why each None is a None, same keys, the rank named in
    the text — "why is number 3 blank" is the question it answers.

    Generated ONCE. A label is an output, not a setting: the last render's
    checkpoint is read first and every label it holds for the same moment
    (bounds, not just index — _same_moment) is reused verbatim, so a
    re-render burns the same words and spends no call. Only moments
    without a stored label are asked for: new ones after a count change,
    and ones that failed last time — a None is a failure, not a label, so
    a re-run of the stage retries it (a cached render never reaches here
    and keeps the blank). The client is built only when there is something
    to ask, so a fully-reused run makes no network call at all. Nothing
    regenerates a label that exists: there is no editing in this version
    (D-17).

    Failure is a blank entry, never a failed render (§5.9). A client that
    cannot be built blanks every pending moment, said once; a call that
    fails blanks that moment, said once; a failure the client marks fatal
    (a rejected key, no quota) blanks the rest without asking, since every
    further call would fail the same way.
    """
    previous = (_previous_render(ctx.job_dir).get("ranking") or {}).get("labels")
    previous = previous if isinstance(previous, dict) else {}
    labels: dict[str, dict | None] = {}
    errors: dict[str, str] = {}
    pending: list[int] = []
    for i in ranked:
        stored = previous.get(str(i))
        if _same_moment(stored, inputs.clips[i]):
            labels[str(i)] = stored
        else:
            pending.append(i)
    if not pending:
        return labels, errors

    def blank(i: int, reason: str) -> None:
        labels[str(i)] = None
        errors[str(i)] = f"moment #{ranked.index(i) + 1}: {reason}"

    ctx.emit(-1, f"Naming {len(pending)} moment{'s' if len(pending) != 1 else ''}…")
    try:
        client = llm_mod.make_client(ctx.settings.llm_mode, ctx.settings.gemini_model)
    except Exception as err:  # noqa: BLE001 — a label is optional; the montage is not
        for i in pending:
            blank(i, str(err))
        ctx.emit(-1, f"Moment labels unavailable — the list shows numbers only. {err}")
        return labels, errors

    for n, i in enumerate(pending):
        clip = inputs.clips[i]
        start, end = float(clip["start"]), float(clip["end"])
        out = labels_mod.generate(
            client, clip_transcript(inputs, start, end), clip.get("summary", "")
        )
        if out["label"]:
            labels[str(i)] = {
                "text": out["label"],
                "grounded_in": out["grounded_in"],
                "start": start,
                "end": end,
            }
            continue
        reason = out["error"] or (
            f"the model's answer {out['proposed']!r} was rejected ({out['rejected_because']})"
        )
        blank(i, reason)
        if out["fatal"]:
            for j in pending[n + 1:]:
                blank(j, reason)
            ctx.emit(-1, f"Moment labels unavailable — the list shows numbers only. {reason}")
            break
        ctx.emit(
            -1,
            f"Moment #{ranked.index(i) + 1}: no label — its entry shows the number only. {reason}",
        )
    return labels, errors


def render_montage(ctx: StageContext, inputs: RenderInputs, fingerprint: dict) -> dict:
    settings = ctx.settings
    count = int(settings.ranking.count)
    ranked = ranked_clips(inputs.clips, inputs.trajectories, count)
    if not ranked:
        raise StageError("No clips were rendered.", code="no-clips-rendered")
    n = len(ranked)
    if n < count:
        ctx.emit(-1, f"Only {n} of the top {count} moments have a camera pass — the ranking video uses {n}.")

    # Play order is a countdown over rank positions; `order` is the clip
    # index playing at each position. Its keys are what the fills map and
    # the fingerprint iterate (stage._fill_keys).
    order = [ranked[p] for p in overlay.play_order(n)]
    trajectories = {
        i: json.loads(Path(inputs.trajectories[str(i)]).read_text(encoding="utf-8"))
        for i in order
    }
    total = sum(float(inputs.clips[i]["end"]) - float(inputs.clips[i]["start"]) for i in order)
    ctx.emit(-1, f"Ranking video: {n} moments, {_fmt_total(total)} total.")

    # One band for every segment, sized by the tightest top bar among them —
    # the list must not move at a cut. A segment without a bar (podcast
    # framing) contributes 0 and forces the boxed layout for all of them.
    bars = []
    for traj in trajectories.values():
        geometry = renderer.letterbox_geometry(traj.get("content_w", 0), traj.get("content_h", 0))
        bars.append(geometry[1] if geometry else 0)
    band = overlay.band_for(bars, n)
    if band.boxed:
        ctx.emit(-1, "No letterbox bar at this framing — the list sits over the top of the picture.")
    job_preset = ass_mod.resolve_preset(settings.caption_preset, settings.captions.overrides)
    styles = overlay.overlay_styles(job_preset, band)

    # The text next to each number, before the first encode: it is burned
    # into every segment's document. In rank order, as the overlay draws
    # its rows; a None row draws the number alone.
    labels, label_errors = moment_labels(ctx, inputs, ranked)
    label_texts = [(labels.get(str(i)) or {}).get("text") for i in ranked]

    fills = _fills_for([str(i) for i in order], inputs.clip_edits, settings)
    segment_paths: list[Path] = []
    segments: list[dict] = []
    words_total = 0
    tags_total = 0
    offset = 0.0
    for k, i in enumerate(order):
        clip = inputs.clips[i]
        edit = inputs.clip_edits.get(str(i)) or {}
        rank = ranked.index(i) + 1
        start, end = float(clip["start"]), float(clip["end"])
        duration = end - start
        ctx.emit(k / max(1, n), f"Rendering moment #{rank} ({k + 1}/{n})…")
        if _has_structural_edits(edit, clip):
            ctx.emit(-1, f"Moment #{rank}: editor bounds/cuts cannot join a montage — rendered from job settings.")

        words, clip_events = clip_captions(inputs, start, end)
        style = clip_style(ctx, edit)
        ass_path = inputs.out_dir / f"{SEGMENT_NAME.format(k)}.ass"
        ass_doc = ass_mod.build_ass(
            words, clip_events, preset_name=style["preset"], emoji_ok=inputs.emoji_ok,
            overrides=style["overrides"],
            extra_styles=styles,
            extra_events=overlay.overlay_events(job_preset, band, k, duration, labels=label_texts),
        )
        ass_path.write_text(ass_doc, encoding="utf-8")

        seg_path = inputs.out_dir / f"{SEGMENT_NAME.format(k)}.mp4"
        try:
            renderer.render_clip(
                inputs.media, seg_path, start, end, trajectories[i],
                ass_path if inputs.captions_ok else None, ass_mod.FONTS_DIR,
                lufs=style["lufs"], true_peak=style["true_peak"],
                src_w=inputs.src_w, src_h=inputs.src_h,
                hardware_encode=settings.performance.hardware_encode,
                letterbox_fill=fills[str(i)],
                edge_fade_s=EDGE_FADE_S,
            )
        except RuntimeError as err:
            raise StageError(
                f"Moment #{rank} failed to encode.", code="render-failed", detail=str(err)
            ) from err
        check = renderer.verify_output(seg_path, duration)
        if not check["ok"]:
            raise StageError(
                f"Moment #{rank} failed verification (duration {check['duration']:.1f}s, "
                f"{check['width']}x{check['height']}).",
                code="clip-verification-failed",
            )
        segment_paths.append(seg_path)
        segments.append({
            "clip": i,
            "rank": rank,
            "offset": round(offset, 3),
            "duration": round(check["duration"], 2),
        })
        offset += duration
        words_total += len(words)
        tags_total += len(clip_events)

    out_path = inputs.out_dir / MONTAGE_NAME
    ctx.emit(0.98, "Joining the moments…")
    try:
        renderer.concat_copy(segment_paths, out_path)
    except RuntimeError as err:
        raise StageError(
            "The ranking video failed to join.", code="render-failed", detail=str(err)
        ) from err
    check = renderer.verify_output(out_path, total)
    if not check["ok"]:
        raise StageError(
            f"The ranking video failed verification (duration {check['duration']:.1f}s, "
            f"{check['width']}x{check['height']}).",
            code="clip-verification-failed",
        )
    for seg_path in segment_paths:
        seg_path.unlink(missing_ok=True)

    top = inputs.clips[ranked[0]]
    return {
        "outputs": [
            {
                # The rank-1 clip's index, so the review panel's audit shows
                # the winning moment. `montage` is what tells the checkpoint
                # readers this entry is not that clip's own file.
                "clip": ranked[0],
                "path": str(out_path),
                "score": top["score"],
                "best_platform": top["best_platform"],
                "duration": round(check["duration"], 2),
                "words": words_total,
                "event_tags": tags_total,
                "montage": True,
            }
        ],
        "kept_from_editor": [],
        "emoji_ok": inputs.emoji_ok,
        "captions_burned": inputs.captions_ok,
        **fingerprint,
        "fills": fills,
        # Presence of this key is what routes artifacts_ok onto the ranking
        # path; `count` is the setting as rendered, `rendered` how many
        # moments actually existed.
        "ranking": {
            "count": count,
            "rendered": n,
            "order": order,
            "title": overlay.title_for(n),
            "segments": segments,
            "band": {"top": band.top, "line_h": band.line_h, "boxed": band.boxed},
            # E18-F04. An output, not a fingerprint: artifacts_ok never reads
            # these. `labels` is what the next render reuses (moment_labels);
            # `label_errors` is why a blank entry is blank.
            "labels": labels,
            "label_errors": label_errors,
        },
    }
