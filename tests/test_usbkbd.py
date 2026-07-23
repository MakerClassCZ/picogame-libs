"""picogame_usbkbd: boot-report parsing + settings remap (device object faked)."""
import _bootstrap  # noqa: F401

import picogame_usbkbd as uk
from picogame_input import UP, LEFT, A, B, START


class _FakeDev:
    idVendor = 0x1234
    idProduct = 0x5678

    def __init__(self, reports):
        self._reports = list(reports)

    def is_kernel_driver_active(self, i):
        return False

    def set_configuration(self):
        pass

    def read(self, ep, buf, timeout=0, raise_on_timeout=None):
        if not self._reports:
            if raise_on_timeout is False:
                return 0
            raise TimeoutError()          # stands in for USBTimeoutError
        r = self._reports.pop(0)
        buf[:len(r)] = r
        return len(r)


def _kbd(reports):
    return uk.UsbKbd(dev=_FakeDev(reports), ep=0x81, timeout_ms=1)


def test_parse_boot_report():
    k = _kbd([bytes((0, 0, 0x52, 0x1D, 0, 0, 0, 0))])   # Up arrow + Z held
    assert k.read() == (UP | A)
    # no new report -> hold the last state
    assert k.read() == (UP | A)


def test_release_and_rollover():
    k = _kbd([bytes((0, 0, 0x50, 0, 0, 0, 0, 0)),        # Left
              bytes((0, 0, 0, 0, 0, 0, 0, 0)),           # all released
              bytes((0, 0, 1, 1, 1, 1, 1, 1))])          # error rollover -> ignored
    assert k.read() == LEFT
    assert k.read() == 0
    assert k.read() == 0


def test_settings_remap_merges(monkeypatch=None):
    import os
    os.environ["PICOGAME_USBKBD"] = "A=0x2B B=0x35"      # Tab=A, Grave=B
    try:
        keys = uk._keys_from_settings()
    finally:
        del os.environ["PICOGAME_USBKBD"]
    m = dict((c, l) for c, l in keys)
    assert m[0x2B] == A and m[0x35] == B
    assert 0x1D not in m and 0x1B not in m               # old A/B codes dropped
    assert m[0x28] == START                              # unrelated defaults kept
