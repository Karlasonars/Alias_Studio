# AGENT-WORKPLAN.md — what to build, in what order

The execution order behind `PRODUCT-REQUIREMENTS.md`. That document says *what and
why*; this one says *next, and which files*.

**Mode: one agent at a time, sequentially.** Each task is one requirement ID, one
branch, one PR. Do not start a task whose blockers are unmerged.

**Before every task:** read `CLAUDE.md`, then the section of `SPECIFICATION.md` that
covers the stage you are touching, then the requirement in `PRODUCT-REQUIREMENTS.md`.
Do not read the whole PRD — it is 78 pages and most of it is not your task.

**`CLAUDE.md` wins on any conflict.** `SPECIFICATION.md` has drifted: its §5, §15 and
§17 still carry the pre-correction fingerprint table, test counts and house rules.
Read it for architecture and intent, not for current fact. T-23 fixes it.

---

## How to read a task entry

```
### T-07 · E2-F07 — Job cancellation                            [P0, v0.9]
Blocked by  what must be merged first
Touches     files you are expected to change
Do not      files this task must not touch
Proves it   the test that fails without the change
Watch out   the invariant most likely to be broken here
```

**"Touches" is a budget, not a suggestion.** If the change needs a file outside the
list, that is a signal the task was scoped wrong — say so in the PR rather than
widening it silently. It can also be wrong the other way: T-22's list named one test
file and the task needed two. A budget that turns out too small is a finding, not a
licence.

---

## Which model runs which task

**Default: development on the stronger model, documentation on the cheaper one.**
That split is easy to apply without thinking, which is most of its value — a rule you
follow every time beats a sharper one you apply unevenly.

**Three exceptions, all in the same direction.** These produce a document but the work
is verification, and a literal reading of them can hurt someone:

| Task | Why it is not a documentation task |
|---|---|
| T-05 | Pinning checksums looks like data entry. The PANNs note is a trap: the ~312 MB file is correct and the 514 MB response is the corrupt one. Pin the wrong hash and every user's download fails, and no test catches it — the guard checks that a sha256 *exists*, not that it is right |
| T-17 | The privacy notice is an audit of every network call in the codebase. Miss one and the document lies about the product's central promise |
| T-18 | AGPL compliance in the UI is legal, plus a screen. Half of it is code |

**Spotting the next one.** Read the task's own `Proves it` line, then ask the question
that matters: *would that proof catch a literal-but-wrong execution?*

- `Proves it` names a test that would fail on a wrong answer → cheaper model is fine
- `Proves it` says "read-and-compare", "manual", or names a check that only confirms
  the *shape* of the answer → stronger model

T-06 is the worked example of the second case. Its proof was a baseline dropping 39 →
0, which a literal sweep would have satisfied — while turning a silently-wrong read
into a crash in the user's clip editor. The number went to zero either way.

---

## Phase 0 — hygiene, before any feature work

These are unblocked, take hours not days, and every later task is easier because of
them. Do them in this order.

### T-01 · E16-F07 — Line endings                              [DONE 2026-08-25]

```
Merged      95f493d  repo: add .gitattributes
Proves it   guards.yml "No CRLF in tracked text files"
```

Done before the first agent started. Recorded here because the reasoning was
corrected along the way, and the correction is worth knowing.

**What was claimed:** 82 modified files, 26,550 phantom lines, "the repository is
unreadable". **What was true:** `git ls-files --eol` reports 112 tracked text files
with LF in the index and **zero** with CRLF. The stored content was always clean.

The real problem was the missing *declaration*: with no `.gitattributes` and no
`core.autocrlf`, a Windows working tree ends up CRLF while the index stays LF, so the
same checkout reads clean on Windows and as 82 modified files from Linux. Ambiguity,
not damage. `git add --renormalize .` touched exactly one file.

**Why it is still in this plan:** the ambiguity would have surfaced as noise in
someone's PR eventually, and five minutes of work removed it permanently. But the
severity was wrong, and a plan that never records its own corrections stops being
worth reading.

### T-02 · Guard tests and lint                               [DONE 2026-08-26]

```
Merged      d9e8e72  CLAUDE.md, AGENT-WORKPLAN.md, test_house_rules.py, ruff.toml
            152c32b  ci: run guards on pull requests
            9604c9d  pipeline: enable ruff, and fix what it found
Proves it   guards.yml green on a pull request
```

Both workflows carry a `pull_request:` trigger and `ruff check` is clean.

**Everything in Phase 1 is now unblocked.** An earlier revision of this file left
T-02 as "partly done" after the work had landed, which — read literally, under this
file's own "do not start a task whose blockers are unmerged" rule — made all of
Phase 1 unstartable. Stale status in a document that gates work is not cosmetic.

### T-21 · `events` has no settings fingerprint               [DONE 2026-08-26]

```
Merged      7f3d7da  events: fingerprint the laughter specialist (PR #2)
Touches     pipeline/publikclip_pipeline/events/stage.py
Proves it   a new test: flipping laughter_specialist on a job with an existing
            events checkpoint must invalidate it
Watch out   Stage order is ingest → asr → diarize → events → candidates → scoring
            → camera → render. events is upstream of FOUR stages, including
            candidates — the only stage in the pipeline that calls fingerprint_ok,
            so the one whose invalidation semantics differ from everything else in
            the cascade. Invalidating correctly is right but expensive. Do not
            widen the fingerprint beyond what the stage actually reads
```

`events.artifacts_ok` is `return (job_dir / "curves.json").exists()`. It reads
`Settings.laughter_specialist` at line 81, and that setting is a shipped UI toggle
(`settings_schema.py:380`). **Turning it on for a job that has already run does
nothing, forever, silently.** That is a live violation of CLAUDE.md §5.2, and it is
the exact failure the checkpoint contract exists to prevent.

Found by the first agent during orientation, before it wrote a line of code. Check
the other stages in the same pass: `asr` and `diarize` have no `artifacts_ok`
override at all, which may be correct (neither reads a user-facing setting) but is
undocumented either way.

### T-22 · The settings-group guard cannot see new groups  [DONE 2026-08-26]

```
Blocked by  nothing
Touches     pipeline/tests/test_settings.py (the group list at ~line 129)
Proves it   adding a new dataclass group to config.Settings and not reading it
            makes the test fail
```

`config.py` has `from __future__ import annotations`, so `f.type` is the *string*
`"CameraSettings"` and `dataclasses.is_dataclass(f.type)` is always `False`. Only the
hardcoded ten-name tuple is ever checked. The test written to catch "a whole settings
group silently does nothing" **cannot catch a newly added group** — the precise case
it exists for.

`descriptions` already sits outside that list. It happens to be read at `cli.py:309`,
so there is no live bug — but that is luck, not the guard working.

Fix: `typing.get_type_hints(config.Settings)` instead of `f.type`, and delete the
hardcoded tuple so it cannot drift again.

**Same pass, same shape:** `test_schema_fields_all_carry_help` iterates `GROUPS` only.
`settings_schema.CAPTION_FIELDS` is 15 more user-facing fields outside that loop. They
all carry `help` today, but nothing checks that they keep doing so. Extend the test.

### T-23 · `SPECIFICATION.md` has drifted from the code  [DONE 2026-08-26]

```
Blocked by  nothing
Touches     SPECIFICATION.md §5, §15, §17
Proves it   no automated test — this one is read-and-compare
```

`CLAUDE.md` §4 and §5 were corrected; their source document was not, and both files
tell an agent to read it. Specifically wrong today:

- **§5** — two-row fingerprint table (`camera`/`render` only), and rule 3 stated as
  universal with no mention that `fingerprint_ok` has one caller.
- **§15** — "244 tests, no video or model I/O in the default run". Both halves wrong:
  263 tests, and `test_render_smoke` shells out to ffmpeg on every run. The per-file
  table omits `test_house_rules.py` entirely; `test_insights_sync.py` is 33 not 19,
  `test_instagram_auth.py` is 19 not 12.
- **§15** closes in bold with "when you add a settings group, this test is what tells
  you that you wired it" — the exact guarantee T-22 shows to be false.
- **§17** — four places, no fifth; and scopes UTF-8 to "checkpoint or settings files"
  where `CLAUDE.md` says every call and the guard scans every non-vendor `.py`.
  Three scopes, three documents, one test.

Until this lands, `CLAUDE.md` §1 carries a precedence note. That is a patch over the
problem, not the fix.

### T-24 · `_load_clip_edits` does not survive an undecodable file  [DONE 2026-08-26]

```
Blocked by  nothing
Touches     pipeline/publikclip_pipeline/render/stage.py (the except at ~line 34)
Proves it   a new test: a clip_edits.json holding invalid UTF-8 must make
            render.artifacts_ok answer, not raise
Watch out   this is the render fingerprint's read path. Degrading to {} means
            "no per-clip edits", which invalidates nothing — check that is the
            answer you want before copying edits/store.py's handler verbatim
```

`render/stage.py:_load_clip_edits` is the second reader of `clip_edits.json` — the
render stage keeps its own copy so it does not depend on the editing package. It
already passes `encoding="utf-8"` and it already catches only `(JSONDecodeError,
OSError)`, so `UnicodeDecodeError` escapes it. It feeds `_clip_edits_fingerprint`,
which feeds `render.artifacts_ok`: a file an older build wrote under the Windows ANSI
codepage crashes the render fingerprint rather than degrading (CLAUDE.md §5.9).

**This predates T-06 and was not caused by it.** That line was never one of the 39 —
it already had its encoding — so the sweep neither introduced the hazard nor was
required to fix it. T-06 widened the same handler at the five sites its own change
made reachable and deliberately left this one; see that PR's "did not do".

### T-25 · Two loose ends from the audit-cleanup batch     [P2, found 2026-08-26]

```
Blocked by  nothing
Touches     pipeline/publikclip_pipeline/render/stage.py (_previous_outputs),
            pipeline/tests/test_house_rules.py (the help threshold)
Proves it   a test for the first; the second is a one-line decision
```

Two things T-24 and T-22 surfaced and correctly left alone.

**`_previous_outputs` (`render/stage.py:50`)** carries T-24's exact hazard: reads
`render.json` as UTF-8, catches `(JSONDecodeError, OSError, KeyError, TypeError)` but
not `UnicodeDecodeError`. It is reachable only from `run()`, never from
`artifacts_ok`, so it is a different failure from T-24's — and by §5.9's
adjacent/consequential test it was adjacent, which is why it is here and not in that
commit. Correct call; still worth fixing.

**The help-text guard exists twice, at two thresholds.**
`test_settings.py::test_every_schema_field_has_help_text` requires `len(help) >= 20`
and covers `GROUPS` plus `CAPTION_FIELDS`. `test_house_rules.py`'s copy requires only
non-empty. The duplication earns its place — `-k house_rules` deselects the other
file — but two thresholds for one rule will eventually disagree. Raise the
house-rules copy to match, or delete it and accept that the guard only runs in the
full suite. Decide, do not leave both.

### T-03 · Split `ClipEditor.tsx`                               [P1, before E6]

```
Blocked by  T-01
Touches     app/src/components/ClipEditor.tsx (1175 lines) → a ClipEditor/ directory
Do not      change any behaviour; this is a pure move
Proves it   npx tsc --noEmit clean; the editor still opens, saves and re-renders
Watch out   the onMove/onUp persist pattern must survive the split intact
```

Three v1.0 features land in this file ([E6-F01], [E6-F02], [E6-F04]). It is already
22 % of the frontend. Split first, or the three tasks after it are unreviewable.

**The "suggested shape" that used to sit here — `Timeline` / `PreviewPane` /
`ControlsPanel` — was written without reading the component, and reading it says
otherwise.** It is one function: 1071 lines, 15 `useState`, 7 `useEffect`, 10
`useRef`. Those names cut across visual regions; the state does not run along those
seams. **Split by state ownership or you will drill twenty props.** Propose the
boundaries and stop before moving anything.

Five landmines, all of which typecheck fine after being broken:

1. **Two refs are assigned during render, not in an effect** (lines 130 and 132:
   `editRef.current = edit`, `ctxRef.current = ctx`). The rAF loop reads them to get
   the latest values without re-subscribing. The ref must travel with the state and
   stay assigned in the same render pass — break it and the preview plays against a
   stale edit. No error, wrong frames.
2. **The rAF effect's dependency array is `[win, span]` and that is deliberate** — it
   does not depend on `edit`, because it reads `editRef`. Move the loop into a child
   that takes `edit` as a prop and the natural dependency array restarts the loop on
   every state change: every drag frame, every keystroke. Visible stutter, nothing red.
3. **`setTimeLabel` runs on every animation frame** (line 247), so the component
   re-renders ~10×/s during playback. Survivable in one component; after a split with
   prop drilling it is every child. Put `timeLabel` in its own leaf — and note in the
   PR that doing so is a performance change inside a task defined as a pure move.
4. **Three `window` listeners across two effects** — `keydown` (297), `mousemove` ×2
   and `mouseup` (361–363). They must land in exactly one component. `StrictMode` is
   on, so a double mount double-attaches; dev shows it, CI does not.
5. **The persist asymmetry.** See CLAUDE.md §6. Do not "fix" it here.

**There is no frontend test infrastructure at all** — no vitest, no jest, no
`.test.tsx`, and `package.json` has four scripts, none of them `test`. `tsc --noEmit`
is the entire net, and it will happily typecheck an animation loop reading stale
state. §7's "one new test fails without your change" does not apply; say so and carry
a manual checklist instead: open the editor, drag both bounds, scrub, play through a
dead-space cut, drag an overlay on the timeline and on the monitor, change a caption
preset, render. Two more steps, because the obvious list misses landmines 1 and 2:
**type in the title field while playback is running** (if the rAF loop restarts on
every state change, the stutter is immediate), and **move a bound, then play without
persisting** (the preview must follow the new bound, not the stale one). Adding a test runner is its own task and its own PR.

Move the 6 `invoke()` calls into `api.ts` — that lowers
`INVOKE_OUTSIDE_API_BASELINE` from 12 to 6. Note that three of them are
`save_clip_edits` with an identical argument shape (373, 378, 387) but three
different intents: 373 is inside `persist()`, the other two are pre-flight saves
before render and before suggest. Collapsing them is slightly more than a move —
worth one sentence in the PR either way.

---

## Phase 1 — v0.9 Beta

Goal: a closed beta of 20–30 people who can report problems. Order below is the
dependency order; follow it.

### T-04 · E16-F01 — Installer config parity                    [P0]

```
Blocked by  nothing (T-02 is done)
Touches     app/src-tauri/tauri.conf.json, .github/workflows/windows.yml
Proves it   a local `npx tauri build` produces the same artifacts CI does
```

`bundle.targets` is `["dmg"]` while CI passes `--bundles nsis`. Make the config
carry both and drop the CI flag, so local and CI builds stop diverging.

### T-05 · E1-F04 — Pin model checksums                         [P0]

```
Blocked by  nothing (T-02 is done)
Touches     pipeline/publikclip_pipeline/models/specs.py, models/registry.py
Proves it   test_house_rules.py::test_model_specs_pin_a_sha256 baseline drops 5 → 0
Watch out   the PANNs note in SPECIFICATION.md §11 — the ~312 MB file is the correct
            one; the 514 MB response is the corrupt one, not the other way round
```

Download each weight once, checksum it, pin it. Five of six specs are currently
unverified against exactly the truncation failure the sixth was pinned for.

### T-06 · T10-A — Encoding sweep                             [DONE 2026-08-26]

```
Blocked by  nothing (T-02 is done)
Touches     39 call sites across 14 files (not vendor/). Heaviest:
            render_clip.py (10), scoring/llm.py (5), cli.py (4),
            candidates/stage.py (3), render/stage.py (3)
Do not      touch vendor/
Proves it   test_encoding_baseline_is_not_stale — the `==` half. The `<=` test
            is green before, during and after the sweep and proves nothing
Watch out   Three things, all found while planning this task, none of them
            mechanical:
            1. Five of the 39 are multi-line calls whose opening line reads
               `…write_text(`. The detector is per-line, so putting encoding=
               on a continuation line leaves the violation counted. Do not touch
               the regex. Two of the five cannot collapse to one line at all
               (captions/ass.py:402 is an implicitly-concatenated string literal;
               camera/stage.py:135 is a multi-line json.dumps). The technique is
               HOIST THE PAYLOAD TO A LOCAL, then call on a single short line:
                   payload = json.dumps({...})
                   path.write_text(payload, encoding="utf-8")
               This keeps lines under 100 chars. ruff.toml sets line-length = 100
               but does not select "E", so E501 is inert today and would report
               ~211 violations if enabled — do not add to that pile.
            2. Adding encoding= to a READ is a behaviour change on Windows: a
               file written by an older build under cp1252 currently decodes as
               mojibake and afterwards raises UnicodeDecodeError. edits/store.py
               catches (JSONDecodeError, OSError); UnicodeDecodeError is neither,
               so a clip_edits.json with a smart quote goes from silently-wrong
               to a hard crash. Widen that except.
            3. captions/ass.py:402 and render/renderer.py:275 are the two sites
               most likely to hold non-ASCII today (subtitles, sendcmd). Treat
               them as the highest-value fixes in the task.
```

Mechanical, low-risk, and it removes a whole class of silent corruption. Good first
real task for a new agent.

### T-07 · E2-F07 — Job cancellation                            [P0]

```
Blocked by  nothing (T-02 is done)
Touches     app/src-tauri/src/main.rs (new cancel_job command), app/src/api.ts,
            app/src/components/Studio.tsx, pipeline/publikclip_pipeline/jobs/queue.py
            (a 'cancelled' status)
Proves it   a new tests/test_cancel.py: checkpoints survive, partial outputs do not
Watch out   cancellation must NOT delete checkpoints — resume from the last completed
            stage has to keep working (CLAUDE.md §4)
```

There is no way to stop a started job. The processing screen shows a Cancel button
with nothing behind it.

### T-08 · E2-F04 — Job queue                                   [P0]

```
Blocked by  T-07
Touches     app/src-tauri/src/main.rs (the runner), app/src/api.ts,
            app/src/App.tsx, app/src/components/ (a Queue view),
            pipeline/publikclip_pipeline/jobs/queue.py
Proves it   tests/test_queue_persistence.py: queue survives a restart; one failure
            does not stop the rest
Watch out   the data model already exists — jobs.status is pending|running|done|failed
            and create_job() writes 'pending'. Do not invent a second one
```

One job at a time; the GPU is a single resource. Parallelism is not in scope.

### T-09 · E1-F02 — Onboarding: the gate that leads through     [P0]

```
Blocked by  nothing (T-02 is done)
Touches     app/src/components/Onboarding.tsx, app/src/api.ts,
            app/src-tauri/src/main.rs (Ollama install/pull helpers)
Do not      remove the `disabled` condition on line 118 — the gate is deliberate
            (PRD §4.2, D-15). Do not add an llm_mode="none"
Proves it   manual: with Ollama absent, the screen offers a real path forward
```

The gate stays. What changes is that the Ollama card stops saying "Not detected" and
starts helping: platform download link, recommended model, `ollama pull` with
progress, and a status that refreshes when the user installs it in another window.

This is the only free way into the product. Treat it accordingly.

### T-10 · E1-F03 + E13-F01 — Hardware profile                  [P0]

```
Blocked by  T-09
Touches     pipeline/publikclip_pipeline/hardware.py (a persisted profile),
            app/src/components/Onboarding.tsx, app/src/components/Studio.tsx
Proves it   tests/test_performance.py additions: measured ratio persists and is used
Watch out   hardware.summary() already exists — surface it, do not rewrite it
```

Show the GPU, and an honest "60 min video ≈ N min" from a measured realtime ratio that
updates after each job.

### T-11 · E1-F01 — Setup flow                                  [P0]

```
Blocked by  T-10
Touches     app/src-tauri/src/main.rs (bootstrap progress events),
            app/src/components/Onboarding.tsx
Proves it   manual: killing the app mid-setup resumes at the last completed step
```

### T-12 · E1-F07 — Disk space check                            [P0]

```
Blocked by  T-10
Touches     pipeline/publikclip_pipeline/jobs/queue.py, app/src/components/Studio.tsx
Proves it   a unit test on the estimate; blocked start when free space is short
```

### T-13 · E14-F01 — Error catalogue                            [P0]

```
Blocked by  T-08
Touches     a new pipeline/publikclip_pipeline/errors.py, every stage's raise sites,
            app/src/components/ (an ErrorPanel)
Proves it   tests/test_error_catalog.py: every known class has a cause and an action
Watch out   SPECIFICATION.md §20 is the starting list — cover all of it
```

No error may surface as a Python traceback. Cause in human language, at least one
action, traceback behind a disclosure.

### T-14 · E14-F02 — Resume from stage                          [P0]

```
Blocked by  T-13
Touches     pipeline/publikclip_pipeline/jobs/queue.py, app/src (the library row)
Proves it   tests/test_queue.py additions
Watch out   resuming must respect the invalidation cascade (CLAUDE.md §4 rule 2)
```

### T-15 · E14-F03 — Diagnostic bundle                          [P0]

```
Blocked by  T-13
Touches     pipeline/publikclip_pipeline/cli.py (a `diagnose` subcommand), app/src
Proves it   a test asserting keys, paths and source names are stripped
Watch out   never include API keys, file paths or media
```

### T-16 · E15-F01 — Auto-update                                [P0]

```
Blocked by  T-04
Touches     app/src-tauri/tauri.conf.json, Cargo.toml, .github/workflows/
Proves it   an update run that preserves jobs, settings and presets
```

### T-17 · E15-F03 — Privacy notice                             [P0]

```
Blocked by  nothing
Touches     PRIVACY.md (new), app/src/components/ (Settings → Privacy)
Proves it   review: every network call in the code appears in the document
```

Name every network call the app makes. Auditable claim, not marketing.

### T-18 · E16-F03 — AGPL in the UI                             [P0]

```
Blocked by  nothing
Touches     app/src/components/ (an About screen), app/scripts/prepare-resources.mjs
Proves it   the About screen shows the licence, the source link, and the exact version
Watch out   each release must publish a source archive for that version, not just main
```

### T-19 · E16-F04 — macOS CI                                   [P0]

```
Blocked by  T-04
Touches     .github/workflows/macos.yml (new)
Proves it   the workflow goes green on Apple Silicon
```

macOS is the only bundle target and the only platform with no CI. Mirror
`windows.yml`: sync, ffmpeg, full suite, build the `.dmg`, mount, launch, check alive.

### T-20 · E1-F06 — ETA and stage names                         [P1]

```
Blocked by  T-10
Touches     pipeline stages (progress events), app/src/App.tsx,
            app/src/components/Studio.tsx
Watch out   structured progress ALREADY EXISTS — {event:'progress', stage, fraction,
            message}, consumed by App.tsx. Do not rebuild the protocol. Add the ETA,
            the human-readable stage names in one place, and measured stage weights
```

**Phase 1 exit:** 20 beta users complete a job; crashes < 5 %; zero data-loss
incidents; `guards.yml` green on every PR.

---

## Phase 2 — v1.0, then v1.1

Full requirement lists live in `PRODUCT-REQUIREMENTS.md` §34.3 and §34.4. Ordering
constraints that are not obvious from the PRD:

**Before v1.0 work starts:**
- T-03 (split `ClipEditor.tsx`) must be merged, or E6 is unreviewable.
- `E12-F01` (settings levels) changes `settings_schema.py`'s shape — do it before
  anything that adds a setting, or every later task collides there.

**Before v1.1 work starts:**
- Split `insights/calibration.py` (908 lines). It is about to carry two more
  platforms plus the packaging attribution.
- **Run the R16 check first.** Take 30 already-published clips, record their
  Publikclip score and their real retention, compute the correlation. If it is near
  zero, the v1.1 premise is wrong and ten weeks of calibration work should not start.
  This is a spreadsheet, not a task.

**E17 (packaging experiments) ordering:** `E17-F01` (packaging as a unit) blocks
everything else in the epic. `E17-F04` (attribution) needs `E10-F03` (publishing)
and `E11-F02` (metrics) merged first — it has nothing to attribute otherwise.

---

## File hotspots

Files that several tasks want. In sequential mode these are not merge risks, but they
are *review* risks: two tasks in the same file in a row means the second agent is
reading code the first just wrote.

| File | Lines | Wanted by | Note |
|---|---|---|---|
| `app/src-tauri/src/main.rs` | 544 | T-07, T-08, T-09, T-16 | 17 commands, flat handler; grows with every task |
| `app/src/components/ClipEditor.tsx` | 1175 | T-03, then all of E6 | Split first (T-03) |
| `app/src/api.ts` | 65 | T-07, T-08, T-09 | Every new command lands here |
| `pipeline/.../jobs/queue.py` | 355 | T-07, T-08, T-12, T-14 | The checkpoint contract lives here — read `CLAUDE.md` §4 |
| `pipeline/.../insights/calibration.py` | 908 | all of E11 | Split before v1.1 |
| `pipeline/.../settings_schema.py` | 487 | E12-F01, then anything adding a setting | Do E12-F01 first |
| `app/src/components/Onboarding.tsx` | 122 | T-09, T-10, T-11 | Three tasks in a row; keep them in that order |

---

## Off limits

| Path | Why |
|---|---|
| `pipeline/publikclip_pipeline/vendor/` | Upstream copies, two of them AGPL. Edit only when unavoidable and record it in `VENDORED-LICENSES.md` in the same commit |
| `graphify-out/` | Generated, gitignored |
| `app/src-tauri/gen/` | Generated by Tauri |
| `pipeline/uv.lock`, `app/package-lock.json` | Only via the tool that owns them, never by hand |

---

## The scope list

Do not build these, and do not add scaffolding for them. Full reasoning in
`PRODUCT-REQUIREMENTS.md` §2.5:

a general multi-track editor · recording · cloud rendering · mandatory accounts ·
AI avatars or voice cloning · a mobile app · paid tiers or licence keys ·
a degraded "no AI" mode · automatic recalibration without user approval ·
money tracking (RPM, brand deals) — the product measures retention, not euros

If a requirement seems to need one of these, stop and say so in the PR.
