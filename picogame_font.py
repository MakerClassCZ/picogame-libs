# picogame text helper: render strings into picogame.Bitmap using ANY
# fontio font (e.g. the bundled terminalio.FONT) - no extra assets, no reflash.
#
# The builtin font is a monospace tile sheet. get_glyph(cp) returns a Glyph
# object whose `.bitmap` is the (shared) 1-bit sheet and `.tile_index` locates
# the glyph; get_bounding_box() is the cell size.
#
# Rendering composes the glyphs into an 8-bit paletted Bitmap (index 0 = bg,
# index 1 = fg). With an opaque bg, redrawing a Label fully overwrites the old
# text, so score/HUD updates need no separate clear.

import array


def render_text(pg, font, text, fg, bg=None):
    """Render `text` (any fontio font) -> the tuple `(bmp, w, h)` (a PAL8 picogame.Bitmap + its
    pixel size). Use as `bmp, w, h = render_text(...)`. fg/bg are wire colors from pg.rgb565();
    bg=None makes the background transparent (index 0). (See render_text_pal to also get the palette.)"""
    bmp, w, h, _pal = render_text_pal(pg, font, text, fg, bg)
    return bmp, w, h


def render_text_pal(pg, font, text, fg, bg=None):
    """Like render_text, but ALSO returns the PAL8 palette as an array('H'):
    (bmp, w, h, palette). Keep the palette ref and mutate palette[1] (the fg)
    for a colour shimmer without rebuilding the bitmap - the C Bitmap reads the
    same buffer, so the change shows up immediately (Bitmap.palette is not a
    Python attribute on device, so mutate THIS array, not bmp.palette)."""
    fw, fh = font.get_bounding_box()[:2]
    n = len(text)
    w = fw * max(1, n)
    h = fh
    data = bytearray(w * h)  # all index 0 (bg)
    for i in range(n):
        g = font.get_glyph(ord(text[i]))
        if g is None:
            continue
        sheet = g.bitmap            # shared 1-bit tile sheet
        tiles_per_row = sheet.width // fw
        ti = g.tile_index
        tx = (ti % tiles_per_row) * fw
        ty = (ti // tiles_per_row) * fh
        ox = i * fw
        for gy in range(fh):
            row = gy * w + ox
            sy = ty + gy
            for gx in range(fw):
                if sheet[tx + gx, sy]:
                    data[row + gx] = 1
    if bg is None:
        palette = array.array("H", [pg.rgb565(0, 0, 0), fg])
        transparent = 0
    else:
        palette = array.array("H", [bg, fg])
        transparent = None
    bmp = pg.Bitmap(data, w, h, format=pg.PAL8, palette=palette,
                    frames=1, stride=w, transparent=transparent)
    return bmp, w, h, palette


class Label:
    """A positioned text label drawn immediately to the display (good for HUD).
    Re-renders only when the text changes; draw() repaints just its rectangle."""

    def __init__(self, pg, font, x, y, fg, bg):
        self.pg = pg
        self.font = font
        self.x = x
        self.y = y
        self.fg = fg
        self.bg = bg  # opaque background so updates overwrite cleanly
        self.text = None
        self.sprite = None
        self._slist = [None]   # reused 1-element list for draw() (no per-frame alloc)
        self.w = 0
        self.h = 0

    def move(self, x, y):
        """Reposition the label (forces a re-render at the new spot on next set/draw)."""
        self.x = x
        self.y = y
        self.text = None

    def set(self, text):
        text = str(text)
        if text == self.text:
            return False
        self.text = text
        bmp, w, h = render_text(self.pg, self.font, text, self.fg, self.bg)
        self.w, self.h = w, h
        self.sprite = self.pg.Sprite(bmp, self.x, self.y)
        self._slist[0] = self.sprite
        return True

    def draw(self, display, buffer):
        if self.sprite is None:
            return
        self.pg.render(display, self._slist, buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)
