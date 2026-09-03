"""picogame_game.open_framebuffer on a DVI board, with the picodvi stack faked: the reuse check
and the failed-switch recovery must cover the colour depth, not only the size."""
import _bootstrap  # noqa: F401

import sys
import types

import picogame_game as G


class _FakeFB:
    built = []                                       # every (w, h, depth) constructed
    fail_on = None                                   # (w, h, depth) that raises MemoryError

    def __init__(self, w, h, color_depth=16, **pins):
        if _FakeFB.fail_on == (w, h, color_depth):
            raise MemoryError("no scanout")
        self.width, self.height, self.color_depth = w, h, color_depth
        _FakeFB.built.append((w, h, color_depth))


class _FakeDisplay:
    """CircuitPython keeps its displays in a static array: a rebuilt display is the SAME object
    (same id()) wearing a new framebuffer. The fake models that with one reused slot."""
    _slot = None

    def __init__(self, fb, auto_refresh=False):
        self.framebuffer = fb
        self.width, self.height = fb.width, fb.height

    @classmethod
    def new(cls, fb, auto_refresh=False):
        if cls._slot is None:
            cls._slot = cls(fb, auto_refresh)
        else:
            cls._slot.__init__(fb, auto_refresh)
        return cls._slot


def _dvi_stack():
    """Install fake board / picodvi / framebufferio / displayio / supervisor; return a restore()."""
    saved = {k: sys.modules.get(k) for k in ("board", "picodvi", "framebufferio", "displayio",
                                             "supervisor")}
    board = types.ModuleType("board")
    for pin in ("CKP", "CKN", "D0P", "D0N", "D1P", "D1N", "D2P", "D2N"):
        setattr(board, pin, pin)
    picodvi = types.ModuleType("picodvi")
    picodvi.Framebuffer = _FakeFB
    fbio = types.ModuleType("framebufferio")
    fbio.FramebufferDisplay = _FakeDisplay.new
    _FakeDisplay._slot = None
    dio = types.ModuleType("displayio")
    dio.released = 0

    def release_displays():
        dio.released += 1
        sup.runtime.display = None
    dio.release_displays = release_displays
    sup = types.ModuleType("supervisor")
    sup.runtime = types.SimpleNamespace(display=None)
    sys.modules.update(board=board, picodvi=picodvi, framebufferio=fbio, displayio=dio,
                       supervisor=sup)
    _FakeFB.built = []
    _FakeFB.fail_on = None
    G._TARGET.clear()                                # the id(display)-keyed memos
    G._RESOLVED.clear()

    def restore():
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return sup, dio, restore


def test_same_size_other_depth_rebuilds_instead_of_reusing():
    sup, dio, restore = _dvi_stack()
    try:
        d16 = G.open_framebuffer(320, 240)               # default depth for 320x240 = 16
        assert d16.framebuffer.color_depth == 16 and sup.runtime.display is d16
        assert dio.released == 1
        assert G.open_framebuffer(320, 240) is d16      # same mode -> reused, no realloc
        assert G.open_framebuffer(320, 240, color_depth=16) is d16
        G._TARGET[id(d16)] = (d16, "stale-16")          # a memoized target() / resolve_display()
        G._RESOLVED[id(d16)] = (d16, "stale-16", True)   # for the mode we are about to leave
        d8 = G.open_framebuffer(320, 240, color_depth=8)
        assert d8 is d16 and d8.framebuffer.color_depth == 8    # the static slot, rebuilt
        assert sup.runtime.display is d8 and dio.released == 2
        assert not G._TARGET and not G._RESOLVED          # the memos cannot alias the old buffer
        assert G.open_framebuffer(320, 240, color_depth=8) is d8
        assert G.open_framebuffer(320, 240).framebuffer.color_depth == 16   # back to the default
        assert _FakeFB.built == [(320, 240, 16), (320, 240, 8), (320, 240, 16)]
    finally:
        restore()


def test_failed_switch_restores_the_exact_previous_depth():
    sup, dio, restore = _dvi_stack()
    try:
        d8 = G.open_framebuffer(320, 240, color_depth=8)
        _FakeFB.fail_on = (640, 480, 8)
        try:
            G.open_framebuffer(640, 480)
        except MemoryError as e:
            assert "kept 320x240" in str(e)
        else:
            assert False, "the failed switch must raise"
        back = sup.runtime.display
        assert (back.width, back.height) == (320, 240)
        assert back.framebuffer.color_depth == 8         # not the 16 the size formula would pick
        assert _FakeFB.built == [(320, 240, 8), (320, 240, 8)]
    finally:
        restore()
