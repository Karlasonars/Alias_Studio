"""Guard: no secret may reach a log line, a JSONL event, or an exception
message.

The incident this pins: a Gemini 503 surfaced the full request URL in the
app's live log - key included - because httpx embeds the request URL in its
error messages and the key was a query parameter. scoring/stage.py emits
LlmError text straight into the JSONL stream the app renders, so a secret
in the URL is a secret on screen. The fix is that the key travels in the
x-goog-api-key header and is never part of the URL, plus a redaction belt
on the error text itself.

The fake httpx.post below builds the SAME httpx.Request the real call
would (params become part of the URL at request construction), so these
tests exercise the genuine leak mechanism: with the key back in `params`,
the URL contains it, httpx's error text quotes it, and the assertions fail.
"""

import httpx
import pytest

from publikclip_pipeline.edits import visuals
from publikclip_pipeline.scoring import llm

SENTINEL_KEY = "AQ.SENTINEL-KEY-THAT-MUST-NEVER-SURFACE"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PUBLIKCLIP_GEMINI_API_KEY", SENTINEL_KEY)
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    yield


def _unavailable_post(captured):
    def post(url, *, params=None, headers=None, json=None, timeout=None):
        req = httpx.Request("POST", url, params=params, headers=headers)
        captured.append(req)
        return httpx.Response(503, request=req)

    return post


def test_gemini_error_text_never_contains_the_key(monkeypatch):
    captured: list[httpx.Request] = []
    monkeypatch.setattr(llm.httpx, "post", _unavailable_post(captured))
    client = llm.GeminiClient()
    with pytest.raises(llm.LlmError) as exc:
        client.generate_json("prompt", {"type": "object"})
    # the message that scoring/stage.py emits into the JSONL stream
    assert SENTINEL_KEY not in str(exc.value)
    # the key never entered a URL in the first place
    assert captured, "the client never issued a request"
    assert all(SENTINEL_KEY not in str(req.url) for req in captured)
    # and auth was still sent - the key rides the header instead
    assert all(req.headers.get("x-goog-api-key") == SENTINEL_KEY for req in captured)


def test_redaction_belt_strips_a_key_that_reaches_error_text(monkeypatch):
    # Even if some future layer folds the key into the error text (httpx
    # quoting a URL, a proxy echoing the request), the LlmError message
    # must not carry it.
    def post_raising_key_bearing_error(url, **kwargs):
        raise httpx.ConnectError(
            f"proxy refused https://example.com/v1?key={SENTINEL_KEY}"
        )

    monkeypatch.setattr(llm.httpx, "post", post_raising_key_bearing_error)
    client = llm.GeminiClient()
    with pytest.raises(llm.LlmError) as exc:
        client.generate_json("prompt", {"type": "object"})
    assert SENTINEL_KEY not in str(exc.value)


def test_gemini_image_fetch_keeps_the_key_out_of_the_url(monkeypatch, tmp_path):
    captured: list[httpx.Request] = []
    monkeypatch.setattr(visuals.httpx, "post", _unavailable_post(captured))
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    # errors are swallowed here (degrade to no overlay), so the observable
    # is the request itself: the key must be in the header, not the URL
    assert visuals.fetch_gemini("a query", job_dir) is None
    assert captured, "fetch_gemini never issued a request"
    assert all(SENTINEL_KEY not in str(req.url) for req in captured)
    assert all(req.headers.get("x-goog-api-key") == SENTINEL_KEY for req in captured)
