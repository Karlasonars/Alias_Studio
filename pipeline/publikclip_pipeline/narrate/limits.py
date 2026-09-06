"""How long a story may be, and how long its narration will run (E20-F01).

The deck shows the estimated narration length before the job starts, warns
above WARN_WORDS and refuses above MAX_WORDS with the limit named; `jobs
create` applies the same refusal, so a job over the limit cannot be
enqueued from the CLI either. One module holds the numbers, and the deck
reads them from `settings story-limits` rather than carrying a copy — a
second copy is how a limit drifts.

The two word limits are STARTING NUMBERS, chosen to be revised after the
owner has made a few stories, not measured against anything: 1500 words
is roughly ten minutes of narration, already long for the format, and 500
is where a story stops being one sitting on a phone. Nobody should later
read 1500 as research. WORDS_PER_MINUTE was measured once, on the
synthesis that verified the Kokoro integration (see the PR for E20); it
is an estimate for the deck's label, never a promise about the render.
"""

from __future__ import annotations

import re

MAX_WORDS = 1500   # hard limit — starting number, revise after use
WARN_WORDS = 500   # the deck warns above this — starting number, revise after use
# Kokoro's af_heart at speed 1.0, measured once on the verification
# synthesis (E20 PR, 2026-09-06): 51 words of prose became 16.48 s of
# audio, 185.7 words per minute. One paragraph, one voice — an estimate
# for the deck's label, not a promise about the render.
WORDS_PER_MINUTE = 185.0

_WORD = re.compile(r"\S+")


def word_count(text: str) -> int:
    return len(_WORD.findall(text or ""))


def estimate_seconds(words: int, speed: float = 1.0) -> float:
    """Narration seconds for `words` at Kokoro's `speed` multiplier. The
    deck computes the same expression with these numbers; the numbers
    travel to it, the formula is trivial enough to repeat."""
    rate = max(0.1, float(speed or 1.0))
    return words / WORDS_PER_MINUTE * 60.0 / rate


def check(text: str) -> str | None:
    """The refusal for a text that cannot be a story, or None. Names the
    limit in the message: a rejection that does not say the number leaves
    the user guessing how much to cut."""
    words = word_count(text)
    if words == 0:
        return "The story is empty — paste or load some text first."
    if words > MAX_WORDS:
        return (
            f"The story is {words} words; the limit is {MAX_WORDS}. "
            f"Cut it down by {words - MAX_WORDS} words, or split it into two stories."
        )
    return None


def warning(text: str) -> str | None:
    """The soft notice above WARN_WORDS, or None. Advisory: the job runs."""
    words = word_count(text)
    if words > WARN_WORDS:
        return (
            f"{words} words is a long story — about "
            f"{int(round(estimate_seconds(words) / 60))} minutes of narration. "
            f"Stories under {WARN_WORDS} words tend to hold better."
        )
    return None


def limits_payload() -> dict:
    """What `settings story-limits` prints: the numbers the deck needs to
    show the estimate and apply the same gates this module applies."""
    from . import kokoro_tts

    return {
        "ok": True,
        "max_words": MAX_WORDS,
        "warn_words": WARN_WORDS,
        "words_per_minute": WORDS_PER_MINUTE,
        "voices": [{"id": vid, "label": label} for vid, label in kokoro_tts.VOICES],
        "default_voice": kokoro_tts.DEFAULT_VOICE,
    }
