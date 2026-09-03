"""picogame_script.Director - resumable story scripts as generators.

The primitives must never block (the game loop owns the frame), the A press
that starts a script must not dismiss its first dialog, and finishing or
running scripts must not leak state into the next one.
"""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)
import picogame as pg
import picogame_scene
import picogame_script
import terminalio


class FakeButtons:
    A, B = 1, 2

    def __init__(self):
        self._just = 0

    def press(self, mask):          # a one-frame edge, like poll() would produce
        self._just = mask

    def just_pressed(self, mask):
        hit = bool(self._just & mask)
        return hit

    def clear(self):
        self._just = 0


def _view():
    return picogame_scene.load(pg, {
        "bg": 0,
        "assets": {"t": ("pal8", (bytes([0] * 64 + [1] * 64)).hex(), 8, 8, 2, 0, (0, 0xFFFF))},
        "tileprops": {}, "anims": {},
        "layers": [("tilemap", "t", 2, 2, 0, 0, bytes([1, 0, 0, 1]))],
        "camera": None,
    })


def _director(btn):
    v = _view()
    return picogame_script.Director(pg, v.scene, btn, terminalio.FONT), v


def test_script_runs_stepwise_and_finishes():
    btn = FakeButtons()
    d, _ = _director(btn)
    seen = []

    def s(d):
        seen.append("a")
        yield
        seen.append("b")

    assert d.start(s)
    assert d.active
    assert d.tick() is True        # runs up to the yield
    assert seen == ["a"]
    assert d.tick() is True        # the FINISHING step still reports running,
    assert seen == ["a", "b"]      # so its input cannot leak into game logic
    assert not d.active
    assert d.tick() is False       # idle ticks are cheap no-ops


def test_text_waits_for_a_and_ignores_the_starting_press():
    btn = FakeButtons()
    d, _ = _director(btn)

    def s(d):
        yield from d.text(["hi"])

    btn.press(btn.A)               # the SAME press that triggered the start
    d.start(s)
    assert d.tick() is True        # frame 1: box shown, guard yield eats the press
    btn.clear()
    assert d.tick() is True        # frame 2: no press -> still waiting
    assert d._box._visible if hasattr(d._box, "_visible") else True
    btn.press(btn.A)
    assert d.tick() is True        # dismissed; the dismissing frame still "runs"
    assert not d.active
    assert d.tick() is False       # ...and only the NEXT frame frees the input


def test_ask_sets_answer_from_a_or_b():
    for mask, expected in ((FakeButtons.A, True), (FakeButtons.B, False)):
        btn = FakeButtons()
        d, _ = _director(btn)

        def s(d):
            yield from d.ask(["sure?"])

        d.start(s)
        btn.clear()
        d.tick()                   # guard frame
        btn.press(mask)
        d.tick()
        assert d.answer is expected


def test_wait_counts_frames():
    btn = FakeButtons()
    d, _ = _director(btn)

    def s(d):
        yield from d.wait(3)

    d.start(s)
    ticks = 0
    while d.tick():
        ticks += 1
    assert ticks == 4              # 3 waits + the finishing step


def test_start_refuses_while_running_and_events_persist():
    btn = FakeButtons()
    d, _ = _director(btn)

    def s(d):
        d.ev_set("gate_open")
        yield

    assert d.start(s)
    assert d.start(s) is False     # no interrupting a running script
    while d.tick():
        pass
    assert d.ev("gate_open")
    d.ev_clear("gate_open")
    assert not d.ev("gate_open")


def test_script_can_flip_tile_props_live():
    btn = FakeButtons()
    v = _view()
    d = picogame_script.Director(pg, v.scene, btn, terminalio.FONT)

    def lever(d):
        v.set_tile_prop(1, "solid", False)
        yield

    v.set_tile_prop(1, "solid", True)
    assert v.is_solid(0, 0)
    d.start(lever)
    while d.tick():
        pass
    assert not v.is_solid(0, 0)    # the whole gate opened from a script


def test_fade_out_drives_fx_until_done():
    btn = FakeButtons()
    d, _ = _director(btn)

    def s(d):
        yield from d.fade_out(speed=8.0)

    d.start(s)
    ticks = 0
    while d.tick() and ticks < 120:
        ticks += 1
    assert not d.active, "fade never finished"
    assert 0 < ticks < 120
    assert d._fade.is_done


def test_retarget_rebinds_scene_and_keeps_story():
    btn = FakeButtons()
    d, _ = _director(btn)

    def s(d):
        yield from d.text(["hello"])

    d.start(s)
    d.tick()                       # builds the box on the first scene
    old_box = d._box
    d.ev_set("met_elder")
    btn.press(btn.A)
    d.tick()                       # dismiss, script ends
    v2 = _view()                   # "another map"
    d.retarget(v2.scene)
    assert d._box is None and d._fade is None
    assert d.scene is v2.scene
    assert d.ev("met_elder")       # the story survives the move
    d.start(s)
    d.tick()
    assert d._box is not old_box   # box rebuilt on the new scene


def _lit_in_box(d):
    # fg pixels INSIDE the box rect (the map's white tiles outside it do dim)
    import _host
    import board
    w = board.DISPLAY.width
    x0, y0, bw, bh = d._boxgeom
    return sum(1 for y in range(y0, y0 + bh) for x in range(x0, x0 + bw)
               if _host.fb[y * w + x] == 0xFFFF)


def test_dialogue_stays_above_the_fade_whatever_is_built_first():
    # Round-9 finding: the box and the fade are lazily added on first use, and insertion order is
    # z-order. A box built BEFORE the fade sat under it, so text shown during a dim() was mostly
    # stippled away. The test shows text FIRST (the bad order), then asks for the fade and dims -
    # the fade must lift the box back on top, so the text pixel count must not drop.
    btn = FakeButtons()
    d, v = _director(btn)

    def s(d):
        yield from d.text(["HELLO WORLD", "HELLO WORLD"])

    d.start(s)
    d.tick()                       # box built; no fade yet
    v.scene.refresh()
    plain = _lit_in_box(d)
    assert plain > 50, "text must render"
    d._ensure_fade().dim(12)       # the fade arrives AFTER the box -> box lifted above it
    v.scene.refresh()
    assert _lit_in_box(d) == plain, "a dim under the box must not eat the dialogue"
    assert v.scene._items.index(d._box._sd) > v.scene._items.index(d._fade.sd)


def test_text_only_director_never_builds_the_fade():
    # A story that only talks must not pay for picogame_fx + a Fade (~1.5 KB, plus the module if
    # nothing else imported it) at its first dialogue - mid-game, on a fragmented heap. Both
    # parts are lazy on their OWN first use; z-order is fixed up by _ensure_fade instead.
    import sys
    btn = FakeButtons()
    d, v = _director(btn)

    def s(d):
        yield from d.text(["Gatekeeper:", "Go on through."])
        yield from d.ask(["Really?"])

    had_fx = "picogame_fx" in sys.modules
    sys.modules.pop("picogame_fx", None)
    try:
        d.start(s)
        for _ in range(3):
            d.tick()
        assert d._box is not None and d._fade is None
        assert "picogame_fx" not in sys.modules, "text() must not import picogame_fx"
    finally:
        if had_fx:
            import picogame_fx  # noqa: F401  (restore for the other tests)


def test_fade_first_then_text_keeps_the_box_on_top_without_a_lift():
    # The other order (fade, then a first dialogue) needs no fix-up: the box is simply added later.
    btn = FakeButtons()
    d, v = _director(btn)

    def s(d):
        yield from d.fade_out(speed=16.0)
        yield from d.fade_in(speed=16.0)
        yield from d.text(["HELLO WORLD", "HELLO WORLD"])

    d.start(s)
    for _ in range(12):
        d.tick()
    assert d._fade is not None and d._box is not None
    v.scene.refresh()
    plain = _lit_in_box(d)
    assert plain > 50
    d._fade.dim(12)
    v.scene.refresh()
    assert _lit_in_box(d) == plain
    assert v.scene._items.index(d._box._sd) > v.scene._items.index(d._fade.sd)
