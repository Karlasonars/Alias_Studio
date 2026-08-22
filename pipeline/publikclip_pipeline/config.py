"""Paths and settings.

Everything lives under PUBLIKCLIP_HOME (default ~/.publikclip):

    ~/.publikclip/
      db.sqlite3            job + stage bookkeeping
      settings.json         user-editable global defaults (seeds new jobs)
      caption_presets.json  user edits to built-in presets + custom presets
      bin/                  managed binaries (yt-dlp)
      models/               downloaded model weights
      jobs/<job_id>/        per-job artifacts (media, audio, stage checkpoints)

The desktop app points PUBLIKCLIP_HOME at its own app-data dir; the CLI uses
the default. Artifacts on disk are the source of truth — the DB only records
what should exist so a stage can decide whether to skip itself on resume.

Settings model
--------------
`Settings` is the whole tunable surface of the pipeline, grouped by the thing
it controls. Two rules keep it honest:

  1. Every field here is READ somewhere in the pipeline. A field that nothing
     consumes is a lie to the user — if you add one, wire it in the same
     commit.
  2. Settings are snapshotted per job at creation (jobs/<id>/settings.json +
     the DB row), so changing a global default never silently rescores or
     reframes an old job. `load_defaults()` seeds NEW jobs only.

Deserialization is deliberately lenient (`_build`): unknown keys are dropped
and missing keys keep their default, so a settings file written by an older
or newer build always loads instead of crashing a resume.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar


def home_dir() -> Path:
    return Path(os.environ.get("PUBLIKCLIP_HOME", str(Path.home() / ".publikclip")))


def jobs_dir() -> Path:
    return home_dir() / "jobs"


def bin_dir() -> Path:
    return home_dir() / "bin"


def models_dir() -> Path:
    return home_dir() / "models"


def db_path() -> Path:
    return home_dir() / "db.sqlite3"


def settings_path() -> Path:
    return home_dir() / "settings.json"


def caption_presets_path() -> Path:
    return home_dir() / "caption_presets.json"


def ensure_home() -> Path:
    root = home_dir()
    for d in (root, jobs_dir(), bin_dir(), models_dir()):
        d.mkdir(parents=True, exist_ok=True)
    return root


# Hard per-attempt network timeouts (seconds). A blackholed connection must
# never freeze the pipeline — every subprocess/network call takes one of these.
HTTP_TIMEOUT = 60.0
SUBPROCESS_INACTIVITY_TIMEOUT = 120.0  # kill if no output for this long
PROBE_TIMEOUT = 60.0

# Ingest
MAX_HEIGHT = 1080
AUDIO_SR = 16_000  # analysis sample rate; every M1 model consumes this wav


T = TypeVar("T")


def _build(cls: type[T], data: Any) -> T:
    """Construct a settings dataclass from JSON, ignoring unknown keys and
    keeping defaults for missing ones. Lets old jobs load under new builds
    (and vice versa) instead of raising on an unexpected keyword."""
    if not isinstance(data, dict):
        return cls()
    names = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


# ---------------------------------------------------------------------------
# Clips: what counts as a candidate moment, and how many survive to the
# expensive passes. Consumed by candidates/windows.py + scoring/stage.py.


@dataclass
class ClipSettings:
    min_len: float = 15.0          # a window shorter than this is discarded
    max_len: float = 75.0          # ...longer than this is contracted
    target_len: float = 42.0       # the length windows are grown toward
    snap_radius: float = 6.0       # how far an edge may move to hit a sentence
    dedupe_iou: float = 0.55       # overlap above this = same moment
    max_candidates: int = 35       # pool size handed to scoring
    peak_min_distance_s: int = 20  # suppress curve peaks closer than this
    select_count: int = 12         # finalists that get the visual pass + render
    # Candidates with fewer spoken words are skipped before any LLM call. The
    # gate exists so silent filler isn't scored as a talking clip — but it also
    # drops quiet action moments, so gameplay-style content wants it low.
    min_words: int = 20


# ---------------------------------------------------------------------------
# Interest curve: how the free channels are weighed into "is this moment
# interesting". Consumed by candidates/curve.py. Missing channels (e.g. no
# public heatmap) have their weight redistributed across the rest.


@dataclass
class CurveWeights:
    heatmap: float = 0.30    # real viewer replays, when the platform exposes them
    dynamics: float = 0.25   # audio energy deviation from local baseline
    events: float = 0.18     # laughter / gasp / applause density
    turns: float = 0.10      # conversational back-and-forth rate
    arousal: float = 0.09    # vocal arousal (speech emotion)
    scenes: float = 0.05     # visual change rate (shot cuts)
    lexical: float = 0.03    # power words in the transcript


DEFAULT_PLATFORM_WEIGHTS: dict[str, dict[str, float]] = {
    "tiktok": {"hook": 0.32, "funniness": 0.26, "shock": 0.16, "curiosity_gap": 0.16, "value": 0.10},
    "reels": {"hook": 0.28, "funniness": 0.22, "shock": 0.14, "curiosity_gap": 0.16, "value": 0.20},
    "shorts": {"hook": 0.26, "funniness": 0.20, "shock": 0.12, "curiosity_gap": 0.22, "value": 0.20},
}


@dataclass
class ScoringSettings:
    """How the LLM subscores and the free curve combine into a 0-100 score.
    Consumed by scoring/rubric.py."""

    t0_weight: float = 0.30       # curve share of the pre-visual composite
    text_weight: float = 0.6      # text vs visual split, once the T2 pass ran
    visual_weight: float = 0.4
    platform_weights: dict[str, dict[str, float]] = field(
        default_factory=lambda: copy.deepcopy(DEFAULT_PLATFORM_WEIGHTS)
    )


# ---------------------------------------------------------------------------
# Retention: the pattern-interrupt layer. Punch-ins are the only automatic
# visual interrupt today; these knobs set how hard and how often they fire.
# Consumed by camera/director.py.


@dataclass
class RetentionSettings:
    punch_zoom: float = 1.12          # peak zoom of a punch-in (1.0 = off)
    punch_rise_s: float = 0.25
    punch_hold_s: float = 1.3
    punch_fall_s: float = 0.55
    punch_min_spacing_s: float = 3.0  # never two punches closer than this
    punch_seconds_per_punch: float = 8.0  # cap: one punch per N s of clip


# ---------------------------------------------------------------------------
# Pacing: dead-space removal in the per-clip editor. Consumed by
# edits/timeline.py.


@dataclass
class PacingSettings:
    min_cut_gap: float = 0.5        # silences shorter than this always stay
    breath_pad: float = 0.15        # kept on each side of a cut silence
    event_protect_s: float = 2.0    # pauses near laughter are comedic timing
    natural_pause_max: float = 1.1  # post-sentence pauses up to this feel natural
    min_keep_range: float = 0.4     # never emit keep slivers shorter than this


# ---------------------------------------------------------------------------
# Camera / framing.


@dataclass
class CameraSettings:
    """User-facing camera preset knobs (locked decision #7: exposed options)."""

    # 'cut' = hard cut on speaker change (default), 'pan' = eased pan between
    # speakers, 'locked' = static crop on the dominant face.
    speaker_change: str = "cut"
    # Length of the eased pan in 'pan'/'locked' mode — drives the smoothing
    # window, so a longer value glides more slowly between speakers.
    pan_duration_s: float = 0.6
    # Target drift below this fraction of frame width is ignored, so the crop
    # holds still instead of chasing sub-pixel jitter.
    deadzone_frac: float = 0.05
    punch_in: bool = True
    punch_in_sensitivity: float = 1.0  # scales event/energy trigger thresholds
    zoom_lock_per_scene: bool = True
    # 0.0 = tight 9:16 face crop. 1.0 = full source frame, letterboxed — for
    # gameplay/facecam content where the tight crop shows only the face.
    gameplay_amount: float = 0.0


# ---------------------------------------------------------------------------
# Captions. `preset` names a built-in (or a user-defined preset stored in
# caption_presets.json); `overrides` is a partial field patch applied on top,
# so a job can deviate without forking a whole preset.


@dataclass
class CaptionSettings:
    overrides: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Performance. These trade a little fidelity for a lot of wall-clock, so each
# one is opt-out rather than hidden — and each says what it actually costs.


@dataclass
class PerformanceSettings:
    # PySceneDetect compares every frame in Python; on an 81-minute source
    # that measured 48+ minutes to feed a 0.05-weight channel. ffmpeg does
    # the same job in C on downscaled frames.
    fast_scene_detect: bool = True
    scene_threshold: float = 0.35   # ffmpeg `scene` score, 0-1
    scene_height: int = 180         # frames are compared at this height
    # Hardware video encoding (NVENC / QuickSync). Much faster than x264,
    # but the encoder is different, so output is comparable rather than
    # identical — off by default so nobody's renders change silently.
    hardware_encode: bool = False


# ---------------------------------------------------------------------------
# Copywriting: titles and hooks. Consumed by copywriting/titles.py and
# copywriting/hooks.py, which run on demand rather than as pipeline stages —
# regenerating a title must never invalidate a render.


DEFAULT_TITLE_STYLES = ["direct", "curiosity", "question"]
DEFAULT_HOOK_TYPES = [
    "question", "statement", "surprising_fact", "conflict",
    "open_loop", "teaser", "in_medias_res", "emotional",
]


@dataclass
class TitleSettings:
    variants: int = 3
    min_chars: int = 20
    max_chars: int = 80
    tone: str = "natural"          # natural | punchy | provocative | informative
    styles: list[str] = field(default_factory=lambda: list(DEFAULT_TITLE_STYLES))
    allow_questions: bool = True
    allow_numbers: bool = True
    require_cta: bool = False
    # Guards against titles that promise more than the clip delivers. The
    # feedback loop punishes overselling, so this defaults on.
    forbid_clickbait: bool = True
    uppercase: bool = False
    keywords: str = ""             # words to weave in where they fit naturally


@dataclass
class DescriptionSettings:
    """The post caption — the longer text pasted under the video, as opposed
    to the title. Same honesty rule as titles: it must describe the clip that
    actually exists."""

    max_chars: int = 300           # long enough to matter, short enough to read
    min_chars: int = 40
    tone: str = "natural"          # natural | punchy | provocative | informative
    hashtags: int = 3              # 0 disables them entirely
    include_cta: bool = False      # "follow for more" style ending
    allow_emoji: bool = False
    forbid_clickbait: bool = True
    keywords: str = ""             # woven in where they fit naturally


@dataclass
class HookSettings:
    window_s: float = 3.0          # how much of the opening counts as the hook
    max_shift_s: float = 8.0       # how far the start may move to find a better one
    max_options: int = 5           # start points offered to the model
    min_remaining_s: float = 8.0   # never suggest a start that guts the clip
    suggest_text_hook: bool = True
    types: list[str] = field(default_factory=lambda: list(DEFAULT_HOOK_TYPES))


def _string_list(value: Any, allowed: list[str], fallback: list[str]) -> list[str]:
    """Settings lists come from JSON and from a UI; keep only known values and
    never return empty, so a mis-click can't leave an engine with nothing to
    choose from."""
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [v for v in value if isinstance(v, str) and v in allowed]
    return cleaned or list(fallback)


@dataclass
class Settings:
    """Per-job settings snapshot. Serialized into the job dir at creation so a
    resumed job never silently picks up changed defaults."""

    camera: CameraSettings = field(default_factory=CameraSettings)
    clips: ClipSettings = field(default_factory=ClipSettings)
    curve: CurveWeights = field(default_factory=CurveWeights)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    retention: RetentionSettings = field(default_factory=RetentionSettings)
    pacing: PacingSettings = field(default_factory=PacingSettings)
    captions: CaptionSettings = field(default_factory=CaptionSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    titles: TitleSettings = field(default_factory=TitleSettings)
    descriptions: DescriptionSettings = field(default_factory=DescriptionSettings)
    hooks: HookSettings = field(default_factory=HookSettings)
    lufs_target: float = -14.0  # decision #8: configurable per destination
    true_peak_db: float = -1.0
    llm_mode: str = "gemini"  # 'gemini' (BYO key) | 'ollama' (local fallback)
    caption_preset: str = "classic"
    # jrgillick laughter specialist: 10 ms precision but ~300k CPU forward
    # passes on an hour-plus source. OFF by default — PANNs' AudioSet
    # laughter classes cover the bus at 320 ms resolution for a fraction of
    # the compute; flip on for the two-detector agreement boost.
    laughter_specialist: bool = False

    def to_json(self) -> dict:
        return {
            "camera": self.camera.__dict__.copy(),
            "clips": self.clips.__dict__.copy(),
            "curve": self.curve.__dict__.copy(),
            "scoring": {
                **self.scoring.__dict__,
                "platform_weights": copy.deepcopy(self.scoring.platform_weights),
            },
            "retention": self.retention.__dict__.copy(),
            "pacing": self.pacing.__dict__.copy(),
            "captions": {"overrides": dict(self.captions.overrides)},
            "performance": self.performance.__dict__.copy(),
            "titles": {**self.titles.__dict__, "styles": list(self.titles.styles)},
            "descriptions": self.descriptions.__dict__.copy(),
            "hooks": {**self.hooks.__dict__, "types": list(self.hooks.types)},
            "lufs_target": self.lufs_target,
            "true_peak_db": self.true_peak_db,
            "llm_mode": self.llm_mode,
            "caption_preset": self.caption_preset,
            "laughter_specialist": self.laughter_specialist,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Settings":
        scoring = _build(ScoringSettings, data.get("scoring"))
        # platform_weights is a free-form dict: merge onto defaults so a
        # partial edit (or a platform added in a later build) still resolves.
        merged = copy.deepcopy(DEFAULT_PLATFORM_WEIGHTS)
        for platform, weights in (scoring.platform_weights or {}).items():
            if isinstance(weights, dict):
                merged.setdefault(platform, {}).update(
                    {k: float(v) for k, v in weights.items() if isinstance(v, (int, float))}
                )
        scoring.platform_weights = merged

        # Lists need their own sanitising: a stale or hand-edited value must
        # not leave an engine with an unknown style or an empty choice set.
        titles = _build(TitleSettings, data.get("titles"))
        titles.styles = _string_list(
            titles.styles,
            ["direct", "curiosity", "question", "quote", "stakes", "contrast", "listicle"],
            DEFAULT_TITLE_STYLES,
        )
        hooks = _build(HookSettings, data.get("hooks"))
        hooks.types = _string_list(hooks.types, DEFAULT_HOOK_TYPES, DEFAULT_HOOK_TYPES)

        return cls(
            camera=_build(CameraSettings, data.get("camera")),
            clips=_build(ClipSettings, data.get("clips")),
            curve=_build(CurveWeights, data.get("curve")),
            scoring=scoring,
            retention=_build(RetentionSettings, data.get("retention")),
            pacing=_build(PacingSettings, data.get("pacing")),
            captions=_build(CaptionSettings, data.get("captions")),
            performance=_build(PerformanceSettings, data.get("performance")),
            titles=titles,
            descriptions=_build(DescriptionSettings, data.get("descriptions")),
            hooks=hooks,
            lufs_target=data.get("lufs_target", -14.0),
            true_peak_db=data.get("true_peak_db", -1.0),
            llm_mode=data.get("llm_mode", "gemini"),
            caption_preset=data.get("caption_preset", "classic"),
            laughter_specialist=data.get("laughter_specialist", False),
        )


# ---------------------------------------------------------------------------
# Global defaults: what a NEW job starts from. Existing jobs keep their own
# snapshot, so editing these never rewrites history.


def load_defaults() -> Settings:
    path = settings_path()
    if path.exists():
        try:
            return Settings.from_json(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass  # a corrupt settings file must never block a run
    return Settings()


def save_defaults(settings: Settings) -> None:
    ensure_home()
    path = settings_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings.to_json(), indent=1), encoding="utf-8")
    tmp.replace(path)


def load_caption_presets() -> dict[str, dict]:
    """User edits to built-in presets + fully custom presets, as partial
    field patches keyed by preset name. Merged over the built-ins in
    captions/ass.py."""
    path = caption_presets_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, dict)}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_caption_presets(presets: dict[str, dict]) -> None:
    ensure_home()
    path = caption_presets_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(presets, indent=1), encoding="utf-8")
    tmp.replace(path)
