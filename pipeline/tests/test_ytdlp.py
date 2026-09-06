"""The yt-dlp failure message (T-44's neighbour, a defect fix): what the
user is told when the download fails, driven through `_run` with a fake
process so the watchdog and the exit code are under the test's control.

Two halves. The watchdog's kill used to be recognised by exit code, -9 or
-15 — POSIX signal numbers; on Windows `Popen.kill()` exits with 1, so the
one message that helps ("stalled … check your connection") was unreachable
on the platform the app ships to. And a failure without an ERROR: line
threw away everything yt-dlp had printed and reported a bare exit code.
"""

from __future__ import annotations

import io
import threading

import pytest

from publikclip_pipeline import errors
from publikclip_pipeline.ingest import ytdlp

SENTINEL_KEY = "AQ.SENTINEL-KEY-THAT-MUST-NEVER-SURFACE"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # redact() reads the key from the environment and secrets.json from
    # PUBLIKCLIP_HOME; neither may be the developer's real ones here
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PUBLIKCLIP_GEMINI_API_KEY", SENTINEL_KEY)
    yield


class FakeProc:
    """A yt-dlp that prints `stderr` and then either exits with `code` on
    its own or hangs silently until something kills it — at which point
    it exits with `code`, whatever the platform would have made that."""

    def __init__(self, code: int, stderr: str = "", *, hangs: bool = False):
        self.stdout = io.StringIO("")
        self.stderr = io.StringIO(stderr)
        self._code = code
        self._hangs = hangs
        self._killed = threading.Event()
        self.kill_calls = 0

    def kill(self) -> None:
        self.kill_calls += 1
        self._killed.set()

    def wait(self) -> int:
        if self._hangs:
            self._killed.wait(timeout=5)
        return self._code


def _run_with(monkeypatch, proc: FakeProc, timeout: float = 0.05) -> ytdlp.YtDlpError:
    monkeypatch.setattr(ytdlp.subprocess, "Popen", lambda *a, **kw: proc)
    with pytest.raises(ytdlp.YtDlpError) as exc:
        ytdlp._run(ytdlp.binary_path(), ["-J", "https://example.com/v"], inactivity_timeout=timeout)
    return exc.value


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(1, id="windows-kill-exits-1"),
        pytest.param(-9, id="posix-sigkill"),
        pytest.param(-15, id="posix-sigterm"),
    ],
)
def test_a_watchdog_kill_is_the_stalled_message_whatever_the_exit_code(monkeypatch, code):
    """The watchdog says it killed the process; the exit code is not
    consulted. Exit code 1 is the Windows case, and the one that used to
    read "yt-dlp exited with code 1"."""
    proc = FakeProc(code, hangs=True)
    err = _run_with(monkeypatch, proc)
    assert proc.kill_calls == 1
    assert str(err) == ytdlp.STALLED_MESSAGE
    assert errors.describe(err).code == "download-stalled"


def test_a_process_that_exits_on_its_own_is_never_called_stalled(monkeypatch):
    """The other side of knowing rather than inferring: an exit code the
    old test would have called a stall (-9) is not one when the watchdog
    did not fire. An empty stderr leaves the bare exit code."""
    proc = FakeProc(-9)
    err = _run_with(monkeypatch, proc, timeout=5.0)
    assert proc.kill_calls == 0
    assert str(err) == "yt-dlp exited with code -9"
    assert errors.describe(err).code == "download-failed"


def test_an_error_line_wins_over_the_stall_and_the_tail(monkeypatch):
    stderr = (
        "WARNING: something first\n"
        "ERROR: [youtube] abc123: Video unavailable. This video is private.\n"
        "Traceback (most recent call last):\n"
        "  File ... in run\n"
    )
    # ...over the stall: yt-dlp said why before the watchdog gave up
    err = _run_with(monkeypatch, FakeProc(1, stderr, hangs=True))
    assert str(err) == "Video unavailable. This video is private."
    # ...and over the tail of everything else it printed
    err = _run_with(monkeypatch, FakeProc(1, stderr), timeout=5.0)
    assert str(err) == "Video unavailable. This video is private."
    assert "Traceback" not in str(err) and "exited with code" not in str(err)
    assert errors.describe(err).code == "url-needs-login"


def test_a_failure_without_an_error_line_surfaces_the_stderr_tail(monkeypatch):
    """No ERROR: line, no stall: the last few non-empty lines ride the
    message, so the next failure is diagnosable without a debugging
    session — a handful of lines, not the 64 KB kept."""
    noise = "".join(f"[debug] line {i}\n" for i in range(200))
    stderr = noise + "\n\nTraceback (most recent call last):\n   \n  File \"x.py\", line 1\nKeyError: 'formats'\n"
    err = _run_with(monkeypatch, FakeProc(1, stderr), timeout=5.0)
    msg = str(err)
    assert msg.startswith("yt-dlp exited with code 1. Its last output: ")
    assert "KeyError: 'formats'" in msg and "Traceback (most recent call last):" in msg
    assert "[debug] line 0" not in msg and "[debug] line 190" not in msg
    assert msg.count(" | ") == ytdlp.STDERR_TAIL_LINES - 1
    assert ytdlp.stderr_tail("a\n\n b \n\nc\n", limit=2) == ["b", "c"]
    assert errors.describe(err).cause == msg


def test_the_surfaced_tail_is_redacted(monkeypatch):
    """§5.11: the tail is foreign text and may quote a request. A stored
    key and a key-shaped query parameter in stderr reach neither the
    exception text nor the user-facing cause errors.describe builds."""
    stderr = (
        f"[debug] GET https://example.com/api?key={SENTINEL_KEY}\n"
        "[debug] auth header AIzaSyD-FAKE-SHAPED-KEY-0123456789abcdef\n"
        "requests.exceptions.HTTPError: 403 Forbidden\n"
    )
    err = _run_with(monkeypatch, FakeProc(1, stderr), timeout=5.0)
    info = errors.describe(err, stage="ingest")
    for text in (str(err), info.cause, info.detail or ""):
        assert SENTINEL_KEY not in text
        assert "AIzaSyD-FAKE" not in text
    assert "403 Forbidden" in info.cause          # the reason survives
    assert "key=[redacted]" in info.cause         # the shape, not the value
