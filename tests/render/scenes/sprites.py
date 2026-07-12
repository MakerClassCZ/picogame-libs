# Golden fixture 1/5 — unscaled blit_bitmap: orientation (flip/transpose), frames, RGB565 source,
# transparent-key. Deterministic (static). Asymmetric "F" glyph so flips/transpose move pixels.
import array

import picogame as pg
import picogame_game
import picogame_shapes as shp

scene, bufA, bufB = picogame_game.setup(background=pg.rgb565(16, 24, 48))   # bg != 0 (word-fill path)

GLYPH = shp.from_mask(["#####", "#....", "####.", "#....", "#...."], pg.rgb565(240, 90, 60))
FRAMES = shp.color_frames(8, 8, [pg.rgb565(230, 60, 60), pg.rgb565(60, 230, 60), pg.rgb565(60, 120, 240)])

# RGB565-source bitmap (16-bit units) with a transparent key punched through it.
KEY = pg.rgb565(255, 0, 255)
rgb = array.array("H")
for y in range(8):
    for x in range(8):
        rgb.append(KEY if (x + y) % 3 == 0 else pg.rgb565(28 * x, 18 * y, 200))
RGBBM = pg.Bitmap(rgb, 8, 8, format=pg.RGB565, transparent=KEY)


def put(bm, x, y, **attrs):
    s = pg.Sprite(bm, x, y)
    for k, v in attrs.items():
        setattr(s, k, v)
    scene.add(s)
    return s


# Row A (y=12): the 8 orientations of the fast path
put(GLYPH, 12, 12)                                  # A1 plain
put(GLYPH, 44, 12, flip_x=True)                     # A3
put(GLYPH, 76, 12, flip_y=True)                     # A4
put(GLYPH, 108, 12, flip_x=True, flip_y=True)       # A5
put(GLYPH, 140, 12, transpose=True)                 # A9
put(GLYPH, 172, 12, transpose=True, flip_x=True)    # A10

# Row B (y=44): a patch, then a glyph over it (index-0 transparency = A2), then multi-frame (A6)
scene.add(pg.Sprite(shp.rect(28, 28, pg.rgb565(70, 70, 80)), 12, 44))
put(GLYPH, 16, 48)                                  # A2 (patch shows through the glyph's key)
put(FRAMES, 64, 48, frame=1)                        # A6
put(FRAMES, 96, 48, frame=2)                        # A6

# Row C (y=90): RGB565 source with key holes
put(RGBBM, 12, 90)                                  # A7 + A8

while True:
    scene.refresh()
