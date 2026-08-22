"""Hook engine: make the first seconds earn the rest of the clip.

The single most effective hook lever in this app is not text — it is WHERE
the clip starts. A clip that opens two sentences before the interesting line
has already lost. So this engine's primary output is a set of candidate
start times, each snapped to a real sentence boundary (the same boundaries
the candidate stage uses, so a suggestion is always a legal cut), with the
opening line it produces and why it works.

Secondary output is an optional on-screen text hook for the opening seconds.

Everything here is a suggestion: it maps onto `ClipEdit.start`, which the
user already controls in the clip editor, so accepting a suggestion is the
same cheap per-clip re-render as dragging the handle by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Hook shapes the engine can be asked for. Descriptions are written for the
# model, so they say what to DO, not what the term means academically.
HOOK_TYPES: dict[str, str] = {
    "question": "Open on a question the clip then answers.",
    "statement": "Open on the single boldest claim actually made.",
    "surprising_fact": "Open on the most counterintuitive true detail.",
    "conflict": "Open mid-disagreement or mid-tension.",
    "open_loop": "Open on something unresolved that the clip resolves.",
    "teaser": "Open by naming the payoff without giving it away.",
    "in_medias_res": "Open mid-action, skipping all setup.",
    "emotional": "Open on the strongest emotional beat.",
}

HOOK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_index": {
                        "type": "integer",
                        "description": "0-based index of the offered start option this refers to",
                    },
                    "hook_type": {"type": "string", "enum": sorted(HOOK_TYPES)},
                    "strength": {
                        "type": "number",
                        "description": "0-10, how hard this opening stops a scroll",
                    },
                    "why": {"type": "string", "description": "one short line"},
                    "risk": {
                        "type": "string",
                        "description": "what this opening loses (missing context, etc), or 'none'",
                    },
                },
                "required": ["start_index", "hook_type", "strength", "why", "risk"],
            },
        },
        "text_hook": {
            "type": "string",
            "description": "optional short on-screen hook for the opening seconds, or empty",
        },
    },
    "required": ["candidates", "text_hook"],
}


@dataclass
class HookOptions:
    """Mirrors config.HookSettings."""

    window_s: float = 3.0        # how much of the opening counts as "the hook"
    max_shift_s: float = 8.0     # how far the start may move, in either direction
    max_options: int = 5         # start points offered to the model
    types: list[str] = field(default_factory=lambda: sorted(HOOK_TYPES))
    suggest_text_hook: bool = True
    min_remaining_s: float = 8.0  # never suggest a start that guts the clip


def start_options(
    sentence_starts: list[float],
    clip_start: float,
    clip_end: float,
    opts: HookOptions,
) -> list[float]:
    """Legal alternative start points: real sentence starts within
    ±max_shift_s of the current one, that still leave a usable clip.

    Snapping to sentence starts is what keeps a suggestion actionable — an
    arbitrary timestamp would open mid-word, which is exactly the thing the
    candidate stage already refuses to do.
    """
    lo = clip_start - abs(opts.max_shift_s)
    hi = clip_start + abs(opts.max_shift_s)
    out: list[float] = []
    for t in sorted(sentence_starts):
        if t < lo or t > hi:
            continue
        if clip_end - t < opts.min_remaining_s:
            continue
        if any(abs(t - existing) < 0.25 for existing in out):
            continue  # same beat, don't offer it twice
        out.append(round(float(t), 3))
    # Always include the current start so the model can say "leave it".
    if not any(abs(clip_start - t) < 0.25 for t in out):
        out.append(round(float(clip_start), 3))
    out.sort()
    if len(out) > opts.max_options:
        # Keep the current start plus the nearest alternatives around it.
        out.sort(key=lambda t: abs(t - clip_start))
        out = sorted(out[: opts.max_options])
    return out


def opening_line(words: list[dict], start: float, window_s: float) -> str:
    """The words a viewer actually hears in the first `window_s` seconds if
    the clip started at `start`."""
    spoken = [
        str(w.get("word", "")).strip()
        for w in words
        if start <= float(w.get("start", 0.0)) < start + window_s
    ]
    return " ".join(t for t in spoken if t)


def prompt(
    options: list[float],
    words: list[dict],
    opts: HookOptions,
    summary: str = "",
) -> str:
    allowed = [t for t in opts.types if t in HOOK_TYPES] or sorted(HOOK_TYPES)
    lines = []
    for i, start in enumerate(options):
        heard = opening_line(words, start, opts.window_s) or "(silence)"
        lines.append(f'{i}. t={start:.2f}s → "{heard}"')

    ask_text = (
        "Also write one short on-screen text hook (max 60 chars) for the "
        "opening seconds, grounded in what is actually said. Leave it empty "
        "if nothing honest fits.\n"
        if opts.suggest_text_hook
        else "Return an empty string for text_hook.\n"
    )

    return (
        "You are choosing where a short-form clip should START so that its "
        "first seconds stop a scroll.\n\n"
        f"{('What the clip is about: ' + summary) if summary else ''}\n\n"
        f"These are the legal start points and what the viewer would hear in "
        f"the first {opts.window_s:.0f} seconds of each:\n"
        + "\n".join(lines)
        + "\n\nRate each option you consider viable. Be honest: an opening that "
        "sounds strong but removes the context needed to understand the clip is "
        "a bad opening — say so in `risk`. Most openings are mediocre; a 9 or 10 "
        "should be rare.\n"
        f"Allowed hook types: {', '.join(allowed)}\n"
        + ask_text
    )


def _clean_candidates(raw: list[dict], options: list[float], opts: HookOptions) -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("start_index", -1))
        except (TypeError, ValueError):
            continue
        if not 0 <= idx < len(options) or idx in seen:
            continue  # a hallucinated index must not become a bogus cut
        seen.add(idx)
        try:
            strength = max(0.0, min(10.0, float(item.get("strength", 0))))
        except (TypeError, ValueError):
            strength = 0.0
        hook_type = str(item.get("hook_type", ""))
        out.append(
            {
                "start": options[idx],
                "hook_type": hook_type if hook_type in HOOK_TYPES else "statement",
                "strength": round(strength, 1),
                "why": str(item.get("why", "")),
                "risk": str(item.get("risk", "")),
            }
        )
    out.sort(key=lambda c: c["strength"], reverse=True)
    return out


def analyze(
    client: Any,
    sentence_starts: list[float],
    words: list[dict],
    clip_start: float,
    clip_end: float,
    opts: HookOptions,
    summary: str = "",
) -> dict:
    """Rank alternative openings for one clip.

    Returns the current opening alongside the ranked candidates so the UI can
    show whether moving is actually an improvement — 'the model suggested
    something' is not the same as 'this is better than what you have'.
    """
    options = start_options(sentence_starts, clip_start, clip_end, opts)
    if len(options) <= 1:
        return {
            "candidates": [],
            "text_hook": "",
            "current_start": round(clip_start, 3),
            "note": "no alternative sentence boundaries within range",
        }

    data = client.generate_json(prompt(options, words, opts, summary), HOOK_SCHEMA)
    candidates = _clean_candidates(data.get("candidates", []), options, opts)
    current = next(
        (c for c in candidates if abs(c["start"] - clip_start) < 0.25), None
    )
    best = candidates[0] if candidates else None
    return {
        "candidates": candidates,
        "text_hook": str(data.get("text_hook", "")).strip()[:60],
        "current_start": round(clip_start, 3),
        "current_strength": current["strength"] if current else None,
        # Only claim an improvement when the model actually rated the
        # alternative above the opening the user already has.
        "improves": bool(
            best and current and best["start"] != current["start"]
            and best["strength"] > current["strength"]
        ),
        "options_considered": options,
    }
