# Alias Studio — Specification

Everything a new developer needs to understand this project and work on it
without prior briefing. Written against commit `3dc43c1` (2026-08-22); §5, §15
and §17 re-verified against the code on 2026-08-26 (T-23), after T-06, T-21,
T-22 and T-24.

Companion documents: [README.md](README.md) is the user-facing pitch;
[VENDORED-LICENSES.md](VENDORED-LICENSES.md) covers third-party code;
[PRIVACY.md](PRIVACY.md) names every network call the app can make (T-17 —
guarded by a test, shown verbatim under Settings → Privacy);
[CLAUDE.md](CLAUDE.md) is the working rules and **wins on any conflict with
this file**; this file is the engineering reference for how the built thing
works.

---

## Table of contents

1. [What the product is](#1-what-the-product-is)
2. [Architecture at a glance](#2-architecture-at-a-glance)
3. [Repository layout](#3-repository-layout)
4. [The pipeline: eight stages](#4-the-pipeline-eight-stages)
5. [The checkpoint contract](#5-the-checkpoint-contract)
6. [Settings](#6-settings)
7. [Per-clip editing](#7-per-clip-editing)
8. [The desktop shell](#8-the-desktop-shell)
9. [The frontend](#9-the-frontend)
10. [Data on disk](#10-data-on-disk)
11. [Models and external services](#11-models-and-external-services)
12. [Hardware and performance](#12-hardware-and-performance)
13. [The Instagram feedback loop](#13-the-instagram-feedback-loop)
14. [Development setup](#14-development-setup)
15. [Testing](#15-testing)
16. [Building and installing](#16-building-and-installing)
17. [Conventions and house rules](#17-conventions-and-house-rules)
18. [Change history: what this build added](#18-change-history-what-this-build-added)
19. [Known limitations and deferred work](#19-known-limitations-and-deferred-work)
20. [Troubleshooting](#20-troubleshooting)
21. [Licensing](#21-licensing)

---

## 1. What the product is

A desktop application that takes **one long horizontal video** — a YouTube URL
or a local file — and produces **several short vertical (9:16) clips**, each
one scored, captioned, reframed and ready to post.

Three properties define the design:

- **Everything runs locally.** Media never leaves the machine. The only
  network calls are model-weight downloads, the optional LLM scoring pass, and
  the optional Instagram feedback loop. An Ollama mode removes the LLM call
  too.
- **The score is auditable.** A clip never ships as a bare number. It carries
  its subscores, which detectors fired, and every adjustment applied, so a
  user can disagree with the ranking on evidence.
- **Every knob is real.** A setting that nothing in the pipeline reads is
  treated as a bug, and there is a test that fails when a whole settings group
  goes unread ([§17](#17-conventions-and-house-rules)).

This repository is **Alias Studio**, a modified build of the open-source
[publikclip](https://github.com/Blueturboguy07/publikclip). Both are AGPL-3.0.
See [§18](#18-change-history-what-this-build-added) for what this fork changed.

---

## 2. Architecture at a glance

Three processes, one direction of control:

```
┌─────────────────────────────────────────────────────────┐
│  React frontend (TypeScript, Vite)                      │
│  app/src/ — screens, no business logic                  │
└──────────────────────┬──────────────────────────────────┘
                       │  @tauri-apps/api  invoke() / listen()
┌──────────────────────▼──────────────────────────────────┐
│  Rust shell (Tauri v2)                                  │
│  app/src-tauri/src/main.rs — ~544 lines, no logic       │
│  spawns the sidecar, relays JSONL as Tauri events       │
└──────────────────────┬──────────────────────────────────┘
                       │  uv run publikclip … --jsonl
                       │  stdout: JSONL progress
                       │  stderr: captured for the console
┌──────────────────────▼──────────────────────────────────┐
│  Python pipeline (the product)                          │
│  pipeline/publikclip_pipeline/ — ~11 000 lines          │
│  eight stages, checkpointed to disk                     │
└─────────────────────────────────────────────────────────┘
```

**The Rust layer holds no product logic.** It resolves where the sidecar
lives, spawns it without flashing a console window, forwards JSONL lines as
Tauri events, and reads job artifacts off disk. Anything you would want to
unit-test belongs in Python.

**The frontend holds no product logic either.** It renders what the sidecar
reports and sends back user intent. Where the UI needs to preview something
(the clip editor's crop preview, the dead-space timeline), the preview must
resolve its numbers the same way the render does — if they drift, the user
sees one thing and gets another. `edits/timeline.py:resolve_pacing()` exists
specifically to keep one such calculation in a single place.

**Artifacts on disk are the source of truth.** The SQLite database records
only what *should* exist so a stage can decide whether to skip itself. If the
database and the disk disagree, the disk wins.

---

## 3. Repository layout

```
publikclip/
├── LICENSE                       AGPL-3.0
├── README.md                     user-facing description
├── VENDORED-LICENSES.md          third-party attribution
├── SPECIFICATION.md              this file
│
├── pipeline/                     the Python product
│   ├── pyproject.toml            deps, CUDA index config, entry point
│   ├── uv.lock
│   ├── publikclip_pipeline/
│   │   ├── cli.py                argparse surface; the sidecar's entry point
│   │   ├── config.py             the whole settings tree + paths
│   │   ├── settings_schema.py    UI schema for the settings panel
│   │   ├── hardware.py           CUDA/CPU detection
│   │   ├── winpatches.py         Windows-specific runtime patches
│   │   │
│   │   ├── jobs/queue.py         Job/Stage machinery, SQLite, checkpoints
│   │   │
│   │   ├── ingest/               stage 1  — download, normalise, heatmap
│   │   ├── asr/                  stage 2  — whisperX transcription
│   │   ├── diarize/              stage 3  — CAM++ speaker turns
│   │   ├── events/               stage 4  — laughter/reaction timeline
│   │   ├── candidates/           stage 5  — interest curve → windows
│   │   ├── scoring/              stage 6  — LLM rubric + composites
│   │   ├── camera/               stage 7  — active-speaker crop paths
│   │   ├── render/               stage 8  — ffmpeg → finished MP4s
│   │   │
│   │   ├── captions/             ASS subtitle generation + fonts
│   │   ├── copywriting/          titles, descriptions, hooks, moment labels
│   │   ├── edits/                per-clip editing + single-clip render
│   │   ├── insights/             Instagram feedback loop
│   │   ├── models/               weight registry + specs
│   │   ├── music/                music brief generation
│   │   └── vendor/               vendored third-party code (~1 400 lines)
│   └── tests/                    275 tests
│
└── app/                          the desktop shell
    ├── package.json
    ├── scripts/prepare-resources.mjs   stages pipeline+uv for bundling
    ├── src/                      React frontend (~3 900 lines)
    │   ├── App.tsx               view router + job lifecycle
    │   ├── api.ts                every invoke() in one place
    │   ├── types.ts              the shapes the sidecar returns
    │   ├── styles.css            all styling, incl. themes
    │   └── components/
    │       ├── Studio.tsx        the main screen: submit a link
    │       ├── Review.tsx        clip analysis, restyle, descriptions
    │       ├── ClipEditor.tsx    per-clip fine-tuning
    │       ├── Settings.tsx      schema-generated settings panel
    │       ├── Loop.tsx          Instagram feedback screen
    │       ├── Onboarding.tsx    first-run setup
    │       ├── IgModal.tsx       Instagram OAuth entry
    │       ├── KeyModal.tsx      API key entry
    │       └── ThemeSwitcher.tsx
    └── src-tauri/
        ├── src/main.rs           the whole Rust layer
        ├── tauri.conf.json
        └── Cargo.toml
```

---

## 4. The pipeline: eight stages

Registered in order in [cli.py:34-41](pipeline/publikclip_pipeline/cli.py#L34-L41).
Each is a `Stage` subclass with `name`, `schema_version`, `run()` and
`artifacts_ok()`.

The chain is **linear**: every stage consumes the outputs of the ones before
it. That is why a stage that re-runs invalidates everything after it
([§5](#5-the-checkpoint-contract)).

### 1. `ingest` — URL or file → media + analysis audio + heatmap

`ingest/stage.py`, with `ytdlp.py` (managed yt-dlp binary) and
`normalize.py`.

Downloads the source, normalises it into the job directory, extracts two WAV
files (`audio16k.wav` for speech models, `audio32k.wav` for audio-event
models), and pulls YouTube's replay heatmap when the source has one. Produces
`media.mp4`, and `media_cfr.mp4` where a constant frame rate is needed.

### 2. `asr` — speech → word-level timestamps

`asr/stage.py`. whisperX 3.8.6 (BSD-2-Clause), model `large-v3-turbo`, batch
size 8, with Silero VAD instead of whisperX's bundled VAD.

Word-level timestamps are the substrate for **everything downstream** —
captions, sentence-snapping of clip boundaries, dead-space detection, the
lexical interest channel. Two models load in sequence (transcription, then
forced alignment); the ASR weights are freed before the alignment model loads,
because peak RSS on a long source otherwise becomes the binding constraint.

Device selection goes through `hardware.whisper_device()`, which returns
`("cuda", "float16")` or `("cpu", "int8")`. Alignment follows
`hardware.torch_device()` separately — ctranslate2's CUDA support is
independent of torch's, so the two are resolved independently.

**First run downloads ~1.6 GB.**

### 3. `diarize` — who spoke when

`diarize/stage.py`, `campplus.py`, `cluster.py`.

CAM++ speaker embeddings over the ASR speech windows, clustered into speaker
turns, then merged back into the transcript as word-level speaker labels.
Embeddings are cached to `diar_embeddings.npy`.

Consumed by the camera director (to know whose face to hold on) and by the
`turns` interest channel.

### 4. `events` — the shared audio-event timeline

`events/stage.py`, with `panns_channel.py`, `ser.py`, `dsp.py`, `post.py`.

**This is the architectural spine.** Four channels:

- **jrgillick laughter specialist** — native ~43 fps, high precision, ~300k
  CPU forward passes on a long source. **Off by default**
  (`Settings.laughter_specialist`).
- **PANNs Cnn14_DecisionLevelMax** — laugh/gasp/scream/shout/applause/cheer at
  320 ms resolution. This is the default detector.
- **Transcript long pauses.**
- **DSP energy/flux/dynamics curves** — continuous signals, not events.

Fusion: per-channel DCASE post-processing, then IOU-0.4 cross-model merge
where agreement boosts confidence. Laughter is the only event type with two
independent detectors, deliberately: it drives the most visible behaviour
(punch-ins, `[laughs]` caption tags, humour-score corroboration), so it gets
the redundancy.

Computed **exactly once**, then consumed by scoring, captions, the camera
director and the music brief.

Writes `curves.json` (the continuous signals) and the event timeline.

### 5. `candidates` — interest curve → candidate windows

`candidates/stage.py`, `curve.py`, `windows.py`.

Builds seven free (non-LLM) channels and weighs them into one interest curve:

| Channel | Source |
|---|---|
| `heatmap` | YouTube replay graph (all-zero on most sources) |
| `dynamics` | audio energy |
| `events` | detected reactions |
| `turns` | conversation rate |
| `arousal` | vocal arousal (SER) |
| `scenes` | visual change |
| `lexical` | power words in the transcript |

Weights are user-configurable (`Settings.curve`). Channels that are entirely
zero are dropped from the weighted sum rather than dragging it down, so a
source without a heatmap scores the same as one with a flat heatmap.

Peaks become ~35 sentence-snapped candidate windows. **No LLM spend happens
here** — this count is the cost gate for the next stage.

### 6. `scoring` — rubric, ranking, provenance

`scoring/stage.py`, `rubric.py`, `llm.py`, `frames.py`, `constants.py`.

Two tiers:

- **T1** — one text-rubric call per candidate (~35 calls).
- **T2** — a vision pass on the finalists only (~12 calls), plus a music
  brief per finalist.

Cost shape on Gemini Flash: ~35 + ~12 + ~12 calls per video. **In Ollama mode
T2 is skipped** and recorded as a missing input rather than silently scored as
zero.

Two LLM backends behind one interface in `llm.py`:

- `GeminiClient` — model `gemini-3.6-flash` by default, overridable per job
  via `Settings.gemini_model` (T-39: the rolling `gemini-flash-latest` alias
  died under this product with persistent 503s, so the pin is a stable
  versioned id and the setting is the user's escape hatch when Google
  retires it). Key resolution order: `PUBLIKCLIP_GEMINI_API_KEY` env var,
  then the stored key.
- `OllamaClient` — local, auto-picks an installed model.

Responses are cached on a hash of (backend, model, prompt, schema, images), so
a re-run does not re-pay for identical calls. Retries back off using the delay
the error body asks for.

The composite score combines the free signals with the LLM tiers, weighted by
`Settings.scoring` and per-platform weights. **LLM humour scores are
discounted when no actual laughter corroborates them** — the single most
important guard against a model confidently rating an unfunny clip.

Output carries full provenance: subscores, which detectors fired, and every
adjustment applied.

### 7. `camera` — active-speaker crop paths

`camera/stage.py`, `director.py`, `detect.py`, `asd.py`, `tracks.py`.

Runs **only over the selected finalists**, not the whole source. This is the
single biggest compute saving against reference implementations that reframe
the entire hour.

Per clip:

1. UltraFace detects faces.
2. LR-ASD decides which detected face is speaking.
3. Speaker turns from stage 3 are fused with the ASD signal.
4. The result is smoothed into a per-frame crop path.

Key concepts in `director.py`:

- **`_resolve_content_box(gameplay_amount, src_w, src_h)`** — the framing
  dial. At `0.0` it reproduces the tight 9:16 face crop (which on a 16:9
  source is only ~31.7% of the frame width). At `1.0` the crop is the entire
  source frame, letterboxed by the renderer. Linear in between. Only the axis
  that is not already full grows, so the dial is a true no-op for sources that
  already fill one dimension.
- **Speaker-change behaviour** — `cut` (hard cut), `pan`, or `locked`.
- **Deadzone** — the crop holds still until the target moves beyond
  `deadzone_frac`, so small head movements do not produce a drifting frame.
- **Punch-ins** — transient zooms fired by laughter and vocal energy, shaped
  by `Settings.retention` (strength, frequency, rise/hold/fall times).

Writes `trajectory_NN.json` per clip: `frames`, `cuts`, `punches`,
`content_w`, `content_h`, `meta`.

**Per-clip framing overrides are applied here** — see
[§7](#7-per-clip-editing).

### 8. `render` — finished MP4s

`render/stage.py`, `renderer.py`, `ffmpeg_bin.py`.

One ffmpeg graph per clip:

```
sendcmd → crop@c → scale/pad (or blur letterbox) → setsar → subtitles → loudnorm
```

- `sendcmd` animates the crop rect from the trajectory.
- `scale_pad_vf(content_w, content_h, fill)` handles the case where the crop's
  aspect ratio is not 9:16 (the gameplay end of the dial). With `fill="black"`
  it pads with black bars; with `fill="blur"` it splits the stream, scales one
  copy to cover and blurs it (`gblur=sigma=22`) as a background, and overlays
  the correctly-scaled foreground on top.
- Captions are burned in from a generated ASS file.
- Audio is normalised to `Settings.lufs_target` / `true_peak_db`.

`ffmpeg_bin.py` resolves ffmpeg and, if the available binary cannot burn
subtitles, fetches a capable static build. `encoder_works()` **probes** the
hardware encoder by actually encoding a frame rather than trusting the
`-encoders` listing — NVENC is listed on machines whose driver is too old to
use it.

Every output is verified (`verify_output`: streams present, duration sane)
before it is reported.

**Per-clip style overrides are applied here**, and clips with structural edits
are protected — see [§7](#7-per-clip-editing).

**Ranking mode (E18).** With `Settings.ranking.enabled` the stage renders its
clips exactly as in clip mode and then, from the same finalists, up to two
ranking videos (D-18: as well as the clips, never instead — D-17's one-format
clause is reversed; the play-order reveal and the absence of label editing
stand). The top `ranking.count` finalists with a trajectory make
`clips/ranking_1-5.mp4` and the next N make `clips/ranking_6-10.mp4`
(E18-F06); the second exists only as a full N, so both are the same "TOP N",
and when there are not 2N finalists the stage makes one and says why, naming
`clips.select_count` when that is the reason. Every segment goes through the
same `render_clip` as a standalone clip would, with the list for that segment
(`captions/ranking.py`) spliced into its own ASS document — the list is static
within a segment, so it rides the one subtitles burn — and a 15 ms audio edge
fade. The segments are then joined by `renderer.concat_copy`, a concat-demuxer
remux: the video is encoded once and the montage carries no second lossy
generation. Segment files are deleted once the montage verifies; their ASS
documents stay; the previous render's montage files are unlinked before new
ones are written, since their names carry the rank range. One band for the
whole series, sized from the tightest top bar among every segment of both
videos, so the list never moves at a cut and never differs between them; at
podcast framing there is no bar and it is drawn over the picture behind a
translucent band — the owner's decision, recorded in that module.
Structurally-edited clips keep their editor file as clip entries but are not
adopted into a montage (the segment needs the list burned in); that segment
renders from job settings and the stage says so. The checkpoint is the
clip-mode checkpoint with the montage entries appended to `outputs` — clip
entries first, each montage entry carrying `montage: true`, `ranks`, and its
rank-1 clip's index so the review panel's audit shows the winning moment — plus
a `ranking` key (`count`, `band`, `montages` — one record per video with
`path`, `ranks`, `rendered`, `order`, `title`, `segments` — `note`, `labels`,
`label_errors`). `artifacts_ok` tells three shapes apart: no `ranking` key is
a clip checkpoint and serves a clip job; a `ranking` without `montages` is the
one-montage checkpoint E18-F02..F04 wrote, which has no clip files and now
serves nothing, so those few re-render once; `ranking.montages` serves a
ranking job with the same count. Crosswise stays invalid: switching the mode
re-renders (E18-F01).

**Moment labels (E18-F04).** Before the first segment of any video is
encoded, the stage asks, once for every moment of both videos,
`copywriting/labels.py` for the one to three words next to each number —
one LLM call per moment, the title engine's honesty rule in the prompt and
a filter behind it (over three words, sentence punctuation, empty, over the
column budget: rejected, never trimmed, because the text goes into pixels
nobody can edit). An answer the filter rejects earns exactly one retry whose
prompt names the actual reason and limit; a failed call — network, API, the
breaker — never does, because that endpoint is already failing and a second
call would re-spend on it. A label is an output of the render, not a setting of it:
`ranking.labels` keys each moment's clip index to `{text, grounded_in,
start, end}`, a later render reuses every stored label for the same moment
(bounds, not just index) verbatim and builds no client when nothing is
missing, and `artifacts_ok` never reads them — a model's word choice must
not invalidate a render, and the same job re-rendered burns the same words.
A moment that gets no label (client unbuildable, call failed, answer
rejected) plays with its number alone, the reason in `ranking.label_errors`;
a re-run of the stage retries it, a cached render keeps the blank. Clip mode
makes no LLM call. Nothing regenerates or edits a label in this version
(D-17). This is the one copywriting engine called from inside a stage;
`copywriting/__init__.py` says why.

---

## 5. The checkpoint contract

This is the part most likely to bite a new contributor.

Every stage writes its result to `<job_dir>/<stage>.json`:

```json
{"stage": "render", "schema_version": 1, "created_at": "...", "data": { ... }}
```

On the next run, `run_stages()`
([jobs/queue.py:296](pipeline/publikclip_pipeline/jobs/queue.py#L296)) asks
each stage `artifacts_ok(ctx, data)`: *given the current settings, is this
cached result still correct?*

Three rules:

**1. `artifacts_ok` must diff every setting that changes its output.**
If a stage bakes a setting into its artifacts but does not compare it, the
setting appears to do nothing — the stage happily serves the old result. This
has been a real bug three separate times in this codebase.

**2. A stage that re-runs invalidates every stage after it.**
`run_stages` tracks `upstream_stale`. Without it, a settings change could
recompute an upstream stage while a downstream stage served output derived
from the *old* upstream data — new candidate windows with stale scores, or a
re-directed camera whose trajectories never reach a cached render.

**3. A missing fingerprint key is compared against the factory default.**
Checkpoints written before a setting existed lack its key. Comparing the
missing key against the current value would throw away an hour of
transcription because someone added an unrelated toggle.
`fingerprint_ok(stored, current, factory)` treats a missing key as the
factory value: untouched settings survive, genuinely changed ones re-run.
"Missing means unchanged" is the wrong summary — it is unchanged only while
the current value is still the default.

Note the shape of `fingerprint_ok` itself: `stored=None` returns `False`
immediately, so a checkpoint with *no* fingerprint key at all re-runs. When a
fingerprint is added to a stage that never had one, every checkpoint on disk
is in exactly that position, which is why those call sites pass
`data.get(key) or {}` — an empty dict routes each missing key to the factory
comparison rather than failing the whole check. `camera`'s `clip_framing` and
`events`' `settings_used` both do this.

### What each stage currently fingerprints

All eight, because a two-row version of this table is how a shipped setting
once stayed dead for a release: the stages absent from it looked like stages
that did not need one.

| Stage | `artifacts_ok` asks | Rule 3? |
|---|---|---|
| `ingest` | media + `audio16k.wav` exist; `source_hash` still matches | n/a |
| `asr` | **no override** — reads zero settings, so nothing can invalidate it | n/a |
| `diarize` | **no override** — same | n/a |
| `events` | `curves.json` exists, then `fingerprint_ok` on `laughter_specialist` | yes |
| `candidates` | `fingerprint_ok` on `clips`, `curve` and the scene-detector settings | yes |
| `scoring` | `fingerprint_ok` on `settings_used` (model + weights + word gate) | yes (T-39) |
| `camera` | strict `!=` on `camera_settings` (minus `letterbox_fill`, which is render-only and used to re-run the whole DIRECT pass) and `retention_settings`, plus `clip_framing` | no |
| `render` | strict comparisons on `caption_preset`, `caption_style`, `audio`, `encoder`, `clip_edits`, plus a versioned camera compare: checkpoints carrying a `fills` map (E6-F09) compare `camera_settings` minus `letterbox_fill` and the **resolved** per-clip fill (explicit per-clip value, else the job default), so a default change re-renders only jobs it actually reaches; older checkpoints keep the full strict `camera_settings` compare, byte for byte. **Output unit first (E18):** a checkpoint carrying a `ranking` key serves only a job with `ranking.enabled`, and vice versa, with a strict compare on `ranking.count`; the `fills` map is recomputed over the montage's segments (`_fill_keys`) rather than its one output entry. Checkpoints from before the key existed lack it and the mode defaults off, so nothing on disk re-rendered when the feature arrived | no |

**`fingerprint_ok` has three callers** — `candidates`, `events` and, since
T-39, `scoring` (the naive strict fix for the new `gemini_model` key would
have rescored every job on disk under the new model, missing the LLM cache
and re-spending real API money). `camera` and `render` still compare
strictly, so rule 3 does *not* hold there: adding a field to
`CameraSettings` or the render fingerprint invalidates every existing
checkpoint for that stage. That is a known gap, not a design intent.

`camera`'s `clip_framing` is the only fingerprint that reaches outside
`Settings` — it reads `clip_edits.json` off disk, so a per-clip framing
override invalidates the trajectory even when no job-level setting moved.

`caption_style` resolves the preset through the same layers the renderer uses
(built-in → saved edits → job overrides), so editing a *saved preset* — not
just a job override — also invalidates the render.

Each fingerprint deliberately covers **only** what that stage reads. A title
edit must not force a re-encode; a caption tweak must not re-run the expensive
camera pass.

**Resume from a chosen stage (T-14 / E14-F02)** rides this contract rather
than adding one: `queue.invalidate_stage` deletes the chosen stage's
checkpoint and rule 2's cascade re-runs everything after. The exception is
`render`, whose checkpoint is also the adoption map for editor-reshaped
clips (`_previous_outputs`) — there the invalidation deletes the
reproducible clips' FILES instead (T-07's mechanism), keeping `render.json`
and every structurally-edited clip's file intact. The picker's per-stage
cost line is T-10's measured medians × the job's duration, summed over the
chosen stage and its tail, and absent unless every tail stage has a sample
under the current hardware key.

The tests for this section are `tests/test_clip_edit_sync.py` (28) and, for
rule 2 specifically, `test_queue.py:test_a_rerun_stage_invalidates_every_stage_after_it`.
`tests/test_house_rules.py` does **not** cover the checkpoint contract.

---

## 6. Settings

### The tree

`config.Settings` ([config.py](pipeline/publikclip_pipeline/config.py)) is the
whole tunable surface, grouped by what it controls:

| Group | Controls |
|---|---|
| `clips` | target/min/max length, how many to render, candidate pool size, sentence snap radius, overlap dedupe, peak spacing |
| `curve` | the seven interest-channel weights |
| `scoring` | signal-vs-AI balance, text/visual weights, per-platform weight matrix |
| `retention` | punch-in strength, frequency, spacing, rise/hold/fall |
| `camera` | framing dial, letterbox fill, speaker-change mode, pan duration, deadzone, punch-ins, zoom lock |
| `captions` | preset overrides (15 style fields) |
| `pacing` | dead-space thresholds: min cut gap, breath pad, event protect, natural pause max |
| `performance` | fast scene detection (+ threshold, compare height), hardware encoding |
| `titles` | length limits, styles, count |
| `descriptions` | length, hashtags, CTA, platform limits |
| `hooks` | hook types, count, ranking |
| top level | `lufs_target`, `true_peak_db`, `llm_mode`, `caption_preset`, `laughter_specialist` |

Two rules govern this file, stated in its own docstring:

> 1. Every field here is READ somewhere in the pipeline. A field that nothing
>    consumes is a lie to the user — if you add one, wire it in the same
>    commit.
> 2. Settings are snapshotted per job at creation, so changing a global
>    default never silently rescores or reframes an old job.

Deserialisation (`_build`) is deliberately lenient: unknown keys are dropped,
missing keys keep their defaults. A settings file from an older or newer build
always loads instead of crashing a resume.

### The UI schema

`settings_schema.py` describes the settings panel as data: **13 groups, 72
controls**, plus **15 caption style fields**. The frontend renders it
generically — adding a setting means adding a schema entry, not writing a
React component.

`validate_schema()` checks **both directions**:

- every schema key resolves to a real settings field, and
- every settings field is reachable from the panel.

A setting nobody can reach from the UI is as broken as a control that points
at nothing.

### Where settings live

Three layers:

1. `~/.publikclip/settings.json` — global defaults. **Seeds new jobs only.**
2. `<job_dir>/settings.json` **and** the job's DB row — the per-job snapshot.
   Both are written by `queue.update_settings()`; if they drift, the clip
   editor and the analyzer disagree about the same job.
3. `clip_edits.json` — per-clip overrides ([§7](#7-per-clip-editing)).

---

## 7. Per-clip editing

The clip editor lets a user fine-tune one clip without re-running the job.
State lives in `<job_dir>/clip_edits.json`, keyed by clip index, shaped by
`edits/timeline.py:ClipEdit`.

### What a `ClipEdit` carries

| Field | Effect |
|---|---|
| `start`, `end` | free bounds, independent of the scored window |
| `remove_dead_space`, `disabled_cuts` | which silences to cut; every auto-detected cut is individually toggleable |
| `overlays` | images placed on the output timeline |
| `camera_mode`, `gameplay_amount` | per-clip framing |
| `letterbox_fill` | `black` or `blur` |
| `caption_preset`, `caption_overrides` | per-clip subtitle style |
| `pacing` | partial patch of `PacingSettings` |
| `lufs_target`, `true_peak_db` | per-clip loudness |
| `title`, `title_variants`, `description`, `description_meta` | generated copy |

`None` means "inherit the job's value". `pacing` and `caption_overrides` are
partial patches, so a clip carries only what was actually changed.

### The two render paths, and how they are kept in agreement

There are two ways a clip gets rendered, and **they must produce the same
result for the same inputs**:

| Path | Code | Used by |
|---|---|---|
| Whole-job | `render/stage.py` | a run, a resume, a restyle |
| Single-clip | `edits/render_clip.py` | the editor's re-render button |

They build different ffmpeg graphs — the single-clip path adds trim/concat for
dead-space removal and overlay compositing, which the stage path does not
build at all. Keeping them consistent takes three explicit mechanisms:

1. **`camera/stage.py:_settings_for_clip()`** layers a clip's
   `camera_mode`/`gameplay_amount` on top of the job settings before directing
   that clip. It returns a whole `Settings` object, not a bare
   `CameraSettings`, because the director also reads `settings.retention` for
   the punch-in envelope — handing it only the camera group silently resets
   those knobs to defaults.

2. **`render/stage.py` applies the style overrides it can reproduce**
   (`caption_preset`, `caption_overrides`, `lufs_target`, `true_peak_db`,
   `letterbox_fill`), and for a clip with **structural** edits — changed
   bounds, dead-space cuts, overlays — it keeps and reports the file the
   editor already produced rather than overwriting it.
   `_has_structural_edits()` draws that line.

3. **`edits/render_clip.py:_run_framing()`** compares a clip's framing against
   what the camera stage actually baked into the trajectory, not against the
   job dial. Comparing against the dial alone would spend minutes of ASD
   arriving at the trajectory already on disk.

The single-clip path also keeps `render.json` in sync after it writes, marking
the entry `"edited": true`, so the review screen reflects the new file.

**If you add a per-clip field, you must touch four places:** the `ClipEdit`
dataclass, the consuming render path, the relevant stage fingerprint, and the
editor UI. Miss the fingerprint and the setting silently does nothing on the
next restyle.

---

## 8. The desktop shell

[app/src-tauri/src/main.rs](app/src-tauri/src/main.rs), ~544 lines.

### Sidecar resolution

`pipeline_invocation()` returns the command to run:

- **Dev build** (`debug_assertions`): `uv --directory <repo>/pipeline run publikclip`
- **Packaged build**: the bundled `uv` under the platform resource layout —
  `../Resources/resources` on macOS, `resources/` next to the exe on Windows —
  pointed at the bundled pipeline source. The venv bootstraps into
  `PUBLIKCLIP_HOME` on first launch; uv downloads Python 3.12 and the
  dependencies itself.

### Two details that matter

**`quiet_command()`** wraps every spawn. It sets `CREATE_NO_WINDOW` on Windows
(a GUI app popping up console windows reads as malware to most users) and sets
`PYTHONUTF8=1`, because the sidecar writes JSON that Rust reads back with
`fs::read_to_string` — under the OS locale encoding a non-ASCII character
corrupts the file and the read fails silently.

**stderr is captured**, not discarded. When the sidecar crashes, its traceback
arrives here rather than in the JSONL stream, and it is what the live console
displays. Without this, every crash surfaces as "the pipeline exited
unexpectedly" with the actual error thrown away.

### Tauri commands

| Command | Purpose |
|---|---|
| `run_job` | start a new job |
| `resume_job` | resume/restyle an existing job (optionally from a chosen stage, T-14) |
| `resume_info` | passthrough to `jobs resume-info` for the resume picker |
| `diagnose_job` | builds the T-15 bundle via the CLI, copies it to Downloads |
| `job_results` | read every stage checkpoint for a job |
| `list_job_dirs` | enumerate jobs |
| `save_clip_edits` | write `clip_edits.json` |
| `run_edit_render` | single-clip re-render |
| `edit_tool`, `settings_tool`, `ig_tool` | generic passthrough to CLI subcommands |
| `save_gemini_key`, `save_pexels_key` | credential storage |
| `get_setup_state`, `mark_onboarded`, `check_ollama` | first-run flow |
| `update_checks_enabled`, `set_update_checks` | the launch update-check preference — a marker file in `PUBLIKCLIP_HOME`, on by default (T-16) |
| `bootstrap_status`, `run_bootstrap` | T-40: the pre-python environment — instant disk-truth status (ready? costs? free space?), and the visible `uv sync` with disk-watcher progress on `bootstrap-event` |
| `ig_status`, `ig_connect` | Instagram auth |
| `export_clip` | save a rendered clip out of the job dir |

---

## 9. The frontend

React 19 + TypeScript + Vite. Six views, routed by one `useState` in
[App.tsx](app/src/App.tsx):

`boot` → `onboarding` → **`studio`** ⇄ `review` / `loop` / `settings`

| Screen | Responsibility |
|---|---|
| **Studio** | submit a URL or file, pick run options (LLM backend, caption preset, framing), watch the live console |
| **Review** | the clip analyzer: per-clip video, score breakdown, generated title/description, restyle controls |
| **ClipEditor** | per-clip fine-tuning: bounds, dead-space cuts, overlays, framing, subtitles, audio |
| **Settings** | the schema-generated panel — 13 groups, rendered from `settings_schema.py` |
| **Loop** | Instagram feedback: linked Reels, metrics, score-vs-outcome calibration |
| **Onboarding** | first-run: dependency bootstrap, API keys |

`api.ts` holds **every** `invoke()` call. If you are adding a Tauri command,
its wrapper goes there and nowhere else. `types.ts` holds the shapes the
sidecar returns — it is the contract between the two languages and is easy to
let drift, because nothing enforces it at runtime.

Styling is entirely in `styles.css`, including the theme system. Themes are
CSS custom properties swapped on the root element.

**Drag interactions must not persist on every tick.** `ClipEditor` updates
local state continuously in `onMove` and calls `persist()` once in `onUp`;
follow that pattern for any new slider or handle.

---

## 10. Data on disk

Everything lives under `PUBLIKCLIP_HOME`, default `~/.publikclip`. The desktop
app points it at its own app-data directory; the CLI uses the default.

```
~/.publikclip/
├── db.sqlite3              job + stage bookkeeping
├── settings.json           global defaults (seeds NEW jobs only)
├── caption_presets.json    user edits to built-in presets + custom presets
├── bin/                    managed binaries (yt-dlp)
├── models/                 downloaded weights
│   ├── hf/                 HuggingFace cache (HF_HOME points here)
│   └── torch/              torch cache (TORCH_HOME points here)
└── jobs/<job_id>/
    ├── settings.json       the per-job snapshot
    ├── media.mp4           normalised source
    ├── media_cfr.mp4       constant-frame-rate copy where needed
    ├── audio16k.wav        speech models
    ├── audio32k.wav        audio-event models
    ├── diar_embeddings.npy
    ├── curves.json         continuous signals
    ├── interest_curve.json
    ├── scenes.json
    ├── ingest.json ─┐
    ├── asr.json     │
    ├── diarize.json │
    ├── events.json  ├─ stage checkpoints
    ├── candidates.json
    ├── score.json   │
    ├── camera.json  │
    ├── render.json ─┘
    ├── error.json          the described failure (errors.ErrorInfo, T-13):
    │                       code, cause, actions, stage, redacted detail.
    │                       Written on any stage failure, cleared at run
    │                       start like the cancel flags; read by the
    │                       ErrorPanel, T-14 and T-15 between the two
    ├── trajectory_NN.json  per-clip crop paths
    ├── clip_edits.json     per-clip overrides
    ├── t2frames/           frames sent to the vision pass
    ├── overlays/           user-added overlay images
    └── clips/
        ├── clip_NN.mp4     the deliverable
        └── clip_NN.ass     burned-in subtitles
```

All model caches are redirected under `PUBLIKCLIP_HOME` deliberately, so
"delete the app data" actually reclaims the disk.

Job IDs are `YYYYMMDD-HHMMSS-<6 hex>`.

### Disk pre-flight (E1-F07, T-12)

Before any stage writes, `jobs/disk.py` estimates what the job still needs to
put on disk — the URL download (yt-dlp's own filesize fields where its format
pick matches ours, a bitrate range otherwise), the analysis wav (exact
arithmetic from duration), the rendered clips (always a range), and any
missing model bytes from `setup status` — charges each piece to the volume it
lands on (`HF_HOME`/`TORCH_HOME` can point the caches at another drive), and
compares with what is free there. What is already on disk costs nothing, so a
resume after freeing space passes.

The policy: **block only on a confident shortfall** (free below the low end of
the estimate); in the gray zone the job starts with a warning; unknown —
unreadable free space, an unsizeable component — warns and never refuses
(§5.9-shaped). A blocked job is marked `failed` with the numbers in its error,
never left `pending`, because `next_pending()` would hand a pending job
straight back to the shell's auto-advance in a loop; the queue continues and
checkpoint resume keeps retry free. The system temp dir is not checked: the
pipeline writes only kilobytes there.

---

## 11. Models and external services

**The authoritative list of network calls is [PRIVACY.md](PRIVACY.md)**
(E15-F03, T-17): every host the code can reach, what is sent, when, and what
refusing costs. It is enforced, not aspirational —
`tests/test_privacy_notice.py` extracts every host from the Python string
constants (ast), the Rust shell, the frontend and `pyproject.toml`, plus the
hosts the no-literal-URL downloaders reach (huggingface_hub, torch.hub, uv),
and fails when one is missing from the document. The app renders the file
itself under Settings → Privacy via a build-time `?raw` import
(`PrivacyNotice.tsx`), so the shown text cannot drift from the repo copy.
This section covers the model-weight subset in engineering detail.

### Downloaded weights

On a packaged build, everything below is the SECOND half of the first run:
the Python environment itself (~3.86 GB download on Windows, torch-cu128
being 3.46 GB of it — measured 2026-08-28 from uv.lock plus HEAD requests,
identical with or without an NVIDIA GPU because the CUDA index marker in
`pyproject.toml` is per-platform) must materialize before python can run at
all. §16's first-launch section covers how T-40 made that visible; the
constants live in `main.rs` and are guarded by `tests/test_bootstrap_numbers.py`.

A first job fetches **~2.39 GB, through three different downloaders** — measured
2026-08-27 from a complete install (T-11), because the "~2.5 GB" figure had
never been checked. Only the registry share is fully ours:

| Downloader | What | Bytes | Resume | Verify | Progress |
|---|---|---|---|---|---|
| `models/registry.py` (ours) | PANNs 312 MB, CAM++ 28 MB, vision ONNX 4.6 MB, (laughter 10 MB, optional) | ~360 MB (15%) | `.part` + Range | pinned sha256 | our callback |
| huggingface_hub (faster-whisper) | whisper `large-v3-turbo` snapshot | 1.62 GB (68%) | `.incomplete` | etag | none — T-11 watches the cache dir |
| torch.hub (whisperX) | wav2vec2 English aligner 378 MB, silero-vad repo ~35 MB | 413 MB (17%) | **no** | **none** | none |

Registry weights are declared in `models/specs.py` and land in
`PUBLIKCLIP_HOME/models/<name>`; the HF and torch caches live under
`models/hf` and `models/torch` (`asr/stage.py` points `HF_HOME`/`TORCH_HOME`
there so deleting the app data dir stays a complete uninstall).

`publikclip setup status` reports what is present — derived from disk on every
call, never remembered — and `publikclip setup run` fetches what is missing
with JSONL progress (E1-F01, T-11). The onboarding warning step drives both;
stages keep their lazy fetches, so setup is a default, not a gate. Setup
deliberately skips: the laughter specialist unless the user's settings enable
it, non-English aligners (the language is detected mid-transcribe), and the
SER weights (~378 MB) whose loader has never succeeded (T-38).

| Model | File | Purpose |
|---|---|---|
| whisperX `large-v3-turbo` | (HF cache) | transcription, 1.62 GB |
| wav2vec2 ASR base 960h | (torch.hub cache) | English word alignment, 378 MB |
| silero-vad | (torch.hub cache) | voice activity detection, ~35 MB |
| PANNs Cnn14_DecisionLevelMax | `Cnn14_DecisionLevelMax.pth` | audio events, ~312 MB |
| CAM++ | `campplus_cn_common.bin` | speaker embeddings, 28 MB |
| UltraFace RFB-320 | `ultraface-rfb-320.onnx` | face detection |
| LR-ASD frontend | `frontend.onnx` | active-speaker detection |
| LR-ASD backend | `backend.onnx` | active-speaker detection |
| jrgillick laughter | `best.pth.tar` | optional laughter specialist |
| speechbrain SER | (should be `models/ser`) | arousal — **has never loaded; T-38** |

> **Note on the PANNs checkpoint.** The correct file is ~312 MB
> (`content-length: 327428481`). A 514 MB response from that URL is the
> corrupt one, not the other way round. The sha256 is pinned in `specs.py` for
> exactly this reason.

### Managed binaries

- **yt-dlp** — downloaded into `PUBLIKCLIP_HOME/bin/`, kept current.
- **ffmpeg** — resolved from the system, or a capable static build is fetched
  when the available one cannot burn subtitles. `PUBLIKCLIP_FFMPEG` overrides.
- **uv** — bundled with packaged builds.

### Network services

| Service | Required? | Used for |
|---|---|---|
| Gemini (`gemini-3.6-flash` by default; `Settings.gemini_model`) | optional | T1 rubric, T2 vision, music briefs, copywriting |
| Ollama (local) | optional | the same, minus T2 |
| Pexels | optional | overlay image search |
| Meta Graph / Instagram | optional | the feedback loop |

The app runs end to end without any of them, at reduced capability.

---

## 12. Hardware and performance

`hardware.py` is the single place that answers "what can this machine do".

| Function | Returns |
|---|---|
| `cuda_available()` | torch sees a usable CUDA device |
| `ctranslate2_cuda_ok()` | ctranslate2's CUDA works — **independent** of torch's |
| `vram_gb()` | via torch, falling back to `nvidia-smi` |
| `gpu_name()` | device name for display |
| `torch_device()` | `"cuda"` or `"cpu"` |
| `whisper_device()` | `("cuda", "float16")` or `("cpu", "int8")` |

`_forced()` reads `PUBLIKCLIP_DEVICE` (`cpu` or `cuda`) so a user can pin the
device. `_register_nvidia_dll_dirs()` handles Windows DLL discovery.

Precision is chosen by VRAM: `large-v3-turbo` is ~1.6 GB in float16, so above
`_FLOAT16_VRAM_GB = 3.5` it runs float16; below that it drops to
`int8_float16` — measured 17.1x vs 16.1x realtime on an RTX 3050 Ti Laptop
(4 GB), so barely slower and noticeably less memory.

### Environment variables

| Variable | Effect |
|---|---|
| `PUBLIKCLIP_HOME` | where everything lives (default `~/.publikclip`) |
| `PUBLIKCLIP_DEVICE` | pin `cpu` or `cuda` |
| `PUBLIKCLIP_FFMPEG` | use a specific ffmpeg binary |
| `PUBLIKCLIP_BUNDLED_FFMPEG` | the packaged build's ffmpeg |
| `PUBLIKCLIP_GEMINI_API_KEY` | LLM key, checked before the stored one |

**Every path degrades safely.** No CUDA is a fallback, never an error.

### The CUDA dependency trap

PyPI serves CPU-only torch wheels on Windows; the CUDA builds live on
PyTorch's own index. This must be configured **in `pyproject.toml`**, not
side-loaded with `uv pip install`:

```toml
[[tool.uv.index]]
name = "pytorch-cu128"
url = "https://download.pytorch.org/whl/cu128"
explicit = true

[tool.uv.sources]
torch = [{ index = "pytorch-cu128", marker = "sys_platform == 'win32'" }]
torchaudio = [{ index = "pytorch-cu128", marker = "sys_platform == 'win32'" }]
torchvision = [{ index = "pytorch-cu128", marker = "sys_platform == 'win32'" }]
```

The desktop app launches the pipeline through `uv run`, which **re-syncs
against this file on every launch** — a side-loaded CUDA build gets silently
replaced by the CPU one and the GPU sits idle. Scoped to Windows because there
are no cu128 wheels for macOS.

> The **installed app has its own `pyproject.toml`** under
> `resources/pipeline/`. Fixing the repo copy alone does not fix an installed
> build.

### Measured

On an 81-minute source with an RTX 3050 Ti, the two largest stages went from
49.9 → ~4.7 minutes (transcription) and 54.7 minutes → the fast path (scene
detection).

`Settings.performance` exposes `fast_scene_detect`, `scene_threshold`,
`scene_height` and `hardware_encode`. Hardware encoding is **off by default**:
the encoder is different from x264, so output is comparable rather than
identical, and nobody's renders should change silently.

Hardware encoders are **probed**, not trusted: NVENC appears
in `ffmpeg -encoders` on machines whose driver is too old to actually use it.

---

## 13. The Instagram feedback loop

`insights/instagram.py` and `insights/calibration.py`, surfaced as the Loop
screen.

The purpose: link a rendered clip to the Reel it became, pull that Reel's
metrics, and **compare the predicted score against the real outcome** so the
scoring weights can be calibrated on evidence rather than taste.

### Auth

Meta Business Login against **the user's own Meta app** — no shared
credentials.

Meta's App Dashboard **refuses to save `http://localhost/...`** for Business
Login. Since the local callback server can only listen on plain HTTP, a
compliant `https://` redirect can never reach it. The flow is therefore built
to survive a redirect it cannot catch:

- `DEFAULT_REDIRECT_URI` is `https://localhost:<port>/callback`.
- `extract_code(pasted)` is deliberately forgiving — it accepts the whole
  address bar, a bare code, a code with Instagram's trailing `#_`, a URL
  without a scheme, and stray quotes or whitespace from copying.
- `connect()` rejects an unusable paste **locally**, before spending a round
  trip on Meta's generic error.
- The redirect URI used for the token exchange is the exact one the code was
  issued against — Meta matches it character for character — so it is stored
  with the connection and reused.

### "Insufficient Developer Role"

This is **configuration, not a bug**. While a Meta app is in Development mode,
Instagram Login only accepts accounts that hold a role on that app. Fix:

1. App Dashboard → **App roles → Roles → Add people** → add the Instagram
   account as an **Instagram Tester**.
2. In Instagram: **Settings → Apps and websites → Tester invites → Accept.**
   The invite does nothing until it is accepted.
3. **Products → Instagram → API setup with Instagram login** → confirm the
   account appears under *Generate access tokens*.
4. The account must be **Business** or **Creator**. A personal Instagram
   account cannot use this API at all.

### Sync

`ig sync` runs one pass: media list, thumbnails, the insights ladder (Meta
deprecates metric names, so `_drop_named_field()` retries without a field the
API rejected), then auto-fit matching of clips to Reels by duration and
thumbnail. Matches are suggestions; `link`, `unlink` and `reject` are the user
verbs, and a rejected pair is never suggested again.

---

## 14. Development setup

### Prerequisites

- **Python 3.12** (`>=3.12,<3.13` — whisperX pins this)
- **[uv](https://docs.astral.sh/uv/)**
- **Node 18+**
- **Rust toolchain** (for the desktop shell)
- **ffmpeg** — or let the app fetch a static build

### Pipeline only

```bash
cd pipeline
uv sync
uv run publikclip run "https://youtube.com/watch?v=..."
uv run publikclip jobs
uv run publikclip resume <job_id> --captions beast --gameplay-amount 0.8
```

Add `--jsonl` for machine-readable progress — that is what the desktop shell
consumes.

### Full app in dev mode

```bash
cd app
npm install
npm run tauri dev
```

Dev builds call `uv run` against the repo's `pipeline/` directory, so Python
changes take effect on the next job with no rebuild.

### CLI surface

| Command | Purpose |
|---|---|
| `run <source>` | process a URL or file |
| `resume <job_id>` | resume from checkpoints, optionally with new settings |
| `resume <job_id> --from-stage <name>` | invalidate that stage first, so it and everything after re-run (T-14) |
| `jobs resume-info <job_id>` | per-stage status + measured re-run cost, for the resume picker |
| `diagnose [job_id] [--out]` | one inspectable, redacted zip for a bug report (T-15) — allowlist-built, no network |
| `jobs` | list jobs |
| `settings get\|set\|reset` | read/write the global settings tree |
| `settings preset-save\|preset-reset <name>` | caption preset editing |
| `edit context <job> <clip>` | everything the editor needs for one clip |
| `edit suggest-visuals <job> <clip>` | overlay suggestions (Pexels or Gemini) |
| `edit titles\|description\|hook <job> <clip>` | copywriting |
| `edit render-clip <job> <clip>` | single-clip re-render |
| `ig auth-url\|connect\|sync\|overview` | Instagram auth and sync |
| `ig media\|link\|unlink\|reject\|pull\|report` | clip↔Reel linking and metrics |

Run flags: `--llm {gemini,ollama}`, `--captions <preset>`,
`--camera {cut,pan,locked}`, `--gameplay-amount <0..1>`.

> **`0.0` is a legitimate value and falsy in Python.** Every check on
> `--gameplay-amount` must be `is not None`, never `if args.x:`. The older
> `--camera`/`--captions` flags get away with the truthy idiom only because
> their values are never empty strings.

---

## 15. Testing

```bash
cd pipeline
uv run pytest -q
```

**275 tests**, ~20 s. No *source* media and no model weights — but the
default run does shell out to ffmpeg, so it needs one on `PATH`.

| File | Tests | Covers |
|---|---|---|
| `test_settings.py` | 42 | the settings tree, schema, snapshotting, anti-drift |
| `test_insights_sync.py` | 33 | Instagram sync, matching, metric ladder |
| `test_clip_edit_sync.py` | 26 | editor ⇄ analyzer agreement, render/camera fingerprints |
| `test_copywriting.py` | 21 | title/hook generation and constraint enforcement |
| `test_descriptions.py` | 20 | description assembly, hashtags, platform limits |
| `test_instagram_auth.py` | 19 | redirect URIs, code extraction |
| `test_house_rules.py` | 19 | the invariants in §17, as tests that fail |
| `test_queue.py` | 16 | checkpoints, the invalidation cascade, the events fingerprint |
| `test_director.py` | 15 | framing dial, crop geometry, smoothing |
| `test_performance.py` | 15 | hardware detection, fast scene detect |
| `test_render.py` | 14 | filtergraph construction, letterbox, verification |
| `test_rubric.py` | 13 | scoring rubric, corroboration discount |
| `test_events_post.py` | 9 | DCASE post-processing, cross-model merge |
| `test_timeline_edits.py` | 8 | keep-ranges, time remapping |
| `test_cluster.py` | 5 | speaker clustering |

`test_render.py:test_render_smoke` encodes a 20-second synthetic `testsrc2`
clip and burns captions into it, resolving ffmpeg the way the product does.
It carries `@pytest.mark.slow`, but **that marker is not registered and
nothing deselects it**, so it runs on every `pytest -q` — the mark currently
does nothing but emit a warning. With no ffmpeg on `PATH` the resolver
downloads a static build mid-test, which is why `guards.yml` installs ffmpeg
before running the suite. `PUBLIKCLIP_FFMPEG` points the suite at a specific
binary.

Synthetic fixtures like this one are the sanctioned way to verify a render
change. The rule against real runs (§14) is about *source* media and model
weights, not about ffmpeg.

### The test that exists because of a specific failure

`test_settings.py:test_every_settings_group_is_read_by_the_pipeline` greps the
package for a real read of each settings group.

It was written after `PacingSettings` was fully plumbed — dataclass, JSON
serialisation, UI schema entry, **and a passing unit test of the function that
consumes it** — and the pipeline still never passed it in. The whole Pacing
group silently did nothing. A unit test that calls the consumer directly
cannot catch that, because the consumer works fine; the caller is what is
broken.

**When you add a settings group, this test is what tells you that you wired
it.** It is crude, and that is the point.

That claim was false for most of this codebase's life, and the reason is worth
keeping. `config.py` has `from __future__ import annotations`, so the field
type is the *string* `"PacingSettings"` and `dataclasses.is_dataclass()` on a
string is always `False`. The discovery half never fired; only a hardcoded
ten-name tuple was ever checked, and a newly added group — the precise case
the test exists for — was invisible to it. Fixed in T-22 with
`typing.get_type_hints`, which resolves the strings and now finds eleven
groups. The sentence above is true again; it was not before.

The general lesson, which §17 repeats: **every guard in this repository is
narrower than the rule it is named after.** Read the test before trusting the
heading.

---

## 16. Building and installing

```bash
cd app
npx tauri build
```

Use `npx tauri build`, **not** `cargo build --release`. A bare cargo build
produces a binary that still points at the dev server on `localhost:1430`.

`beforeBuildCommand` runs `scripts/prepare-resources.mjs`, which stages the
Python pipeline and a `uv` binary into `src-tauri/resources/`. Its exclude
list keeps `.venv`, `__pycache__`, `.pytest_cache` and tests out of the
bundle — and specifically `wav2vec2_checkpoints`, a stray HF cache a developer
machine may carry that is 700+ MB and must never ride into the app.

### The first launch (T-40)

A packaged first launch must download Python 3.12 and every dependency in
`pyproject.toml` before the sidecar can answer anything — **~3.86 GB on
Windows** (torch-cu128 3.46 GB; ~10 minutes at 50 Mbps), then T-11's
~2.39 GB of models: **~6.3 GB true first-run total**. Until T-40 this was
invisible: SetupModels fired `setup_status` on mount, and on a cold machine
that python one-shot IS the download, hidden behind "checking what is
already on this machine…".

The fix is ordering plus visibility. `bootstrap_status` (Rust, instant,
disk-truth: env present? what does a cold bootstrap cost? how much is
free?) answers first, and the python one-shot fires only once the env is
ready. When it is not, the environment renders as the first row of the
setup list with its measured size, the free-space line warns (never walls,
§5.9) using the same headroom rule as `disk.py`, and `run_bootstrap` runs
the visible `uv sync`: progress is T-11's disk-watcher pattern implemented
in Rust (python cannot run yet) — real bytes appearing under the venv and
uv's cache against a measured apparent total, uv's own output never parsed.
The child carries KILL_ON_JOB_CLOSE like the setup downloader; a killed or
failed bootstrap resumes at wheel granularity from uv's cache, and the
screen offers retry with the last stderr line named.

Packaged builds check `github.com/Karlasonars/Alias_Studio`'s latest release
for `latest.json` once at launch (switchable off — the preference is a
marker file in `PUBLIKCLIP_HOME`) and on demand from Settings → About, which
owns the whole flow: changelog before install, an install that refuses while
a job is running, minisign verification against the pubkey in
`tauri.conf.json` (`plugins.updater`). `release.yml`'s `windows-updater` job
builds the NSIS installer with the signing key from CI secrets
(`TAURI_SIGNING_PRIVATE_KEY`/`_PASSWORD`) and uploads installer + `.sig` +
`latest.json` to the tagged release. There is no Authenticode signing —
SmartScreen warns on install, and README says so before the download link.

Two survival facts, both load-bearing:

- **User data lives in `~/.publikclip`** (`home_dir()` in both `main.rs`
  and `config.py`), outside the NSIS install dir
  (`%LOCALAPPDATA%\Alias Studio`) — jobs, checkpoints, settings, presets,
  models, secrets and the hardware profile all survive any update.
- **The packaged Python env lives in `~/.publikclip/venv`**, because
  `quiet_command` sets `UV_PROJECT_ENVIRONMENT` there in release builds
  (T-16). Before that it materialized as `resources/pipeline/.venv` inside
  the install dir, where an update's file replacement could wipe it and
  silently re-cost gigabytes. With the env outside and uv's cache
  (`%LOCALAPPDATA%\uv`) also outside, an update's next launch is a
  re-sync: sub-second when `uv.lock` is unchanged, only the changed
  packages when it is not (measured: full venv rebuild from a warm cache
  is ~15 s with zero network). Dev builds keep `pipeline/.venv`.

> **`tauri.conf.json` currently sets `bundle.targets` to `["dmg"]`.** On
> Windows, `npx tauri build` therefore produces only
> `src-tauri/target/release/alias-studio-app.exe` — no NSIS installer. For local
> use, copy that exe over the installed one (close the app first). To produce
> a Windows installer, add `"nsis"` to the targets.

### The live-code junction (Windows dev convenience)

The installed app's `resources/pipeline/publikclip_pipeline` can be replaced
with a directory junction to the repo:

```
mklink /J "…\AppData\Local\Alias Studio\resources\pipeline\publikclip_pipeline" ^
          "…\publikclip\pipeline\publikclip_pipeline"
```

Python changes then take effect in the installed app immediately, and only
Rust/frontend changes need a rebuild. Note the installed build keeps its own
`.venv` and `pyproject.toml` alongside the junction — see the CUDA note in
[§12](#12-hardware-and-performance).

---

## 17. Conventions and house rules

These are not style preferences; each one exists because breaking it caused a
real failure.

**No decorative settings.** No dummy buttons, no controls without backend
logic, no hardcoded values that should be configurable. Every setting must
have real functionality; if you add one, wire it in the same commit.

**Match the surrounding code.** Comment density, naming and idiom vary by
module; follow the file you are in.

**Comments explain *why*, not *what*.** The codebase's existing comments
document the failure a piece of code prevents. Preserve that when editing near
them.

**UTF-8 explicitly, everywhere.** Every `read_text`/`write_text` in the
package passes `encoding="utf-8"` — not just on checkpoints and settings
files. A `±` in a score once corrupted `score.json` under cp1252 and Rust's
read failed silently. `test_house_rules.py` pins the violation count at 0
(T-06), so a new one fails the suite. The guard does not see `open()`, which
is narrower than the rule as stated here.

**Probe, do not trust.** Encoder availability, caption support in ffmpeg,
emoji support in fonts — all probed at runtime.

**Verify outputs.** Every rendered clip is checked for streams and duration
before it is reported as done.

**Preview and render must resolve settings identically.** If the editor shows
one thing and the render produces another, the feature is broken even if both
halves are individually correct.

**A new per-clip or per-job setting touches four places:** the dataclass, the
consumer, the stage fingerprint, and the UI. The fingerprint is the one people
forget, and forgetting it makes the setting silently do nothing — because
places 1, 2 and 4 all produce visible behaviour the first time you run the
app, while 3 only misbehaves on the *second* run of a job that already exists.

For a `ClipEdit` field there is a **fifth** place: the classification list in
`test_house_rules.py`, which fails until the field is declared either
fingerprinted or render-irrelevant. That is expected work, not a sign the
architecture is being bent.

A field on `config.Settings` has **no** such guard — places 3 and 4 are
unchecked for job-level settings, so they need the discipline rather than the
test. `CLAUDE.md` §5.1 carries the current procedure.

---

## 18. Change history: what this build added

Alias Studio forks publikclip at `a53a359`. Since then: **10 commits, 62
files, +10 433 / −389 lines.**

### `5d0c447` — Windows: fix the failures that stopped a real run end to end

Six separate faults, each of which killed a real run: ffmpeg resolution in two
places, a speechbrain import guard that never matched on Windows, silent
truncation of a model download, an inconsistent checkpoint URL, an LLM retry
loop that did not back off, and checkpoint writes using the OS locale encoding
instead of UTF-8.

### `b0a34bf` — Camera: a podcast-to-gameplay framing dial

The original always cropped tight onto the tracked face. On gameplay footage —
game filling the frame, a small facecam in a corner — every clip contained
only the facecam and none of the game.

Root cause was structural, not tuning: the camera pipeline tracked faces with
no size veto, so a corner facecam won the crop target 100% of the time; and a
9:16 crop at full source height is mathematically capped at ~31.7% of a 16:9
source's width. **No crop-only setting can reveal more.** The fix needed the
renderer to scale-to-width and pad.

`gameplay_amount` (0.0–1.0) interpolates between the original tight crop
(0.0 = zero regression) and the full frame, letterboxed (1.0). Settable per
job and per clip.

### `a8dd260` — Settings: make the real knobs configurable, and prove they work

Module constants became a configurable tree with a generated UI, plus
`validate_schema()`'s bidirectional check and the anti-drift test described in
[§15](#15-testing).

### `c566291` — Copywriting: title, description and hook engines

Title variants, a post description with hashtags, and a hook pass that ranks
alternative openings against the current one. Constraints are **enforced on
the model's answer**, not merely requested in the prompt.

### `0c1706e` — Performance: use the GPU that is already in the machine

Models ran on the CPU regardless of hardware. Added `hardware.py`, the
`pyproject.toml` CUDA index configuration, encoder probing, and the fast
ffmpeg scene-detection path. Measured: 49.9 → ~4.7 min transcription; 54.7 min
→ the fast path for scene detection.

### `e090989` — App: settings panel, clip fine-tuning, live console, themes, rebrand

The settings panel, per-clip fine-tuning inside the editor, the live console
(the shell previously discarded the sidecar's stderr, so every crash surfaced
as "the pipeline exited unexpectedly" with the traceback thrown away), the
theme switcher, and the rename to Publikclip Extra.

### `a3d8ee2` — README

### `eb31c83` — Keep a job's settings in sync, and add blurred letterbox bars

The job DB row and `<job_dir>/settings.json` could disagree, so the editor and
the analyzer read different settings for the same job. Plus `letterbox_fill`:
`gblur` background instead of black bars.

### `826c240` — Instagram: survive Meta refusing `http://` redirect URIs

The redesign described in [§13](#13-the-instagram-feedback-loop), plus
per-clip letterbox fill.

### `3dc43c1` — Clips: make the editor and the analyzer agree

A whole-job restyle rebuilt every clip from the job's settings and never read
`clip_edits.json`, so a hand-edited clip came back as if none of that had
happened — losing not just the per-clip framing and fill, but the **trimmed
bounds themselves**.

Three faults produced that one symptom, all described in
[§7](#7-per-clip-editing): `RenderStage` ignored per-clip edits entirely;
`CameraStage` built trajectories from the job dial alone; and the editor's
re-direct handed the director a bare `CameraSettings`, so `settings.retention`
silently fell back to defaults — which is why identical settings still
rendered differently on the two paths.

---

## 19. Known limitations and deferred work

**True split-screen is not implemented.** The framing dial widens the crop; it
does not composite the game region and the facecam as two independently
positioned live regions. That needs new `-filter_complex` work and a way to
isolate the facecam from the game area.

**Moment selection is audio/dialogue-biased.** Candidate windows come from
speech-derived channels and drop sub-20-word candidates, so a purely visual
highlight — a clutch play with no commentary — is unlikely to be selected. The
framing dial fixes how a selected clip is *shown*, not *which* moments are
picked. A visual/action signal is the missing channel.

**Captions can land inside the letterbox bar.** `captions/ass.py` positions
captions by a fixed `MarginV` in the 1080×1920 canvas. At a high
`gameplay_amount`, a bottom-anchored preset can sit in the bar rather than over
the footage. The fix is to clamp caption placement to the visible band.

**No face-size veto.** A tiny facecam is treated identically to a face filling
the frame. Adding one risks changing `gameplay_amount=0` output on some
sources, which would break the zero-regression guarantee, so it was left out
deliberately.

**Structural per-clip edits freeze that clip against job restyles.** A clip
with custom bounds keeps its editor render; a job-level caption change does
not reach it. This is correct — the alternative silently destroys the user's
work — but it means such clips must be updated in the editor. The review
screen labels them.

**Windows is the validated platform.** macOS is the bundle target in
`tauri.conf.json` but has had less real-run exercise in this fork.

---

## 20. Troubleshooting

Since T-13 this table is also the floor of the in-app **error catalogue**
(`errors.py`, E14-F01): every row maps to a catalogue code
(`errors.SPEC20_CODES`, enforced by `test_error_catalog.py`), job failures
reach the UI as a structured `error_info` — cause, actions, optional docs
link, technical detail behind a disclosure — and an unrecognized failure
gets a generic cause naming the stage plus a `signature` for grouping,
never a Python repr. Unhandled tracebacks are redacted at birth
(`errors.install_excepthook`), so the shell's captured stderr tail carries
no secrets and no home paths.

| Symptom | Cause and fix |
|---|---|
| "The pipeline exited unexpectedly" | The sidecar crashed. The live console has the traceback — read it there. |
| A setting appears to do nothing | Its stage's `artifacts_ok` probably does not diff it, so the cached result is being served. See [§5](#5-the-checkpoint-contract). |
| A restyle discards editor work | Should not happen since `3dc43c1`. If it does, check that the relevant field is in the stage fingerprint **and** applied in `run()`. |
| GPU sits idle after installing CUDA torch | `uv run` re-synced from `pyproject.toml`. Configure the index there — and remember the **installed app has its own copy**. See [§12](#12-hardware-and-performance). |
| NVENC selected, then render fails | Driver too old for the listed encoder. `encoder_works()` probes for this; if it regressed, the probe is the place to look. |
| Rust reads a checkpoint as empty/invalid | Encoding. Every write needs `encoding="utf-8"`, and `PYTHONUTF8=1` is set in `quiet_command`. |
| App loads a blank page / `localhost:1430` | Built with `cargo build --release` instead of `npx tauri build`. |
| No installer after a Windows build | `bundle.targets` is `["dmg"]`. See [§16](#16-building-and-installing). |
| "Insufficient Developer Role" on Instagram | Meta app-role configuration, not a code bug. See [§13](#13-the-instagram-feedback-loop). |
| A model download looks truncated | Check the expected size before deleting anything. The PANNs checkpoint is correctly ~312 MB; the 514 MB response is the corrupt one. |

---

## 21. Licensing

**AGPL-3.0-or-later**, inherited from
[publikclip](https://github.com/Blueturboguy07/publikclip).

Practical obligations:

- **Source must accompany distribution.** If you give someone the app, they
  are entitled to the source of the version they received.
- **Network use counts as distribution.** This is what separates AGPL from
  GPL: run a modified version as a network service and users of that service
  are entitled to its source. Relevant if this ever becomes hosted.
- **Modifications must be stated.** [README.md](README.md) and
  [§18](#18-change-history-what-this-build-added) of this document do that.
- **The licence cannot be changed** on this codebase, and derivative works
  must also be AGPL-3.0.

**In the UI (E16-F03, T-18):** Settings → About renders these obligations on
T-17's one-source pattern — LICENSE, VENDORED-LICENSES.md and README's "What
this build adds" section arrive via build-time `?raw` imports, so the screen
can only show the files that ship in the repo. The version shown is
`getVersion()`'s answer (tauri.conf.json is its one defined place — a guard
in `tests/test_vendored_licenses.py` rejects any literal copy in `app/src`),
and the exact-source link resolves through the commit `vite.config.ts` bakes
in at build time (`src/buildInfo.ts` is its only reader). A build made
without git — a source archive — shows "no commit recorded" instead of a
dead link. `.github/workflows/release.yml` closes the release half: pushing
a `v*` tag creates the GitHub Release carrying that tag's source archives,
after a gate that refuses a tag whose name disagrees with
tauri.conf.json's version. The same guard file cross-checks `vendor/`
against VENDORED-LICENSES.md in both directions and verifies the
attribution headers the doc claims.

### Third-party code

[VENDORED-LICENSES.md](VENDORED-LICENSES.md) is the authoritative list —
upstream, licence, where it lives, and what was taken. It also records what
was **deliberately not used** for licence or quality reasons, which is worth
reading before adding a dependency.

Two things to be careful about when contributing:

- **Two upstreams are themselves AGPL-3.0** (supoclip, ViralMint, both in
  `captions/ass.py`). Their influence is part of why this project cannot
  relicense.
- **`vendor/` is vendored code, not ours.** `clippyme`, `laughter`, `panns`
  and `campplus` are copies of upstream projects. Modify them only when you
  must, and record it — the attribution table describes what was taken.
