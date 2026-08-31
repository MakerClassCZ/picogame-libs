"""picogame_shapes.tileset_colors - the gap parameter. gap=N carves an N-px transparent
right+bottom edge into each SOLID frame (frame 0 stays all-transparent), so touching
same-colour tiles read as individual tiles; gap=0 must stay the old edge-to-edge fill."""
import _bootstrap  # noqa: F401

import picogame_shapes as shp


def _frame(bm, f, w, h, frames):
    stride = w * frames
    d = bm._data if hasattr(bm, "_data") else bm.data     # sim keeps the buffer private
    return [[d[y * stride + f * w + x] for x in range(w)] for y in range(h)]


def test_gap_carves_right_and_bottom():
    bm = shp.tileset_colors(4, 3, [0xF800, 0x07E0], gap=1)
    assert _frame(bm, 1, 4, 3, 3) == [[1, 1, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0]]
    assert _frame(bm, 2, 4, 3, 3) == [[2, 2, 2, 0], [2, 2, 2, 0], [0, 0, 0, 0]]
    assert all(v == 0 for row in _frame(bm, 0, 4, 3, 3) for v in row)   # frame 0 stays empty


def test_default_is_edge_to_edge():
    bm = shp.tileset_colors(4, 3, [0xF800])
    assert all(v == 1 for row in _frame(bm, 1, 4, 3, 2) for v in row)


def _rows(bm, frame, w, h):
    d = bm._data if hasattr(bm, "_data") else bm.data
    return ["".join("#" if d[y * bm.stride + frame * w + x] else "." for x in range(w))
            for y in range(h)]


def test_masks_packs_frames_left_to_right():
    a = ["..#..", ".###.", "#####"]
    b = [".....", "..#..", ".###."]
    bm = shp.masks([a, b], 0xF800)
    assert (bm.frames, bm.width, bm.height, bm.stride) == (2, 5, 3, 10)
    assert _rows(bm, 0, 5, 3) == a
    assert _rows(bm, 1, 5, 3) == b


def test_masks_sizes_to_the_largest_and_pads_the_rest():
    small = ["#"]
    big = ["##", "##", "##"]
    bm = shp.masks([small, big], 0xF800)
    assert (bm.width, bm.height) == (2, 3)
    assert _rows(bm, 0, 2, 3) == ["#.", "..", ".."]      # short mask left transparent


def test_masks_accepts_the_same_set_chars_as_from_mask():
    bm = shp.masks([["#X1."]], 0xF800)
    assert _rows(bm, 0, 4, 1) == ["###."]


def test_masks_rejects_a_single_mask():
    try:
        shp.masks(["..#..", ".###."], 0xF800)       # a flat list of strings = one mask
    except TypeError:
        return
    raise AssertionError("a flat string list must raise, not silently make 1px frames")


def test_from_mask_multicolour_palette():
    """One mask, several colours: the design bar wants shape AND colour identity, and three
    probe agents hand-built a PAL8 atlas because from_mask took a single colour."""
    A, B = 0xF800, 0x07E0
    bm = shp.from_mask(["#o", ".."], {"#": A, "o": B})
    assert _frame(bm, 0, 2, 2, 1) == [[1, 2], [0, 0]]    # own index each; '.' transparent
    assert list(bm.palette)[1:3] == [A, B]               # ... and index -> the given colours


def test_masks_multicolour_palette():
    A, B = 0xF800, 0x001F
    bm = shp.masks([["#o"], ["o#"]], {"#": A, "o": B})
    assert _frame(bm, 0, 2, 1, 2) == [[1, 2]]
    assert _frame(bm, 1, 2, 1, 2) == [[2, 1]]
    assert list(bm.palette)[1:3] == [A, B]


def test_mask_palette_rejects_multichar_keys():
    try:
        shp.from_mask(["#"], {"##": 1})
    except ValueError:
        return
    raise AssertionError("a multi-character palette key must raise")
