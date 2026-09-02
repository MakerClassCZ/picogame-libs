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
