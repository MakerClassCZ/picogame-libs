# picogame_synth: real on-device sound via synthio - no WAV files, no sample RAM.
#
# CircuitPython's synthio generates audio in real time (oscillators + ADSR envelopes +
# LFOs + filters), so a whole SFX set or a MIDI tune costs almost no RAM. This wraps the
# Fruitris pattern (PWMAudioOut -> Mixer -> Synthesizer) with built-in waveforms, so games
# can finally make noise on the PicoPad/PicoSystem. (Sample-based audio lives in
# picogame_audio; this is the synthesis path.)
#
#   import picogame_synth as snd
#   s = snd.Synth()                                   # board.AUDIO, PWM out
#   beep = snd.note(72, snd.SQUARE, decay=0.08)       # an SFX (build once)
#   s.sfx(beep)                                       # fire it (retriggers cleanly)
#
# Needs synthio + audiopwmio + audiomixer in the firmware (they are on both our boards).
# No simulator support - this is a device-only module.

import array
import math
import board
import synthio
from audiopwmio import PWMAudioOut
from audiomixer import Mixer

# ---- built-in oscillator waveforms (signed 16-bit, one cycle) ----
_LEN = 256
_AMP = 28000


def sine():
    return array.array("h", [int(_AMP * math.sin(2 * math.pi * i / _LEN)) for i in range(_LEN)])


def saw():
    return array.array("h", [int(_AMP * (2.0 * i / _LEN - 1.0)) for i in range(_LEN)])


def triangle():
    return array.array("h", [int(_AMP * (2.0 * abs(2.0 * i / _LEN - 1.0) - 1.0)) for i in range(_LEN)])


def square():
    return array.array("h", [_AMP if i < _LEN // 2 else -_AMP for i in range(_LEN)])


def noise():
    out = array.array("h", bytes(2 * _LEN))
    s = 0x1234
    for i in range(_LEN):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        out[i] = (s >> 8) % (2 * _AMP) - _AMP
    return out


# Prebuilt singletons (share one waveform across notes - they're read-only).
SINE = sine()
SAW = saw()
TRIANGLE = triangle()
SQUARE = square()
NOISE = noise()


def note(midi, waveform=None, attack=0.005, decay=0.06, sustain=0.0, release=0.08,
         amplitude=0.6, bend=None, cutoff=None):
    """Build a reusable SFX/instrument note. `midi` = MIDI number (60 = middle C);
    `bend` = an LFO (see pitch_bend) for a slide; `cutoff` = low-pass filter Hz."""
    env = synthio.Envelope(attack_time=attack, decay_time=decay,
                           sustain_level=sustain, release_time=release)
    flt = synthio.Biquad(synthio.FilterMode.LOW_PASS, cutoff) if cutoff else None
    return synthio.Note(frequency=synthio.midi_to_hz(midi), waveform=waveform,
                        envelope=env, amplitude=amplitude, bend=bend, filter=flt)


def pitch_bend(semitones, ms, waveform=None, once=True):
    """An LFO for note `bend`: slide by `semitones` over `ms` ms (e.g. a laser zap)."""
    return synthio.LFO(waveform=waveform, rate=1000.0 / ms, scale=semitones / 12.0, once=once)


class Synth:
    """PWM audio out -> a mixer with a music voice + a synth voice for SFX."""

    def __init__(self, pin=None, sample_rate=22050, buffer_size=2048,
                 music_level=0.4, sfx_level=0.7):
        self.sample_rate = sample_rate
        self.audio = PWMAudioOut(pin if pin is not None else board.AUDIO)
        self.mixer = Mixer(voice_count=2, sample_rate=sample_rate, channel_count=1,
                           bits_per_sample=16, buffer_size=buffer_size)
        self.audio.play(self.mixer)
        self.mixer.voice[0].level = music_level      # voice 0: music (MidiTrack)
        self.mixer.voice[1].level = sfx_level        # voice 1: live synth SFX
        self.synth = synthio.Synthesizer(sample_rate=sample_rate, channel_count=1)
        self.mixer.voice[1].play(self.synth)

    def sfx(self, n):
        """Play an SFX note. Retriggers its LFOs first so repeats sound identical."""
        for lfo in (n.bend, n.amplitude,
                    n.filter.frequency if isinstance(n.filter, synthio.Biquad) else None):
            if isinstance(lfo, synthio.LFO):
                lfo.retrigger()
        self.synth.release_all_then_press(n)

    def press(self, n):
        self.synth.press(n)

    def release(self, n):
        self.synth.release(n)

    def music(self, midi_track):
        self.mixer.voice[0].play(midi_track, loop=True)

    def stop_music(self):
        self.mixer.voice[0].stop()


def load_midi(path, sample_rate=22050, waveform=None, envelope=None, tempo=120, ppqn=240):
    """Load a .mid file as a synthio.MidiTrack to play on the music voice (Synth.music)."""
    with open(path, "rb") as f:
        if f.read(4) != b"MThd":
            f.seek(0)
        else:
            # already consumed the 4-byte "MThd" magic; a standard format-0 SMF header is 22 bytes
            # total (MThd chunk 14 + MTrk header 8), so skip the remaining 18 to land on event 0.
            f.read(18)
        return synthio.MidiTrack(f.read(), tempo=ppqn * tempo // 60,
                                 sample_rate=sample_rate, waveform=waveform, envelope=envelope)
