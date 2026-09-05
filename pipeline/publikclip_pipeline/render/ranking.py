"""Ranking mode of the render stage (E18-F02, E18-F06): vertical files from
the top finalists, each played back to back as a countdown under the
numbered list of captions/ranking.py — two of them, moments 1..N and
N+1..2N, beside the clips the stage renders anyway (D-18).

Shape: every segment is rendered exactly as a standalone clip would be —
the same render_clip, the same trajectory, captions and letterbox fill —
with the list for that segment spliced into its own caption document, and
the segments are then joined by a remux (renderer.concat_copy). The video
is encoded once; the montage carries no second lossy generation, which is
E18-F02's "must not look worse than the clips it is made of".

What this deliberately does not do: adopt editor-reshaped clips. The clip
loop keeps an editor's file for a structurally-edited clip; a montage
cannot, because the segment needs the list burned in. Such a segment
renders from job settings and the stage says so. The segment files are
the concat inputs and are deleted once the montage verifies; the caption
documents stay, as they do for clips. D-17's "one format, not both" was
reversed by D-18 after the owner saw the first version: the clips render
first and always (render/stage.py), and the montages are appended to the
same checkpoint.

Moment labels (E18-F04): before the first segment, every moment gets the
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
from .stage import _has_structural_edits, _previous_montages, _previous_render

# The file name carries the global rank range the video plays — ranking_1-5,
# ranking_6-10 — so the library rail, which reads the directory, can tell
# which is which. Segments: ranking_1-5_seg_00.
MONTAGE_STEM = "ranking_{}-{}"
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


def _blank_reason(out: dict) -> str:
    """Why a moment has no label, for label_errors: every answer the filter
    rejected — the retry's too (E18-F04 amendment) — with the text that was
    rejected, and the call error when an attempt did not answer at all.
    "Why is number 3 blank" is answered in the job dir by this string."""
    rejected = [f"{a['proposed']!r} ({a['rejected_because']})" for a in out.get("attempts") or []]
    if out.get("error"):
        if rejected:
            return f"the model's answer {rejected[0]} was rejected, and the retry failed: {out['error']}"
        return str(out["error"])
    if len(rejected) > 1:
        return f"the model's answers {' and '.join(rejected)} were both rejected"
    if rejected:
        return f"the model's answer {rejected[0]} was rejected"
    return "no label"


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
        reason = _blank_reason(out)
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


def montage_slices(ranked: list[int], count: int) -> list[list[int]]:
    """The moment slices the videos play, in rank order: ranks 1..N, then
    N+1..2N — the second only when it is a full N, so both videos are the
    same "TOP N" with the same list length and the same geometry (E18-F06:
    one series). A partial second slice is not a smaller video; it is no
    video, and render_montages says why."""
    count = max(1, int(count))
    first, second = ranked[:count], ranked[count:2 * count]
    slices = [first] if first else []
    if len(second) == count:
        slices.append(second)
    return slices


def _shortfall_note(have: int, count: int, select_count: int) -> str:
    """Why only one video, with the setting that decides it named: the
    second needs 2N finalists with a camera pass, and the camera pass
    covers clips.select_count finalists — a setting this mode must not
    touch itself, since changing it re-runs scoring and the camera pass
    (E18-F05: switching the mode invalidates nothing before render)."""
    note = (
        f"The second ranking video needs {2 * count} finalists with a camera pass; "
        f"this job has {have}, so one ranking video was made."
    )
    if select_count < 2 * count:
        note += (
            f" 'Clips to render' is {select_count}; set it to at least {2 * count} "
            "(a re-run: selection re-scores) for two."
        )
    return note


def render_montages(
    ctx: StageContext, inputs: RenderInputs, fills: dict[str, str]
) -> tuple[list[dict], dict]:
    """Every ranking video this job gets, after the clip loop (D-18: as
    well as the clips, never instead). Returns the montage output entries —
    the stage appends them to the clip entries — and the `ranking` summary
    the checkpoint carries. `fills` is the clip loop's resolved map: the
    segments ARE those clips, so they render with those fills."""
    settings = ctx.settings
    count = int(settings.ranking.count)
    ranked = ranked_clips(inputs.clips, inputs.trajectories, 2 * count)
    if not ranked:
        raise StageError("No clips were rendered.", code="no-clips-rendered")
    slices = montage_slices(ranked, count)
    note = None
    if len(slices) < 2:
        note = _shortfall_note(len(ranked), count, settings.clips.select_count)
        ctx.emit(-1, note)
    if len(slices[0]) < count:
        ctx.emit(
            -1,
            f"Only {len(slices[0])} of the top {count} moments have a camera pass — "
            f"the ranking video uses {len(slices[0])}.",
        )

    # The previous render's videos go before anything is written: their
    # names carry the rank range, so a count change would otherwise leave
    # the old files beside the new ones, and the library rail reads the
    # directory, not the checkpoint.
    for previous in _previous_montages(ctx.job_dir):
        path = Path(str(previous.get("path", "")))
        if path.name and path.exists():
            path.unlink(missing_ok=True)

    used = [i for ranked_slice in slices for i in ranked_slice]
    trajectories = {
        i: json.loads(Path(inputs.trajectories[str(i)]).read_text(encoding="utf-8"))
        for i in used
    }
    # One band for the whole series (E18-F06): the tightest top bar among
    # EVERY segment of every video, so the list never moves at a cut and
    # never differs between the two. A segment without a bar (podcast
    # framing) contributes 0 and forces the boxed layout for all of them.
    # Sized for the list length both share — a short first video only
    # exists when there is no second.
    bars = []
    for traj in trajectories.values():
        geometry = renderer.letterbox_geometry(traj.get("content_w", 0), traj.get("content_h", 0))
        bars.append(geometry[1] if geometry else 0)
    band = overlay.band_for(bars, len(slices[0]))
    if band.boxed:
        ctx.emit(-1, "No letterbox bar at this framing — the list sits over the top of the picture.")
    job_preset = ass_mod.resolve_preset(settings.caption_preset, settings.captions.overrides)
    styles = overlay.overlay_styles(job_preset, band)

    # The text next to each number, before the first encode, for every
    # moment of every video: one map, one reuse rule (moment_labels).
    labels, label_errors = moment_labels(ctx, inputs, used)

    entries: list[dict] = []
    records: list[dict] = []
    for m, ranked_slice in enumerate(slices):
        ranks = (m * count + 1, m * count + len(ranked_slice))
        entry, record = _render_one(
            ctx, inputs, ranked_slice, ranks, trajectories, band, styles, job_preset,
            labels, fills, index=m + 1, total=len(slices),
        )
        entries.append(entry)
        records.append(record)
    return entries, {
        "count": count,
        "band": {"top": band.top, "line_h": band.line_h, "boxed": band.boxed},
        # One record per video, in series order (ranks 1..N first). Presence
        # of this list is the shape version: a `ranking` without it is the
        # one-montage checkpoint E18-F02..F04 wrote, which artifacts_ok
        # retires because it has no clip files.
        "montages": records,
        "note": note,
        # E18-F04. An output, not a fingerprint: artifacts_ok never reads
        # these. `labels` is what the next render reuses (moment_labels);
        # `label_errors` is why a blank entry is blank.
        "labels": labels,
        "label_errors": label_errors,
    }


def _render_one(
    ctx: StageContext,
    inputs: RenderInputs,
    ranked: list[int],
    ranks: tuple[int, int],
    trajectories: dict[int, dict],
    band: overlay.Band,
    styles: str,
    job_preset: ass_mod.Preset,
    labels: dict,
    fills: dict[str, str],
    *,
    index: int,
    total: int,
) -> tuple[dict, dict]:
    """One ranking video from `ranked` (its moments, rank order): the
    countdown of segments, each through render_clip with the list spliced
    into its own caption document, then the remux. `ranks` is the global
    rank range it plays — its file name and what the review panel shows;
    inside the video the list counts 1..N, so both videos are "TOP N"."""
    settings = ctx.settings
    n = len(ranked)
    stem = MONTAGE_STEM.format(ranks[0], ranks[1])
    # Play order is a countdown over rank positions; `order` is the clip
    # index playing at each position.
    order = [ranked[p] for p in overlay.play_order(n)]
    label_texts = [(labels.get(str(i)) or {}).get("text") for i in ranked]
    total_s = sum(float(inputs.clips[i]["end"]) - float(inputs.clips[i]["start"]) for i in order)
    ctx.emit(
        -1,
        f"Ranking video {index} of {total} (moments {ranks[0]}–{ranks[1]}): "
        f"{n} moments, {_fmt_total(total_s)} total.",
    )

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
        ctx.emit(k / max(1, n), f"Rendering moment #{rank} of video {index} ({k + 1}/{n})…")
        if _has_structural_edits(edit, clip):
            ctx.emit(-1, f"Moment #{rank}: editor bounds/cuts cannot join a montage — rendered from job settings.")

        words, clip_events = clip_captions(inputs, start, end)
        style = clip_style(ctx, edit)
        ass_path = inputs.out_dir / f"{stem}_seg_{k:02d}.ass"
        ass_doc = ass_mod.build_ass(
            words, clip_events, preset_name=style["preset"], emoji_ok=inputs.emoji_ok,
            overrides=style["overrides"],
            extra_styles=styles,
            extra_events=overlay.overlay_events(job_preset, band, k, duration, labels=label_texts),
        )
        ass_path.write_text(ass_doc, encoding="utf-8")

        seg_path = inputs.out_dir / f"{stem}_seg_{k:02d}.mp4"
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

    out_path = inputs.out_dir / f"{stem}.mp4"
    ctx.emit(0.98, f"Joining the moments of video {index}…")
    try:
        renderer.concat_copy(segment_paths, out_path)
    except RuntimeError as err:
        raise StageError(
            "The ranking video failed to join.", code="render-failed", detail=str(err)
        ) from err
    check = renderer.verify_output(out_path, total_s)
    if not check["ok"]:
        raise StageError(
            f"The ranking video failed verification (duration {check['duration']:.1f}s, "
            f"{check['width']}x{check['height']}).",
            code="clip-verification-failed",
        )
    for seg_path in segment_paths:
        seg_path.unlink(missing_ok=True)

    top = inputs.clips[ranked[0]]
    entry = {
        # The rank-1 clip's index, so the review panel's audit shows the
        # winning moment. `montage` is what tells the checkpoint readers
        # this entry is not that clip's own file; `ranks` is which video.
        "clip": ranked[0],
        "path": str(out_path),
        "score": top["score"],
        "best_platform": top["best_platform"],
        "duration": round(check["duration"], 2),
        "words": words_total,
        "event_tags": tags_total,
        "montage": True,
        "ranks": [ranks[0], ranks[1]],
    }
    record = {
        "path": str(out_path),
        "ranks": [ranks[0], ranks[1]],
        "rendered": n,
        "order": order,
        "title": overlay.title_for(n),
        "segments": segments,
    }
    return entry, record
