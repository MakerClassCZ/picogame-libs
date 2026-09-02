"""picogame_ui — the alloc-free helpers behind menus/text boxes (ui usage: 40 imports). We test the
pure logic added in A4: `_seq_eq` (the no-alloc list compare) and `_menu_step` (cursor nav + paging
+ A/B actions), with a fake button so no engine/render is needed."""
import _bootstrap  # noqa: F401

import picogame_ui as UI
import terminalio


def test_seq_eq():
    assert UI._seq_eq(["a", "b", "c"], ["a", "b", "c"])
    assert not UI._seq_eq(["a", "b"], ["a", "x"])
    assert not UI._seq_eq(["a", "b"], ["a", "b", "c"])   # different length
    assert UI._seq_eq([], [])


class FakeBtn:
    UP, DOWN, A, B = 1, 2, 4, 8

    def __init__(self, down=False, up=False, a=False, b=False):
        self._d, self._u, self._a, self._b = down, up, a, b

    def repeat(self, m):
        return (m == self.DOWN and self._d) or (m == self.UP and self._u)

    def just_pressed(self, m):
        return (m == self.A and self._a) or (m == self.B and self._b)


def test_menu_step_down_up_wrap():
    # sel, top, action = _menu_step(btn, sel, top, rows, n, paged)
    sel, top, act = UI._menu_step(FakeBtn(down=True), 0, 0, 3, 5, True)
    assert sel == 1 and act is None
    sel, top, act = UI._menu_step(FakeBtn(down=True), 4, 0, 3, 5, True)
    assert sel == 0                                  # wraps past the end
    sel, top, act = UI._menu_step(FakeBtn(up=True), 0, 0, 3, 5, True)
    assert sel == 4                                  # wraps before the start


def test_menu_step_actions():
    _, _, act = UI._menu_step(FakeBtn(a=True), 2, 0, 3, 5, True)
    assert act == "A"                                # confirm
    _, _, act = UI._menu_step(FakeBtn(b=True), 2, 0, 3, 5, True)
    assert act == "B"                                # cancel


def test_menu_step_empty():
    sel, top, act = UI._menu_step(FakeBtn(down=True), 0, 0, 3, 0, True)
    assert sel == 0 and top == 0 and act is None     # n==0 -> nothing to navigate


def test_menu_step_paging_window():
    # moving below the visible window (rows=3) should page the window to keep sel visible
    sel, top, act = UI._menu_step(FakeBtn(down=True), 2, 0, 3, 10, True)
    assert sel == 3
    assert top == 3                                  # paged: window jumps a whole page


def test_menu_step_line_scroll():
    # paged=False (used by OptionsMenu): the window follows the cursor one line at a time
    sel, top, _ = UI._menu_step(FakeBtn(down=True), 2, 0, 3, 10, False)
    assert sel == 3 and top == 1                      # sel left the window -> top slides by one


# --- the shared menu helpers (dedup of Menu / SceneMenu / OptionsMenu) ---
def test_marked():
    assert UI._marked("Play", True) == "> Play"
    assert UI._marked("Play", False) == "  Play"


def test_panel_h():
    assert UI._panel_h(3) == 10 + 3 * UI.LINE_H


def test_menu_w():
    assert UI._menu_w(["Hi"], 200) == 200                      # explicit width wins
    assert UI._menu_w(["a", "longer"], None) == max(60, 11 * 6 + 16)   # heuristic on longest label
    assert UI._menu_w([], None) == max(60, 11 * 4 + 16)        # empty -> the default-4 floor


def test_menu_pick():
    assert UI._menu_pick(3, "A") == 3                          # chosen index/key on A
    assert UI._menu_pick("done", "B") == UI.CANCEL             # CANCEL on B
    assert UI._menu_pick(3, None) is None                      # still navigating


def test_menu_lines_window():
    rt = lambda i: "r%d" % i
    assert UI._menu_lines("T", rt, 0, 3, 10) == ["T", "r0", "r1", "r2"]   # title + window
    assert UI._menu_lines(None, rt, 4, 3, 10) == ["r4", "r5", "r6"]       # no title, mid-list
    assert UI._menu_lines(None, rt, 8, 3, 10) == ["r8", "r9"]             # clamps at the end


def test_wrap():
    assert UI.wrap("one two three", 7) == ["one two", "three"]            # word wrap
    assert UI.wrap("a\nb c", 10) == ["a", "b c"]                          # breaks on newlines too
    assert UI.wrap("one two three four", 7, maxlines=2) == ["one two", "three"]   # maxlines cap
    assert UI.wrap(None, 5) == []                                         # None -> no lines
    assert UI.wrap("verylongword", 4) == ["verylongword"]                # over-long word on its own line


def test_text_width_is_the_fixed_cell_metric():
    """Four probe agents hand-computed `len(s) * 6` for every HUD field; make it a function."""
    assert UI.text_width(terminalio.FONT, "HELLO") == 5 * 6
    assert UI.text_width(terminalio.FONT, "") == 0


def test_centred_pads_without_str_center():
    """`str.center` needs an EXTRA_FEATURES MicroPython build - it is compiled OUT of
    CircuitPython, so it works in the CPython sim and raises on device."""
    assert UI.centred("AB", 8) == "   AB   "
    assert UI.centred("ABC", 8) == "  ABC   "     # odd remainder -> extra space right
    assert UI.centred("TOOLONG", 4) == "TOOL"     # never grows past the reserve


def test_gridcursor_repeat_is_tunable():
    """The default auto-repeat suits a menu; a cursor that IS the core verb needs it faster."""
    seen = []

    class BtnStub:
        LEFT, RIGHT, UP, DOWN, A, B = (1, 2, 4, 8, 16, 32)

        def just_pressed(self, m):
            return False

        def repeat(self, m, delay=15, interval=4):
            seen.append((delay, interval))
            return False

    UI.GridCursor(4, 4, delay=6, interval=2).tick(BtnStub())
    assert seen and all(d == 6 and i == 2 for d, i in seen)


def test_txt_passes_a_str_through_untouched():
    s = "score 1234"
    assert UI._txt(s) is s                             # no copy (str(s) allocates in MicroPython)
    assert UI._txt(None) == ""
    assert UI._txt(42) == "42"
