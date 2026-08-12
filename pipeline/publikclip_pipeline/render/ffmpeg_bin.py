"""ffmpeg binary resolution.

Caption burning needs an ffmpeg built with libass, and (as this very
machine demonstrates) Homebrew's slimmed `ffmpeg` formula ships without it.
Resolution order: PUBLIKCLIP_FFMPEG env → bundled sidecar binary (packaged
app) → Homebrew ffmpeg-full keg → PATH. The first candidate that actually
has the `subtitles` filter wins; if none do, the plain PATH binary is
returned with `has_subtitles=False` so the caller can degrade (render
without burned captions) with an honest message instead of a crash.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import zipfile
from functools import lru_cache
from pathlib import Path

from .. import config

_KEG_CANDIDATES = [
    "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg",
    "/usr/local/opt/ffmpeg-full/bin/ffmpeg",
]

# Static macOS builds with libass (ffmpeg.martin-riedl.de). Used only when
# no capable ffmpeg exists on the machine — downloaded once into
# PUBLIKCLIP_HOME/bin so end users never touch Homebrew.
_STATIC_BASE = "https://ffmpeg.martin-riedl.de/redirect/latest/macos/{arch}/release/{tool}.zip"


def _has_subtitles_filter(binary: str) -> bool:
    try:
        proc = subprocess.run(
            [binary, "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return " subtitles " in proc.stdout


@lru_cache(maxsize=1)
def resolve() -> tuple[str, bool]:
    """(ffmpeg_path, has_subtitles)."""
    candidates: list[str] = []
    env = os.environ.get("PUBLIKCLIP_FFMPEG")
    if env:
        candidates.append(env)
    candidates.append(str(config.bin_dir() / "ffmpeg"))  # our downloaded static
    bundled = os.environ.get("PUBLIKCLIP_BUNDLED_FFMPEG")  # set by the app shell
    if bundled:
        candidates.append(bundled)
    candidates.extend(_KEG_CANDIDATES)
    path_ffmpeg = shutil.which("ffmpeg")
    if path_ffmpeg:
        candidates.append(path_ffmpeg)

    fallback: str | None = None
    for cand in candidates:
        if not os.path.exists(cand):
            continue
        fallback = fallback or cand
        if _has_subtitles_filter(cand):
            return cand, True
    return (fallback or "ffmpeg"), False


def ffmpeg() -> str:
    return resolve()[0]


def ffprobe() -> str:
    """ffprobe next to the resolved ffmpeg when present, else PATH."""
    sibling = Path(ffmpeg()).parent / "ffprobe"
    if sibling.exists():
        return str(sibling)
    return shutil.which("ffprobe") or "ffprobe"


def supports_captions() -> bool:
    return resolve()[1]


def ensure_capable(progress=None) -> bool:
    """If no libass ffmpeg exists anywhere, download the static build once
    into PUBLIKCLIP_HOME/bin (macOS arm64/x86_64), then re-resolve. Returns
    whether caption burning is available afterwards."""
    if supports_captions():
        return True
    if platform.system() != "Darwin":
        return False
    import httpx

    arch = "arm64" if platform.machine() == "arm64" else "amd64"
    config.ensure_home()
    for tool in ("ffmpeg", "ffprobe"):
        dest = config.bin_dir() / tool
        if dest.exists() and (_has_subtitles_filter(str(dest)) if tool == "ffmpeg" else True):
            continue
        if progress:
            progress(-1, f"Downloading {tool} (one-time, caption support)…")
        url = _STATIC_BASE.format(arch=arch, tool=tool)
        zpath = dest.with_suffix(".zip")
        try:
            with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as res:
                if res.status_code != 200:
                    return False
                with open(zpath, "wb") as fh:
                    for chunk in res.iter_bytes():
                        fh.write(chunk)
            with zipfile.ZipFile(zpath) as zf:
                for name in zf.namelist():
                    if name.rstrip("/").endswith(tool):
                        dest.write_bytes(zf.read(name))
                        break
            dest.chmod(0o755)
        except (httpx.HTTPError, OSError, zipfile.BadZipFile):
            return False
        finally:
            zpath.unlink(missing_ok=True)
    resolve.cache_clear()
    return supports_captions()
