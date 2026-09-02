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
import _host
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


def _strict_scene():
    """A --strict-dirty scene: background StripDraw(always_dirty=False) + a sprite over it."""
    pg._set_strict_dirty(True)
    scene, d = _scene()
    return scene, d


def test_strict_dirty_does_not_burn_in_a_passing_sprite():
    # Round-6 finding A1: the restore used to come from the whole previous FRAME, so a sprite that
    # crossed a clean StripDraw left its imprint burned in for good (seen on shipped squest). The
    # device re-runs a clean layer whenever an overlapping dirty rect repaints it, so no ghost.
    scene, d = _strict_scene()
    try:
        red = pg.rgb565(255, 0, 0)
        sky = pg.StripDraw(lambda view, vx, vy, vw, vh:
                           view.fill_rect(0 - vx, 0 - vy, d.width, 80, pg.rgb565(0, 0, 200)),
                           0, 0, d.width, 80, always_dirty=False)
        scene.add(sky)
        sprite = pg.Sprite(pg.Bitmap(b"\x01" * 256, 16, 16, format=pg.PAL8,
                                     palette=(0, red)), 40, 30)
        scene.add(sprite)
        scene.refresh()
        sprite.x = 200                      # fly away; the vacated pixels must not keep the sprite
        scene.refresh()
        assert _host.fb[38 * d.width + 48] != red
    finally:
        pg._set_strict_dirty(False)


def test_strict_dirty_still_freezes_a_forgotten_invalidate():
    # The trap the mode exists for must survive the A1 fix: content changed without invalidate()
    # keeps showing the OLD content (as the panel does), and invalidate() unfreezes it.
    scene, d = _strict_scene()
    try:
        blue = pg.rgb565(0, 0, 200)
        colour = [blue]
        panel = pg.StripDraw(lambda view, vx, vy, vw, vh:
                             view.fill_rect(0 - vx, 0 - vy, d.width, 80, colour[0]),
                             0, 0, d.width, 80, always_dirty=False)
        scene.add(panel)
        scene.refresh()
        colour[0] = pg.rgb565(0, 200, 0)    # changed, but nobody called invalidate()
        scene.refresh()
        assert _host.fb[10 * d.width + 10] == blue, "a forgotten invalidate() must still freeze"
        panel.invalidate()
        scene.refresh()
        assert _host.fb[10 * d.width + 10] != blue
    finally:
        pg._set_strict_dirty(False)


def test_strict_dirty_reruns_when_something_below_changes():
    # The device rule (Scene.c: a clean StripDraw "still re-runs when another layer's dirty rect
    # overlaps it"): a tilemap edit UNDER the layer must reach the screen, not be restored away.
    scene, d = _strict_scene()
    try:
        runs = []

        def draw(view, vx, vy, vw, vh):     # paints only the BOTTOM strip of its own rect
            runs.append(vy)
            view.fill_rect(0 - vx, 40 - vy, d.width, 20, pg.rgb565(0, 0, 200))

        overlay = pg.StripDraw(draw, 0, 0, d.width, 80, always_dirty=False)
        atlas = bytes(([1] * 8 + [2] * 8) * 8)          # per-row atlas: frame0 | frame1
        tiles = pg.Bitmap(atlas, 8, 8, format=pg.PAL8, frames=2,
                          palette=(0, pg.rgb565(80, 80, 80), pg.rgb565(200, 200, 0)))
        tilemap = pg.Tilemap(tiles, 8, 4)
        tilemap.fill(0)
        scene.add(tilemap)
        scene.add(overlay)                              # overlay sits ON TOP of the map
        scene.refresh()
        scene.refresh()
        before, pixel = len(runs), _host.fb[8 * d.width + 8]
        tilemap.set_tile(1, 1, 1)                       # a change UNDER the clean overlay
        scene.refresh()
        assert len(runs) > before, "the callback must re-run when its rect is dirtied from below"
        assert _host.fb[8 * d.width + 8] != pixel, "the change below must reach the screen"
        quiet = len(runs)
        scene.refresh()
        assert len(runs) == quiet, "a genuinely quiet frame must still skip the callback"
    finally:
        pg._set_strict_dirty(False)


def _banded_scene():
    """A scene with a reserved HUD band, as picogame_game.setup(top=16) makes."""
    d = board.DISPLAY
    return pg.Scene(d, bytearray(d.width * 24 * 2), bytearray(d.width * 24 * 2),
                    background=0, top=16), d


def _sprite(x, y):
    return pg.Sprite(pg.Bitmap(b"\x01" * 256, 16, 16, format=pg.PAL8,
                               palette=(0, 0xFFFF)), x, y)


def test_reserved_band_warning_ignores_ordinary_idioms():
    # Round-6 finding A4 (three agents, five shipped games): the check judged a layer at add()
    # time in world coordinates, so a pooled/parked sprite, a "construct then place" sprite and
    # anything in a scrolling world tripped it.
    _host.take_notes()
    scene, _ = _banded_scene()
    parked = _sprite(0, 0)
    parked.visible = False                    # picogame_pool parks unspawned sprites like this
    scene.add(parked)
    placed = scene.add(_sprite(0, 0))
    placed.x, placed.y = 100, 100             # construct, then place
    scene.refresh()
    assert not _host.take_notes()

    scene, _ = _banded_scene()
    scene.add(_sprite(500, 300))              # far out in a world bigger than the screen...
    scene.set_view(-450, -250)                # ...but the camera brings it on screen
    scene.refresh()
    assert not _host.take_notes()


def test_reserved_band_warning_ignores_offscreen_layers():
    # An inset of 0 is not a band: a layer beyond that edge is merely OFF-SCREEN (parked, pooled,
    # scrolled away), which is normal. Reported on shipped pictor until the check required a real
    # band AND an on-screen rect.
    _host.take_notes()
    scene, d = _banded_scene()                # top=16 only; left/right/bottom are 0
    scene.add(_sprite(d.width + 300, 100))    # far off the right edge
    scene.refresh()
    assert not _host.take_notes()


def test_reserved_band_warning_still_catches_a_dead_layer():
    # The warning must survive: a VISIBLE layer whose screen rect is wholly inside the band
    # really never draws, whether it is fixed or scrolled there by the camera.
    _host.take_notes()
    scene, _ = _banded_scene()
    scene.add(_sprite(100, 0))                # sits in the top=16 band
    scene.refresh()
    assert _host.take_notes(), "a visible layer inside the reserved band must be reported"

    scene, _ = _banded_scene()
    scene.add(_sprite(500, 300))
    scene.set_view(-450, -300)                # camera puts it at screen y=0: still dead
    scene.refresh()
    assert _host.take_notes()


def test_always_dirty_warning_only_for_scene_layers():
    # Round-7 finding: the warning fired in StripDraw's constructor, so picogame_ui's IMMEDIATE
    # widgets (which build a StripDraw purely to carry a pg.render callback and never join a
    # scene) were accused of a trap they cannot fall into. always_dirty only means anything to
    # scene.refresh(), so the layer is judged on scene entry.
    import terminalio
    import picogame_ui as ui
    _host.take_notes()
    d = board.DISPLAY
    ui.TextBox(pg, terminalio.FONT, 0, 0, d.width, d.height,
               pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 60))
    assert not _host.take_notes(), "an immediate widget must not trip the always_dirty warning"

    scene, _ = _scene()
    scene.add(pg.StripDraw(lambda view, vx, vy, vw, vh: None, 0, 0, d.width, d.height))
    scene.refresh()
    assert _host.take_notes(), "a full-screen always_dirty SCENE layer must still be reported"

    scene, _ = _scene()
    scene.add(pg.StripDraw(lambda view, vx, vy, vw, vh: None, 0, 0, d.width, d.height,
                           always_dirty=False))
    scene.refresh()
    assert not _host.take_notes()
