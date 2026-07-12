"""picogame_ui — the alloc-free helpers behind menus/text boxes (ui usage: 40 imports). We test the
pure logic added in A4: `_seq_eq` (the no-alloc list compare) and `_menu_step` (cursor nav + paging
+ A/B actions), with a fake button so no engine/render is needed."""
import _bootstrap  # noqa: F401

import picogame_ui as UI


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
