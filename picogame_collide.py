# picogame_collide: zero-allocation collision helpers that read positions/sizes
# straight off sprites, so games stop hand-writing `abs(a.x-b.x) < w and ...`
# in every entity loop. Reads ONLY the integer getters (sprite.x/.y,
# bitmap.width/.height) - never sprite.anchor (whose getter allocates a tuple),
# so these are safe to call many times per frame.
#
# Positions are treated as the sprites' reference points: if both sprites use the
# same anchor (e.g. both centre, or both top-left), the anchor offset cancels in
# the difference, so these work regardless of which anchor you chose.
#
#   import picogame_collide as collide
#   if collide.hit(bullet, rock): ...           # AABB overlap (half-sizes from bitmaps)
#   if collide.hit(player, enemy, 12, 16): ...   # explicit half-extents
#   if collide.hit_point(orb, px, py): ...
#   if collide.is_within(ship, rock, 20): ...       # circular (centre distance)


def hit(a, b, hw=None, hh=None):
    """AABB overlap of two sprites. hw/hh = half-extents of the combined box;
    default = half the sum of the two bitmaps' sizes (a centre-overlap test)."""
    if hw is None:
        hw = (a.bitmap.width + b.bitmap.width) >> 1
    if hh is None:
        hh = (a.bitmap.height + b.bitmap.height) >> 1
    dx = a.x - b.x
    if dx < 0:
        dx = -dx
    if dx >= hw:
        return False
    dy = a.y - b.y
    if dy < 0:
        dy = -dy
    return dy < hh


def hit_point(a, px, py, hw=None, hh=None):
    """Is point (px, py) within the sprite's half-extents of its position?"""
    if hw is None:
        hw = a.bitmap.width >> 1
    if hh is None:
        hh = a.bitmap.height >> 1
    dx = a.x - px
    if dx < 0:
        dx = -dx
    if dx >= hw:
        return False
    dy = a.y - py
    if dy < 0:
        dy = -dy
    return dy < hh


def is_within(a, b, r):
    """Circular test: are the sprites' positions within radius r? (no sqrt)."""
    dx = a.x - b.x
    dy = a.y - b.y
    return dx * dx + dy * dy < r * r
