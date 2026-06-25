# picogame_ui: the UI scaffolding the ergonomics review found missing - a
# camera-independent HUD label, a multi-line text box, and a cursor menu. Built on
# the new Scene `fixed` layer (SceneLabel) + the universal pg.render path (TextBox/
# Menu). See ENGINE_ERGONOMICS.md.
#
#   import picogame_ui as ui
#   score = ui.SceneLabel(scene, pg, font, 4, 4, white, black)   # pinned over a scroll
#   score.set("SCORE 1200")                                    # drawn by scene.refresh()
#
#   box = ui.TextBox(pg, font, 8, 180, 304, 52, white, navy)
#   box.draw(board.DISPLAY, bufA, ["Villager:", "Beware the slimes."])
#
#   menu = ui.Menu(pg, font, 8, 160, ["ATTACK", "MAGIC", "FLEE"], white, navy)
#   pick = menu.tick(btn); menu.draw(board.DISPLAY, bufA)      # pick>=0 on confirm

import picogame_font

LINE_H = 12

# tick() return values for Menu / SceneMenu / GridCursor: an index/cell on A (confirm), CANCEL on B
# (back), or None while still navigating. Text menus can also exit via a "Back" item; graphical/tile
# menus use B (the cancel). Pick whichever fits - both are supported.
CANCEL = -2


class SceneLabel:
    """One line of text that lives IN the scene as a `fixed` (camera-independent) layer, so it stays
    put while the world scrolls and scene.refresh() paints it (no extra draw call). The scene-layer
    twin of the immediate picogame_font.Label. Updates by swapping its sprite's bitmap.

    NAMING: scene-layer widgets are `Scene*` (SceneLabel / SceneBox / SceneMenu) - use them OVER a
    live scene (one still calling scene.refresh()). Their immediate twins (Label / TextBox / Menu)
    draw via pg.render and are for a STATIC screen you render entirely yourself."""

    def __init__(self, scene, pg, font, x, y, fg, bg):
        self.pg = pg
        self.font = font
        self.fg = fg
        self.bg = bg
        bmp, _, _, self._buf, _ = picogame_font._render_into(pg, font, " ", fg, bg, None)
        self.sprite = pg.Sprite(bmp, x, y)
        scene.add(self.sprite, fixed=True)  # fixed = camera-independent
        self._text = None

    def set(self, text):
        text = str(text)
        if text == self._text:
            return
        self._text = text
        if not text.strip():                # empty/blank -> hide fully, leaving no bg patch
            self.sprite.visible = False     # (dirty-rect erases the old text box cleanly)
            return
        self.sprite.visible = True
        bmp, _, _, self._buf, _ = picogame_font._render_into(self.pg, self.font, text, self.fg, self.bg, self._buf)
        self.sprite.bitmap = bmp            # swap (dirty-rect handles old/new bounds); buffer reused

    def prewarm(self, longest):
        """Reserve the glyph buffer NOW, on the fresh/contiguous startup heap, so it isn't first
        allocated later on a fragmented one (a MemoryError risk). Renders nothing visible; later set()
        calls reuse this buffer instead of re-allocating.

        Pass the LONGEST line as a STRING (recommended): it sizes the buffer AND warms the font glyph
        cache for exactly those characters - so a banner shown only at game-over allocates nothing then.
        Pass an INT char-count to only size the buffer (when you know the width but not the glyphs; the
        glyphs are then cached on the first set())."""
        if isinstance(longest, int):
            fw, fh = self.font.get_bounding_box()[:2]
            need = fw * max(1, longest) * fh
            if self._buf is None or len(self._buf) < need:
                self._buf = bytearray(need)
        else:
            _, _, _, self._buf, _ = picogame_font._render_into(
                self.pg, self.font, str(longest), self.fg, self.bg, self._buf)
        self.sprite.visible = False         # nothing is shown


class SceneBox:
    """A multi-line text box that lives IN the scene: a Canvas panel + SceneLabel rows as FIXED
    layers, toggled with show()/hide(). Because the single scene.refresh() per frame paints it, it's
    ONE present (no flicker) and composites correctly over a scrolling / animated world.

    The scene-layer twin of the immediate `TextBox`. Use SceneBox for a dialog/status box OVER a LIVE
    scene (overworld talk, in-game popup). Use `TextBox` (immediate, pg.render) only on a STATIC
    screen with no scene.refresh under it - over a live scene it fights scene.refresh and flickers.

        dlg = ui.SceneBox(scene, pg, font, 8, H - 70, W - 16, 62, fg, bg, nlines=3)
        dlg.show(["Villager:", "Beware the slimes", "in the tall grass."])   # call ONCE
        ...                              # scene.refresh() each frame paints it; no per-frame draw
        dlg.hide()                       # when dismissed
    """

    def __init__(self, scene, pg, font, x, y, w, h, fg, bg, nlines=3,
                 key=None, border=None):
        self.pg = pg
        self.w, self.h = w, h
        self.bg = bg
        self.border = border
        self.key = key if key is not None else pg.rgb565(255, 0, 255)   # transparent-when-hidden
        self.box = pg.Canvas(w, h, transparent=self.key)
        self.box.move(x, y)
        self.box.clear(self.key)
        scene.add(self.box, fixed=True)                                 # fixed: ignore the camera
        self.labels = [SceneLabel(scene, pg, font, x + 8, y + 7 + i * LINE_H, fg, bg)
                       for i in range(nlines)]
        self.hide()

    def show(self, lines):
        """Fill the panel + set the text, then reveal it. Call once (not per frame) - the scene
        paints it from then on."""
        self.box.clear(self.bg)
        if self.border is not None:
            self.box.frame3d(0, 0, self.w, self.h, self.border, self.bg)
        for i, lb in enumerate(self.labels):
            lb.set(lines[i] if i < len(lines) else " ")

    def hide(self):
        self.box.clear(self.key)                                        # panel -> fully transparent
        for lb in self.labels:
            lb.set("")                                                  # SceneLabel("") hides the sprite

    def set_line(self, i, text):
        """Update ONE line in place - no Canvas/border redraw. Lets a menu repaint just the rows
        whose cursor marker changed (each SceneLabel.set is its own small dirty rect)."""
        if 0 <= i < len(self.labels):
            self.labels[i].set(text)


class HudBar:
    """A HUD strip drawn OUTSIDE the scene, in a region the scene reserves with
    Scene(..., top=/bottom=). The scene never paints there, so the strip costs nothing
    per frame and keeps no buffer of its own - `redraw()` fills the background and blits
    its sprites via pg.render, and you call it only when the HUD changes (score, lives).

    Add Sprites (hearts, gauges) with add(); add text with label(); update via .visible /
    swap / set_text(), then redraw(). `buffer` is any scratch strip buffer (e.g. the
    scene's bufA). Background is a flat colour (for a gradient bar use a Canvas instead)."""

    def __init__(self, pg, display, buffer, x, y, w, h, bg):
        self.pg = pg
        self.display = display
        self.buffer = buffer
        self.x, self.y, self.w, self.h = x, y, w, h
        self.bg = bg
        self.sprites = []

    def add(self, sprite):
        self.sprites.append(sprite)
        return sprite

    def label(self, font, x, y, fg, text=" "):
        """A text sprite stored in this bar; update it with set_text(), then redraw()."""
        text = str(text)
        bmp, _, _, data, _ = picogame_font._render_into(self.pg, font, text, fg, self.bg, None)
        s = self.pg.Sprite(bmp, x, y)
        s.data = (font, fg, data, text)     # (font, fg, reused glyph buffer, last rendered text)
        self.sprites.append(s)
        return s

    def set_text(self, sprite, text):
        font, fg, buf, last = sprite.data
        text = str(text)
        if text == last:                    # value unchanged -> skip the render entirely (callers may
            return                          # refresh the HUD often for other widgets; don't re-rasterize)
        bmp, _, _, data, _ = picogame_font._render_into(self.pg, font, text, fg, self.bg, buf)
        sprite.data = (font, fg, data, text)
        sprite.bitmap = bmp

    def redraw(self):
        """Repaint the strip (flat bg + visible sprites). Call only on HUD changes."""
        # pg.render already skips invisible sprites, so pass the list directly (no temp list).
        self.pg.render(self.display, self.sprites, self.buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)


class TextBox:
    """A screen-space multi-line box: a filled rect (via pg.render) + text lines.
    For dialog/battle/menu screens that aren't a scrolling scene."""

    def __init__(self, pg, font, x, y, w, h, fg, bg, maxlines=6):
        self.pg = pg
        self.x, self.y, self.w, self.h = x, y, w, h
        self.bg = bg
        self._drawn = None                  # last drawn lines - skip the repaint if unchanged
        self._sprites = []                  # reused row-sprite list for the one-pass render
        self._labels = [picogame_font.Label(pg, font, x + 6, y + 6 + i * LINE_H, fg, bg)
                        for i in range(maxlines)]

    def draw(self, display, buffer, lines, force=False):
        # callers often draw every frame with the SAME text (a static dialog/box) -> skip when
        # nothing changed. When we DO draw, render the background AND every text row in ONE
        # pg.render pass (like HudBar.redraw): a SINGLE present, so there's no blank-fill flash
        # and no row-by-row pop-in. force=True repaints even if unchanged (the screen under us
        # was wiped, e.g. a full-screen pg.render, so our pixels are gone).
        if not force and lines == self._drawn:
            return
        self._drawn = list(lines)
        sprites = self._sprites
        del sprites[:]
        for i, ln in enumerate(lines):
            if i >= len(self._labels):
                break
            lb = self._labels[i]
            lb.set(ln)                      # rebuilds only on change; position is fixed (__init__)
            if lb.sprite is not None:
                sprites.append(lb.sprite)
        self.pg.render(display, sprites, buffer,
                       self.x, self.y, self.x + self.w, self.y + self.h, background=self.bg)

    def draw_line(self, display, buffer, i, text):
        """Repaint a SINGLE row in place (its label rect only) - lets a menu update just the rows
        that changed (cursor move) without touching the rest of the box. Atomic per row: Label.draw
        is one pg.render (bg + glyphs), so no flash."""
        lb = self._labels[i]
        lb.set(text)
        lb.draw(display, buffer)


def _menu_step(btn, sel, top, rows, n, paged):
    """Shared cursor + scroll/paging math for both menus (immediate Menu and scene-layer SceneMenu),
    so they navigate identically. Returns (new_sel, new_top, action) where action is "A" (confirm),
    "B" (cancel) or None (still navigating). paged: window jumps a whole page at the edges (cheap -
    most moves keep `top`); else a line scroll (a full repaint per step)."""
    if n == 0:                                        # empty menu -> nothing to navigate
        return sel, top, None
    if btn.repeat(btn.DOWN):                          # auto-repeat while held
        sel = (sel + 1) % n
    elif btn.repeat(btn.UP):
        sel = (sel - 1) % n
    if paged:
        if sel < top or sel >= top + rows:
            top = (sel // rows) * rows
    elif sel < top:
        top = sel
    elif sel >= top + rows:
        top = sel - rows + 1
    if btn.just_pressed(btn.A):
        return sel, top, "A"
    if btn.just_pressed(btn.B):
        return sel, top, "B"
    return sel, top, None


class Menu:
    """A cursor menu over a TextBox. `tick(btn)` returns the chosen index on A (confirm),
    `ui.CANCEL` on B (back), or None while navigating. D-pad UP/DOWN navigate with auto-repeat
    when held. If there are more items than `rows`, the list scrolls to keep the cursor in
    view (default `rows=None` shows them all - no scroll). `draw()` renders a '>' marker.

    `paged=True` (default) advances the window a whole PAGE at a time at the edges instead of
    one line: moving within a page is a cheap 2-row repaint, and only crossing a page boundary
    triggers a full-box repaint. On this hardware a line-by-line scroll repaints the WHOLE box
    every step (the panel can't be hardware-scrolled and the display can't be read back), so
    paging is dramatically snappier on long, near-full-screen lists. Pass paged=False for the
    classic line scroll (smoother-looking, but a full repaint per step) on short lists."""

    def __init__(self, pg, font, x, y, items, fg, bg, *, title=None, rows=None, width=None,
                 paged=True):
        self.items = list(items)
        self.title = title
        self.sel = 0
        self.top = 0                                  # first visible item (scroll window)
        self.paged = paged
        self.rows = min(rows or len(self.items), len(self.items))
        n = self.rows + (1 if title else 0)
        # box width: pass `width` when you need it (long labels, full-screen lists); the
        # default heuristic (~11 px/char) over-sizes for a narrow font and can run off-screen.
        w = width if width else max(60, 11 * max((len(s) for s in self.items), default=4) + 16)
        self.box = TextBox(pg, font, x, y, w, 10 + n * LINE_H, fg, bg, maxlines=n)
        self._title_rows = 1 if title else 0
        self._drawn = None         # (sel, top) last drawn - detects move vs. scroll vs. idle

    def tick(self, btn):
        self.sel, self.top, a = _menu_step(btn, self.sel, self.top, self.rows, len(self.items), self.paged)
        return self.sel if a == "A" else (CANCEL if a == "B" else None)

    def _row_text(self, i):
        return ("> " if i == self.sel else "  ") + self.items[i]

    def draw(self, display, buffer, force=False):
        # draw() is typically called every frame. Repaint only what actually changed:
        #   nothing  -> return (no render at all)
        #   cursor moved within the window -> repaint just the 2 affected rows
        #   window scrolled (or first draw) -> repaint the whole box
        # force=True repaints the whole box unconditionally - pass it when the screen UNDER the
        # menu was wiped (e.g. a full-screen pg.render), since the incremental paths assume the
        # menu's pixels are still on screen.
        if force:
            self._drawn = None
        key = (self.sel, self.top)
        if key == self._drawn:
            return
        t = self._title_rows
        if self._drawn is None or self._drawn[1] != self.top:   # first draw or scroll
            lines = [self.title] if self.title else []
            for i in range(self.top, min(self.top + self.rows, len(self.items))):
                lines.append(self._row_text(i))
            self.box.draw(display, buffer, lines, force=force)   # forward force: after a wipe the
            #          box's pixels are gone, so it MUST repaint even if its lines are unchanged
        else:                                                   # moved within the window
            for s in (self._drawn[0], self.sel):
                self.box.draw_line(display, buffer, t + (s - self.top), self._row_text(s))
        self._drawn = key


class SceneMenu:
    """A cursor menu that lives IN the scene (built on `SceneBox` - a Canvas + SceneLabel rows as FIXED
    layers). Use it OVER a LIVE scene - one that calls `scene.refresh()` every frame (battle
    actions, an in-game choice popup). Because the scene paints it, the fast Display can't push its
    strips over it and erase it (the trap that makes an immediate `Menu` vanish over a live scene).

        m = ui.SceneMenu(scene, pg, font, 96, 64, ["Fireball", "Rally"], WHITE, NAVY, title="CAST")
        m.show()                          # show it
        ...each frame:  pick = m.tick(btn)     # >=0 index on A, ui.CANCEL on B, None navigating
        if pick is not None: m.hide()          # hide on confirm/cancel
        # scene.refresh() paints it - no draw() call.

    Same navigation/paging as `Menu` (shared `_menu_step`). Pick `Menu` instead for a STATIC screen
    drawn entirely with pg.render (no scene.refresh under it)."""

    def __init__(self, scene, pg, font, x, y, items, fg, bg, title=None, rows=None, width=None,
                 border=None, paged=True):
        self.items = list(items)
        self.title = title
        self.sel = 0
        self.top = 0
        self.paged = paged
        self.rows = max(1, min(rows or len(self.items), len(self.items)))
        self._t = 1 if title else 0
        n = self.rows + self._t
        w = width if width else max(60, 11 * max((len(s) for s in self.items), default=4) + 16)
        self.panel = SceneBox(scene, pg, font, x, y, w, 10 + n * LINE_H, fg, bg, nlines=n, border=border)
        self.active = False

    def _clamp(self, sel):
        return max(0, min(sel, len(self.items) - 1))

    def _row_text(self, i):
        return ("> " if i == self.sel else "  ") + self.items[i]

    def _render_full(self):
        lines = [self.title] if self.title else []
        for i in range(self.top, min(self.top + self.rows, len(self.items))):
            lines.append(self._row_text(i))
        self.panel.show(lines)

    def show(self, sel=0):
        """Reveal the menu (resets the cursor). The scene paints it from now until close()."""
        self.active = True
        self.sel = self._clamp(sel)
        self.top = (self.sel // self.rows) * self.rows if self.paged else max(0, min(self.sel, len(self.items) - self.rows))
        self._render_full()

    def hide(self):
        self.active = False
        self.panel.hide()

    def tick(self, btn):
        if not self.active:
            return None
        osel, otop = self.sel, self.top
        self.sel, self.top, a = _menu_step(btn, self.sel, self.top, self.rows, len(self.items), self.paged)
        if self.top != otop:                                  # scrolled/paged -> redraw the box
            self._render_full()
        elif self.sel != osel:                                # moved in-window -> just the 2 rows
            self.panel.set_line(self._t + (osel - self.top), self._row_text(osel))
            self.panel.set_line(self._t + (self.sel - self.top), self._row_text(self.sel))
        return self.sel if a == "A" else (CANCEL if a == "B" else None)


class GridCursor:
    """A 2D cursor over a cols x rows grid - the battlefield, a tile inventory, match-3, etc.
    LOGIC ONLY: you draw the grid + a highlight at (cursor.tx, cursor.ty); this handles
    movement (D-pad with auto-repeat) and confirm/cancel. `tick(btn)` returns the (tx, ty)
    tuple on A (confirm), `ui.CANCEL` on B (the "cross"/back), or None while navigating.
    `wrap=True` wraps at the edges; otherwise the cursor clamps."""

    def __init__(self, cols, rows, tx=0, ty=0, wrap=False):
        self.cols = cols
        self.rows = rows
        self.tx = tx
        self.ty = ty
        self.wrap = wrap

    @property
    def index(self):
        return self.ty * self.cols + self.tx

    def tick(self, btn):
        dx = (1 if btn.repeat(btn.RIGHT) else 0) - (1 if btn.repeat(btn.LEFT) else 0)
        dy = (1 if btn.repeat(btn.DOWN) else 0) - (1 if btn.repeat(btn.UP) else 0)
        if dx or dy:
            if self.wrap:
                self.tx = (self.tx + dx) % self.cols
                self.ty = (self.ty + dy) % self.rows
            else:
                self.tx = max(0, min(self.cols - 1, self.tx + dx))
                self.ty = max(0, min(self.rows - 1, self.ty + dy))
        if btn.just_pressed(btn.A):
            return (self.tx, self.ty)
        if btn.just_pressed(btn.B):
            return CANCEL
        return None
