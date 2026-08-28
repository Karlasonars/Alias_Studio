"""E15-F01 / T-16: what is checkable about the updater without publishing
two releases — the configuration, its consistency, and the promises the
docs make about it. The update itself (signature verification, the
installer swap, relaunch, data survival) is provable only by a real
release; the T-16 PR says so rather than pretending otherwise.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONF = REPO / "app" / "src-tauri" / "tauri.conf.json"


def _conf() -> dict:
    return json.loads(CONF.read_text(encoding="utf-8"))


def test_updater_config_is_complete_and_signed() -> None:
    """The pubkey must actually be a minisign public key, not a placeholder
    that would make every installed app reject every update. And
    createUpdaterArtifacts must NOT be global: with it in tauri.conf.json,
    every plain `npx tauri build` (windows.yml, any dev machine) refuses to
    build without the signing key — found the hard way when the first CI
    run of this branch died on exactly that. It belongs only in the release
    workflow's --config override, next to the key (checked below)."""
    conf = _conf()
    assert "createUpdaterArtifacts" not in conf["bundle"]
    pubkey = conf["plugins"]["updater"]["pubkey"]
    decoded = base64.b64decode(pubkey).decode("utf-8")
    assert decoded.startswith("untrusted comment: minisign public key")


def test_update_endpoint_is_the_release_page_the_ui_links() -> None:
    """One repository, referenced twice: the About screen's source links
    and the updater endpoint. If they ever name different repos, either
    the source offer or the update feed is pointing at the wrong place."""
    endpoints = _conf()["plugins"]["updater"]["endpoints"]
    assert len(endpoints) == 1
    about = (REPO / "app" / "src" / "components" / "About.tsx").read_text(encoding="utf-8")
    repo_url = re.search(r"const REPO = '([^']+)'", about).group(1)
    assert endpoints[0] == f"{repo_url}/releases/latest/download/latest.json"


def test_release_workflow_produces_what_the_endpoint_serves() -> None:
    """The endpoint promises latest.json beside a signed installer; the
    release workflow is the only thing that puts them there. If someone
    edits the workflow and drops the signing env or the upload, installed
    apps poll an endpoint that never updates again — silently."""
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "TAURI_SIGNING_PRIVATE_KEY" in workflow
    assert "latest.json" in workflow
    assert "gh release upload" in workflow
    assert '{"bundle":{"createUpdaterArtifacts":true}}' in workflow


def test_privacy_md_names_the_update_check_and_the_off_switch() -> None:
    """T-17's rule: a network call nobody documents is a lie by omission.
    The launch check is the app's only background call, so PRIVACY.md must
    name it AND say it can be switched off — the switch is what makes it
    a choice rather than a disclosure."""
    notice = (REPO / "PRIVACY.md").read_text(encoding="utf-8")
    assert "update check" in notice
    assert "switch it off" in notice
