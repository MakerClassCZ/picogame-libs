# Golden fixture 4/5 — Tilemap + StripDraw (Sky/HUD/Scanlines) + Particles + camera set_view.
# Deterministic: particles are seeded and pre-advanced in setup, then frozen; everything else static.
import random
import terminalio

import picogame as pg
import picogame_game
import picogame_shapes as shp
import picogame_fx as fx

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(20, 20, 28))

# --- Tilemap (world layer, shifts with the camera) ---
TILES = shp.tileset_colors(10, 10, [pg.rgb565(40, 120, 40), pg.rgb565(120, 80, 40), pg.rgb565(80, 80, 160)])
tm = pg.Tilemap(TILES, 8, 6)
for gy in range(6):
    for gx in range(8):
        tm.tile(gx, gy, (gx + gy) % 3)                 # 0 = empty (F2), 1/2 = solid (F1)
tm.tile(1, 1, 1, flip_x=True)                          # F3 orientation flags
tm.tile(2, 1, 2, flip_y=True)
tm.tile(3, 1, 1, transpose=True)
tm.move(24, 48)                                        # F4
scene.add(tm)                                          # non-fixed -> shifts with set_view

# --- Particles (seeded, advanced, then frozen) ---
random.seed(1234)
ps = pg.Particles(40, size=3, gravity=0.1, fade=True)
scene.add(ps)
ps.emit(180, 80, 30, 2, 30, pg.rgb565(255, 200, 80))   # H1
for _ in range(12):
    ps.tick()                                          # H2: partial-life fade, then static

# --- Fixed overlays (ignore the camera) ---
fx.Sky(scene, 0, 0, 320, 28, pg.rgb565(40, 90, 160), pg.rgb565(150, 190, 230))   # G1/G5 (self-adds fixed)


def hud(view, vx, vy, vw, vh):
    view.clear(pg.rgb565(0, 0, 0))                     # G2 full-region fill
    view.text(4, 4, "SCORE 42", pg.rgb565(255, 255, 255), terminalio.FONT)       # G3 0-RAM text


scene.add(pg.StripDraw(hud, 4, 220, 128, 16), fixed=True)   # fixed corner -> proves I4 (won't move)

fx.Scanlines(scene, 0, 0, 320, 240, step=3)            # G4 (self-adds fixed, last)

scene.set_view(-16, -8)                                # I3 world shifts; I4 fixed layers don't

while True:
    scene.refresh()
