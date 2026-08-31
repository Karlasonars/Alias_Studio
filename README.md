# Alias Studio

**Long video in. Scored vertical clips out. Everything runs on your machine.**

Alias Studio is a modified build of
[publikclip](https://github.com/Blueturboguy07/publikclip), an open-source
(AGPL-3.0) desktop app that turns a YouTube URL or a horizontal video file into
vertical 9:16 clips. This fork keeps the original pipeline and adds control
over it: the framing, the copy, the pacing and the scoring are all tunable
rather than baked in.

Like the original, it is AGPL-3.0 — see [License](#license).

## What this build adds

Everything below is on top of the base project.

- **Podcast ↔ gameplay framing** — the original always cropped tight onto the
  tracked face, which on gameplay footage produced clips containing only the
  facecam and none of the game. A single dial interpolates from that tight crop
  to the full source frame, letterboxed. Set it per job or per clip.
- **A real settings panel** — 78 parameters that were previously module
  constants: clip lengths, interest-curve channel weights, platform scoring
  weights, punch-in shape and frequency, dead-space thresholds, and the caption
  presets, which are now editable data rather than frozen code. Grouped by what
  changing them costs (re-render / re-direct / rescore).
- **Per-clip fine-tuning** — dead space, subtitle size/colour/position and
  loudness are editable inside the clip editor, where the result is visible,
  and apply to that clip alone.
- **Copywriting** — title variants, a post description with hashtags, and a
  hook pass that ranks alternative openings against the current one. Every
  constraint you set is enforced on the model's answer, not just requested in
  the prompt.
- **GPU acceleration** — models ran on the CPU regardless of hardware. Now
  detected and used, with CPU fallback that never fails a job.
- **Faster scene detection** — the frame-by-frame Python pass is replaced by an
  ffmpeg equivalent.
- **A live console** — every pipeline event as it happens. The shell used to
  discard the sidecar's stderr, so a crash surfaced as "the pipeline exited
  unexpectedly" with the traceback thrown away.
- **Windows reliability** — six separate faults that each killed a real run:
  ffmpeg resolution in two places, a speechbrain import guard that never
  matched on Windows, silent truncation of a model download, an inconsistent
  checkpoint URL, an LLM retry loop that didn't back off, and checkpoint writes
  using the OS locale encoding instead of UTF-8.

On an 81-minute source with an RTX 3050 Ti, the two largest stages measured
49.9 → ~4.7 minutes (transcription) and 54.7 minutes → the fast path (scene
detection).

## What it does (from the base project)

- **Smart camera** — active-speaker-tracked crop paths, smoothed motion, hard
  cuts on speaker change, punch-ins fired by actual laughter and vocal energy
- **Word-accurate captions** — multiple styles, karaoke highlighting, prosodic
  emphasis (loud words get loud styling), `[laughs]` tags from real laughter
  detection
- **A virality score you can audit** — never a bare number: every clip ships
  with its subscores, which detectors fired, and every adjustment applied. LLM
  humor scores get discounted when no actual laughter corroborates them.
- **Music-type suggestions** — an editable genre/mood/energy brief derived from
  what's being said and how it sounds
- **Optional real-outcomes loop** — connect your own Instagram (via your own
  Meta app, no middleman) and the scorer calibrates against how your clips
  actually perform

Every model — speech recognition, forced alignment, diarization, laughter
detection, audio tagging, face detection, active-speaker detection — runs
locally. Your video is never uploaded; scoring sends transcript excerpts and
a few still frames to Gemini (bring your own key), or stays fully local via
Ollama at reduced scoring quality. [PRIVACY.md](PRIVACY.md) names every
network call the app can make.

## Status

**No release yet. Nothing here is packaged for general use.**

The repository is public because the project is AGPL-3.0 and because CI and
branch protection need it to be — not because it is finished. There are no
installers, no support, and no answer time on issues. If you install this
today, you are installing from source and you are on your own.

Working end to end: hour-long source in, rendered/captioned/scored 9:16 clips
out, validated on real footage including gameplay. Builds are unsigned —
install from source below.

Where the project is going, and why:
[`PRODUCT-REQUIREMENTS.md`](PRODUCT-REQUIREMENTS.md) (Latvian) for the product
decisions, [`AGENT-WORKPLAN.md`](AGENT-WORKPLAN.md) for what is being built in
what order, [`SPECIFICATION.md`](SPECIFICATION.md) for how the built thing
works today.

Developed and validated on Windows 11 x64. The macOS path is inherited from the
base project and is not currently exercised here; GPU acceleration is
NVIDIA-only, and everything falls back to the CPU without it.

## Layout

```
pipeline/   Python package — the entire processing pipeline + CLI
app/        Tauri v2 desktop shell (React UI, Python sidecar)
```

## Installing a release build (Windows)

Release installers are on the
[releases page](https://github.com/Karlasonars/Alias_Studio/releases), built
by CI from the tagged source that sits beside them.

**Expect a Windows SmartScreen warning — it is normal for this app.** The
installer is not Authenticode-signed (a paid certificate this free beta
deliberately skips), so Windows shows "Windows protected your PC". Click
**More info → Run anyway**. You will see it once per downloaded installer.
If you want to verify what you downloaded first, each release lists its
source and CI run.

The lack of a Windows certificate does not mean updates are unverified:
the app's built-in updater checks every update against its own signing key
and refuses anything unsigned or tampered with. Update checks run at launch
and can be switched off in Settings → About ([PRIVACY.md](PRIVACY.md) has
the details).

## Install from source (Windows)

You need [Rust](https://rustup.rs), the Visual Studio **Desktop development
with C++** build tools, [Node](https://nodejs.org), git, and
[uv](https://docs.astral.sh/uv/) (`winget install --id astral-sh.uv -e`).
Then, in PowerShell:

```powershell
git clone https://github.com/Karlasonars/Alias_Studio.git
cd Alias_Studio\app
npm.cmd install
node_modules\.bin\tauri.cmd build --bundles nsis
# run the installer it produces:
Start-Process (Get-ChildItem src-tauri\target\release\bundle\nsis -Filter *-setup.exe).FullName
```

On first run the app downloads its Python environment (~3.9 GB on Windows —
PyTorch's CUDA build is most of it, and it lands on machines without an
NVIDIA GPU too) and then its speech/audio models (~2.4 GB), about **6.3 GB
in total**, behind a progress bar; a caption-capable static ffmpeg is
fetched automatically if the machine has none. Scoring uses your own Gemini API key, or a local Ollama model
at reduced quality — onboarding walks through both.

On a machine with an NVIDIA GPU, `uv sync` installs the CUDA build of PyTorch
automatically (see `pipeline/pyproject.toml`). Without one, the CPU build is
used and nothing else changes.

## Development

```sh
# pipeline
cd pipeline && uv sync && uv run pytest
uv run publikclip run "https://www.youtube.com/watch?v=..."

# app
cd app && npm install && npm run tauri dev
```

`PUBLIKCLIP_DEVICE=cpu` forces every model back onto the CPU — the first thing
to try when diagnosing a suspected GPU problem.

On an installed build the variable must reach the app's process: **close the
app first**, set the variable in a terminal, then launch the exe from that
same terminal — e.g. in PowerShell,
`$env:PUBLIKCLIP_DEVICE = 'cpu'; & "$env:LOCALAPPDATA\Alias Studio\Alias Studio.exe"`
(right-click the app's shortcut → Open file location if it installed
elsewhere; setting the variable while the app is already running does
nothing). The studio's
hardware line confirms it took effect: it reads
`forced CPU (PUBLIKCLIP_DEVICE)` instead of naming your GPU.

[SPECIFICATION.md](SPECIFICATION.md) is the engineering reference: the eight
stages and what each one produces, the checkpoint contract that decides what
re-runs, the settings model, the two render paths and how they are kept in
agreement, and the conventions that exist because breaking them caused a real
failure. Read it before changing pipeline behaviour.

## License

AGPL-3.0-or-later, inherited from
[publikclip](https://github.com/Blueturboguy07/publikclip). This is a modified
version: the changes are summarised under
[What this build adds](#what-this-build-adds) and recorded in the commit
history.

Portions adapted from other open-source projects — see `VENDORED-LICENSES.md`
for the full provenance list.
