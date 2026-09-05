"""E19 — overlays on the clip: the burned title (E19-F01) and the watermark
(E19-F02).

Pure tests for the two fragment builders and the placement arithmetic;
stage runs on fake encoders (the caption documents and the filter fragment
handed to the encoder are what the assertions read); and two renders on
real pixels through the synthetic-ffmpeg path test_render_smoke uses (§3):
the mark composes with the blur fill branch and with the black one, in the
stage's `-vf` graph AND the editor's `-filter_complex` graph."""

import json
import struct
import subprocess
import zlib
from pathlib import Path

import numpy as np
import pytest

from publikclip_pipeline import config
from publikclip_pipeline.captions import ass as ass_mod
from publikclip_pipeline.captions import title as title_mod
from publikclip_pipeline.edits import render_clip as rc
from publikclip_pipeline.edits.timeline import ClipEdit
from publikclip_pipeline.render import ffmpeg_bin, renderer, watermark
from publikclip_pipeline.render import stage as render_stage
from publikclip_pipeline.scoring import llm as llm_mod

# ---------------------------------------------------------------------------
# Fixtures


def _png(path: Path, width: int = 200, height: int = 100, rgb=(0, 255, 0)) -> Path:
    """A solid-colour 8-bit RGB PNG, written by hand (signature, IHDR, one
    IDAT, IEND) so the tests need no image library and no ffmpeg."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    path.write_bytes(
        watermark.PNG_SIGNATURE
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return path


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


def _seed(job_dir: Path, media: str, windows, content_box) -> dict:
    """A finished job's prior stages, synthetic: one clip per window, one
    trajectory each with the given content box (full 16:9 frame → a real
    bar, tight 9:16 → none), words every half second, one laugh."""
    job_dir.mkdir(parents=True, exist_ok=True)
    curves = job_dir / "curves.json"
    curves.write_text(json.dumps({"rms": [0.2] * 200, "grid_sec": 0.1}), encoding="utf-8")
    clips, trajectories = [], {}
    for i, (start, end) in enumerate(windows):
        clips.append({"start": start, "end": end, "score": 90 - 10 * i, "best_platform": "tiktok"})
        frames = [[0.0, 0.0, float(content_box[0]), float(content_box[1])]] * int((end - start) * 25)
        p = job_dir / f"traj_{i:02d}.json"
        p.write_text(json.dumps({
            "fps": 25, "frames": frames, "cuts": [], "punches": [],
            "content_w": content_box[0], "content_h": content_box[1],
        }), encoding="utf-8")
        trajectories[str(i)] = str(p)
    words = [{"word": f"w{i}", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(40)]
    return {
        "ingest": {"media_path": media, "probe": {"width": 1280, "height": 720}},
        "diarize": {"segments": [{"words": words}]},
        "events": {"timeline": [{"type": "laugh", "start": 7.0, "end": 8.0}], "curves_path": str(curves)},
        "score": {"clips": clips},
        "camera": {"trajectories": trajectories, "camera_settings": config.CameraSettings().__dict__},
    }


def _job(tmp_path, windows=((0.0, 4.0), (6.0, 10.0)), content_box=(1280, 720), media="src.mp4"):
    settings = config.Settings()
    return FakeCtx(tmp_path, settings, _seed(tmp_path, media, list(windows), content_box))


def _write_edits(job_dir: Path, edits: dict) -> None:
    (job_dir / "clip_edits.json").write_text(json.dumps(edits), encoding="utf-8")


def _checkpoint(job_dir: Path, data: dict) -> None:
    (job_dir / "render.json").write_text(
        json.dumps({"stage": "render", "schema_version": 1, "created_at": 0, "data": data}),
        encoding="utf-8",
    )


def _stage_files(ctx) -> None:
    """The prior stages as the editor's path reads them: <stage>.json
    envelopes plus the job's settings snapshot."""
    for name, data in ctx.prior.items():
        (ctx.job_dir / f"{name}.json").write_text(json.dumps({"data": data}), encoding="utf-8")
    (ctx.job_dir / "settings.json").write_text(
        json.dumps(ctx.settings.to_json()), encoding="utf-8"
    )


def _fake_encoders(monkeypatch) -> dict:
    """No pixels: the encoder calls are stubbed and RECORDED — the filter
    fragment each render was handed is what the watermark assertions read,
    the caption documents (still written) what the title ones read."""
    calls = {"render": [], "concat": []}

    def render(media, out, *a, **kw):
        calls["render"].append({"out": Path(out), "overlay_vf": kw.get("overlay_vf", "")})
        Path(out).write_bytes(b"mp4")

    def concat(parts, out, **kw):
        calls["concat"].append(list(parts))
        Path(out).write_bytes(b"mp4")

    monkeypatch.setattr(renderer, "render_clip", render)
    monkeypatch.setattr(renderer, "concat_copy", concat)
    monkeypatch.setattr(
        renderer, "verify_output",
        lambda path, expected: {"ok": True, "duration": float(expected), "width": 1080, "height": 1920},
    )
    monkeypatch.setattr(ass_mod, "emoji_probe", lambda *a, **kw: False)
    monkeypatch.setattr(ffmpeg_bin, "supports_captions", lambda: True)
    monkeypatch.setattr(ffmpeg_bin, "ensure_capable", lambda progress=None: True)
    return calls


def _capture_edit_render(monkeypatch) -> list[list[str]]:
    """The editor's path without ffmpeg: its one subprocess call recorded,
    the output touched, the encoder probe pinned."""
    seen: list[list[str]] = []

    class Done:
        returncode = 0
        stderr = ""

    def run(args, **kw):
        seen.append(list(args))
        Path(args[-1]).write_bytes(b"mp4")
        return Done()

    monkeypatch.setattr(rc.subprocess, "run", run)
    monkeypatch.setattr(renderer, "video_encoder_args", lambda hardware: ["-c:v", "libx264"])
    monkeypatch.setattr(ffmpeg_bin, "ffmpeg", lambda: "ffmpeg")
    return seen


def _lines(doc: str, style: str) -> list[str]:
    return [ln for ln in doc.splitlines() if f",{style}," in ln or ln.startswith(f"Style: {style},")]


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Ranking mode asks for a label client (E18-F04); the owner's machine
    has a key. The no-key stand-in keeps every montage here to numbers."""
    def refuse(llm_mode, gemini_model=None):
        raise llm_mod.LlmError("No Gemini API key found (test stand-in).", code="no-gemini-key")

    monkeypatch.setattr(llm_mod, "make_client", refuse)


# ---------------------------------------------------------------------------
# E19-F01 — the burned title, pure


def test_burned_title_reads_a_dict_or_a_clip_edit_and_whitespace_is_nothing():
    assert title_mod.burned_title({"burned_title": "  Bath   bomb\n"}) == "Bath bomb"
    assert title_mod.burned_title({"burned_title": "   "}) == ""
    assert title_mod.burned_title({}) == ""
    assert title_mod.burned_title(ClipEdit(0.0, 1.0, burned_title="A title")) == "A title"
    assert title_mod.burned_title(ClipEdit(0.0, 1.0)) == ""


def test_the_title_sits_in_the_top_safe_zone_for_the_whole_clip():
    preset = ass_mod.PRESETS["classic"]
    styles, events = title_mod.overlay(preset, "Why the {bath bomb} flew", 12.5)
    # top-centre, the safe zone as its margin, the captions' side margins
    assert styles.startswith("Style: BurnTitle,Inter,")
    fields = styles.strip().split(",")
    assert fields[-5:] == ["8", str(ass_mod.SIDE_MARGIN), str(ass_mod.SIDE_MARGIN), str(ass_mod.TOP_SAFE_PX), "1"]
    assert int(fields[2]) == title_mod.title_size(preset) == 58  # 72 * 0.8, inside the clamp
    # one event, first frame to last, wrapping on — and the braces escaped
    assert events == "Dialogue: 2,0:00:00.00,0:00:12.50,BurnTitle,,0,0,0,{\\q0}Why the (bath bomb) flew\n"
    # the preset's case rule applies, as it does to captions
    assert "WHY THE (BATH BOMB) FLEW" in title_mod.overlay(ass_mod.PRESETS["beast"], "Why the {bath bomb} flew", 1.0)[1]


def test_no_marked_title_leaves_the_caption_document_untouched():
    """A pin, not a change: an unmarked clip's document must be what it
    was before this module existed (passes on both trees by design)."""
    preset = ass_mod.PRESETS["classic"]
    assert title_mod.overlay(preset, "", 5.0) == ("", "")
    words = [ass_mod.Word("hello", 0.0, 0.4)]
    styles, events = title_mod.overlay(preset, "", 5.0)
    assert ass_mod.build_ass(words, [], extra_styles=styles, extra_events=events) == ass_mod.build_ass(words, [])


# ---------------------------------------------------------------------------
# E19-F01 — through the stage


def test_a_restyle_preserves_a_burned_title(tmp_path, monkeypatch):
    """E19-F01's last criterion, and the one most likely to rot: the title
    is a STYLE the stage reproduces from the clip's edit, so a job-level
    restyle re-renders the clip WITH it — in the new preset's face — rather
    than losing it, and never adopts the editor's file to keep it."""
    _fake_encoders(monkeypatch)
    ctx = _job(tmp_path)
    _write_edits(tmp_path, {"0": {"burned_title": "The bath bomb incident"}})
    ctx.settings.caption_preset = "classic"
    data = render_stage.RenderStage().run(ctx)
    first = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    assert "Style: BurnTitle,Inter," in first and "The bath bomb incident" in first
    assert "BurnTitle" not in (tmp_path / "clips" / "clip_01.ass").read_text(encoding="utf-8")
    assert data["kept_from_editor"] == []  # re-rendered as a style, not adopted as a structure
    assert data["clip_edits"] == {"0": {"burned_title": "The bath bomb incident"}}

    # the restyle: a different job preset invalidates, and the re-render
    # carries the title in the new face (beast uppercases)
    _checkpoint(tmp_path, data)
    ctx.settings.caption_preset = "beast"
    assert render_stage.RenderStage().artifacts_ok(ctx, data) is False
    again = render_stage.RenderStage().run(ctx)
    second = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    assert "Style: BurnTitle,Anton," in second and "THE BATH BOMB INCIDENT" in second
    assert again["kept_from_editor"] == []


def test_the_edit_path_and_the_stage_place_the_title_and_the_mark_identically(tmp_path, monkeypatch):
    """§5.8: the two render paths build the title's two ASS lines and the
    watermark's filter fragment through the same functions, so for the
    same clip they are byte-identical — not merely similar."""
    calls = _fake_encoders(monkeypatch)
    logo = _png(tmp_path / "logo.png")
    ctx = _job(tmp_path, windows=[(0.0, 4.0)])
    ctx.settings.watermark.image = str(logo)
    # the full shape the app writes: the editor's store needs the bounds
    _write_edits(tmp_path, {"0": {"start": 0.0, "end": 4.0, "burned_title": "Same words, both paths"}})
    render_stage.RenderStage().run(ctx)
    stage_doc = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    stage_vf = calls["render"][0]["overlay_vf"]
    assert stage_vf.startswith("null[wm_base];movie=filename=")

    _stage_files(ctx)
    argv = _capture_edit_render(monkeypatch)
    rc.render_clip_edit(tmp_path, 0, lambda f, m: None)
    edit_doc = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    assert _lines(stage_doc, "BurnTitle") == _lines(edit_doc, "BurnTitle")
    assert len(_lines(stage_doc, "BurnTitle")) == 2  # the style and the one event
    graph = argv[0][argv[0].index("-filter_complex") + 1]
    assert f"[vb]{stage_vf}[wm_on]" in graph          # the same fragment, after the base video
    assert "[wm_on]subtitles=" in graph                 # and before the caption burn


# ---------------------------------------------------------------------------
# E19-F02 — placement, pure


def test_placement_at_both_framing_endpoints_of_a_1080p_source():
    """The numbers in the PR description come from here. A 2:1 logo and a
    word, at gameplay framing (a 656 px bar) and podcast framing (no bar),
    with the classic preset's captions 560 px from the bottom."""
    logo = watermark.Mark("image", path="x.png", width=200, height=100)
    full = watermark.place(logo, 1920, 1080, 560)
    assert (full.width, full.height) == (238, 118)      # 22 % of 1080 wide, even
    assert full.in_bar and full.opacity == 1.0
    assert full.y == 1264 + (656 - 118) // 2 == 1533     # centred in the bar
    assert full.x == (1080 - 238) // 2 == 421
    tight = watermark.place(logo, 607.5, 1080, 560)
    assert not tight.in_bar and tight.opacity == watermark.PICTURE_OPACITY
    assert tight.y == 1920 - 120 - 118 == 1682           # on the picture's bottom

    word = watermark.Mark("text", text="@alias")
    full_w = watermark.place(word, 1920, 1080, 560)
    assert full_w.height == 53 and full_w.y == 1565 and full_w.margin_v == 302 and full_w.in_bar
    tight_w = watermark.place(word, 607.5, 1080, 560)
    assert tight_w.y == 1747 and tight_w.margin_v == 120 and not tight_w.in_bar

    # a bar too thin to hold the mark counts as no bar (dial at 0.05: 93 px)
    thin = watermark.place(logo, 673.0, 1080, 560)
    assert not thin.in_bar and thin.opacity == watermark.PICTURE_OPACITY

    # a tall logo is capped, not stretched
    tall = watermark.place(watermark.Mark("image", path="x", width=100, height=400), 1920, 1080, 560)
    assert tall.height == watermark.IMAGE_MAX_HEIGHT and tall.width == 60


def test_the_mark_never_covers_the_captions():
    """Captions anchor their bottom edge margin_v from the frame's and grow
    upward; the mark's top edge stays CAPTION_GAP below that anchor, pushed
    down out of its centred spot when it must — and when the captions sit
    so low that nothing fits underneath, there is no mark."""
    logo = watermark.Mark("image", path="x.png", width=200, height=100)
    centred = watermark.place(logo, 1920, 1080, 560)
    assert centred.y >= 1920 - 560 + watermark.CAPTION_GAP
    low = watermark.place(logo, 1920, 1080, 300)
    assert low.y == 1920 - 300 + watermark.CAPTION_GAP == 1644 and low.in_bar
    assert low.y + low.height <= 1920 - watermark.EDGE_MIN
    assert watermark.place(logo, 1920, 1080, 100) is None


def test_the_image_fragment_uses_its_own_labels_and_composes_with_the_blur_fill():
    logo = watermark.Mark("image", path="C:\\Users\\x\\logo.png", width=200, height=100)
    vf = watermark.image_vf(logo, watermark.place(logo, 1920, 1080, 560))
    assert vf.startswith("null[wm_base];movie=filename=")
    assert vf.endswith("[wm_src];[wm_base][wm_src]overlay=x=421:y=1533")
    assert ",scale=238:118:flags=lanczos,format=rgba" in vf
    assert "colorchannelmixer" not in vf                 # opaque in the bar
    picture = watermark.image_vf(logo, watermark.place(logo, 607.5, 1080, 560))
    assert "format=rgba,colorchannelmixer=aa=0.60" in picture
    # joined into the stage's chain beside the blur fill: disjoint label namespaces
    chain = ",".join([*renderer.scale_pad_vf(1920, 1080, "blur"), "setsar=1", vf])
    assert {"lb_a", "lb_b", "lb_bg", "lb_fg", "wm_base", "wm_src"} <= set(
        __import__("re").findall(r"\[(\w+)\]", chain)
    )
    assert "[vc]" not in vf and "[vb]" not in vf and "[ov" not in vf and "[vf]" not in vf


def test_the_word_rides_the_caption_document_under_the_captions():
    preset = ass_mod.PRESETS["classic"]
    word = watermark.Mark("text", text="@alias {studio}")
    in_bar = watermark.place(word, 1920, 1080, preset.margin_v)
    style, event = watermark.text_ass(word, in_bar, preset, 4.0)
    fields = style.strip().split(",")
    assert fields[0] == "Style: Watermark" and fields[1] == "Inter"
    assert fields[-5:] == ["2", "60", "60", str(in_bar.margin_v), "1"]  # bottom-centre, MarginV
    assert event == "Dialogue: 0,0:00:00.00,0:00:04.00,Watermark,,0,0,0,{\\alpha&H00&\\q2}@alias (studio)\n"
    on_picture = watermark.place(word, 607.5, 1080, preset.margin_v)
    assert "{\\alpha&H66&\\q2}" in watermark.text_ass(word, on_picture, preset, 4.0)[1]  # 60 % opaque


def test_resolve_prefers_the_image_and_never_falls_through_to_the_word(tmp_path):
    settings = config.Settings()
    assert watermark.resolve(settings) is None
    settings.watermark.text = "  @alias  "
    assert watermark.resolve(settings) == watermark.Mark("text", text="@alias")
    logo = _png(tmp_path / "logo.png", 320, 80)
    settings.watermark.image = str(logo)
    assert watermark.resolve(settings) == watermark.Mark("image", path=str(logo), width=320, height=80)
    # a set image that is unusable is NO mark, not the word: the user asked for the logo
    said: list[str] = []
    settings.watermark.image = str(tmp_path / "gone.png")
    assert watermark.resolve(settings, said.append) is None
    assert said == ["Watermark image gone.png is missing — rendering without a watermark."]


# ---------------------------------------------------------------------------
# E19-F02 — the fingerprint (§4 rules 1 and 3)


def _clip_checkpoint(ctx, tmp_path) -> dict:
    mp4 = tmp_path / "clip_00.mp4"
    mp4.write_bytes(b"x")
    return {"outputs": [{"clip": 0, "path": str(mp4)}], "fills": {"0": "black"}, **render_stage._fingerprint(ctx)}


def test_changing_the_watermark_file_content_with_the_same_path_invalidates_the_render(tmp_path):
    """§4 rule 1, the reason the criterion exists: a logo replaced under
    the same name must re-render, or the old logo stays in every clip.
    And why a content hash rather than size+mtime: the same bytes under a
    new mtime are the same render."""
    logo = _png(tmp_path / "logo.png", 200, 100, (0, 255, 0))
    ctx = FakeCtx(tmp_path, config.Settings(), {})
    ctx.settings.watermark.image = str(logo)
    data = _clip_checkpoint(ctx, tmp_path)
    assert data["watermark"]["kind"] == "image" and len(data["watermark"]["sha256"]) == 64
    stage = render_stage.RenderStage()
    assert stage.artifacts_ok(ctx, data) is True
    # rewritten byte for byte: a new mtime and size unchanged — still valid
    logo.write_bytes(logo.read_bytes())
    assert stage.artifacts_ok(ctx, data) is True
    # the same size, the same path, different pixels — invalid
    _png(logo, 200, 100, (255, 0, 0))
    assert stage.artifacts_ok(ctx, data) is False
    # the file gone: a different render (one without a mark) — and once it
    # is back, that markless render is invalid in turn
    logo.unlink()
    assert stage.artifacts_ok(ctx, data) is False
    markless = _clip_checkpoint(ctx, tmp_path)
    assert markless["watermark"]["sha256"] == "missing"
    assert stage.artifacts_ok(ctx, markless) is True
    _png(logo, 200, 100, (0, 255, 0))
    assert stage.artifacts_ok(ctx, markless) is False


def test_a_checkpoint_from_before_the_watermark_existed_stays_valid_until_one_is_set(tmp_path):
    """§4 rule 3: every render on disk lacks the key; none may re-render
    because the setting arrived. Setting a word — or the deck's explicit
    "" after one — is what invalidates."""
    ctx = FakeCtx(tmp_path, config.Settings(), {})
    data = _clip_checkpoint(ctx, tmp_path)
    del data["watermark"]
    stage = render_stage.RenderStage()
    assert stage.artifacts_ok(ctx, data) is True
    ctx.settings.watermark.text = "@alias"
    assert stage.artifacts_ok(ctx, data) is False
    worded = _clip_checkpoint(ctx, tmp_path)
    assert stage.artifacts_ok(ctx, worded) is True
    ctx.settings.watermark.text = "@other"
    assert stage.artifacts_ok(ctx, worded) is False
    ctx.settings.watermark.text = ""
    assert stage.artifacts_ok(ctx, worded) is False


# ---------------------------------------------------------------------------
# E19-F02 — through the stage


def test_a_missing_or_unreadable_watermark_file_renders_the_clip_without_it(tmp_path, monkeypatch):
    """§5.9. Both failures render every clip, hand the encoder no fragment,
    and say so once; the positive control at the end is what makes the
    first two degradations rather than absence."""
    calls = _fake_encoders(monkeypatch)
    stage = render_stage.RenderStage()

    ctx = _job(tmp_path)
    ctx.settings.watermark.image = str(tmp_path / "gone.png")
    data = stage.run(ctx)
    assert [o["clip"] for o in data["outputs"]] == [0, 1]
    assert all(c["overlay_vf"] == "" for c in calls["render"])
    assert ctx.messages.count("Watermark image gone.png is missing — rendering without a watermark.") == 1
    assert data["watermark"] == {"kind": "image", "path": str(tmp_path / "gone.png"), "sha256": "missing"}

    calls["render"].clear()
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"GIF89a not a png at all")
    ctx = _job(tmp_path)
    ctx.settings.watermark.image = str(junk)
    stage.run(ctx)
    assert all(c["overlay_vf"] == "" for c in calls["render"])
    assert ctx.messages.count("Watermark image junk.png is not a PNG — rendering without a watermark.") == 1

    calls["render"].clear()
    ctx = _job(tmp_path)
    ctx.settings.watermark.image = str(_png(tmp_path / "logo.png"))
    stage.run(ctx)
    assert all("[wm_base][wm_src]overlay=x=421:y=1533" in c["overlay_vf"] for c in calls["render"])
    assert not any("rendering without a watermark" in m for m in ctx.messages)


def test_ranking_segments_carry_the_watermark_and_the_montage_stays_a_remux(tmp_path, monkeypatch):
    """A ranking video is channel output, so its segments get the mark in
    their one encode and the join stays the remux E18-F02 rests on — no
    encode is added for it. The burned title, by contrast, is a clip's
    own and never reaches a segment (E19-F01: ranking videos carry their
    own title)."""
    calls = _fake_encoders(monkeypatch)
    ctx = _job(tmp_path, windows=[(0.0, 4.0), (6.0, 10.0), (12.0, 16.0)])
    ctx.settings.ranking.enabled = True
    ctx.settings.ranking.count = 3
    ctx.settings.watermark.text = "@alias"
    _write_edits(tmp_path, {"0": {"burned_title": "Only on the clip"}})
    data = render_stage.RenderStage().run(ctx)
    assert len(calls["render"]) == 6 and len(calls["concat"]) == 1  # 3 clips + 3 segments, one join
    for k in range(3):
        doc = (tmp_path / "clips" / f"ranking_1-3_seg_{k:02d}.ass").read_text(encoding="utf-8")
        assert "Style: Watermark," in doc and "@alias" in doc and ",RankTitle," in doc
        assert "BurnTitle" not in doc and "Only on the clip" not in doc
    clip0 = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    assert "Style: Watermark," in clip0 and "Style: BurnTitle," in clip0
    assert data["watermark"] == {"kind": "text", "text": "@alias"}

    # the image kind reaches the segments' encoder call the same way
    calls["render"].clear()
    ctx = _job(tmp_path, windows=[(0.0, 4.0), (6.0, 10.0), (12.0, 16.0)])
    ctx.settings.ranking.enabled = True
    ctx.settings.ranking.count = 3
    ctx.settings.watermark.image = str(_png(tmp_path / "logo.png"))
    render_stage.RenderStage().run(ctx)
    segment_calls = [c for c in calls["render"] if c["out"].name.startswith("ranking_")]
    assert len(segment_calls) == 3
    assert all("[wm_base][wm_src]overlay=" in c["overlay_vf"] for c in calls["render"])


def test_no_overlay_configured_leaves_the_render_command_and_the_document_untouched(tmp_path, monkeypatch):
    """A pin: with no mark and no marked title, the encoder's command line
    and the caption document are byte-for-byte what they were (passes on
    both trees by design — it protects every render on disk)."""
    seen: list[list[str]] = []

    class Done:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(renderer, "video_encoder_args", lambda hardware: ["-c:v", "libx264"])
    monkeypatch.setattr(renderer.ffmpeg_bin, "ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(renderer.subprocess, "run", lambda args, **kw: seen.append(list(args)) or Done())
    traj = {"fps": 25, "frames": [[0, 0, 1280, 720]], "content_w": 1280, "content_h": 720}
    out = tmp_path / "a.mp4"
    renderer.render_clip("src.mp4", out, 0.0, 4.0, traj, None, None, src_w=1280, src_h=720)
    vf = seen[-1][seen[-1].index("-vf") + 1]
    cmd = renderer._q(out.with_suffix(".cmd"))
    assert vf == (
        f"sendcmd=f={cmd},crop@c=w=1280:h=720:x=0:y=0,"
        "scale=1080:608:flags=lanczos,pad=1080:1920:0:656:color=black,setsar=1"
    )

    calls = _fake_encoders(monkeypatch)
    ctx = _job(tmp_path)
    render_stage.RenderStage().run(ctx)
    assert all(c["overlay_vf"] == "" for c in calls["render"])
    doc = (tmp_path / "clips" / "clip_00.ass").read_text(encoding="utf-8")
    assert "Watermark" not in doc and "BurnTitle" not in doc and ",1\n\n[Events]\n" in doc


# ---------------------------------------------------------------------------
# E19-F02 — the import behind the deck's picker


def test_watermark_import_copies_the_png_into_the_home_and_refuses_the_rest(tmp_path, monkeypatch, capsys):
    from publikclip_pipeline import cli

    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    src = _png(tmp_path / "My Logo (final).png", 64, 64)
    stored = watermark.import_image(src)
    assert stored.parent == tmp_path / "home" / "watermarks"
    assert stored.name.startswith("My_Logo_final-") and stored.suffix == ".png"
    assert stored.read_bytes() == src.read_bytes()
    assert watermark.import_image(src) == stored               # the same bytes, the same path
    _png(src, 64, 64, (255, 0, 0))
    assert watermark.import_image(src) != stored               # a changed logo, a new path
    with pytest.raises(watermark.WatermarkError):
        watermark.import_image(tmp_path / "missing.png")
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"not a png")
    with pytest.raises(watermark.WatermarkError):
        watermark.import_image(junk)
    # the CLI verb the shell's settings_tool passes through
    assert cli.main(["settings", "watermark-import", str(src)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True and Path(out["path"]).exists() and out["bytes"] > 0
    assert cli.main(["settings", "watermark-import", str(junk)]) == 1
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is False and "not a PNG" in out["error"]


# ---------------------------------------------------------------------------
# Real pixels: the mark composes with both fills, in both graphs


@pytest.fixture(scope="module")
def source(tmp_path_factory) -> Path:
    src = tmp_path_factory.mktemp("src") / "src.mp4"
    subprocess.run(
        [
            ffmpeg_bin.ffmpeg(), "-v", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25:duration=6",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(src),
        ],
        check=True, timeout=300,
    )
    return src


def _frame(path: Path, at: float) -> np.ndarray:
    """One decoded frame as an (1920, 1080, 3) RGB array."""
    proc = subprocess.run(
        [
            ffmpeg_bin.ffmpeg(), "-v", "error", "-ss", f"{at:.2f}", "-i", str(path),
            "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ],
        capture_output=True, timeout=120, check=True,
    )
    return np.frombuffer(proc.stdout, dtype=np.uint8).reshape(1920, 1080, 3)


def _green_dominates(region: np.ndarray) -> bool:
    mean = region.reshape(-1, 3).mean(axis=0)
    return mean[1] > 170 and mean[0] < 90 and mean[2] < 90


@pytest.mark.slow
def test_the_watermark_composes_with_the_blur_fill_branch_and_the_black_one(tmp_path, source):
    """The stage's `-vf` graph on real pixels: a pure green logo lands
    opaque, centred in the bar, over the blurred copy of the frame — the
    branch whose labelled split could have collided — and over black."""
    logo = _png(tmp_path / "logo.png", 200, 100, (0, 255, 0))
    settings = config.Settings()
    settings.watermark.image = str(logo)
    mark = watermark.resolve(settings)
    preset = ass_mod.PRESETS["classic"]
    placement = watermark.place(mark, 1280, 720, preset.margin_v)
    composed = watermark.compose(mark, 1280, 720, preset, 4.0)
    traj = {"fps": 25, "frames": [[0.0, 0.0, 1280.0, 720.0]] * 100, "content_w": 1280, "content_h": 720}
    words = [ass_mod.Word(f"word{i}", i * 0.5, i * 0.5 + 0.4) for i in range(8)]
    ass_path = tmp_path / "caps.ass"
    ass_path.write_text(ass_mod.build_ass(words, []), encoding="utf-8")
    for fill in ("blur", "black"):
        out = tmp_path / f"{fill}.mp4"
        renderer.render_clip(
            str(source), out, 0.0, 4.0, traj, ass_path, ass_mod.FONTS_DIR,
            src_w=1280, src_h=720, letterbox_fill=fill, overlay_vf=composed.vf,
        )
        assert renderer.verify_output(out, 4.0)["ok"]
        frame = _frame(out, 1.0)
        y, x, h, w = placement.y, placement.x, placement.height, placement.width
        assert _green_dominates(frame[y + 8:y + h - 8, x + 8:x + w - 8]), fill
        # beside it the bar is whatever the fill made it, so this is a mark and not a green bar
        assert not _green_dominates(frame[y:y + h, 40:40 + w]), fill

    # the word, through the caption document, still an encodable graph
    settings.watermark.image = ""
    settings.watermark.text = "@alias"
    worded = watermark.compose(watermark.resolve(settings), 1280, 720, preset, 4.0)
    ass_path.write_text(
        ass_mod.build_ass(words, [], extra_styles=worded.styles, extra_events=worded.events),
        encoding="utf-8",
    )
    out = tmp_path / "word.mp4"
    renderer.render_clip(str(source), out, 0.0, 4.0, traj, ass_path, ass_mod.FONTS_DIR, src_w=1280, src_h=720)
    assert renderer.verify_output(out, 4.0)["ok"]


@pytest.mark.slow
def test_the_editor_render_composes_the_watermark_with_the_blur_fill_too(tmp_path, source, monkeypatch):
    """The editor's `-filter_complex` graph names [vc]/[vb]/[vf] itself and
    carries the blur fill's lb_* split inside a labelled chain; the mark's
    fragment is spliced between the base video and the caption burn."""
    monkeypatch.setattr(ass_mod, "emoji_probe", lambda *a, **kw: False)
    logo = _png(tmp_path / "logo.png", 200, 100, (0, 255, 0))
    ctx = _job(tmp_path, windows=[(0.0, 4.0)], media=str(source))
    ctx.settings.watermark.image = str(logo)
    ctx.settings.camera.letterbox_fill = "blur"
    _stage_files(ctx)
    _write_edits(tmp_path, {"0": {"start": 0.0, "end": 4.0, "burned_title": "On the picture too"}})
    entry = rc.render_clip_edit(tmp_path, 0, lambda f, m: None)
    out = Path(entry["path"])
    assert renderer.verify_output(out, 4.0)["ok"]
    placement = watermark.place(watermark.resolve(ctx.settings), 1280, 720, ass_mod.PRESETS["classic"].margin_v)
    frame = _frame(out, 1.0)
    y, x, h, w = placement.y, placement.x, placement.height, placement.width
    assert _green_dominates(frame[y + 8:y + h - 8, x + 8:x + w - 8])
    assert not _green_dominates(frame[y:y + h, 40:40 + w])
