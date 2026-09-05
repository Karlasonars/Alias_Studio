"""Moment labels for the ranking video (E18-F04): the one to three words
next to each number in the list — "bath bomb", "the confession" — a name
for the moment, not a title for it.

Same shape as titles.py, for the same reason: a schema, a prompt that
carries the same honesty rule, and a filter that guarantees what the
prompt only asked for. One call per moment rather than one for all N: a
failure then blanks one number instead of five, and the client's disk
cache makes an identical re-ask free.

Unlike the other engines in this package this one is called from INSIDE
a stage (render/ranking.py): a title is metadata beside the file, a label
is burned into it. The package docstring names that exception. This
module only ever turns one transcript into one label; whether to ask at
all — a label is generated once and then reused from the render
checkpoint — is the stage's decision, not this module's.
"""

from __future__ import annotations

import re
from typing import Any

MAX_WORDS = 3
# The column budget. Labels are drawn NUMBER_COLUMN px right of the numbers
# (captions/ranking.py), the largest entry face is 56 px, and the widest
# preset font (Archivo Black, uppercase) advances about 0.7 em per glyph:
# 1080 - 60 - 90 - 60 = 870 px of column at ~39 px per glyph. Measured on
# a burned frame (2026-09-05): 22 M's fit every preset at 56 px with ~95 px
# to spare in Archivo Black; only 22 W's reach the frame edge, where the
# overlay's \q2 cuts them rather than wrapping. A label that does not fit
# its row is worse than none — the row below is the next number — so the
# filter rejects it rather than the overlay folding it.
MAX_CHARS = 22

LABEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {
            "type": "string",
            "description": "one to three words naming what happens in this moment",
        },
        "grounded_in": {
            "type": "string",
            "description": "the words in the transcript this label is based on",
        },
    },
    "required": ["label", "grounded_in"],
}

# A label is a name for the moment, not a sentence: a full stop under a
# number reads as a caption that lost its words. Dots and commas between
# digits ("3.5", "1,000") are numbers, not punctuation, and stay.
_SENTENCE_PUNCT = re.compile(r"[!?;:…]|(?<!\d)[.,]|[.,](?!\d)")
# The ranges descriptions.py drops, for a harder reason here: the caption
# fonts have no emoji glyphs, and a burned tofu box cannot be edited away.
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0000fe00-\U0000fe0f\U00002b00-\U00002bff]+"
)


def prompt(transcript: str, summary: str) -> str:
    rules = [
        f"One to three words. Two is ideal. At most {MAX_CHARS} characters.",
        "The label must be supported by the transcript. Do not invent facts, "
        "numbers, outcomes, or drama that is not there. If the moment is "
        "ordinary, name it honestly.",
        "A name, not a sentence: no full stop, no question mark, no quotes, no emoji.",
        "Write it in the language of the transcript.",
        "Return the exact transcript words it is based on in grounded_in.",
    ]
    return (
        "You are naming one moment in a countdown of the best moments from a "
        "longer video: a 'TOP 5' list burned into a vertical clip. Next to the "
        "moment's number the viewer reads a few words that say what the moment "
        "is ('bath bomb', 'the confession', 'wrong door'). It appears the "
        "instant the moment starts playing, so it must be recognisable from "
        "what is on screen, not clever.\n\n"
        f"What the moment is about: {summary or 'see transcript'}\n\n"
        f"Transcript:\n{transcript}\n\n"
        + "\n".join(f"{i + 1}. {r}" for i, r in enumerate(rules))
    )


def _normalize(text: Any) -> str:
    text = " ".join(str(text).split()).strip().strip("\"'“”‘’").strip()
    return " ".join(_EMOJI.sub("", text).split())


def _rejection(text: str) -> str | None:
    """Why this label is unusable, or None. Returned rather than silently
    dropped so the blank entry it becomes can be explained (the stage
    stores it beside the blank, in render.json)."""
    if not text:
        return "empty"
    if len(text.split()) > MAX_WORDS:
        return f"longer than {MAX_WORDS} words"
    if _SENTENCE_PUNCT.search(text):
        return "sentence punctuation"
    if len(text) > MAX_CHARS:
        return f"longer than {MAX_CHARS} characters"
    return None


def finalize(raw: Any) -> dict:
    """Model output → the label actually burned, or None and why. A bad
    answer is rejected, not repaired: descriptions.py trims because a
    too-long caption is fixable, but a label goes into pixels nobody can
    edit afterwards, so an unusable one must become a blank entry rather
    than a trimmed guess. `proposed` keeps what the model said either way,
    so a rejection can be read in the job dir."""
    raw = raw if isinstance(raw, dict) else {}
    proposed = _normalize(raw.get("label", ""))
    reason = _rejection(proposed)
    return {
        "label": None if reason else proposed,
        "proposed": proposed,
        "grounded_in": str(raw.get("grounded_in", "")),
        "rejected_because": reason,
    }


def generate(client: Any, transcript: str, summary: str) -> dict:
    """One LLM call → one validated label, or None and the reason.

    Never raises: a label is optional and the montage that carries it is
    not (CLAUDE.md §5.9), so a failing client yields a blank entry, never a
    failed render. `fatal` relays LlmError's verdict on whether every
    further call would fail the same way (a rejected key, no quota left);
    the stage uses it to stop asking, not to fail."""
    try:
        raw = client.generate_json(prompt(transcript, summary), LABEL_SCHEMA)
    except Exception as err:  # noqa: BLE001 — a blank entry, never a failed render
        return {
            "label": None,
            "proposed": "",
            "grounded_in": "",
            "rejected_because": None,
            "error": str(err),
            "fatal": bool(getattr(err, "fatal", False)),
        }
    return {**finalize(raw), "error": None, "fatal": False}
