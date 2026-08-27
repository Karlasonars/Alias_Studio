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

### T-03 · Split `ClipEditor.tsx`                          [DONE 2026-08-27]

```
Merged      three commits: wiring, the pure move, one disclosed change
Proves it   tsc clean at each commit; a whitespace-normalized line-multiset diff of
            the monolith against the nine files; INVOKE_OUTSIDE_API_BASELINE 12 → 6
```

1175 lines became nine files under `app/src/components/ClipEditor/`, largest
`Controls.tsx` at 293. The move commit carries no semantic edits because the wiring
landed first and the one behaviour-adjacent change sits alone at the end — so the
move could be reviewed as a move.

**The "suggested shape" this entry used to carry — `Timeline` / `PreviewPane` /
`ControlsPanel` — was written without reading the component, and was wrong.** The
state does not run along visual seams: `selectedOverlay` alone is read by three
children across two of the proposed regions. The agent read the file first and split
by state ownership instead. Recorded because the guess cost nothing *only* because
someone checked it before executing it.

**The landmines survived the split and are still live**, now spread across nine files
instead of hidden in one. They are documented in `CLAUDE.md` §6; the two that bite
hardest are `useClipEdit.ts` assigning `editRef`/`ctxRef` during render, and
`usePlayer.ts`'s rAF dependency array being `[win, span]` on purpose. The `timeLabel`
state became a rAF-written ref, so the ~10 Hz whole-tree re-render is gone and React
no longer owns that node's content. The §6 persist asymmetry moved byte-for-byte and
is still unresolved.

**The manual checklist has never been run.** It needs an existing job's artifacts,
which only a real pipeline run produces, and §3 forbids that. Whoever first has a
machine with a completed job should run it before E6 starts:

open the editor · drag both bounds · scrub · play through a dead-space cut · drag an
overlay on the timeline and on the monitor (the monitor drag must persist on release,
the timeline drags must not) · change a caption preset · render · **type in the
description textarea during playback** — titles are chosen by buttons, so the textarea
is the only free-typing surface and that is where landmine 1 lives · **move a bound,
then play without persisting** — the out-point must honour the un-persisted bound.

`Monitor` and `Timeline` still take ~11 props each, deliberately: the price of
byte-for-byte inline handlers. That is the next refactor, once behaviour is proven —
not a defect to fold into an E6 task.

---

## Phase 1 — v0.9 Beta

Goal: a closed beta of 20–30 people who can report problems. Order below is the
dependency order; follow it.

### T-04 · E16-F01 — Installer config parity              [DONE 2026-08-27]

```
Merged      76d42da  build: make tauri.conf.json the single source of installer targets
Proves it   windows.yml's own `throw "no NSIS installer produced"` — green before the
            change only because of the CLI flag, green after only because of the config
```

`bundle.targets` was `["dmg"]` while CI passed `--bundles nsis`, so a bare
`npx tauri build` on Windows produced nothing — while `CLAUDE.md` §3 tells you to
build exactly that way. Config now carries both targets; the flag is gone.

Verified rather than assumed, and this is why the task was worth doing carefully:
`Settings::package_types()` intersects configured targets with a per-platform
allowlist and **silently drops** what the host cannot build — no warning, no error.
Windows gets `[Nsis]`, native macOS gets `[Dmg]`. Had it errored instead, adding
`nsis` would have broken every macOS build and set a trap for T-19. Do not look for
an "ignoring dmg" line in build logs as evidence; dmg is filtered a call earlier,
silently. The evidence is the exit code and the artifact.

### T-05 · E1-F04 — Pin model checksums                   [DONE 2026-08-27]

```
Merged      d475218  models: pin the five unpinned weights against publisher hashes
Proves it   UNPINNED_MODELS_BASELINE 5 → 0. At zero the two-sided pin stops being a
            ratchet and becomes a plain rule: a new ModelSpec without a sha256 fails
```

All six weights are now pinned. **The trap this task existed to avoid:** hashing your
own download pins whatever you received, corruption included — it then rejects every
future *good* download and accepts the bad one forever. Every pin here was checked
against an identity the publisher records, before anything was pinned:

- `campplus` — Hugging Face stores it in LFS, where the object id **is** its sha256.
  The pinned value is literally the publisher's own hash.
- the four `raw.githubusercontent.com` weights — GitHub publishes no sha256, but it
  publishes the git blob SHA-1, which is recomputable from bytes you hold
  (`sha1(b"blob %d\0" + content)`). Identity checked against that first, sha256
  computed only from bytes that matched.

Same check answered the LFS question for free: an LFS pointer's blob hash covers
~130 bytes of pointer text and could never equal a blob hash recomputed over a
multi-MB binary. All four matched over the binaries, so none is LFS.

**Two findings left deliberately unfixed:**

- `registry.ensure()` returns the moment the file exists, before any hash runs. These
  pins protect future downloads only; a user already holding a corrupt weight keeps
  loading it. `E1-F04`'s own acceptance criteria ask for detect-and-redownload, so
  that belongs with the model-manager work, not here.
- **`specs.py` and `registry.py` contradicted each other about the PANNs failure, and
  `specs.py` is right.** Zenodo's record API reports `size: 327428481` (~312 MB) for
  the complete file, so the ~490 MB response was the corrupt one.
  `registry.py`'s comment — "a 466 MB PANNs checkpoint silently landing at 312 MB" —
  inverts the failure and will mislead the next person into fixing the pin backwards.
  Neither comment was edited; fixing that comment is a one-line task nobody has filed.

One limit worth not over-reading: this chain proves the bytes are the object the
publisher records. It does not prove they are benign. A compromised upstream repo
would be pinned faithfully.

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

### T-26 · E16-F01 follow-on — the rebrand left `windows.yml` behind  [DONE 2026-08-27]

```
Merged      a83786a  ci: derive the install directory from tauri.conf.json
Proves it   the windows job green through install-and-launch for the first time
            since e090989 — red on main, green on the branch
```

`windows.yml` hardcoded `$LOCALAPPDATA\publikclip`, a copy of the then-current
`productName`. `e090989` renamed the product in 16 files and did not touch the
workflow. **The job was red on every pull request for 37 commits across 9 merged
PRs** and nobody noticed, because the ruleset required only `guards`.

Verified from the pinned bundler (`@tauri-apps/cli-v2.11.4`): the NSIS install path
is `$LOCALAPPDATA\${PRODUCTNAME}` — **productName**, not `mainBinaryName`, not the
identifier. Install mode defaults to `currentUser` because we configure no `nsis`
block; if it ever becomes `perMachine` the base becomes `$PROGRAMFILES64` and this
derivation must follow. The workflow now reads `productName` from `tauri.conf.json`,
so no second copy of the name exists there to go stale again.

This task and T-27 are the same defect twice: **a copy of a name, in a place nobody
re-reads.** That is the shape to watch for, not the specific file.

### T-27 · E16-F02 — Rebrand to "Alias Studio"            [DONE 2026-08-27]

```
Merged      f500ff6  display only (20 files, 39 replacements)
            b45d32c  identity: productName, identifier, Cargo and npm package names
Proves it   commit 2's windows run green with windows.yml's install step untouched —
            the T-26 derivation followed productName rather than coinciding with it
```

Split into display and identity because **`productName` is an identity value, not a
display one**: NSIS derives the install directory *and* the uninstall registry key
from it, so renaming it means no upgrade continuity and an orphaned old install.
Free today, expensive the day v0.9 ships.

Two judgement calls worth keeping:

- `insights/instagram.py:113` looked like a display string and is one — it is the
  HTML body the local `127.0.0.1` callback server shows the user's own browser. Meta
  receives the redirect, never this response. **A display string that is also a wire
  value would not have been bucket A**, which is why it was checked rather than swept.
- `prepare-resources.mjs:4` was listed as a cosmetic comment and was **left alone**:
  the word sits inside the literal packaged-build spawn command, making it a console-
  script contract. The agent overrode its own inventory. That is the inventory doing
  its job, not failing.

Attribution to the upstream project (`Studio.tsx`, `README`, `SPECIFICATION`, the
PRD, `VENDORED-LICENSES`) was kept verbatim — renaming it would falsify AGPL
attribution. Historical references ("the rename to Publikclip Extra") were kept for
the same reason: they describe what happened.

**Bucket C is untouched and is a task nobody has filed yet:** the
`publikclip_pipeline` package, the `publikclip` console script and its `main.rs`
spawn contract, `PUBLIKCLIP_HOME`/`_FFMPEG`/`_BUNDLED_FFMPEG`/`_DEVICE`/
`_GEMINI_API_KEY`, `~/.publikclip` and the assetProtocol scope, the
`publikclip-theme` localStorage key. Each has stored state or a cross-process
contract behind it and needs a migration step. 179 lines in 44 files still say
`publikclip`; every one is bucket C, attribution, or history.

`PUBLIKCLIP_BUNDLED_FFMPEG` surfaced along the way: **read at `ffmpeg_bin.py:73`
and set nowhere in the tree.** Harmless under §5.9, but if the app shell was meant to
set it, every installed user re-downloads an ffmpeg that is already on their disk.
Unfiled.

### T-28 · E16-F02 follow-on — the identifier                [DONE 2026-08-27]

```
Merged      ee111c9  identifier → com.alias.studio
Proves it   the windows job green AND invisible — install log byte-identical to
            T-27's apart from the pid, confirming nothing in that job reads it
```

T-27 shipped `com.publikhq.aliasstudio` from a superseded task version. The
correction was one line — but the agent **stopped before committing**, because
`build.rs:181-186` warns on any identifier ending in `.app` and the owner's chosen
value did. A warning, not an error: CI would have stayed green and printed it in
every build log forever, and on macOS the per-app data directory would have been a
folder named `com.aliasstudio.app` that Finder treats as an application bundle.

Owner chose `com.alias.studio`, which drops the segment rather than working around
it. **The gate is the lesson: a task that says "stop on a warning" is worth more
than one that says "use this value", because the second one ships the warning.**

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
- T-03 (split `ClipEditor.tsx`) is merged. Its manual checklist has still never
  been run — see the entry. Run it before the first E6 task, not after.
- `E12-F01` (settings levels) changes `settings_schema.py`'s shape — do it before
  anything that adds a setting, or every later task collides there.

**Before v1.1 work starts:**
- Split `insights/calibration.py` (908 lines). It is about to carry two more
  platforms plus the packaging attribution.
- **Run the R16 check first.** Take 30 already-published clips, record their
  Alias Studio score and their real retention, compute the correlation. If it is near
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
| `app/src/components/ClipEditor/` | 1151 in 9 files | all of E6 | Split by state ownership (T-03). Add along those seams |
| `app/src/api.ts` | 81 | T-07, T-08, T-09 | Every new command lands here. 6 stray `invoke()` remain, 4 of them duplicating a wrapper that exists |
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
