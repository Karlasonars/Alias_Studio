"""E18 — the ranking video. Pure tests for the overlay and its geometry, and
synthetic-ffmpeg fixtures (the way test_render_smoke does it, §3) for the
montage itself: the segments concatenate exactly, the list is in the
pixels, and the checkpoint the stage writes is the one artifacts_ok will
accept — and reject, once the mode or the count changes."""

import json
import subprocess
from pathlib import Path

import pytest

from publikclip_pipeline import config
from publikclip_pipeline.captions import ass as ass_mod
from publikclip_pipeline.captions import ranking as overlay
from publikclip_pipeline.render import ffmpeg_bin, ranking, renderer
from publikclip_pipeline.render import stage as render_stage
from publikclip_pipeline.scoring import llm as llm_mod

# ---------------------------------------------------------------------------
# Play order and geometry — pure


def test_play_order_is_a_countdown():
    # Rank N first, rank 1 last: the list fills from the bottom and the top
    # slot is the last reveal (D-17).
    assert overlay.play_order(5) == [4, 3, 2, 1, 0]
    assert overlay.play_order(1) == [0]
    assert overlay.play_order(0) == []


@pytest.mark.parametrize(
    "bar,count,boxed,line",
    [
        (656, 5, False, 70),   # gameplay framing, 16:9 source: room to spare
        (656, 8, False, 49),   # the most the deck offers still fits the bar
        (498, 5, False, 46),   # half-way dial: lines shrink toward the floor
        (498, 8, True, overlay.LINE_BOXED),   # ...and past it the list goes over the picture
        (336, 5, True, overlay.LINE_BOXED),
        (0, 5, True, overlay.LINE_BOXED),     # podcast framing: no bar at all
    ],
)
def test_band_fits_the_bar_or_goes_over_the_picture(bar, count, boxed, line):
    band = overlay.band_for([bar], count)
    assert band.boxed is boxed
    assert band.line_h == line
    assert band.top == ass_mod.TOP_SAFE_PX
    if not boxed:
        # inside the bar, under the top safe zone — never over the picture
        assert band.bottom <= bar


def test_the_tightest_bar_decides_for_every_segment():
    """One band for the whole montage: a single podcast-framed segment
    forces the boxed layout for all of them, and a shorter bar shrinks the
    lines for all of them. The list must not move at a cut."""
    assert overlay.band_for([656, 0], 5).boxed is True
    assert overlay.band_for([656, 498], 5).line_h == 46


def _entries(doc: str) -> list[tuple[str, str]]:
    """(tags, number) per RankEntry dialogue line, in row order."""
    out = []
    for line in doc.splitlines():
        if ",RankEntry," not in line:
            continue
        text = line.split(",", 8)[8]  # Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Text
        tags, number = text.rsplit("}", 1)
        out.append((tags + "}", number))
    return out


def test_overlay_reveals_in_play_order_not_top_down():
    preset = ass_mod.PRESETS["classic"]
    band = overlay.band_for([656], 3)
    # segment 0 plays rank 3: only the bottom entry is lit
    first = _entries(overlay.overlay_events(preset, band, 0, 4.0))
    assert [n for _, n in first] == ["1", "2", "3"]
    assert "\\alpha&H80&" in first[0][0] and "\\alpha&H80&" in first[1][0]  # still to come
    assert preset.active in first[2][0] and "\\fad" in first[2][0]           # playing now
    # last segment plays rank 1: 3 and 2 are played, 1 is now
    last = _entries(overlay.overlay_events(preset, band, 2, 4.0))
    assert preset.active in last[0][0] and "\\fad" in last[0][0]
    assert "\\alpha" not in last[1][0] and "\\alpha" not in last[2][0]
    assert "\\fad" not in last[1][0] and "\\fad" not in last[2][0]


def test_overlay_is_static_for_the_whole_segment():
    """Every overlay line spans the entire segment — the only motion is the
    fade on the entry that just started. That is what lets the list ride
    each segment's own ASS and the montage be a remux, not an encode."""
    preset = ass_mod.PRESETS["beast"]
    band = overlay.band_for([656], 4)
    doc = overlay.overlay_events(preset, band, 1, 12.5)
    lines = [ln for ln in doc.splitlines() if ln.startswith("Dialogue:")]
    assert len(lines) == 1 + 4  # title + entries; no band drawing in a real bar
    for ln in lines:
        _, start, end = ln.split(",", 3)[:3]
        assert start == "0:00:00.00" and end == "0:00:12.50"
    assert doc.count("\\fad(") == 1
    assert "TOP 4" in doc  # beast uppercases; the title is already uppercase


def test_overlay_draws_a_backing_band_only_over_the_picture():
    preset = ass_mod.PRESETS["classic"]
    boxed = overlay.overlay_events(preset, overlay.band_for([0], 5), 0, 4.0)
    assert ",RankBand," in boxed and "\\p1" in boxed and overlay.BOX_ALPHA in boxed
    clear = overlay.overlay_events(preset, overlay.band_for([656], 5), 0, 4.0)
    assert ",RankBand," not in clear


def test_build_ass_splices_the_overlay_and_is_unchanged_without_it():
    words = [ass_mod.Word("hello", 0.0, 0.4)]
    preset = ass_mod.PRESETS["classic"]
    band = overlay.band_for([656], 2)
    doc = ass_mod.build_ass(
        words, [], extra_styles=overlay.overlay_styles(preset, band),
        extra_events=overlay.overlay_events(preset, band, 0, 2.0),
    )
    styles, events = doc.split("[Events]")
    assert "Style: RankTitle," in styles and "Style: RankEntry," in styles
    assert ",RankEntry," in events and "Dialogue: 0," in events  # captions still there
    # A plain clip's document keeps its exact former shape: styles, a blank
    # line, then [Events].
    plain = ass_mod.build_ass(words, [])
    assert "Rank" not in plain
    assert ",1\n\n[Events]\n" in plain


# ---------------------------------------------------------------------------
# Which clips, and which fills — pure


def test_ranked_clips_takes_the_top_n_that_have_a_camera_pass(tmp_path):
    clips = [{"score": 90}, {"score": 80}, {"score": 70}, {"score": 60}]
    trajectories = {}
    for i in (0, 2, 3):
        p = tmp_path / f"t{i}.json"
        p.write_text("{}", encoding="utf-8")
        trajectories[str(i)] = str(p)
    trajectories["1"] = str(tmp_path / "missing.json")
    assert ranking.ranked_clips(clips, trajectories, 2) == [0, 2]
    assert ranking.ranked_clips(clips, trajectories, 5) == [0, 2, 3]


def test_fill_keys_follow_the_output_unit():
    clip_mode = {"outputs": [{"clip": 0}, {"clip": 3}]}
    assert render_stage._fill_keys(clip_mode) == ["0", "3"]
    montage = {"outputs": [{"clip": 0, "montage": True}], "ranking": {"order": [2, 1, 0]}}
    assert render_stage._fill_keys(montage) == ["2", "1", "0"]


def test_edge_fade_is_absent_from_a_plain_clip_and_present_in_a_segment(tmp_path, monkeypatch):
    """Zero fade adds no filter: a standalone clip's -af is exactly the
    loudnorm it always was, so clip-mode renders stay byte-identical."""
    seen: list[list[str]] = []

    class Done:
        returncode = 0
        stderr = ""

    # No ffmpeg involved: the encoder probe and the binary lookup are pinned
    # so the only subprocess call left is the render itself.
    monkeypatch.setattr(renderer, "video_encoder_args", lambda hardware: ["-c:v", "libx264"])
    monkeypatch.setattr(renderer.ffmpeg_bin, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(renderer.subprocess, "run", lambda args, **kw: seen.append(args) or Done())
    traj = {"fps": 25, "frames": [[0, 0, 405, 720]]}
    renderer.render_clip("src.mp4", tmp_path / "a.mp4", 0.0, 4.0, traj, None, None)
    renderer.render_clip("src.mp4", tmp_path / "b.mp4", 0.0, 4.0, traj, None, None, edge_fade_s=0.015)
    plain = seen[-2][seen[-2].index("-af") + 1]
    faded = seen[-1][seen[-1].index("-af") + 1]
    assert plain.startswith("loudnorm=") and "afade" not in plain
    assert faded.startswith(plain) and faded.count("afade=") == 2


# ---------------------------------------------------------------------------
# The montage, through the stage, on a synthetic source


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    src = tmp_path_factory.mktemp("src") / "src.mp4"
    subprocess.run(
        [
            ffmpeg_bin.ffmpeg(), "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=20",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(src),
        ],
        check=True, timeout=300,
    )
    return src


def _probe(path: Path) -> dict:
    proc = subprocess.run(
        [
            ffmpeg_bin.ffprobe(), "-v", "error", "-count_frames", "-print_format", "json",
            "-show_streams", str(path),
        ],
        capture_output=True, text=True, timeout=300,
    )
    streams = json.loads(proc.stdout or "{}").get("streams", [])
    video = next(s for s in streams if s["codec_type"] == "video")
    audio = next(s for s in streams if s["codec_type"] == "audio")
    return {"video": video, "audio": audio}


class FakeJob:
    def __init__(self, path):
        self.dir = path


class FakeCtx:
    def __init__(self, job_dir, settings, prior):
        self.job = FakeJob(job_dir)
        self.settings = settings
        self.prior = prior
        self.messages: list[str] = []

    @property
    def job_dir(self):
        return self.job.dir

    def emit(self, fraction, message, stage=""):
        self.messages.append(message)


def _seed(job_dir: Path, source: Path, windows, content_box) -> dict:
    """A finished job's prior stages, synthetic: N clips over `source`, one
    trajectory each with the given content box (full frame → a real bar,
    tight 9:16 → none), words every half second, one laugh."""
    job_dir.mkdir(parents=True, exist_ok=True)
    curves = job_dir / "curves.json"
    curves.write_text(json.dumps({"rms": [0.2] * 200, "grid_sec": 0.1}), encoding="utf-8")
    clips = []
    trajectories = {}
    for i, (start, end) in enumerate(windows):
        clips.append({
            "start": start, "end": end, "score": 90 - 10 * i, "best_platform": "tiktok",
        })
        frames = [[0.0, 0.0, float(content_box[0]), float(content_box[1])]] * int((end - start) * 25)
        p = job_dir / f"traj_{i:02d}.json"
        p.write_text(json.dumps({
            "fps": 25, "frames": frames, "cuts": [], "punches": [],
            "content_w": content_box[0], "content_h": content_box[1],
        }), encoding="utf-8")
        trajectories[str(i)] = str(p)
    words = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]
    return {
        "ingest": {"media_path": str(source), "probe": {"width": 1280, "height": 720}},
        "diarize": {"segments": [{"words": words}]},
        "events": {"timeline": [{"type": "laugh", "start": 7.0, "end": 8.0}], "curves_path": str(curves)},
        "score": {"clips": clips},
        "camera": {"trajectories": trajectories},
    }


def test_montage_smoke(tmp_path, source):
    """The whole ranking branch: three moments → one file, a countdown, the
    segments gone, the frame count exact, and a checkpoint the stage then
    accepts as its own."""
    settings = config.Settings()
    settings.ranking.enabled = True
    settings.ranking.count = 3
    prior = _seed(tmp_path, source, [(0.0, 4.0), (6.0, 10.0), (12.0, 16.0)], (1280, 720))
    ctx = FakeCtx(tmp_path, settings, prior)

    data = render_stage.RenderStage().run(ctx)

    assert len(data["outputs"]) == 1
    out = data["outputs"][0]
    assert out["montage"] is True and out["clip"] == 0  # rank 1 fronts the entry
    assert Path(out["path"]).name == "ranking.mp4" and Path(out["path"]).exists()
    assert data["ranking"]["order"] == [2, 1, 0]           # countdown
    assert data["ranking"]["title"] == "TOP 3"
    assert data["ranking"]["band"]["boxed"] is False       # full-frame content: a real bar
    assert [s["offset"] for s in data["ranking"]["segments"]] == [0.0, 4.0, 8.0]
    assert [s["rank"] for s in data["ranking"]["segments"]] == [3, 2, 1]
    assert list(data["fills"]) == ["2", "1", "0"]
    assert data["kept_from_editor"] == []
    # one format, not both: the segment files are gone, their documents stay
    assert not list((tmp_path / "clips").glob("ranking_seg_*.mp4"))
    assert len(list((tmp_path / "clips").glob("ranking_seg_*.ass"))) == 3
    # the total length, said before the first encode (E18-F02)
    assert any("3 moments, 0:12 total" in m for m in ctx.messages)
    # E18-F04 with no client to build (the no_real_llm stand-in below, the
    # no-key path): every entry blank, said once, written down per moment,
    # and the montage still made — §5.9, on real pixels
    assert data["ranking"]["labels"] == {"0": None, "1": None, "2": None}
    assert set(data["ranking"]["label_errors"]) == {"0", "1", "2"}
    assert all("No Gemini API key" in e for e in data["ranking"]["label_errors"].values())
    assert sum("numbers only" in m for m in ctx.messages) == 1

    probe = _probe(Path(out["path"]))
    assert int(probe["video"]["nb_read_frames"]) == 3 * 4 * 25   # sum of the segments, exactly
    assert int(probe["video"]["width"]) == 1080 and int(probe["video"]["height"]) == 1920
    # the audio runs one AAC frame long by construction (tail padding, not
    # drift — measured before this was written); anything bigger is a real
    # desync
    assert abs(float(probe["audio"]["duration"]) - float(probe["video"]["duration"])) < 0.05

    stage = render_stage.RenderStage()
    assert stage.artifacts_ok(ctx, data) is True
    ctx.settings.ranking.count = 4
    assert stage.artifacts_ok(ctx, data) is False   # a different top N
    ctx.settings.ranking.count = 3
    ctx.settings.ranking.enabled = False
    assert stage.artifacts_ok(ctx, data) is False   # a different output unit
    ctx.settings.ranking.enabled = True
    assert stage.artifacts_ok(ctx, data) is True


def test_podcast_framing_puts_the_list_over_the_picture(tmp_path, source):
    """No bar at the tight 9:16 crop, so the band goes over the picture
    behind the backing drawing — and libass must accept that drawing, which
    only a real burn can prove. Owner's decision (2026-09-03), stated in
    captions/ranking.py."""
    settings = config.Settings()
    settings.ranking.enabled = True
    settings.ranking.count = 2
    prior = _seed(tmp_path, source, [(0.0, 2.0), (5.0, 7.0)], (405, 720))
    ctx = FakeCtx(tmp_path, settings, prior)
    data = render_stage.RenderStage().run(ctx)
    assert data["ranking"]["band"]["boxed"] is True
    assert any("over the top of the picture" in m for m in ctx.messages)
    assert renderer.verify_output(Path(data["outputs"][0]["path"]), 4.0)["ok"]


def test_segments_are_concat_compatible_and_the_list_is_in_the_pixels(tmp_path, source):
    """The claim concat_copy rests on, as a test: two segments of one job
    come out of render_clip with identical stream parameters. And the
    overlay is burned, not decorative: the first frame of a segment with
    the list differs from the same segment without it."""
    traj = {
        "fps": 25, "frames": [[0.0, 0.0, 1280.0, 720.0]] * 50,
        "content_w": 1280, "content_h": 720,
    }
    preset = ass_mod.PRESETS["classic"]
    band = overlay.band_for([656], 2)
    words = [ass_mod.Word(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(4)]
    paths = []
    for k in range(2):
        ass_path = tmp_path / f"seg{k}.ass"
        ass_path.write_text(
            ass_mod.build_ass(
                words, [], extra_styles=overlay.overlay_styles(preset, band),
                extra_events=overlay.overlay_events(preset, band, k, 2.0),
            ),
            encoding="utf-8",
        )
        out = tmp_path / f"seg{k}.mp4"
        renderer.render_clip(
            str(source), out, 3.0 * k, 3.0 * k + 2.0, traj, ass_path, ass_mod.FONTS_DIR,
            src_w=1280, src_h=720, edge_fade_s=ranking.EDGE_FADE_S,
        )
        paths.append(out)
    plain_ass = tmp_path / "plain.ass"
    plain_ass.write_text(ass_mod.build_ass(words, []), encoding="utf-8")
    plain = tmp_path / "plain.mp4"
    renderer.render_clip(str(source), plain, 0.0, 2.0, traj, plain_ass, ass_mod.FONTS_DIR,
                         src_w=1280, src_h=720)

    keys_v = ("codec_name", "pix_fmt", "width", "height", "sample_aspect_ratio", "r_frame_rate", "profile")
    keys_a = ("codec_name", "sample_rate", "channels")
    probes = [_probe(p) for p in paths]
    for key in keys_v:
        assert probes[0]["video"].get(key) == probes[1]["video"].get(key), key
    for key in keys_a:
        assert probes[0]["audio"].get(key) == probes[1]["audio"].get(key), key

    montage = tmp_path / "montage.mp4"
    renderer.concat_copy(paths, montage)
    assert int(_probe(montage)["video"]["nb_read_frames"]) == 2 * 2 * 25

    def first_frame(path: Path) -> bytes:
        png = path.with_suffix(".png")
        subprocess.run(
            [ffmpeg_bin.ffmpeg(), "-v", "error", "-y", "-i", str(path), "-frames:v", "1", str(png)],
            check=True, timeout=120,
        )
        return png.read_bytes()

    assert first_frame(paths[0]) != first_frame(plain)


# ---------------------------------------------------------------------------
# Moment labels (E18-F04)


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """The ranking branch asks for an LLM client (E18-F04), and the owner's
    machine has a key: without this, every montage test in this file would
    spend real calls. The default stand-in cannot be built — the no-key
    path — so a montage renders with numbers only; the tests about labels
    install a fake client over it."""
    def refuse(llm_mode, gemini_model=None):
        raise llm_mod.LlmError("No Gemini API key found (test stand-in).", code="no-gemini-key")

    monkeypatch.setattr(llm_mod, "make_client", refuse)


class LabelClient:
    """Stands in for the LLM behind the label engine: answers with a label
    unique to the moment (its first transcript word), raises for a moment
    whose transcript carries `poison`, answers four words for one carrying
    `wordy` — on every ask, or only on the first when it `relents` — and
    counts every call. The determinism guard is a count."""

    def __init__(self, poison: str | None = None, wordy: str | None = None, relents: bool = False):
        self.poison = poison
        self.wordy = wordy
        self.relents = relents
        self.calls: list[str] = []
        self.asked: dict[str, int] = {}

    def generate_json(self, prompt, schema, images=None):
        self.calls.append(prompt)
        transcript = prompt.split("Transcript:\n", 1)[1].split("\n", 1)[0].split()
        first = transcript[0]
        self.asked[first] = self.asked.get(first, 0) + 1
        if self.poison and self.poison in transcript:
            raise RuntimeError("model down")
        wordy = self.wordy and self.wordy in transcript
        if wordy and not (self.relents and self.asked[first] > 1):
            return {"label": " ".join(transcript[:4]), "grounded_in": first}
        return {"label": f"moment {first}", "grounded_in": first}


def _install(monkeypatch, client) -> list:
    """make_client → `client`; returns the list of times it was asked to
    build one, so a test can assert the stage never even tried."""
    built: list[str] = []

    def make(llm_mode, gemini_model=None):
        built.append(llm_mode)
        return client

    monkeypatch.setattr(llm_mod, "make_client", make)
    return built


def _fake_encoders(monkeypatch):
    """The label logic needs no pixels. The three ffmpeg calls of the
    montage path are stubbed so a run costs milliseconds; the caption
    documents are still written, and they are what the assertions read."""
    def touch(path):
        Path(path).write_bytes(b"mp4")

    monkeypatch.setattr(renderer, "render_clip", lambda media, out, *a, **kw: touch(out))
    monkeypatch.setattr(renderer, "concat_copy", lambda parts, out, **kw: touch(out))
    monkeypatch.setattr(
        renderer, "verify_output",
        lambda path, expected: {"ok": True, "duration": float(expected), "width": 1080, "height": 1920},
    )
    monkeypatch.setattr(ass_mod, "emoji_probe", lambda *a, **kw: False)


def _checkpoint(job_dir: Path, data: dict) -> None:
    """What the runner writes after run(): the envelope read_checkpoint and
    render/stage.py:_previous_render read (jobs/queue.py:write_checkpoint)."""
    (job_dir / "render.json").write_text(
        json.dumps({"stage": "render", "schema_version": 1, "created_at": 0, "data": data}),
        encoding="utf-8",
    )


def _labelled_job(tmp_path, source, monkeypatch, client, windows=((0.0, 4.0), (6.0, 10.0), (12.0, 16.0))):
    """A ranking job over `windows` on fake encoders, with `client` behind
    the label engine. Words run every half second, so clip (6, 10) starts
    at w12 — the transcript each moment's label is derived from."""
    _fake_encoders(monkeypatch)
    settings = config.Settings()
    settings.ranking.enabled = True
    settings.ranking.count = len(windows)
    prior = _seed(tmp_path, source, list(windows), (1280, 720))
    ctx = FakeCtx(tmp_path, settings, prior)
    built = _install(monkeypatch, client)
    return ctx, built


def _label_lines(doc: str) -> list[tuple[str, str]]:
    """(tags, text) per RankLabel dialogue line, in row order."""
    out = []
    for line in doc.splitlines():
        if ",RankLabel," not in line:
            continue
        text = line.split(",", 8)[8]
        tags, label = text.rsplit("}", 1)
        out.append((tags + "}", label))
    return out


def _segment_docs(job_dir: Path, n: int) -> list[str]:
    return [
        (job_dir / "clips" / f"ranking_seg_{k:02d}.ass").read_text(encoding="utf-8")
        for k in range(n)
    ]


# --- the overlay, pure


def test_labels_reveal_with_their_numbers_and_not_before():
    preset = ass_mod.PRESETS["classic"]
    band = overlay.band_for([656], 3)
    labels = ["the confession", "bath bomb", None]  # ranks 1, 2, 3; rank 3 has none
    # segment 0 plays rank 3: nothing with a label has been revealed yet
    assert _label_lines(overlay.overlay_events(preset, band, 0, 4.0, labels=labels)) == []
    # segment 1 plays rank 2: its label fades in with its number; rank 1's stays hidden
    mid = _label_lines(overlay.overlay_events(preset, band, 1, 4.0, labels=labels))
    assert [t for _, t in mid] == ["bath bomb"]
    assert preset.active in mid[0][0] and "\\fad" in mid[0][0] and "\\q2" in mid[0][0]
    # segment 2 plays rank 1: both, rank 2's now in the played colour, no fade
    last = _label_lines(overlay.overlay_events(preset, band, 2, 4.0, labels=labels))
    assert [t for _, t in last] == ["the confession", "bath bomb"]
    assert "\\fad" in last[0][0]
    assert "\\fad" not in last[1][0] and "\\alpha" not in last[1][0]
    # the numbers are what they were: one per row, in row order, label or not
    numbers = _entries(overlay.overlay_events(preset, band, 2, 4.0, labels=labels))
    assert [n for _, n in numbers] == ["1", "2", "3"]


def test_labels_take_the_presets_case_and_are_escaped():
    preset = ass_mod.PRESETS["beast"]  # uppercase
    doc = overlay.overlay_events(preset, overlay.band_for([656], 1), 0, 4.0, labels=["bath {bomb}"])
    assert [t for _, t in _label_lines(doc)] == ["BATH (BOMB)"]


def test_label_column_starts_right_of_the_numbers():
    """Same face and size as the numbers, placed by its style's margin like
    every other line of the overlay — only MarginL differs, by the column."""
    styles = overlay.overlay_styles(ass_mod.PRESETS["classic"], overlay.band_for([656], 3)).splitlines()
    label = next(ln for ln in styles if ln.startswith("Style: RankLabel,")).split(",")
    entry = next(ln for ln in styles if ln.startswith("Style: RankEntry,")).split(",")
    assert label[1:19] == entry[1:19] and label[20:] == entry[20:]
    assert int(entry[19]) == ass_mod.SIDE_MARGIN
    assert int(label[19]) == ass_mod.SIDE_MARGIN + overlay.NUMBER_COLUMN


def test_without_labels_the_overlay_is_what_it_was():
    preset = ass_mod.PRESETS["classic"]
    band = overlay.band_for([656], 3)
    plain = overlay.overlay_events(preset, band, 1, 4.0)
    assert plain == overlay.overlay_events(preset, band, 1, 4.0, labels=[None, None, None])
    assert ",RankLabel," not in plain


# --- through the stage


def test_one_failed_label_blanks_one_entry_and_the_rest_render(tmp_path, source, monkeypatch):
    """§5.9 for one moment: the call for rank 2 fails; its entry shows the
    number alone, the two others carry their labels, the montage is made,
    and the failure is said once and written down once."""
    client = LabelClient(poison="w12")
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, client)
    data = render_stage.RenderStage().run(ctx)
    result = data["ranking"]
    assert result["labels"] == {
        "0": {"text": "moment w0", "grounded_in": "w0", "start": 0.0, "end": 4.0},
        "1": None,
        "2": {"text": "moment w24", "grounded_in": "w24", "start": 12.0, "end": 16.0},
    }
    assert list(result["label_errors"]) == ["1"]
    assert result["label_errors"]["1"].startswith("moment #2: ")
    assert "model down" in result["label_errors"]["1"]
    assert len(client.calls) == 3
    assert sum("shows the number only" in m for m in ctx.messages) == 1
    assert Path(data["outputs"][0]["path"]).exists()
    # play order is rank 3 (clip 2), rank 2 (clip 1, blank), rank 1 (clip 0)
    docs = _segment_docs(tmp_path, 3)
    assert [t for _, t in _label_lines(docs[0])] == ["moment w24"]
    assert [t for _, t in _label_lines(docs[1])] == ["moment w24"]  # rank 2 revealed, nothing to show
    assert [t for _, t in _label_lines(docs[2])] == ["moment w0", "moment w24"]
    # the segment after the failed one still carries every number, the blank row's included
    assert [n for _, n in _entries(docs[2])] == ["1", "2", "3"]


def test_an_unusable_answer_is_a_blank_entry_that_says_what_was_answered(tmp_path, source, monkeypatch):
    """Two unusable answers — the first and its one retry — are a blank
    entry, and label_errors records both, with the text that was
    rejected (E18-F04 amendment)."""
    client = LabelClient(wordy="w12")
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, client)
    data = render_stage.RenderStage().run(ctx)
    assert data["ranking"]["labels"]["1"] is None
    assert data["ranking"]["label_errors"]["1"] == (
        "moment #2: the model's answers 'w12 w13 w14 w15' (longer than 3 words) and "
        "'w12 w13 w14 w15' (longer than 3 words) were both rejected"
    )
    assert len(client.calls) == 4  # three moments, one retry — not a loop


def test_a_retried_label_is_stored_and_reused_like_any_other(tmp_path, source, monkeypatch):
    """The retry happens inside the first generation: an answer the filter
    rejected, then a good one, lands on the checkpoint like any label — and
    the re-render reuses it without a call, as the determinism guard
    demands of every label."""
    client = LabelClient(wordy="w12", relents=True)
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, client)
    stage = render_stage.RenderStage()
    data = stage.run(ctx)
    assert len(client.calls) == 4
    assert data["ranking"]["labels"]["1"] == {
        "text": "moment w12", "grounded_in": "w12", "start": 6.0, "end": 10.0,
    }
    assert data["ranking"]["label_errors"] == {}
    _checkpoint(tmp_path, data)

    ctx.settings.caption_preset = "beast"
    again = LabelClient()
    built = _install(monkeypatch, again)
    assert stage.run(ctx)["ranking"]["labels"] == data["ranking"]["labels"]
    assert again.calls == [] and built == []


def test_a_fatal_llm_error_blanks_the_rest_without_asking(tmp_path, source, monkeypatch):
    """A rejected key fails every call the same way: after the first, the
    remaining moments are blanked without a call each, and the outage is
    said once, not once per moment."""
    class Rejected:
        calls = 0

        def generate_json(self, prompt, schema, images=None):
            Rejected.calls += 1
            raise llm_mod.LlmError("Gemini rejected the API key.", code="gemini-key-rejected")

    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, Rejected())
    data = render_stage.RenderStage().run(ctx)
    assert Rejected.calls == 1
    assert data["ranking"]["labels"] == {"0": None, "1": None, "2": None}
    assert all("rejected the API key" in e for e in data["ranking"]["label_errors"].values())
    assert sum("numbers only" in m for m in ctx.messages) == 1


def test_a_re_render_reuses_the_stored_labels_and_makes_no_llm_call(tmp_path, source, monkeypatch):
    """The determinism guard, and the most important test of E18-F04: the
    same job re-rendered burns the same words. Labels are an output stored
    on the checkpoint, not a setting in its fingerprint — a caption restyle
    invalidates the render, the stage re-runs, and it neither builds a
    client nor asks the model; it reuses what it stored."""
    first = LabelClient()
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, first)
    stage = render_stage.RenderStage()
    data = stage.run(ctx)
    assert len(first.calls) == 3
    _checkpoint(tmp_path, data)

    ctx.settings.caption_preset = "beast"
    assert stage.artifacts_ok(ctx, data) is False  # the restyle re-runs the stage...
    second = LabelClient()
    built = _install(monkeypatch, second)
    again = stage.run(ctx)
    assert again["ranking"]["labels"] == data["ranking"]["labels"]  # ...which burns the same words
    assert second.calls == [] and built == []  # without one call, or even a client
    assert again["ranking"]["label_errors"] == {}
    last = _segment_docs(tmp_path, 3)[2]
    assert [t for _, t in _label_lines(last)] == ["MOMENT W0", "MOMENT W12", "MOMENT W24"]  # beast uppercases


def test_a_re_run_retries_only_the_moment_that_had_no_label(tmp_path, source, monkeypatch):
    """A None is a failure, not a label. When the stage re-runs (here: the
    outage passed and the render was restyled), the failed moment is asked
    again and the two that have labels are not — one call, not three. A
    CACHED render never reaches this code and keeps the blank."""
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, LabelClient(poison="w12"))
    stage = render_stage.RenderStage()
    data = stage.run(ctx)
    assert data["ranking"]["labels"]["1"] is None
    _checkpoint(tmp_path, data)

    ctx.settings.caption_preset = "beast"
    healthy = LabelClient()
    _install(monkeypatch, healthy)
    again = stage.run(ctx)
    assert len(healthy.calls) == 1 and "\nw12 w13 " in healthy.calls[0]
    assert again["ranking"]["labels"]["1"] == {
        "text": "moment w12", "grounded_in": "w12", "start": 6.0, "end": 10.0,
    }
    assert again["ranking"]["labels"]["0"] == data["ranking"]["labels"]["0"]
    assert again["ranking"]["labels"]["2"] == data["ranking"]["labels"]["2"]
    assert again["ranking"]["label_errors"] == {}


def test_a_stored_label_is_not_reused_for_a_different_moment(tmp_path, source, monkeypatch):
    """Clip indices are positions in score.json. After a scoring re-run a
    different moment can sit at the same position, and reusing by index
    alone would burn the old moment's words onto the new one's pictures,
    silently. Bounds identify the moment: only the moved one is asked."""
    ctx, _ = _labelled_job(tmp_path, source, monkeypatch, LabelClient())
    stage = render_stage.RenderStage()
    data = stage.run(ctx)
    _checkpoint(tmp_path, data)

    ctx.prior = _seed(tmp_path, source, [(0.0, 4.0), (7.0, 11.0), (12.0, 16.0)], (1280, 720))
    client = LabelClient()
    _install(monkeypatch, client)
    again = stage.run(ctx)
    assert len(client.calls) == 1
    assert again["ranking"]["labels"]["1"] == {
        "text": "moment w14", "grounded_in": "w14", "start": 7.0, "end": 11.0,
    }
    assert again["ranking"]["labels"]["0"] == data["ranking"]["labels"]["0"]
    assert again["ranking"]["labels"]["2"] == data["ranking"]["labels"]["2"]


def test_clip_mode_makes_no_llm_call(tmp_path, source, monkeypatch):
    """Labels exist only in ranking mode. A clip-mode render must not build
    a client, let alone ask — counted, not assumed: a raising stand-in
    would be swallowed by the label path's own degradation."""
    _fake_encoders(monkeypatch)
    settings = config.Settings()
    assert settings.ranking.enabled is False
    prior = _seed(tmp_path, source, [(0.0, 4.0), (6.0, 10.0)], (1280, 720))
    ctx = FakeCtx(tmp_path, settings, prior)
    client = LabelClient()
    built = _install(monkeypatch, client)
    data = render_stage.RenderStage().run(ctx)
    assert len(data["outputs"]) == 2 and "ranking" not in data
    assert built == [] and client.calls == []
