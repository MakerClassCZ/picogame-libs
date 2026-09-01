"""Sim <-> firmware BEHAVIOUR parity (the B3 trio from the 2026-09 doc-truth audit).

selftest_api.py guards the SURFACE (names + signatures); these pin the return-value semantics
that the C engine defines and games can observe:
  1. Scene.refresh() returns None on a no-change frame (C returns the dirty union, or None).
  2. flash/tint getters read 0 while the effect is off (C: 0 also DISABLES flash, so pure
     black can never be a flash colour) - never None.
  3. StripDraw.invalidate() takes none-or-all-four rect args; a partial rect raises
     ValueError on device (a partial rect is a bug, not a request for "everything").
"""
import _bootstrap  # noqa: F401

import board
import picogame as pg


def _scene():
    d = board.DISPLAY
    buf_a = bytearray(d.width * 24 * 2)
    buf_b = bytearray(d.width * 24 * 2)
    return pg.Scene(d, buf_a, buf_b, background=pg.rgb565(0, 0, 40)), d


def test_refresh_returns_none_when_nothing_changed():
    scene, d = _scene()
    sprite = pg.Sprite(pg.Bitmap(b"\x01" * 64, 8, 8, format=pg.PAL8,
                                 palette=(0, 0xFFFF)), 10, 10)
    scene.add(sprite)
    assert scene.refresh(), "first frame paints -> truthy rect"
    assert scene.refresh() is None, "untouched frame -> None (firmware contract)"
    sprite.x += 3
    assert scene.refresh(), "a moved sprite -> truthy rect again"


def test_fx_getters_read_zero_while_off():
    sprite = pg.Sprite(pg.Bitmap(b"\x01" * 64, 8, 8, format=pg.PAL8,
                                 palette=(0, 0xFFFF)), 0, 0)
    assert sprite.flash == 0 and sprite.flash is not None
    assert sprite.tint == 0 and sprite.tint is not None
    sprite.flash = pg.rgb565(255, 255, 255)
    assert sprite.flash != 0
    sprite.flash = 0                          # 0 turns it back off
    assert sprite.flash == 0


def test_stripdraw_invalidate_rejects_partial_rect():
    sd = pg.StripDraw(lambda view, vx, vy, vw, vh: None, 0, 0, 64, 48,
                      always_dirty=False)
    sd.invalidate()                           # whole layer: fine
    sd.invalidate(0, 0, 10, 10)               # full rect: fine
    for partial in ((3,), (3, 4), (3, 4, 5)):
        try:
            sd.invalidate(*partial)
        except ValueError:
            pass
        else:
            raise AssertionError("partial rect %r must raise ValueError" % (partial,))


def test_stripdraw_ignores_scene_view():
    # Screen-space by design: the C compositor keeps a StripDraw's rows at layer.y
    # whether or not the layer is fixed - the sim must not scroll it with set_view.
    scene, d = _scene()
    rows = []
    sd = pg.StripDraw(lambda view, vx, vy, vw, vh: rows.append(vy), 0, 60, d.width, 30)
    scene.add(sd)                             # non-fixed on purpose
    scene.refresh()
    first = (min(rows), max(rows))
    scene.set_view(0, 20)
    del rows[:]
    scene.refresh()
    assert rows and (min(rows), max(rows)) == first, rows
