# Golden fixture 5/5 — the hardware colour-invert path (pg.invert / INVON). The sim's _host applies
# the negative in _to_image(), so the shot is the inverted frame. Deterministic (static).
import board

import picogame as pg
import picogame_game
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(30, 30, 40))

GLYPH = shp.from_mask(["#####", "#....", "####.", "#....", "#...."], pg.rgb565(240, 90, 60))
scene.add(pg.Sprite(GLYPH, 40, 40))
scene.add(pg.Sprite(shp.rect(70, 44, pg.rgb565(80, 200, 120)), 130, 90))

scene.refresh()
pg.invert(board.DISPLAY, True)          # I6: everything renders as its photo-negative from here

while True:
    scene.refresh()
