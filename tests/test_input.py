"""picogame_input — the single most-used lib (is_pressed/just_pressed 340+ calls). We test the
pure query logic (mask + edge detection + repeat) by driving state directly, plus the settings.toml
profile parser. Hardware pin polling is covered by the sim-smoke tests, not here."""
import _bootstrap  # noqa: F401

import os

import picogame_input as I


def _btns():
    # empty profile + no keypad -> the polling backend with no pins; we set .state/.prev by hand
    # to exercise the query logic that games call every frame.
    return I.Buttons(profile=(), prefer_keypad=False)


def test_constants_distinct_bits():
    names = [I.UP, I.DOWN, I.LEFT, I.RIGHT, I.A, I.B, I.X, I.Y,
             I.L1, I.L2, I.R1, I.R2, I.START, I.SELECT]
    assert len(set(names)) == len(names)             # all distinct
    for v in names:
        assert v & (v - 1) == 0 and v != 0           # each is a single bit
    assert I.ALL == (1 << 14) - 1                     # ALL covers the 14 logical buttons


def test_is_pressed_mask():
    b = _btns()
    b.state = I.UP | I.A
    assert b.is_pressed(I.UP)
    assert b.is_pressed(I.A)
    assert not b.is_pressed(I.B)
    assert b.is_pressed(I.UP | I.B)                   # mask matches if ANY bit is down
    assert b.is_pressed()                             # default ALL -> any button


def test_just_pressed_released_edges():
    b = _btns()
    b.prev = I.UP                                     # UP was down last frame
    b.state = I.UP | I.A                              # A newly pressed, UP still held
    assert b.just_pressed(I.A)                        # rising edge
    assert not b.just_pressed(I.UP)                   # held, not an edge
    b.prev = I.UP | I.A
    b.state = I.UP                                    # A released this frame
    assert b.just_released(I.A)
    assert not b.just_released(I.UP)


class _Src:
    """A button source (.read() -> mask) the test drives frame by frame."""
    mapped = I.ALL

    def __init__(self):
        self.mask = 0

    def read(self):
        return self.mask


def _held_frames(b, src, mask, frames, delay=15, interval=4):
    """Hold `mask` for `frames` polls; return the list of repeat() answers, one per poll."""
    src.mask = mask
    return [b.poll() and b.repeat(mask, delay, interval) for _ in range(frames)]


def test_repeat_delay_interval():
    b = I.Buttons(sources=[src := _Src()])
    fired = _held_frames(b, src, I.A, 24)
    # frame 1 (the press) fires; silent through the delay; then every `interval` frames
    assert fired == [f in (1, 19, 23) for f in range(1, 25)], fired
    src.mask = 0
    b.poll()
    assert not b.repeat(I.A)                          # released: never fires
    src.mask = I.A
    b.poll()
    assert b.repeat(I.A)                              # a fresh press fires again on its first frame


def _hold_counts_reference(states):
    """The pre-stamp bookkeeping: per-button consecutive-frames-held counters, one list per poll."""
    h = [0] * 14
    out = []
    for s in states:
        h = [h[i] + 1 if s & (1 << i) else 0 for i in range(14)]
        out.append(list(h))
    return out


def test_repeat_matches_held_frame_counters():
    # Differential: repeat() (press-frame stamps) must answer exactly what the old per-poll
    # held-frame counters answered, over a random press/hold/release sequence on every button.
    import random
    rnd = random.Random(7)
    b = I.Buttons(sources=[src := _Src()])
    states = []
    cur = 0
    for _ in range(600):
        if rnd.random() < 0.15:                       # flip a random button now and then
            cur ^= 1 << rnd.randrange(14)
        states.append(cur)
    ref = _hold_counts_reference(states)
    for s, counts in zip(states, ref):
        src.mask = s
        b.poll()
        for i in range(14):
            c = counts[i]
            want = c == 1 or (c > 5 and (c - 5) % 3 == 0)
            assert b.repeat(1 << i, delay=5, interval=3) == want, (s, i, c)


def test_clear_then_held_button_does_not_repeat():
    # clear() while a button is held: the next poll must not report the first-frame edge
    # (a menu opened by a held button would move its cursor one step).
    b = I.Buttons(sources=[src := _Src()])
    src.mask = I.DOWN
    b.poll()
    assert b.repeat(I.DOWN)
    b.clear()
    b.poll()
    assert not b.just_pressed(I.DOWN)
    assert not b.repeat(I.DOWN)
    # ...but it keeps counting as held: the delayed auto-repeat still arrives on schedule
    fired = [b.poll() and b.repeat(I.DOWN, delay=15, interval=4) for _ in range(30)]
    assert any(fired) and not any(fired[:14])


def test_has_reports_mapped():
    b = _btns()
    assert not b.has(I.A)                             # empty profile maps nothing


def test_profile_from_settings_parsing():
    os.environ["PICOGAME_BUTTONS"] = "UP=GP4 A=GP7 bogus=GP1 B=GP6"
    try:
        prof = I._profile_from_settings()
    finally:
        del os.environ["PICOGAME_BUTTONS"]
    d = dict(prof)                                    # {pin_str: mask}
    assert d["GP4"] == I.UP
    assert d["GP7"] == I.A
    assert d["GP6"] == I.B
    assert "GP1" not in d                             # unknown logical name dropped


def test_profile_from_settings_unset():
    os.environ.pop("PICOGAME_BUTTONS", None)
    assert I._profile_from_settings() is None


# --- local multiplayer: Buttons(sources=[...]) = one player per device ---
class FakeSource:
    """A minimal input source (the .read()->mask / .mapped protocol UsbPad/UsbKbd implement)."""
    def __init__(self, mapped=I.ALL):
        self.mapped = mapped
        self._m = 0

    def read(self):
        return self._m


def test_sources_two_players_isolated():
    s1, s2 = FakeSource(), FakeSource()
    p1 = I.Buttons(sources=[s1])
    p2 = I.Buttons(sources=[s2])
    s1._m = I.A
    p1.poll(); p2.poll()
    assert p1.is_pressed(I.A) and not p2.is_pressed(I.A)   # each player reads only its own device
    assert p1.just_pressed(I.A) and not p2.just_pressed(I.A)
    s1._m = I.A; s2._m = I.LEFT                            # p1 keeps holding A, p2 presses LEFT
    p1.poll(); p2.poll()
    assert not p1.just_pressed(I.A)                        # held, not a fresh press
    assert p2.just_pressed(I.LEFT)
    assert p1.is_pressed(I.A) and p2.is_pressed(I.LEFT)


def test_sources_mapped_union_and_or():
    a, b = FakeSource(mapped=I.A | I.B), FakeSource(mapped=I.LEFT)
    p = I.Buttons(sources=[a, b])
    assert p.has(I.A) and p.has(I.B) and p.has(I.LEFT) and not p.has(I.START)   # mapped = OR
    a._m = I.A; b._m = I.LEFT
    p.poll()
    assert p.is_pressed(I.A) and p.is_pressed(I.LEFT)      # a player CAN still combine >1 device
