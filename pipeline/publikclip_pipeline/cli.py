"""Alias Studio CLI.

Doubles as the desktop app's sidecar: with --jsonl every progress event and
the final result are emitted as one JSON object per stdout line, so the
Tauri shell just spawns `publikclip --jsonl run <source>` and streams.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import chains, config, errors, winpatches
from .jobs import queue

winpatches.apply_all()
# Before anything else can crash: unhandled tracebacks print through
# redact(), so the stderr tail the shell captures for its 'exited' event
# never carries a secret or the user's home path (T-13).
errors.install_excepthook()


def _stages(mode: str = chains.DEFAULT_MODE) -> list[queue.Stage]:
    """The stage instances for one chain (E20 / D-19), in the order
    chains.CHAINS gives — that table is the light-import truth and a test
    pins this function to it for every chain. Stage imports are deferred so
    `publikclip jobs` doesn't pay the torch import tax."""
    names = chains.chain_for(mode)
    if names == chains.CLIPS_CHAIN:
        from .asr.stage import AsrStage
        from .camera.stage import CameraStage
        from .candidates.stage import CandidatesStage
        from .diarize.stage import DiarizeStage
        from .events.stage import EventsStage
        from .ingest.stage import IngestStage
        from .render.stage import RenderStage
        from .scoring.stage import ScoreStage

        built = [
            IngestStage(),
            AsrStage(),
            DiarizeStage(),
            EventsStage(),
            CandidatesStage(),
            ScoreStage(),
            CameraStage(),
            RenderStage(),
        ]
    elif names == chains.STORY_CHAIN:
        from .asr.stage import AsrStage
        from .ingest.stage import IngestStage
        from .narrate.stage import NarrateStage
        from .render.story import StoryRenderStage

        built = [
            # silent b-roll is the normal background; its sound is never used
            IngestStage(needs_audio=False),
            NarrateStage(),
            # F04: the captions' timings come from transcribing the narration
            AsrStage(source="narrate"),
            StoryRenderStage(),
        ]
    else:  # pragma: no cover - chain_for refused every other mode above
        raise ValueError(f"no stage builder for mode {mode!r}")
    assert tuple(s.name for s in built) == names, (mode, built, names)
    return built


def _progress_printer(jsonl: bool):
    def emit(stage: str, fraction: float, message: str) -> None:
        if jsonl:
            print(
                json.dumps(
                    {"event": "progress", "stage": stage, "fraction": fraction, "message": message}
                ),
                flush=True,
            )
        else:
            pct = f"{fraction * 100:5.1f}%" if fraction >= 0 else "  ...."
            print(f"[{stage:<10}] {pct} {message}", file=sys.stderr, flush=True)

    return emit


def _emit_result(jsonl: bool, payload: dict) -> None:
    if jsonl:
        print(json.dumps({"event": "result", **payload}), flush=True)
    else:
        print(json.dumps(payload, indent=2))


def _source_type(source: str) -> str:
    return "url" if source.startswith(("http://", "https://")) else "file"


def _apply_setting_flags(settings: "config.Settings", args: argparse.Namespace) -> "config.Settings":
    """One place for CLI flag -> settings overrides, shared by run, resume
    and `jobs create`, so enqueueing a job cannot drift from running one."""
    if args.llm:
        settings.llm_mode = args.llm
    if args.captions:
        settings.caption_preset = args.captions
    if getattr(args, "camera", None):
        settings.camera.speaker_change = args.camera
    if args.gameplay_amount is not None:  # 0.0 is a legitimate value, not falsy-skippable
        settings.camera.gameplay_amount = args.gameplay_amount
    if getattr(args, "letterbox_fill", None):  # choices bar '', so truthy is safe here
        settings.camera.letterbox_fill = args.letterbox_fill
    # E18-F01. on|off rather than store_true so resume can tell "not
    # mentioned" (keep the job's snapshot) from "turn it off".
    ranking = getattr(args, "ranking", None)
    if ranking is not None:
        settings.ranking.enabled = ranking == "on"
    ranking_count = getattr(args, "ranking_count", None)
    if ranking_count is not None:
        settings.ranking.count = max(1, int(ranking_count))
    # E18-F07. argparse holds the choices; the snapshot stores the word.
    ranking_order = getattr(args, "ranking_order", None)
    if ranking_order is not None:
        settings.ranking.order = ranking_order
    # E19-F02. `is not None`, never truthiness: "" is an explicit "no
    # watermark" — the deck sends it so a job never inherits a mark the
    # deck did not show, and `resume --watermark-text ""` clears one.
    watermark_image = getattr(args, "watermark_image", None)
    if watermark_image is not None:
        settings.watermark.image = watermark_image.strip()
    watermark_text = getattr(args, "watermark_text", None)
    if watermark_text is not None:
        settings.watermark.text = watermark_text.strip()
    # E20 (D-19): which chain. Only `run` and `jobs create` carry the flag —
    # a job's chain is fixed at creation, because its checkpoints belong to
    # that chain; resume reads the snapshot and never takes the flag.
    mode = getattr(args, "mode", None)
    if mode:
        settings.mode = mode
    # E20-F02: the narrator. Explicit on the deck like the rest, so the
    # snapshot records the choice; `resume --voice` re-narrates.
    voice = getattr(args, "voice", None)
    if voice:
        settings.story.voice = voice
    speed = getattr(args, "speed", None)
    if speed is not None:
        settings.story.speed = float(speed)
    return settings


def _story_input(args: argparse.Namespace, settings: "config.Settings") -> tuple[str | None, str | None]:
    """(text, refusal) for a story job's `--story-file` (E20-F01). Read
    here, validated here, BEFORE the job row exists, so a refused story
    never leaves a pending job the queue would try to run. A clips job
    answers (None, None). The tool never fetches text from anywhere: this
    is the only way a story reaches a job."""
    if settings.mode != "stories":
        return None, None
    from .narrate import limits

    path = getattr(args, "story_file", None)
    if not path:
        return None, "A story job needs its text: pass --story-file <a .txt file>."
    try:
        text = Path(path).expanduser().read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, f"Story file not found: {path}"
    except UnicodeDecodeError:
        return None, f"Story file is not UTF-8 text: {path}"
    except OSError as err:
        return None, f"Story file could not be read: {err}"
    refusal = limits.check(text)
    if refusal:
        return None, refusal
    return text, None


def _store_story(job: queue.Job, text: str | None) -> None:
    """The copy into the job dir (E20-F01): content travels WITH the job,
    never in the settings snapshot."""
    if text is None:
        return
    from .narrate import story

    story.store(job.dir, text)


def cmd_run(args: argparse.Namespace) -> int:
    # New jobs start from the user's saved global settings; CLI flags
    # override just those fields. Existing jobs keep their own snapshot.
    settings = _apply_setting_flags(config.load_defaults(), args)
    text, refusal = _story_input(args, settings)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    job = queue.create_job(_source_type(args.source), args.source, json.dumps(settings.to_json()))
    _store_story(job, text)
    return _execute(job, args.jsonl)


def cmd_resume(args: argparse.Namespace) -> int:
    job = queue.get_job(args.job_id)
    if job is None:
        print(f"No job {args.job_id}", file=sys.stderr)
        return 2
    # T-14 (E14-F02): the user chose where to restart. Invalidate that one
    # stage; run_stages' cascade re-runs everything after it and nothing
    # before. Without the flag, resume behaves exactly as it always has.
    if getattr(args, "from_stage", None):
        # The choices list spans every chain (argparse cannot know the job
        # yet); the job's own chain is the real gate. A stage outside it
        # would delete nothing and re-run nothing — a resume that silently
        # did not do what was asked.
        if args.from_stage not in chains.chain_for(job.mode):
            print(
                f"{args.from_stage} is not a stage of this {job.mode} job "
                f"(its stages: {', '.join(chains.chain_for(job.mode))})",
                file=sys.stderr,
            )
            return 2
        queue.invalidate_stage(job, args.from_stage)
    # Every settings flag resume accepts must be listed here: one that is
    # parsed but not listed is accepted and silently changes nothing (§5.2).
    # `--letterbox-fill` was exactly that from E6-F09 until this line.
    if (
        args.llm or args.captions or args.camera or args.gameplay_amount is not None
        or getattr(args, "letterbox_fill", None)
        or getattr(args, "ranking", None) is not None
        or getattr(args, "ranking_count", None) is not None
        or getattr(args, "ranking_order", None) is not None
        or getattr(args, "watermark_image", None) is not None
        or getattr(args, "watermark_text", None) is not None
        or getattr(args, "voice", None)
        or getattr(args, "speed", None) is not None
    ):
        settings = _apply_setting_flags(
            config.Settings.from_json(json.loads(job.settings_json)), args
        )
        # Updates the DB row AND the job-dir snapshot; the clip editor reads
        # the latter, so writing only one leaves the job disagreeing with
        # itself about its own settings.
        job = queue.update_settings(job.id, json.dumps(settings.to_json()))
    return _execute(job, args.jsonl)


def _failure_payload(job: queue.Job, err: BaseException) -> dict:
    """The result event's error fields: the described ErrorInfo run_stages
    just wrote to error.json (authoritative — it knows the stage), falling
    back to describing the exception directly when the file is not there
    (a failure outside run_stages). `error` stays the flat cause string so
    every consumer that predates error_info keeps rendering."""
    try:
        payload = json.loads((job.dir / queue.ERROR_FILE).read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("cause"):
            return {"error": payload["cause"], "error_info": payload}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    info = errors.describe(err)
    return {"error": info.cause, "error_info": info.to_json()}


def _execute(job: queue.Job, jsonl: bool) -> int:
    emit = _progress_printer(jsonl)
    # `mode` rides the job event (E20): the deck draws the running chain's
    # rows from it, and this event is the one place a job start is observed
    # (§5.12) — so the chain reaches the screen with the same transition
    # that resets it, whichever of the four paths started the job.
    if jsonl:
        print(
            json.dumps({"event": "job", "job_id": job.id, "dir": str(job.dir), "mode": job.mode}),
            flush=True,
        )
    else:
        print(f"job {job.id} ({job.mode}) → {job.dir}", file=sys.stderr)
    # E1-F07: per-volume disk pre-flight before anything heavy writes. A
    # confident shortfall fails the job with the numbers in its error —
    # never leaves it pending, which the shell's auto-advance would respawn
    # in a loop — so the queue continues and a resume after freeing space
    # retries for free. Unknown warns, never refuses, and a crash inside
    # the check itself must not take the job with it (§5.9).
    from .jobs import disk

    emit("setup", -1.0, "Checking disk space…")
    try:
        report = disk.preflight(job)
    except Exception as err:  # noqa: BLE001 — the check is advisory
        sys.stderr.write(f"disk check skipped: {err!r}\n")
        report = None
    if report is not None and report["action"] != "ok":
        if jsonl:
            print(json.dumps({"event": "disk", **report}), flush=True)
        else:
            print(f"[disk] {report['action']}: {report['message']}", file=sys.stderr, flush=True)
        if report["action"] == "block":
            disk.block_start(job, report)
            info = errors.info_for("disk-space-blocked", cause=report["message"])
            _emit_result(
                jsonl,
                {"ok": False, "job_id": job.id, "error": info.cause, "error_info": info.to_json()},
            )
            return 1
    # Resolve (and fetch if missing) ffmpeg once, up front — several stages
    # (ingest merging, ASR decoding, rendering) need it and some, like
    # whisperx's ASR step, shell out to a bare `ffmpeg` on PATH rather than
    # asking us for the path, so it must be in place before any stage runs.
    from .render import ffmpeg_bin

    ffmpeg_bin.ensure_capable(progress=lambda f, m: emit("setup", f, m))
    run_started = time.time()
    try:
        results = queue.run_stages(job, _stages(job.mode), emit)
    except queue.JobCancelled:
        # Deliberate stop, exit 0: a non-zero exit would land in the shell's
        # 'exited' crash handler and a cancel would read as a crash even with
        # every line of it working (T-07).
        if jsonl:
            print(json.dumps({"event": "cancelled", "job_id": job.id}), flush=True)
        else:
            print(f"job {job.id} cancelled - checkpoints kept", file=sys.stderr)
        return 0
    except queue.StageError as err:
        _emit_result(jsonl, {"ok": False, "job_id": job.id, **_failure_payload(job, err)})
        return 1
    except Exception as err:  # noqa: BLE001 — T-13: the unknown must not reach the UI as a repr
        # run_stages already recorded and described this into error.json;
        # emitting a result here is what lets the UI show the described
        # shape instead of relying on the shell's 'exited' fallback. The
        # (redacted) traceback still goes to stderr for the live console.
        _emit_result(jsonl, {"ok": False, "job_id": job.id, **_failure_payload(job, err)})
        import traceback

        sys.stderr.write(errors.redact(traceback.format_exc()))
        return 1
    # E13-F01: fold this run's measured stage timings into the hardware
    # profile. Best-effort - a profile hiccup must never fail a job that
    # just finished rendering (§5.9).
    try:
        from . import hardware_profile

        hardware_profile.update_after_job(job.id, run_started)
    except Exception:  # noqa: BLE001
        pass
    summary = {
        "ok": True,
        "job_id": job.id,
        "stages": list(results.keys()),
        "title": results.get("ingest", {}).get("title"),
        "heatmap_segments": len(results.get("ingest", {}).get("heatmap") or []),
    }
    _emit_result(jsonl, summary)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    """E14-F03: one inspectable zip a beta user can safely send. No
    network, no upload — the user sends the file themselves."""
    from . import diagnose

    job = queue.get_job(args.job_id) if args.job_id else next(iter(queue.list_jobs(1)), None)
    if job is None:
        print(json.dumps({"ok": False, "error": "no job to diagnose"}))
        return 2
    out = Path(args.out) if args.out else None
    result = diagnose.build_bundle(job, out)
    print(json.dumps({"ok": True, "job_id": job.id, **result}))
    return 0


def cmd_hardware(args: argparse.Namespace) -> int:
    """Probe, persist, print. The shell only ever READS the profile file
    (probing costs a uv one-shot plus, worst case, nvidia-smi's 20 s
    timeout); this verb is the one deliberate way to re-probe."""
    from . import hardware_profile

    print(json.dumps(hardware_profile.refresh()), flush=True)
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    """E1-F01: what a first job would download, checked or fetched up front.
    `status` is filesystem-only and prints one JSON line; `run` fetches
    everything missing with JSONL progress and is safe to kill — completion
    is re-derived from disk, and the resumable downloads keep their offset."""
    from . import setup as setup_mod

    if getattr(args, "setup_cmd", None) == "status":
        print(json.dumps(setup_mod.status()), flush=True)
        return 0

    def emit(obj: dict) -> None:
        if args.jsonl:
            print(json.dumps(obj), flush=True)
        else:
            state = obj.get("state", obj.get("event"))
            frac = obj.get("fraction")
            pct = f" {frac * 100:5.1f}%" if isinstance(frac, float) and frac >= 0 else ""
            detail = obj.get("message") or obj.get("error") or ""
            print(f"[{obj.get('item', 'setup'):<10}] {state}{pct} {detail}", file=sys.stderr, flush=True)

    result = setup_mod.run(emit)
    _emit_result(args.jsonl, result)
    return 0 if result["ok"] else 1


def cmd_jobs(args: argparse.Namespace) -> int:
    sub = getattr(args, "jobs_cmd", None)
    if sub == "create":
        # Enqueue: the first half of cmd_run and nothing else. The row (and
        # its settings snapshot) exists before any run does - that is what
        # makes a job that has not started representable at all (T-08).
        settings = _apply_setting_flags(config.load_defaults(), args)
        text, refusal = _story_input(args, settings)
        if refusal:
            # JSON, because the shell reads this line: the deck shows the
            # refusal where the press happened (E20-F01's limit, named).
            print(json.dumps({"ok": False, "error": refusal}))
            return 2
        job = queue.create_job(_source_type(args.source), args.source, json.dumps(settings.to_json()))
        _store_story(job, text)
        print(json.dumps({"job_id": job.id, "status": job.status}))
        return 0
    if sub == "next":
        job = queue.next_pending()
        print(json.dumps({"job_id": job.id if job else None}))
        return 0
    if sub == "reconcile":
        print(json.dumps({"reconciled": queue.reconcile_stale_running()}))
        return 0
    if sub == "cancel-pending":
        print(json.dumps(queue.cancel_pending(args.job_id)))
        return 0
    if sub == "resume-info":
        # T-14: everything the resume picker shows — statuses, the failed
        # stage as the default, measured cost per starting stage.
        job = queue.get_job(args.job_id)
        if job is None:
            print(json.dumps({"error": f"no job {args.job_id}"}))
            return 2
        print(json.dumps(queue.resume_info(job)))
        return 0
    if sub == "mark-cancelled":
        print(json.dumps(queue.mark_cancelled(args.job_id)))
        return 0
    if args.jsonl:
        # The Queue view's data source: SQLite is the queue's bookkeeping,
        # and this is the one view that shows bookkeeping. The library rail
        # stays filesystem-truth (list_job_dirs) - two views, two truths,
        # deliberately.
        for job in queue.list_jobs():
            stages = queue.stage_statuses(job.id)
            done = sum(1 for s in stages.values() if s == "done")
            print(
                json.dumps(
                    {
                        "id": job.id,
                        "status": job.status,
                        "error": job.error,
                        "title": job.title,
                        "source": job.source,
                        "created_at": job.created_at,
                        "stages_done": done,
                    }
                )
            )
        return 0
    for job in queue.list_jobs():
        stages = queue.stage_statuses(job.id)
        done = sum(1 for s in stages.values() if s == "done")
        print(f"{job.id}  {job.status:<8} {done} stage(s) done  {job.title or job.source}")
    return 0


def cmd_settings(args: argparse.Namespace) -> int:
    """Settings panel backend. All output is one JSON blob on stdout.

    The panel edits GLOBAL defaults (what new jobs start from) and caption
    presets. Existing jobs keep their own snapshot on purpose — editing a
    default must never silently rescore or reframe finished work.
    """
    from . import settings_schema
    from .captions import ass as ass_mod

    def payload() -> dict:
        defaults = config.load_defaults()
        saved = config.load_caption_presets()
        return {
            "ok": True,
            "defaults": defaults.to_json(),
            "factory": config.Settings().to_json(),
            "schema": settings_schema.schema_payload(),
            "presets": {
                name: ass_mod.preset_to_ui(ass_mod.resolve_preset(name))
                for name in ass_mod.preset_names()
            },
            "preset_names": ass_mod.preset_names(),
            "edited_presets": sorted(saved),
        }

    if args.settings_cmd == "get":
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "set":
        try:
            incoming = json.loads(args.json)
        except json.JSONDecodeError as err:
            print(json.dumps({"ok": False, "error": f"bad settings JSON: {err}"}))
            return 2
        # Round-trip through Settings so unknown/garbage keys are dropped and
        # every missing field lands on its default rather than being lost.
        config.save_defaults(config.Settings.from_json(incoming))
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "reset":
        config.save_defaults(config.Settings())
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "preset-save":
        try:
            patch = json.loads(args.json)
        except json.JSONDecodeError as err:
            print(json.dumps({"ok": False, "error": f"bad preset JSON: {err}"}))
            return 2
        saved = config.load_caption_presets()
        saved[args.name] = ass_mod.preset_from_ui(args.name, patch)
        config.save_caption_presets(saved)
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "preset-reset":
        saved = config.load_caption_presets()
        saved.pop(args.name, None)
        config.save_caption_presets(saved)
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "story-limits":
        # E20-F01: the deck's numbers — the word limits, the words-per-minute
        # its length estimate uses, and the voices on offer — from the one
        # module that applies them, so the deck cannot drift from the gate.
        from .narrate import limits

        print(json.dumps(limits.limits_payload()))
        return 0

    if args.settings_cmd == "story-read":
        # E20-F01: a .txt the user picked, read for the deck's textarea so
        # the estimate and the limits apply to it exactly as to pasted
        # text. The frontend has no file access of its own; python reads
        # it and the deck edits it like anything pasted. The tool never
        # fetches text from anywhere else.
        from .narrate import limits

        path = Path(args.path).expanduser()
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(json.dumps({"ok": False, "error": f"not found: {args.path}"}))
            return 1
        except UnicodeDecodeError:
            print(json.dumps({"ok": False, "error": f"not a UTF-8 text file: {path.name}"}))
            return 1
        except OSError as err:
            print(json.dumps({"ok": False, "error": f"could not read {path.name}: {err}"}))
            return 1
        print(json.dumps({
            "ok": True, "text": text, "name": path.name, "words": limits.word_count(text),
            "refusal": limits.check(text), "warning": limits.warning(text),
        }))
        return 0

    if args.settings_cmd == "remember-background":
        # E20 (Q2): the last-used background is a real setting. The deck
        # calls this on every pick; a missing file is refused so a stale
        # path is never remembered as a default.
        path = Path(args.path).expanduser()
        if not path.is_file():
            print(json.dumps({"ok": False, "error": f"not a file: {args.path}"}))
            return 1
        defaults = config.load_defaults()
        defaults.story.background = str(path)
        config.save_defaults(defaults)
        print(json.dumps(payload()))
        return 0

    if args.settings_cmd == "watermark-import":
        # E19-F02: the deck's PNG picker lands here. The copy into
        # PUBLIKCLIP_HOME and the PNG check are python's — testable here,
        # and the shell stays the passthrough it already is.
        from .render import watermark

        try:
            stored = watermark.import_image(Path(args.path))
        except watermark.WatermarkError as err:
            print(json.dumps({"ok": False, "error": str(err)}))
            return 1
        print(json.dumps({
            "ok": True, "path": str(stored), "name": stored.name, "bytes": stored.stat().st_size,
        }))
        return 0

    print(json.dumps({"ok": False, "error": f"unknown settings command {args.settings_cmd}"}))
    return 2


def cmd_edit(args: argparse.Namespace) -> int:
    """Per-clip editing verbs. All output is JSON on stdout for the app."""
    from pathlib import Path

    from .edits import render_clip as rc
    from .edits import store, visuals

    job = queue.get_job(args.job_id)
    if job is None:
        print(json.dumps({"ok": False, "error": f"no job {args.job_id}"}))
        return 2
    job_dir = Path(job.dir)

    if args.edit_cmd == "context":
        # A declined context (E20: a story job has no clips to tune)
        # arrives with its own ok=False and error; the merge lets it win.
        print(json.dumps({"ok": True, **rc.context_for_clip(job_dir, args.clip)}))
        return 0

    if args.edit_cmd == "suggest-visuals":
        score = json.loads((job_dir / "score.json").read_text(encoding="utf-8"))["data"]
        clip = score["clips"][args.clip]
        edit = store.edit_for_clip(job_dir, args.clip, clip)
        # plan against OUTPUT-time words = current bounds without dead-space
        # (suggestions land on the source-bounds timeline the UI shows)
        diarize = json.loads((job_dir / "diarize.json").read_text(encoding="utf-8"))["data"]
        words = [
            {"word": w["word"], "start": w["start"] - edit.start, "end": w["end"] - edit.start}
            for seg in diarize["segments"]
            for w in seg.get("words", [])
            if edit.start <= w["start"] < edit.end
        ]
        settings = config.Settings.from_json(json.loads(job.settings_json))
        try:
            suggestions = visuals.suggest(
                job_dir, words, settings.llm_mode, prefer=args.prefer,
                gemini_model=settings.gemini_model,
            )
        except Exception as err:  # noqa: BLE001 — surface, don't crash the app
            print(json.dumps({"ok": False, "error": str(err)}))
            return 1
        edits = store.load(job_dir)
        current = edits.get(str(args.clip), edit)
        known = {o.id for o in current.overlays}
        current.overlays.extend(o for o in suggestions if o.id not in known)
        edits[str(args.clip)] = current
        store.save(job_dir, edits)
        print(json.dumps({"ok": True, "edit": current.to_json()}))
        return 0

    if args.edit_cmd in ("titles", "description", "hook"):
        from .copywriting import descriptions as desc_mod
        from .copywriting import hooks as hooks_mod
        from .copywriting import titles as titles_mod
        from .scoring import llm as llm_mod

        score = json.loads((job_dir / "score.json").read_text(encoding="utf-8"))["data"]
        clip = score["clips"][args.clip]
        edit = store.edit_for_clip(job_dir, args.clip, clip)
        settings = config.Settings.from_json(json.loads(job.settings_json))
        diarize = json.loads((job_dir / "diarize.json").read_text(encoding="utf-8"))["data"]
        try:
            client = llm_mod.make_client(settings.llm_mode, settings.gemini_model)
        except llm_mod.LlmError as err:
            print(json.dumps({"ok": False, "error": str(err)}))
            return 1

        if args.edit_cmd == "titles":
            words = [
                w["word"]
                for seg in diarize["segments"]
                for w in seg.get("words", [])
                if edit.start <= w["start"] < edit.end
            ]
            opts = titles_mod.TitleOptions(**settings.titles.__dict__)
            try:
                out = titles_mod.generate(
                    client, " ".join(words), clip.get("summary", ""), opts
                )
            except Exception as err:  # noqa: BLE001 — surface, don't crash the app
                print(json.dumps({"ok": False, "error": str(err)}))
                return 1
            # Keep the variants on the clip so they survive a restart and can
            # be compared later without paying to regenerate them.
            edits = store.load(job_dir)
            current = edits.get(str(args.clip), edit)
            current.title_variants = out["titles"]
            edits[str(args.clip)] = current
            store.save(job_dir, edits)
            print(json.dumps({"ok": True, **out, "edit": current.to_json()}))
            return 0

        if args.edit_cmd == "description":
            words = [
                w["word"]
                for seg in diarize["segments"]
                for w in seg.get("words", [])
                if edit.start <= w["start"] < edit.end
            ]
            opts = desc_mod.DescriptionOptions(**settings.descriptions.__dict__)
            try:
                out = desc_mod.generate(
                    client, " ".join(words), clip.get("summary", ""), opts,
                    # The title is passed so the description complements it
                    # instead of restating it.
                    {"title": edit.title},
                )
            except Exception as err:  # noqa: BLE001 — surface, don't crash the app
                print(json.dumps({"ok": False, "error": str(err)}))
                return 1
            edits = store.load(job_dir)
            current = edits.get(str(args.clip), edit)
            current.description = out["full"]
            current.description_meta = {
                k: out[k] for k in ("description", "hashtags", "warnings", "chars", "grounded_in")
            }
            edits[str(args.clip)] = current
            store.save(job_dir, edits)
            print(json.dumps({"ok": True, **out, "edit": current.to_json()}))
            return 0

        # hook: rank alternative openings for this clip
        words = [
            {"word": w["word"], "start": w["start"], "end": w["end"]}
            for seg in diarize["segments"]
            for w in seg.get("words", [])
        ]
        sentence_starts = [float(s["start"]) for s in diarize["segments"]]
        opts = hooks_mod.HookOptions(**settings.hooks.__dict__)
        try:
            out = hooks_mod.analyze(
                client, sentence_starts, words, edit.start, edit.end, opts,
                summary=clip.get("summary", ""),
            )
        except Exception as err:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(err)}))
            return 1
        print(json.dumps({"ok": True, **out}))
        return 0

    if args.edit_cmd == "render-clip":
        emit = _progress_printer(args.jsonl)
        try:
            entry = rc.render_clip_edit(job_dir, args.clip, lambda f, m: emit("render", f, m))
        except Exception as err:  # noqa: BLE001
            _emit_result(args.jsonl, {"ok": False, "error": str(err)})
            return 1
        _emit_result(args.jsonl, {"ok": True, "output": entry})
        return 0
    return 2


def cmd_ig(args: argparse.Namespace) -> int:
    from .insights import calibration, instagram

    if args.ig_cmd == "auth-url":
        # Printed so the user can open it themselves and paste the code back.
        # Needed because Meta rejects http:// redirect URIs, so the browser
        # cannot reach our local callback server at all.
        import secrets as pysecrets

        print(json.dumps({
            "ok": True,
            "url": instagram.auth_url(args.app_id, pysecrets.token_urlsafe(16), args.redirect),
            "redirect_uri": instagram.redirect_uri(args.redirect),
        }))
        return 0

    if args.ig_cmd == "connect":
        try:
            conn = instagram.connect(
                args.app_id, args.app_secret,
                open_browser=not args.code,
                code=args.code,
                redirect=args.redirect,
            )
        except instagram.IgError as err:
            print(json.dumps({"ok": False, "error": str(err)}))
            return 1
        print(json.dumps({
            "ok": True,
            "username": conn.get("username"),
            "user_id": conn.get("user_id"),
        }))
        return 0

    # App-facing commands: exactly one JSON line on stdout (the shell's
    # ig_tool parses the last JSON line, same contract as edit_tool).
    if args.ig_cmd == "sync":
        summary = calibration.sync()
        print(json.dumps(summary))
        return 0 if summary.get("ok") else 1

    if args.ig_cmd == "overview":
        print(json.dumps(calibration.overview()))
        return 0

    if args.ig_cmd == "link":
        job = queue.get_job(args.job_id)
        if job is None:
            print(json.dumps({"ok": False, "error": f"no job {args.job_id}"}))
            return 2
        score_data = queue.read_checkpoint(job, "score", 1)
        if not score_data:
            print(json.dumps({"ok": False, "error": "job has no score checkpoint"}))
            return 2
        clips = score_data["clips"]
        if not 0 <= args.clip < len(clips):
            print(json.dumps({"ok": False, "error": f"clip index out of range (0..{len(clips) - 1})"}))
            return 2
        calibration.link_clip(
            args.job_id, args.clip, args.media_id, clips[args.clip],
            link_source=args.source,
            config_version=score_data.get("scoring_config_version", 1),
        )
        print(json.dumps({"ok": True, "linked": {"job_id": args.job_id, "clip": args.clip, "media_id": args.media_id}}))
        return 0

    if args.ig_cmd == "unlink":
        removed = calibration.unlink(args.media_id)
        print(json.dumps({"ok": True, "removed": removed}))
        return 0

    if args.ig_cmd == "reject":
        calibration.reject_match(args.media_id, args.job_id, args.clip)
        print(json.dumps({"ok": True}))
        return 0

    # Human/legacy commands.
    conn = instagram.load_connection()
    if args.ig_cmd in ("media", "pull") and conn is None:
        print("Not connected. Run: publikclip ig connect --app-id ... --app-secret ...", file=sys.stderr)
        return 2
    if conn is not None:
        conn = instagram.refresh_if_needed(conn)

    if args.ig_cmd == "media":
        for m in instagram.recent_media(conn):
            if m.get("media_product_type") == "REELS" or m.get("media_type") == "VIDEO":
                caption = (m.get("caption") or "")[:60].replace("\n", " ")
                print(f"{m['id']}  {m.get('timestamp', '')[:10]}  {caption}")
        return 0

    if args.ig_cmd == "pull":
        rows = calibration.tracked()
        if not rows:
            print("No linked clips yet. Post an exported clip, then: publikclip ig link ...")
            return 0
        for row in rows:
            if not row["ig_media_id"]:
                continue
            try:
                metrics = instagram.media_insights(conn, row["ig_media_id"])
            except instagram.IgError as err:
                print(f"{row['ig_media_id']}: {err}", file=sys.stderr)
                continue
            calibration.store_metrics(row["ig_media_id"], metrics)
            views = metrics.get("views")
            watch = metrics.get("ig_reels_avg_watch_time")
            print(
                f"{row['ig_media_id']}  score {row['score']:.0f} → views {views}, "
                f"avg watch {round(watch / 1000, 1) if watch else '?'}s"
            )
        return 0

    if args.ig_cmd == "report":
        print(json.dumps(calibration.report(args.metric), indent=2))
        return 0
    return 2



def _add_ranking_flags(parser: argparse.ArgumentParser) -> None:
    """E18-F01's two flags, identical on run, resume and `jobs create` so
    enqueueing a job cannot drift from running one."""
    parser.add_argument(
        "--ranking", choices=["on", "off"], default=None,
        help="on: also emit the ranking videos (moments 1..N and N+1..2N) beside the clips",
    )
    parser.add_argument(
        "--ranking-count", dest="ranking_count", type=int, default=None,
        help="how many top moments one ranking video plays; the second takes the next N (default 5)",
    )
    parser.add_argument(
        "--ranking-order", dest="ranking_order", choices=["countdown", "random"], default=None,
        help="the order the moments play in: countdown (N first, 1 last; default) or random "
             "(shuffled once per job and kept, so a re-render plays the same order)",
    )


def _add_mode_flag(parser: argparse.ArgumentParser) -> None:
    """E20's chain choice, on `run` and `jobs create` only — never on
    resume: a job's checkpoints belong to the chain that wrote them."""
    parser.add_argument(
        "--mode", choices=sorted(chains.CHAINS), default=None,
        help="which chain runs: clips (the default) cuts a long video into scored clips; "
             "stories narrates a text over a background video of yours",
    )


def _add_story_flags(parser: argparse.ArgumentParser, with_text: bool) -> None:
    """E20's narrator flags — voice and speed on run, resume and `jobs
    create`; the story file only where a job is created, because the text
    is content copied into the job dir once (F01), not a setting."""
    from .narrate import kokoro_tts

    if with_text:
        parser.add_argument(
            "--story-file", dest="story_file", default=None,
            help="stories mode: a UTF-8 .txt whose first line is the title; copied into the job",
        )
    parser.add_argument(
        "--voice", choices=list(kokoro_tts.VOICE_IDS), default=None,
        help="stories mode: the narrator voice (a generic Kokoro speaker)",
    )
    parser.add_argument(
        "--speed", type=float, default=None,
        help="stories mode: narration speed multiplier, 1.0 = the voice's natural pace",
    )


def _add_watermark_flags(parser: argparse.ArgumentParser) -> None:
    """E19-F02's two flags, identical on run, resume and `jobs create`. No
    choices list: the image is a path and the word is free text, and an
    empty value is the explicit "none"."""
    parser.add_argument(
        "--watermark-image", dest="watermark_image", default=None,
        help="a PNG overlaid bottom-centre on every clip and ranking video; '' for none",
    )
    parser.add_argument(
        "--watermark-text", dest="watermark_text", default=None,
        help="a word burned bottom-centre instead of a picture, when no image is set; '' for none",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="publikclip")
    parser.add_argument("--jsonl", action="store_true", help="machine-readable progress on stdout")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="process a YouTube URL or local video file")
    p_run.add_argument("source")
    p_run.add_argument("--llm", choices=["gemini", "ollama"], default=None)
    p_run.add_argument("--captions", default=None, help="caption preset name")
    p_run.add_argument("--camera", choices=["cut", "pan", "locked"], default=None)
    p_run.add_argument(
        "--gameplay-amount", dest="gameplay_amount", type=float, default=None,
        help="0.0 (podcast/tight face crop) .. 1.0 (gameplay/full-frame letterboxed)",
    )
    p_run.add_argument(
        "--letterbox-fill", dest="letterbox_fill", choices=["black", "blur"], default=None,
        help="what fills the bars once framing letterboxes: black bars or a blurred copy",
    )
    _add_ranking_flags(p_run)
    _add_watermark_flags(p_run)
    _add_mode_flag(p_run)
    _add_story_flags(p_run, with_text=True)
    p_run.set_defaults(fn=cmd_run)

    p_resume = sub.add_parser("resume", help="resume a job from its checkpoints")
    p_resume.add_argument("job_id")
    p_resume.add_argument("--llm", choices=["gemini", "ollama"], default=None)
    p_resume.add_argument("--captions", default=None, help="caption preset name")
    p_resume.add_argument("--camera", choices=["cut", "pan", "locked"], default=None)
    p_resume.add_argument(
        "--gameplay-amount", dest="gameplay_amount", type=float, default=None,
        help="0.0 (podcast/tight face crop) .. 1.0 (gameplay/full-frame letterboxed)",
    )
    p_resume.add_argument(
        "--letterbox-fill", dest="letterbox_fill", choices=["black", "blur"], default=None,
        help="what fills the bars once framing letterboxes: black bars or a blurred copy",
    )
    _add_ranking_flags(p_resume)
    _add_watermark_flags(p_resume)
    _add_story_flags(p_resume, with_text=False)
    # chains.ALL_STAGES is the light-import union of every chain's stages
    # (a test pins each chain equal to cli._stages()); argparse must not
    # pay the torch tax, and it cannot know the job's chain yet — cmd_resume
    # applies that gate once it has the job.
    p_resume.add_argument(
        "--from-stage", dest="from_stage", choices=list(chains.ALL_STAGES),
        default=None,
        help="invalidate this stage first, so the run re-does it and everything after (T-14)",
    )
    p_resume.set_defaults(fn=cmd_resume)

    p_hw = sub.add_parser(
        "hardware", help="probe the machine, update hardware_profile.json, print it"
    )
    p_hw.set_defaults(fn=cmd_hardware)

    p_diag = sub.add_parser(
        "diagnose", help="build a redacted, inspectable diagnostic zip for one job (T-15)"
    )
    p_diag.add_argument("job_id", nargs="?", default=None, help="defaults to the most recent job")
    p_diag.add_argument("--out", default=None, help="zip path (default: inside the job dir)")
    p_diag.set_defaults(fn=cmd_diagnose)

    p_setup = sub.add_parser(
        "setup", help="fetch everything a first job would download (resumable; kill-safe)"
    )
    setup_sub = p_setup.add_subparsers(dest="setup_cmd", required=False)
    setup_sub.add_parser("status", help="what is present and what is missing, from disk")
    setup_sub.add_parser("run", help="fetch what is missing (the default)")
    p_setup.set_defaults(fn=cmd_setup)

    p_jobs = sub.add_parser("jobs", help="list jobs (with --jsonl: one JSON object per job)")
    jobs_sub = p_jobs.add_subparsers(dest="jobs_cmd", required=False)
    p_mark = jobs_sub.add_parser(
        "mark-cancelled",
        help="bookkeeping after the shell hard-kills a job: status, marker, cleanup",
    )
    p_mark.add_argument("job_id")
    p_create = jobs_sub.add_parser("create", help="enqueue a job without running it (T-08)")
    p_create.add_argument("source")
    p_create.add_argument("--llm", choices=["gemini", "ollama"], default=None)
    p_create.add_argument("--captions", default=None, help="caption preset name")
    p_create.add_argument("--camera", choices=["cut", "pan", "locked"], default=None)
    p_create.add_argument(
        "--gameplay-amount", dest="gameplay_amount", type=float, default=None,
        help="0.0 (podcast/tight face crop) .. 1.0 (gameplay/full-frame letterboxed)",
    )
    p_create.add_argument(
        "--letterbox-fill", dest="letterbox_fill", choices=["black", "blur"], default=None,
        help="what fills the bars once framing letterboxes: black bars or a blurred copy",
    )
    _add_ranking_flags(p_create)
    _add_watermark_flags(p_create)
    _add_mode_flag(p_create)
    _add_story_flags(p_create, with_text=True)
    jobs_sub.add_parser("next", help="print the next pending job id, or null")
    p_ri = jobs_sub.add_parser(
        "resume-info", help="per-stage status + measured re-run cost for the resume picker (T-14)"
    )
    p_ri.add_argument("job_id")
    jobs_sub.add_parser("reconcile", help="app-start bookkeeping for ghost 'running' rows")
    p_cp = jobs_sub.add_parser("cancel-pending", help="cancel a job that has not started")
    p_cp.add_argument("job_id")
    p_jobs.set_defaults(fn=cmd_jobs)

    p_set = sub.add_parser("settings", help="read/write global settings + caption presets")
    set_sub = p_set.add_subparsers(dest="settings_cmd", required=True)
    set_sub.add_parser("get")
    p_set_set = set_sub.add_parser("set")
    p_set_set.add_argument("json", help="full settings tree as JSON")
    set_sub.add_parser("reset")
    p_preset = set_sub.add_parser("preset-save")
    p_preset.add_argument("name")
    p_preset.add_argument("json", help="partial preset patch as JSON (hex colours)")
    p_preset_reset = set_sub.add_parser("preset-reset")
    p_preset_reset.add_argument("name")
    p_wm = set_sub.add_parser(
        "watermark-import",
        help="copy a PNG into the app's watermark folder and print its stored path (E19-F02)",
    )
    p_wm.add_argument("path")
    set_sub.add_parser(
        "story-limits",
        help="the story word limits, the words-per-minute estimate and the voices (E20)",
    )
    p_sr = set_sub.add_parser(
        "story-read", help="read a UTF-8 .txt for the deck's story field, with its word count (E20)"
    )
    p_sr.add_argument("path")
    p_bg = set_sub.add_parser(
        "remember-background",
        help="save a background video path as the default the next story starts from (E20)",
    )
    p_bg.add_argument("path")
    p_set.set_defaults(fn=cmd_settings)

    p_edit = sub.add_parser("edit", help="per-clip editing (context / visuals / render)")
    edit_sub = p_edit.add_subparsers(dest="edit_cmd", required=True)
    p_ctx = edit_sub.add_parser("context")
    p_ctx.add_argument("job_id")
    p_ctx.add_argument("clip", type=int)
    p_sv = edit_sub.add_parser("suggest-visuals")
    p_sv.add_argument("job_id")
    p_sv.add_argument("clip", type=int)
    p_sv.add_argument("--prefer", choices=["pexels", "gemini"], default="pexels")
    p_titles = edit_sub.add_parser("titles", help="generate title options for one clip")
    p_titles.add_argument("job_id")
    p_titles.add_argument("clip", type=int)
    p_desc = edit_sub.add_parser("description", help="generate the post description for one clip")
    p_desc.add_argument("job_id")
    p_desc.add_argument("clip", type=int)
    p_hook = edit_sub.add_parser("hook", help="rank alternative openings for one clip")
    p_hook.add_argument("job_id")
    p_hook.add_argument("clip", type=int)
    p_rcl = edit_sub.add_parser("render-clip")
    p_rcl.add_argument("job_id")
    p_rcl.add_argument("clip", type=int)
    p_edit.set_defaults(fn=cmd_edit)

    p_ig = sub.add_parser("ig", help="Instagram feedback loop (your own Meta app)")
    ig_sub = p_ig.add_subparsers(dest="ig_cmd", required=True)
    p_authurl = ig_sub.add_parser("auth-url", help="print the authorization URL to open (JSON)")
    p_authurl.add_argument("--app-id", required=True)
    p_authurl.add_argument("--redirect", default=None, help="redirect URI registered in your Meta app")
    p_connect = ig_sub.add_parser("connect", help="OAuth against your own Meta app")
    p_connect.add_argument("--app-id", required=True)
    p_connect.add_argument("--app-secret", required=True)
    p_connect.add_argument(
        "--code", default=None,
        help="authorization code (or the whole redirected URL) pasted back from the browser",
    )
    p_connect.add_argument("--redirect", default=None, help="redirect URI registered in your Meta app")
    ig_sub.add_parser("sync", help="one sync pass: media + thumbnails + insights ladder + auto-fit (JSON)")
    ig_sub.add_parser("overview", help="everything the Loop screen renders (JSON)")
    ig_sub.add_parser("media", help="list your recent Reels to link against")
    p_link = ig_sub.add_parser("link", help="link a rendered clip to a posted Reel (JSON)")
    p_link.add_argument("job_id")
    p_link.add_argument("clip", type=int)
    p_link.add_argument("media_id")
    p_link.add_argument("--source", default="manual", choices=["manual", "match_confirmed"])
    p_unlink = ig_sub.add_parser("unlink", help="remove a clip↔Reel link (JSON)")
    p_unlink.add_argument("media_id")
    p_reject = ig_sub.add_parser("reject", help="'not this' — never suggest this pair again (JSON)")
    p_reject.add_argument("media_id")
    p_reject.add_argument("job_id")
    p_reject.add_argument("clip", type=int)
    ig_sub.add_parser("pull", help="fetch metrics for every linked clip")
    p_report = ig_sub.add_parser("report", help="score-vs-outcome calibration report")
    p_report.add_argument("--metric", default="views")
    p_ig.set_defaults(fn=cmd_ig)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
