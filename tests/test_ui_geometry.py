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


def test_scenemenu_set_items_reuses_the_layer():
    # Round-7 finding: a menu whose entry count changes had to be rebuilt, against the module's own
    # build-once rule. set_items swaps the entries in place - no new scene layer - and resizes,
    # forcing a full repaint when it shrinks so the vacated rect is erased.
    import terminalio
    scene, d = _scene()
    menu = ui.SceneMenu(scene, pg, terminalio.FONT, 20, 20, ["Go", "Rest"],
                        pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 60), title="CREW")
    menu.show()
    scene.refresh()
    layers, tall = len(scene._items), menu.panel.h

    menu.set_items(["Go", "Rest", "Upgrade", "Hire", "Sell"])
    scene.refresh()
    assert len(scene._items) == layers, "set_items must not add a scene layer"
    assert menu.panel.h > tall, "the panel must grow with the list"
    assert menu.tick is not None and len(menu.items) == 5

    lit_before = sum(1 for px in _host.fb if px)
    menu.set_items(["Go"])
    scene.refresh()
    assert menu.panel.h < tall + 1
    assert sum(1 for px in _host.fb if px) < lit_before, "a shrink must erase the vacated rect"


def test_scenebox_visible_is_assignable_and_overflow_is_flagged():
    # Round-9 findings: `box.visible = True` was a silent no-op (the API is show()/hide()), and
    # show() dropped lines past nlines without a word.
    scene, d = _scene()
    fg, bg = pg.rgb565(255, 255, 255), pg.rgb565(0, 0, 80)
    box = ui.SceneBox(scene, pg, terminalio.FONT, 10, 10, 200, 50, fg, bg, nlines=3)
    _host.take_notes()
    box.show(["one", "two", "three", "four"])
    notes = [n for n in _host.take_notes() if "SceneBox.show()" in n]
    assert notes and "4 lines" in notes[0] and "nlines=3" in notes[0], notes
    scene.refresh()

    def lit():
        return sum(1 for px in _host.fb if px)

    shown = lit()
    assert shown > 100 and box.visible
    box.visible = False
    scene.refresh()
    assert lit() == 0 and not box.visible, "hiding via the attribute must erase the panel"
    box.visible = True
    scene.refresh()
    assert lit() == shown, "re-showing via the attribute must bring the same panel back"
    box.show(["a", "b"])
    assert not [n for n in _host.take_notes() if "SceneBox.show()" in n], "fits: no note"


def _fresh_compose(text, chars):
    """Oracle: a from-scratch compose of `text` into a blank buffer of `chars` cells."""
    import picogame_font
    fw, fh = terminalio.FONT.get_bounding_box()[:2]
    buf = bytearray(fw * chars * fh)
    picogame_font.compose_into(terminalio.FONT, text, buf, fw * chars, chars)
    return buf


def test_scenelabel_diff_compose_matches_a_fresh_compose():
    # set() rewrites only the cells whose character changed - the buffer must still equal a
    # from-scratch compose after every step, incl. the traps: set("") hides WITHOUT repainting
    # (the old pixels stay in the buffer), a shorter text must blank the old tail, an over-run
    # regrows the buffer, reserve() forgets everything.
    import random
    scene, d = _scene()
    label = ui.SceneLabel(scene, pg, terminalio.FONT, 0, 0, pg.rgb565(255, 255, 255))
    label.reserve(12)
    for text in ("SCORE 000042", "SCORE 000043", "SCORE 000143", "", "HI", "SCORE 9", "",
                 "SCORE 000144", "S", "", "LONGER THAN TWELVE", "X", "SCORE 000145"):
        label.set(text)
        if text:
            assert label._buf[:len(_fresh_compose(text, label._chars))] == \
                _fresh_compose(text, label._chars), repr(text)
    rng = random.Random(7)
    alphabet = "ABC 0123456789"
    for _ in range(200):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 18)))
        label.set(text)
        if text:
            assert label._buf == _fresh_compose(text, label._chars), repr(text)
    label.reserve(6)
    label.set("ABC")
    assert label._buf == _fresh_compose("ABC", 6)


def test_compose_into_skips_unchanged_cells():
    # The point of the diff: a one-cell change touches one cell's rows, and a blank-padded old
    # tail is trusted (no rewrite of blank-on-blank).
    import picogame_font
    fw, fh = terminalio.FONT.get_bounding_box()[:2]
    chars = 8
    buf = bytearray(fw * chars * fh)
    picogame_font.compose_into(terminalio.FONT, "SCORE 12", buf, fw * chars, chars)
    poison = bytearray(buf)
    for i in range(len(poison)):                     # scribble over every cell except cell 7
        if (i % (fw * chars)) // fw != 7:
            poison[i] = 0xEE
    picogame_font.compose_into(terminalio.FONT, "SCORE 13", poison, fw * chars, chars,
                               old="SCORE 12")
    fresh = _fresh_compose("SCORE 13", chars)
    for i in range(len(fresh)):
        cell = (i % (fw * chars)) // fw
        if cell == 7:
            assert poison[i] == fresh[i], "the changed cell is repainted"
        else:
            assert poison[i] == 0xEE, "an unchanged cell is left alone (cell %d)" % cell
