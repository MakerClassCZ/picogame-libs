"""Span-batch regression tests: the vspans-based draw paths (picogame_ray, fx.Fade, fx.Sky)
must produce byte-identical pixels to an independent NAIVE reference implementation written
here (per-column / per-cell / per-scanline fills). The reference code in this file is the
specification - it intentionally reimplements what the optimized paths replaced, so a bug in
run merging, span clipping, strip replay (x_off/y_off) or invalidation-driven rebuilds shows
up as a pixel diff. See tests/_recording.py for the shared recorder.
"""
import _bootstrap  # noqa: F401

from _recording import RecordingCanvas, SceneStub, strips_of

import picogame as pg
import picogame_ray
import picogame_fx as fx
import picogame_launcher

W, H = 320, 240

MAP = ["1111111111111111", "1000000000000001", "1002200001100001", "1002000001003301",
       "1000000001003001", "1001110000030001", "1000010000220001", "1033010000000001",
       "1030220001110001", "1030000001000001", "1000000001000001", "1111111111111111"]
WALLS = {1: (0x9999, 0x5555), 2: (0xAA55, 0x55AA), 3: (0x3C3C, 0x1E1E)}
SKY, FLOOR = 0x1111, 0x2222
POSES = [(2.5, 2.5, 0.0), (3.1, 2.5, 0.7), (2.5, 3.0, 2.2), (8.2, 6.5, 3.9), (12.0, 9.5, 5.1)]

SUBRECT = [(60, y, 180, min(8, H - y)) for y in range(40, 200, 8)]   # temporal dirty window


def _ray_reference(rc, cv, strips):
    """Naive per-column paint straight from the caster's top/bot/col arrays."""
    stride = rc.stride
    top, bot, col = rc.top, rc.bot, rc.col
    ncols = len(top)
    half = rc.sh >> 1
    for (vx, vy, vw, vh) in strips:
        v = cv.band(vx, vy, vw, vh)
        y0, y1 = vy, vy + vh
        if y1 <= half:
            v.fill_rect(0, 0, vw, vh, rc.sky)
        elif y0 >= half:
            v.fill_rect(0, 0, vw, vh, rc.floor)
        else:
            v.fill_rect(0, 0, vw, half - y0, rc.sky)
            v.fill_rect(0, half - y0, vw, y1 - half, rc.floor)
        for c in range(ncols):
            sx0 = c * stride
            sx1 = min(sx0 + stride, rc.sw)
            st = max(top[c], y0)
            sb = min(bot[c], y1)
            if sb > st and sx1 > vx and sx0 < vx + vw:
                v.fill_rect(max(sx0, vx) - vx, st - vy, min(sx1, vx + vw) - max(sx0, vx), sb - st, col[c])


def test_ray_vspans_matches_columns():
    for stride in (1, 2, 3):
        rc = picogame_ray.Raycaster(MAP, WALLS, SKY, FLOOR, stride=stride)
        for label, strips in (("sh8", strips_of(W, H, 8)), ("sh24", strips_of(W, H, 24)),
                              ("subrect", SUBRECT)):
            for i, (px, py, ang) in enumerate(POSES):
                rc.cast(px, py, ang, W, H)
                got = RecordingCanvas(W, H)
                for (vx, vy, vw, vh) in strips:
                    rc.draw(got.band(vx, vy, vw, vh), vx, vy, vw, vh)
                ref = RecordingCanvas(W, H)
                _ray_reference(rc, ref, strips)
                assert got.bytes() == ref.bytes(), \
                    "ray mismatch stride=%d %s pose=%d" % (stride, label, i)


def _fade_reference(f, cv, strips, lvl):
    """The original per-cell Bayer dither loop (screen-aligned cell grid)."""
    S = f.cell
    bayer = fx._BAYER
    for (vx, vy, vw, vh) in strips:
        v = cv.band(vx, vy, vw, vh)
        by0, by1 = vy // S, (vy + vh - 1) // S
        bx0, bx1 = f.X // S, (f.X + f.W - 1) // S
        for by in range(by0, by1 + 1):
            brow = bayer[by & 3]
            sy = by * S - vy
            for bx in range(bx0, bx1 + 1):
                if brow[bx & 3] < lvl:
                    v.fill_rect(bx * S - vx, sy, S, S, f.color)


def test_fade_runs_match_bayer():
    for lvl in (1, 4, 8, 12, 15, 16):
        f = fx.Fade(SceneStub(), W, H, color=0xF800, cell=8)
        f.set(lvl)
        for label, strips in (("sh8", strips_of(W, H, 8)), ("subrect", SUBRECT)):
            got = RecordingCanvas(W, H)
            for (vx, vy, vw, vh) in strips:
                f._draw(got.band(vx, vy, vw, vh), vx, vy, vw, vh)
            ref = RecordingCanvas(W, H)
            _fade_reference(f, ref, strips, int(f.level))
            assert got.bytes() == ref.bytes(), "fade mismatch lvl=%d %s" % (lvl, label)


def test_fade_rebuilds_on_level_change():
    f = fx.Fade(SceneStub(), W, H, color=0xF800, cell=8)
    f.set(4)
    strips = strips_of(W, H, 8)
    a = RecordingCanvas(W, H)
    for (vx, vy, vw, vh) in strips:
        f._draw(a.band(vx, vy, vw, vh), vx, vy, vw, vh)
    f.set(12)                                     # pattern must follow the level change
    b = RecordingCanvas(W, H)
    for (vx, vy, vw, vh) in strips:
        f._draw(b.band(vx, vy, vw, vh), vx, vy, vw, vh)
    ref = RecordingCanvas(W, H)
    _fade_reference(f, ref, strips, 12)
    assert b.bytes() == ref.bytes()
    assert a.bytes() != b.bytes()


def _sky_reference(s, cv, strips):
    """The original per-scanline LUT fill (full view width), incl. the band's y clip."""
    hh = s.h
    den = hh - 1 if hh > 1 else 1
    lut = [fx._lerp565(s.top, s.bottom, r / den) for r in range(hh)]
    y0 = s.y
    for (vx, vy, vw, vh) in strips:
        if vy + vh <= y0 or vy >= y0 + hh:        # the engine skips strips outside the layer
            continue
        s0 = max(vy, y0)
        s1 = min(vy + vh, y0 + hh)
        v = cv.band(vx, s0, vw, s1 - s0)
        for ly in range(s1 - s0):
            r = s0 + ly - y0
            v.fill_rect(0, ly, vw, 1, lut[r])


def test_sky_runs_match_lut():
    for (t, b, y, h) in ((0x001F, 0xF800, 0, H), (0x07E0, 0x0000, 0, 120), (0x1234, 0xABCD, 40, 100)):
        s = fx.Sky(SceneStub(), 0, y, W, h, t, b)
        for label, strips in (("sh8", strips_of(W, H, 8)), ("sh24", strips_of(W, H, 24))):
            got = RecordingCanvas(W, H)
            for (vx, vy, vw, vh) in strips:
                if vy + vh <= y or vy >= y + h:
                    continue
                s0 = max(vy, y)
                s1 = min(vy + vh, y + h)
                s._draw(got.band(vx, s0, vw, s1 - s0), vx, s0, vw, s1 - s0)
            ref = RecordingCanvas(W, H)
            _sky_reference(s, ref, strips)
            assert got.bytes() == ref.bytes(), \
                "sky mismatch %s top=%04x bot=%04x y=%d h=%d" % (label, t, b, y, h)


def test_sky_property_change_rebuilds():
    s = fx.Sky(SceneStub(), 0, 0, W, 120, 0x001F, 0xF800)
    strips = strips_of(W, 120, 8)
    a = RecordingCanvas(W, H)
    for (vx, vy, vw, vh) in strips:
        s._draw(a.band(vx, vy, vw, vh), vx, vy, vw, vh)
    s.top = 0x07E0                                 # property setter must invalidate + rebuild
    b = RecordingCanvas(W, H)
    for (vx, vy, vw, vh) in strips:
        s._draw(b.band(vx, vy, vw, vh), vx, vy, vw, vh)
    ref = RecordingCanvas(W, H)
    _sky_reference(s, ref, strips)
    assert b.bytes() == ref.bytes()
    assert a.bytes() != b.bytes()


def test_launcher_desc_wrap_cached():
    ui = picogame_launcher._UI.__new__(picogame_launcher._UI)
    ui.apps = [picogame_launcher.App("games/x", "code.py", "T", None, "A", "games", 1,
                                     "a long description that wraps across several lines for the cache test")]
    ui.sel = 0
    ui.pchars = 20
    ui._loaded_sel = -1
    ui.cur_icon = None
    ui.ensure_icon()
    assert ui._desc_lines == picogame_launcher._wrap(ui.apps[0].desc, ui.pchars)
    assert ui._loaded_sel == 0
