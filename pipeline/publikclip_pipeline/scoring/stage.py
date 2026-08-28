"""Scoring stage: T1 rubric per candidate → cross-validation → rank → T2
frames on the finalists → per-platform composites + music briefs, all with
full provenance (decision #3).

Cost shape: ~35 T1 text calls + ~12 T2 vision calls + ~12 music calls per
video on Gemini Flash. In Ollama mode T2 is skipped (recorded as a missing
signal) and scores are labeled local-estimate."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .. import config
from ..jobs.queue import Stage, StageContext, StageError
from ..music import brief as music_brief
from . import constants as constants_mod
from . import frames as frames_mod
from . import llm as llm_mod
from . import rubric

SELECT_COUNT = 12

# Circuit breaker for the T1 loop (T-39). Skipping ONE moment whose call
# failed after its own 5-attempt retry ladder is §5.9 working; skipping all
# of them is a failed run wearing a success — a real outage once burned ten
# minutes of doomed, backoff-padded calls across 26 moments and the run
# carried on. Four CONSECUTIVE total failures is ~20 HTTP attempts spanning
# minutes of wall clock including backoff — beyond anything the per-call
# retries are designed to absorb — while still one more than the
# outage-recovers-at-moment-4 case a smaller threshold would wrongly kill.
# Any success resets the count, so a flaky-but-alive service never trips it.
CONSECUTIVE_FAILURE_LIMIT = 4


class _FactoryCtx:
    """Minimal StageContext stand-in so artifacts_ok can compute the
    factory-default fingerprint (the candidates stage's pattern)."""

    def __init__(self, settings: "config.Settings"):
        self.settings = settings


def _transcript_slice(segments: list[dict], start: float, end: float) -> tuple[str, str]:
    """(speaker-labeled transcript, flat text) for a window."""
    lines: list[str] = []
    flat: list[str] = []
    for seg in segments:
        if seg["end"] < start or seg["start"] > end:
            continue
        words = [w for w in seg.get("words", []) if start <= w["start"] < end]
        if not words:
            continue
        text = " ".join(w["word"] for w in words)
        speaker = seg.get("speaker", 0)
        lines.append(f"S{speaker}: {text}")
        flat.append(text)
    return "\n".join(lines), " ".join(flat)


def _events_in(timeline: list[dict], start: float, end: float, pad: float = 0.0) -> list[dict]:
    return [e for e in timeline if e["end"] >= start - pad and e["start"] <= end + pad]


def _events_desc(events: list[dict]) -> str:
    if not events:
        return "none detected"
    parts = []
    for e in events[:12]:
        parts.append(f"{e['type']} at {e['start'] - 0:.0f}s (conf {e.get('confidence', 0):.2f})")
    return "; ".join(parts)


def _window_pct(values: np.ndarray, grid_sec: float, start: float, end: float) -> float:
    """Percentile rank of this window's mean vs the whole video."""
    if len(values) == 0:
        return 0.0
    a, b = int(start / grid_sec), max(int(start / grid_sec) + 1, int(end / grid_sec))
    window_mean = float(np.mean(values[a : min(b, len(values))])) if a < len(values) else 0.0
    return float(np.mean(values <= window_mean))


class ScoreStage(Stage):
    name = "score"
    schema_version = 1

    @staticmethod
    def _settings_used(ctx: StageContext) -> dict:
        return {
            "llm_mode": ctx.settings.llm_mode,
            # A different model produces different scores for identical
            # inputs — and misses the LLM disk cache, which keys on the
            # model — so it must invalidate exactly like a weight change.
            "gemini_model": ctx.settings.gemini_model,
            "select_count": ctx.settings.clips.select_count,
            "min_words": ctx.settings.clips.min_words,
            "scoring": {
                "t0_weight": ctx.settings.scoring.t0_weight,
                "text_weight": ctx.settings.scoring.text_weight,
                "visual_weight": ctx.settings.scoring.visual_weight,
                "platform_weights": ctx.settings.scoring.platform_weights,
            },
        }

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        # Weights, the word gate and the model change which clips win and
        # what they score — a change here must rescore rather than serve old
        # numbers. Compared via fingerprint_ok rather than strict `==`
        # (T-21's events pattern): every checkpoint written before
        # gemini_model existed lacks the key, and a strict comparison would
        # force a rescore of every job on disk under the NEW model — which
        # misses the LLM cache and re-spends real API money on scores that
        # are already valid, honest work of the model that made them. A user
        # who actually changes the setting still mismatches and rescores.
        from ..jobs.queue import fingerprint_ok

        factory = self._settings_used(
            _FactoryCtx(config.Settings())  # type: ignore[arg-type]
        )
        return fingerprint_ok(data.get("settings_used") or {}, self._settings_used(ctx), factory)

    @staticmethod
    def _count_failure(ctx: StageContext, index: int, err: Exception) -> None:
        ctx.emit(-1, f"moment {index + 1} scoring failed, skipping: {err}")

    @staticmethod
    def _breaker_message(last: Exception) -> str:
        # T-13 will fold this into the catalogue; until then it must stand
        # on its own: the cause, what was NOT lost, and the way forward.
        return (
            f"The scoring model failed {CONSECUTIVE_FAILURE_LIMIT} moments in a row "
            "(each call already retried with backoff), so the service is down for "
            f"this run — stopping instead of failing every remaining moment. "
            f"Last error: {last}. Everything before scoring is checkpointed; resume "
            "this job to retry, or pick a different Gemini model in Settings → AI."
        )

    def run(self, ctx: StageContext) -> dict:
        prior = ctx.prior or {}
        ingest = prior.get("ingest")
        diarize = prior.get("diarize")
        events = prior.get("events")
        cands = prior.get("candidates")
        if not (ingest and diarize and events and cands):
            raise StageError(
                "Scoring needs ingest + diarize + events + candidates.",
                code="prior-stage-missing",
            )

        llm_mode = ctx.settings.llm_mode
        try:
            client = llm_mod.make_client(llm_mode, ctx.settings.gemini_model)
        except llm_mod.LlmError as err:
            raise StageError(str(err)) from err

        segments = diarize["segments"]
        timeline = events["timeline"]
        curves = json.loads(Path(events["curves_path"]).read_text(encoding="utf-8"))
        arousal = np.asarray(curves.get("arousal", []), dtype=float)
        arousal_grid = float(curves.get("arousal_grid_sec", 0.5))
        arousal_source = curves.get("arousal_source", "dsp-proxy")
        heatmap = ingest.get("heatmap")
        scenes_path = ctx.job_dir / "scenes.json"
        scene_times = (
            json.loads(scenes_path.read_text(encoding="utf-8")) if scenes_path.exists() else []
        )

        heat_values = None
        if heatmap:
            duration = float(ingest["probe"]["duration_sec"])
            heat_values = np.zeros(int(np.ceil(duration)))
            for seg in heatmap:
                a, b = int(seg["start_time"]), int(np.ceil(seg["end_time"]))
                heat_values[max(0, a) : min(len(heat_values), b)] = seg["value"]

        # Calibrated constants (decision #13): loaded once per run, version
        # stamped into every clip's provenance.
        scoring_config = constants_mod.active()
        cv_constants = scoring_config["constants"]

        candidates = cands["candidates"]
        scored: list[dict] = []
        consecutive_failures = 0
        llm_failures = 0
        last_llm_error: Exception | None = None
        for i, cand in enumerate(candidates):
            start, end = cand["start"], cand["end"]
            ctx.emit(i / max(1, len(candidates)) * 0.6, f"Scoring moment {i + 1}/{len(candidates)}…")
            labeled, flat = _transcript_slice(segments, start, end)
            if len(flat.split()) < ctx.settings.clips.min_words:
                continue
            window_events = _events_in(timeline, start, end)
            near_laughs = [e for e in _events_in(timeline, start, end, pad=3.0) if e["type"] == "laugh"]
            context = {
                "duration": end - start,
                "events_desc": _events_desc(window_events),
            }
            try:
                t1 = client.generate_json(rubric.t1_prompt(labeled, context), rubric.T1_SCHEMA)
            except llm_mod.LlmError as err:
                if err.fatal:
                    raise
                self._count_failure(ctx, i, err)
                llm_failures += 1
                consecutive_failures += 1
                last_llm_error = err
                if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                    raise StageError(
                        self._breaker_message(err), code="llm-consecutive-failures"
                    ) from err
                continue
            except Exception as err:  # noqa: BLE001
                self._count_failure(ctx, i, err)
                llm_failures += 1
                consecutive_failures += 1
                last_llm_error = err
                if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                    raise StageError(
                        self._breaker_message(err), code="llm-consecutive-failures"
                    ) from err
                continue
            consecutive_failures = 0  # the service is alive; isolated skips stay §5.9

            arousal_pct = _window_pct(arousal, arousal_grid, start, end)
            heatmap_pct = (
                _window_pct(heat_values, 1.0, start, end) if heat_values is not None else None
            )
            sub, adjustments = rubric.cross_validate(
                t1,
                laughs_near=near_laughs,
                arousal_pct=arousal_pct,
                heatmap_pct=heatmap_pct,
                constants=cv_constants,
            )
            scored.append(
                {
                    "start": start,
                    "end": end,
                    "curve_score": cand["curve_score"],
                    "channel_scores": cand["channel_scores"],
                    "t1_raw": t1,
                    "subscores": {k: round(v, 2) for k, v in sub.items()},
                    "adjustments": adjustments,
                    "arousal_pct": round(arousal_pct, 3),
                    "heatmap_pct": round(heatmap_pct, 3) if heatmap_pct is not None else None,
                    "summary": t1.get("summary", ""),
                    "transcript": labeled,
                }
            )

        if not scored:
            # Two very different failures used to share one message that
            # blamed the video. Name the real cause: a run where the LLM
            # failed every attempted moment is a service problem the user
            # can act on, not a video that lacks scoreable speech.
            if llm_failures:
                raise StageError(
                    f"Scoring produced nothing: the LLM failed on all {llm_failures} "
                    f"moment(s) it was asked about (last error: {last_llm_error}). "
                    "Nothing was scored — resume this job to retry once the service "
                    "or connection recovers.",
                    code="llm-all-failed",
                )
            raise StageError(
                "No candidate produced a scoreable transcript.",
                code="no-scoreable-transcript",
            )

        # Rank by best pre-visual platform score, take the finalists.
        def _text_rank(entry: dict) -> float:
            scores, _ = rubric.composite(
                entry["subscores"], entry["curve_score"], entry["heatmap_pct"], None,
                constants=cv_constants, scoring=ctx.settings.scoring,
            )
            return max(scores.values())

        scored.sort(key=_text_rank, reverse=True)
        finalists = scored[: ctx.settings.clips.select_count]

        # T2 visual pass + music brief on finalists only.
        supports_vision = client.backend == "gemini"
        for j, entry in enumerate(finalists):
            ctx.emit(0.6 + j / max(1, len(finalists)) * 0.35, f"Visual pass {j + 1}/{len(finalists)}…")
            visual = None
            if supports_vision:
                times = frames_mod.sample_times(entry["start"], entry["end"], scene_times)
                imgs = frames_mod.extract_frames(
                    ingest["media_path"], times, ctx.job_dir / "t2frames"
                )
                if imgs:
                    try:
                        visual = client.generate_json(
                            "Rate these frames sampled from one candidate vertical clip. "
                            "Judge visual interest for short-form: expressions, motion, variety.",
                            rubric.T2_SCHEMA,
                            images=imgs,
                        )
                    except Exception:  # noqa: BLE001 — visual is optional evidence
                        visual = None
            entry["t2"] = visual

            platform_scores, comp_adjustments = rubric.composite(
                entry["subscores"], entry["curve_score"], entry["heatmap_pct"], visual,
                constants=cv_constants, scoring=ctx.settings.scoring,
            )
            entry["adjustments"].extend(comp_adjustments)
            entry["platform_scores"] = platform_scores
            entry["score"] = max(platform_scores.values())
            entry["best_platform"] = max(platform_scores, key=platform_scores.get)

            window_events = _events_in(timeline, entry["start"], entry["end"])
            fired, missing = rubric.signals_summary(
                laughs_near=[e for e in window_events if e["type"] == "laugh"],
                events_in_window=window_events,
                arousal_pct=entry["arousal_pct"],
                heatmap_pct=entry["heatmap_pct"],
                t2_ran=visual is not None,
                arousal_source=arousal_source,
            )
            entry["signals_fired"] = fired
            entry["signals_missing"] = missing
            entry["confidence"] = "standard" if client.backend == "gemini" else "local-estimate"

            prior_mood = music_brief.mood_prior(window_events, entry["arousal_pct"])
            try:
                entry["music"] = client.generate_json(
                    music_brief.music_prompt(
                        entry["summary"], entry["transcript"], prior_mood, _events_desc(window_events)
                    ),
                    music_brief.MUSIC_SCHEMA,
                )
                entry["music"]["mood_prior"] = prior_mood
            except Exception:  # noqa: BLE001 — a clip without a music brief still ships
                entry["music"] = None

        finalists.sort(key=lambda e: e["score"], reverse=True)
        for entry in finalists:
            entry.pop("transcript", None)  # bulky; review UI re-slices from diarize

        return {
            "llm_mode": llm_mode,
            "model": client.model,
            "clips": finalists,
            "scored_count": len(scored),
            "t2_ran": supports_vision,
            "scoring_config_version": scoring_config["version"],
            "scoring_constants": cv_constants,
            "settings_used": self._settings_used(ctx),
        }
