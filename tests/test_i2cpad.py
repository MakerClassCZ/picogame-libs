"""picogame_i2cpad — the generic I2C gamepad driver. We test the recipe parser, the bit
mapping/polarity logic and the miss-healing against a fake bus; real hardware (QwSTPad) is
covered by the community tester, not here."""
import _bootstrap  # noqa: F401

import picogame_i2cpad as P
import picogame_input as I


class FakeI2C:
    """Registers the pad writes, canned bytes for reads. `state` = raw input value."""

    def __init__(self, present=True, rlen=2):
        self.present = present
        self.state = 0
        self.rlen = rlen
        self.writes = []
        self.fail_reads = 0

    def try_lock(self):
        return True

    def unlock(self):
        pass

    def writeto(self, addr, buf):
        if not self.present:
            raise OSError("no ack")
        self.writes.append((addr, bytes(buf)))

    def writeto_then_readfrom(self, addr, out, buf):
        self.readfrom_into(addr, buf)

    def readfrom_into(self, addr, buf):
        if not self.present or self.fail_reads > 0:
            self.fail_reads -= 1
            raise OSError("no ack")
        for i in range(len(buf)):
            buf[i] = (self.state >> (8 * i)) & 0xFF


def test_parse_recipe_full():
    r = P.parse_recipe("addr=0x20 init=06FF,02C0 read=00:2 inv=1 UP=0 A=14")
    assert r["addr"] == 0x20
    assert r["init"] == (b"\x06\xff", b"\x02\xc0")
    assert r["rreg"] == b"\x00" and r["rlen"] == 2
    assert r["inv"] is True
    assert (0, I.UP) in r["map"] and (14, I.A) in r["map"]


def test_parse_recipe_plain_read_and_errors():
    r = P.parse_recipe("addr=0x38 read=:1 B=5")
    assert r["rreg"] is None and r["rlen"] == 1 and r["inv"] is False
    for bad in ("read=00:2 UP=1", "addr=0x20 read=00:2", "addr=0x20 read=00:2 WOBBLE=3"):
        try:
            P.parse_recipe(bad)
            assert False, bad
        except ValueError:
            pass


def test_qwstpad_preset_mapping():
    i2c = FakeI2C()
    pad = P.I2CPad(P.PRESETS["qwstpad"], i2c)
    assert len(i2c.writes) == 3                       # config + polarity + output init
    i2c.state = (1 << 1) | (1 << 14)                  # U + A bits (pressed reads 1)
    assert pad.read() == I.UP | I.A
    i2c.state = 1 << 11
    assert pad.read() == I.START
    assert pad.mapped == (I.UP | I.DOWN | I.LEFT | I.RIGHT | I.A | I.B | I.X | I.Y
                          | I.START | I.SELECT)


def test_active_low_recipe_inverts():
    i2c = FakeI2C(rlen=1)
    r = P.parse_recipe("addr=0x38 read=:1 inv=1 UP=0 A=4")
    pad = P.I2CPad(r, i2c)
    i2c.state = 0xFF & ~(1 << 4)                      # A pressed = bit LOW
    assert pad.read() == I.A
    i2c.state = 0xFF                                  # nothing pressed
    assert pad.read() == 0


def test_miss_holds_then_releases():
    i2c = FakeI2C()
    pad = P.I2CPad(P.PRESETS["qwstpad"], i2c)
    i2c.state = 1 << 1
    assert pad.read() == I.UP
    i2c.fail_reads = 3                                # brief glitch: state held
    assert pad.read() == I.UP
    assert pad.read() == I.UP
    assert pad.read() == I.UP
    assert pad.read() == I.UP                         # recovered read, still UP
    i2c.fail_reads = 99                               # cable gone: released after 8 misses
    for _ in range(8):
        pad.read()
    assert pad.read() == 0


def test_attach_multiplayer_and_leds():
    i2c = FakeI2C()
    pads = P.attach("qwstpad;qwstpad@0x23", i2c)
    assert [p._addr for p in pads] == [0x21, 0x23]
    # each pad lit its player-number LED: an extra OUTPUT-register write per pad
    led_writes = [w for w in i2c.writes if w[1][0] == 0x02 and len(w[1]) == 3]
    assert len(led_writes) >= 2


def test_attach_recipe_segment():
    i2c = FakeI2C(rlen=1)
    pads = P.attach("addr=0x38 read=:1 inv=1 UP=0 DOWN=1 A=4", i2c)
    assert len(pads) == 1 and pads[0]._addr == 0x38
    i2c.state = 0xFF & ~1
    assert pads[0].read() == I.UP


def test_missing_device_raises():
    i2c = FakeI2C(present=False)
    try:
        P.attach("qwstpad", i2c)
        assert False
    except OSError:
        pass


def test_attach_retries_transient_failure():
    # first construction attempt dies mid-init (stuck-bus style), the retry succeeds
    i2c = FakeI2C()
    orig = i2c.writeto
    fails = [2]

    def flaky(addr, buf):
        if fails[0] > 0:
            fails[0] -= 1
            raise OSError(116)
        orig(addr, buf)

    i2c.writeto = flaky
    pads = P.attach("qwstpad", i2c)
    assert len(pads) == 1
    i2c.state = 1 << 1
    assert pads[0].read() == I.UP


def test_bus_unresolvable_pins_raise_clearly():
    # field bug (Fruit Jam): PICOGAME_I2C = "GP20,GP21" - no such names there, and
    # busio.I2C(None, None) used to throw an opaque TypeError. Now: a clear ValueError.
    import os
    os.environ["PICOGAME_I2C"] = "NOPE_A,NOPE_B"
    try:
        P._bus()
        assert False
    except ValueError as e:
        assert "NOPE" in str(e) and "GPIOn" in str(e)
    finally:
        del os.environ["PICOGAME_I2C"]


def test_resolve_pin_gp_to_gpio_translation():
    import picogame_input as I2
    assert I2._resolve_pin("GP20") is not None      # translated to GPIO20 (Fruit Jam case)
    assert I2._resolve_pin("GPIO7") is not None
    assert I2._resolve_pin("TOTALLY_BOGUS") is None


def test_bus_board_pins_route_to_singleton():
    # field bug #2 (Fruit Jam): explicit pins that ARE the board bus (SDA/SCL=GPIO20/21,
    # shared with the audio DAC) must reuse board.I2C(), not build a private busio.I2C
    # (which dies with 'I2C peripheral in use').
    import os
    import sys
    board = sys.modules["board"]
    sentinel_bus = object()
    added = []
    for name, val in (("SDA", object()), ("SCL", object()), ("I2C", lambda: sentinel_bus)):
        if not hasattr(board, name):
            setattr(board, name, val)
            added.append(name)
    os.environ["PICOGAME_I2C"] = "SDA,SCL"
    try:
        assert P._bus() is board.I2C()
    finally:
        del os.environ["PICOGAME_I2C"]
        for name in added:
            delattr(board, name)
