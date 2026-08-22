"""Instagram OAuth entry-point tests.

Meta's App Dashboard rejects `http://localhost/...` for Business Login, which
broke the only way this app could connect: the callback server listens on
plain http, so a compliant https redirect can never reach it. The flow now
has to survive a redirect it cannot catch, which means the code arrives by
hand — and everything here is about that path being forgiving enough to work
on the first try.
"""

import pytest

from publikclip_pipeline.insights import instagram as ig


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIKCLIP_HOME", str(tmp_path / "home"))
    yield


# ---------------------------------------------------------------------------
# Redirect URI


def test_default_redirect_is_https():
    """http:// is what Meta refuses to save, so it cannot be the default."""
    assert ig.redirect_uri().startswith("https://")


def test_override_wins_over_everything():
    assert ig.redirect_uri("https://example.com/cb") == "https://example.com/cb"


def test_override_is_trimmed():
    """People paste from the dashboard and bring whitespace with them."""
    assert ig.redirect_uri("  https://example.com/cb  ") == "https://example.com/cb"


def test_blank_override_falls_back_to_the_default():
    assert ig.redirect_uri("   ") == ig.DEFAULT_REDIRECT_URI


def test_stored_redirect_is_reused():
    """Meta matches the redirect character for character, so the token
    exchange has to reuse the exact URI the code was issued against."""
    ig.save_connection({"app_id": "1", "redirect_uri": "https://saved.example/cb"})
    assert ig.redirect_uri() == "https://saved.example/cb"


def test_missing_connection_file_does_not_crash():
    assert ig.redirect_uri() == ig.DEFAULT_REDIRECT_URI


# ---------------------------------------------------------------------------
# Code extraction — the part a real person interacts with


@pytest.mark.parametrize(
    "pasted, expected",
    [
        # the whole address bar, which is what most people copy
        ("https://localhost:8137/callback?code=AQBabc123&state=xyz", "AQBabc123"),
        # Instagram appends #_ to the redirect
        ("https://localhost:8137/callback?code=AQBabc123#_", "AQBabc123"),
        # just the code, with the #_ still attached
        ("AQBabc123#_", "AQBabc123"),
        # just the code
        ("AQBabc123", "AQBabc123"),
        # stray whitespace and quotes from copying
        ('  "AQBabc123"  ', "AQBabc123"),
        # no scheme, because the browser hid it
        ("localhost:8137/callback?code=AQBabc123&state=x", "AQBabc123"),
        # codes contain - and _
        ("https://x/cb?code=AQB_with-dashes_123&state=x", "AQB_with-dashes_123"),
        # a custom hosted redirect
        ("https://example.com/ig?code=AQBabc123", "AQBabc123"),
    ],
)
def test_extract_code_handles_what_people_paste(pasted, expected):
    assert ig.extract_code(pasted) == expected


def test_extract_code_returns_empty_for_nothing_usable():
    for junk in ("", "   ", None):
        assert ig.extract_code(junk) == ""


def test_error_url_without_a_code_yields_nothing():
    """A denied authorization redirects with error=, not code= — that must
    not be mistaken for a code."""
    assert ig.extract_code("https://localhost:8137/callback?error=access_denied") != "AQB"


# ---------------------------------------------------------------------------
# Auth URL


def test_auth_url_carries_the_redirect_and_state():
    url = ig.auth_url("12345", "state-token", "https://example.com/cb")
    assert "client_id=12345" in url
    assert "state=state-token" in url
    assert "example.com" in url
    assert url.startswith(ig.AUTH_URL)


def test_auth_url_requests_the_scopes_the_loop_needs():
    url = ig.auth_url("1", "s")
    assert "instagram_business_basic" in url
    assert "instagram_business_manage_insights" in url


def test_connect_rejects_an_unusable_paste_before_calling_meta():
    """A blank paste must fail locally with a readable message rather than
    burning a round trip and returning Meta's generic error."""
    with pytest.raises(ig.IgError) as excinfo:
        ig.connect("1", "secret", open_browser=False, code="   ")
    assert "code" in str(excinfo.value).lower()
