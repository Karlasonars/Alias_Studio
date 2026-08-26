"""The house rules from CLAUDE.md, as tests that fail.

Every rule in here failed silently in the past: the code ran, the suite was
green, and a setting quietly did nothing. Documentation did not stop that from
happening three separate times, so the rules live here instead.

Two of these are RATCHETS. The codebase carries known violations that predate
the rule; the test pins the current count so it can only go down. Lowering a
baseline is a good commit. Raising one is never correct — if a change needs a
higher baseline, the change is wrong, not the baseline.

Read `CLAUDE.md` §5 before editing anything in this file.
"""

from __future__ import annotations

import ast
import re
from dataclasses import fields
from pathlib import Path

import pytest

from publikclip_pipeline.camera.director import _resolve_content_box
from publikclip_pipeline.edits.timeline import ClipEdit

PKG = Path(__file__).resolve().parents[1] / "publikclip_pipeline"
REPO = Path(__file__).resolve().parents[2]
APP_SRC = REPO / "app" / "src"

#: Vendored upstream code. Not ours; excluded from every rule here.
VENDOR = PKG / "vendor"


def _our_py_files() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if VENDOR not in p.parents and p != VENDOR)


# --------------------------------------------------------------------------
# 5.3 — UTF-8, explicitly, everywhere
# --------------------------------------------------------------------------

#: Ratchet. A `±` in a score once corrupted score.json under cp1252 and Rust's
#: read failed silently. PYTHONUTF8=1 in quiet_command hides this in the desktop
#: app but NOT in CLI use. Lower this number; never raise it.
#:
#: Swept to zero in T-06. At zero the two tests below stop being a ratchet and
#: become a plain rule: any new `read_text`/`write_text` without an encoding
#: fails the suite. Note the guard still cannot see `open()` — see CLAUDE.md
#: §5.3, which is the rule this number only partly enforces.
TEXT_IO_WITHOUT_ENCODING_BASELINE = 0

_TEXT_IO = re.compile(r"\.(read_text|write_text)\s*\(")


def _text_io_violations() -> list[str]:
    out: list[str] = []
    for path in _our_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _TEXT_IO.search(line) and "encoding=" not in line:
                out.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")
    return out


def test_no_text_io_without_encoding() -> None:
    violations = _text_io_violations()
    assert len(violations) <= TEXT_IO_WITHOUT_ENCODING_BASELINE, (
        f"{len(violations)} text-IO calls lack encoding='utf-8' "
        f"(baseline {TEXT_IO_WITHOUT_ENCODING_BASELINE}). New ones:\n  "
        + "\n  ".join(violations)
    )


def test_encoding_baseline_is_not_stale() -> None:
    """When the count drops, lower the baseline in the same commit — otherwise
    the ratchet stops protecting the ground that was just won."""
    violations = _text_io_violations()
    assert len(violations) == TEXT_IO_WITHOUT_ENCODING_BASELINE, (
        f"Down to {len(violations)} violations. Set "
        f"TEXT_IO_WITHOUT_ENCODING_BASELINE = {len(violations)}."
    )


# --------------------------------------------------------------------------
# 5.1 — the four-place law: a ClipEdit field must reach a fingerprint
# --------------------------------------------------------------------------

#: Fields that genuinely do not change any stage's output, with the reason.
#: Adding to this set is a real decision — it means "no re-render can ever be
#: needed for this" — so it needs a reason, not just an entry.
CLIP_EDIT_RENDER_IRRELEVANT = {
    "start": "structural: handled by _has_structural_edits(), and in the render fingerprint",
    "end": "structural: as above",
    "title": "publishing copy; never reaches the video",
    "title_variants": "publishing copy",
    "description": "publishing copy",
    "description_meta": "publishing copy",
    "overlays": "structural: the editor's own render is kept, not overwritten",
    "pacing": "structural: only applies on the single-clip path, which owns its output",
}

#: Mirrors render/stage.py:_clip_edits_fingerprint
RENDER_FINGERPRINT_FIELDS = {
    "start", "end", "caption_preset", "caption_overrides",
    "lufs_target", "true_peak_db", "letterbox_fill",
    "remove_dead_space", "disabled_cuts",
}

#: Mirrors camera/stage.py:_framing_fingerprint
CAMERA_FINGERPRINT_FIELDS = {"camera_mode", "gameplay_amount"}


def test_every_clip_edit_field_is_fingerprinted_or_exempt() -> None:
    """The one people forget. A field that reaches neither a fingerprint nor the
    exemption list silently does nothing on the next restyle."""
    known = RENDER_FINGERPRINT_FIELDS | CAMERA_FINGERPRINT_FIELDS | set(CLIP_EDIT_RENDER_IRRELEVANT)
    actual = {f.name for f in fields(ClipEdit)}
    unclassified = actual - known
    assert not unclassified, (
        f"New ClipEdit field(s) {sorted(unclassified)} reach no stage fingerprint.\n"
        "Pick one, in this commit:\n"
        "  (a) add it to render/stage.py:_clip_edits_fingerprint, or\n"
        "  (b) add it to camera/stage.py:_framing_fingerprint, or\n"
        "  (c) add it to CLIP_EDIT_RENDER_IRRELEVANT with the reason it cannot\n"
        "      change any rendered output.\n"
        "Skipping this is what makes a per-clip setting quietly do nothing."
    )


def test_fingerprint_mirrors_have_not_drifted() -> None:
    """This test file duplicates two sets that live in the stages. If a stage
    changes and this copy does not, the test above starts lying."""
    render_src = (PKG / "render" / "stage.py").read_text(encoding="utf-8")
    camera_src = (PKG / "camera" / "stage.py").read_text(encoding="utf-8")
    for field in RENDER_FINGERPRINT_FIELDS - {"start", "end"}:
        assert f'"{field}"' in render_src, (
            f"'{field}' is listed here but no longer appears in render/stage.py"
        )
    for field in CAMERA_FINGERPRINT_FIELDS:
        assert f'"{field}"' in camera_src, (
            f"'{field}' is listed here but no longer appears in camera/stage.py"
        )


# --------------------------------------------------------------------------
# 5.5 — 0.0 is legitimate and falsy
# --------------------------------------------------------------------------

_TRUTHY_GAMEPLAY = re.compile(
    r"if\s+(?:not\s+)?[\w.]*gameplay_amount\s*[):\n]"
)


def test_no_truthy_gameplay_amount_check() -> None:
    """`if args.gameplay_amount:` treats the tight-crop endpoint as unset, which
    silently ignores the user asking for 0.0. Always `is not None`."""
    violations: list[str] = []
    for path in _our_py_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if "gameplay_amount" not in stripped or "is not None" in stripped:
                continue
            if "is None" in stripped or "!= None" in stripped:
                continue
            if _TRUTHY_GAMEPLAY.search(stripped):
                violations.append(f"{path.relative_to(REPO)}:{lineno}: {stripped}")
    assert not violations, (
        "Truthy check on gameplay_amount — 0.0 is a legitimate value and falsy:\n  "
        + "\n  ".join(violations)
    )


# --------------------------------------------------------------------------
# 5.6 — the zero-regression guarantee
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "src_w,src_h",
    [(1920, 1080), (3840, 2160), (2560, 1440), (1280, 720)],
)
def test_framing_dial_zero_is_exact_landscape(src_w: int, src_h: int) -> None:
    """At 0.0 the dial must reproduce the original tight 9:16 crop to the pixel:
    full source height, height*9/16 width. Any change that moves this endpoint is
    a regression however good it looks elsewhere."""
    w, h = _resolve_content_box(0.0, src_w, src_h)
    assert h == float(src_h)
    assert w == float(src_h) * 9.0 / 16.0
    # ~31.6% of a 16:9 frame — the physical ceiling of a padding-free 9:16 crop.
    if abs(src_w / src_h - 16 / 9) < 1e-6:
        assert abs(w / src_w - 0.31640625) < 1e-9


def test_framing_dial_zero_is_exact_portrait() -> None:
    """Narrower-than-9:16 sources pillar-fit width instead, so height is the axis
    that grows. 0.0 must still be a no-op."""
    w, h = _resolve_content_box(0.0, 500, 1000)
    assert w == 500.0
    assert h == 500.0 * 16.0 / 9.0


def test_framing_dial_one_reveals_whole_frame() -> None:
    for src_w, src_h in [(1920, 1080), (500, 1000)]:
        w, h = _resolve_content_box(1.0, src_w, src_h)
        assert (w, h) == (float(src_w), float(src_h))


def test_framing_dial_is_monotonic() -> None:
    prev = _resolve_content_box(0.0, 1920, 1080)
    for step in range(1, 21):
        cur = _resolve_content_box(step / 20, 1920, 1080)
        assert cur[0] >= prev[0] and cur[1] >= prev[1]
        prev = cur


def test_framing_dial_clamps_out_of_range() -> None:
    assert _resolve_content_box(-5.0, 1920, 1080) == _resolve_content_box(0.0, 1920, 1080)
    assert _resolve_content_box(9.0, 1920, 1080) == _resolve_content_box(1.0, 1920, 1080)


# --------------------------------------------------------------------------
# 5.4 — every invoke() lives in api.ts
# --------------------------------------------------------------------------

#: Ratchet. 6 calls predate the rule: IgModal.tsx (3), KeyModal.tsx (3).
#: ClipEditor's 6 moved into api.ts in T-03. Lower this; never raise it.
INVOKE_OUTSIDE_API_BASELINE = 6

_INVOKE = re.compile(r"\binvoke\s*<[^>]*>\s*\(|\binvoke\s*\(")


def _invoke_violations() -> list[str]:
    if not APP_SRC.is_dir():  # pipeline checked out alone
        return []
    out: list[str] = []
    for path in sorted(APP_SRC.rglob("*.ts*")):
        if path.name == "api.ts":
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _INVOKE.search(line):
                out.append(f"{path.relative_to(REPO)}:{lineno}: {line.strip()}")
    return out


def test_invoke_baseline_is_not_stale() -> None:
    violations = _invoke_violations()
    if not violations and not APP_SRC.is_dir():
        pytest.skip("frontend not checked out")
    assert len(violations) == INVOKE_OUTSIDE_API_BASELINE, (
        f"Down to {len(violations)} direct invoke() calls. Set "
        f"INVOKE_OUTSIDE_API_BASELINE = {len(violations)}."
    )


def test_no_invoke_outside_api_ts() -> None:
    violations = _invoke_violations()
    assert len(violations) <= INVOKE_OUTSIDE_API_BASELINE, (
        f"{len(violations)} direct invoke() calls outside api.ts "
        f"(baseline {INVOKE_OUTSIDE_API_BASELINE}). api.ts is the single list of "
        "Tauri commands; add yours there.\n  " + "\n  ".join(violations)
    )


# --------------------------------------------------------------------------
# Model integrity — a truncated weight file must not be used
# --------------------------------------------------------------------------

#: Ratchet. Only the PANNs checkpoint is pinned today, and it is pinned because
#: a 514 MB truncated response came back from a URL whose correct file is
#: ~312 MB. The other five are exposed to exactly that failure.
UNPINNED_MODELS_BASELINE = 5


def _unpinned_models() -> list[str]:
    src = (PKG / "models" / "specs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    unpinned: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "ModelSpec"):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        sha = kwargs.get("sha256")
        pinned = isinstance(sha, ast.Constant) and isinstance(sha.value, str) and sha.value
        if not pinned:
            name = kwargs.get("filename") or kwargs.get("name")
            label = name.value if isinstance(name, ast.Constant) else "<unknown>"
            unpinned.append(str(label))
    return unpinned


def test_model_specs_pin_a_sha256() -> None:
    unpinned = _unpinned_models()
    assert len(unpinned) <= UNPINNED_MODELS_BASELINE, (
        f"{len(unpinned)} model specs have no sha256 "
        f"(baseline {UNPINNED_MODELS_BASELINE}): {unpinned}. "
        "An unverified weight file fails as a wrong answer, not as an error."
    )


def test_unpinned_model_baseline_is_not_stale() -> None:
    unpinned = _unpinned_models()
    assert len(unpinned) == UNPINNED_MODELS_BASELINE, (
        f"Down to {len(unpinned)} unpinned models ({unpinned}). Set "
        f"UNPINNED_MODELS_BASELINE = {len(unpinned)}."
    )


# --------------------------------------------------------------------------
# 5.2 — no decorative settings (companion to test_settings.py)
# --------------------------------------------------------------------------

def test_schema_fields_all_carry_help() -> None:
    """`help` is what tells the user whether a change is worth a re-render. A
    control without it is a knob with no label.

    CAPTION_FIELDS is checked too. It lives outside GROUPS, so iterating
    GROUPS alone left 15 user-facing fields unguarded — the same
    guard-narrower-than-the-rule shape as §5.3's `open()` hole. (T-22)
    """
    from publikclip_pipeline import settings_schema

    missing: list[str] = []
    for group in settings_schema.GROUPS:
        for field in group["fields"]:
            if not field.get("help", "").strip():
                missing.append(field["key"])
    for field in settings_schema.CAPTION_FIELDS:
        if not field.get("help", "").strip():
            missing.append(f"caption.{field['key']}")
    assert not missing, f"Settings fields with no help text: {missing}"


def test_schema_groups_declare_their_cost() -> None:
    """Groups tell the UI what a change re-runs. A group without a cost makes the
    app unable to warn honestly before an expensive edit."""
    from publikclip_pipeline import settings_schema

    missing = [g["key"] for g in settings_schema.GROUPS if not g.get("cost")]
    assert not missing, f"Settings groups with no cost declared: {missing}"
