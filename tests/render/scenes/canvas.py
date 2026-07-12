# Golden fixture 3/5 — Canvas: every draw primitive + text + bitmap blit + the fill565 paths
# (full clear, aligned fill_rect, odd-offset/odd-width fill_rect). Deterministic (static).
import terminalio

import picogame as pg
import picogame_game
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(8, 10, 20))

GLYPH = shp.from_mask(["#####", "#....", "####.", "#....", "#...."], pg.rgb565(240, 90, 60))

KEY = pg.rgb565(255, 0, 255)
cv = pg.Canvas(280, 200, transparent=KEY)
cv.move(20, 20)                                     # E20 placement
scene.add(cv)                                       # E18 composite (E19: leaves a transparent hole)

cv.clear(pg.rgb565(24, 30, 60))                     # E1 full-surface fill565
cv.fill_rect(8, 8, 100, 30, pg.rgb565(220, 80, 80))   # E2 aligned
cv.fill_rect(9, 44, 61, 18, pg.rgb565(80, 220, 120))  # E3 odd x & odd width (leading-pixel guard)
cv.pixel(120, 12, pg.rgb565(255, 255, 255))         # E4
cv.rect(120, 20, 70, 34, pg.rgb565(240, 220, 60))   # E5 outline
cv.line(8, 74, 200, 96, pg.rgb565(120, 180, 255))   # E6 Bresenham
cv.fill_circle(40, 130, 22, pg.rgb565(200, 120, 240))  # E7
cv.circle(100, 130, 20, pg.rgb565(120, 240, 200))   # E8 outline
cv.ring(160, 130, 22, 6, pg.rgb565(240, 160, 80))   # E9
cv.triangle(200, 105, 240, 105, 220, 145, pg.rgb565(200, 200, 120))    # E10 outline
cv.fill_triangle(200, 150, 250, 150, 225, 190, pg.rgb565(120, 200, 120))  # E11
cv.ellipse(60, 175, 30, 16, pg.rgb565(200, 120, 120))   # E12 outline
cv.fill_ellipse(140, 175, 30, 14, pg.rgb565(120, 120, 220))  # E13
cv.fill_round_rect(180, 158, 60, 34, 8, pg.rgb565(90, 210, 130))   # E14
cv.frame3d(8, 100, 40, 40, pg.rgb565(220, 230, 255), pg.rgb565(40, 60, 110))  # E15
cv.blit(GLYPH, 100, 70, 0, True, False)             # E16 bitmap into canvas, flipped
cv.text(120, 62, "PG 0123", pg.rgb565(255, 255, 255), terminalio.FONT, bg=pg.rgb565(0, 0, 0))  # E17

while True:
    scene.refresh()
