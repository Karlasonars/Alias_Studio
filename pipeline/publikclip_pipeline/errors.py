"""The error catalogue (E14-F01 / T-13).

One idea: a failure that reaches a user is a VALUE, not a string. The value
is `ErrorInfo` — a stable code, a human-language cause, at least one action,
an optional docs link, and the technical text demoted to a `detail` field
the UI keeps behind a disclosure. `describe()` is the only constructor of
that value, and it redacts every field on the way through, which is what
makes the redaction rule unskippable by future call sites.

How a failure becomes an ErrorInfo — the choke point, not 51 edited sites:
run_stages' two except arms (and the CLI's result emission) call
`describe(exc, stage)`. An exception carrying a `code` (StageError,
LlmError and YtDlpError all accept one) names its own catalogue entry; an
uncoded exception is matched by recognizers against its chain (a StageError
wrapping an LlmError inherits the inner code); anything unrecognized takes
the UNKNOWN path — which is the case this module exists for, because the
twenty-first failure is by definition the one nobody wrote a message for.

The unknown shape never guesses: a generic cause that names the stage, two
always-true actions (resume — the checkpoints are real; copy the details),
the redacted technical text in `detail`, and a `signature` (exception class
+ errno) so recurrences are legible in T-15's bundles without the UI ever
claiming a cause it does not know. "I know what this is" means a recognizer
matched a mechanism; "I know this is unusual" means unknown + signature;
there is no third state.

Tracebacks are redacted AT BIRTH: `install_excepthook()` (installed by the
CLI at import) prints every unhandled traceback through `redact()`, so the
stderr tail the Rust shell captures for its 'exited' event is clean before
Rust ever sees it — one implementation of the rule, in one language.
Residual, stated: output produced before Python starts (a broken uv env)
can still carry the venv path; nothing in-process can reach that text.

Persistence: run_stages writes the described value to <job_dir>/error.json
(redacted at write time — T-15 bundles it verbatim; T-14 reads stage+code
from it) and clears it at run start alongside the cancel flags. The
`jobs.error` DB column keeps holding the flat cause string, unchanged.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import config

DOCS = "SPECIFICATION.md#20-troubleshooting"


# ---------------------------------------------------------------------------
# Redaction. Error text is about to become a stored, structured thing that
# T-15 will zip up and users will paste into GitHub issues — so secrets and
# the user's home directory are scrubbed here, before storage, not by
# whatever later ships the text somewhere.


_SECRET_MIN_LEN = 8  # shorter values ("true", a count) are not secrets

# Belt for secrets we never held literally: Google API key shapes, and
# credential-bearing query parameters (§5.11's Instagram debt, T-32, rides
# as ?access_token=… today — hidden here at the display layer, NOT fixed).
_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{16,}"),
    re.compile(r"(access_token|client_secret|api_key|apikey|key|token)=([^&\s\"'>]+)", re.IGNORECASE),
]


def _stored_secret_values() -> list[str]:
    """Every credential this app knows about, wherever it is stored."""
    values: list[str] = []
    env_key = os.environ.get("PUBLIKCLIP_GEMINI_API_KEY")
    if env_key:
        values.append(env_key)
    for name in ("secrets.json", "instagram.json"):
        path = config.home_dir() / name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue

        def walk(node) -> None:
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            elif isinstance(node, str) and len(node) >= _SECRET_MIN_LEN:
                values.append(node)

        walk(data)
    return values


def redact(text: str, extra: "tuple[str, ...] | list[str]" = ()) -> str:
    """Strip secrets and the user's identity from text bound for a user
    surface, a stored error.json, or a pasted issue. Order matters: literal
    secrets first (they may contain pattern-breaking chars), then shape
    patterns, then path rewrites.

    `extra` is T-15's addition and the ONLY redaction knob: literal terms
    the caller knows identify the user's CONTENT (a source filename, a
    video title) rather than the user. The live UI passes none — a user
    should see their own filename on screen; the diagnostic bundler passes
    the job's known content identifiers so a bundle never names unreleased
    footage. One implementation, parameterized — never a second redact()."""
    if not text:
        return text
    for value in _stored_secret_values():
        if value in text:
            text = text.replace(value, "[redacted]")
    for term in extra:
        if term and len(term) >= 3 and term in text:
            text = text.replace(term, "[removed]")
    for pattern in _PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda m: f"{m.group(1)}=[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    # A Windows traceback carries C:\Users\<name>\ on every frame — the
    # username must not ride into a pasted issue. Both slash spellings.
    home = Path.home()
    for variant in (str(home), home.as_posix()):
        if variant and variant not in ("/", "\\"):
            text = text.replace(variant, "~")
    custom_home = os.environ.get("PUBLIKCLIP_HOME")
    if custom_home:
        for variant in (custom_home, custom_home.replace("\\", "/")):
            text = text.replace(variant, "~")
    return text


def install_excepthook() -> None:
    """Print unhandled tracebacks through redact(). The Rust shell's
    'exited' event is built from the stderr tail it captures — this hook is
    what makes that tail clean at the source instead of asking a second
    language to reimplement the rule."""
    def hook(exc_type, exc, tb) -> None:
        sys.stderr.write(redact("".join(traceback.format_exception(exc_type, exc, tb))))

    sys.excepthook = hook


# ---------------------------------------------------------------------------
# The catalogue. Every entry: human cause, at least one action, optional
# docs anchor. Entries with a recognizer are reachable at runtime; the rest
# are reference entries for §20's symptom rows (the test maps every §20 row
# to a code, per E14-F01's coverage criterion).

RESUME_ACTION = "Resume the job from the rail — everything up to the failed step is saved."
REPORT_ACTION = "If it happens again, copy the technical details and open an issue."


@dataclass(frozen=True)
class Entry:
    cause: str
    actions: tuple[str, ...]
    docs: str | None = None


CATALOG: dict[str, Entry] = {
    # --- LLM / scoring ----------------------------------------------------
    "no-gemini-key": Entry(
        "No Gemini API key is saved, and Gemini mode needs one.",
        ("Add a key in Settings (or set PUBLIKCLIP_GEMINI_API_KEY).",
         "Or switch this job to Ollama mode — local, no key."),
    ),
    "gemini-key-rejected": Entry(
        "Google rejected the saved Gemini API key.",
        ("Check the key in Settings — re-paste it from aistudio.google.com.",
         "Or switch to Ollama mode."),
    ),
    "gemini-quota-exhausted": Entry(
        "The Gemini key is out of quota — Google refused the call and said retrying will not help.",
        ("Check the key's usage and billing at aistudio.google.com.",
         RESUME_ACTION + " Scoring picks up where it stopped."),
    ),
    "llm-call-failed": Entry(
        "A scoring call to the model failed even after retries.",
        (RESUME_ACTION, "If it keeps failing, try a different Gemini model in Settings → AI."),
    ),
    "llm-consecutive-failures": Entry(
        "The scoring model failed several moments in a row — the service looks down for this run.",
        (RESUME_ACTION + " Scoring retries only the unscored moments.",
         "Or pick a different Gemini model in Settings → AI."),
    ),
    "llm-all-failed": Entry(
        "The model failed on every moment it was asked about — nothing was scored.",
        (RESUME_ACTION, "Check your connection, or pick a different Gemini model in Settings → AI."),
    ),
    "ollama-not-running": Entry(
        "Ollama is not running on this machine.",
        ("Start it (`ollama serve`), then resume the job.", "Or switch this job to Gemini mode."),
    ),
    "ollama-no-models": Entry(
        "Ollama is running but has no models installed.",
        ("Pull one, e.g. `ollama pull llama3.1:8b`, then resume the job.",),
    ),
    "no-scoreable-transcript": Entry(
        "No candidate moment had enough speech to score — the video may be too short or too quiet.",
        ("Check that the source has clear dialogue.",
         "Lower the minimum-words gate in Settings → Clips if quiet moments should count."),
    ),
    "no-candidates": Entry(
        "No candidate moments were found — the video may be too short or too quiet.",
        ("Check the source: Alias Studio needs speech and at least a few minutes of material.",),
    ),
    # --- source / download ------------------------------------------------
    "url-needs-login": Entry(
        "The site refused an anonymous download — this video needs a login, purchase, or age check.",
        ("Try a video that plays without signing in.",
         "Or download it yourself with your own access and drop the file in."),
    ),
    "url-not-video": Entry(
        "That URL does not point at a downloadable video.",
        ("Check the link — a channel page, playlist or members-only page will not work.",),
    ),
    "download-stalled": Entry(
        "The download stopped making progress and was cut off.",
        ("Check your connection, then " + RESUME_ACTION.lower(),),
    ),
    "download-failed": Entry(
        "The video could not be downloaded.",
        ("Check the link and your connection, then " + RESUME_ACTION.lower(),),
    ),
    "download-no-output": Entry(
        "The download finished but no video file appeared.",
        (RESUME_ACTION, REPORT_ACTION),
    ),
    "source-file-missing": Entry(
        "The source file is gone from where this job expects it.",
        ("Put the file back at its original path, or start a new job from its new location.",),
    ),
    "no-audio-track": Entry(
        "This video has no audio track, and Alias Studio needs speech to find moments.",
        ("Use a version of the video that includes its audio.",),
    ),
    "no-speech": Entry(
        "No speech was found in this video, and Alias Studio needs dialogue to find moments.",
        ("Check that the right audio track is present and audible.",),
    ),
    "media-unreadable": Entry(
        "The video file could not be read or probed — it may be corrupt or an unsupported format.",
        ("Try re-downloading or re-exporting the source, then resume the job.",),
    ),
    # --- machinery --------------------------------------------------------
    "prior-stage-missing": Entry(
        "An earlier step's results are missing from this job — its files may have been moved or deleted.",
        (RESUME_ACTION + " Missing steps re-run automatically.",),
    ),
    "audio-extract-failed": Entry(
        "The audio track could not be extracted for analysis.",
        (RESUME_ACTION, REPORT_ACTION),
    ),
    "render-failed": Entry(
        "A clip failed to encode.",
        (RESUME_ACTION + " Only unrendered clips re-run.",
         "If hardware encoding is on, try turning it off in Settings → Performance."),
        docs=DOCS,
    ),
    "clip-verification-failed": Entry(
        "A rendered clip failed its integrity check and was not kept.",
        (RESUME_ACTION, REPORT_ACTION),
    ),
    "no-clips-rendered": Entry(
        "No clips made it through rendering.",
        (RESUME_ACTION, REPORT_ACTION),
    ),
    "disk-full": Entry(
        "The disk filled up while this job was writing.",
        ("Free some space, then " + RESUME_ACTION.lower(),),
    ),
    "disk-space-blocked": Entry(
        "There is not enough free disk space to start this job.",
        ("Free some space, then " + RESUME_ACTION.lower(),),
    ),
    "out-of-memory": Entry(
        "The machine ran out of memory during this step.",
        ("Close other applications and resume the job.",
         "Very long sources need more headroom — a shorter source may be the practical fix."),
    ),
    "model-download-failed": Entry(
        "A model download failed.",
        ("Check your connection, then resume — downloads continue from where they stopped.",),
    ),
    "model-checksum-mismatch": Entry(
        "A downloaded model did not match its expected checksum — the file was corrupt and was discarded.",
        ("Resume the job to re-download it.", REPORT_ACTION),
        docs=DOCS,
    ),
    "ffmpeg-unavailable": Entry(
        "A subtitle-capable ffmpeg could not be found or downloaded.",
        ("Check your connection — the app fetches a static build when the system one cannot burn subtitles.",),
    ),
    # --- the two shapes no site raises directly ---------------------------
    "pipeline-exited": Entry(
        "The pipeline exited unexpectedly.",
        (RESUME_ACTION, REPORT_ACTION),
        docs=DOCS,
    ),
    "unknown": Entry(
        "Something failed that this app does not have an explanation for yet.",
        (RESUME_ACTION, REPORT_ACTION),
    ),
    # --- reference entries: §20 symptom rows with no runtime recognizer ---
    "setting-does-nothing": Entry(
        "A setting appears to change nothing — its stage is probably serving a cached result.",
        ("Re-run the job after changing the setting; if it still has no effect, open an issue.",),
        docs="SPECIFICATION.md#5-the-checkpoint-contract",
    ),
    "restyle-discards-edits": Entry(
        "A whole-job restyle appeared to discard per-clip editor work.",
        ("This should not happen — open an issue naming the clip and the setting changed.",),
        docs=DOCS,
    ),
    "gpu-idle": Entry(
        "The GPU sits idle even though CUDA torch is installed.",
        ("uv re-syncs from pyproject.toml on every launch — configure the CUDA index there.",),
        docs="SPECIFICATION.md#12-hardware-and-performance",
    ),
    "encoder-too-old": Entry(
        "A hardware encoder is listed but the driver is too old to use it.",
        ("Update the GPU driver, or turn hardware encoding off in Settings → Performance.",),
        docs=DOCS,
    ),
    "checkpoint-unreadable": Entry(
        "A job checkpoint could not be read.",
        (RESUME_ACTION + " Unreadable steps re-run.", REPORT_ACTION),
        docs=DOCS,
    ),
    "build-blank-page": Entry(
        "The app loads a blank page pointing at localhost:1430.",
        ("This is a build made with `cargo build` — rebuild with `npx tauri build`.",),
        docs="SPECIFICATION.md#16-building-and-installing",
    ),
    "no-installer": Entry(
        "A Windows build produced no installer.",
        ("bundle.targets is set for macOS — see the build documentation.",),
        docs="SPECIFICATION.md#16-building-and-installing",
    ),
    "ig-insufficient-role": Entry(
        "Instagram answered \"Insufficient Developer Role\" — a Meta app-role problem, not a bug here.",
        ("Add your Instagram account as a tester on the Meta app and accept the invite.",),
        docs="SPECIFICATION.md#13-the-instagram-feedback-loop",
    ),
}

# E14-F01: the catalogue covers at least every row of SPECIFICATION §20.
# One code per row, in the table's order; the test walks this list.
SPEC20_CODES = [
    "pipeline-exited",
    "setting-does-nothing",
    "restyle-discards-edits",
    "gpu-idle",
    "encoder-too-old",
    "checkpoint-unreadable",
    "build-blank-page",
    "no-installer",
    "ig-insufficient-role",
    "model-checksum-mismatch",
]


# ---------------------------------------------------------------------------
# ErrorInfo and describe()


@dataclass
class ErrorInfo:
    code: str
    cause: str
    actions: list[str]
    docs: str | None = None
    stage: str | None = None
    detail: str | None = None
    signature: str | None = None

    def to_json(self) -> dict:
        return {
            "code": self.code,
            "cause": self.cause,
            "actions": list(self.actions),
            "docs": self.docs,
            "stage": self.stage,
            "detail": self.detail,
            "signature": self.signature,
        }


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    node: BaseException | None = exc
    while node is not None and node not in seen and len(seen) < 8:
        seen.append(node)
        node = node.__cause__ or node.__context__
    return seen


def _signature(exc: BaseException) -> str:
    root = _chain(exc)[-1]
    sig = type(root).__name__
    errno = getattr(root, "errno", None)
    if errno is not None:
        sig += f" errno {errno}"
    return sig


def _classify(exc: BaseException) -> str | None:
    """Chain-walk recognizers. A coded exception anywhere in the chain wins
    (a StageError wrapping a coded LlmError inherits the inner code); after
    that, mechanisms we can name from the exception itself. Message
    sniffing is used only on OUR OWN stable strings, never on foreign
    library text."""
    for node in _chain(exc):
        code = getattr(node, "code", None)
        if isinstance(code, str) and code in CATALOG:
            return code
    for node in _chain(exc):
        name = type(node).__name__
        text = str(node)
        if isinstance(node, MemoryError):
            return "out-of-memory"
        if isinstance(node, OSError) and getattr(node, "errno", None) == 28:
            return "disk-full"
        if name == "YtDlpError":
            from .ingest.ytdlp import is_auth_error

            if is_auth_error(text):
                return "url-needs-login"
            if "stalled" in text:
                return "download-stalled"
            return "download-failed"
        if name == "FfmpegError":
            return "media-unreadable"
        if name == "LlmError":
            return "llm-call-failed"
        if name == "RuntimeError":
            if text.startswith("Model download failed"):
                return "model-download-failed"
            if "checksum mismatch" in text:
                return "model-checksum-mismatch"
            if "ffmpeg with subtitle support" in text:
                return "ffmpeg-unavailable"
    return None


def _is_user_facing(exc: BaseException) -> bool:
    """StageError's contract ("message is user-facing") extends to LlmError
    and YtDlpError, which are written to the same standard. Their text may
    serve as the cause; anything else may not."""
    return type(exc).__name__ in ("StageError", "LlmError", "YtDlpError", "IgError")


def describe(exc: BaseException, stage: str | None = None) -> ErrorInfo:
    """The one constructor of the user-facing error value. Every field is
    redacted here, which is what makes the rule unskippable."""
    code = _classify(exc)
    detail_parts: list[str] = []
    if code is not None:
        entry = CATALOG[code]
        # A user-facing message from the raise site beats the entry's
        # generic cause — the site knows more (bucket A: good text stays).
        cause = str(exc) if _is_user_facing(exc) and str(exc) else entry.cause
        chained = _chain(exc)
        if len(chained) > 1 or not _is_user_facing(exc):
            detail_parts.append("".join(traceback.format_exception(exc)).strip())
        site_detail = getattr(exc, "detail", None)
        if isinstance(site_detail, str) and site_detail:
            detail_parts.append(site_detail)
        info = ErrorInfo(
            code=code,
            cause=cause,
            actions=list(entry.actions),
            docs=entry.docs,
            stage=stage,
            detail="\n\n".join(detail_parts) or None,
            signature=_signature(exc),
        )
    elif _is_user_facing(exc):
        # An uncoded StageError honours its contract: its message is the
        # cause; the catalogue supplies the always-true actions.
        info = ErrorInfo(
            code="stage-error",
            cause=str(exc),
            actions=[RESUME_ACTION, REPORT_ACTION],
            stage=stage,
            detail="".join(traceback.format_exception(exc.__cause__)).strip()
            if exc.__cause__ else None,
            signature=_signature(exc),
        )
    else:
        # The unknown path — the twenty-first failure. Generic, names the
        # stage, claims nothing, and keeps the technical text (and only
        # there, the repr/traceback) behind the disclosure.
        where = f"the {stage} step" if stage else "this run"
        info = ErrorInfo(
            code="unknown",
            cause=f"Something failed in {where} that this app does not have an explanation for yet.",
            actions=[RESUME_ACTION, REPORT_ACTION],
            stage=stage,
            detail="".join(traceback.format_exception(exc)).strip(),
            signature=_signature(exc),
        )
    info.cause = redact(info.cause)
    info.actions = [redact(a) for a in info.actions]
    info.detail = redact(info.detail) if info.detail else None
    return info


def info_for(code: str, cause: str | None = None, stage: str | None = None,
             detail: str | None = None) -> ErrorInfo:
    """A catalogued ErrorInfo for a failure that is a decision, not an
    exception (e.g. the disk pre-flight's block)."""
    entry = CATALOG[code]
    return ErrorInfo(
        code=code,
        cause=redact(cause or entry.cause),
        actions=list(entry.actions),
        docs=entry.docs,
        stage=stage,
        detail=redact(detail) if detail else None,
    )
