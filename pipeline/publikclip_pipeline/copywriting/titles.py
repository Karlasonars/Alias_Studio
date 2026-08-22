"""Title / caption-copy generation.

Produces several titles for one clip so they can be compared (and later
A/B tested) instead of accepting whatever the model said first. Every
constraint the user sets in Settings — length, tone, whether questions or
numbers are allowed, required keywords, CTA — is enforced twice: once in
the prompt, and again in `_filter_variants` after the model answers, because
a prompt is a request and a filter is a guarantee.

Honesty rule (from the brief, and non-negotiable): a title must describe
what is actually in the clip. The prompt forbids inventing facts, numbers,
or outcomes that the transcript doesn't support, and `forbid_clickbait`
additionally rejects the classic bait constructions. A title that oversells
costs the account its next impression — the loop that feeds this app punishes
it, so generating it would be self-defeating, not clever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Styles the engine can be asked for. Each is a genuinely different framing,
# not a synonym — the point of variants is coverage, not five rewordings.
STYLES: dict[str, str] = {
    "direct": "State the most interesting thing plainly. No teasing.",
    "curiosity": "Open a specific loop the clip closes. Never vague ('this one trick').",
    "question": "Ask the exact question the clip answers.",
    "quote": "Lead with the strongest short quote actually said in the clip.",
    "stakes": "Lead with what was at risk, lost, or won.",
    "contrast": "Set two things against each other ('X, but Y').",
    "listicle": "Lead with a concrete count of what is shown.",
}

TONES = ("natural", "punchy", "provocative", "informative")

TITLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "variants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "the title itself"},
                    "style": {"type": "string", "enum": sorted(STYLES)},
                    "why": {
                        "type": "string",
                        "description": "one short line: what makes this land",
                    },
                    "grounded_in": {
                        "type": "string",
                        "description": "the words in the transcript this title is based on",
                    },
                },
                "required": ["text", "style", "why", "grounded_in"],
            },
        }
    },
    "required": ["variants"],
}

# Constructions that promise a payoff the clip cannot contain. Rejected when
# forbid_clickbait is on.
_BAIT_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"\byou won'?t believe\b",
        r"\bthis one (weird )?trick\b",
        r"\bwhat happened next\b",
        r"\bdoctors hate\b",
        r"\bgone wrong\b",
        r"\bshocking truth\b",
        r"\bnobody talks about\b",
        r"\bwill blow your mind\b",
        r"\bchanged my life forever\b",
    )
]

_NUMERIC = re.compile(r"\d")
_QUESTION = re.compile(r"\?\s*$")


@dataclass
class TitleOptions:
    """Mirrors config.TitleSettings; kept as its own dataclass so the engine
    is usable (and testable) without constructing a whole Settings tree."""

    variants: int = 3
    min_chars: int = 20
    max_chars: int = 80
    styles: list[str] = field(default_factory=lambda: ["direct", "curiosity", "question"])
    tone: str = "natural"
    allow_questions: bool = True
    allow_numbers: bool = True
    require_cta: bool = False
    forbid_clickbait: bool = True
    keywords: str = ""
    uppercase: bool = False


def _style_lines(styles: list[str]) -> str:
    chosen = [s for s in styles if s in STYLES] or ["direct"]
    return "\n".join(f"- {s}: {STYLES[s]}" for s in chosen)


def prompt(transcript: str, summary: str, opts: TitleOptions, context: dict | None = None) -> str:
    context = context or {}
    rules: list[str] = [
        f"Write {max(1, opts.variants)} DIFFERENT titles for this clip.",
        f"Each title must be between {opts.min_chars} and {opts.max_chars} characters.",
        "Every title must be supported by the transcript. Do not invent facts, "
        "numbers, outcomes, or drama that is not there. If the clip is ordinary, "
        "write an honest title for an ordinary clip.",
        "Return the exact transcript words each title is based on in grounded_in.",
    ]
    if not opts.allow_questions:
        rules.append("Do NOT phrase any title as a question.")
    if not opts.allow_numbers:
        rules.append("Do NOT use digits or numerals.")
    if opts.require_cta:
        rules.append("End each title with a short, natural call to action.")
    if opts.forbid_clickbait:
        rules.append(
            "No clickbait formulas ('you won't believe', 'this one trick', "
            "'what happened next'). Specific beats sensational."
        )
    if opts.keywords.strip():
        rules.append(
            f"Work these words in naturally where they fit: {opts.keywords.strip()}. "
            "Do not force one in if it would make the title read badly."
        )
    tone = opts.tone if opts.tone in TONES else "natural"
    rules.append(f"Overall tone: {tone}.")

    events = context.get("events_desc")
    extra = f"\nAudio events in this clip: {events}\n" if events else ""

    return (
        "You are writing titles for a short-form video clip (TikTok / Reels / "
        "Shorts). The title is what makes someone stop scrolling, so it must be "
        "both accurate and specific.\n\n"
        f"What the clip is about: {summary or 'see transcript'}\n"
        f"{extra}\n"
        f"Transcript:\n{transcript}\n\n"
        "Use a different framing for each title:\n"
        f"{_style_lines(opts.styles)}\n\n"
        + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rules))
    )


def _normalize(text: str, opts: TitleOptions) -> str:
    text = " ".join(str(text).split())
    text = text.strip().strip('"').strip("'").strip()
    return text.upper() if opts.uppercase else text


def _rejection(text: str, opts: TitleOptions) -> str | None:
    """Why this variant is unusable, or None if it passes. Returned rather
    than silently dropped so the UI can explain an empty result."""
    if not text:
        return "empty"
    if len(text) < opts.min_chars:
        return f"shorter than {opts.min_chars} chars"
    if len(text) > opts.max_chars:
        return f"longer than {opts.max_chars} chars"
    if not opts.allow_questions and _QUESTION.search(text):
        return "questions are disabled"
    if not opts.allow_numbers and _NUMERIC.search(text):
        return "numbers are disabled"
    if opts.forbid_clickbait:
        for pattern in _BAIT_PATTERNS:
            if pattern.search(text):
                return f"clickbait phrasing ({pattern.pattern})"
    return None


def filter_variants(raw: list[dict], opts: TitleOptions) -> tuple[list[dict], list[dict]]:
    """(kept, rejected). The model is asked to follow the constraints; this
    is where they are actually enforced, because a prompt is a request and a
    filter is a guarantee."""
    kept: list[dict] = []
    rejected: list[dict] = []
    seen: set[str] = set()
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        text = _normalize(item.get("text", ""), opts)
        reason = _rejection(text, opts)
        entry = {
            "text": text,
            "style": str(item.get("style", "direct")),
            "why": str(item.get("why", "")),
            "grounded_in": str(item.get("grounded_in", "")),
            "chars": len(text),
        }
        if reason:
            rejected.append({**entry, "rejected_because": reason})
            continue
        key = text.casefold()
        if key in seen:
            rejected.append({**entry, "rejected_because": "duplicate"})
            continue
        seen.add(key)
        kept.append(entry)
    return kept, rejected


def generate(
    client: Any,
    transcript: str,
    summary: str,
    opts: TitleOptions,
    context: dict | None = None,
) -> dict:
    """One LLM call → validated title variants. The client's disk cache means
    regenerating with identical inputs and options costs nothing."""
    text = client.generate_json(prompt(transcript, summary, opts, context), TITLE_SCHEMA)
    kept, rejected = filter_variants(text.get("variants", []), opts)
    return {
        "titles": kept,
        "rejected": rejected,
        "options": opts.__dict__.copy(),
    }
