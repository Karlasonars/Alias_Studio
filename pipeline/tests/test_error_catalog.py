"""E14-F01 / T-13: every known error class has a cause and an action, the
unknown path produces the designed shape (never a repr), and the choke
point in run_stages writes the described value — to the DB row as a human
cause, to error.json as the full structure."""

import json

import pytest

from publikclip_pipeline import config, errors
from publikclip_pipeline.ingest.ytdlp import YtDlpError
from publikclip_pipeline.jobs import queue
from publikclip_pipeline.scoring.llm import LlmError


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


# ---------------------------------------------------------------------------
# The catalogue itself


def test_every_entry_has_a_cause_and_at_least_one_action():
    for code, entry in errors.CATALOG.items():
        assert entry.cause.strip(), f"{code} has no cause"
        assert len(entry.actions) >= 1, f"{code} has no action"
        for text in (entry.cause, *entry.actions):
            assert "Traceback" not in text, f"{code} leaks a traceback into authored text"
            assert not text.startswith(("OSError", "RuntimeError", "ValueError")), (
                f"{code} starts with a Python exception name"
            )


def test_no_entry_authors_an_absolute_path_or_query_string():
    # This text is stored, bundled by T-15, and pasted into issues — it must
    # never carry a machine's paths or a credential-shaped query (§5.11).
    import re

    for code, entry in errors.CATALOG.items():
        for text in (entry.cause, *entry.actions):
            assert not re.search(r"[A-Za-z]:\\Users|/home/|/Users/", text), code
            assert not re.search(r"\?\w+=", text), code


def test_catalog_covers_every_spec20_row():
    # E14-F01: the catalogue covers at least SPECIFICATION §20's table.
    # SPEC20_CODES mirrors that table row by row; each must be an entry.
    assert len(errors.SPEC20_CODES) == 10  # the §20 table's row count
    for code in errors.SPEC20_CODES:
        assert code in errors.CATALOG, f"§20 row's code {code} missing from the catalogue"


# ---------------------------------------------------------------------------
# describe(): recognizers, the user-facing contract, and the unknown path


def test_a_coded_exception_names_its_entry_and_keeps_its_message():
    err = LlmError("Gemini rejected the API key. Check it in Settings.", code="gemini-key-rejected")
    info = errors.describe(err, stage="score")
    assert info.code == "gemini-key-rejected"
    # bucket A: the site's good message IS the cause; the entry adds actions
    assert info.cause == "Gemini rejected the API key. Check it in Settings."
    assert info.actions == list(errors.CATALOG["gemini-key-rejected"].actions)
    assert info.stage == "score"


def test_a_wrapping_stage_error_inherits_the_inner_code():
    inner = LlmError("no key", code="no-gemini-key")
    outer = queue.StageError("no key")
    outer.__cause__ = inner
    assert errors.describe(outer).code == "no-gemini-key"


def test_recognizers_name_mechanisms_without_site_edits():
    auth = YtDlpError("Sign in to confirm your age. This video may be inappropriate.")
    assert errors.describe(auth).code == "url-needs-login"
    assert errors.describe(YtDlpError("yt-dlp stalled (no output for a while) and was stopped.")).code == "download-stalled"
    assert errors.describe(OSError(28, "No space left on device")).code == "disk-full"
    assert errors.describe(MemoryError()).code == "out-of-memory"
    assert errors.describe(RuntimeError("Model download failed for panns: HTTP 503")).code == "model-download-failed"


def test_an_uncoded_stage_error_keeps_its_contract():
    # "Message is user-facing" — an uncoded site loses nothing: its text is
    # the cause and the generic actions apply.
    info = errors.describe(queue.StageError("Something specific went wrong."), stage="camera")
    assert info.code == "stage-error"
    assert info.cause == "Something specific went wrong."
    assert len(info.actions) >= 1


def test_the_unknown_path_names_the_stage_and_never_prints_python():
    # The twenty-first failure: the one nobody wrote a message for. This is
    # the exact shape that replaces OSError(22, 'Invalid argument') on a
    # user's screen (T-37 stays unknown — unreproduced means no guessed cause).
    info = errors.describe(OSError(22, "Invalid argument"), stage="score")
    assert info.code == "unknown"
    assert "score" in info.cause
    assert "OSError" not in info.cause and "(" not in info.cause.split("step")[0]
    assert "explanation" in info.cause  # claims nothing it does not know
    assert any("Resume" in a for a in info.actions)
    assert "OSError" in (info.detail or "")  # the repr lives ONLY here
    assert info.signature == "OSError errno 22"  # legible recurrence, no guessed cause


# ---------------------------------------------------------------------------
# The choke point: run_stages' two arms


class _UnknownFailure(queue.Stage):
    name = "boom"
    schema_version = 1

    def run(self, ctx):
        raise OSError(22, "Invalid argument")


class _KnownFailure(queue.Stage):
    name = "known"
    schema_version = 1

    def run(self, ctx):
        raise queue.StageError("The disk filled up mid-write.", code="disk-full")


def _job():
    return queue.create_job("file", "C:/x.mp4", json.dumps(config.Settings().to_json()))


def test_an_unknown_stage_failure_reaches_the_db_as_a_cause_not_a_repr():
    job = _job()
    with pytest.raises(OSError):
        queue.run_stages(job, [_UnknownFailure()], lambda *a: None)
    failed = queue.get_job(job.id)
    assert failed.status == "failed"
    assert "OSError(" not in failed.error  # the repr path is dead
    assert failed.error.startswith("boom: Something failed")
    payload = json.loads((job.dir / queue.ERROR_FILE).read_text(encoding="utf-8"))
    assert payload["code"] == "unknown"
    assert payload["stage"] == "boom"
    assert payload["signature"] == "OSError errno 22"
    assert "OSError" in payload["detail"]


def test_a_known_failure_writes_its_code_and_the_next_run_clears_the_file():
    job = _job()
    with pytest.raises(queue.StageError):
        queue.run_stages(job, [_KnownFailure()], lambda *a: None)
    error_file = job.dir / queue.ERROR_FILE
    assert json.loads(error_file.read_text(encoding="utf-8"))["code"] == "disk-full"
    # T-14 reads stage+code from this file BETWEEN failure and the next
    # spawn; run start clears it, exactly like the cancel flags — by then
    # the checkpoint contract, not this file, decides what re-runs.
    class Fine(queue.Stage):
        name = "fine"
        schema_version = 1

        def run(self, ctx):
            return {}

    queue.run_stages(job, [Fine()], lambda *a: None)
    assert not error_file.exists()
