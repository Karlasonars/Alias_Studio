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
| `SPECIFICATION.md` | **How the built thing works today.** Architecture, the eight stages, the checkpoint contract. Read the relevant section before touching a stage — but see the precedence note below. |
| `PRODUCT-REQUIREMENTS.md` | **What it should become and why.** Requirement IDs (`E11-F03`), priorities, acceptance criteria. Written in Latvian. |
| `AGENT-WORKPLAN.md` | **What to do next, in what order, and which files it touches.** Start here when picking up work. |
| `VENDORED-LICENSES.md` | Third-party code. Authoritative — read before adding a dependency. |
| This file | The rules that apply to every task. |

**Precedence: this file wins.** `SPECIFICATION.md` is descriptive and has drifted —
its §5 still shows the two-row fingerprint table, states rule 3 as universal, claims
244 tests, and asserts in bold that the settings-group test catches an unwired group
(it cannot — T-22). Read it for architecture and intent; where it disagrees with §4
or §5 here, this file is correct. T-23 tracks bringing it back into line.

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
  settings_schema.py (487) UI schema — 13 groups; 67 nested + 5 top-level = 72
                           fields, plus CAPTION_FIELDS (15) outside GROUPS and
                           outside the help guard. Real surface: 87
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
  tests/                   263 tests, 15 files

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
uv run pytest -q                    # 263 tests, ~50 s. Needs ffmpeg on PATH:
                                    # test_render_smoke encodes a synthetic clip.
uv run pytest -q -k house_rules     # the §5 guards — but NOT test_settings.py,
                                    # which holds the §5.2 guard. Before a PR,
                                    # run the full suite, not just this.
uv run ruff check .                 # lint

# Frontend — CI runs this, so run it before pushing frontend work
cd app
npm ci                              # what CI runs; npm install drifts the lockfile
npx tsc --noEmit                    # the only frontend check that exists
npm run tauri dev                   # dev builds call `uv run` against ./pipeline,
                                    # so Python changes need no rebuild

# Build — use tauri, NEVER `cargo build --release`
npx tauri build                     # a bare cargo build still points at localhost:1430
```

**Never run the pipeline on real source media or model weights to "check if it
works".** A full job takes 10–60 minutes and downloads ~2.5 GB of models. If you
think you need a real run, say so in the PR and stop.

Synthetic ffmpeg fixtures are fine and the suite already uses them:
`test_render_smoke` encodes a 20-second `testsrc2` clip and burns captions into
it. That is the intended way to verify a render change. Note that it is marked
`@pytest.mark.slow` but the marker is **not registered**, so it runs on every
`pytest -q` — the mark currently does nothing but emit a warning.

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

3. **A missing fingerprint key is compared against the factory default.** Checkpoints
   written before a setting existed lack its key. `fingerprint_ok(stored, current,
   factory)` treats a missing key as the factory value — so a user who never touched
   that setting keeps their hour of transcription, and a user who did gets a re-run.
   "Missing means unchanged" is the wrong summary: it is only unchanged *if the
   current value is still the default*.

   **`fingerprint_ok` has exactly one caller** (`candidates`). Everything below uses
   strict comparison instead, which means rule 3 does **not** hold for those stages.

What each stage actually does — all eight, because the two-row version of this table
is how a shipped setting ended up dead:

| Stage | `artifacts_ok` | Rule 3 holds? |
|---|---|---|
| `ingest` | files exist + source hash | n/a |
| `asr` | **no override** — cached forever once written | n/a |
| `diarize` | **no override** — cached forever once written | n/a |
| `events` | `curves.json` exists — **no settings fingerprint at all** | **no** |
| `candidates` | `fingerprint_ok(...)` — the only caller | yes |
| `scoring` | strict `==` on `settings_used` | no |
| `camera` | two strict `!=` on `__dict__` (`camera`, `retention`) **plus `clip_framing`, which reads `clip_edits.json` off disk** — the only fingerprint that reaches outside `Settings` | no |
| `render` | six strict comparisons | no |

Two live consequences, both worth knowing before you touch any of this:

- **`Settings.laughter_specialist` is a shipped UI toggle that does nothing on a
  re-run.** It is consumed at `events/stage.py:81`, but `events.artifacts_ok` only
  checks that `curves.json` exists. Turn it on for a job that has already run and
  the setting is inert, forever, silently. This violates §5.2 and is tracked as
  T-21 in `AGENT-WORKPLAN.md`.
- **Adding any field to `CameraSettings` or the scoring settings invalidates every
  existing checkpoint**, because those stages compare `__dict__` strictly. That is
  precisely the "throw away an hour of work over an unrelated toggle" failure rule 3
  claims to have solved. It has not been solved outside `candidates`.

Each fingerprint covers **only** what that stage reads. A title edit must not force a
re-encode; a caption tweak must not re-run the expensive camera pass.

**The tests for this section are in `pipeline/tests/test_clip_edit_sync.py`** (23
tests: fingerprint invalidation, structural edits, cache survival). Nothing in §5's
guard file covers the checkpoint contract. If you change a fingerprint, that is the
file that will tell you whether you were right.

---

## 5. Invariants

**Six of these ten are enforced by a test. Four are not, and you need to know which.**

| Invariant | Where the guard lives |
|---|---|
| 5.1, 5.3, 5.4, 5.5, 5.6 | `test_house_rules.py` |
| 5.2 | `test_settings.py` — which `-k house_rules` **deselects**, and which T-22 shows is weaker than it reads |
| **5.7, 5.8, 5.9, 5.10** | **Nowhere. On these you are on your own.** |

**Every guard in this repo is narrower than the rule above it.** §5.3's covers
`read_text`/`write_text` but not `open()`; §5.2's covers a hardcoded list of groups;
the schema help check covers `GROUPS` but not `CAPTION_FIELDS`. A green suite means
"nothing known-checkable broke", not "the rule holds". Read the test before trusting
the heading.

**Do not edit a guard test to silence it.** That is the one change that is never
correct.

**But registering a new field in a guard's classification list is not silencing it** —
it is the guard doing its job. `test_every_clip_edit_field_is_fingerprinted_or_exempt`
exists precisely to make you make that declaration. Adding your field to
`RENDER_FINGERPRINT_FIELDS`, `CAMERA_FINGERPRINT_FIELDS` or
`CLIP_EDIT_RENDER_IRRELEVANT` is expected and required. Changing an assertion,
raising a baseline, or deleting a case is silencing. The line is: **you may tell a
guard what your change is; you may not tell it not to look.**

### 5.1 The four-place law

**A new per-clip or per-job setting touches four places:**

1. the dataclass (`config.Settings` or `edits/timeline.ClipEdit`)
2. the consumer (the code that actually reads it)
3. **the stage fingerprint** (`artifacts_ok`)
4. the UI (`settings_schema.py` entry, or the editor component)

**Number 3 is the one people forget**, and forgetting it makes the setting silently do
nothing on the next run. Not through carelessness: 1, 2 and 4 all produce visible
behaviour the moment you run the app, so you get feedback. 3 only misbehaves on the
*second* run of an existing job — which is not something you do while building the
feature. You can hand-test a new setting to your own satisfaction and never once
enter the broken path.

**5. For a `ClipEdit` field there is a fifth place: the guard's classification list.**
`test_every_clip_edit_field_is_fingerprinted_or_exempt` fails until you add the field
to `RENDER_FINGERPRINT_FIELDS`, `CAMERA_FINGERPRINT_FIELDS`, or
`CLIP_EDIT_RENDER_IRRELEVANT` with a reason. This is expected work, not architecture
being bent, and §10's "stop if you need a fifth place" does **not** apply to it. It is
also not "editing a test to make it pass" — see the carve-out above.

**A field on `config.Settings` has no such guard.** Places 3 and 4 are unchecked for
job-level settings; `test_settings.py`'s group check is coarse and, as written, only
covers a hardcoded list (see T-22). Job-level settings need the four places by
discipline, not by test.

**So supply the missing net yourself:** add a fingerprint test to
`test_clip_edit_sync.py` alongside the existing ones. `test_camera_cache_is_invalidated_by_a_framing_edit`
and `test_render_fingerprint_covers_every_style_the_stage_applies` are the templates —
set up a checkpoint, change the setting, assert `artifacts_ok` returns False. This
also satisfies §7's "one new test that fails without your change" for free.

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
39 call sites currently violate this.

**The baseline is a two-sided pin, not a one-way ratchet.** There are two tests:
`test_no_text_io_without_encoding` asserts `<=` and `test_encoding_baseline_is_not_stale`
asserts `==`. The suite goes red the moment you fix one call site without lowering the
constant. Practical consequence: **a partial sweep is not possible** — every commit
that fixes a violation must lower the baseline in the same commit, and a task that
incidentally fixes one site drags the constant edit into its diff. That is deliberate
(a baseline nobody lowers stops protecting anything), but it is the opposite of what
"ratchet" implies.

**The guard covers `read_text` / `write_text` only.** `open()` is invisible to it —
`events/panns_channel.py:64` is a text read with no encoding that the count does not
see. "Everywhere" in the heading is the rule; the guard is narrower than the rule.

### 5.4 Every `invoke()` lives in `api.ts`

`app/src/api.ts` is the single list of Tauri calls — but it covers only 13 of the 17
Tauri commands (missing: `run_edit_render`, `save_clip_edits`, `save_pexels_key`,
`ig_connect`). **12** direct `invoke()` calls currently sit outside it: `ClipEditor.tsx`
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
good it looks at other values. `test_framing_dial_zero_is_exact_landscape`
(parametrized over four resolutions) and `test_framing_dial_zero_is_exact_portrait`
pin both branches.

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
- [ ] `uv run pytest -q` passes — the **full** suite, not `-k house_rules`, which
      deselects the §5.2 guard in `test_settings.py`.
- [ ] No baseline raised in `test_house_rules.py`. Equal is fine only if you fixed
      nothing — the `==` guard goes red the moment you fix a violation and leave the
      constant alone (§5.3).
- [ ] `uv run ruff check .` is clean.
- [ ] If you touched `app/`: `npx tsc --noEmit` is clean.
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
- **Never mass reformat or reorder imports across files you are not otherwise
  changing.** Diff noise is what makes review impossible.
- `git add --renormalize` is the one exception, and only when line endings are
  genuinely wrong — which is what `guards.yml` tells you to run when its CRLF check
  fails. When you do, it goes in a commit that contains **nothing else**.

---

## 10. When you are stuck

Stop and say so. Specifically:

- The requirement conflicts with an invariant here → say which, do not pick one.
- You need a real pipeline run to verify → say so, do not run it.
- The change would need a fifth place not listed in §5.1 → say so; that means the
  architecture is being bent and a human should look. **Exception: the `ClipEdit`
  guard classification list in `test_house_rules.py` is an expected fifth place —
  register your field there and carry on. See §5.1.**
- You cannot make a test fail without your change → the change may not be doing
  anything. Say so.

A stopped task with a clear question is worth more than a finished task that quietly
broke a fingerprint.
