# picogame_ray: a first-person raycaster (Wolfenstein-style corridors/dungeons)
# drawn into a buffer-less StripDraw view - a fake-3D mode at ZERO retained RAM,
# pure Python, no firmware change. A tile map of walls, solid distance-shaded
# columns via the engine's C fill_rect. Cast once per frame, then the Scene's
# per-strip refresh paints it.
#
#   rc = picogame_ray.Raycaster(MAP, wall_colors, sky, floor)
#   sd = pg.StripDraw(rc.draw, 0, 0, W, H)   ; scene.add(sd)
#   ...each frame: rc.cast(px, py, angle, W, H) ; scene.refresh()
# MAP = list of equal-length strings, '0' = empty, '1'..'9' = wall types.
#
# PERF (RP2040): the whole thing is interpreted Python, so the two hot loops -
# the per-column DDA and the per-strip wall paint - dominate. Three levers keep
# it playable: `stride` casts one ray per N screen columns (2 = half the rays
# AND half the fill_rects for a small loss in wall crispness), the draw pass
# run-length-merges adjacent identical columns into one wide fill_rect (a flat
# wall face facing you collapses to a single rect), and both loops hoist every
# attribute to a local. Bump `stride` to 3-4 on a big map or a slow board.
import math


class Raycaster:
    def __init__(self, world, wall_colors, sky, floor, fov=0.66, stride=2):
        # world: list of strings; wall_colors: {type_int: (near_color, side_color)}
        self.map = world
        self.mw = len(world[0])
        self.mh = len(world)
        # flat int grid for the hot DDA loop: flat[y*mw+x] = wall type (0 = empty).
        # Avoids per-step nested indexing + 1-char string alloc + string compare.
        flat = bytearray(self.mw * self.mh)
        for y, row in enumerate(world):
            base = y * self.mw
            for x, ch in enumerate(row):
                flat[base + x] = 0 if ch == "0" else int(ch)
        self._flat = flat
        self.wall = wall_colors
        self.sky = sky
        self.floor = floor
        self.fov = fov
        self.stride = stride if stride > 0 else 1
        self.sw = self.sh = 0
        self.top = self.bot = self.col = None

    def solid(self, x, y):
        if 0 <= x < self.mw and 0 <= y < self.mh:
            return self.map[y][x] != "0"
        return True                          # out of bounds = wall

    def cast(self, px, py, ang, sw, sh):
        """DDA one ray per `stride` screen columns; cache wall top/bottom/colour.
        Arrays are COMPACT (length ceil(sw/stride)); draw() expands them back."""
        self.sw, self.sh = sw, sh
        stride = self.stride
        ncols = (sw + stride - 1) // stride
        top = [0] * ncols
        bot = [0] * ncols
        col = [0] * ncols
        # hoist everything the inner loop touches into locals (module/attr lookups
        # are the #1 interpreter cost on-device)
        flat = self._flat
        mw = self.mw
        mh = self.mh
        wall = self.wall
        wall1 = wall[1]
        wget = wall.get
        dirx = math.cos(ang)
        diry = math.sin(ang)
        fov = self.fov
        planex = -diry * fov
        planey = dirx * fov
        half = sh >> 1
        ipx = int(px)
        ipy = int(py)
        inv_sw = 2.0 / sw
        for c in range(ncols):
            camx = (c * stride) * inv_sw - 1.0
            rdx = dirx + planex * camx
            rdy = diry + planey * camx
            mapx = ipx
            mapy = ipy
            ddx = abs(1.0 / rdx) if rdx else 1e30
            ddy = abs(1.0 / rdy) if rdy else 1e30
            if rdx < 0:
                stepx = -1
                sidex = (px - mapx) * ddx
            else:
                stepx = 1
                sidex = (mapx + 1.0 - px) * ddx
            if rdy < 0:
                stepy = -1
                sidey = (py - mapy) * ddy
            else:
                stepy = 1
                sidey = (mapy + 1.0 - py) * ddy
            side = 0
            cell = 1
            for _ in range(64):              # DDA step cap
                if sidex < sidey:
                    sidex += ddx
                    mapx += stepx
                    side = 0
                else:
                    sidey += ddy
                    mapy += stepy
                    side = 1
                cell = flat[mapy * mw + mapx] if (0 <= mapx < mw and 0 <= mapy < mh) else 1
                if cell:
                    break
            dist = (sidex - ddx) if side == 0 else (sidey - ddy)
            if dist < 0.01:
                dist = 0.01
            lh = int(sh / dist)
            t = half - (lh >> 1)
            b = t + lh
            if t < 0:
                t = 0
            if b > sh:
                b = sh
            near, far = wget(cell, wall1)
            top[c] = t
            bot[c] = b
            col[c] = far if side else near   # y-side walls slightly darker (depth cue)
        self.top, self.bot, self.col = top, bot, col

    def draw(self, view, vx, vy, vw, vh):
        """StripDraw callback: sky/floor background for this band, then the wall
        column runs that cross it. Adjacent equal columns merge into one rect."""
        if self.top is None:
            return
        fr = view.fill_rect
        half = self.sh >> 1
        y0 = vy
        y1 = vy + vh
        # background: sky above the horizon, floor below (split at screen mid)
        if y1 <= half:
            fr(0, 0, vw, vh, self.sky)
        elif y0 >= half:
            fr(0, 0, vw, vh, self.floor)
        else:
            fr(0, 0, vw, half - y0, self.sky)
            fr(0, half - y0, vw, y1 - half, self.floor)
        # walls: run-length-merge adjacent identical columns, clip run to strip
        top = self.top
        bot = self.bot
        col = self.col
        stride = self.stride
        ncols = len(top)
        c = 0
        while c < ncols:
            t = top[c]
            b = bot[c]
            cc = col[c]
            c2 = c + 1
            while c2 < ncols and top[c2] == t and bot[c2] == b and col[c2] == cc:
                c2 += 1
            st = t if t > y0 else y0
            sb = b if b < y1 else y1
            if sb > st:
                x0 = c * stride
                x1 = c2 * stride
                if x1 > vw:
                    x1 = vw
                fr(x0, st - vy, x1 - x0, sb - st, cc)
            c = c2
