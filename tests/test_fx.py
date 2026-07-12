"""picogame_fx.Shake — screen-shake (shake.add/tick, 14 calls). Driven with a fake scene that just
records set_view(), so we test the trauma model + the idle early-out + bounded offset without any
engine. (A1 change: idle must not call the RNG; offsets stay within max_offset; trauma decays.)"""
import _bootstrap  # noqa: F401

import picogame_fx as FX


class FakeScene:
    def __init__(self):
        self.view = None
        self.calls = 0

    def set_view(self, x, y):
        self.view = (x, y)
        self.calls += 1


def test_shake_idle_tracks_camera_no_shake():
    s = FakeScene()
    sh = FX.Shake(s)
    r = sh.tick(5, 7)                       # trauma 0 -> just apply the camera, no offset
    assert r is False
    assert s.view == (5, 7)


def test_shake_active_within_bounds():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6)
    sh.add(1.0)
    for _ in range(5):
        r = sh.tick(0, 0)
        ox, oy = s.view
        assert -6 <= ox <= 6 and -6 <= oy <= 6   # offset never exceeds max_offset
        assert r is True                          # still shaking


def test_shake_offset_rides_camera():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6)
    sh.add(1.0)
    sh.tick(100, 200)
    ox, oy = s.view
    assert 100 - 6 <= ox <= 100 + 6              # shake is added ON TOP of the camera
    assert 200 - 6 <= oy <= 200 + 6


def test_shake_decays_and_stops():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6, decay=0.1)
    sh.add(0.3)
    ticks = 0
    while sh.tick(0, 0):
        ticks += 1
        assert ticks < 100                       # must terminate
    assert sh.trauma == 0.0
    # once stopped, idle ticks keep working and stay centred
    assert sh.tick(0, 0) is False
    assert s.view == (0, 0)


def test_shake_add_clamps_to_one():
    sh = FX.Shake(FakeScene())
    sh.add(0.8)
    sh.add(0.8)
    assert sh.trauma <= 1.0
