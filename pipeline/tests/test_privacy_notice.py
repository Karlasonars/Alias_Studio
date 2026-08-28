"""E15-F03 / T-17: the privacy notice is auditable, not marketing.

PRIVACY.md claims to name every network call the app makes. A claim like
that decays the moment someone adds an httpx call in a feature branch, so
this guard extracts every host the code can reach and asserts each one
appears in PRIVACY.md:

  - literal http(s):// URLs in the pipeline's Python string constants
    (via ast, so vendored code and # comments stay out of it),
  - literal URLs in the Rust shell and the frontend (text scan with
    comment lines stripped — the shell reaches the network through curl,
    which no Python-side grep would ever see),
  - literal URLs in pyproject.toml (the CUDA wheel index uv pulls from),
  - and the hosts reached by downloaders that never spell a URL in this
    repository at all (huggingface_hub, torch.hub, uv's bootstrap).

The scan is deliberately over-inclusive: a host in an f-string fragment
or after an inline comment still counts. A false positive costs one line
of documentation; a false negative costs the document its honesty — an
incomplete privacy notice is worse than none.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "publikclip_pipeline"
REPO = Path(__file__).resolve().parents[2]
VENDOR = PKG / "vendor"
PRIVACY = REPO / "PRIVACY.md"

_HOST = re.compile(r"https?://([A-Za-z0-9][A-Za-z0-9.-]*)")

#: Hosts the app reaches without any literal URL in this repository. Each
#: entry names the code path that proves it, so a future reader can check
#: the claim instead of trusting it.
INDIRECT_HOSTS = {
    "huggingface.co": "huggingface_hub fetches the Whisper snapshot (setup.py) "
    "and lazy non-English aligners (asr/stage.py) with no literal URL",
    "download.pytorch.org": "torchaudio resolves the wav2vec2 aligner there; "
    "also uv's CUDA wheel index (pyproject.toml)",
    "pypi.org": "uv resolves the pipeline's dependencies on a packaged "
    "build's first launch (main.rs pipeline_invocation)",
    "files.pythonhosted.org": "where pypi.org actually serves wheels from",
    "github.com": "torch.hub fetches the silero-vad snapshot; also literal "
    "in models/specs.py and ingest/ytdlp.py",
}


def _hosts_in(text: str) -> set[str]:
    return {m.group(1).lower().rstrip(".") for m in _HOST.finditer(text)}


def _python_hosts() -> dict[str, set[str]]:
    """Hosts per file, from string constants only — comments never carry
    traffic, but every URL that does get requested is a string first."""
    out: dict[str, set[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        if VENDOR in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found |= _hosts_in(node.value)
        if found:
            out[path.relative_to(REPO).as_posix()] = found
    return out


def _stripped_of_comment_lines(text: str) -> str:
    """Drop whole-line comments (Rust ///, //, TS //, block-comment lines
    starting with *) and JSON $schema editor references: neither carries
    traffic. Inline trailing comments stay in — over-inclusive is the
    safe direction here."""
    kept = [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*", '"$schema"'))
    ]
    return "\n".join(kept)


def _shell_and_frontend_hosts() -> dict[str, set[str]]:
    files = [REPO / "app" / "src-tauri" / "src" / "main.rs"]
    app_src = REPO / "app" / "src"
    for pattern in ("*.ts", "*.tsx"):
        files += [
            p
            for p in app_src.rglob(pattern)
            if ".test." not in p.name and (app_src / "test") not in p.parents
        ]
    files.append(REPO / "pipeline" / "pyproject.toml")
    # T-16's updater endpoint will land here — the guard must see it arrive.
    files.append(REPO / "app" / "src-tauri" / "tauri.conf.json")
    out: dict[str, set[str]] = {}
    for path in sorted(files):
        found = _hosts_in(_stripped_of_comment_lines(path.read_text(encoding="utf-8")))
        if found:
            out[path.relative_to(REPO).as_posix()] = found
    return out


def test_every_reachable_host_appears_in_privacy_md() -> None:
    notice = PRIVACY.read_text(encoding="utf-8").lower()
    missing: list[str] = []
    sources: dict[str, set[str]] = {}
    for origin, hosts in {**_python_hosts(), **_shell_and_frontend_hosts()}.items():
        for host in hosts:
            sources.setdefault(host, set()).add(origin)
    for host, reason in INDIRECT_HOSTS.items():
        sources.setdefault(host, set()).add(f"(no literal URL) {reason}")
    for host, origins in sorted(sources.items()):
        if host not in notice:
            missing.append(f"{host}  — from: {', '.join(sorted(origins))}")
    assert not missing, (
        "Hosts the code can reach that PRIVACY.md does not name — the "
        "privacy notice is now incomplete, which is worse than having "
        "none. Document each (what is sent, when, to whom, optional or "
        "not) or remove the call:\n  " + "\n  ".join(missing)
    )


def test_the_scan_actually_sees_the_known_calls() -> None:
    """A guard that greps for nothing passes forever. Pin the hosts this
    scan must find today, one per scanning mechanism, so a refactor that
    blinds the extractor (moved file, changed literal shape) fails here
    instead of silently passing above."""
    python = {h for hosts in _python_hosts().values() for h in hosts}
    shell = {h for hosts in _shell_and_frontend_hosts().values() for h in hosts}
    assert "generativelanguage.googleapis.com" in python  # scoring/llm.py
    assert "zenodo.org" in python  # models/specs.py
    assert "ffmpeg.martin-riedl.de" in python  # render/ffmpeg_bin.py
    assert "generativelanguage.googleapis.com" in shell  # main.rs key check
    assert "download.pytorch.org" in shell  # pyproject.toml CUDA index
    assert "aistudio.google.com" in shell  # Onboarding.tsx browser link


def test_the_two_load_bearing_sentences_are_present() -> None:
    """The PRD's acceptance criteria name two claims the notice must make:
    media is never uploaded, and Gemini's free tier may use prompts to
    improve Google's products (the T-39 finding — the single most
    important sentence in the document). Pin both so a rewrite cannot
    soften them away while the host list stays green."""
    notice = PRIVACY.read_text(encoding="utf-8")
    assert "never uploaded" in notice
    assert "free-tier prompts" in notice and "improve its products" in notice
