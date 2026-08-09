"""picogame_music — the PICO-8 music player. We drive the pure sequencing logic with a
fake synth + fake clock; audio rendering itself is synthio's job (device-verified via
review/synth_music_bench.py)."""
import _bootstrap  # noqa: F401

import picogame_music as M

TICK = 7812500                     # 1/128 s in ns


def note(pitch, wave=3, vol=5, fx=0):
    return bytes((pitch, (wave << 4) | vol, fx))


def sfx(notes, speed=8):
    data = b"".join(notes) + note(0, 0, 0) * (32 - len(notes))
    return (speed, 0, 0, data)


class Bank:
    def __init__(self, sfx_map, patterns):
        self.SFX = sfx_map
        self.PATTERNS = patterns


class FakeSynth:
    def __init__(self):
        self.live = []
        self.events = []

    def press(self, n):
        self.live.append(n)
        self.events.append(("press", n))

    def release(self, n):
        self.live.remove(n)
        self.events.append(("release", n))


class FakeVoice:
    def __init__(self):
        self.playing = None

    def play(self, s):
        self.playing = s


class FakeMixer:
    def __init__(self):
        self.voice = [FakeVoice(), FakeVoice()]


class FakeHost:
    def __init__(self):
        self.available = True
        self.sample_rate = 22050
        self.mixer = FakeMixer()
        self.synth = FakeSynth()      # the sfx-side synth (voice 1) - music must NOT use it


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


def make(bank):
    host = FakeHost()
    clk = Clock()
    s = FakeSynth()
    p = M.Player(host, bank, _now=clk, _synth=s)
    return p, s, clk


def test_first_tick_presses_active_channels():
    bank = Bank({1: sfx([note(24)]), 2: sfx([note(36)])},
                ((1, 2, 0xFF, 0xFF, 0),))
    p, s, clk = make(bank)
    p.play(0)
    p.tick()
    assert len(s.live) == 2
    f = sorted(n.frequency for n in s.live)
    assert abs(f[0] - 65.406 * 2 ** 2) < 0.5          # pitch 24 = +2 octaves
    assert abs(f[1] - 65.406 * 2 ** 3) < 0.5


def test_note_advance_and_rest():
    bank = Bank({1: sfx([note(24), note(0, 0, 0), note(30)], speed=8)},
                ((1, 0xFF, 0xFF, 0xFF, 0),))
    p, s, clk = make(bank)
    p.play(0)
    p.tick()
    assert len(s.live) == 1
    clk.t += 8 * TICK
    p.tick()                                          # rest: releases, presses nothing
    assert len(s.live) == 0
    clk.t += 8 * TICK
    p.tick()
    assert len(s.live) == 1


def test_volume_scales_amplitude():
    bank = Bank({1: sfx([note(24, vol=7)])}, ((1, 0xFF, 0xFF, 0xFF, 0),))
    p, s, clk = make(bank)
    p.play(0, level=0.5)
    p.tick()
    assert abs(s.live[0].amplitude - 0.5) < 1e-6      # vol 7/7 * level 0.5


def test_stop_flag_silences_everything():
    bank = Bank({1: sfx([note(24)] * 32, speed=1)},
                ((1, 0xFF, 0xFF, 0xFF, 4),))          # flags: stop at pattern end
    p, s, clk = make(bank)
    p.play(0)
    for _ in range(40):
        p.tick()
        clk.t += TICK
    assert len(s.live) == 0
    p.tick()
    assert len(s.events)                              # and it stays stopped
    n = len(s.events)
    clk.t += 10 * TICK
    p.tick()
    assert len(s.events) == n


def test_loop_flags_return_to_loop_start():
    bank = Bank({1: sfx([note(24)] * 32, speed=1), 2: sfx([note(30)] * 32, speed=1)},
                ((1, 0xFF, 0xFF, 0xFF, 1),            # loop start
                 (2, 0xFF, 0xFF, 0xFF, 2)))           # loop end
    p, s, clk = make(bank)
    p.play(0)
    seen = set()
    for _ in range(80):
        p.tick()
        seen.add(p._pattern)
        clk.t += TICK
    assert seen == {0, 1}                             # cycles 0 -> 1 -> 0, never stops


def test_arpeggio_mutates_frequency_without_retrigger():
    notes = [note(24, fx=6), note(28), note(31), note(36)]
    bank = Bank({1: sfx(notes, speed=8)}, ((1, 0xFF, 0xFF, 0xFF, 0),))
    p, s, clk = make(bank)
    p.play(0)
    p.tick()
    presses = sum(1 for e in s.events if e[0] == "press")
    f0 = s.live[0].frequency
    clk.t += 2 * TICK + 1                             # one arp sub-step (dur/4)
    p.tick()
    assert s.live[0].frequency != f0                  # pitch moved...
    assert sum(1 for e in s.events if e[0] == "press") == presses   # ...without a new press


def test_silent_host_is_noop():
    class Off:
        available = False
        synth = None
    bank = Bank({1: sfx([note(24)])}, ((1, 0xFF, 0xFF, 0xFF, 0),))
    p = M.Player(Off(), bank)
    assert not p.available
    p.play(0)
    p.tick()                                          # must not raise
    p.stop()


def test_own_synth_on_music_voice():
    # without the test hook the player builds its own synthesizer and puts it on the
    # mixer's MUSIC voice (voice 0) - never on the sfx synth
    bank = Bank({1: sfx([note(24)])}, ((1, 0xFF, 0xFF, 0xFF, 0),))
    host = FakeHost()
    p = M.Player(host, bank)
    assert host.mixer.voice[0].playing is p._synth
    assert p._synth is not host.synth
    assert p.available
