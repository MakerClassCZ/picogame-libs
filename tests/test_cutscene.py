"""picogame_cutscene: the auto_hold wait loop's frame count (show() itself needs an image + LCD)."""
import _bootstrap  # noqa: F401

import picogame_cutscene as CS


class _Clock:
    def __init__(self):
        self.ticks = 0

    def tick(self):
        self.ticks += 1


class _Buttons:
    A, B = 1, 2

    def __init__(self, press_a_on_poll=0):
        self.polls = 0
        self._press = press_a_on_poll

    def poll(self):
        self.polls += 1

    def just_pressed(self, mask):
        return mask == self.A and self.polls == self._press


def _stub_show(monkey):
    monkey.show = lambda *a, **k: None
    monkey._dst = lambda display: display


def test_auto_hold_paces_exactly_that_many_frames():
    _stub_show(CS)
    for n in (1, 3, 30):
        clock = _Clock()
        assert CS.play(None, None, None, None, "x", auto_hold=n, clock=clock) is None
        assert clock.ticks == n                         # auto_hold=N holds N frames, not N-1 / N+1


def test_press_dismisses_before_the_hold_runs_out():
    _stub_show(CS)
    clock = _Clock()
    btn = _Buttons(press_a_on_poll=3)                   # poll 1 = the flush, 2.. = the wait loop
    assert CS.play(None, None, None, btn, "x", auto_hold=30, clock=clock) == btn.A
    assert clock.ticks == 1                             # one paced frame, then the press


def test_btn_less_play_needs_auto_hold():
    _stub_show(CS)
    try:
        CS.play(None, None, None, None, "x")
    except ValueError:
        return
    assert False, "play() without btn or auto_hold must raise"
