"""Alias Studio CLI.

Doubles as the desktop app's sidecar: with --jsonl every progress event and
the final result are emitted as one JSON object per stdout line, so the
Tauri shell just spawns `publikclip --jsonl run <source>` and streams.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config, winpatches
from .jobs import queue

winpatches.apply_all()


def _stages() -> list[queue.Stage]:
    # Grows per milestone: ingest → asr → diarize → events → candidates →
    # score → camera → render. Stage imports are deferred so `publikclip
    # jobs` doesn't pay the torch import tax.
    from .asr.stage import AsrStage
    from .camera.stage import CameraStage
    from .candidates.stage import CandidatesStage
    from .diarize.stage import DiarizeStage
    from .events.stage import EventsStage
    from .ingest.stage import IngestStage
    from .render.stage import RenderStage
    from .scoring.stage import ScoreStage

    return [
        IngestStage(),
        AsrStage(),
        DiarizeStage(),
        EventsStage(),
        CandidatesStage(),
        ScoreStage(),
        CameraStage(),
        RenderStage(),
    ]


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


def cmd_run(args: argparse.Namespace) -> int:
    source = args.source
    source_type = "url" if source.startswith(("http://", "https://")) else "file"
    # New jobs start from the user's saved global settings; CLI flags below
    # override just those fields. Existing jobs keep their own snapshot.
    settings = config.load_defaults()
    if args.llm:
        settings.llm_mode = args.llm
    if args.captions:
        settings.caption_preset = args.captions
    if args.camera:
        settings.camera.speaker_change = args.camera
    if args.gameplay_amount is not None:  # 0.0 is a legitimate value, not falsy-skippable
        settings.camera.gameplay_amount = args.gameplay_amount
    job = queue.create_job(source_type, source, json.dumps(settings.to_json()))
    return _execute(job, args.jsonl)


def cmd_resume(args: argparse.Namespace) -> int:
    job = queue.get_job(args.job_id)
    if job is None:
        print(f"No job {args.job_id}", file=sys.stderr)
        return 2
    if args.llm or args.captions or args.camera or args.gameplay_amount is not None:
        settings = config.Settings.from_json(json.loads(job.settings_json))
        if args.llm:
            settings.llm_mode = args.llm
        if args.captions:
            settings.caption_preset = args.captions
        if args.camera:
            settings.camera.speaker_change = args.camera
        if args.gameplay_amount is not None:
            settings.camera.gameplay_amount = args.gameplay_amount
        # Updates the DB row AND the job-dir snapshot; the clip editor reads
        # the latter, so writing only one leaves the job disagreeing with
        # itself about its own settings.
        job = queue.update_settings(job.id, json.dumps(settings.to_json()))
    return _execute(job, args.jsonl)


def _execute(job: queue.Job, jsonl: bool) -> int:
    emit = _progress_printer(jsonl)
    if jsonl:
        print(json.dumps({"event": "job", "job_id": job.id, "dir": str(job.dir)}), flush=True)
    else:
        print(f"job {job.id} → {job.dir}", file=sys.stderr)
    # Resolve (and fetch if missing) ffmpeg once, up front — several stages
    # (ingest merging, ASR decoding, rendering) need it and some, like
    # whisperx's ASR step, shell out to a bare `ffmpeg` on PATH rather than
    # asking us for the path, so it must be in place before any stage runs.
    from .render import ffmpeg_bin

    ffmpeg_bin.ensure_capable(progress=lambda f, m: emit("setup", f, m))
    try:
        results = queue.run_stages(job, _stages(), emit)
    except queue.StageError as err:
        _emit_result(jsonl, {"ok": False, "job_id": job.id, "error": str(err)})
        return 1
    summary = {
        "ok": True,
        "job_id": job.id,
        "stages": list(results.keys()),
        "title": results.get("ingest", {}).get("title"),
        "heatmap_segments": len(results.get("ingest", {}).get("heatmap") or []),
    }
    _emit_result(jsonl, summary)
    return 0


def cmd_jobs(args: argparse.Namespace) -> int:
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
            suggestions = visuals.suggest(job_dir, words, settings.llm_mode, prefer=args.prefer)
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
            client = llm_mod.make_client(settings.llm_mode)
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
    p_resume.set_defaults(fn=cmd_resume)

    p_jobs = sub.add_parser("jobs", help="list jobs")
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
