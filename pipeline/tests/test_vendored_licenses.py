"""E16-F03 / T-18: the AGPL surface stays true.

Three claims the About screen makes are only as good as the records
behind them, so each record gets a guard:

  - VENDORED-LICENSES.md says it covers the vendored code. If someone
    drops a fifth project into vendor/ without recording it, the About
    screen's attribution list silently lies — cheaper to catch here than
    in a licence dispute. Both directions are checked: every vendor dir
    is recorded, every recorded vendor dir exists.
  - The doc also claims "vendored files carry an attribution header".
    That claim is checked, not assumed (this repo has walked back four
    unverified claims already).
  - The version the UI shows has ONE defined place: tauri.conf.json,
    read at runtime through getVersion(). A literal copy of that value
    in app/src would eventually drift from it, so none is allowed —
    About.test.tsx pins the other half (the screen shows whatever the
    API answers).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "publikclip_pipeline"
REPO = Path(__file__).resolve().parents[2]
VENDOR = PKG / "vendor"
DOC = REPO / "VENDORED-LICENSES.md"


def _vendor_dirs() -> list[str]:
    return sorted(
        p.name for p in VENDOR.iterdir() if p.is_dir() and not p.name.startswith("__")
    )


def test_every_vendor_dir_is_recorded_in_the_doc() -> None:
    doc = DOC.read_text(encoding="utf-8")
    missing = [name for name in _vendor_dirs() if f"vendor/{name}" not in doc]
    assert not missing, (
        f"vendor/ holds {missing} but VENDORED-LICENSES.md never mentions "
        "them. §1 calls that file authoritative — record the upstream, its "
        "license and what was taken, in the same commit as the code."
    )


def test_every_recorded_vendor_dir_exists() -> None:
    doc = DOC.read_text(encoding="utf-8")
    recorded = set(re.findall(r"vendor/([a-z0-9_]+)", doc))
    stale = sorted(recorded - set(_vendor_dirs()))
    assert not stale, (
        f"VENDORED-LICENSES.md records vendor dirs that no longer exist: "
        f"{stale}. Remove the row or restore the code — a record of ghosts "
        "is not authoritative."
    )


def test_vendored_files_carry_an_attribution_header() -> None:
    """The doc's own claim: 'Vendored files carry an attribution header
    pointing back here.' Checked as: every vendored .py names its
    upstream (an Upstream: line or an upstream Copyright) in its opening
    lines."""
    bare: list[str] = []
    for path in sorted(VENDOR.rglob("*.py")):
        if path.name == "__init__.py":
            continue
        head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:6])
        if "Upstream:" not in head and "Copyright" not in head:
            bare.append(str(path.relative_to(REPO)))
    assert not bare, f"vendored files with no attribution header: {bare}"


def test_the_app_version_is_defined_in_exactly_one_place() -> None:
    """The UI must show getVersion()'s answer, never a copy. A literal
    of the version value anywhere in app/src is a second definition
    waiting to drift from tauri.conf.json's."""
    conf = json.loads(
        (REPO / "app" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    version = conf["version"]
    offenders: list[str] = []
    app_src = REPO / "app" / "src"
    for pattern in ("*.ts", "*.tsx"):
        for path in app_src.rglob(pattern):
            if version in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO)))
    assert not offenders, (
        f"the app version {version!r} appears as a literal in {offenders} — "
        "the version has one defined place (tauri.conf.json) and one reader "
        "(getVersion()). Delete the copy."
    )
