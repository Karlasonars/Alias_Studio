# Privacy — every network call, named

Alias Studio runs on your machine. This document names **every network
call the app can make**: what is sent, when, to whom, whether it is
optional, and what happens if you say no. It is part of the repository
and versioned with the code, and a test
(`pipeline/tests/test_privacy_notice.py`) scans the codebase for
network-capable calls and fails when one is missing from this file — so
the document cannot silently fall behind the code. The app shows this
exact file under Settings → Privacy.

## What never leaves your machine

- **Your video and its audio are never uploaded — not to transcribe, not
  to score, not to render.** Transcription (Whisper), speaker and
  laughter detection, face tracking, camera direction and rendering all
  run locally.
- Your library, your jobs, the full transcript, your clip edits, your
  settings and your rendered clips live on disk under your home
  directory and go nowhere.
- There is no telemetry, no analytics, no crash reporting, and no
  account. The one background call is the launch update check — a single
  request to github.com for the latest release, described below, and you
  can switch it off.

One deliberate exception exists, and you control it: in Gemini mode,
short transcript excerpts and a few still frames are sent to Google to
score your moments — detailed next. **On Google's free tier, Google may
use free-tier prompts to improve its products — meaning the excerpts and
frames you send can be used by Google beyond answering the request.**
Ollama mode removes that path entirely: nothing about your content
leaves the machine.

## Scoring and writing — Gemini, or Ollama which sends nothing

### Gemini mode (generativelanguage.googleapis.com)

The default mode, using an API key you bring. What is sent, and when:

- **Scoring a job**: for each candidate moment, the transcript excerpt
  of that window plus its duration and a short description of detected
  events (laughs, audio events). For the few finalist clips only: a
  handful of JPEG still frames sampled from the clip (the visual pass),
  and the clip's summary and transcript excerpt for a music brief.
- **Titles, descriptions, hooks** (when you ask for them in the editor):
  that clip's transcript excerpt, its summary, and your own keyword
  settings.
- **Overlay suggestions** (when you ask): the clip's transcript words;
  generating an image sends the short image prompt derived from them.
- **When you save a key**: one models-list call that carries only the
  key, to check it works.

The key always travels in a request header, never in the URL. Responses
are cached on disk locally, so a re-run does not re-send what was
already answered. Nothing is sent at idle — only while a job is scoring
or when you press an editor button that asks for copy or overlays.

**The free-tier sentence, again, because it matters most: Google states
that free-tier prompts may be used to improve its products.** The paid
tier is governed by Google's paid terms, which exclude that use.

Optional: yes. If you refuse — switch `llm_mode` to Ollama. Every
feature still works; scoring uses your local model, the visual pass is
skipped, and scores are honestly marked as local estimates.

### Ollama mode (localhost:11434)

The same prompts go to an Ollama model running **on your machine** —
`localhost` only, nothing leaves it. No frames are sent (the visual pass
needs Gemini). The app also probes localhost to see whether Ollama is
running and which models it has. Getting Ollama is a link the app opens
in your browser (ollama.com); the app itself downloads nothing for it.

## Stock photos — Pexels (api.pexels.com), only with your key

Only if you add a Pexels API key, and only at the moment overlay images
are fetched: the app sends a short search query — a few words derived
from the clip's transcript, like "possum close up" — with your key in a
header, and downloads the chosen photo from Pexels' image host. If you
never add a key, Pexels is never contacted; overlay images fall back to
Gemini image generation, or to nothing.

## Instagram (www.instagram.com, api.instagram.com, graph.instagram.com), only when connected

Nothing Instagram-related happens unless you explicitly connect an
account. When you do: sign-in runs in your own browser
(www.instagram.com); the app briefly listens on localhost to catch the
redirect, then exchanges the code — sending your Meta app id and secret
— for a token (api.instagram.com), which it refreshes periodically.
After that it **reads**: your account's recent media list and per-Reel
insights (graph.instagram.com), and downloads Reel cover thumbnails from
Instagram's image CDN. **It never posts, never uploads, and cannot** —
publishing is not built. If you never connect, none of these hosts are
ever contacted, and everything else works.

## Video URLs — yt-dlp, only when the source is a link

A job whose source is a file touches no network at all. A job whose
source is a URL:

- downloads the official yt-dlp binary (~30 MB) from github.com on first
  use, and on a failure lets it self-update once against the same host;
- yt-dlp then contacts the site your URL points to and fetches the
  video anonymously — no account, no cookies. Like any browser visit,
  that site sees your IP address and which video was requested.

## Model weights — first run, ~2.4 GB, plain downloads

The AI models download once, on first run (or up front via the setup
screen). These are anonymous file downloads — no account, no token, and
nothing of yours is sent:

- **huggingface.co** — Whisper large-v3-turbo (1.62 GB) and the CAM++
  speaker model (28 MB). If a video turns out not to be English, its
  alignment model also comes from here, when first needed.
- **download.pytorch.org** — the English alignment model (378 MB).
- **github.com** — the silero-vad voice model (~35 MB), face and
  active-speaker models (~5 MB), and the laughter model (~10 MB, fetched
  only if you switch the laughter specialist on).
- **zenodo.org** — the PANNs audio-event model (327 MB).

If the machine is offline, jobs that need a missing model fail with a
clear message and nothing is retried behind your back. Transcription and
scoring cannot run without these; there is no bundled offline installer
today.

## ffmpeg — only when your system's cannot burn subtitles

If no ffmpeg on the machine supports subtitles, the app fetches a static
build once: on Windows from github.com (~80 MB), on macOS from
ffmpeg.martin-riedl.de. If a capable ffmpeg is already installed,
nothing is downloaded.

## The Python environment — packaged app, first launch

The installed app bootstraps its Python environment with the bundled
`uv` tool on first launch: Python 3.12 and the pipeline's dependencies
download from pypi.org and files.pythonhosted.org, and on Windows the
CUDA build of PyTorch from download.pytorch.org. Several gigabytes,
once. These are package downloads; nothing of yours is sent.

## The update check — github.com, once at launch, switchable off

When the app starts it asks github.com for the latest release
description (a small JSON file on the releases page) and compares
versions. Nothing about you or your work is sent — the request is a
plain download, the same as fetching any release page; GitHub sees your
IP address, as any visited site does. If an update exists, the app shows
what changed and installs **only when you press install** — and it
refuses while a job is running. Updates are verified against a signing
key baked into the app; an unsigned or tampered update is rejected.

Optional: yes — Settings → About has the switch ("check at launch"),
and the check also runs when you press "Check for updates" there. If you
switch it off: the app makes no background network call at all; you
check manually, or watch the releases page yourself. Refusing costs you
nothing but hearing about fixes later.

An update never touches your jobs, settings, presets, models or keys —
they live in the app's data folder, outside the install directory.

## Links that open in your browser

Some buttons open a page in your default browser — get a Gemini key
(aistudio.google.com), get Ollama (ollama.com), this project's source
and error documentation (github.com), a linked Reel's permalink
(instagram.com). The app hands the URL to the browser and sends nothing
itself.

## Not in the app today

- **Crash reporting / telemetry** (deliberately absent): a failure
  produces a local, redacted diagnostic zip that only you can choose to
  send, and the app has no way to send it for you.
