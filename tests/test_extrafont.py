"""picogame_font.ExtraFont: BDF-subset fallback glyphs over terminalio.FONT."""
import _bootstrap  # noqa: F401
import os
import tempfile

import picogame as pg
import picogame_font
import terminalio

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "fonts")
CZ = os.path.join(FONTS, "picogame_cz.bdf")
SYM = os.path.join(FONTS, "picogame_symbols.bdf")


def _ink(font, ch):
    """Set of lit (x, y) pixels of one glyph cell."""
    fw, fh = font.get_bounding_box()[:2]
    flat = picogame_font._glyph_flat(font, ord(ch), fw, fh)
    return {(i % fw, i // fw) for i, v in enumerate(flat) if v}


def test_fallback_chain():
    f = picogame_font.ExtraFont(CZ, SYM)
    assert f.get_bounding_box() == terminalio.FONT.get_bounding_box()
    # ASCII comes from the builtin font (same sheet + tile)
    ga = f.get_glyph(ord("A"))
    gb = terminalio.FONT.get_glyph(ord("A"))
    assert ga.bitmap is gb.bitmap and ga.tile_index == gb.tile_index
    # diacritics + symbols come from the BDFs
    assert f.get_glyph(ord("č")) is not None
    assert f.get_glyph(0x2190) is not None          # <- arrow (symbols set)
    # still None for something in neither
    assert f.get_glyph(0x4E2D) is None


def test_glyph_pixels():
    f = picogame_font.ExtraFont(CZ)
    c_plain = _ink(f, "c")
    c_caron = _ink(f, "č")
    assert c_plain and c_caron
    # the caron adds ink above the base letter, which is otherwise contained
    assert c_plain < c_caron | c_plain
    assert min(y for _, y in c_caron) < min(y for _, y in c_plain)


def test_render_mixed_text():
    f = picogame_font.ExtraFont(CZ, SYM)
    fg = pg.rgb565(0, 255, 0)
    bmp, w, h = picogame_font.render_text(pg, f, "Žluťoučký ←→", fg)
    assert (w, h) == (12 * 6, 12)
    assert any(bmp.data)                         # some ink rendered
    # unknown glyphs render as blank cells, not crashes
    bmp2, _, _ = picogame_font.render_text(pg, f, "中", fg)
    assert not any(bmp2.data)


def test_first_load_wins_and_charcell_guard():
    f = picogame_font.ExtraFont(CZ)
    before = f._glyphs[ord("č")]
    f.load(CZ)                                   # reload: must not replace
    assert f._glyphs[ord("č")] is before
    bad = ("STARTFONT 2.1\nCHARS 1\nSTARTCHAR x\nENCODING 65\n"
           "BITMAP\nFF\nFF\nENDCHAR\nENDFONT\n")
    with tempfile.NamedTemporaryFile("w", suffix=".bdf", delete=False) as tf:
        tf.write(bad)
    try:
        try:
            picogame_font.ExtraFont(tf.name)
        except ValueError:
            pass
        else:
            raise AssertionError("short glyph must raise (charcell only)")
    finally:
        os.unlink(tf.name)
