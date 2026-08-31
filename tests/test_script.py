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
        "assets": {"t": ("pal8", (bytes([0] * 32 + [1] * 32)).hex(), 8, 8, 2, 0, (0, 0xFFFF))},
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
