"""UI schema for the settings tree.

The settings panel is generated from this file, not hand-written in the
frontend. One source of truth means a new knob shows up in the UI with the
right control, range and explanation the moment it's added here — and a knob
that is removed can't leave a ghost control behind.

Every entry must correspond to a real field on `config.Settings` (or on
`captions.ass.Preset`). `validate_schema()` asserts exactly that and runs in
the test suite, so a typo here is a failing test rather than a dead control
in the panel.

Field contract
--------------
key    dotted path into Settings.to_json(), e.g. "clips.min_len"
type   number | bool | select | color | text
help   what it does AND what changing it costs — the user is deciding whether
       a re-render is worth it, so "reruns scoring" belongs in the text.
"""

from __future__ import annotations

from typing import Any

from . import config

# Which stages a group invalidates, so the UI can warn honestly about cost
# before the user changes something expensive.
COST_CHEAP = "cheap"        # re-render only (ffmpeg per clip)
COST_MODERATE = "moderate"  # re-direct camera + re-render
COST_EXPENSIVE = "high"     # rescore / re-pick moments (LLM + full re-render)


GROUPS: list[dict[str, Any]] = [
    {
        "key": "clips",
        "label": "Clips",
        "help": "Which moments become clips, and how long they are.",
        "cost": COST_EXPENSIVE,
        "cost_note": "Changing these re-picks candidate moments and rescores them.",
        "fields": [
            {
                "key": "clips.target_len", "label": "Target length", "type": "number",
                "min": 5, "max": 180, "step": 1, "unit": "s",
                "help": "The length windows are grown toward before snapping to sentence boundaries. The single biggest lever on clip pacing.",
            },
            {
                "key": "clips.min_len", "label": "Minimum length", "type": "number",
                "min": 3, "max": 120, "step": 1, "unit": "s",
                "help": "Windows shorter than this are discarded rather than shipped as fragments.",
            },
            {
                "key": "clips.max_len", "label": "Maximum length", "type": "number",
                "min": 10, "max": 300, "step": 1, "unit": "s",
                "help": "Windows longer than this are contracted back to an earlier sentence end.",
            },
            {
                "key": "clips.select_count", "label": "Clips to render", "type": "number",
                "min": 1, "max": 40, "step": 1,
                "help": "How many top-ranked candidates get the expensive visual pass and a finished render. Higher = more output, more time and more LLM spend.",
            },
            {
                "key": "clips.min_words", "label": "Minimum spoken words", "type": "number",
                "min": 0, "max": 100, "step": 1,
                "help": "Candidates with fewer words are skipped before any scoring. Keeps silent filler out of talking clips — but set it low (or 0) for gameplay and action content, where great moments can be nearly wordless.",
            },
            {
                "key": "clips.max_candidates", "label": "Candidate pool", "type": "number",
                "min": 5, "max": 120, "step": 1,
                "help": "How many candidate moments survive dedupe and reach scoring. A bigger pool finds more, and costs one LLM call per candidate.",
            },
            {
                "key": "clips.snap_radius", "label": "Sentence snap radius", "type": "number",
                "min": 0, "max": 20, "step": 0.5, "unit": "s",
                "help": "How far a clip edge may move to land on a sentence boundary instead of mid-word.",
            },
            {
                "key": "clips.dedupe_iou", "label": "Overlap dedupe", "type": "number",
                "min": 0.1, "max": 0.95, "step": 0.05,
                "help": "Two windows overlapping more than this are treated as the same moment and only the higher-scoring one survives. Lower = more aggressive deduplication.",
            },
            {
                "key": "clips.peak_min_distance_s", "label": "Peak spacing", "type": "number",
                "min": 1, "max": 120, "step": 1, "unit": "s",
                "help": "Interest-curve peaks closer together than this are suppressed, so candidates spread across the source instead of clustering.",
            },
        ],
    },
    {
        "key": "curve",
        "label": "Moment detection",
        "help": "How the free signals are weighed into 'is this moment interesting'. A channel that is missing for a video (no public replay heatmap, say) has its weight redistributed across the rest.",
        "cost": COST_EXPENSIVE,
        "cost_note": "Changing these re-picks candidate moments and rescores them.",
        "fields": [
            {"key": "curve.heatmap", "label": "Replay heatmap", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "Real viewer replays, when the source platform exposes them. The strongest signal available — but absent on most videos."},
            {"key": "curve.dynamics", "label": "Audio energy", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "How far loudness deviates from the local baseline. Catches shouting, sudden silence and emphasis."},
            {"key": "curve.events", "label": "Reactions", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "Density of detected laughter, gasps, applause and cheering."},
            {"key": "curve.turns", "label": "Conversation rate", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "How fast speakers trade turns. High values favour banter over monologue."},
            {"key": "curve.arousal", "label": "Vocal arousal", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "Speech-emotion intensity — excitement in the voice rather than volume."},
            {"key": "curve.scenes", "label": "Visual change", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "Shot-cut density. Raise it for edited or gameplay footage, where visual action carries the moment rather than speech."},
            {"key": "curve.lexical", "label": "Power words", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "Transcript keywords and numbers. Deliberately the weakest channel — it only nudges."},
        ],
    },
    {
        "key": "scoring",
        "label": "Scoring",
        "help": "How the AI's judgement and the free signals combine into the 0-100 score that ranks clips.",
        "cost": COST_EXPENSIVE,
        "cost_note": "Changing these rescores every clip (cached AI calls are reused, so it is cheaper than a first run).",
        "fields": [
            {"key": "scoring.t0_weight", "label": "Signal vs AI", "type": "number", "min": 0, "max": 1, "step": 0.05,
             "help": "How much of the pre-visual score comes from the measured interest curve rather than the AI's read of the transcript. Higher = trust the microphone over the model."},
            {"key": "scoring.text_weight", "label": "Text weight", "type": "number", "min": 0, "max": 1, "step": 0.05,
             "help": "Share of the final score from what is said, once the visual pass has run."},
            {"key": "scoring.visual_weight", "label": "Visual weight", "type": "number", "min": 0, "max": 1, "step": 0.05,
             "help": "Share of the final score from what is seen. Raise for visual content, lower for talking heads."},
        ],
        "matrix": {
            "key": "scoring.platform_weights",
            "label": "Platform priorities",
            "help": "What each platform's score rewards. These decide which clip ranks first for each destination.",
            "columns": ["hook", "funniness", "shock", "curiosity_gap", "value"],
            "column_help": {
                "hook": "Strength of the opening seconds.",
                "funniness": "How funny the moment is.",
                "shock": "Surprise or disbelief.",
                "curiosity_gap": "Leaves an open question the viewer wants closed.",
                "value": "Concrete usefulness or insight.",
            },
            "min": 0, "max": 1, "step": 0.01,
        },
    },
    {
        "key": "retention",
        "label": "Retention",
        "help": "Pattern interrupts — the automatic punch-in zooms fired by laughter, gasps, shouting and energy peaks. These exist to reset attention before it drifts.",
        "cost": COST_MODERATE,
        "cost_note": "Changing these re-directs the camera and re-renders.",
        "fields": [
            {"key": "retention.punch_zoom", "label": "Punch-in strength", "type": "number", "min": 1.0, "max": 1.6, "step": 0.01,
             "help": "Peak zoom of a punch-in. 1.00 disables the effect while leaving the detection intact; above ~1.25 reads as aggressive."},
            {"key": "retention.punch_seconds_per_punch", "label": "Seconds per punch-in", "type": "number", "min": 1, "max": 60, "step": 1, "unit": "s",
             "help": "Frequency cap: at most one punch-in per this many seconds of clip. Lower = more interrupts."},
            {"key": "retention.punch_min_spacing_s", "label": "Minimum spacing", "type": "number", "min": 0, "max": 30, "step": 0.5, "unit": "s",
             "help": "Never fire two punch-ins closer together than this, even if two reactions land back to back."},
            {"key": "retention.punch_rise_s", "label": "Zoom-in time", "type": "number", "min": 0.05, "max": 2.0, "step": 0.05, "unit": "s",
             "help": "How long the punch-in takes to reach full zoom. Short is snappy; long is cinematic."},
            {"key": "retention.punch_hold_s", "label": "Hold time", "type": "number", "min": 0.0, "max": 5.0, "step": 0.1, "unit": "s",
             "help": "How long the zoom stays at its peak before releasing."},
            {"key": "retention.punch_fall_s", "label": "Zoom-out time", "type": "number", "min": 0.05, "max": 3.0, "step": 0.05, "unit": "s",
             "help": "How long the zoom takes to release back to normal."},
        ],
    },
    {
        "key": "camera",
        "label": "Camera",
        "help": "How the 9:16 crop follows the action.",
        "cost": COST_MODERATE,
        "cost_note": "Changing these re-directs the camera and re-renders.",
        "fields": [
            {"key": "camera.gameplay_amount", "label": "Framing: podcast to gameplay", "type": "number", "min": 0, "max": 1, "step": 0.01,
             "help": "0 = tight crop that follows the speaker's face. 1 = the whole source frame, letterboxed. Use the high end for gameplay with a facecam, where a tight crop shows only the face and none of the game."},
            {"key": "camera.letterbox_fill", "label": "Letterbox bars", "type": "select",
             "options": [
                 {"value": "black", "label": "Black"},
                 {"value": "blur", "label": "Blurred video"},
             ],
             "help": "What fills the bars once the framing dial is wide enough to stop the crop filling the frame. Blurred repeats the same frame zoomed and blurred behind the image, so the bars carry the shot's colour instead of sitting dead — it costs an extra scale and a blur per frame."},
            {"key": "camera.speaker_change", "label": "On speaker change", "type": "select",
             "options": [
                 {"value": "cut", "label": "Hard cut"},
                 {"value": "pan", "label": "Eased pan"},
                 {"value": "locked", "label": "Locked"},
             ],
             "help": "How the camera moves between speakers. A cut has no motion-sickness cost; a pan is smoother but slower to arrive."},
            {"key": "camera.pan_duration_s", "label": "Pan duration", "type": "number", "min": 0.1, "max": 4.0, "step": 0.1, "unit": "s",
             "help": "How long an eased pan takes. Only applies in Eased pan / Locked mode."},
            {"key": "camera.deadzone_frac", "label": "Deadzone", "type": "number", "min": 0, "max": 0.5, "step": 0.01,
             "help": "Ignore subject movement smaller than this fraction of frame width, so the crop holds still instead of chasing small movements."},
            {"key": "camera.punch_in", "label": "Punch-ins enabled", "type": "bool",
             "help": "Master switch for reaction-triggered zooms. Turn off for a completely static camera."},
            {"key": "camera.punch_in_sensitivity", "label": "Punch-in sensitivity", "type": "number", "min": 0.2, "max": 3.0, "step": 0.1,
             "help": "How eagerly reactions and energy peaks trigger a punch-in. Higher fires on weaker signals."},
            {"key": "camera.zoom_lock_per_scene", "label": "Lock zoom per scene", "type": "bool",
             "help": "Keep zoom constant within a shot. Continuous zoom drift is the top motion-sickness trigger, so leave this on unless you want a floating look."},
        ],
    },
    {
        "key": "captions",
        "label": "Subtitles",
        "help": "Which caption style is used. Edit the style itself — font, colours, size, words per caption — in the Subtitle styles editor below.",
        "cost": COST_CHEAP,
        "cost_note": "Changing these re-renders (captions are burned into the video).",
        "fields": [
            {"key": "caption_preset", "label": "Style", "type": "select", "options_from": "presets",
             "help": "The caption style applied to every clip in a new job. Individual clips can override it in the clip editor."},
        ],
    },
    {
        "key": "performance",
        "label": "Performance",
        "help": "Speed/fidelity trades. The pipeline uses your GPU automatically wherever it can — these are the choices that are not automatic because they change the output slightly.",
        "cost": COST_EXPENSIVE,
        "cost_note": "Scene-detection changes re-pick moments; encoder changes re-render.",
        "fields": [
            {"key": "performance.fast_scene_detect", "label": "Fast scene detection", "type": "bool",
             "help": "Detect shot changes with ffmpeg instead of frame-by-frame Python. On an 81-minute source the slow path measured 48+ minutes — for a signal weighted 0.05. The cut list differs slightly; turn this off if you need the most precise boundaries."},
            {"key": "performance.scene_threshold", "label": "Scene sensitivity", "type": "number", "min": 0.05, "max": 0.9, "step": 0.05,
             "help": "How different two frames must be to count as a cut. Lower finds more cuts (including camera moves), higher only hard cuts."},
            {"key": "performance.scene_height", "label": "Detection height", "type": "number", "min": 90, "max": 720, "step": 30, "unit": "px",
             "help": "Frames are shrunk to this height before comparison. Smaller is faster and rarely changes which cuts are found."},
            {"key": "performance.hardware_encode", "label": "Hardware video encoding", "type": "bool",
             "help": "Encode finished clips with the GPU (NVENC / QuickSync) instead of x264. Much faster, but a different encoder means the file is not bit-identical to the x264 reference — quality is comparable, not the same. Off by default so renders never change without you asking."},
        ],
    },
    {
        "key": "ranking",
        "label": "Ranking video",
        "help": "Two vertical files beside the clips: the top moments play back to back under a numbered list that fills in as the viewer watches — moments 1 to N in the first video, the next N in the second. The same moments, the same framing and captions; the clips are rendered as always.",
        "cost": COST_CHEAP,
        "cost_note": "Changing these re-renders only. Selection, scoring and the camera pass are untouched.",
        "fields": [
            {"key": "ranking.enabled", "label": "Ranking videos", "type": "bool",
             "help": "On: the job produces its individual clips AND two ranking videos (one when there are not enough finalists for two — the log says why). Off: clips only, as before. Switching re-renders; nothing earlier re-runs."},
            {"key": "ranking.count", "label": "Moments per video", "type": "number", "min": 2, "max": 8, "step": 1,
             "help": "How many top-ranked moments one ranking video plays; the second video takes the next N, so two need 'Clips to render' at 2N or more. Independent of that setting — this only slices what scoring already ranked, so changing it re-renders and never rescores. Fewer than 8 fit comfortably above gameplay footage; above a podcast crop the list sits over the picture."},
        ],
    },
    {
        "key": "descriptions",
        "label": "Descriptions",
        "help": "The caption pasted under the video. Longer than the title and doing a different job: the context and searchable words the title had no room for.",
        "cost": COST_CHEAP,
        "cost_note": "Generated on demand per clip; never re-renders video.",
        "fields": [
            {"key": "descriptions.max_chars", "label": "Maximum length", "type": "number",
             "min": 60, "max": 2000, "step": 10,
             "help": "Anything longer is trimmed at a sentence or word boundary. Platforms truncate long captions in the feed, so the first line still has to carry it."},
            {"key": "descriptions.min_chars", "label": "Minimum length", "type": "number",
             "min": 0, "max": 500, "step": 10,
             "help": "Shorter results are kept but flagged, so a one-line answer doesn't slip through unnoticed."},
            {"key": "descriptions.hashtags", "label": "Hashtags", "type": "number",
             "min": 0, "max": 15, "step": 1,
             "help": "How many to append. 0 disables them. They are generated from what the clip actually contains — generic reach-bait like #fyp is explicitly discouraged."},
            {"key": "descriptions.tone", "label": "Tone", "type": "select",
             "options": [
                 {"value": "natural", "label": "Natural"},
                 {"value": "punchy", "label": "Punchy"},
                 {"value": "provocative", "label": "Provocative"},
                 {"value": "informative", "label": "Informative"},
             ],
             "help": "How the caption reads. Natural is the safe default; provocative leans harder without being allowed to overstate what happened."},
            {"key": "descriptions.include_cta", "label": "Call to action", "type": "bool",
             "help": "End with a short prompt to follow or comment. Off by default — it costs characters and reads as filler on a clip that doesn't earn it."},
            {"key": "descriptions.allow_emoji", "label": "Allow emoji", "type": "bool",
             "help": "When off, emoji are stripped after generation. Other alphabets are never touched."},
            {"key": "descriptions.forbid_clickbait", "label": "Block clickbait", "type": "bool",
             "help": "Rejects bait constructions ('you won't believe', 'wait for it'). Overselling costs the account its next impression, so this defaults on."},
            {"key": "descriptions.keywords", "label": "Keywords", "type": "text",
             "help": "Words to weave in where they fit naturally — for search. They are never forced in if they would read badly."},
        ],
    },
    {
        "key": "titles",
        "label": "Titles",
        "help": "Generated title options for each clip. Several are written per clip so you can compare framings rather than accept the first thing the model says.",
        "cost": COST_CHEAP,
        "cost_note": "Generated on demand per clip; never re-renders video.",
        "fields": [
            {"key": "titles.variants", "label": "Titles per clip", "type": "number", "min": 1, "max": 8, "step": 1,
             "help": "How many different titles to write. More options cost one slightly longer AI call, not more calls."},
            {"key": "titles.styles", "label": "Framings to use", "type": "multiselect",
             "options": [
                 {"value": "direct", "label": "direct"},
                 {"value": "curiosity", "label": "curiosity"},
                 {"value": "question", "label": "question"},
                 {"value": "quote", "label": "quote"},
                 {"value": "stakes", "label": "stakes"},
                 {"value": "contrast", "label": "contrast"},
                 {"value": "listicle", "label": "listicle"},
             ],
             "help": "Each framing opens the title differently — a quote leads with what was said, stakes with what was at risk. Pick several so the variants genuinely differ instead of rewording each other."},
            {"key": "titles.min_chars", "label": "Minimum length", "type": "number", "min": 5, "max": 120, "step": 1,
             "help": "Titles shorter than this are rejected after the model answers, not merely discouraged."},
            {"key": "titles.max_chars", "label": "Maximum length", "type": "number", "min": 20, "max": 200, "step": 1,
             "help": "Hard cap. Most platforms truncate well before 100 characters in feed."},
            {"key": "titles.tone", "label": "Tone", "type": "select",
             "options": [
                 {"value": "natural", "label": "natural"},
                 {"value": "punchy", "label": "punchy"},
                 {"value": "provocative", "label": "provocative"},
                 {"value": "informative", "label": "informative"},
             ],
             "help": "Overall voice. Provocative pushes harder on tension; informative leads with the substance."},
            {"key": "titles.keywords", "label": "Keywords", "type": "text",
             "help": "Words to work in where they fit naturally — a channel name, a game, a topic. They are never forced in if they would make the title read badly."},
            {"key": "titles.allow_questions", "label": "Allow questions", "type": "bool",
             "help": "Whether a title may be phrased as a question. Turn off if your feed already leans heavily on them."},
            {"key": "titles.allow_numbers", "label": "Allow numbers", "type": "bool",
             "help": "Whether digits may appear. Numbers raise specificity, which usually helps — unless the clip has no real count to give."},
            {"key": "titles.require_cta", "label": "Require call to action", "type": "bool",
             "help": "Append a short prompt to act. Useful for growth, but it costs characters and can read as pushy."},
            {"key": "titles.forbid_clickbait", "label": "Block clickbait phrasing", "type": "bool",
             "help": "Rejects 'you won't believe', 'this one trick' and similar formulas. Leave on: a title that oversells costs the account its next impression, which is exactly what the feedback loop measures."},
            {"key": "titles.uppercase", "label": "Uppercase", "type": "bool",
             "help": "Force capitals on the finished title."},
        ],
    },
    {
        "key": "hooks",
        "label": "Hooks",
        "help": "The opening seconds decide whether the rest is watched. The strongest lever here is WHERE the clip starts, so the engine proposes alternative start points — each snapped to a real sentence boundary, so every suggestion is a legal cut you can accept with one click.",
        "cost": COST_CHEAP,
        "cost_note": "Analysed on demand per clip; accepting a suggestion re-renders that one clip.",
        "fields": [
            {"key": "hooks.window_s", "label": "Hook window", "type": "number", "min": 1.0, "max": 10.0, "step": 0.5, "unit": "s",
             "help": "How much of the opening counts as 'the hook' when judging and comparing start points."},
            {"key": "hooks.max_shift_s", "label": "Search range", "type": "number", "min": 0.0, "max": 30.0, "step": 0.5, "unit": "s",
             "help": "How far before or after the current start the engine may look for a stronger opening. Wider finds more, but risks cutting away context the clip needs."},
            {"key": "hooks.min_remaining_s", "label": "Keep at least", "type": "number", "min": 2.0, "max": 60.0, "step": 1, "unit": "s",
             "help": "A start point that would leave less clip than this is never offered, so chasing a hook can't gut the payoff."},
            {"key": "hooks.max_options", "label": "Start points to weigh", "type": "number", "min": 2, "max": 12, "step": 1,
             "help": "How many candidate openings are compared. The current start is always included, so the engine can honestly answer 'leave it alone'."},
            {"key": "hooks.types", "label": "Hook types allowed", "type": "multiselect",
             "options": [
                 {"value": "question", "label": "question"},
                 {"value": "statement", "label": "bold statement"},
                 {"value": "surprising_fact", "label": "surprising fact"},
                 {"value": "conflict", "label": "conflict"},
                 {"value": "open_loop", "label": "open loop"},
                 {"value": "teaser", "label": "teaser"},
                 {"value": "in_medias_res", "label": "mid-action"},
                 {"value": "emotional", "label": "emotional"},
             ],
             "help": "Which shapes of opening the engine may propose. Restrict them if your channel has a consistent style."},
            {"key": "hooks.suggest_text_hook", "label": "Suggest on-screen hook text", "type": "bool",
             "help": "Also write a short line of text for the opening seconds, grounded in what is actually said."},
        ],
    },
    {
        "key": "pacing",
        "label": "Pacing",
        "help": "Dead-space removal in the clip editor — which silences get trimmed and which are left as timing.",
        "cost": COST_CHEAP,
        "cost_note": "Applies when you re-render a clip from the editor.",
        "fields": [
            {"key": "pacing.min_cut_gap", "label": "Shortest silence to cut", "type": "number", "min": 0.1, "max": 5.0, "step": 0.05, "unit": "s",
             "help": "Silences shorter than this are always kept. Lower = tighter, more aggressive edit."},
            {"key": "pacing.breath_pad", "label": "Breathing room", "type": "number", "min": 0.0, "max": 1.0, "step": 0.05, "unit": "s",
             "help": "Kept on each side of a trimmed silence so cuts don't clip the start of words."},
            {"key": "pacing.event_protect_s", "label": "Protect around reactions", "type": "number", "min": 0.0, "max": 6.0, "step": 0.1, "unit": "s",
             "help": "Pauses this close to laughter or a gasp are comedic timing and are never trimmed."},
            {"key": "pacing.natural_pause_max", "label": "Natural pause limit", "type": "number", "min": 0.0, "max": 4.0, "step": 0.1, "unit": "s",
             "help": "Pauses after a finished sentence up to this long read as normal cadence and are kept."},
            {"key": "pacing.min_keep_range", "label": "Shortest kept segment", "type": "number", "min": 0.1, "max": 3.0, "step": 0.05, "unit": "s",
             "help": "Never leave a surviving sliver shorter than this between two cuts."},
        ],
    },
    {
        "key": "audio",
        "label": "Audio",
        "help": "Loudness normalisation applied to every rendered clip.",
        "cost": COST_CHEAP,
        "cost_note": "Changing these re-renders.",
        "fields": [
            {"key": "lufs_target", "label": "Loudness target", "type": "number", "min": -30, "max": -8, "step": 0.5, "unit": "LUFS",
             "help": "Integrated loudness every clip is normalised to. -14 LUFS is the common short-form target; going louder risks platform-side turn-down."},
            {"key": "true_peak_db", "label": "True peak ceiling", "type": "number", "min": -6, "max": 0, "step": 0.1, "unit": "dB",
             "help": "Hard ceiling for peaks after normalisation, to avoid clipping on playback."},
        ],
    },
    {
        "key": "ai",
        "label": "AI",
        "help": "Which model judges the clips, and which optional detectors run.",
        "cost": COST_EXPENSIVE,
        "cost_note": "Changing the model rescores every clip.",
        "fields": [
            {"key": "llm_mode", "label": "Model", "type": "select",
             "options": [
                 {"value": "gemini", "label": "Gemini (your API key)"},
                 {"value": "ollama", "label": "Ollama (local, no key)"},
             ],
             "help": "Gemini also does the visual pass; Ollama is text-only and marks clips as local estimates."},
            {"key": "gemini_model", "label": "Gemini model", "type": "text",
             "help": "The exact Gemini model id used for scoring, e.g. gemini-3.6-flash. "
                     "Change it if Google retires the default — the app keeps working without an update. "
                     "Leave empty to use the built-in default."},
            {"key": "laughter_specialist", "label": "Laughter specialist", "type": "bool",
             "help": "Adds a second, higher-precision laughter detector. Substantially slower on long sources — worth it when laughter is the thing you cut on, since two agreeing detectors boost a clip's score."},
        ],
    },
]


# Caption preset fields, edited per preset rather than per job.
CAPTION_FIELDS: list[dict[str, Any]] = [
    {"key": "font", "label": "Font", "type": "select", "options_from": "fonts",
     "help": "Typeface. Only bundled fonts are listed — they ship with the app so renders are reproducible."},
    {"key": "size", "label": "Font size", "type": "number", "min": 20, "max": 200, "step": 2,
     "help": "Cap height in a 1080x1920 frame. Around 72-92 is typical for short form."},
    {"key": "primary", "label": "Word colour", "type": "color", "help": "Base colour of words that are not active or emphasised."},
    {"key": "active", "label": "Active word", "type": "color", "help": "The word being spoken right now — the karaoke highlight."},
    {"key": "emphasis", "label": "Emphasis colour", "type": "color", "help": "Words detected as emphasised: power words, numbers, and prosodic peaks."},
    {"key": "outline_color", "label": "Outline colour", "type": "color", "help": "Outline behind the text. Dark outlines keep captions readable over any footage."},
    {"key": "outline", "label": "Outline width", "type": "number", "min": 0, "max": 12, "step": 1,
     "help": "Thicker outlines survive busy backgrounds; too thick reads as a sticker."},
    {"key": "shadow", "label": "Shadow", "type": "number", "min": 0, "max": 8, "step": 1, "help": "Drop shadow depth. 0 disables it."},
    {"key": "margin_v", "label": "Distance from bottom", "type": "number", "min": 0, "max": 1400, "step": 10,
     "help": "Vertical position in a 1920-tall frame. Keep captions clear of platform UI at the very bottom — and, at high gameplay framing, clear of the letterbox bar."},
    {"key": "bold", "label": "Bold", "type": "bool", "help": "Synthetic bold. Fonts that are already heavy (Anton, Archivo Black) don't need it."},
    {"key": "uppercase", "label": "Uppercase", "type": "bool", "help": "Force capitals. Reads louder and fills the line more evenly."},
    {"key": "pop", "label": "Entrance pop", "type": "bool", "help": "Small scale-up animation as each caption appears. Adds motion without moving the text."},
    {"key": "max_words", "label": "Words per caption", "type": "number", "min": 1, "max": 12, "step": 1,
     "help": "How many words share one on-screen caption. Fewer words = faster turnover and a more urgent feel."},
    {"key": "pause_break", "label": "Pause break", "type": "number", "min": 0.1, "max": 3.0, "step": 0.05, "unit": "s",
     "help": "A pause longer than this forces a new caption even mid-sentence."},
    {"key": "event_tag_color", "label": "Reaction tag colour", "type": "color",
     "help": "Colour of bracketed tags like [laughs] shown for detected non-speech reactions."},
]


def _resolve(data: dict, dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node


def validate_schema() -> list[str]:
    """Every schema key must point at a real settings field, and every
    settings field should be reachable from the UI. Returns problems."""
    from .captions import ass as ass_mod

    problems: list[str] = []
    data = config.Settings().to_json()

    covered: set[str] = set()
    for group in GROUPS:
        for fielddef in group.get("fields", []):
            key = fielddef["key"]
            try:
                _resolve(data, key)
            except KeyError:
                problems.append(f"schema key has no settings field: {key}")
            covered.add(key)
        matrix = group.get("matrix")
        if matrix:
            try:
                _resolve(data, matrix["key"])
            except KeyError:
                problems.append(f"schema matrix has no settings field: {matrix['key']}")
            covered.add(matrix["key"])

    # Reverse check: a settings field nobody can reach from the panel is a
    # knob the user was promised but can't touch.
    def walk(node: dict, prefix: str = "") -> None:
        for key, value in node.items():
            path = f"{prefix}{key}"
            if path in covered:
                continue
            if isinstance(value, dict):
                walk(value, f"{path}.")
            else:
                problems.append(f"settings field missing from UI schema: {path}")

    walk({k: v for k, v in data.items() if k != "captions"})

    preset_fields = {f.name for f in __import__("dataclasses").fields(ass_mod.Preset)}
    for fielddef in CAPTION_FIELDS:
        if fielddef["key"] not in preset_fields:
            problems.append(f"caption schema key has no preset field: {fielddef['key']}")
    for name in preset_fields - {"name", "font_file"}:
        if name not in {f["key"] for f in CAPTION_FIELDS}:
            problems.append(f"preset field missing from UI schema: {name}")
    return problems


def schema_payload() -> dict:
    """Everything the settings panel needs to render itself."""
    from .captions import ass as ass_mod

    fonts = sorted({p.font for p in ass_mod.PRESETS.values()})
    return {
        "groups": GROUPS,
        "caption_fields": CAPTION_FIELDS,
        "fonts": fonts,
        "builtin_presets": {
            name: {
                **{k: v for k, v in preset.__dict__.items() if k != "name"},
            }
            for name, preset in ass_mod.PRESETS.items()
        },
    }
