"""picogame_audioout - the shared output-device picker. The PWM/I2S selection itself needs a board;
here we cover the one piece of state the module keeps: the DAC driver object it must hold alive."""
import _bootstrap  # noqa: F401

import sys
import time
import types

import board
import picogame_audioout as ao


class _FakeDac:
    """adafruit_tlv320.TLV320DAC3100 stand-in: accepts every setting the init writes."""
    def __init__(self, i2c):
        pass

    def configure_clocks(self, sample_rate=None):
        pass


class _FakeI2SOut:
    def __init__(self, bclk, ws, din):
        pass


def _with_fake_i2s(fn):
    """Run fn() with a fake I2S DAC board (pins + driver modules), restoring everything after."""
    fake_bus = types.ModuleType("audiobusio")
    fake_bus.I2SOut = _FakeI2SOut
    fake_drv = types.ModuleType("adafruit_tlv320")
    fake_drv.TLV320DAC3100 = _FakeDac
    saved_mods = {k: sys.modules.get(k) for k in ("audiobusio", "adafruit_tlv320")}
    sys.modules["audiobusio"] = fake_bus
    sys.modules["adafruit_tlv320"] = fake_drv
    saved_pins = {k: getattr(board, k, None) for k in ("I2S_BCLK", "I2S_WS", "I2S_DIN", "I2C")}
    for k in ("I2S_BCLK", "I2S_WS", "I2S_DIN"):
        setattr(board, k, k)
    board.I2C = lambda: None
    real_sleep = time.sleep
    time.sleep = lambda s: None                     # the 350 ms DAC ramp is a no-op on a fake
    try:
        return fn()
    finally:
        time.sleep = real_sleep
        for k, v in saved_pins.items():
            if v is None:
                delattr(board, k)
            else:
                setattr(board, k, v)
        for k, v in saved_mods.items():
            if v is None:
                del sys.modules[k]
            else:
                sys.modules[k] = v


def test_i2s_reinit_keeps_exactly_one_dac_alive():
    def run():
        ao._KEEP.clear()
        first = ao._try_i2s(22050)
        assert isinstance(first, _FakeI2SOut) and len(ao._KEEP) == 1
        held = ao._KEEP[0]
        assert isinstance(held, _FakeDac)
        second = ao._try_i2s(22050)                 # deinit() + a new Audio/Synth in the same VM
        assert isinstance(second, _FakeI2SOut)
        assert len(ao._KEEP) == 1                   # the old driver object is replaced, not stacked
        assert ao._KEEP[0] is not held
    _with_fake_i2s(run)
    ao._KEEP.clear()
