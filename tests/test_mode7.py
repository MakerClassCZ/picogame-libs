"""picogame_mode7.Camera: the pose -> Q16 conversion is cached across the strips of one frame,
and must feed Canvas.mode7 exactly what the straight per-call conversion did."""
import _bootstrap  # noqa: F401

import math

import picogame_mode7 as m7


class _Canvas:
    def __init__(self, width):
        self.width = width
        self.calls = []

    def mode7(self, *args):
        self.calls.append(args)


def _reference(canvas_w, fov, x, y, angle, horizon, height, y_off):
    q = m7._q16
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy * fov, dx * fov
    r0x, r0y = dx - px, dy - py
    r1x, r1y = dx + px, dy + py
    return (horizon, y_off, q(height), q(r0x), q(r0y),
            q((r1x - r0x) / canvas_w), q((r1y - r0y) / canvas_w), q(x), q(y))


POSES = [(2.5, 2.5, 0.0, 5.0), (2.5, 2.5, 0.0, 5.0), (3.1, 2.5, 0.7, 5.0), (3.1, 2.5, 0.7, 6.0),
         (3.1, 2.5, 0.7, 6.0), (12.0, 9.5, 5.1, 6.0), (2.5, 2.5, 0.0, 5.0)]


def test_draw_feeds_the_same_q16_args_as_the_direct_conversion():
    cam = m7.Camera(fov=0.66)
    cv = _Canvas(320)
    tex = object()
    for (x, y, a, h) in POSES:
        for strip in range(3):                       # the StripDraw calls it once per strip
            cam.draw(cv, tex, x, y, a, 90, h, y_off=strip * 8)
            got = cv.calls[-1]
            assert got[0] is tex
            assert got[1:] == _reference(320, 0.66, x, y, a, 90, h, strip * 8), (x, y, a, h, strip)


def test_cache_follows_fov_and_canvas_width():
    cam = m7.Camera(fov=0.66)
    tex = object()
    cv = _Canvas(320)
    cam.draw(cv, tex, 1.0, 2.0, 0.3, 90, 5.0)
    cam.fov = 0.9
    cam.draw(cv, tex, 1.0, 2.0, 0.3, 90, 5.0)
    assert cv.calls[-1][1:] == _reference(320, 0.9, 1.0, 2.0, 0.3, 90, 5.0, 0)
    narrow = _Canvas(160)
    cam.draw(narrow, tex, 1.0, 2.0, 0.3, 90, 5.0)
    assert narrow.calls[-1][1:] == _reference(160, 0.9, 1.0, 2.0, 0.3, 90, 5.0, 0)
