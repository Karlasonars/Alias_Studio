# CLAUDE.md — working rules for this repository

You are working on **Alias Studio**: a desktop app that turns one long horizontal
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

**Precedence: this file wins.** `SPECIFICATION.md` is descriptive — it says how the
built thing works; this file says what you must not break. T-23 brought its §5, §15
and §17 back into line, so they agree today. They will drift again, because one
changes when the code changes and the other when a rule is learned: where they
disagree, this file is correct, and the disagreement is a bug worth reporting.

Your task will name a requirement ID. That ID is the contract: implement exactly it,
nothing adjacent.

**Language:** the codebase, comments, tests, commit messages and PR descriptions are
**English**. `PRODUCT-REQUIREMENTS.md` is Latvian; translate what you need, do not
mirror it into the code.

---

## 2. Repository map

```
pipeline/publikclip_pipeline/     the product — ~11,000 lines of Python
  cli.py            (718)  argparse surface; the sidecar's entry point
  config.py         (452)  the whole settings tree
  settings_schema.py (492) UI schema — 13 groups; 67 nested + 6 top-level = 73
                           fields, plus CAPTION_FIELDS (15) outside GROUPS.
                           Real surface: 88, all of it help-guarded
  hardware.py       (231)  CUDA/CPU detection. The single place that answers
                           "what can this machine do"
  errors.py                the error catalogue (T-13). describe() is the ONLY
                           constructor of the user-facing error value and it
                           redacts every field — add entries, never a second
                           path around it
  jobs/queue.py     (355)  Job/Stage machinery, SQLite, checkpoints
  ingest/ asr/ diarize/ events/ candidates/ scoring/ camera/ render/
                           the eight stages, in that order
  captions/ass.py   (429)  ASS subtitle generation. 5 built-in presets
  copywriting/             titles, descriptions, hooks
  edits/                   per-clip editing + single-clip render
  insights/calibration.py  (908) LARGEST FILE. Instagram feedback + calibration
  models/specs.py    (82)  weight registry
  vendor/                  DO NOT EDIT — see §6
  tests/                   15 files. No exact count here on purpose —
                           see §3

app/src/                          React frontend
  App.tsx           (321)  view router + the pipeline-event listener. The 'job'
                           event is where a job START is observed — every path
                           into a running job goes through it (§5.12)
  api.ts             (88)  EVERY invoke() belongs here — see §5.4
  types.ts          (405)  the Rust↔TS contract. Nothing enforces it at runtime
  styles.css       (1441)  all styling, including themes
  components/QueueView.tsx (191)  the queue. Reads SQLite via `--jsonl jobs`;
                           the library rail reads the filesystem. Two views,
                           two truths, deliberately
  components/ClipEditor/   nine files, 1151 lines — one 1175-line component until
                           T-03. Largest is now Controls.tsx (293). Split by state
                           ownership, not by visual region; §6 says why
  test/tauri.ts + *.test.tsx  the T-36 suite: vitest + jsdom. Started as 5 tests
                           re-catching T-08's hand-found defects; T-09/T-10/T-11
                           grew it (no count here on purpose — §3's lesson; `npm
                           test` prints it). The Tauri boundary is mocked at the
                           module seam — see §7
app/src-tauri/src/main.rs (1253)  the whole Rust layer. Was 544 before T-07 and
                           T-08; it now holds RunState, the Job Object kill, the
                           queue runner, the queue cache and T-11's setup runner.
                           See §6 — it is a danger zone now, not a thin shell,
                           and at this size a split task is overdue
```

**Three processes, one direction of control:** React → Rust (Tauri) → Python sidecar.
The Rust layer holds no product logic; the frontend holds no product logic. Anything
worth unit-testing belongs in Python.

**That rule is doing more work than it looks like, and T-08 is where the line was
drawn explicitly.** Rust owns *triggers* — it asks Python "what is next" and spawns
the answer. Python owns every *decision*: what is eligible, in what order, what a
failure means for the rest. The one judgement that legitimately sits in the shell is
gesture semantics — what the user's action meant (a completion advances the queue, a
cancel holds it; a cancelled exit is not a crash). If you find yourself teaching Rust
which job to run or reading SQLite from it, the line has moved and a human should
look.

**Artifacts on disk are the source of truth.** SQLite records only what *should*
exist. If the database and the disk disagree, the disk wins.

---

## 3. Commands

```bash
# Python pipeline
cd pipeline
uv sync
uv run pytest -q                    # ~292 tests (264 functions + parametrized),
                                    # 18 files, ~50 s. Needs ffmpeg on PATH:
                                    # test_render_smoke encodes a synthetic clip.
                                    # No exact test count is written down anywhere
                                    # in these docs: it changed with every task and
                                    # was wrong in four consecutive revisions, and
                                    # knowing it is 275 rather than 272 helps no
                                    # one. `pytest -q` prints it.
uv run pytest -q -k house_rules     # the §5 guards — but NOT test_settings.py,
                                    # which holds the §5.2 guard. Before a PR,
                                    # run the full suite, not just this.
uv run ruff check .                 # lint

# Frontend — CI runs this, so run it before pushing frontend work
cd app
npm ci                              # what CI runs; npm install drifts the lockfile
npx tsc --noEmit                    # typecheck
npm test                            # vitest run — the T-36 suite (~2 s). CI runs
                                    # both; a green tsc alone proves compilation,
                                    # not behaviour
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

**Rewriting files from a script on Windows: pass `newline="\n"`.**
`Path.write_text(s, encoding="utf-8")` opens in text mode, so Python translates
every `\n` to `\r\n` and a whole-file rewrite comes back CRLF. `.gitattributes`
normalises on staging, so the commit is clean and the guard stays green — which is
exactly why this is easy to miss: nothing fails, git just warns on every command and
the working copy stops matching the index. Use
`p.write_text(s, encoding="utf-8", newline="\n")`, or write bytes. Found in T-06,
where a scripted sweep flipped 14 files and had to convert them back by hand.

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

   **`fingerprint_ok` has three callers** — `candidates`, `events` (T-21) and
   `scoring` (T-39). `camera` and `render` use strict comparison instead, which
   means rule 3 does **not** hold for those two.

What each stage actually does — all eight, because the two-row version of this table
is how a shipped setting ended up dead:

| Stage | `artifacts_ok` | Rule 3 holds? |
|---|---|---|
| `ingest` | files exist + source hash | n/a |
| `asr` | no override — **correct: reads zero settings** | n/a |
| `diarize` | no override — **correct: reads zero settings** | n/a |
| `events` | `curves.json` exists + `fingerprint_ok` on `laughter_specialist` | yes |
| `candidates` | `fingerprint_ok(...)` — the only caller | yes |
| `scoring` | `fingerprint_ok` on `settings_used` (model + weights + word gate) | yes (T-39) |
| `camera` | two strict `!=` on `__dict__` (`camera`, `retention`) **plus `clip_framing`, which reads `clip_edits.json` off disk** — the only fingerprint that reaches outside `Settings` | no |
| `render` | six strict comparisons | no |

Two live consequences, both worth knowing before you touch any of this:

- **`Settings.laughter_specialist` was a shipped UI toggle that did nothing on a
  re-run** — `events.artifacts_ok` only checked that `curves.json` existed. Fixed in
  T-21 (`7f3d7da`), and worth reading as the worked example of this whole section:
  the fix had to use `fingerprint_ok`'s `or {}` form, because no events checkpoint
  ever written carries the new key and `fingerprint_ok(None, …)` is False — so the
  naive fix for rule 1 would have re-run the PANNs pass on every job already on
  disk and cascaded into four stages. Fixing rule 1 by breaking rule 3.
- **`ingest`, `asr` and `diarize` read zero settings** (verified by grep, not
  assumed), so having no fingerprint is correct there rather than an oversight.
- **Adding any field to `CameraSettings` invalidates every existing camera and
  render checkpoint**, because those two stages compare `__dict__` strictly. That is
  precisely the "throw away an hour of work over an unrelated toggle" failure rule 3
  claims to have solved. It has not been solved for `camera` or `render`; scoring
  joined the fingerprint_ok callers in T-39, exactly because a strict comparison
  there would have re-spent real LLM money on every job already on disk when
  `gemini_model` arrived.

Each fingerprint covers **only** what that stage reads. A title edit must not force a
re-encode; a caption tweak must not re-run the expensive camera pass.

**The tests for this section are in `pipeline/tests/test_clip_edit_sync.py`** (28
tests: fingerprint invalidation, structural edits, cache survival) and, for rule 2
specifically, `test_queue.py:test_a_rerun_stage_invalidates_every_stage_after_it` —
added in T-21, because the rule the whole cascade depends on had no direct test. Nothing in §5's
guard file covers the checkpoint contract. If you change a fingerprint, that is the
file that will tell you whether you were right.

---

## 5. Invariants

**Seven of these twelve are enforced by a test. Five are not, and you need to know which.**

| Invariant | Where the guard lives |
|---|---|
| 5.1, 5.3, 5.4, 5.5, 5.6 | `test_house_rules.py` |
| 5.2 | `test_settings.py` — which `-k house_rules` **deselects**, and which T-22 shows is weaker than it reads |
| 5.11 | `test_secret_leaks.py` |
| **5.7, 5.8, 5.9, 5.10, 5.12** | **Nowhere. On these you are on your own.** |

**A guard can be narrower than the rule above it.** The live example is §5.3's: it
covers `read_text`/`write_text` and cannot see `open()`. A green suite means "nothing
known-checkable broke", not "the rule holds" — read the test before trusting the
heading.

*Two other examples stood here until T-22 and turned out not to hold: §5.2's group
list is no longer hardcoded, and `CAPTION_FIELDS` was guarded all along by
`test_settings.py`, more strictly than the `test_house_rules.py` copy. Both were
written down from a report without being checked. Verify a "there is no guard for
this" claim with a grep before it becomes a documented fact — it is the cheapest
check there is, and it was skipped three times.*

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

**A task can *be* one of the four places.** §5.1 is written in the voice of adding a
new setting, but the audit findings are producing tasks that supply a place a shipped
setting never got — T-21 was place 3 arriving late for `laughter_specialist`. The
checklist does not apply to those; say so in the PR rather than reporting N/A and
leaving the reader to guess whether you understood it.

**A field on `config.Settings` has no such guard.** Places 3 and 4 are unchecked for
job-level settings; `test_settings.py`'s group check is coarse and, as written, only
was blind to new groups until T-22 fixed it — it now resolves them through
`get_type_hints`. It still only asks whether a group is *read anywhere*, not whether
it is fingerprinted. Job-level settings need places 3 and 4 by discipline, not by
test.

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

**The baseline is 0 (T-06, `e817164`), which makes this a plain rule rather than a
ratchet.** Two tests hold it there: `test_no_text_io_without_encoding` asserts `<=`
and `test_encoding_baseline_is_not_stale` asserts `==`. At 0 they agree, and any new
violation fails both. There is no baseline left to lower and none to raise — if you
find yourself editing that constant, you are adding a violation, not managing debt.

**The guard covers `read_text` / `write_text` only.** `open()` is invisible to it —
`events/panns_channel.py:64` is a text read with no encoding that the count does not
see. "Everywhere" in the heading is the rule; the guard is narrower than the rule.

### 5.4 Every `invoke()` lives in `api.ts`

`app/src/api.ts` is the single list of Tauri calls. It covers 15 of the 17 Tauri
commands; `save_pexels_key` and `ig_connect` have no wrapper at all. **6** direct
`invoke()` calls sit outside it: `IgModal.tsx` (3), `KeyModal.tsx` (3). T-03 moved
`ClipEditor`'s six in and lowered the baseline from 12.

**Only two of the remaining six lack a wrapper.** The other four — `ig_status`
twice, `get_setup_state`, `save_gemini_key` — call a command `api.ts` already
wraps, so those are not "add it to api.ts", they are "use the function that is
already there". A smaller job than the count makes it look, and worth knowing
before someone scopes it as four new wrappers.

`test_no_invoke_outside_api_ts` is a **two-sided pin, not a ratchet** — `==` at
line 248, `<=` at line 256. Fix one call site without lowering the constant and the
suite goes red, exactly as in §5.3. Add new commands to `api.ts` and nowhere else.

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

**Adjacent versus consequential.** §8 tells you not to widen scope; this rule can
still oblige you to touch a file your task did not name. The line is: *adjacent* work
is what you could have done without your change, and it stays out. *Consequential*
work is what your change makes necessary, and it is part of the change. When a fix
turns a path that used to degrade into one that raises, restoring the degradation is
not scope creep — it is finishing the fix. Shipping the regression with a note
explaining it is worse than not shipping it. T-06 is the worked example: adding
`encoding="utf-8"` to five reads made `UnicodeDecodeError` reachable where those
handlers had only ever seen `JSONDecodeError` and `OSError`, so widening them was
consequential; the identical hole in `render/stage.py`, which predated the sweep, was
adjacent and became T-24.

### 5.10 Verify outputs

Every rendered clip is checked for streams and sane duration before it is reported as
done.

### 5.11 A secret is never in a URL

API keys go in headers. Never in a query parameter, never in a path.

This is not style. `httpx` puts the full request URL into the text of every
`HTTPStatusError`, the scoring stage folds that text into its error message, and the
app renders that message in the live console. Nobody wrote a line that logs a key —
the leak came from composing two entirely reasonable things, and the owner's Gemini
key ended up on screen and in his screenshots. It had to be rotated.

`test_secret_leaks.py` guards it by building the same `httpx.Request` the code would
issue, so a key passed as a parameter genuinely lands in the URL. It asserts the key
is absent from the raised error text and present in the header.

The guard covers the Gemini paths. **Instagram is not fixed**: `access_token` and
`client_secret` still ride as query parameters at six call sites in
`insights/instagram.py`. No `IgError` quotes a URL today, so nothing leaks yet —
which is exactly the state `visuals.py` was in before someone would have added error
output to it. T-32.

Redaction is a belt, not the fix. If a secret can be in a URL, some layer will
eventually print that URL.

### 5.12 A job start is one transition, wherever it came from

A job can start four ways: the user enqueues while idle, the queue advances on its
own, START QUEUE, or a rail resume. All four must leave the screen in the same
state — this job's stage bars, this job's log, no stale error, no stale cancelled
notice, and the cancel affordance available.

They did not. The reset lived in the click handler for one of the four paths, so an
auto-advanced job inherited the previous job's screen: six stages already green while
the second was still transcribing, and — because `running` never returned to true —
**no Cancel button at all.** T-07's kill was unreachable for exactly the jobs the
queue exists to run, and the suite was green throughout.

Put the reset where the transition is *observed* (`App.tsx`'s `'job'` event), not
where each trigger lives. The same reasoning applies to anything else that must be
true whenever a job starts.

Note the asymmetry: enqueueing is **not** a start. A busy enqueue must never clear
the running job's screen. Both halves have been broken once each.

---

## 6. Danger zones

**Scripted rewrites run against a named file list, never a tree walk.** Two tasks
have now been bitten by `rglob`-style sweeps: T-06 flipped 14 files to CRLF because
`Path.write_text` translates newlines on Windows, and T-22's cleanup wrote to 42
files including `vendor/`. Both were caught and reverted, both left the tree
byte-identical — and neither should have been possible. Build the list first, print
it, then write. "The diff came out empty" is not the same as "I was allowed to write
there".

**After a scripted rewrite, `git status` lies until you refresh the index.** Files
show as modified while `git diff` is empty: the stat cache is stale because mtimes
changed, not because content did. `git update-index --refresh` clears it instantly.
This is how T-22's cleanup ended up writing into `vendor/` — it was "repairing" 42
files that had nothing wrong with them.

**`pipeline/publikclip_pipeline/vendor/` — do not edit.** `clippyme`, `laughter`,
`panns` and `campplus` are copies of upstream projects, and two upstreams are
themselves AGPL-3.0. Modify only when you must, and record it in
`VENDORED-LICENSES.md` in the same commit. Guard tests skip this tree; that is not
permission to lower its standards.

**`app/src/components/ClipEditor/` — split in T-03, and the split is load-bearing.**
Nine files, largest 293 lines. The boundaries follow **state ownership, not visual
regions**: the plan that used to sit in the workplan proposed `Timeline` /
`PreviewPane` / `ControlsPanel` and was wrong — `selectedOverlay` alone is read by
three children that would have straddled two of those regions.

Three v1.0 features land here (`E6-F01`, `E6-F02`, `E6-F04`). Add them along the
seams that exist, and read `useClipEdit.ts` before touching anything that renders
during playback: it assigns `editRef` and `ctxRef` **during render**, deliberately,
so the rAF loop in `usePlayer.ts` reads current values without re-subscribing. That
loop's dependency array is `[win, span]` and does **not** include `edit`. Break
either and the preview plays against stale state — no error, wrong frames. T-36
added a component test runner, but nothing covers this rAF path: for this file,
`tsc --noEmit` is still the whole net.

**`pipeline/publikclip_pipeline/insights/calibration.py` (908 lines).** Largest file in
the pipeline, and about to carry two more platforms. Same advice.

**`app/src-tauri/src/main.rs` — 993 lines, and no longer a thin shell.** It was 544
before T-07 and T-08. It now holds `RunState` (the active run and the Windows Job
Object handle that kills the process tree), the queue runner, the queue cache and the
cancel latch. Two things follow. First, it is a split candidate on the same grounds
`ClipEditor.tsx` was. Second and more urgent: **the kill path has no automated test
of any kind.** `cargo check` proves it compiles. Nothing proves it kills anything.
Any change to the spawn path can silently un-break the process tree kill, and the
only thing that would notice is a person watching Task Manager. Read §7's hand-test
clause before touching `stream_pipeline` or `start_job_locked`.

**`pyproject.toml` CUDA index config.** `uv run` re-syncs from this file on every
launch, so a side-loaded CUDA torch build is silently replaced by the CPU one. The
installed app has its **own copy** under `resources/pipeline/` — fixing the repo copy
alone does not fix an installed build.

**Drag interactions.** Update local state continuously in `onMove`, call `persist()`
once in `onUp`. Follow that pattern for any new slider or handle.

`ClipEditor/index.tsx` follows it for the monitor drag only (`onUp` at line 124 persists
only when `monitorDragRef` is set). Timeline bound and overlay drags update state and
are never persisted on mouseup — they survive on whatever calls `persist()` next, or
on `doRender()` saving on its way out. Whether that is intended or a bug is
**unresolved**. Do not "correct" it as part of another task; if you think it is
wrong, file it.

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
- [ ] If you touched `app/`: `npx tsc --noEmit` is clean **and `npm test` is green.**
- [ ] At least one new test **fails without your change**. Verify this by reverting
      your change and watching it fail; a test that passes both ways tests nothing.
      **When your change strengthens a guard rather than altering behaviour,
      reverting proves nothing** — both versions pass on a clean tree. Verify by
      injecting the defect the guard exists to catch, then showing the old version
      passes it and the new one fails. **When a task changes no behaviour at all**
      (documentation, a pure move), this item does not apply: say so explicitly in
      the PR rather than inventing a test to satisfy it.
- [ ] Every attribute your test sets actually exists. `config.Settings` and its
      groups are ordinary dataclasses, so `settings.curve.weights = …` on a field
      that was never declared creates it silently and the assertion then passes
      while testing nothing. Caught in T-21 before it shipped; it would not have
      failed any guard.
- [ ] If you added a setting: all four places from §5.1, in this commit.
- [ ] If you added a `ClipEdit` field: classified in the fingerprint test.
- [ ] Comments explain **why**, not what — document the failure the code prevents.
      Match the surrounding file's comment density and idiom.
- [ ] No new file over ~400 lines without saying why in the PR.
- [ ] **If you touched `app/` or the Rust shell: the hand test, and it is not a
      formality.** See below.

### Frontend tests exist now (T-36). Know what they cover — and what they cannot.

`npm test` runs vitest (jsdom + testing-library) over `app/src/*.test.tsx`;
guards.yml runs it after the typecheck. The Tauri runtime does not exist in a
test, so `invoke`/`listen` are mocked at the module seam (`src/test/tauri.ts`) —
**no product code was restructured to be testable**, and the §5.4 guard scans the
test files like any other: they contain no direct `invoke(` and must stay that way.

The suite earned its place by re-catching T-08's hand-found defects. That task
shipped to review with **289 green tests and green CI**, and one afternoon of a
person clicking found seven, every one invisible to everything automated:

1. enqueueing while busy changed nothing on screen — six duplicate jobs queued.
   **Pinned** (`App.test.tsx`)
2. the queue view rendered inside a 264 px column. **CSS — a DOM test cannot see
   layout; still hand-test only**
3. it polled a `uv run` subprocess every 2 s, stacking processes faster than they
   could answer. **Pinned** (`QueueView.test.tsx` — one ask at mount, none on a
   60 s fake clock)
4. the rail footer had no layout rule at all; a fourth button broke it. **CSS —
   same as 2**
5. the queue view was a flat history list — a waiting job was indistinguishable
   from one cancelled days ago. **Partially pinned**: the NOW / UP NEXT / HISTORY
   sections and FIFO numbering are asserted; whether they *read* well is not
6. an auto-advanced job inherited the previous job's stage bars. **Pinned**
7. and, worst, `running` never returned to true, so **every job after the first
   had no Cancel button** — T-07's process-tree kill unreachable for exactly the
   jobs the queue exists to run. **Pinned — the most valuable test in the suite**

What the suite still cannot see, and the hand test still owns: **CSS layout**
(defects 2 and 4 were real, and a class-name assertion would test the test, not
the layout), **the Rust kill path** (§6 — nothing but Task Manager proves a
cancel kills the process tree), and **anything needing a real job's artifacts**
(§3 forbids producing them).

So the hand-test rule stands — narrowed, not retired: a UI or shell task carries
a hand-test checklist in its PR **for what the suite cannot see**, written for
someone who has not read the thread — what to click, and what must appear. Say
plainly which steps you ran and which you could not. **Do not describe a step you
did not run.** Steps needing a completed job's artifacts belong to whoever has a
machine with models, and the PR should say so rather than quietly omitting them.
And when a UI behaviour *is* pinnable, pin it: a UI change ships with a test the
way a Python change does.

### Who runs the checklist, and when — the standing policy

**Write the checklist. Do not expect it to be run before merge.** The owner is
deferring hand-testing to one session before v0.9 ships, deliberately, to keep
velocity while the surface is still moving. A merged PR therefore means "green
and reviewed", **not** "exercised by a human". Write every checklist as if the
person reading it has forgotten this project entirely, because by then they
nearly will have.

**One exception, and it is sixty seconds.** If your change touches
`stream_pipeline`, `start_job_locked`, or anything else on the path that spawns
the sidecar, the owner runs the kill check before merge: start a job, press
CANCEL, confirm no `uv`/`python`/`ffmpeg` survive. Say so at the top of your
checklist when it applies.

Why that one and nothing else: nothing in this repository tests it. `cargo check`
proves the code compiles. It has already been broken once — after T-08 every
auto-advanced job had no Cancel button at all — and its symptom is an ffmpeg
quietly burning a core after the UI said "cancelled", which is not something
anyone notices while testing a feature. Every other defect this policy defers is
visible the moment someone looks; this one is not.

**The obligation this puts on you: earn your way off the list.** Before writing a
hand-test step, say why it cannot be a test. "It is UI" is not a reason — T-36
exists and pinned five of T-08's seven. CSS layout, the kill path, and anything
needing a real job's artifacts are the three honest categories; a step that is
not one of those belongs in `*.test.tsx` or `tests/`, not in the owner's evening.
A PR whose checklist grew instead of shrinking should explain why.

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
- **Branch from the commit that contains your task's own entry, not reflexively from
  `main`.** Doc corrections often land on a branch that is ahead of `main`, and a task
  whose entry, invariants or numbers live there must be based on it. Name in the PR
  which branch must merge first.
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
