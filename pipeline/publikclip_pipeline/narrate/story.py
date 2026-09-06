"""The story text as the job holds it (E20-F01).

A story is CONTENT, not a setting: it is copied into the job dir as
`story.txt` by `jobs create` and read from there by every stage that needs
it. It never lives in the settings snapshot — a whole story in global
defaults would seed every later job with it — and it is never fetched
from anywhere: the tool takes pasted text or a .txt file the user chose,
and nothing else (F01).

Shape: the first non-empty line is the TITLE, everything after it the
BODY. The title is what the story card shows (F05) and what the narration
reads first; a text with one line is a title and nothing more. No other
markup is understood, on purpose — a story is a story, not a document.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import limits

STORY_FILE = "story.txt"


@dataclass(frozen=True)
class Story:
    title: str
    body: str
    text: str          # the normalised whole, what is hashed and narrated
    sha256: str        # identity of `text` — the narrate fingerprint's text key
    word_count: int


def normalise(text: str) -> str:
    """One canonical form for hashing: LF line endings, no trailing
    whitespace per line, no leading or trailing blank lines. The same
    story pasted from Windows and from a .txt therefore hashes the same,
    and a saved-then-reloaded file does not re-narrate."""
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n").strip()


def parse(text: str) -> Story:
    whole = normalise(text)
    lines = whole.split("\n") if whole else []
    non_empty = [i for i, line in enumerate(lines) if line.strip()]
    if not non_empty:
        return Story(title="", body="", text="", sha256=_sha(""), word_count=0)
    first = non_empty[0]
    title = lines[first].strip()
    body = "\n".join(lines[first + 1:]).strip("\n").strip()
    return Story(
        title=title,
        body=body,
        text=whole,
        sha256=_sha(whole),
        word_count=limits.word_count(whole),
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def path_in(job_dir: Path) -> Path:
    return Path(job_dir) / STORY_FILE


def store(job_dir: Path, text: str) -> Path:
    """Copy the story into the job dir, normalised, UTF-8, LF — the file
    the narrate stage hashes. Returns its path."""
    dest = path_in(job_dir)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # newline="\\n": text mode would write CRLF on Windows and the hash
    # would depend on the platform the job was created on (CLAUDE.md §3).
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(normalise(text) + "\n")
    return dest


def load(job_dir: Path) -> Story:
    """The job's story. Raises FileNotFoundError when the job has none —
    the stage turns that into a described failure."""
    return parse(path_in(job_dir).read_text(encoding="utf-8"))
