"""Settings contract tests.

The product promise for the configuration system is blunt: a setting the UI
exposes must actually change the output. These tests exist to catch the
opposite — a knob that serializes, round-trips, renders in the panel, and
changes nothing. Each test below moves ONE setting and asserts the pipeline
behaves differently because of it.

They are all pure logic (no media, no models, no ffmpeg), so they run in
milliseconds and can gate every future settings addition.
"""

import dataclasses
import json

import numpy as np
import pytest

from publikclip_pipeline import config
from publikclip_pipeline.candidates import curve as curve_mod
from publikclip_pipeline.candidates import windows as windows_mod
from publikclip_pipeline.camera import director
from publikclip_pipeline.camera.asd import AsdAnalysis, ScoredTrack
from publikclip_pipeline.captions import ass as ass_mod
from publikclip_pipeline.edits import timeline as timeline_mod
from publikclip_pipeline.jobs import queue
from publikclip_pipeline.scoring import rubric


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


def test_enqueue_flag_sets_the_job_letterbox_fill(capsys):
    """E6-F09's whole chain below the UI: `jobs create --letterbox-fill`
    must land on the job's settings snapshot, exactly as the deck's other
    three controls do — and without the flag the saved default governs."""
    from publikclip_pipeline import cli

    assert cli.main(["jobs", "create", "C:/nowhere/a.mp4", "--letterbox-fill", "blur"]) == 0
    job_id = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["job_id"]
    saved = config.Settings.from_json(json.loads(queue.get_job(job_id).settings_json))
    assert saved.camera.letterbox_fill == "blur"

    assert cli.main(["jobs", "create", "C:/nowhere/b.mp4"]) == 0
    job_id = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["job_id"]
    saved = config.Settings.from_json(json.loads(queue.get_job(job_id).settings_json))
    assert saved.camera.letterbox_fill == "black"


# ---------------------------------------------------------------------------
# Persistence


def test_adding_a_new_setting_does_not_discard_existing_work():
    """The scenario this protects: a job finishes an hour of work, a new
    setting ships, and resume throws that hour away because the old
    checkpoint lacks a key it could not possibly have had. A key missing
    from the stored fingerprint is compared against the factory default —
    untouched default keeps the work, a real change still invalidates."""
    stored = {"clips": {"min_len": 15.0}}                 # written before 'scenes' existed
    factory = {"clips": {"min_len": 15.0}, "scenes": {"fast": True}}

    same = {"clips": {"min_len": 15.0}, "scenes": {"fast": True}}
    assert queue.fingerprint_ok(stored, same, factory) is True

    changed_new = {"clips": {"min_len": 15.0}, "scenes": {"fast": False}}
    assert queue.fingerprint_ok(stored, changed_new, factory) is False

    changed_old = {"clips": {"min_len": 30.0}, "scenes": {"fast": True}}
    assert queue.fingerprint_ok(stored, changed_old, factory) is False


def test_missing_fingerprint_is_not_trusted():
    """No fingerprint at all (a checkpoint from before fingerprinting) must
    re-run rather than be assumed fresh."""
    assert queue.fingerprint_ok(None, {"a": 1}, {"a": 1}) is False


def test_clip_edit_round_trips_every_field():
    """A ClipEdit field that to_json writes but from_json forgets is a setting
    that silently resets on reload — this caught exactly that for
    gameplay_amount. Compare the whole dict rather than named fields, so a
    future field can't be added without being round-tripped."""
    from publikclip_pipeline.edits.timeline import ClipEdit

    edit = ClipEdit(
        start=1.0, end=9.0, caption_preset="beast", camera_mode="pan",
        gameplay_amount=0.65, title="a chosen title",
        title_variants=[{"text": "another", "style": "direct"}],
        remove_dead_space=True, disabled_cuts=[1, 3],
    )
    assert ClipEdit.from_json(edit.to_json()).to_json() == edit.to_json()


def test_settings_update_reaches_both_stores():
    """A job holds its settings twice: the DB row (read by run_stages) and
    <job_dir>/settings.json (read by the per-clip edit path). The bug this
    guards: restyle updated only the DB, so clips re-rendered with the new
    settings while the clip editor still showed — and re-rendered with — the
    old ones, silently reverting any clip touched afterwards."""
    settings = config.Settings()
    job = queue.create_job("file", "x.mp4", json.dumps(settings.to_json()))

    settings.camera.gameplay_amount = 1.0
    settings.caption_preset = "beast"
    updated = queue.update_settings(job.id, json.dumps(settings.to_json()))

    # the DB row
    assert updated is not None
    from_db = config.Settings.from_json(json.loads(updated.settings_json))
    assert from_db.camera.gameplay_amount == 1.0
    assert from_db.caption_preset == "beast"

    # the job-dir snapshot the clip editor actually reads
    on_disk = config.Settings.from_json(
        json.loads((job.dir / "settings.json").read_text(encoding="utf-8"))
    )
    assert on_disk.camera.gameplay_amount == 1.0
    assert on_disk.caption_preset == "beast"


def test_every_settings_group_is_read_by_the_pipeline():
    """Guards the bug this test was written after: PacingSettings was fully
    plumbed — dataclass, JSON, UI schema, a passing unit test of the function
    that consumes it — and the pipeline still never passed it, so the whole
    Pacing group silently did nothing.

    A unit test that calls the consumer directly cannot catch that. This one
    greps for a real read of each group somewhere in the package, which is
    crude but catches an entire group going dark.
    """
    import re
    import typing
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "publikclip_pipeline"
    sources = [
        p.read_text(encoding="utf-8")
        for p in pkg.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "config.py"
    ]
    blob = "\n".join(sources)

    # get_type_hints, not f.type. config.py has `from __future__ import
    # annotations`, so f.type is the STRING "CameraSettings" and
    # is_dataclass() on it is always False — the discovery half never fired
    # and only a hardcoded ten-name tuple was ever checked. The test written
    # to catch a newly added group going dark could not see a newly added
    # group at all. `descriptions` was already sitting outside that tuple; it
    # happens to be read at cli.py:309, so it was luck, not the guard. (T-22)
    hints = typing.get_type_hints(config.Settings)
    groups = [
        f.name
        for f in dataclasses.fields(config.Settings)
        if dataclasses.is_dataclass(hints[f.name])
    ]
    assert len(groups) >= 11, (
        f"Only {len(groups)} dataclass groups discovered ({groups}). If this "
        "dropped, resolution is broken again and the test is passing vacuously."
    )
    unread = [g for g in groups if not re.search(rf"settings\.{g}\b", blob)]
    assert unread == [], f"settings groups nothing in the pipeline reads: {unread}"


def test_ui_schema_matches_the_settings_tree():
    """The panel is generated from settings_schema.py. This test is the thing
    that stops it drifting: a control with no backing field (a fake setting)
    or a field with no control (a knob the user was promised but can't reach)
    both fail here."""
    from publikclip_pipeline import settings_schema

    assert settings_schema.validate_schema() == []


def test_every_schema_field_has_help_text():
    """The brief was explicit: each setting explains what it does."""
    from publikclip_pipeline import settings_schema

    missing = []
    for group in settings_schema.GROUPS:
        for f in group.get("fields", []):
            if len(f.get("help", "")) < 20:
                missing.append(f["key"])
    for f in settings_schema.CAPTION_FIELDS:
        if len(f.get("help", "")) < 20:
            missing.append(f"caption.{f['key']}")
    assert missing == []


def test_caption_colours_round_trip_through_the_ui_format():
    """The panel edits hex; ASS stores &HAABBGGRR byte-reversed with alpha.
    A lossy conversion here would silently recolour every caption."""
    for name, preset in ass_mod.PRESETS.items():
        for field in ass_mod._COLOR_FIELDS:
            original = getattr(preset, field)
            back = ass_mod.hex_to_ass(ass_mod.ass_to_hex(original), original)
            assert back == original.upper(), f"{name}.{field}"


def test_preset_from_ui_keeps_font_file_in_sync():
    """Picking a font in the panel must also switch the bundled font file,
    or libass silently falls back to a different face at render time."""
    patch = ass_mod.preset_from_ui("classic", {"font": "Anton"})
    assert patch["font_file"] == "Anton-Regular.ttf"


def test_settings_round_trip_is_lossless():
    s = config.Settings()
    assert config.Settings.from_json(s.to_json()).to_json() == s.to_json()


def test_pre_refactor_settings_json_still_loads():
    """A job created before the settings tree existed must resume, picking up
    defaults for every new group instead of raising."""
    old = {
        "camera": {"speaker_change": "cut", "punch_in": True},
        "lufs_target": -14.0,
        "llm_mode": "gemini",
        "caption_preset": "beast",
    }
    s = config.Settings.from_json(old)
    assert s.caption_preset == "beast"
    assert s.clips.min_len == 15.0          # new group defaulted
    assert s.retention.punch_zoom == 1.12


def test_unknown_keys_are_ignored_not_fatal():
    """Settings written by a NEWER build must not break an older one."""
    s = config.Settings.from_json(
        {"clips": {"min_len": 9.0, "invented_later": True}, "brand_new_group": {"x": 1}}
    )
    assert s.clips.min_len == 9.0


def test_global_defaults_seed_new_settings():
    s = config.Settings()
    s.clips.target_len = 21.0
    s.camera.gameplay_amount = 1.0
    config.save_defaults(s)
    loaded = config.load_defaults()
    assert loaded.clips.target_len == 21.0
    assert loaded.camera.gameplay_amount == 1.0


def test_corrupt_defaults_file_falls_back_instead_of_crashing():
    config.ensure_home()
    config.settings_path().write_text("{not json", encoding="utf-8")
    assert config.load_defaults().clips.min_len == 15.0


# ---------------------------------------------------------------------------
# Clips: length settings must change which windows are produced


def _segments(n=40, step=5.0):
    return [{"start": i * step, "end": i * step + step} for i in range(n)]


def test_target_len_changes_window_length():
    segs = _segments()
    starts, ends = windows_mod.sentence_boundaries(segs)
    short = windows_mod.window_around(
        100, np.zeros(200), starts, ends, 200.0,
        config.ClipSettings(min_len=5.0, max_len=90.0, target_len=20.0),
    )
    long = windows_mod.window_around(
        100, np.zeros(200), starts, ends, 200.0,
        config.ClipSettings(min_len=5.0, max_len=90.0, target_len=60.0),
    )
    assert short is not None and long is not None
    assert (long[1] - long[0]) > (short[1] - short[0])


def test_max_len_caps_window():
    segs = _segments()
    starts, ends = windows_mod.sentence_boundaries(segs)
    win = windows_mod.window_around(
        100, np.zeros(200), starts, ends, 200.0,
        config.ClipSettings(min_len=5.0, max_len=25.0, target_len=60.0),
    )
    assert win is not None
    assert win[1] - win[0] <= 25.0 + 1e-6


def test_max_candidates_limits_pool():
    cands = [
        windows_mod.Candidate(start=i * 100.0, end=i * 100.0 + 30.0, peak_time=i * 100.0, curve_score=1.0)
        for i in range(20)
    ]
    assert len(windows_mod.dedupe(cands, 0.55, max_candidates=5)) == 5
    assert len(windows_mod.dedupe(cands, 0.55, max_candidates=12)) == 12


# ---------------------------------------------------------------------------
# Interest curve weights must change the curve


def test_curve_weights_shift_the_peak():
    
    channels = {
        "dynamics": np.concatenate([np.ones(5), np.zeros(5)]),
        "lexical": np.concatenate([np.zeros(5), np.ones(5)]),
    }
    dyn_heavy, _ = curve_mod.interest_curve(channels, {"dynamics": 0.9, "lexical": 0.1})
    lex_heavy, _ = curve_mod.interest_curve(channels, {"dynamics": 0.1, "lexical": 0.9})
    assert int(np.argmax(dyn_heavy)) < 5   # first half wins
    assert int(np.argmax(lex_heavy)) >= 5  # second half wins


def test_curve_weights_default_when_not_overridden():
    channels = {"dynamics": np.ones(4)}
    a, _ = curve_mod.interest_curve(channels)
    b, _ = curve_mod.interest_curve(channels, {})
    assert np.allclose(a, b)


# ---------------------------------------------------------------------------
# Scoring weights must change the score


def _subscores():
    return {"hook": 9.0, "funniness": 1.0, "shock": 5.0, "curiosity_gap": 5.0, "value": 5.0}


def test_platform_weights_change_the_score():
    hook_heavy = config.ScoringSettings(
        platform_weights={"tiktok": {"hook": 1.0, "funniness": 0.0, "shock": 0.0, "curiosity_gap": 0.0, "value": 0.0}}
    )
    funny_heavy = config.ScoringSettings(
        platform_weights={"tiktok": {"hook": 0.0, "funniness": 1.0, "shock": 0.0, "curiosity_gap": 0.0, "value": 0.0}}
    )
    a, _ = rubric.composite(_subscores(), 0.5, None, None, scoring=hook_heavy)
    b, _ = rubric.composite(_subscores(), 0.5, None, None, scoring=funny_heavy)
    assert a["tiktok"] > b["tiktok"]  # the clip has a strong hook, weak humor


def test_t0_weight_changes_curve_influence():
    low = config.ScoringSettings(t0_weight=0.0)
    high = config.ScoringSettings(t0_weight=0.9)
    a, _ = rubric.composite(_subscores(), 1.0, None, None, scoring=low)
    b, _ = rubric.composite(_subscores(), 1.0, None, None, scoring=high)
    assert a["tiktok"] != b["tiktok"]


def test_composite_without_settings_matches_builtin_defaults():
    """Omitting settings must reproduce the pre-settings behavior exactly."""
    explicit = config.ScoringSettings()
    a, _ = rubric.composite(_subscores(), 0.4, None, None)
    b, _ = rubric.composite(_subscores(), 0.4, None, None, scoring=explicit)
    assert a == b


# ---------------------------------------------------------------------------
# Captions: preset edits must reach the rendered ASS document


def _words():
    return [ass_mod.Word("one", 0.0, 0.4), ass_mod.Word("two", 0.4, 0.8)]


def test_caption_override_changes_ass_output():
    plain = ass_mod.build_ass(_words(), [], preset_name="classic")
    big = ass_mod.build_ass(_words(), [], preset_name="classic", overrides={"size": 140})
    assert ",140," in big and ",140," not in plain


def test_saved_preset_edit_is_picked_up_by_renderer():
    """Editing a built-in preset in the settings panel must change renders
    without the job asking for an override."""
    config.save_caption_presets({"classic": {"uppercase": True}})
    doc = ass_mod.build_ass(_words(), [], preset_name="classic")
    assert "ONE" in doc


def test_job_override_beats_saved_preset_edit():
    config.save_caption_presets({"classic": {"size": 100}})
    preset = ass_mod.resolve_preset("classic", {"size": 40})
    assert preset.size == 40


def test_custom_preset_name_falls_back_to_classic_shape():
    config.save_caption_presets({"my-style": {"size": 66, "uppercase": True}})
    preset = ass_mod.resolve_preset("my-style")
    assert preset.size == 66 and preset.uppercase is True
    assert "my-style" in ass_mod.preset_names()


def test_bad_preset_values_are_ignored_not_fatal():
    config.save_caption_presets({"classic": {"size": "enormous", "nonsense": 1}})
    preset = ass_mod.resolve_preset("classic")
    assert preset.size == ass_mod.PRESETS["classic"].size


def test_words_per_caption_changes_chunking():
    words = [ass_mod.Word(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(6)]
    assert [len(c.words) for c in ass_mod.chunk_words(words, max_words=2)] == [2, 2, 2]
    assert [len(c.words) for c in ass_mod.chunk_words(words, max_words=6)] == [6]


# ---------------------------------------------------------------------------
# Camera / retention: the two formerly-dead settings must now do something


def _analysis(n=250, centre=0.3):
    track = ScoredTrack(
        start=0, centres=[centre] * n, centres_y=[0.5] * n,
        areas=[0.04] * n, scores=[2.0] * n,
    )
    return AsdAnalysis(tracks=[track], frame_count=n, scene_cuts=[], fps=25)


class _Cam:
    """Stands in for Settings: camera group + retention group."""

    def __init__(self, **kw):
        self.camera = config.CameraSettings(**{k: v for k, v in kw.items() if hasattr(config.CameraSettings, k) or k in config.CameraSettings().__dict__})
        self.retention = config.RetentionSettings()


def _traj(cam, analysis=None, timeline=None, dynamics=None):
    return director.build_trajectory(
        analysis or _analysis(), [], timeline or [],
        dynamics if dynamics is not None else np.zeros(0), 0.1,
        0.0, 10.0, 1920, 1080, cam,
    )


def test_punch_zoom_setting_changes_the_envelope():
    """punch_zoom=1.0 must flatten punch-ins without disabling the feature."""
    punches = [director.Punch(start=1.0, trigger="laugh")]
    strong = director.punch_envelope(200, 25, punches, zoom=1.30)
    off = director.punch_envelope(200, 25, punches, zoom=1.0)
    assert strong.max() > 1.25
    assert np.allclose(off, 1.0)


def test_punch_spacing_setting_thins_punches():
    timeline = [
        {"type": "laugh", "start": float(t), "end": float(t) + 0.5, "confidence": 0.9}
        for t in range(2, 40, 2)
    ]
    tight = director.punch_schedule(timeline, np.zeros(0), 0.1, 0.0, 60.0, min_spacing_s=1.0)
    loose = director.punch_schedule(timeline, np.zeros(0), 0.1, 0.0, 60.0, min_spacing_s=12.0)
    assert len(tight) > len(loose)


def test_seconds_per_punch_caps_frequency():
    timeline = [
        {"type": "laugh", "start": float(t), "end": float(t) + 0.5, "confidence": 0.9}
        for t in range(2, 60, 4)
    ]
    dense = director.punch_schedule(timeline, np.zeros(0), 0.1, 0.0, 60.0, seconds_per_punch=4.0)
    sparse = director.punch_schedule(timeline, np.zeros(0), 0.1, 0.0, 60.0, seconds_per_punch=30.0)
    assert len(dense) > len(sparse)


def test_deadzone_frac_holds_the_crop_still():
    """A subject drifting slowly across frame must move the crop less when the
    deadzone is wide. (A tiny ±1% jitter is a bad probe here — the savgol
    tripod lock already absorbs that entirely, so both settings would read
    0.0 and the test would prove nothing.)"""
    n = 200
    analysis = _analysis(n)
    analysis.tracks[0].centres = list(np.linspace(0.2, 0.8, n))  # slow pan across

    held = _traj(_Cam(speaker_change="locked", punch_in=False, deadzone_frac=0.30), analysis)
    free = _traj(_Cam(speaker_change="locked", punch_in=False, deadzone_frac=0.0), analysis)

    held_spread = max(f[0] for f in held.frames) - min(f[0] for f in held.frames)
    free_spread = max(f[0] for f in free.frames) - min(f[0] for f in free.frames)
    assert free_spread > 0, "control case must actually move, or the test is vacuous"
    assert held_spread < free_spread


def test_pan_duration_changes_smoothing_in_pan_mode():
    """A longer pan_duration_s must glide more slowly between speakers."""
    n = 200
    analysis = _analysis(n)
    analysis.tracks[0].centres = [0.2] * (n // 2) + [0.8] * (n // 2)

    quick = _traj(_Cam(speaker_change="pan", punch_in=False, deadzone_frac=0.0, pan_duration_s=0.2), analysis)
    slow = _traj(_Cam(speaker_change="pan", punch_in=False, deadzone_frac=0.0, pan_duration_s=2.0), analysis)

    quick_step = max(abs(np.diff([f[0] for f in quick.frames])))
    slow_step = max(abs(np.diff([f[0] for f in slow.frames])))
    assert slow_step < quick_step  # slower pan = smaller per-frame movement


# ---------------------------------------------------------------------------
# Pacing: dead-space settings must change the detected cuts


def _pacing_words():
    return [
        {"word": "hello", "start": 0.0, "end": 0.5},
        {"word": "world", "start": 3.0, "end": 3.5},  # 2.5 s gap
    ]


def test_min_cut_gap_controls_what_counts_as_dead_space():
    strict = timeline_mod.detect_dead_space(
        _pacing_words(), [], 0.0, 5.0, config.PacingSettings(min_cut_gap=0.2)
    )
    lax = timeline_mod.detect_dead_space(
        _pacing_words(), [], 0.0, 5.0, config.PacingSettings(min_cut_gap=10.0)
    )
    assert any(not c["kept"] for c in strict)
    assert not any(not c["kept"] for c in lax)  # nothing is long enough to cut


def test_breath_pad_changes_cut_width():
    tight = timeline_mod.detect_dead_space(
        _pacing_words(), [], 0.0, 5.0, config.PacingSettings(breath_pad=0.05)
    )
    padded = timeline_mod.detect_dead_space(
        _pacing_words(), [], 0.0, 5.0, config.PacingSettings(breath_pad=0.5)
    )
    tight_cut = next(c for c in tight if not c["kept"])
    padded_cut = next(c for c in padded if not c["kept"])
    assert (tight_cut["end"] - tight_cut["start"]) > (padded_cut["end"] - padded_cut["start"])


def test_per_clip_pacing_override_beats_the_job_setting():
    """The clip editor tunes dead space per clip. An override must win over
    the job's value, and an absent key must inherit it — otherwise the
    editor's sliders either do nothing or wipe the job's settings."""
    settings = config.Settings()
    settings.pacing.min_cut_gap = 0.5
    settings.pacing.breath_pad = 0.15

    edit = timeline_mod.ClipEdit(start=0.0, end=5.0, pacing={"min_cut_gap": 2.0})
    resolved = timeline_mod.resolve_pacing(settings, edit)
    assert resolved.min_cut_gap == 2.0   # overridden
    assert resolved.breath_pad == 0.15   # inherited


def test_resolve_pacing_without_an_edit_is_the_job_setting():
    settings = config.Settings()
    settings.pacing.min_cut_gap = 0.9
    assert timeline_mod.resolve_pacing(settings, None).min_cut_gap == 0.9


def test_per_clip_pacing_survives_a_json_round_trip():
    """Overrides live in clip_edits.json; a lossy round-trip would silently
    reset the user's tuning on the next open."""
    edit = timeline_mod.ClipEdit(
        start=0.0, end=5.0,
        pacing={"min_cut_gap": 1.25},
        caption_overrides={"size": 96, "uppercase": True},
        lufs_target=-16.0,
    )
    back = timeline_mod.ClipEdit.from_json(edit.to_json())
    assert back.pacing == {"min_cut_gap": 1.25}
    assert back.caption_overrides == {"size": 96, "uppercase": True}
    assert back.lufs_target == -16.0


def test_old_clip_edits_without_overrides_still_load():
    back = timeline_mod.ClipEdit.from_json({"start": 0.0, "end": 5.0})
    assert back.pacing == {} and back.caption_overrides == {}
    assert back.lufs_target is None


def test_event_protect_window_saves_a_pause():
    events = [{"type": "laugh", "start": 3.6, "end": 3.9}]
    unprotected = timeline_mod.detect_dead_space(
        _pacing_words(), events, 0.0, 5.0, config.PacingSettings(event_protect_s=0.05)
    )
    protected = timeline_mod.detect_dead_space(
        _pacing_words(), events, 0.0, 5.0, config.PacingSettings(event_protect_s=5.0)
    )
    assert any(not c["kept"] for c in unprotected)
    assert all(c["kept"] for c in protected)


# ---------------------------------------------------------------------------
# The runner's dependency cascade


class _Recorder(queue.Stage):
    schema_version = 1

    def __init__(self, name, fresh=True):
        self.name = name
        self.runs = 0
        self._fresh = fresh

    def run(self, ctx):
        self.runs += 1
        return {"runs": self.runs}

    def artifacts_ok(self, ctx, data):
        return self._fresh


def test_downstream_reruns_when_upstream_goes_stale():
    """The bug this prevents: an upstream stage recomputes (settings changed)
    while a downstream stage serves output derived from the OLD upstream
    data — which is what makes a real setting look like it does nothing."""
    job = queue.create_job("file", "x.mp4", json.dumps(config.Settings().to_json()))
    first = [_Recorder("a"), _Recorder("b")]
    queue.run_stages(job, first, lambda *a: None)
    assert [s.runs for s in first] == [1, 1]

    # 'a' is now stale, 'b' still claims its own artifacts are fine.
    second = [_Recorder("a", fresh=False), _Recorder("b", fresh=True)]
    queue.run_stages(job, second, lambda *a: None)
    assert second[0].runs == 1, "stale upstream stage must re-run"
    assert second[1].runs == 1, "downstream stage must follow its upstream"


def test_everything_cached_runs_nothing():
    job = queue.create_job("file", "y.mp4", json.dumps(config.Settings().to_json()))
    stages = [_Recorder("a"), _Recorder("b")]
    queue.run_stages(job, stages, lambda *a: None)
    again = [_Recorder("a"), _Recorder("b")]
    queue.run_stages(job, again, lambda *a: None)
    assert [s.runs for s in again] == [0, 0]


def test_enqueue_flags_set_the_job_ranking_mode(capsys):
    """E18-F01's chain below the UI: `jobs create --ranking on
    --ranking-count 7` lands on the job's settings snapshot; without the
    flags the group keeps its defaults, off and 5."""
    from publikclip_pipeline import cli

    assert cli.main([
        "jobs", "create", "C:/nowhere/a.mp4", "--ranking", "on", "--ranking-count", "7",
    ]) == 0
    job_id = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["job_id"]
    saved = config.Settings.from_json(json.loads(queue.get_job(job_id).settings_json))
    assert saved.ranking.enabled is True and saved.ranking.count == 7

    assert cli.main(["jobs", "create", "C:/nowhere/b.mp4"]) == 0
    job_id = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["job_id"]
    saved = config.Settings.from_json(json.loads(queue.get_job(job_id).settings_json))
    assert saved.ranking.enabled is False and saved.ranking.count == 5


def test_resume_ranking_flags_reach_the_job_snapshot(monkeypatch):
    """`resume --ranking off` must be able to turn the mode OFF, which is
    why the flag is on|off rather than a store_true: a bare presence check
    cannot say "off", and cmd_resume's guard has to see the flag at all —
    a flag it does not list is silently inert (the letterbox_fill flag is
    in exactly that state today, and has its own task)."""
    from publikclip_pipeline import cli

    settings = config.Settings()
    settings.ranking.enabled = True
    job = queue.create_job("file", "C:/nowhere/c.mp4", json.dumps(settings.to_json()))
    monkeypatch.setattr(cli, "_execute", lambda job, jsonl: 0)

    assert cli.main(["resume", job.id, "--ranking", "off"]) == 0
    saved = config.Settings.from_json(json.loads(queue.get_job(job.id).settings_json))
    assert saved.ranking.enabled is False

    assert cli.main(["resume", job.id, "--ranking-count", "3"]) == 0
    saved = config.Settings.from_json(json.loads(queue.get_job(job.id).settings_json))
    assert saved.ranking.count == 3 and saved.ranking.enabled is False  # untouched by the count flag


def test_resume_letterbox_fill_flag_reaches_the_job_snapshot(monkeypatch):
    """`resume --letterbox-fill blur` was parsed, applied by
    _apply_setting_flags, and then never reached the job: cmd_resume's
    guard did not list the flag, so the settings were never re-saved — a
    shipped flag that did nothing (§5.2). The snapshot must change."""
    from publikclip_pipeline import cli

    settings = config.Settings()
    assert settings.camera.letterbox_fill == "black"
    job = queue.create_job("file", "C:/nowhere/d.mp4", json.dumps(settings.to_json()))
    monkeypatch.setattr(cli, "_execute", lambda job, jsonl: 0)

    assert cli.main(["resume", job.id, "--letterbox-fill", "blur"]) == 0
    saved = config.Settings.from_json(json.loads(queue.get_job(job.id).settings_json))
    assert saved.camera.letterbox_fill == "blur"
