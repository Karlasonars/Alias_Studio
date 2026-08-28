"""T-40: the first-launch numbers, kept honest across the language boundary.

The bootstrap runs before python can — so its constants live in main.rs,
where python's own numbers cannot reach them at runtime. These tests are
the compensating guard: the Rust models figure must track setup.py's
measured split, and the env constants must keep their documented ordering.

What is NOT checkable here, said plainly: ENV_DOWNLOAD_BYTES includes the
three pytorch-cu128 wheels, whose sizes uv.lock does not record — they
were measured with HEAD requests (2026-08-28: torch 3,461,384,651 B,
torchaudio 4,673,203 B, torchvision 7,540,039 B) and re-verifying them
needs the network, which tests do not get. What this file CAN do offline
is recompute every wheel size the lock does record and refuse a constant
smaller than that floor.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from publikclip_pipeline import config, setup

REPO = Path(__file__).resolve().parents[2]
MAIN_RS = REPO / "app" / "src-tauri" / "src" / "main.rs"


def _rust_const(name: str) -> int:
    text = MAIN_RS.read_text(encoding="utf-8")
    m = re.search(rf"const {name}: u64 = ([\d_]+);", text)
    assert m, f"main.rs no longer defines {name}"
    return int(m.group(1).replace("_", ""))


def test_the_rust_models_figure_tracks_setup_py() -> None:
    """The onboarding screen prices the models BEFORE python exists, from a
    Rust constant — a copy of setup.py's measured split, which is exactly
    the kind of number that drifts (T-27's lesson: a copy of a value in a
    place nobody re-reads). 5% tolerance: the setup figures are display
    estimates, not contracts."""
    figure = _rust_const("MODELS_FIRST_RUN_BYTES")
    measured = sum(
        item.bytes for item in setup.items(config.Settings()) if item.bytes is not None
    )
    assert abs(figure - measured) / measured < 0.05, (
        f"main.rs says the first-run models are {figure:,} bytes but setup.py's "
        f"items sum to {measured:,}. Update MODELS_FIRST_RUN_BYTES."
    )


def test_the_env_constants_keep_their_documented_meaning() -> None:
    """Download < physical disk need < apparent watcher total — the three
    describe the same bootstrap seen three ways (compressed wire bytes,
    unique bytes on disk, bytes counted under both watched trees). An edit
    that breaks the ordering has confused what one of them means."""
    download = _rust_const("ENV_DOWNLOAD_BYTES")
    disk = _rust_const("ENV_DISK_NEED_BYTES")
    apparent = _rust_const("ENV_APPARENT_TOTAL_BYTES")
    assert download < disk < apparent


def test_the_download_figure_covers_every_wheel_the_lock_sizes() -> None:
    """The offline-checkable floor: uv.lock records a size for every wheel
    except the pytorch-cu128 three. Sum the sizes a win32/cp312 install
    would pull and refuse an ENV_DOWNLOAD_BYTES below that floor plus the
    smallest the cu128 torch has ever been — a constant that fails this has
    been edited down without re-measuring."""
    lock = tomllib.loads((REPO / "pipeline" / "uv.lock").read_text(encoding="utf-8"))
    floor = 0
    for package in lock["package"]:
        best = None
        for wheel in package.get("wheels", []):
            fname = wheel["url"].rsplit("/", 1)[-1]
            if "size" not in wheel:
                continue
            if "win_amd64" in fname or fname.endswith("-any.whl"):
                best = wheel["size"]
                break
        if best:
            floor += best
    torch_floor = 3_000_000_000  # cu128 torch has never been smaller
    assert _rust_const("ENV_DOWNLOAD_BYTES") >= floor + torch_floor, (
        f"ENV_DOWNLOAD_BYTES is below the lock's own sized floor ({floor:,}) "
        "plus the cu128 torch — re-measure before shrinking it."
    )
