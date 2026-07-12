"""picogame_sfx (signature theme) + the channel arbitration it rides on (picogame_synth.Synth
sfx/sfx_seq/tick/priority/window). Uses the shared bootstrap (works on dev + public sim);
each check is a normal test_* function that raises on failure - no sys.exit that could mask
earlier modules' failures (finding S-H4)."""
import _bootstrap  # noqa: F401  (must be first: sets sys.path to the CURRENT libs + a sim)

import synthio
import picogame_synth as snd
import picogame_sfx


class Spy(snd.Synth):
    """A real (stub-backed) Synth that records every voice actually emitted."""

    def __init__(self):
        super().__init__()
        self.log = []

    def _emit(self, n):
        self.log.append(n)
        super()._emit(n)


def test_raw_sfx_backcompat():
    s = Spy()
    assert s.sfx(snd.note(72)) is True and len(s.log) == 1


def test_priority_window_drops_lower():
    s = Spy()
    s.sfx(snd.note(60), priority=40, window=10)
    s.log = []
    assert s.sfx(snd.note(62), priority=20) is False and not s.log
    assert s.sfx(snd.note(64), priority=40) and s.log
    for _ in range(10):
        s.tick()
    s.log = []
    assert s.sfx(snd.note(66), priority=20) and s.log


def test_sequencer_timing():
    s = Spy()
    a, b, c = snd.note(60), snd.note(62), snd.note(64)
    s.sfx_seq([(0, a), (2, b), (4, c)])
    assert s.log == [a]
    s.tick(); s.tick()
    assert s.log == [a, b]
    s.tick(); s.tick()
    assert s.log == [a, b, c]


def test_new_sound_cancels_sequence_tail():
    s = Spy()
    a, b, c = snd.note(60), snd.note(62), snd.note(64)
    s.sfx_seq([(0, a), (4, b)])
    s.sfx(c)
    s.log = []
    for _ in range(6):
        s.tick()
    assert not s.log


def test_kit_available_and_all_fire():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    assert kit.available
    for name in ("blip", "coin", "powerup", "zap", "pew", "jump", "hit", "hurt", "boom", "explosion"):
        before = len(s.log)
        getattr(kit, name)()
        for _ in range(30):
            kit.tick()
        assert len(s.log) > before, name


def test_explosion_window_drops_lower_then_recovers():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    hitv, boomv = kit._v["hit"][0][1], kit._v["boom"][0][1]
    kit.explosion(); kit.hit(); kit.boom()
    assert hitv not in s.log and boomv not in s.log
    for _ in range(19):
        kit.tick()
    kit.hit()
    assert s.log[-1] is hitv


def test_hurt_interrupts_hit_not_reverse():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    hurtv = kit._v["hurt"][0][1]
    kit.hit(rotate=False)
    kit.hurt()
    kit.hit(rotate=False)
    assert s.log[-1] is hurtv and s.log.count(kit._v["hit"][0][1]) == 1


def test_hit_pitch_rotation():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    f = []
    for _ in range(3):
        kit.hit()
        f.append(kit._rot_note.frequency)
    assert len(set(f)) == 3
    prev = kit._rot_note.frequency
    kit.hit(rotate=False)
    assert kit._rot_note.frequency == prev


def test_explosion_is_single_smear_voice():
    kit = picogame_sfx.Kit(Spy())
    xv = kit._v["explosion"][0][1]
    assert isinstance(xv, synthio.Note) and isinstance(xv.bend, synthio.LFO)


def test_failed_synth_is_true_noop():
    s = Spy()
    s.available = False
    assert s.sfx(snd.note(60)) is False
    assert s.sfx_seq([(0, snd.note(60))]) is False and s._seq is None


def test_protected_window_does_not_leak():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    hitv = kit._v["hit"][0][1]
    kit.boom(); kit.coin(); kit.hit(rotate=False)
    assert hitv in s.log


def test_sequencer_is_zero_copy():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    kit.coin()
    assert s._seq is kit._v["coin"]


def test_dropped_hits_do_not_advance_rotation():
    s = Spy()
    kit = picogame_sfx.Kit(s)
    kit.explosion()
    r0 = kit._rot
    for _ in range(5):
        kit.hit()
    assert kit._rot == r0


def test_set_levels_while_muted_stays_silent():
    s = Spy()
    s.mute(True)
    s.set_levels(sfx=0.2)
    assert s.mixer.voice[1].level == 0.0
    s.mute(False)
    assert abs(s.mixer.voice[1].level - 0.2) < 1e-9
    assert abs(s.sfx_level - 0.2) < 1e-9


def test_synth_exposes_volume_attrs():
    s = Spy()
    assert hasattr(s, "sfx_level") and hasattr(s, "music_level")
