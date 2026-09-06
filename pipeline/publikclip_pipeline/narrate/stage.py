"""Narrate stage (E20-F02): the story text → `narration.wav`.

Second stage of the story chain, between `ingest` (the background) and
`asr` (which transcribes THIS file for word timings — the captions never
come from the synthesiser's own alignment, F04). The title and the body
are synthesised separately and joined with a short silence, so the stage
knows exactly where the title ends: that boundary is the story card's
duration (F05) — the card shows the title while the narrator reads it,
and the one-word captions start on the first body word. Derived from the
audio the stage produced, never from a fixed number of seconds.

Fingerprint (§4 rule 1): the story text's hash, the voice and the speed —
everything that changes the bytes of the wav. A text edit re-runs this
stage and, through the cascade (rule 2), asr and render; nothing before
it. Rule 3 holds through fingerprint_ok: a key this build has not
written yet compares against the factory value.

Degradation (§5.9): a missing story file, a story over the limit, and a
narrator that cannot start (the package failed to import, the weights
could not be fetched) are each a described StageError with a catalogue
code — the job fails with a sentence and a next step, never a traceback.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from .. import config
from ..jobs.queue import Stage, StageContext, StageError, fingerprint_ok
from . import kokoro_tts, limits, story

NARRATION_FILE = "narration.wav"
# Silence between the title and the body: long enough to read as a beat,
# short enough that the card does not hang on a silent frame.
TITLE_GAP_SEC = 0.45


def _fingerprint(ctx: StageContext, text_sha256: str) -> dict:
    return {
        "text_sha256": text_sha256,
        "voice": ctx.settings.story.voice,
        "speed": float(ctx.settings.story.speed),
    }


def _factory_fingerprint() -> dict:
    factory = config.StorySettings()
    return {"text_sha256": "", "voice": factory.voice, "speed": float(factory.speed)}


def write_wav(path: Path, samples: np.ndarray, rate: int = kokoro_tts.SAMPLE_RATE) -> float:
    """16-bit mono PCM, the plainest wav there is — whisperx, ffmpeg and
    the disk pre-flight all read it without a decoder. Returns seconds."""
    clipped = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    tmp = path.with_suffix(".wav.tmp")
    with wave.open(str(tmp), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    tmp.replace(path)
    return len(pcm) / float(rate)


class NarrateStage(Stage):
    name = "narrate"
    schema_version = 1

    def __init__(self, synth: kokoro_tts.Synthesiser | None = None):
        # A synthesiser can be injected (tests hand in a fake that returns
        # a sine; §3 forbids loading the real weights there). None means
        # Kokoro, built lazily on the first run.
        self._synth = synth

    def artifacts_ok(self, ctx: StageContext, data: dict) -> bool:
        if not Path(str(data.get("audio_path") or "")).exists():
            return False
        try:
            current = story.load(ctx.job_dir)
        except (OSError, UnicodeDecodeError):
            return False  # no story, or an unreadable one: run() will say so
        return fingerprint_ok(
            data.get("settings_used"), _fingerprint(ctx, current.sha256), _factory_fingerprint()
        )

    def run(self, ctx: StageContext) -> dict:
        try:
            text = story.load(ctx.job_dir)
        except FileNotFoundError:
            raise StageError(
                "This story job has no story text — story.txt is missing from the job folder.",
                code="story-text-missing",
            ) from None
        refusal = limits.check(text.text)
        if refusal:
            raise StageError(refusal, code="story-too-long")

        voice = ctx.settings.story.voice
        speed = float(ctx.settings.story.speed)
        if voice not in kokoro_tts.VOICE_IDS:
            raise StageError(
                f"Unknown narrator voice {voice!r}. Pick one of: {', '.join(kokoro_tts.VOICE_IDS)}.",
                code="narrator-unavailable",
            )
        synth = self._synth
        try:
            if synth is None:
                synth = kokoro_tts.KokoroSynth()
                ctx.emit(-1, "Loading the narrator (downloads ~330 MB on first use)…")
                synth.ensure(voice, lambda f, m: ctx.emit(f * 0.3, m))
            ctx.emit(0.3, f"Narrating the title in {voice}…")
            title_audio = synth.synth(text.title, voice, speed) if text.title else np.zeros(0, np.float32)
            ctx.emit(0.5, f"Narrating {text.word_count} words…")
            body_audio = synth.synth(text.body, voice, speed) if text.body else np.zeros(0, np.float32)
        except kokoro_tts.NarratorUnavailable as err:
            raise StageError(str(err), code="narrator-unavailable") from err

        if len(title_audio) + len(body_audio) == 0:
            raise StageError(
                "The narrator produced no audio for this story.", code="narration-empty",
            )
        gap = np.zeros(int(TITLE_GAP_SEC * kokoro_tts.SAMPLE_RATE), dtype=np.float32)
        parts = [title_audio, gap, body_audio] if len(title_audio) and len(body_audio) else [
            title_audio if len(title_audio) else body_audio
        ]
        samples = np.concatenate(parts)
        title_end = (len(title_audio) + (len(gap) if len(body_audio) else 0)) / kokoro_tts.SAMPLE_RATE

        ctx.emit(0.9, "Writing narration.wav…")
        out = ctx.job_dir / NARRATION_FILE
        duration = write_wav(out, samples)

        from ..jobs import queue as jobs_queue

        # The library rail and the queue show a story by its title, not by
        # its background's filename (ingest set that; this overrides it).
        jobs_queue.set_job_status(ctx.job.id, "running", title=text.title or None)
        return {
            "audio_path": str(out),
            "duration_sec": round(duration, 3),
            "title": text.title,
            "title_end_sec": round(title_end, 3),
            "word_count": text.word_count,
            "sample_rate": kokoro_tts.SAMPLE_RATE,
            "engine": type(synth).__name__,
            "settings_used": _fingerprint(ctx, text.sha256),
        }
