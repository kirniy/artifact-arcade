"""
Synthesizer voice and waveform generation.

Pure Python synth with oscillators, envelopes, and effects
for that authentic 80s synthwave sound.
"""

import math
import array
from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional


class WaveType(Enum):
    """Oscillator waveform types."""
    SINE = "sine"
    SQUARE = "square"
    SAWTOOTH = "sawtooth"
    TRIANGLE = "triangle"
    NOISE = "noise"
    PULSE = "pulse"  # Variable duty cycle


@dataclass
class ADSR:
    """Attack-Decay-Sustain-Release envelope."""
    attack: float = 0.01   # seconds
    decay: float = 0.1     # seconds
    sustain: float = 0.7   # level (0-1)
    release: float = 0.2   # seconds

    def get_amplitude(self, time: float, note_off_time: Optional[float] = None) -> float:
        """Calculate envelope amplitude at given time."""
        if note_off_time is not None:
            # In release phase
            release_time = time - note_off_time
            if release_time >= self.release:
                return 0.0
            # Get level at note-off
            sustain_level = self._get_level_at(note_off_time)
            return sustain_level * (1.0 - release_time / self.release)

        return self._get_level_at(time)

    def _get_level_at(self, time: float) -> float:
        """Get envelope level at time (without release)."""
        if time < self.attack:
            # Attack phase
            return time / self.attack
        time -= self.attack

        if time < self.decay:
            # Decay phase
            return 1.0 - (1.0 - self.sustain) * (time / self.decay)

        # Sustain phase
        return self.sustain


@dataclass
class SynthVoice:
    """A synthesizer voice with oscillator and envelope."""
    wave_type: WaveType = WaveType.SQUARE
    frequency: float = 440.0
    amplitude: float = 0.5
    envelope: ADSR = None
    detune: float = 0.0  # cents
    pulse_width: float = 0.5  # for pulse wave
    vibrato_rate: float = 0.0  # Hz
    vibrato_depth: float = 0.0  # cents

    def __post_init__(self):
        if self.envelope is None:
            self.envelope = ADSR()
        self._phase = 0.0
        self._noise_value = 0.0
        self._lfsr = 0xACE1  # Linear feedback shift register for noise

    def generate_samples(
        self,
        sample_rate: int,
        duration: float,
        note_off_time: Optional[float] = None
    ) -> array.array:
        """Generate audio samples for this voice."""
        num_samples = int(sample_rate * duration)
        samples = array.array('h')  # signed short

        # Calculate actual frequency with detune
        freq = self.frequency * (2 ** (self.detune / 1200))

        for i in range(num_samples):
            time = i / sample_rate

            # Apply vibrato
            if self.vibrato_rate > 0:
                vibrato = math.sin(2 * math.pi * self.vibrato_rate * time)
                vibrato_cents = vibrato * self.vibrato_depth
                current_freq = freq * (2 ** (vibrato_cents / 1200))
            else:
                current_freq = freq

            # Generate waveform
            sample = self._generate_wave(current_freq, sample_rate)

            # Apply envelope
            env_amp = self.envelope.get_amplitude(time, note_off_time)

            # Apply amplitude and convert to 16-bit
            final = sample * self.amplitude * env_amp
            samples.append(int(max(-32767, min(32767, final * 32767))))

        return samples

    def _generate_wave(self, freq: float, sample_rate: int) -> float:
        """Generate a single sample of the waveform."""
        # Advance phase
        self._phase += freq / sample_rate
        if self._phase >= 1.0:
            self._phase -= 1.0

        phase = self._phase

        if self.wave_type == WaveType.SINE:
            return math.sin(2 * math.pi * phase)

        elif self.wave_type == WaveType.SQUARE:
            return 1.0 if phase < 0.5 else -1.0

        elif self.wave_type == WaveType.PULSE:
            return 1.0 if phase < self.pulse_width else -1.0

        elif self.wave_type == WaveType.SAWTOOTH:
            return 2.0 * phase - 1.0

        elif self.wave_type == WaveType.TRIANGLE:
            if phase < 0.5:
                return 4.0 * phase - 1.0
            else:
                return 3.0 - 4.0 * phase

        elif self.wave_type == WaveType.NOISE:
            # LFSR noise generation
            if phase < self._phase:  # New cycle
                bit = ((self._lfsr >> 0) ^ (self._lfsr >> 2) ^
                       (self._lfsr >> 3) ^ (self._lfsr >> 5)) & 1
                self._lfsr = (self._lfsr >> 1) | (bit << 15)
                self._noise_value = (self._lfsr & 0xFF) / 127.5 - 1.0
            return self._noise_value

        return 0.0


def mix_voices(voices_samples: List[array.array], master_volume: float = 0.7) -> array.array:
    """Mix multiple voice sample arrays together."""
    if not voices_samples:
        return array.array('h')

    # Find longest array
    max_len = max(len(s) for s in voices_samples)
    result = array.array('h', [0] * max_len)

    for samples in voices_samples:
        for i, sample in enumerate(samples):
            # Add with clipping
            mixed = result[i] + int(sample * master_volume / len(voices_samples))
            result[i] = max(-32767, min(32767, mixed))

    return result


def apply_reverb(samples: array.array, delay_ms: float = 100, decay: float = 0.3, sample_rate: int = 44100) -> array.array:
    """Simple comb filter reverb."""
    delay_samples = int(delay_ms * sample_rate / 1000)
    result = array.array('h', samples)

    for i in range(delay_samples, len(result)):
        reverb = int(result[i - delay_samples] * decay)
        result[i] = max(-32767, min(32767, result[i] + reverb))

    return result


def apply_filter(samples: array.array, cutoff: float, resonance: float = 0.5) -> array.array:
    """Simple low-pass filter with resonance."""
    result = array.array('h', samples)
    feedback = resonance + resonance / (1.0 - cutoff + 0.001)

    buf0 = 0.0
    buf1 = 0.0

    for i in range(len(result)):
        sample = result[i] / 32767.0
        buf0 += cutoff * (sample - buf0 + feedback * (buf0 - buf1))
        buf1 += cutoff * (buf0 - buf1)
        result[i] = int(max(-32767, min(32767, buf1 * 32767)))

    return result
