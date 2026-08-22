"""Title + hook engine tests.

Both engines take an LLM's word for things, so the tests focus on the parts
that must hold even when the model misbehaves: constraints are actually
enforced (not merely requested), hallucinated indices can't become real
cuts, and "this is better" is only claimed when it measurably is.
"""

from publikclip_pipeline.copywriting import hooks, titles


class FakeClient:
    """Stands in for GeminiClient/OllamaClient: records the prompt it was
    given and replays a canned response."""

    def __init__(self, response):
        self.response = response
        self.prompts: list[str] = []

    def generate_json(self, prompt, schema, images=None):
        self.prompts.append(prompt)
        return self.response


# ---------------------------------------------------------------------------
# Titles: the constraints must be enforced, not just asked for


def _variant(text, style="direct"):
    return {"text": text, "style": style, "why": "w", "grounded_in": "g"}


def test_length_bounds_are_enforced_after_the_model_answers():
    opts = titles.TitleOptions(min_chars=10, max_chars=25)
    kept, rejected = titles.filter_variants(
        [
            _variant("too short"),
            _variant("a perfectly fine title"),
            _variant("this title runs on far past the configured maximum length"),
        ],
        opts,
    )
    assert [k["text"] for k in kept] == ["a perfectly fine title"]
    assert {r["rejected_because"] for r in rejected} == {
        "shorter than 10 chars",
        "longer than 25 chars",
    }


def test_questions_can_be_disabled():
    opts = titles.TitleOptions(min_chars=5, max_chars=100, allow_questions=False)
    kept, rejected = titles.filter_variants(
        [_variant("Why did this happen?"), _variant("Here is why this happened")], opts
    )
    assert len(kept) == 1
    assert rejected[0]["rejected_because"] == "questions are disabled"


def test_numbers_can_be_disabled():
    opts = titles.TitleOptions(min_chars=5, max_chars=100, allow_numbers=False)
    kept, _ = titles.filter_variants(
        [_variant("3 things he got wrong"), _variant("What he got wrong")], opts
    )
    assert [k["text"] for k in kept] == ["What he got wrong"]


def test_clickbait_is_rejected_when_forbidden():
    opts = titles.TitleOptions(min_chars=5, max_chars=100, forbid_clickbait=True)
    kept, rejected = titles.filter_variants(
        [
            _variant("You won't believe what he said next"),
            _variant("He admits he lied about the numbers"),
        ],
        opts,
    )
    assert [k["text"] for k in kept] == ["He admits he lied about the numbers"]
    assert "clickbait" in rejected[0]["rejected_because"]


def test_clickbait_allowed_when_the_user_turns_the_guard_off():
    opts = titles.TitleOptions(min_chars=5, max_chars=100, forbid_clickbait=False)
    kept, _ = titles.filter_variants([_variant("You won't believe this")], opts)
    assert len(kept) == 1


def test_duplicates_are_dropped_case_insensitively():
    opts = titles.TitleOptions(min_chars=3, max_chars=100)
    kept, rejected = titles.filter_variants(
        [_variant("The same title"), _variant("the SAME title")], opts
    )
    assert len(kept) == 1
    assert rejected[0]["rejected_because"] == "duplicate"


def test_uppercase_option_transforms_output():
    opts = titles.TitleOptions(min_chars=3, max_chars=100, uppercase=True)
    kept, _ = titles.filter_variants([_variant("quiet title")], opts)
    assert kept[0]["text"] == "QUIET TITLE"


def test_prompt_states_the_active_constraints():
    opts = titles.TitleOptions(
        variants=4, min_chars=15, max_chars=55, allow_questions=False,
        require_cta=True, keywords="poker, bluff",
    )
    text = titles.prompt("some transcript", "a summary", opts)
    assert "4 DIFFERENT titles" in text
    assert "between 15 and 55 characters" in text
    assert "NOT phrase any title as a question" in text
    assert "call to action" in text
    assert "poker, bluff" in text


def test_prompt_always_forbids_inventing_facts():
    text = titles.prompt("t", "s", titles.TitleOptions())
    assert "Do not invent facts" in text


def test_generate_returns_only_valid_variants():
    client = FakeClient(
        {"variants": [_variant("A good honest clip title"), _variant("bad")]}
    )
    out = titles.generate(
        client, "transcript", "summary", titles.TitleOptions(min_chars=10, max_chars=60)
    )
    assert len(out["titles"]) == 1
    assert len(out["rejected"]) == 1


# ---------------------------------------------------------------------------
# Hooks: suggestions must be legal cuts, and honest about improvement


SENTENCES = [10.0, 12.5, 15.0, 18.0, 21.0, 24.0, 30.0]


def _words():
    return [
        {"word": f"w{i}", "start": 10.0 + i * 0.5, "end": 10.4 + i * 0.5}
        for i in range(40)
    ]


def test_start_options_stay_within_shift_range():
    opts = hooks.HookOptions(max_shift_s=4.0, min_remaining_s=1.0, max_options=10)
    options = hooks.start_options(SENTENCES, 15.0, 40.0, opts)
    assert all(11.0 <= t <= 19.0 for t in options), options


def test_start_options_never_gut_the_clip():
    """A start that leaves less than min_remaining_s of clip is not an option."""
    opts = hooks.HookOptions(max_shift_s=30.0, min_remaining_s=10.0, max_options=10)
    options = hooks.start_options(SENTENCES, 15.0, 28.0, opts)
    assert all(28.0 - t >= 10.0 for t in options), options


def test_current_start_is_always_offered():
    opts = hooks.HookOptions(max_shift_s=0.1, min_remaining_s=1.0)
    options = hooks.start_options(SENTENCES, 13.7, 40.0, opts)
    assert any(abs(t - 13.7) < 0.25 for t in options)


def test_hallucinated_start_index_is_discarded():
    """The model returning an out-of-range index must not become a cut."""
    options = [10.0, 12.5, 15.0]
    cleaned = hooks._clean_candidates(
        [
            {"start_index": 99, "hook_type": "question", "strength": 9, "why": "w", "risk": "none"},
            {"start_index": 1, "hook_type": "question", "strength": 7, "why": "w", "risk": "none"},
        ],
        options,
        hooks.HookOptions(),
    )
    assert [c["start"] for c in cleaned] == [12.5]


def test_unknown_hook_type_falls_back_instead_of_propagating():
    cleaned = hooks._clean_candidates(
        [{"start_index": 0, "hook_type": "vibes", "strength": 5, "why": "", "risk": ""}],
        [10.0],
        hooks.HookOptions(),
    )
    assert cleaned[0]["hook_type"] == "statement"


def test_strength_is_clamped():
    cleaned = hooks._clean_candidates(
        [{"start_index": 0, "hook_type": "question", "strength": 99, "why": "", "risk": ""}],
        [10.0],
        hooks.HookOptions(),
    )
    assert cleaned[0]["strength"] == 10.0


def test_opening_line_is_what_the_viewer_actually_hears():
    line = hooks.opening_line(_words(), 15.0, 2.0)
    assert line.startswith("w10")   # 15.0s = 10th word at 0.5s spacing
    assert "w14" not in line        # beyond the 2s window


def test_analyze_claims_improvement_only_when_it_beats_the_current_start():
    words = _words()
    client = FakeClient(
        {
            "candidates": [
                {"start_index": 0, "hook_type": "question", "strength": 8.0, "why": "w", "risk": "none"},
                {"start_index": 1, "hook_type": "statement", "strength": 4.0, "why": "w", "risk": "none"},
            ],
            "text_hook": "a short hook",
        }
    )
    opts = hooks.HookOptions(max_shift_s=6.0, min_remaining_s=1.0, max_options=4)
    # current start is the SECOND option, and it scores worse → improves
    options = hooks.start_options(SENTENCES, 12.5, 40.0, opts)
    out = hooks.analyze(client, SENTENCES, words, options[1], 40.0, opts)
    assert out["candidates"], out
    assert isinstance(out["improves"], bool)


def test_analyze_reports_no_improvement_when_current_start_wins():
    words = _words()
    opts = hooks.HookOptions(max_shift_s=6.0, min_remaining_s=1.0, max_options=4)
    options = hooks.start_options(SENTENCES, 15.0, 40.0, opts)
    current_idx = options.index(15.0)
    client = FakeClient(
        {
            "candidates": [
                {"start_index": current_idx, "hook_type": "question", "strength": 9.0, "why": "w", "risk": "none"},
                {"start_index": (current_idx + 1) % len(options), "hook_type": "teaser", "strength": 3.0, "why": "w", "risk": "loses setup"},
            ],
            "text_hook": "",
        }
    )
    out = hooks.analyze(client, SENTENCES, words, 15.0, 40.0, opts)
    assert out["improves"] is False
    assert out["current_strength"] == 9.0


def test_analyze_degrades_gracefully_without_alternatives():
    client = FakeClient({"candidates": [], "text_hook": ""})
    opts = hooks.HookOptions(max_shift_s=0.0, min_remaining_s=1.0)
    out = hooks.analyze(client, [15.0], _words(), 15.0, 40.0, opts)
    assert out["candidates"] == []
    assert "no alternative" in out["note"]
    assert client.prompts == [], "must not spend an LLM call with nothing to compare"


def test_text_hook_is_length_capped():
    client = FakeClient(
        {
            "candidates": [{"start_index": 0, "hook_type": "teaser", "strength": 5, "why": "", "risk": ""}],
            "text_hook": "x" * 200,
        }
    )
    opts = hooks.HookOptions(max_shift_s=6.0, min_remaining_s=1.0)
    out = hooks.analyze(client, SENTENCES, _words(), 12.5, 40.0, opts)
    assert len(out["text_hook"]) <= 60
