"""captions/font_metrics.py: the numbers the story card lays its text out
with — read from the bundled faces' own tables and scaled the way libass
scales an ASS font size — and the wrap and fit rules on top of them. The
card's tests (test_stories.py) check what the card does with these; this
file checks the numbers themselves against the font files, so a wrong
reading of a table fails here and not as a card that quietly runs into
its own bottom row."""

from __future__ import annotations

import struct

import pytest

from publikclip_pipeline.captions import ass as ass_mod
from publikclip_pipeline.captions import font_metrics as fm


def test_the_bundled_faces_read_and_scale_the_way_libass_sizes_them():
    """An ASS size is the face's win height, and a line advances by
    exactly the size in every face; what differs is the em. Inter's win
    height equals its hhea height at 1.21 em; the two display faces
    declare taller win boxes, so the same size draws them at a smaller em
    — the numbers a hand probe of the tables gives, and the ones libass's
    ass_face_set_size derives."""
    inter = fm.load("Inter-Bold.ttf")
    assert inter.real and inter.units_per_em == 2048 and inter.win_height == inter.hhea_height == 2478
    assert inter.pitch(54) == pytest.approx(54) and inter.unit_px(54) == pytest.approx(54 / 2478)
    archivo = fm.load("ArchivoBlack-Regular.ttf")
    assert archivo.real and archivo.units_per_em == 1000 and archivo.win_height == 1347
    assert archivo.pitch(54) == pytest.approx(54) and archivo.unit_px(54) == pytest.approx(54 / 1347)
    anton = fm.load("Anton-Regular.ttf")
    assert anton.real and anton.win_height == 3550 and anton.pitch(54) == pytest.approx(54)
    assert anton.unit_px(54) == pytest.approx(54 / 3550)
    # the em at one size: Inter's the largest, Anton's the smallest (and narrowest)
    assert inter.unit_px(54) * 2048 > archivo.unit_px(54) * 1000 > anton.unit_px(54) * 2048
    for face in (inter, archivo, anton):
        assert 0x2026 in face.cmap                            # the ellipsis is a real glyph in every face
        assert face.width("", 54) == 0.0
        assert 0 < face.width("i", 54) < face.width("W", 54)   # a real advance table, not an average
        assert face.width("ab", 54) == pytest.approx(face.width("a", 54) + face.width("b", 54))
        assert face.width("ab", 108) == pytest.approx(2 * face.width("ab", 54))
    # Inter carries a format 12 cmap and Anton a format 4: both map Latin
    assert inter.width("The chair", 54) > 0 and anton.width("The chair", 54) > 0
    # a character the face lacks still advances — by the wide guess, never zero
    assert inter.advance("\U0001F600") == round(fm.FALLBACK_ADVANCE_EM * 2048)
    # one read per file name, and a preset resolves to its file
    assert fm.load("Inter-Bold.ttf") is inter
    assert fm.for_preset(ass_mod.resolve_preset("classic")) is inter
    assert fm.for_preset(ass_mod.resolve_preset("story")) is archivo


def test_an_unreadable_face_degrades_to_the_estimate_not_a_crash(tmp_path, monkeypatch):
    """§5.9: a preset whose font_file is missing, or a file that is not a
    TrueType font, measures with a generic wide face — the card then ends
    a line early rather than the job failing at its last stage."""
    assert fm.load("no-such-face.ttf") is fm.FALLBACK
    assert fm.FALLBACK.real is False and fm.FALLBACK.pitch(54) == pytest.approx(54)
    assert fm.FALLBACK.width("x", 54) == pytest.approx(0.65 * 45)   # 0.65 em at a 45 px em (1.2 em win box)
    junk = tmp_path / "junk.ttf"
    junk.write_bytes(b"\x00\x01\x00\x00" + b"\xff" * 40)
    with pytest.raises((ValueError, KeyError, struct.error)):
        fm.read(junk)
    monkeypatch.setattr(ass_mod, "FONTS_DIR", tmp_path)
    fm.load.cache_clear()
    try:
        assert fm.load("junk.ttf") is fm.FALLBACK
        assert fm.load("") is fm.FALLBACK
    finally:
        fm.load.cache_clear()


def test_wrap_is_first_fit_and_never_wider_than_the_line():
    face = fm.load("Inter-Bold.ttf")
    text = "Nobody had moved the chair. We had not touched it for eleven years."
    lines = [fm._join(line) for line in fm.wrap(face, 54, text, 400)]
    assert " ".join(lines).split() == text.split()
    assert len(lines) > 2 and all(face.width(line, 54) <= 400 for line in lines)
    # first fit: the word that starts a line would not have fitted on the one before
    space = face.width(" ", 54)
    for prev, nxt in zip(lines, lines[1:]):
        assert face.width(prev, 54) + space + face.width(nxt.split()[0], 54) > 400
    assert fm.wrap(face, 54, "   ", 400) == []
    # a word wider than a line is split into pieces, every piece but the last marked cut
    lines = fm.wrap(face, 54, "tiny Supercalifragilisticexpialidociousness end", 300)
    flat = [token for line in lines for token in line]
    assert flat[0].text == "tiny" and flat[-1].text == "end" and not flat[0].cut and not flat[-1].cut
    pieces = [token for token in flat if token.text not in ("tiny", "end")]
    assert len(pieces) >= 2 and all(p.cut for p in pieces[:-1]) and not pieces[-1].cut
    assert "".join(p.text for p in pieces) == "Supercalifragilisticexpialidociousness"
    assert all(face.width(fm._join(line), 54) <= 300 for line in lines)


def test_fit_cuts_at_a_word_with_an_ellipsis_that_itself_fits():
    face = fm.load("Inter-Bold.ttf")
    para = "Nobody had moved the chair, and every Sunday she dusted it before church."
    full, cut = fm.fit(face, 54, [para], 772, 10)
    assert not cut and " ".join(full).split() == para.split()
    lines, cut = fm.fit(face, 54, [para] * 5, 772, 3)
    assert cut and len(lines) == 3 and lines[-1].endswith("…")
    shown = " ".join(lines).rstrip("…").split()
    words = (" ".join([para] * 5)).split()
    assert shown[:-1] == words[:len(shown) - 1]
    assert words[len(shown) - 1].rstrip(".,;:") == shown[-1]     # a whole word; a trailing comma goes
    assert not lines[-1].endswith(",…") and not lines[-1].endswith(".…")
    assert all(face.width(line, 54) <= 772 for line in lines)
    # the ellipsis must fit too: a line that exactly fills the width loses a word to it
    exact = face.width("aaa bbb", 54)
    assert fm.fit(face, 54, ["aaa bbb ccc"], exact, 1) == (["aaa…"], True)
    # paragraphs each start a new line; no room means nothing, honestly
    assert fm.fit(face, 54, ["One.", "Two."], 772, 10) == (["One.", "Two."], False)
    assert fm.fit(face, 54, [para], 772, 0) == ([], True)
    assert fm.fit(face, 54, [], 772, 3) == ([], False)
    # the cut never lands inside a split word: the word goes, the ellipsis follows the one before it
    lines, cut = fm.fit(face, 54, ["short Supercalifragilisticexpialidociousnessagainandagain tail"], 300, 2)
    assert cut and lines == ["short…"]
    # and a story that is one unbreakable word wider than the room shows nothing rather than a piece
    assert fm.fit(face, 54, ["Supercalifragilisticexpialidociousnessagainandagain"], 300, 1) == ([], True)
