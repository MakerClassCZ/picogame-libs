"""picogame_seq.Script - the scripted input source (the module's original purpose: a game
that plays itself). Pins the whole loop: Script drives a REAL Buttons through the sources
contract, edges fire for taps, attach/detach merges with other input, loop mode restarts,
and the human-override pattern (btn.state & ~script.mask) actually detects a human."""
import _bootstrap  # noqa: F401

import picogame_input as pi
import picogame_seq as seq


class FakePad:
    """A second source standing in for real hardware (a human's pad)."""
    def __init__(self):
        self.mask = 0

    def read(self):
        return self.mask


def drive(btn, script, frames):
    """One game-loop step per frame: script.tick() then btn.poll(); collect edges."""
    taps = []
    for f in range(frames):
        script.tick()
        btn.poll()
        if btn.just_pressed(btn.A):
            taps.append(f)
    return taps


def test_tap_fires_just_pressed_through_real_buttons():
    B = pi.Buttons
    def play(s):
        yield from s.rest(3)
        yield from s.tap(B.A)              # 2-frame tap
        yield from s.rest(5)
        yield from s.tap(B.A)
    script = seq.Script(play)
    btn = pi.Buttons(sources=[script])
    taps = drive(btn, script, 20)
    assert len(taps) == 2                  # two distinct edges, not one long hold
    assert script.done and script.read() == 0


def test_hold_is_continuous_and_released_at_end():
    B = pi.Buttons
    def play(s):
        yield from s.hold(B.RIGHT, 10)
    script = seq.Script(play)
    btn = pi.Buttons(sources=[script])
    held = 0
    for _ in range(15):
        script.tick()
        btn.poll()
        if btn.is_pressed(btn.RIGHT):
            held += 1
    assert held == 10                      # exactly the scripted frames, then released


def test_loop_restarts_the_script():
    B = pi.Buttons
    def play(s):
        yield from s.tap(B.A, frames=1, gap=3)
    script = seq.Script(play, loop=True)
    btn = pi.Buttons(sources=[script])
    taps = drive(btn, script, 17)
    assert len(taps) >= 3                  # keeps playing
    assert not script.done


def test_attach_detach_and_human_override():
    B = pi.Buttons
    def play(s):
        yield from s.hold(B.RIGHT, 100)    # attract: drive right forever
    script = seq.Script(play)
    human = FakePad()
    btn = pi.Buttons(sources=[human])      # "hardware"
    btn.attach(script)                     # attract mode ON
    script.tick(); btn.poll()
    assert btn.is_pressed(btn.RIGHT)
    human.mask = B.A                       # the human grabs the pad
    script.tick(); btn.poll()
    assert btn.state & ~script.mask        # override detected ->
    btn.detach(script); script.stop()
    btn.poll()
    assert not btn.is_pressed(btn.RIGHT)   # the script's press is gone
    assert btn.is_pressed(btn.A)           # the human's remains


def test_tap_with_base_keeps_the_base_held():
    B = pi.Buttons
    def play(s):
        yield from s.tap(B.A, base=B.RIGHT)
        yield from s.hold(B.RIGHT, 2)
    script = seq.Script(play)
    btn = pi.Buttons(sources=[script])
    for _ in range(7):
        script.tick()
        btn.poll()
        assert btn.is_pressed(btn.RIGHT)   # steering never drops during the tap
