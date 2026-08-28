"""T-39: the scoring stage's circuit breaker and what zero scores means.

The defect: a total LLM outage failed all 26 moments one by one — each with
its own 5-attempt backoff ladder — and the run carried on for ten minutes to
produce nothing. Skipping ONE failed moment is §5.9 working; skipping all of
them is a failed run wearing a success. These tests pin the two nets: a run
stops after CONSECUTIVE_FAILURE_LIMIT consecutive total failures with a
message that names the cause, and a run that scored nothing because of LLM
failures says so instead of blaming the video.
"""

import json

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.jobs.queue import StageError
from publikclip_pipeline.scoring import llm as llm_mod
from publikclip_pipeline.scoring import rubric
from publikclip_pipeline.scoring import stage as scoring_stage


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


T1_OK = {
    "hook": 6, "hook_type": "question", "funniness": 2, "punchline_index": 0,
    "shock": 1, "curiosity_gap": 3, "value": 4, "self_contained": True,
    "bait_phrases": [], "summary": "a moment",
}


class ScriptedClient:
    """Fails or answers T1 calls per the script; every other call (the music
    brief) succeeds, so a completed run exercises the full stage."""

    backend = "scripted"  # not "gemini": keeps the T2 vision pass off
    model = "scripted-model"

    def __init__(self, script):
        self.script = list(script)
        self.t1_calls = 0

    def generate_json(self, prompt, schema, images=None):
        if schema is not rubric.T1_SCHEMA:
            return {"queries": []}
        self.t1_calls += 1
        step = self.script.pop(0) if self.script else "ok"
        if step == "fail":
            raise llm_mod.LlmError(
                "Gemini call failed after 5 attempts: 503 UNAVAILABLE", fatal=False
            )
        return dict(T1_OK)


class Ctx:
    def __init__(self, job_dir, prior, settings):
        self.job_dir = job_dir
        self.prior = prior
        self.settings = settings
        self.messages = []

    def emit(self, fraction, message, stage=""):
        self.messages.append(message)


def make_ctx(tmp_path, n_candidates):
    curves = tmp_path / "curves.json"
    curves.write_text(json.dumps({"arousal": [], "arousal_grid_sec": 0.5}), encoding="utf-8")
    settings = config.Settings()
    settings.clips.min_words = 0  # transcripts are not what these tests are about
    prior = {
        "ingest": {"probe": {"duration_sec": 600.0}, "heatmap": None, "media_path": "x.mp4"},
        "diarize": {"segments": []},
        "events": {"timeline": [], "curves_path": str(curves)},
        "candidates": {
            "candidates": [
                {"start": i * 20.0, "end": i * 20.0 + 15.0, "curve_score": 0.5, "channel_scores": {}}
                for i in range(n_candidates)
            ]
        },
    }
    return Ctx(tmp_path, prior, settings)


def run_stage(monkeypatch, ctx, client):
    monkeypatch.setattr(llm_mod, "make_client", lambda mode, model=None: client)
    return scoring_stage.ScoreStage().run(ctx)


def test_consecutive_failures_stop_the_stage_and_name_the_cause(tmp_path, monkeypatch):
    client = ScriptedClient(["fail"] * 26)
    ctx = make_ctx(tmp_path, 26)
    with pytest.raises(StageError) as err:
        run_stage(monkeypatch, ctx, client)
    # The ten-minute version of this outage burned all 26 moments; the
    # breaker must spend exactly the limit, not one moment more.
    assert client.t1_calls == scoring_stage.CONSECUTIVE_FAILURE_LIMIT
    text = str(err.value)
    assert "in a row" in text
    assert "503" in text  # the actual cause survives into the message
    assert "resume" in text  # ...and so does the way forward


def test_a_success_resets_the_breaker(tmp_path, monkeypatch):
    # Three failures, a recovery, three more: never four CONSECUTIVE, so the
    # run must complete — killing it here would punish exactly the transient
    # blip the per-moment skip exists to absorb.
    client = ScriptedClient(["fail", "fail", "fail", "ok", "fail", "fail", "fail", "ok"])
    ctx = make_ctx(tmp_path, 8)
    result = run_stage(monkeypatch, ctx, client)
    assert client.t1_calls == 8
    assert result["scored_count"] == 2  # the failures were still skipped, §5.9
    assert result["model"] == "scripted-model"


def test_zero_scores_from_llm_failures_blames_the_service_not_the_video(tmp_path, monkeypatch):
    # Fewer failing moments than the breaker limit, so the loop ends with
    # nothing scored: the old message here was "No candidate produced a
    # scoreable transcript", which points a user at their video when the
    # actual problem is the service.
    client = ScriptedClient(["fail"] * 3)
    ctx = make_ctx(tmp_path, 3)
    with pytest.raises(StageError) as err:
        run_stage(monkeypatch, ctx, client)
    text = str(err.value)
    assert "transcript" not in text
    assert "all 3" in text
    assert "503" in text


def test_no_transcript_message_survives_for_the_quiet_video_case(tmp_path, monkeypatch):
    # No LLM failures, nothing above min_words: the original message is
    # still the right one for a genuinely unscoreable video.
    client = ScriptedClient([])
    ctx = make_ctx(tmp_path, 2)
    ctx.settings.clips.min_words = 20  # empty segments -> every window gated
    with pytest.raises(StageError) as err:
        run_stage(monkeypatch, ctx, client)
    assert "scoreable transcript" in str(err.value)
    assert client.t1_calls == 0
