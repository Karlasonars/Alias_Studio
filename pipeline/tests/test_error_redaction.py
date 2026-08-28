"""T-13's redaction guards — the same thinking as test_secret_leaks.py:
error text is now a structured, stored thing that T-15 will bundle and
users will paste into issues, so a key, a token, or the user's home
directory must not survive into ANY field of it. describe() is the only
constructor of the shape, and the excepthook redacts tracebacks at birth —
which is what keeps the Rust shell's stderr tail (its 'exited' event, the
one producer that never passes through describe()) clean without teaching
a second language the rule."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from publikclip_pipeline import config, errors

FAKE_KEY = "AIzaFAKEFAKEFAKEFAKEFAKEFAKEFAKE123"
FAKE_TOKEN = "IGQVJfaketokenfaketokenfaketoken"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir(parents=True, exist_ok=True)
    yield tmp_path / "home"


def test_stored_secrets_never_survive_into_any_field(isolated_home):
    (isolated_home / "secrets.json").write_text(
        json.dumps({"gemini_api_key": FAKE_KEY, "pexels_api_key": "px_" + "s" * 20}),
        encoding="utf-8",
    )
    (isolated_home / "instagram.json").write_text(
        json.dumps({"access_token": FAKE_TOKEN, "app_secret": "shh_" + "x" * 20}),
        encoding="utf-8",
    )
    err = RuntimeError(
        f"boom {FAKE_KEY} and {FAKE_TOKEN} and px_{'s' * 20} and shh_{'x' * 20}"
    )
    serialized = json.dumps(errors.describe(err, stage="score").to_json())
    for secret in (FAKE_KEY, FAKE_TOKEN, "px_" + "s" * 20, "shh_" + "x" * 20):
        assert secret not in serialized
    assert "[redacted]" in serialized


def test_key_shapes_and_query_credentials_are_scrubbed_even_when_not_stored():
    # The belt for secrets we never held literally — including §5.11's
    # known Instagram debt (T-32): ?access_token=… is HIDDEN here at the
    # display layer, not fixed at its call sites.
    err = RuntimeError(
        "GET https://graph.instagram.com/me?access_token=SECRETSECRET123 "
        f"then {FAKE_KEY} said no"
    )
    serialized = json.dumps(errors.describe(err).to_json())
    assert "SECRETSECRET123" not in serialized
    assert FAKE_KEY not in serialized


def test_the_home_directory_never_reaches_the_panel_intact():
    # A Windows traceback carries C:\Users\<name>\ on every frame; that is
    # the owner's username riding into every pasted issue.
    try:
        raise RuntimeError(f"could not open {Path.home() / 'publikclip' / 'x.mp4'}")
    except RuntimeError as err:
        info = errors.describe(err, stage="ingest")
    serialized = json.dumps(info.to_json())
    assert str(Path.home()) not in serialized
    assert Path.home().as_posix() not in serialized
    assert "~" in serialized


def test_unhandled_tracebacks_are_redacted_at_birth(isolated_home):
    # The excepthook is what the shell's stderr tail rides on: crash a real
    # interpreter with the hook installed and a home path in the message —
    # the tail Rust would capture must carry ~, never the real path. The
    # frame paths themselves ("File C:\Users\...") are covered by the same
    # replacement.
    script = (
        "from publikclip_pipeline import errors\n"
        "import pathlib\n"
        "errors.install_excepthook()\n"
        "raise RuntimeError('died at ' + str(pathlib.Path.home() / 'job' / 'media.mp4'))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode != 0
    assert "RuntimeError" in proc.stderr  # still a real, debuggable traceback
    assert str(Path.home()) not in proc.stderr
    assert Path.home().as_posix() not in proc.stderr
    assert "~" in proc.stderr


def test_the_cli_installs_the_hook():
    # Importing the CLI module is what arms the hook for every sidecar
    # process the shell ever spawns; if this import stops doing that, the
    # 'exited' tail regresses to raw tracebacks.
    import sys as _sys

    from publikclip_pipeline import cli  # noqa: F401 — the import IS the act

    hook = _sys.excepthook
    assert getattr(hook, "__module__", "") == "publikclip_pipeline.errors"
