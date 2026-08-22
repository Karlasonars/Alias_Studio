"""Post description / caption generation.

The description is the block of text pasted under the video — longer than a
title, and doing a different job: it gives the context the title had no room
for, carries the searchable words, and (optionally) the hashtags.

Same structure as titles.py, and for the same reason: every constraint the
user sets is enforced twice — once in the prompt, and again in `finalize()`
after the model answers, because a prompt is a request and a filter is a
guarantee. The honesty rule is identical too: a description must describe the
clip that actually exists. Overselling costs the account its next impression,
and the feedback loop that feeds this app measures exactly that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

TONES = ("natural", "punchy", "provocative", "informative")

DESCRIPTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {
            "type": "string",
            "description": "the caption text, without hashtags",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "topic words, no '#' prefix, lowercase",
        },
        "grounded_in": {
            "type": "string",
            "description": "the transcript words this description is based on",
        },
    },
    "required": ["description", "hashtags", "grounded_in"],
}

# Same bait constructions titles rejects — a description is just as capable of
# promising a payoff the clip doesn't contain.
_BAIT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\byou won'?t believe\b",
        r"\bthis one (weird )?trick\b",
        r"\bwhat happened next\b",
        r"\bdoctors hate\b",
        r"\bshocking truth\b",
        r"\bnobody talks about\b",
        r"\bwill blow your mind\b",
        r"\bchanged my life forever\b",
        r"\bwait for it\b",
    )
]

# Anything outside the BMP plus the common pictographic ranges. Kept explicit
# rather than "strip non-ascii" so accented Latin, Cyrillic and CJK survive —
# only emoji are optional, not other people's alphabets.
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0000fe00-\U0000fe0f\U00002b00-\U00002bff]+"
)
_HASHTAG_CLEAN = re.compile(r"[^0-9a-z]+")


@dataclass
class DescriptionOptions:
    """Mirrors config.DescriptionSettings; standalone so the engine is usable
    (and testable) without building a whole Settings tree."""

    max_chars: int = 300
    min_chars: int = 40
    tone: str = "natural"
    hashtags: int = 3
    include_cta: bool = False
    allow_emoji: bool = False
    forbid_clickbait: bool = True
    keywords: str = ""


def prompt(
    transcript: str,
    summary: str,
    opts: DescriptionOptions,
    context: dict | None = None,
) -> str:
    context = context or {}
    rules: list[str] = [
        f"Write ONE description between {opts.min_chars} and {opts.max_chars} characters.",
        "It must describe what is actually in this clip. Do not invent facts, "
        "numbers, outcomes, or drama that the transcript does not support. If the "
        "clip is ordinary, write an honest description of an ordinary clip.",
        "Do not repeat the title's wording — add the context the title had no room for.",
        "Return the exact transcript words it is based on in grounded_in.",
    ]
    if opts.hashtags > 0:
        rules.append(
            f"Return up to {opts.hashtags} hashtags as plain lowercase words in the "
            "hashtags array (no '#'). They must be about what the clip actually "
            "contains — not generic reach-bait like 'fyp' or 'viral'."
        )
    else:
        rules.append("Return an empty hashtags array.")
    if not opts.allow_emoji:
        rules.append("Do not use emoji.")
    if opts.include_cta:
        rules.append("End with a short, natural call to action.")
    if opts.forbid_clickbait:
        rules.append(
            "No clickbait formulas ('you won't believe', 'wait for it'). "
            "Specific beats sensational."
        )
    if opts.keywords.strip():
        rules.append(
            f"Work these words in naturally where they fit: {opts.keywords.strip()}. "
            "Do not force one in if it would read badly."
        )
    tone = opts.tone if opts.tone in TONES else "natural"
    rules.append(f"Overall tone: {tone}.")

    events = context.get("events_desc")
    title = context.get("title")
    extra = ""
    if title:
        extra += f"\nThe title already chosen: {title}\n"
    if events:
        extra += f"Audio events in this clip: {events}\n"

    return (
        "You are writing the description that goes under a short-form video "
        "clip (TikTok / Reels / Shorts). It is read after the title has already "
        "earned the stop, so its job is context and searchable words, not a "
        "second hook.\n\n"
        f"What the clip is about: {summary or 'see transcript'}\n"
        f"{extra}\n"
        f"Transcript:\n{transcript}\n\n"
        + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rules))
    )


def clean_hashtags(raw: Any, limit: int) -> list[str]:
    """Normalize to lowercase alphanumeric tags, deduped, capped at `limit`.
    The model is asked for bare words but reliably sometimes returns '#tag',
    'Tag', or a sentence — normalize rather than trust."""
    if limit <= 0 or not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        tag = _HASHTAG_CLEAN.sub("", str(item).strip().lower().lstrip("#"))
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
        if len(out) >= limit:
            break
    return out


def _truncate(text: str, limit: int) -> str:
    """Cut at a sentence end if one is close to the limit, else at a word
    boundary — never mid-word, which reads like a bug rather than an edit."""
    if len(text) <= limit:
        return text
    window = text[: limit + 1]
    for end in (". ", "! ", "? "):
        idx = window.rfind(end)
        if idx >= limit * 0.6:
            return window[: idx + 1].strip()
    idx = window.rfind(" ")
    return (window[:idx] if idx > 0 else window[:limit]).rstrip(" ,;:-") + "…"


def finalize(raw: dict, opts: DescriptionOptions) -> dict:
    """Model output → the description actually shown, plus why anything was
    changed. Returns `warnings` rather than failing: a slightly-too-long
    description is fixable here, and a hard failure would leave the user with
    nothing to paste."""
    warnings: list[str] = []
    text = " ".join(str((raw or {}).get("description", "")).split()).strip()
    text = text.strip('"').strip()

    if not opts.allow_emoji and _EMOJI.search(text):
        text = " ".join(_EMOJI.sub("", text).split())
        warnings.append("removed emoji")

    if opts.forbid_clickbait:
        for pattern in _BAIT_PATTERNS:
            if pattern.search(text):
                warnings.append(f"clickbait phrasing ({pattern.pattern})")
                break

    if len(text) > opts.max_chars:
        text = _truncate(text, opts.max_chars)
        warnings.append(f"trimmed to {opts.max_chars} chars")
    if text and len(text) < opts.min_chars:
        warnings.append(f"shorter than the {opts.min_chars}-char minimum")

    tags = clean_hashtags((raw or {}).get("hashtags"), opts.hashtags)
    return {
        "description": text,
        "hashtags": tags,
        # What the user actually copies: description plus hashtags, ready to
        # paste. Kept as its own field so the two can also be used separately.
        "full": (text + ("\n\n" + " ".join(f"#{t}" for t in tags) if tags else "")).strip(),
        "grounded_in": str((raw or {}).get("grounded_in", "")),
        "warnings": warnings,
        "chars": len(text),
    }


def generate(
    client: Any,
    transcript: str,
    summary: str,
    opts: DescriptionOptions,
    context: dict | None = None,
) -> dict:
    """One LLM call → a validated description. The client's disk cache means
    regenerating with identical inputs and options costs nothing."""
    raw = client.generate_json(prompt(transcript, summary, opts, context), DESCRIPTION_SCHEMA)
    return {**finalize(raw, opts), "options": opts.__dict__.copy()}
