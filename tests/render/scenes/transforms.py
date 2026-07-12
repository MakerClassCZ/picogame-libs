# Golden fixture 2/5 — scaled + affine(rotation) blit + the 4 blit-effects. Deterministic.
# NB: sim scale is a FLOAT (1.0 == 1x). Use 2.0/1.5, and angles 30/45 (not 90, which aliases transpose).
import picogame as pg
import picogame_game
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(10, 10, 14))

GLYPH = shp.from_mask(["#####", "#....", "####.", "#....", "#...."], pg.rgb565(240, 200, 70))
VICTIM = pg.rgb565(120, 200, 255)          # bright patch under fx sprites so shadow/dither/tint show


def put(bm, x, y, **attrs):
    s = pg.Sprite(bm, x, y)
    for k, v in attrs.items():
        setattr(s, k, v)
    scene.add(s)
    return s


def patch(x, y, w=16, h=16, c=VICTIM):
    scene.add(pg.Sprite(shp.rect(w, h, c), x, y))


# Row A (y=16): scale (float!)
put(GLYPH, 12, 16, scale=2.0)                       # C1 integer scale
put(GLYPH, 60, 16, scale=1.5)                       # C2 non-integer
put(GLYPH, 100, 16, scale=2.0, flip_x=True)         # C3 scaled + flip
put(GLYPH, 150, 16, scale=2.0, dither=8)            # C4 scaled + fx

# Row B (y=80): affine rotation
put(GLYPH, 20, 80, angle=30)                        # D1
put(GLYPH, 70, 80, angle=45, scale=2.0)             # D2
put(GLYPH, 130, 80, angle=30, flip_x=True)          # D3
put(GLYPH, 180, 80, angle=30, tint=pg.rgb565(255, 80, 80))   # D4
put(GLYPH, 230, 80, angle=30, anchor=(0.5, 0.5))    # D5 pivot about centre

# Row C (y=160): the 4 effects over known bright patches
patch(12, 160); put(GLYPH, 12, 160, flash=pg.rgb565(255, 255, 255))   # B2 flash
patch(60, 160); put(GLYPH, 60, 160, tint=pg.rgb565(255, 160, 60))     # B3 tint
patch(108, 160); put(GLYPH, 108, 160, shadow=True)                    # B1 shadow
patch(156, 160); put(GLYPH, 156, 160, dither=8)                       # B4 dither

while True:
    scene.refresh()
