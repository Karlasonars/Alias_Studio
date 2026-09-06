"""Keep-range timeline math + dead-space detection.

A clip with dead space removed is a list of (start, end) KEEP ranges in
source time. Everything downstream — captions, crop trajectory, overlay
windows — must be remapped onto the concatenated output timeline. All pure
functions; the remap arithmetic is the part that silently ruins A/V sync if
it's wrong, so it lives here under tests.

Intentional-pause protection (the user's spec: "keep intentional pauses
only when they add emphasis or make the pacing feel natural"): a silence
survives the cut when it sits within EVENT_PROTECT_SEC of a detected
laugh/gasp (comedic timing beat), or when it is shorter than
NATURAL_PAUSE_MAX after a sentence-ending word (normal cadence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_CUT_GAP = 0.5          # silences shorter than this always stay
BREATH_PAD = 0.15          # seconds kept on each side of a cut silence
EVENT_PROTECT_SEC = 2.0    # pauses near laughter/gasps are comedic timing
NATURAL_PAUSE_MAX = 1.1    # post-sentence pauses up to this feel natural
MIN_KEEP_RANGE = 0.4       # never emit keep slivers shorter than this


@dataclass
class Overlay:
    id: str
    query: str
    source: str = "pexels"          # 'pexels' | 'gemini' | 'upload'
    image_path: str = ""
    start: float = 0.0              # OUTPUT-timeline seconds
    end: float = 2.0
    # x/y are fractions of the LEFTOVER space, matching ffmpeg's
    # overlay=(W-w)*x:(H-h)*y — an overlay mathematically cannot leave the
    # frame. y=0.10 sits in the top zone, clear of a centered face.
    # Face-safe default: the director centers the face mid-frame, captions
    # own the bottom third — the safe band is the very top. y=0.04 with
    # scale 0.38 keeps the overlay's bottom edge above ~26% of the frame.
    x: float = 0.5
    y: float = 0.04
    scale: float = 0.38             # width as fraction of frame width
    animation: str = "none"         # 'none' | 'pop' | 'ping' (opt-in)
    phrase: str = ""

    def to_json(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ClipEdit:
    """Per-clip overrides. Absent fields fall back to the run's globals."""

    start: float
    end: float
    caption_preset: str | None = None
    camera_mode: str | None = None
    gameplay_amount: float | None = None  # None = inherit the job's setting
    letterbox_fill: str | None = None     # 'black' | 'blur'; None = inherit
    # Publishing copy. `title` is the one the user picked; `title_variants`
    # keeps the alternatives so they can be compared (and A/B tested later)
    # without paying for regeneration.
    title: str = ""
    title_variants: list[dict] = field(default_factory=list)
    # The post caption. `description` is what the user copies (text plus
    # hashtags, ready to paste); description_meta keeps the parts and any
    # warnings so the UI can show why it was trimmed or what was stripped.
    description: str = ""
    description_meta: dict = field(default_factory=dict)
    # The title burned into the clip (E19-F01): the variant the user marked
    # in the editor, "" for none. Separate from `title`, which is publishing
    # copy beside the file and never reaches the pixels — this one does, so
    # it is in the render fingerprint and `title` stays out of it.
    burned_title: str = ""
    remove_dead_space: bool = False
    disabled_cuts: list[int] = field(default_factory=list)  # indices into auto cuts
    overlays: list[Overlay] = field(default_factory=list)
    # Per-clip overrides of the settings whose only cost is a re-render, so
    # they can be tuned here — where the result is visible — instead of in the
    # global panel. Both are partial patches: a key that isn't here inherits
    # the job's value, so a clip only carries what was actually changed.
    pacing: dict = field(default_factory=dict)              # PacingSettings fields
    caption_overrides: dict = field(default_factory=dict)   # ass.Preset fields
    lufs_target: float | None = None
    true_peak_db: float | None = None

    def to_json(self) -> dict:
        d = self.__dict__.copy()
        d["overlays"] = [o.to_json() for o in self.overlays]
        return d

    @classmethod
    def from_json(cls, data: dict) -> "ClipEdit":
        overlays = [Overlay(**o) for o in data.get("overlays", [])]
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            caption_preset=data.get("caption_preset"),
            camera_mode=data.get("camera_mode"),
            gameplay_amount=data.get("gameplay_amount"),
            letterbox_fill=data.get("letterbox_fill"),
            title=str(data.get("title", "")),
            title_variants=list(data.get("title_variants", [])),
            description=str(data.get("description", "")),
            description_meta=dict(data.get("description_meta") or {}),
            burned_title=str(data.get("burned_title") or ""),
            remove_dead_space=bool(data.get("remove_dead_space", False)),
            disabled_cuts=list(data.get("disabled_cuts", [])),
            overlays=overlays,
            pacing=dict(data.get("pacing") or {}),
            caption_overrides=dict(data.get("caption_overrides") or {}),
            lufs_target=data.get("lufs_target"),
            true_peak_db=data.get("true_peak_db"),
        )


def resolve_pacing(settings: "object", edit: "ClipEdit | None" = None) -> "object":
    """The job's pacing, with this clip's overrides applied on top.

    Kept here rather than inline at the call sites because BOTH the editor's
    timeline preview and the actual re-render must resolve it identically —
    if they drift, the cuts the user sees stop matching the cuts they get.
    """
    from .. import config

    base = config.PacingSettings(**settings.pacing.__dict__)
    for key, value in ((edit.pacing if edit else None) or {}).items():
        if hasattr(base, key) and isinstance(value, (int, float)) and not isinstance(value, bool):
            setattr(base, key, float(value))
    return base


def detect_dead_space(
    words: list[dict],
    events: list[dict],
    clip_start: float,
    clip_end: float,
    pacing: "object | None" = None,
) -> list[dict]:
    """Candidate cut ranges (source time) with the reason each pause was or
    wasn't protected — the UI shows every decision, click-to-toggle.

    `pacing` (settings.pacing) tunes how aggressive the trim is; omit it for
    the built-in defaults."""
    min_cut_gap = float(getattr(pacing, "min_cut_gap", MIN_CUT_GAP))
    breath_pad = float(getattr(pacing, "breath_pad", BREATH_PAD))
    event_protect = float(getattr(pacing, "event_protect_s", EVENT_PROTECT_SEC))
    natural_pause_max = float(getattr(pacing, "natural_pause_max", NATURAL_PAUSE_MAX))

    inside = [w for w in words if clip_start <= w["start"] < clip_end]
    cuts: list[dict] = []
    protect_spans = [
        (e["start"] - event_protect, e["end"] + event_protect)
        for e in events
        if e["type"] in ("laugh", "gasp", "scream", "applause", "cheer")
    ]

    def protected_by_event(a: float, b: float) -> bool:
        return any(a < pe and b > ps for ps, pe in protect_spans)

    boundary_pairs = []
    if inside:
        boundary_pairs.append((clip_start, inside[0]["start"], None))
        for prev, cur in zip(inside, inside[1:]):
            boundary_pairs.append((prev["end"], cur["start"], prev))
        boundary_pairs.append((inside[-1]["end"], clip_end, inside[-1]))

    for gap_start, gap_end, prev_word in boundary_pairs:
        gap = gap_end - gap_start
        if gap < min_cut_gap:
            continue
        if protected_by_event(gap_start, gap_end):
            cuts.append(
                {"start": gap_start, "end": gap_end, "kept": True, "reason": "comedic timing (near a reaction)"}
            )
            continue
        sentence_end = bool(prev_word and prev_word.get("word", "").rstrip().endswith((".", "!", "?")))
        if sentence_end and gap <= natural_pause_max:
            cuts.append(
                {"start": gap_start, "end": gap_end, "kept": True, "reason": "natural sentence pacing"}
            )
            continue
        cut_a = gap_start + breath_pad
        cut_b = gap_end - breath_pad
        if cut_b - cut_a < 0.2:
            continue
        cuts.append(
            {"start": round(cut_a, 3), "end": round(cut_b, 3), "kept": False, "reason": f"silence {gap:.1f}s"}
        )
    return cuts


def keep_ranges(
    clip_start: float,
    clip_end: float,
    cuts: list[dict],
    disabled: list[int] | None = None,
) -> list[tuple[float, float]]:
    """Source-time ranges that survive: the clip minus active (kept=False,
    not user-disabled) cuts. Always returns ≥1 range."""
    disabled = set(disabled or [])
    active = [
        c for i, c in enumerate(cuts)
        if not c.get("kept") and i not in disabled and c["end"] > clip_start and c["start"] < clip_end
    ]
    active.sort(key=lambda c: c["start"])
    ranges: list[tuple[float, float]] = []
    cursor = clip_start
    for cut in active:
        a = max(clip_start, cut["start"])
        b = min(clip_end, cut["end"])
        if a - cursor >= MIN_KEEP_RANGE:
            ranges.append((round(cursor, 3), round(a, 3)))
        cursor = max(cursor, b)
    if clip_end - cursor >= MIN_KEEP_RANGE:
        ranges.append((round(cursor, 3), round(clip_end, 3)))
    if not ranges:
        ranges = [(clip_start, clip_end)]
    return ranges


class TimeRemap:
    """Source time → concatenated output time across keep ranges."""

    def __init__(self, ranges: list[tuple[float, float]]):
        self.ranges = ranges
        self._offsets: list[float] = []
        acc = 0.0
        for a, b in ranges:
            self._offsets.append(acc)
            acc += b - a
        self.output_duration = acc

    def to_output(self, t: float) -> float | None:
        """None when t falls inside a cut."""
        for (a, b), off in zip(self.ranges, self._offsets):
            if a <= t <= b:
                return round(off + (t - a), 3)
        return None

    def to_output_clamped(self, t: float) -> float:
        """Nearest output time — cut interiors snap to the following keep."""
        for (a, b), off in zip(self.ranges, self._offsets):
            if t < a:
                return round(off, 3)
            if t <= b:
                return round(off + (t - a), 3)
        return round(self.output_duration, 3)

    def remap_words(self, words: list[dict]) -> list[dict]:
        """Words surviving the cuts, times moved to the output timeline.
        A word whose middle falls in a cut is dropped (its audio is gone)."""
        out = []
        for w in words:
            mid = (w["start"] + w["end"]) / 2
            if self.to_output(mid) is None:
                continue
            a = self.to_output_clamped(w["start"])
            b = self.to_output_clamped(w["end"])
            if b <= a:
                b = a + 0.04
            out.append({**w, "start": a, "end": b})
        return out

    def remap_trajectory(self, frames: list, fps: float, clip_start: float) -> list:
        """Per-frame crop rects re-sampled onto the output timeline: output
        frame k at time k/fps maps back to a source frame inside some keep
        range."""
        out = []
        n_out = int(self.output_duration * fps)
        for k in range(n_out):
            t_out = k / fps
            # invert: half-open ranges so a frame exactly on a cut boundary
            # maps to the NEXT keep range, not the end of the previous one
            src_t = None
            for i, ((a, b), off) in enumerate(zip(self.ranges, self._offsets)):
                span = b - a
                last = i == len(self.ranges) - 1
                if off <= t_out < off + span or (last and t_out <= off + span):
                    src_t = a + (t_out - off)
                    break
            if src_t is None:
                src_t = self.ranges[-1][1]
            idx = int((src_t - clip_start) * fps)
            idx = max(0, min(idx, len(frames) - 1))
            out.append(frames[idx])
        return out or frames[:1]
