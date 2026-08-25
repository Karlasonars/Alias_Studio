# CLAUDE.md — working rules for this repository

You are working on **Publikclip Extra**: a desktop app that turns one long horizontal
video into several short vertical (9:16) clips, each scored, captioned and reframed.
Everything runs locally. AGPL-3.0.

**Read this file before your first edit in every session.** The rules below are not
style preferences. Each one exists because breaking it caused a real failure, and
most of them fail *silently* — the code runs, the tests pass, and the feature
quietly does nothing.

---

## 1. Documents, and which one answers your question

| Document | Answers |
|---|---|
| `SPECIFICATION.md` | **How the built thing works today.** Architecture, the eight stages, the checkpoint contract. Read the relevant section before touching a stage. |
| `PRODUCT-REQUIREMENTS.md` | **What it should become and why.** Requirement IDs (`E11-F03`), priorities, acceptance criteria. Written in Latvian. |
| `AGENT-WORKPLAN.md` | **What to do next, in what order, and which files it touches.** Start here when picking up work. |
| `VENDORED-LICENSES.md` | Third-party code. Authoritative — read before adding a dependency. |
| This file | The rules that apply to every task. |

Your task will name a requirement ID. That ID is the contract: implement exactly it,
nothing adjacent.

**Language:** the codebase, comments, tests, commit messages and PR descriptions are
**English**. `PRODUCT-REQUIREMENTS.md` is Latvian; translate what you need, do not
mirror it into the code.

---

## 2. Repository map

```
pipeline/publikclip_pipeline/     the product — ~11,000 lines of Python
  cli.py            (584)  argparse surface; the sidecar's entry point
  config.py         (452)  the whole settings tree
  settings_schema.py (487) UI schema — 13 groups, 68 fields, all with `help` + `cost`
  hardware.py       (231)  CUDA/CPU detection. The single place that answers
                           "what can this machine do"
  jobs/queue.py     (355)  Job/Stage machinery, SQLite, checkpoints
  ingest/ asr/ diarize/ events/ candidates/ scoring/ camera/ render/
                           the eight stages, in that order
  captions/ass.py   (429)  ASS subtitle generation. 5 built-in presets
  copywriting/             titles, descriptions, hooks
  edits/                   per-clip editing + single-clip render
  insights/calibration.py  (908) LARGEST FILE. Instagram feedback + calibration
  models/specs.py    (82)  weight registry
  vendor/                  DO NOT EDIT — see §6
  tests/                   223 tests, 14 files

app/src/                          React frontend — ~5,300 lines
  App.tsx           (229)  view router: boot|onboarding|studio|review|loop|settings
  api.ts             (65)  EVERY invoke() belongs here — see §5.4
  types.ts          (338)  the Rust↔TS contract. Nothing enforces it at runtime
  styles.css       (1342)  all styling, including themes
  components/ClipEditor.tsx (1175)  the biggest component. Split before growing it
app/src-tauri/src/main.rs  (544)  the whole Rust layer. 17 commands. No product logic
```

**Three processes, one direction of control:** React → Rust (Tauri) → Python sidecar.
The Rust layer holds no product logic; the frontend holds no product logic. Anything
worth unit-testing belongs in Python.

**Artifacts on disk are the source of truth.** SQLite records only what *should*
exist. If the database and the disk disagree, the disk wins.

---

## 3. Commands

```bash
# Python pipeline
cd pipeline
uv sync
uv run pytest -q                    # 223 tests, no video or model I/O
uv run pytest -q -k house_rules     # the guard tests in §5 — run these before every PR
uv run ruff check .                 # lint

# Full app, dev
cd app
npm install
npm run tauri dev                   # dev builds call `uv run` against ./pipeline,
                                    # so Python changes need no rebuild

# Build — use tauri, NEVER `cargo build --release`
npx tauri build                     # a bare cargo build still points at localhost:1430
```

**Never run the pipeline on real media to "check if it works".** A full job takes
10–60 minutes and downloads ~2.5 GB of models. The test suite is designed to run
without either. If you think you need a real run, say so in the PR and stop.

---

## 4. The checkpoint contract — read this before touching any stage

Every stage writes `<job_dir>/<stage>.json`. On the next run `run_stages()` asks each
stage `artifacts_ok(ctx, data)`: *given the current settings, is this cached result
still correct?*

**Three rules. Breaking any of them makes a setting silently do nothing.**

1. **`artifacts_ok` must diff every setting that changes its output.** If a stage
   bakes a setting into its artifacts but does not compare it, the stage happily
   serves the old result and the setting appears dead. This has been a real bug three
   separate times in this codebase.

2. **A stage that re-runs invalidates every stage after it.** `run_stages` tracks
   `upstream_stale`. Without it, new candidate windows get scored with stale scores,
   or a re-directed camera's trajectories never reach a cached render.

3. **A missing fingerprint key means "unchanged", not "stale".** Checkpoints written
   before a setting existed lack its key. `fingerprint_ok(stored, current, factory)`
   compares a missing key against the **factory default**, so adding an unrelated
   toggle does not throw away an hour of transcription.

Current fingerprints:

| Stage | Invalidated by |
|---|---|
| `camera` | `camera_settings`, `retention_settings`, `clip_framing` |
| `render` | `caption_preset`, `camera_settings`, `caption_style`, `audio`, `encoder`, `clip_edits` |

Each covers **only** what that stage reads. A title edit must not force a re-encode;
a caption tweak must not re-run the expensive camera pass.

---

## 5. Invariants

Every one of these is enforced by a test in `pipeline/tests/test_house_rules.py`.
If you are about to break one, the test will tell you. Do not edit the test to make
it pass — that is the one change that is never correct.

### 5.1 The four-place law

**A new per-clip or per-job setting touches four places:**

1. the dataclass (`config.Settings` or `edits/timeline.ClipEdit`)
2. the consumer (the code that actually reads it)
3. **the stage fingerprint** (`artifacts_ok`)
4. the UI (`settings_schema.py` entry, or the editor component)

**Number 3 is the one people forget, and forgetting it makes the setting silently do
nothing on the next run.** `test_every_clip_edit_field_is_fingerprinted_or_exempt`
fails until you classify a new `ClipEdit` field as either fingerprinted or explicitly
render-irrelevant.

### 5.2 No decorative settings

No dummy buttons, no controls without backend logic, no hardcoded values that should
be configurable. A field that nothing consumes is a lie to the user — if you add one,
wire it in the same commit.

`test_settings.py:test_every_settings_group_is_read_by_the_pipeline` greps the package
for a real read of each settings group. It is crude, and that is the point: it was
written after `PacingSettings` was fully plumbed — dataclass, JSON, UI schema, *and a
passing unit test of the consumer* — while the pipeline still never passed it in. The
whole group silently did nothing. A unit test that calls the consumer directly cannot
catch that; the caller is what is broken.

### 5.3 UTF-8, explicitly, everywhere

Every `read_text` / `write_text` passes `encoding="utf-8"`. A `±` in a score once
corrupted `score.json` under cp1252 and Rust's read failed silently.

`PYTHONUTF8=1` in `quiet_command` masks this in the desktop app but **not** in CLI use.
39 call sites currently violate this; `test_no_text_io_without_encoding` is a
**ratchet** — the count may only go down. If you touch a file with a violation, fix it
and lower the baseline.

### 5.4 Every `invoke()` lives in `api.ts`

`app/src/api.ts` is the single list of Tauri calls — but it covers only 11 of the 17
Tauri commands. **12** direct `invoke()` calls currently sit outside it: `ClipEditor.tsx`
(6), `IgModal.tsx` (3), `KeyModal.tsx` (3). `test_no_invoke_outside_api_ts` is a ratchet
on that count. Add new commands to `api.ts` and nowhere else; if you touch a component
with a stray call, move it and lower the baseline.

### 5.5 `0.0` is a legitimate value and falsy in Python

Every check on `gameplay_amount` must be `is not None`, never `if x:`. The older
`--camera` / `--captions` flags get away with the truthy idiom only because their
values are never empty strings. `test_no_truthy_gameplay_amount_check` enforces this.

### 5.6 The zero-regression guarantee

`_resolve_content_box(0.0, w, h)` must reproduce the original tight 9:16 crop exactly —
full source height, `h * 9/16` width (~31.6 % of a 16:9 frame). Any change to the
framing dial that moves the `0.0` endpoint by a single pixel is a regression, however
good it looks at other values. `test_framing_dial_zero_is_exact` pins both the
landscape and the portrait branch.

### 5.7 Probe, do not trust

Encoder availability, ffmpeg's caption support, emoji support in fonts — all probed at
runtime. NVENC is listed in `ffmpeg -encoders` on machines whose driver is too old to
use it, so `encoder_works()` encodes an actual frame.

### 5.8 Preview and render must resolve settings identically

If the editor shows one thing and the render produces another, the feature is broken
even if both halves are individually correct. `edits/timeline.py:resolve_pacing()`
exists to keep one such calculation in a single place. When you add a value that both
sides read, add a `resolve_*()` for it — do not compute it twice.

### 5.9 Every path degrades safely

No CUDA is a fallback, never an error. A missing API, an unavailable encoder, an
absent optional model — each degrades to a lesser result with a clear message. Nothing
optional may become a hard requirement.

### 5.10 Verify outputs

Every rendered clip is checked for streams and sane duration before it is reported as
done.

---

## 6. Danger zones

**`pipeline/publikclip_pipeline/vendor/` — do not edit.** `clippyme`, `laughter`,
`panns` and `campplus` are copies of upstream projects, and two upstreams are
themselves AGPL-3.0. Modify only when you must, and record it in
`VENDORED-LICENSES.md` in the same commit. Guard tests skip this tree; that is not
permission to lower its standards.

**`app/src/components/ClipEditor.tsx` (1175 lines).** Split it before adding to it.
Three planned features land here and the file is already 22 % of the frontend.

**`pipeline/publikclip_pipeline/insights/calibration.py` (908 lines).** Largest file in
the pipeline, and about to carry two more platforms. Same advice.

**`pyproject.toml` CUDA index config.** `uv run` re-syncs from this file on every
launch, so a side-loaded CUDA torch build is silently replaced by the CPU one. The
installed app has its **own copy** under `resources/pipeline/` — fixing the repo copy
alone does not fix an installed build.

**Drag interactions.** Update local state continuously in `onMove`, call `persist()`
once in `onUp`. Follow that pattern for any new slider or handle.

---

## 7. Definition of done

A task is done when **all** of these hold:

- [ ] The named requirement ID is implemented — and nothing adjacent to it.
- [ ] `uv run pytest -q` passes (223 tests + whatever you added).
- [ ] `uv run pytest -q -k house_rules` passes, with **no baseline raised**.
- [ ] `uv run ruff check .` is clean.
- [ ] At least one new test **fails without your change**. Verify this by reverting
      your change and watching it fail; a test that passes both ways tests nothing.
- [ ] If you added a setting: all four places from §5.1, in this commit.
- [ ] If you added a `ClipEdit` field: classified in the fingerprint test.
- [ ] Comments explain **why**, not what — document the failure the code prevents.
      Match the surrounding file's comment density and idiom.
- [ ] No new file over ~400 lines without saying why in the PR.

---

## 8. Scope discipline

The product deliberately does **not** do these. Do not add them, and do not add
scaffolding "for later":

- a general multi-track video editor — the editor is for tuning one clip
- recording
- cloud rendering, mandatory accounts, or any required upload
- AI avatars, voice cloning, text-to-video
- a mobile app
- paid tiers, licence keys, entitlement checks — the product is free, entirely
- a degraded "no AI" scoring mode — `llm_mode` is `gemini | ollama`, deliberately
- automatic recalibration without explicit user approval

If a requirement seems to need one of these, stop and say so in the PR rather than
building it.

---

## 9. Commits and pull requests

- **One requirement ID, one branch, one PR.** Branch name: `e11-f03-calibration-report`.
- Commit subject: lowercase, imperative, scoped — `render: clamp captions to the
  visible band (E7-F07)`.
- The body explains **why**, and names the failure it prevents. The existing history
  is written this way; match it.
- PR description states: the requirement ID, which of the four places you touched,
  which test fails without the change, and anything you deliberately did not do.
- **Never** `git add --renormalize`, mass reformat, or reorder imports across files you
  are not otherwise changing. Diff noise is what makes review impossible.

---

## 10. When you are stuck

Stop and say so. Specifically:

- The requirement conflicts with an invariant here → say which, do not pick one.
- You need a real pipeline run to verify → say so, do not run it.
- The change would need a fifth place not listed in §5.1 → say so; that means the
  architecture is being bent and a human should look.
- You cannot make a test fail without your change → the change may not be doing
  anything. Say so.

A stopped task with a clear question is worth more than a finished task that quietly
broke a fingerprint.
