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


def test_repeat_delay_interval():
    b = _btns()
    i = 0                                             # bit index of A
    m = I.A
    while m > 1:
        m >>= 1
        i += 1
    b._hold[i] = 1
    assert b.repeat(I.A, delay=15, interval=4)         # fires on the first frame held
    b._hold[i] = 10
    assert not b.repeat(I.A, delay=15, interval=4)     # inside the delay window -> silent
    b._hold[i] = 15
    assert not b.repeat(I.A, delay=15, interval=4)     # exactly at delay -> not yet
    b._hold[i] = 19
    assert b.repeat(I.A, delay=15, interval=4)         # first repeat: (19-15) % 4 == 0
    b._hold[i] = 20
    assert not b.repeat(I.A, delay=15, interval=4)
    b._hold[i] = 23
    assert b.repeat(I.A, delay=15, interval=4)         # every `interval` frames thereafter


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
