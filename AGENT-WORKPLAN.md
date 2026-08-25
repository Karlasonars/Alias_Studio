# AGENT-WORKPLAN.md — what to build, in what order

The execution order behind `PRODUCT-REQUIREMENTS.md`. That document says *what and
why*; this one says *next, and which files*.

**Mode: one agent at a time, sequentially.** Each task is one requirement ID, one
branch, one PR. Do not start a task whose blockers are unmerged.

**Before every task:** read `CLAUDE.md`, then the section of `SPECIFICATION.md` that
covers the stage you are touching, then the requirement in
`PRODUCT-REQUIREMENTS.md`. Do not read the whole PRD — it is 78 pages and most of it
is not your task.

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
widening it silently.

---

## Phase 0 — hygiene, before any feature work

These are unblocked, take hours not days, and every later task is easier because of
them. Do them in this order.

### T-01 · E16-F07 — Line endings                              [P0, immediate]

```
Blocked by  nothing
Touches     .gitattributes (new), then a renormalise commit across the tree
Do not      change any file content in the same commit
Proves it   guards.yml "No CRLF in tracked text files"
```

`git status` currently reports 82 modified files with 26,550 added and 26,550 deleted
lines, none of them real. Until this is fixed every diff you produce is unreadable,
which means nobody can review your work.

Two commits, in this order:

```bash
git add .gitattributes && git commit -m "repo: add .gitattributes"
git add --renormalize . && git commit -m "repo: normalise line endings"
```

The second commit touches ~82 files and must contain **nothing else**. This is the one
time a mass-rewrite commit is correct; §9 of `CLAUDE.md` forbids it every other time.

### T-02 · Guard tests and lint                                 [P0, immediate]

```
Blocked by  T-01
Touches     pipeline/tests/test_house_rules.py, pipeline/ruff.toml,
            .github/workflows/guards.yml, .github/workflows/windows.yml
Do not      touch any production source to make the guards pass
Proves it   guards.yml goes green on a pull request
```

Add `pull_request:` to `windows.yml`'s triggers — it currently runs only on push to
`main`/`win-port`, so an agent's work is verified only *after* it is merged.

Fix whatever `ruff check` reports **in a separate commit** from adding the config, so
the config commit stays readable.

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

Suggested shape: `ClipEditor/index.tsx`, `Timeline.tsx`, `PreviewPane.tsx`,
`ControlsPanel.tsx`, `useClipEdit.ts`. Move the 6 stray `invoke()` calls into
`api.ts` while you are here and lower `INVOKE_OUTSIDE_API_BASELINE`.

---

## Phase 1 — v0.9 Beta

Goal: a closed beta of 20–30 people who can report problems. Order below is the
dependency order; follow it.

### T-04 · E16-F01 — Installer config parity                    [P0]

```
Blocked by  T-02
Touches     app/src-tauri/tauri.conf.json, .github/workflows/windows.yml
Proves it   a local `npx tauri build` produces the same artifacts CI does
```

`bundle.targets` is `["dmg"]` while CI passes `--bundles nsis`. Make the config
carry both and drop the CI flag, so local and CI builds stop diverging.

### T-05 · E1-F04 — Pin model checksums                         [P0]

```
Blocked by  T-02
Touches     pipeline/publikclip_pipeline/models/specs.py, models/registry.py
Proves it   test_house_rules.py::test_model_specs_pin_a_sha256 baseline drops 5 → 0
Watch out   the PANNs note in SPECIFICATION.md §11 — the ~312 MB file is the correct
            one; the 514 MB response is the corrupt one, not the other way round
```

Download each weight once, checksum it, pin it. Five of six specs are currently
unverified against exactly the truncation failure the sixth was pinned for.

### T-06 · T10-A — Encoding sweep                               [P0]

```
Blocked by  T-02
Touches     39 call sites across pipeline/publikclip_pipeline/ (not vendor/)
            heaviest: edits/render_clip.py (8), edits/store.py (2), cli.py (4)
Do not      touch vendor/
Proves it   TEXT_IO_WITHOUT_ENCODING_BASELINE drops 39 → 0
Watch out   edits/store.py is the clip editor's state file. Both Python and Rust
            write it (see E5 in the PRD) — fix the Python side here, note the Rust
            side in the PR
```

Mechanical, low-risk, and it removes a whole class of silent corruption. Good first
real task for a new agent.

### T-07 · E2-F07 — Job cancellation                            [P0]

```
Blocked by  T-02
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
Blocked by  T-02
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
