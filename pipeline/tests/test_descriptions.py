"""Description engine tests.

Same contract as titles: the prompt asks, the filter guarantees. Every test
here feeds `finalize()` a deliberately non-compliant model answer, because
that is the case that matters — a well-behaved model needs no enforcement.
"""

from publikclip_pipeline import config
from publikclip_pipeline.copywriting import descriptions as desc


def _opts(**kw):
    return desc.DescriptionOptions(**{**config.DescriptionSettings().__dict__, **kw})


# ---------------------------------------------------------------------------
# Length


def test_overlong_description_is_trimmed_not_rejected():
    """A too-long caption is fixable, so it must be fixed — failing would
    leave the user with nothing to paste."""
    out = desc.finalize({"description": "word " * 200, "hashtags": []}, _opts(max_chars=100))
    assert len(out["description"]) <= 100
    assert any("trimmed" in w for w in out["warnings"])


def test_trim_never_cuts_mid_word():
    out = desc.finalize({"description": "alpha bravo charlie delta echo foxtrot", "hashtags": []},
                        _opts(max_chars=20))
    body = out["description"].rstrip("…").strip()
    assert all(w in "alpha bravo charlie delta echo foxtrot".split() for w in body.split())


def test_trim_prefers_a_sentence_end_when_one_is_near_the_limit():
    text = "A full first sentence that nearly fills it. " + "tail " * 50
    out = desc.finalize({"description": text, "hashtags": []}, _opts(max_chars=50))
    assert out["description"] == "A full first sentence that nearly fills it."


def test_trim_ignores_a_sentence_end_that_would_waste_the_budget():
    """Cutting at the first full stop is only right when it is close to the
    limit. An early one (here, 20 of 40 chars) would throw away half the
    caption, so the word-boundary trim wins instead."""
    text = "Short one. " + "tail " * 50
    out = desc.finalize({"description": text, "hashtags": []}, _opts(max_chars=40))
    assert len(out["description"]) > 25
    assert out["description"].endswith("…")


def test_short_description_is_flagged_but_kept():
    out = desc.finalize({"description": "Too short.", "hashtags": []}, _opts(min_chars=100))
    assert out["description"] == "Too short."
    assert any("minimum" in w for w in out["warnings"])


# ---------------------------------------------------------------------------
# Emoji


def test_emoji_removed_when_disabled():
    out = desc.finalize({"description": "A clean caption 🚀🔥 about a clip", "hashtags": []},
                        _opts(allow_emoji=False))
    assert "🚀" not in out["description"] and "🔥" not in out["description"]
    assert "removed emoji" in out["warnings"]


def test_emoji_kept_when_allowed():
    out = desc.finalize({"description": "A caption 🚀 about a clip", "hashtags": []},
                        _opts(allow_emoji=True))
    assert "🚀" in out["description"]


def test_non_latin_text_is_never_stripped_as_emoji():
    """The emoji filter must not eat other people's alphabets."""
    text = "Saruna par mākslīgo intelektu — цікаво, 面白い"
    out = desc.finalize({"description": text, "hashtags": []}, _opts(allow_emoji=False))
    for fragment in ("mākslīgo", "цікаво", "面白い"):
        assert fragment in out["description"]


# ---------------------------------------------------------------------------
# Hashtags


def test_hashtags_are_normalized_and_deduped():
    out = desc.finalize(
        {"description": "x" * 60, "hashtags": ["#Gaming", "gaming", "GAMING", "Valorant"]},
        _opts(hashtags=5),
    )
    assert out["hashtags"] == ["gaming", "valorant"]


def test_hashtag_count_is_capped():
    out = desc.finalize(
        {"description": "x" * 60, "hashtags": ["a", "b", "c", "d", "e", "f"]}, _opts(hashtags=2)
    )
    assert len(out["hashtags"]) == 2


def test_hashtags_disabled_returns_none_and_clean_text():
    out = desc.finalize({"description": "x" * 60, "hashtags": ["gaming"]}, _opts(hashtags=0))
    assert out["hashtags"] == []
    assert "#" not in out["full"]


def test_full_is_what_the_user_pastes():
    out = desc.finalize({"description": "A real caption about the clip.", "hashtags": ["a", "b"]},
                        _opts(hashtags=2, min_chars=5))
    assert out["full"].startswith("A real caption about the clip.")
    assert out["full"].endswith("#a #b")


def test_garbage_hashtags_do_not_crash():
    out = desc.finalize({"description": "x" * 60, "hashtags": [None, 5, "  ", "###", {"a": 1}]},
                        _opts(hashtags=3))
    assert all(t.isalnum() for t in out["hashtags"])


# ---------------------------------------------------------------------------
# Honesty


def test_clickbait_is_flagged():
    out = desc.finalize({"description": "You won't believe what happens in this clip at all.",
                         "hashtags": []}, _opts(forbid_clickbait=True))
    assert any("clickbait" in w for w in out["warnings"])


def test_clickbait_not_flagged_when_guard_is_off():
    out = desc.finalize({"description": "You won't believe what happens in this clip at all.",
                         "hashtags": []}, _opts(forbid_clickbait=False))
    assert not any("clickbait" in w for w in out["warnings"])


def test_prompt_always_forbids_inventing_facts():
    text = desc.prompt("transcript", "summary", _opts())
    assert "do not invent" in text.lower()


def test_prompt_states_the_active_constraints():
    text = desc.prompt("t", "s", _opts(max_chars=140, hashtags=2, include_cta=True,
                                       allow_emoji=False, keywords="valorant"))
    assert "140" in text
    assert "2 hashtags" in text
    assert "call to action" in text.lower()
    assert "do not use emoji" in text.lower()
    assert "valorant" in text


def test_prompt_passes_the_title_so_it_is_not_restated():
    text = desc.prompt("t", "s", _opts(), {"title": "The chosen title"})
    assert "The chosen title" in text


# ---------------------------------------------------------------------------
# End to end with a fake client


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate_json(self, prompt, schema):
        self.calls += 1
        return self.payload


def test_generate_returns_a_pasteable_result():
    client = _FakeClient(
        {"description": "A grounded description of what the clip actually contains.",
         "hashtags": ["clip", "demo"], "grounded_in": "what the clip contains"}
    )
    out = desc.generate(client, "transcript", "summary", _opts(hashtags=2))
    assert client.calls == 1
    assert out["full"].endswith("#clip #demo")
    assert out["grounded_in"] == "what the clip contains"
    assert out["options"]["hashtags"] == 2


def test_generate_survives_a_malformed_answer():
    out = desc.generate(_FakeClient({}), "t", "s", _opts())
    assert out["description"] == ""
    assert out["hashtags"] == []
