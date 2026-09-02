"""picogame_ui geometry contracts (round-6 findings A5/A6): widgets stay inside their own
rectangle, and a SceneLabel's position is assignable instead of silently ignored."""
import _bootstrap  # noqa: F401

import board
import terminalio

import _host
import picogame as pg
import picogame_ui as ui


def _scene():
    d = board.DISPLAY
    return pg.Scene(d, bytearray(d.width * 24 * 2), bytearray(d.width * 24 * 2),
                    background=0), d


def test_hudbar_stays_inside_its_rect():
    # As a SCENE LAYER the view spans the whole render region and the layer's rect gates rows
    # only, so neither the background fill nor an over-long label may reach past the bar.
    scene, d = _scene()
    bg, fg = pg.rgb565(0, 0, 60), pg.rgb565(255, 255, 255)
    bar = ui.HudBar(pg, d, bytearray(d.width * 16 * 2), 0, 0, 80, 16, bg)
    label = bar.label(terminalio.FONT, 2, 4, fg, "")
    scene.add(bar._sd)
    label.set("STATUS: OVERFLOW")            # 17 chars = 102 px into an 80 px bar
    scene.refresh()
    fb = _host.fb
    assert not any(fb[y * d.width + x] for x in range(80, d.width) for y in range(16))
    assert sum(1 for x in range(80) for y in range(16)
               if fb[y * d.width + x] == fg) > 20, "the text that fits must still be drawn"


def test_scenelabel_position_is_assignable():
    # There is no move(), so people reach for the attribute; it used to be a silent no-op.
    scene, d = _scene()
    label = ui.SceneLabel(scene, pg, terminalio.FONT, 10, 10, pg.rgb565(255, 255, 255))
    label.reserve(8)
    label.set("SCORE 42")
    scene.refresh()
    assert (label.x, label.y) == (10, 10)
    rows_before = {y for y in range(60) for x in range(d.width) if _host.fb[y * d.width + x]}
    label.x, label.y = 100, 40
    scene.refresh()
    fb = _host.fb
    rows_after = {y for y in range(60) for x in range(d.width) if fb[y * d.width + x]}
    assert min(rows_after) > min(rows_before), "assigning y must move the label"
    cols = {x for y in rows_after for x in range(d.width) if fb[y * d.width + x]}
    assert min(cols) == 100, "assigning x must move the label"
    assert not any(fb[y * d.width + x] for y in rows_before for x in range(90)), "old rect stale"
