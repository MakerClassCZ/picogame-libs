"""Shared pixel-recording canvas for parity/regression tests.

RecordingCanvas mimics the drawing surface a StripDraw callback receives (fill_rect, vspans,
rect, text, blit, clear) but records every pixel into a plain bytearray, so two render paths
can be byte-compared. `band(vx, vy, vw, vh)` returns a view that clips to the band size and
writes into the parent at the band's offset - exactly how the engine hands a strip view to a
callback. Text/blit are deterministic stamps (not real glyphs): good for comparing two code
paths, not for comparing against the real renderer (use the golden render tests for that).

SceneStub satisfies helpers that only need scene.add()/invalidate() (picogame_fx overlays).
"""


class RecordingCanvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.width = w
        self.height = h
        self.px = bytearray(w * h * 2)
        self._off = (0, 0)
        self.parent = self

    def band(self, vx, vy, vw, vh):
        c = RecordingCanvas.__new__(RecordingCanvas)
        c.w = vw
        c.h = vh
        c.width = vw
        c.height = vh
        c._off = (vx, vy)
        c.parent = self
        return c

    def bytes(self):
        return bytes(self.px)

    def clear(self, color):
        self.fill_rect(0, 0, self.w, self.h, color)

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        ox, oy = self._off
        p = self.parent
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        for yy in range(y0, y1):
            base = ((yy + oy) * p.w + ox)
            for xx in range(x0, x1):
                i = (base + xx) * 2
                p.px[i] = hi
                p.px[i + 1] = lo

    def vspans(self, x0s, x1s, tops, bots, colors, n, x_off=0, y_off=0):
        # mirrors the C binding: translate, reject, then fill_rect per span
        for i in range(n):
            t = tops[i] + y_off
            b = bots[i] + y_off
            if b <= 0 or t >= self.h or b <= t:
                continue
            x0 = x0s[i] + x_off
            x1 = x1s[i] + x_off
            if x1 <= 0 or x0 >= self.w or x1 <= x0:
                continue
            self.fill_rect(x0, t, x1 - x0, b - t, colors[i])

    def rect(self, x, y, w, h, color):
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)

    def text(self, x, y, s, color, font, bg=None):
        # deterministic per-char stamp; identical for identical (x, y, s, color)
        for i, ch in enumerate(s):
            self.fill_rect(x + i * 6, y, 1, 1, (color ^ (ord(ch) << 3)) & 0xFFFF)

    def blit(self, bm, x, y, frame=0, flip_x=False, flip_y=False):
        self.fill_rect(x, y, bm.width, bm.height, 0x5A5A)


class SceneStub:
    def add(self, *a, **k):
        pass

    def remove(self, *a, **k):
        pass

    def invalidate(self, *a, **k):
        pass


def strips_of(w, h, sh):
    """Full-width strip layout (vx, vy, vw, vh) like the engine's per-strip callbacks."""
    return [(0, y, w, min(sh, h - y)) for y in range(0, h, sh)]
