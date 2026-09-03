"""picogame_synth's shared waveform tables: built on FIRST USE through the module
__getattr__ and then cached in the module namespace (one build, one object, no per-read
call), None placeholders on an audio-less build, and the plain functions still make fresh
copies. Uses the shared bootstrap (works on dev + public sim)."""
import _bootstrap  # noqa: F401  (must be first: sets sys.path to the CURRENT libs + a sim)

import picogame_synth as snd

TABLES = ("SINE", "SAW", "TRIANGLE", "SQUARE", "NOISE")


def _forget(name):
    """Drop a cached table so the next read goes through __getattr__ again."""
    vars(snd).pop(name, None)


def test_tables_build_once_and_stay_the_same_object():
    for name in TABLES:
        _forget(name)
        assert name not in vars(snd)
        first = getattr(snd, name)
        assert name in vars(snd), name                     # cached into the module namespace
        assert getattr(snd, name) is first, name           # the same object, not a rebuild
        assert len(first) == snd._LEN and first.typecode == "h", name


def test_from_import_and_getattr_default_go_through_the_lazy_path():
    _forget("SQUARE")
    from picogame_synth import SQUARE
    assert SQUARE is snd.SQUARE
    assert getattr(snd, "NOT_A_TABLE", None) is None
    try:
        snd.NOT_A_TABLE
    except AttributeError:
        pass
    else:
        raise AssertionError("unknown names must still raise AttributeError")


def test_lazy_table_equals_the_builder_output_and_the_builder_makes_fresh_copies():
    for name, build in (("SINE", snd.sine), ("SAW", snd.saw), ("TRIANGLE", snd.triangle),
                        ("SQUARE", snd.square), ("NOISE", snd.noise)):
        shared = getattr(snd, name)
        fresh = build()
        assert fresh is not shared and fresh == shared, name


def test_audio_less_build_resolves_tables_to_none():
    was = snd.AVAILABLE
    try:
        snd.AVAILABLE = False
        for name in TABLES:
            _forget(name)
            assert getattr(snd, name) is None, name
    finally:
        snd.AVAILABLE = was
        for name in TABLES:                                # rebuild for the other test modules
            _forget(name)
            assert getattr(snd, name) is not None, name


def test_drone_default_waveform_resolves_the_lazy_saw():
    """Drone(synth) without waveform= must build/reach SAW itself: a bare `SAW` global inside
    the module is NOT routed through the module __getattr__, so it raised NameError until the
    caller happened to touch snd.SAW first."""
    _forget("SAW")

    class _Synth:
        def press(self, note): pass
        def release(self, note): pass

    drone = snd.Drone(_Synth())
    assert "SAW" in vars(snd)                              # the default build went through the lazy path
    if snd.AVAILABLE:
        assert drone.note.waveform is snd.SAW


def test_star_import_binds_the_lazy_tables():
    for name in TABLES:
        _forget(name)
    ns = {}
    exec("from picogame_synth import *", ns)
    for name in TABLES:
        assert name in ns and ns[name] is getattr(snd, name), name
    assert "Synth" in ns and "Drone" in ns and "RAMP" in ns
    for name in snd.__all__:                               # every advertised name really resolves
        getattr(snd, name)


def test_deinit_releases_output_mixer_and_synth_once_and_goes_silent():
    """The twin of picogame_audio.Audio.deinit(): the output (PWM pin / I2S bus) is what a
    second Synth() or Audio() in the same program needs back. Output first (it plays the
    mixer), then the mixer, then the synthesizer; a second deinit() touches nothing; after
    it the instance is the silent no-op, so a game's sfx()/music() calls stay call-safe."""
    if not snd.AVAILABLE:
        s = snd.Synth()
        s.deinit()
        assert s.available is False
        return
    s = snd.Synth()
    assert s.available, "the sim's PWM shim must yield a working Synth"
    calls = []

    class _Dev:
        def __init__(self, name):
            self.name = name

        def deinit(self):
            calls.append(self.name)

        def play(self, *a, **k):
            pass

        def stop(self, *a, **k):
            pass

    s.audio, s.mixer, s.synth = _Dev("out"), _Dev("mixer"), _Dev("synth")
    s._seq = [(0, None)]
    s.deinit()
    assert calls == ["out", "mixer", "synth"]
    assert s.available is False and s._seq is None and s._last_sfx is None
    assert isinstance(s.audio, snd._Null) and isinstance(s.mixer, snd._Null)
    s.deinit()                                  # idempotent: the fakes are gone, nothing to call
    assert calls == ["out", "mixer", "synth"]
    assert s.sfx(snd.note(60)) is False         # a deinit'd Synth is the no-op: dropped, call-safe
    s.music(snd.load_midi)                      # any object: the _Null voice takes it
    s.stop_music()
    s.mute(True)


def test_deinit_on_a_failed_init_synth_is_a_no_op():
    """A Synth that degraded at construction (tight heap / pin in use) owns nothing; deinit()
    must not touch the _Null stand-ins or flip any state."""
    if not snd.AVAILABLE:
        return
    import picogame_audioout

    real = picogame_audioout.make_output

    def boom(*a, **k):
        raise RuntimeError("no audio output")

    picogame_audioout.make_output = boom
    try:
        s = snd.Synth()
    finally:
        picogame_audioout.make_output = real
    assert s.available is False
    s.deinit()
    assert s.available is False and isinstance(s.audio, snd._Null)
