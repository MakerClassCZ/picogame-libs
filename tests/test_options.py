"""picogame_options.OptionsMenu - the value-row menu. Covers the row list being REBUILT at runtime
(a roster that grows, a sub-level's rows swapped in and back) against a fake scene, so no engine or
render is needed."""
import _bootstrap  # noqa: F401

import picogame_options as OPT


class FakeScene:
    def add(self, item, **kw):
        return item


class FakePg:
    """Only what SceneBox touches at construction."""

    class StripDraw:
        def __init__(self, cb, x, y, w, h, **kw):
            self.cb, self.x, self.y, self.w, self.h = cb, x, y, w, h

        def invalidate(self):
            pass

    @staticmethod
    def rgb565(r, g, b):
        return 0


def _menu(rows, visible=None, title=None):
    return OPT.OptionsMenu(FakeScene(), FakePg(), None, 0, 0, 120, rows, 1, 0,
                           title=title, visible=visible)


def test_constructor_normalises():
    m = _menu([{"key": "diff", "label": "Diff", "kind": "choice", "choices": ["Easy", "Hard"]},
               {"key": "vol", "label": "Vol", "kind": "stepper", "min": 0, "max": 10}])
    assert m.rows[0]["i"] == 0 and m.rows[1]["value"] == 0


def test_set_rows_normalises_and_repaints():
    # A rebuilt list is the way a growing menu changes (recruit a unit, a player joins) and how a
    # sub-level's rows are swapped in. Rows written by hand may omit i/value, exactly like the ones
    # handed to the constructor.
    m = _menu([{"key": "a", "label": "A", "kind": "action"}], visible=4)
    m.set_rows([{"key": "type", "label": "Type", "kind": "choice", "choices": ["Beef", "Cheese"]},
                {"key": "qty", "label": "Qty", "kind": "stepper", "min": 1, "max": 9},
                {"key": "snd", "label": "Snd", "kind": "toggle"}])
    assert m.rows[0]["i"] == 0
    assert m.rows[1]["value"] == 1                 # stepper defaults to its min
    assert m.rows[2]["value"] is False
    assert m.value("type") == "Beef" and m.value("qty") == 1


def test_set_rows_clamps_a_shrunken_list():
    rows = [{"key": i, "label": "row %d" % i, "kind": "action"} for i in range(6)]
    m = _menu(rows, visible=4)
    m.show(5)                                      # cursor on the last row
    assert m.sel == 5
    m.set_rows(rows[:2], sel=5)                    # list shrinks under the cursor
    assert m.sel == 1 and m.top == 0               # clamped, no IndexError on the next render


def test_visible_is_the_window_not_the_row_count():
    # A menu that starts with one row but will grow keeps the window it asked for, so the panel does
    # not resize as rows come and go.
    m = _menu([{"key": "add", "label": "+ Add", "kind": "action"}], visible=6)
    assert m.vis == 6
    m.set_rows([{"key": i, "label": "unit %d" % i, "kind": "action"} for i in range(10)])
    assert m.vis == 6                              # still the same panel; the rest scrolls
