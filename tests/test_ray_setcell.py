"""picogame_ray.Raycaster.set_cell - runtime world mutation (doors/gates). Pins the three
consistency guarantees the method exists for: the C grid, solid() and .map all agree after a
change, and a STANDING camera re-casts (the pose cache must not serve the old world)."""
import _bootstrap  # noqa: F401

import picogame as pg
import picogame_ray as pr

MAP = ["11111",
       "10001",
       "10101",
       "10001",
       "11111"]
COLORS = {1: (pg.rgb565(200, 60, 60), pg.rgb565(140, 40, 40))}


def make():
    return pr.Raycaster(list(MAP), COLORS, pg.rgb565(40, 50, 90), pg.rgb565(30, 30, 30))


def test_set_cell_updates_grid_solid_and_map():
    rc = make()
    assert rc.solid(2, 2)                    # the centre pillar
    rc.set_cell(2, 2, 0)                     # the door opens
    assert not rc.solid(2, 2)
    assert rc._flat[2 * rc.mw + 2] == 0
    assert rc.map[2] == "10001"              # minimap readers see it too
    rc.set_cell(2, 2, 3)                     # and a different wall type closes it
    assert rc.solid(2, 2)
    assert rc.map[2] == "10301"


def test_standing_camera_sees_the_change():
    rc = make()
    ANG = 0.7853981633974483                 # 45 deg: dead-on at the (2,2) pillar from (1.5,1.5)
    rc.cast(1.5, 1.5, ANG, 60, 40)
    before = list(rc.top)
    rc.cast(1.5, 1.5, ANG, 60, 40)           # same pose -> pose cache: no re-cast
    rc.set_cell(2, 2, 0)                     # the pillar vanishes
    rc.cast(1.5, 1.5, ANG, 60, 40)           # same pose again - MUST re-cast, not serve the cache
    after = list(rc.top)
    assert after != before                   # rays now travel further: wall tops move


def test_out_of_bounds_is_a_noop():
    rc = make()
    rc.set_cell(-1, 0, 0)
    rc.set_cell(0, 99, 0)
    assert rc.map == MAP                     # untouched


def test_original_world_list_is_not_mutated():
    world = list(MAP)
    rc = pr.Raycaster(world, COLORS, 0, 0)
    rc.set_cell(2, 2, 0)
    assert world[2] == "10101"               # the caller's list is safe (we copied)


def test_draw_is_view_local_not_screen_local():
    """draw()'s row 0 is the top of the RAYCAST VIEW: a layer that starts below y=0 must pass
    vy - top, or the picture renders `top` pixels high. Pins the documented contract."""
    rc = make()
    W, VH, BAND = 64, 40, 10
    rc.cast(1.5, 1.5, 0.0, W, VH)
    screen = pg.Canvas(W, VH)                 # the layer's own strip, screen rows BAND..BAND+VH
    rc.draw(screen, 0, BAND, W, VH)           # WRONG: absolute vy
    wrong = bytes(bytearray(screen._data[i] & 0xFF for i in range(len(screen._data))))
    screen2 = pg.Canvas(W, VH)
    rc.draw(screen2, 0, 0, W, VH)             # RIGHT: band-local (vy - BAND, with vy == BAND)
    right = bytes(bytearray(screen2._data[i] & 0xFF for i in range(len(screen2._data))))
    assert wrong != right                     # the offset genuinely changes the picture


def test_project_sprite_edge_column_still_z_tests():
    """A sprite whose CENTRE column falls off-screen used to skip the z-buffer test entirely
    and draw through edge walls (round-3 gatecrash finding). The test must clamp to the
    nearest on-screen column instead."""
    rc = pr.Raycaster(["11111", "10001", "10101", "10001", "11111"],
                      {1: (1, 2)}, 3, 4)
    rc.cast(1.5, 2.5, 0.0, 60, 40)          # looking +x down the corridor
    # points BEHIND walls whose centre column lands OFF-SCREEN (verified: screen_x -20 and 73;
    # the old code skipped the z-test for both and returned them as visible)
    assert rc.project_sprite(3.5, 0.3) is None
    assert rc.project_sprite(3.5, 4.4) is None
