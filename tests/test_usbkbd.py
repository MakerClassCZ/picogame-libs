"""picogame_usbkbd: boot-report parsing, settings remap, discovery + claim (device faked)."""
import _bootstrap  # noqa: F401

import os

import picogame_usbkbd as uk
from picogame_input import UP, LEFT, A, B, START


class _FakeDev:
    idVendor = 0x1234
    idProduct = 0x5678

    def __init__(self, reports, config=None):
        self._reports = list(reports)
        self._config = config
        self.configured = 0                    # set_configuration() call count
        self.detached = []                     # interfaces detach_kernel_driver saw

    def is_kernel_driver_active(self, i):
        return True

    def detach_kernel_driver(self, i):
        self.detached.append(i)

    def set_configuration(self):
        self.configured += 1

    def ctrl_transfer(self, bmreq, breq, wval, widx, buf, timeout=0):
        if bmreq == 0x80 and breq == 6 and self._config is not None:
            n = min(len(buf), len(self._config))
            buf[:n] = self._config[:n]
            return n
        return 0

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


def _config(*interfaces):
    """Build a fake config descriptor: interfaces = (iface_no, klass, proto, ep)."""
    body = b""
    for num, klass, proto, ep in interfaces:
        body += bytes((9, 4, num, 0, 1, klass, 1, proto, 0))       # INTERFACE
        body += bytes((7, 5, ep, 3, 8, 0, 10))                     # ENDPOINT (int IN)
    total = 9 + len(body)
    head = bytes((9, 2, total & 0xFF, total >> 8, 0, 1, 0, 0x80, 50))
    return head + body


def test_parse_boot_report():
    k = _kbd([bytes((0, 0, 0x52, 0x1D, 0, 0, 0, 0))])   # Up arrow + Z held
    assert k.read() == (UP | A)
    # no new report -> hold the last state
    assert k.read() == (UP | A)


def test_rollover_holds_state():
    k = _kbd([bytes((0, 0, 0x50, 0, 0, 0, 0, 0)),        # Left held
              bytes((0, 0, 1, 1, 1, 1, 1, 1)),           # error rollover: state UNKNOWN
              bytes((0, 0, 0, 0, 0, 0, 0, 0))])          # real release
    assert k.read() == LEFT
    assert k.read() == LEFT                              # rollover must HOLD, not release
    assert k.read() == 0


def test_error_codes_ignored():
    # 0x02 POSTFail / 0x03 ErrorUndefined must not map to buttons (0x04 = LEFT alias 'A' key)
    k = _kbd([bytes((0, 0, 2, 3, 0x04, 0, 0, 0))])
    assert k.read() == LEFT


def test_settings_remap_merges():
    os.environ["PICOGAME_USBKBD"] = "A=0x2B B=0x35"      # Tab=A, Grave=B
    try:
        keys = uk._keys_from_settings()
    finally:
        del os.environ["PICOGAME_USBKBD"]
    m = dict((c, l) for c, l in keys)
    assert m[0x2B] == A and m[0x35] == B
    assert 0x1D not in m and 0x1B not in m               # old A/B codes dropped
    assert m[0x28] == START                              # unrelated defaults kept


def test_settings_remap_evicts_colliding_alias():
    # START=Space must ALSO evict the default Space->A alias: one key, one button
    os.environ["PICOGAME_USBKBD"] = "START=0x2C"
    try:
        keys = uk._keys_from_settings()
    finally:
        del os.environ["PICOGAME_USBKBD"]
    hits = [log for c, log in keys if c == 0x2C]
    assert hits == [START]


def test_candidates_plain_keyboard():
    # single-interface wired keyboard: iface 0 / ep 0x81 is a VALID result, not a sentinel
    dev = _FakeDev([], config=_config((0, 3, 1, 0x81)))
    assert uk._kbd_candidates(dev) == [(0, 0x81)]


def test_candidates_combo_dongle():
    # Rapoo-style: mouse iface 0 excluded, both keyboard-proto interfaces found
    dev = _FakeDev([], config=_config((0, 3, 2, 0x81), (1, 3, 1, 0x82), (2, 3, 1, 0x83)))
    assert uk._kbd_candidates(dev) == [(1, 0x82), (2, 0x83)]


def test_pick_override_and_validation():
    cands = [(1, 0x82), (2, 0x83)]
    os.environ["PICOGAME_USBKBD_EP"] = "2:0x83"
    try:
        assert uk._pick(cands) == (2, 0x83)
        os.environ["PICOGAME_USBKBD_EP"] = "2:0x03"      # OUT endpoint: invalid
        assert uk._pick(cands) == (1, 0x82)
        os.environ["PICOGAME_USBKBD_EP"] = "banana"
        assert uk._pick(cands) == (1, 0x82)
    finally:
        del os.environ["PICOGAME_USBKBD_EP"]


def test_explicit_dev_is_claimed():
    dev = _FakeDev([bytes((0, 0, 0x52, 0, 0, 0, 0, 0))])
    k = uk.UsbKbd(dev=dev, iface=2, ep=0x83, timeout_ms=1)
    assert dev.configured == 1                           # explicit dev claims like UsbPad
    assert 2 in dev.detached
    assert k.read() == UP


class USBTimeoutError(Exception):                        # matched by NAME in the driver
    pass


class _LegacyDev(_FakeDev):
    """Old firmware: read() has no raise_on_timeout kwarg; timeouts raise USBTimeoutError."""

    def read(self, ep, buf, timeout=0, **kw):
        if kw:
            raise TypeError("unexpected keyword argument")
        if not self._reports:
            raise USBTimeoutError()
        r = self._reports.pop(0)
        buf[:len(r)] = r
        return len(r)


def test_legacy_firmware_fallback():
    dev = _LegacyDev([bytes((0, 0, 0x50, 0, 0, 0, 0, 0))])
    k = uk.UsbKbd(dev=dev, iface=0, ep=0x81, timeout_ms=1)
    assert k.read() == 0                                 # TypeError probe frame: hold (empty) state
    assert k.read() == LEFT                              # plain path delivers the report
    assert k.read() == LEFT                              # USBTimeoutError -> hold, not hard error
