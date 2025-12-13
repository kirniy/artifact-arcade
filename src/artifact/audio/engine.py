"""
ARTIFACT Audio Engine - Synthwave Arcade Sound System.

Comprehensive sound design with:
- Procedural synthesized effects
- Retro 80s synthwave style
- Mode-specific soundscapes
- Ambient loops and jingles
"""

import pygame
import array
import math
import logging
from enum import Enum
from typing import Dict, Optional, Callable
from dataclasses import dataclass

from .synth import SynthVoice, WaveType, ADSR, mix_voices, apply_reverb, apply_filter

logger = logging.getLogger(__name__)


class SoundCategory(Enum):
    """Sound effect categories."""
    UI = "ui"
    GAME = "game"
    AMBIENT = "ambient"
    MUSIC = "music"
    MODE = "mode"


@dataclass
class SoundConfig:
    """Configuration for a sound effect."""
    volume: float = 0.7
    category: SoundCategory = SoundCategory.UI


class AudioEngine:
    """
    Main audio engine for ARTIFACT.

    Generates all sounds procedurally using synthesizers.
    No external audio files needed!
    """

    SAMPLE_RATE = 44100
    CHANNELS = 2  # Stereo

    def __init__(self):
        self._initialized = False
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self._music_playing = False
        self._volume_master = 0.7
        self._volume_sfx = 0.8
        self._volume_music = 0.5
        self._muted = False

        # Sound generation cache
        self._generated = False

    def init(self) -> bool:
        """Initialize the audio system."""
        try:
            pygame.mixer.pre_init(self.SAMPLE_RATE, -16, self.CHANNELS, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self._initialized = True
            logger.info("Audio engine initialized")

            # Pre-generate all sounds
            self._generate_all_sounds()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    def _generate_all_sounds(self) -> None:
        """Generate all sound effects."""
        if self._generated:
            return

        logger.info("Generating synthwave sounds...")

        # === UI SOUNDS ===
        self._generate_button_click()
        self._generate_button_confirm()
        self._generate_menu_move()
        self._generate_back()
        self._generate_error()

        # === GAME SOUNDS ===
        self._generate_countdown_tick()
        self._generate_countdown_go()
        self._generate_success()
        self._generate_failure()
        self._generate_score_up()
        self._generate_wheel_tick()
        self._generate_wheel_stop()
        self._generate_jackpot()

        # === MODE SPECIFIC ===
        self._generate_fortune_mystical()
        self._generate_zodiac_stars()
        self._generate_quiz_correct()
        self._generate_quiz_wrong()
        self._generate_roulette_spin()
        self._generate_prophet_scan()
        self._generate_camera_shutter()
        self._generate_print_sound()

        # === AMBIENT ===
        self._generate_idle_hum()
        self._generate_startup_fanfare()
        self._generate_transition_whoosh()

        self._generated = True
        logger.info(f"Generated {len(self._sounds)} sound effects")

    def _create_sound(self, samples: array.array, stereo: bool = True) -> pygame.mixer.Sound:
        """Create a pygame Sound from samples."""
        if stereo:
            # Duplicate mono to stereo
            stereo_samples = array.array('h')
            for sample in samples:
                stereo_samples.append(sample)  # Left
                stereo_samples.append(sample)  # Right
            samples = stereo_samples

        return pygame.mixer.Sound(buffer=samples)

    # ═══════════════════════════════════════════════════════════════
    # UI SOUNDS
    # ═══════════════════════════════════════════════════════════════

    def _generate_button_click(self) -> None:
        """Short percussive click - arcade button feel."""
        voice = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=800,
            amplitude=0.4,
            envelope=ADSR(attack=0.001, decay=0.05, sustain=0.0, release=0.02)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.08)

        # Add a low thump
        thump = SynthVoice(
            wave_type=WaveType.SINE,
            frequency=150,
            amplitude=0.3,
            envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.02)
        )
        thump_samples = thump.generate_samples(self.SAMPLE_RATE, 0.08)

        mixed = mix_voices([samples, thump_samples])
        self._sounds["button_click"] = self._create_sound(mixed)

    def _generate_button_confirm(self) -> None:
        """Satisfying confirm sound - two-tone rising."""
        voices_samples = []

        # First tone
        v1 = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=523,  # C5
            amplitude=0.3,
            envelope=ADSR(attack=0.01, decay=0.1, sustain=0.4, release=0.1)
        )
        voices_samples.append(v1.generate_samples(self.SAMPLE_RATE, 0.15))

        # Second tone (delayed)
        v2 = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=659,  # E5
            amplitude=0.3,
            envelope=ADSR(attack=0.01, decay=0.15, sustain=0.3, release=0.15)
        )
        s2 = v2.generate_samples(self.SAMPLE_RATE, 0.2)

        # Add delay
        delay = array.array('h', [0] * int(self.SAMPLE_RATE * 0.08))
        delay.extend(s2)
        voices_samples.append(delay)

        mixed = mix_voices(voices_samples)
        mixed = apply_reverb(mixed, delay_ms=80, decay=0.2)
        self._sounds["button_confirm"] = self._create_sound(mixed)

    def _generate_menu_move(self) -> None:
        """Quick blip for menu navigation."""
        voice = SynthVoice(
            wave_type=WaveType.TRIANGLE,
            frequency=440,
            amplitude=0.25,
            envelope=ADSR(attack=0.005, decay=0.04, sustain=0.0, release=0.02)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.06)
        self._sounds["menu_move"] = self._create_sound(samples)

    def _generate_back(self) -> None:
        """Descending tone for back/cancel."""
        voice = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=400,
            amplitude=0.25,
            envelope=ADSR(attack=0.01, decay=0.15, sustain=0.0, release=0.05)
        )
        samples = array.array('h')

        # Descending pitch
        for i in range(int(self.SAMPLE_RATE * 0.2)):
            time = i / self.SAMPLE_RATE
            freq = 400 * (1 - time * 2)  # Descend
            freq = max(100, freq)
            voice.frequency = freq
            s = voice.generate_samples(self.SAMPLE_RATE, 1/self.SAMPLE_RATE)
            if s:
                samples.append(s[0])

        self._sounds["back"] = self._create_sound(samples)

    def _generate_error(self) -> None:
        """Harsh error buzz."""
        voice = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=120,
            amplitude=0.3,
            envelope=ADSR(attack=0.01, decay=0.1, sustain=0.5, release=0.1),
            pulse_width=0.3
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.25)
        self._sounds["error"] = self._create_sound(samples)

    # ═══════════════════════════════════════════════════════════════
    # GAME SOUNDS
    # ═══════════════════════════════════════════════════════════════

    def _generate_countdown_tick(self) -> None:
        """Tick for countdown timer."""
        voice = SynthVoice(
            wave_type=WaveType.SINE,
            frequency=1000,
            amplitude=0.2,
            envelope=ADSR(attack=0.001, decay=0.05, sustain=0.0, release=0.02)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.08)
        self._sounds["countdown_tick"] = self._create_sound(samples)

    def _generate_countdown_go(self) -> None:
        """Exciting GO! sound."""
        voices = []

        # Main tone chord
        for freq in [523, 659, 784]:  # C-E-G major chord
            v = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.02, decay=0.3, sustain=0.3, release=0.3)
            )
            voices.append(v.generate_samples(self.SAMPLE_RATE, 0.6))

        # Rising sweep
        sweep = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=200,
            amplitude=0.15,
            envelope=ADSR(attack=0.1, decay=0.2, sustain=0.0, release=0.1)
        )
        sweep_samples = array.array('h')
        for i in range(int(self.SAMPLE_RATE * 0.4)):
            time = i / self.SAMPLE_RATE
            sweep.frequency = 200 + time * 1500
            s = sweep.generate_samples(self.SAMPLE_RATE, 1/self.SAMPLE_RATE)
            if s:
                sweep_samples.append(s[0])
        voices.append(sweep_samples)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=100, decay=0.25)
        self._sounds["countdown_go"] = self._create_sound(mixed)

    def _generate_success(self) -> None:
        """Triumphant success fanfare."""
        voices = []

        # Arpeggio up
        notes = [523, 659, 784, 1047]  # C5 E5 G5 C6
        for i, freq in enumerate(notes):
            v = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.01, decay=0.2, sustain=0.3, release=0.2)
            )
            s = v.generate_samples(self.SAMPLE_RATE, 0.4)
            # Add delay for each note
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.08))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=120, decay=0.3)
        self._sounds["success"] = self._create_sound(mixed)

    def _generate_failure(self) -> None:
        """Sad failure sound - descending."""
        voice = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=400,
            amplitude=0.3,
            envelope=ADSR(attack=0.05, decay=0.3, sustain=0.2, release=0.3)
        )
        samples = array.array('h')

        for i in range(int(self.SAMPLE_RATE * 0.5)):
            time = i / self.SAMPLE_RATE
            voice.frequency = 400 - time * 300  # Descend sadly
            s = voice.generate_samples(self.SAMPLE_RATE, 1/self.SAMPLE_RATE)
            if s:
                samples.append(s[0])

        self._sounds["failure"] = self._create_sound(samples)

    def _generate_score_up(self) -> None:
        """Quick score increment sound."""
        voice = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=800,
            amplitude=0.2,
            envelope=ADSR(attack=0.005, decay=0.08, sustain=0.0, release=0.02)
        )
        samples = array.array('h')

        # Quick rising sweep
        for i in range(int(self.SAMPLE_RATE * 0.1)):
            time = i / self.SAMPLE_RATE
            voice.frequency = 800 + time * 4000
            s = voice.generate_samples(self.SAMPLE_RATE, 1/self.SAMPLE_RATE)
            if s:
                samples.append(s[0])

        self._sounds["score_up"] = self._create_sound(samples)

    def _generate_wheel_tick(self) -> None:
        """Roulette wheel tick."""
        voice = SynthVoice(
            wave_type=WaveType.NOISE,
            frequency=100,
            amplitude=0.15,
            envelope=ADSR(attack=0.001, decay=0.02, sustain=0.0, release=0.01)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.03)
        self._sounds["wheel_tick"] = self._create_sound(samples)

    def _generate_wheel_stop(self) -> None:
        """Wheel stopping - dramatic reveal."""
        voices = []

        # Dramatic chord
        for freq in [261, 329, 392]:  # C E G
            v = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.1, decay=0.3, sustain=0.4, release=0.5)
            )
            voices.append(v.generate_samples(self.SAMPLE_RATE, 1.0))

        # Impact
        impact = SynthVoice(
            wave_type=WaveType.NOISE,
            frequency=80,
            amplitude=0.3,
            envelope=ADSR(attack=0.01, decay=0.1, sustain=0.0, release=0.1)
        )
        voices.append(impact.generate_samples(self.SAMPLE_RATE, 0.2))

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=150, decay=0.35)
        self._sounds["wheel_stop"] = self._create_sound(mixed)

    def _generate_jackpot(self) -> None:
        """JACKPOT! Exciting winning sound."""
        voices = []

        # Fanfare arpeggios
        notes = [523, 659, 784, 1047, 784, 659, 523, 659, 784, 1047, 1319]
        for i, freq in enumerate(notes):
            v = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.01, decay=0.15, sustain=0.2, release=0.15),
                detune=5 if i % 2 else -5
            )
            s = v.generate_samples(self.SAMPLE_RATE, 0.25)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.06))
            delay.extend(s)
            voices.append(delay)

        # Bass hits
        for i in range(4):
            bass = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=65,
                amplitude=0.3,
                envelope=ADSR(attack=0.01, decay=0.15, sustain=0.0, release=0.1)
            )
            s = bass.generate_samples(self.SAMPLE_RATE, 0.2)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.2))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=100, decay=0.3)
        self._sounds["jackpot"] = self._create_sound(mixed)

    # ═══════════════════════════════════════════════════════════════
    # MODE SPECIFIC SOUNDS
    # ═══════════════════════════════════════════════════════════════

    def _generate_fortune_mystical(self) -> None:
        """Mystical fortune-telling ambiance."""
        voices = []

        # Ethereal pad
        for freq in [220, 277, 330, 440]:  # Am7 chord
            v = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=freq,
                amplitude=0.15,
                envelope=ADSR(attack=0.5, decay=0.5, sustain=0.6, release=0.5),
                vibrato_rate=4,
                vibrato_depth=15
            )
            voices.append(v.generate_samples(self.SAMPLE_RATE, 2.5))

        # Sparkle
        sparkle = SynthVoice(
            wave_type=WaveType.TRIANGLE,
            frequency=2000,
            amplitude=0.08,
            envelope=ADSR(attack=0.01, decay=0.3, sustain=0.0, release=0.2)
        )
        for i in range(5):
            s = sparkle.generate_samples(self.SAMPLE_RATE, 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.4))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=200, decay=0.4)
        mixed = apply_filter(mixed, cutoff=0.3)
        self._sounds["fortune_mystical"] = self._create_sound(mixed)

    def _generate_zodiac_stars(self) -> None:
        """Cosmic zodiac atmosphere."""
        voices = []

        # Deep space drone
        drone = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=55,
            amplitude=0.15,
            envelope=ADSR(attack=1.0, decay=0.5, sustain=0.5, release=1.0),
            detune=3
        )
        voices.append(drone.generate_samples(self.SAMPLE_RATE, 3.0))

        # High sparkles
        for i in range(8):
            freq = 1500 + i * 200
            v = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=freq,
                amplitude=0.05,
                envelope=ADSR(attack=0.01, decay=0.2, sustain=0.0, release=0.3)
            )
            s = v.generate_samples(self.SAMPLE_RATE, 0.5)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.3))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=250, decay=0.45)
        self._sounds["zodiac_stars"] = self._create_sound(mixed)

    def _generate_quiz_correct(self) -> None:
        """Correct answer - positive ding."""
        voices = []

        # Main chime
        for freq in [880, 1109]:  # A5, C#6
            v = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.01, decay=0.2, sustain=0.2, release=0.3)
            )
            voices.append(v.generate_samples(self.SAMPLE_RATE, 0.5))

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=60, decay=0.2)
        self._sounds["quiz_correct"] = self._create_sound(mixed)

    def _generate_quiz_wrong(self) -> None:
        """Wrong answer - sad buzz."""
        voice = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=150,
            amplitude=0.25,
            envelope=ADSR(attack=0.02, decay=0.2, sustain=0.3, release=0.15)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.4)
        self._sounds["quiz_wrong"] = self._create_sound(samples)

    def _generate_roulette_spin(self) -> None:
        """Wheel spinning up sound."""
        samples = array.array('h')

        # Accelerating clicks
        click_interval = 0.1
        for i in range(30):
            # Click gets faster
            click_interval *= 0.92
            num_silent = int(self.SAMPLE_RATE * click_interval)

            # Click sound
            click = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=100,
                amplitude=0.2 + i * 0.01,
                envelope=ADSR(attack=0.001, decay=0.01, sustain=0.0, release=0.005)
            )
            click_samples = click.generate_samples(self.SAMPLE_RATE, 0.02)
            samples.extend(click_samples)
            samples.extend(array.array('h', [0] * num_silent))

        self._sounds["roulette_spin"] = self._create_sound(samples)

    def _generate_prophet_scan(self) -> None:
        """AI scanning/processing sound."""
        samples = array.array('h')

        # Electronic scanning sweep
        for i in range(int(self.SAMPLE_RATE * 1.5)):
            time = i / self.SAMPLE_RATE
            # Modulated frequency
            freq = 300 + 200 * math.sin(time * 10) + 100 * math.sin(time * 23)

            phase = (i * freq / self.SAMPLE_RATE) % 1.0
            sample = math.sin(2 * math.pi * phase) * 0.15

            # Add some digital artifacts
            if i % 100 < 10:
                sample += 0.1 * (1 if phase < 0.5 else -1)

            # Envelope
            env = min(1.0, time * 3) * max(0, 1 - (time - 1.2) * 3)

            samples.append(int(sample * env * 32767))

        mixed = apply_reverb(samples, delay_ms=80, decay=0.2)
        self._sounds["prophet_scan"] = self._create_sound(mixed)

    def _generate_camera_shutter(self) -> None:
        """Camera capture sound."""
        voice = SynthVoice(
            wave_type=WaveType.NOISE,
            frequency=200,
            amplitude=0.3,
            envelope=ADSR(attack=0.001, decay=0.05, sustain=0.0, release=0.03)
        )
        samples = voice.generate_samples(self.SAMPLE_RATE, 0.1)

        # Add click
        click = SynthVoice(
            wave_type=WaveType.SQUARE,
            frequency=2000,
            amplitude=0.2,
            envelope=ADSR(attack=0.001, decay=0.01, sustain=0.0, release=0.01)
        )
        click_samples = click.generate_samples(self.SAMPLE_RATE, 0.03)

        mixed = mix_voices([samples, click_samples])
        self._sounds["camera_shutter"] = self._create_sound(mixed)

    def _generate_print_sound(self) -> None:
        """Thermal printer sound."""
        samples = array.array('h')

        # Mechanical printer noise
        for i in range(int(self.SAMPLE_RATE * 2.0)):
            time = i / self.SAMPLE_RATE

            # Base noise
            noise = (hash(i) % 1000 - 500) / 5000.0

            # Periodic mechanical sounds
            mech = 0.1 * math.sin(time * 200) * math.sin(time * 50)

            # Stepping motor
            step = 0.05 * (1 if (int(time * 30) % 2) else -1)

            sample = noise + mech + step

            # Fade out
            env = max(0, 1 - time / 2.0)

            samples.append(int(sample * env * 32767))

        self._sounds["print_sound"] = self._create_sound(samples)

    # ═══════════════════════════════════════════════════════════════
    # AMBIENT SOUNDS
    # ═══════════════════════════════════════════════════════════════

    def _generate_idle_hum(self) -> None:
        """Low ambient hum for idle state."""
        voices = []

        # Deep drone
        drone = SynthVoice(
            wave_type=WaveType.SINE,
            frequency=60,
            amplitude=0.08,
            envelope=ADSR(attack=1.0, decay=0.5, sustain=0.8, release=1.0),
            vibrato_rate=0.5,
            vibrato_depth=5
        )
        voices.append(drone.generate_samples(self.SAMPLE_RATE, 4.0))

        # High harmonic
        harmonic = SynthVoice(
            wave_type=WaveType.SINE,
            frequency=180,
            amplitude=0.03,
            envelope=ADSR(attack=1.0, decay=0.5, sustain=0.5, release=1.0)
        )
        voices.append(harmonic.generate_samples(self.SAMPLE_RATE, 4.0))

        mixed = mix_voices(voices)
        mixed = apply_filter(mixed, cutoff=0.2)
        self._sounds["idle_hum"] = self._create_sound(mixed)

    def _generate_startup_fanfare(self) -> None:
        """Epic startup fanfare - Stranger Things inspired."""
        voices = []

        # Deep synth bass
        bass_notes = [65, 65, 82, 98]  # C2, C2, E2, G2
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.1, decay=0.3, sustain=0.5, release=0.3),
                detune=5
            )
            s = bass.generate_samples(self.SAMPLE_RATE, 0.6)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.4))
            delay.extend(s)
            voices.append(delay)

        # Synth lead - rising arpeggio
        lead_notes = [262, 330, 392, 523, 659, 784, 1047]
        for i, freq in enumerate(lead_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.15,
                envelope=ADSR(attack=0.02, decay=0.15, sustain=0.3, release=0.2),
                pulse_width=0.3
            )
            s = lead.generate_samples(self.SAMPLE_RATE, 0.3)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * (0.3 + i * 0.1)))
            delay.extend(s)
            voices.append(delay)

        # Pad chord
        for freq in [262, 330, 392]:  # C major
            pad = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.1,
                envelope=ADSR(attack=0.5, decay=0.5, sustain=0.6, release=0.8)
            )
            s = pad.generate_samples(self.SAMPLE_RATE, 2.5)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Dramatic hit
        hit = SynthVoice(
            wave_type=WaveType.NOISE,
            frequency=100,
            amplitude=0.2,
            envelope=ADSR(attack=0.01, decay=0.1, sustain=0.0, release=0.2)
        )
        hit_samples = hit.generate_samples(self.SAMPLE_RATE, 0.3)
        delay = array.array('h', [0] * int(self.SAMPLE_RATE * 1.5))
        delay.extend(hit_samples)
        voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=150, decay=0.35)
        mixed = apply_filter(mixed, cutoff=0.6, resonance=0.3)
        self._sounds["startup_fanfare"] = self._create_sound(mixed)

    def _generate_transition_whoosh(self) -> None:
        """Whoosh sound for transitions."""
        samples = array.array('h')

        for i in range(int(self.SAMPLE_RATE * 0.3)):
            time = i / self.SAMPLE_RATE

            # Filtered noise sweep
            noise = (hash(i * 7) % 1000 - 500) / 500.0

            # High to low sweep
            freq = 3000 - time * 8000
            freq = max(100, freq)

            # Envelope
            env = math.sin(time * math.pi / 0.3) * 0.3

            samples.append(int(noise * env * 32767))

        mixed = apply_filter(samples, cutoff=0.4)
        self._sounds["transition_whoosh"] = self._create_sound(mixed)

    # ═══════════════════════════════════════════════════════════════
    # PLAYBACK API
    # ═══════════════════════════════════════════════════════════════

    def play(self, sound_name: str, volume: float = 1.0, loops: int = 0) -> Optional[pygame.mixer.Channel]:
        """Play a sound effect."""
        if not self._initialized or self._muted:
            return None

        sound = self._sounds.get(sound_name)
        if not sound:
            logger.warning(f"Sound not found: {sound_name}")
            return None

        sound.set_volume(volume * self._volume_sfx * self._volume_master)
        return sound.play(loops=loops)

    def play_ui_click(self) -> None:
        """Play button click sound."""
        self.play("button_click")

    def play_ui_confirm(self) -> None:
        """Play confirmation sound."""
        self.play("button_confirm")

    def play_ui_move(self) -> None:
        """Play menu move sound."""
        self.play("menu_move")

    def play_ui_back(self) -> None:
        """Play back/cancel sound."""
        self.play("back")

    def play_ui_error(self) -> None:
        """Play error sound."""
        self.play("error")

    def play_countdown_tick(self) -> None:
        """Play countdown tick."""
        self.play("countdown_tick")

    def play_countdown_go(self) -> None:
        """Play GO! sound."""
        self.play("countdown_go")

    def play_success(self) -> None:
        """Play success fanfare."""
        self.play("success")

    def play_failure(self) -> None:
        """Play failure sound."""
        self.play("failure")

    def play_score_up(self) -> None:
        """Play score increment sound."""
        self.play("score_up")

    def play_jackpot(self) -> None:
        """Play jackpot celebration."""
        self.play("jackpot")

    def play_wheel_tick(self) -> None:
        """Play wheel tick."""
        self.play("wheel_tick", volume=0.5)

    def play_wheel_stop(self) -> None:
        """Play wheel stop reveal."""
        self.play("wheel_stop")

    def play_startup(self) -> None:
        """Play startup fanfare."""
        self.play("startup_fanfare")

    def play_transition(self) -> None:
        """Play transition whoosh."""
        self.play("transition_whoosh")

    def play_mode_ambient(self, mode_name: str) -> Optional[pygame.mixer.Channel]:
        """Play mode-specific ambient sound."""
        sound_map = {
            "fortune": "fortune_mystical",
            "zodiac": "zodiac_stars",
            "ai_prophet": "prophet_scan",
        }
        sound_name = sound_map.get(mode_name)
        if sound_name:
            return self.play(sound_name, loops=-1)  # Loop
        return None

    def play_camera_shutter(self) -> None:
        """Play camera capture sound."""
        self.play("camera_shutter")

    def play_print(self) -> None:
        """Play printing sound."""
        self.play("print_sound")

    def play_quiz_correct(self) -> None:
        """Play correct answer sound."""
        self.play("quiz_correct")

    def play_quiz_wrong(self) -> None:
        """Play wrong answer sound."""
        self.play("quiz_wrong")

    def play_roulette_spin(self) -> None:
        """Play roulette spin sound."""
        self.play("roulette_spin")

    def start_idle_ambient(self) -> pygame.mixer.Channel:
        """Start idle ambient loop."""
        return self.play("idle_hum", loops=-1, volume=0.3)

    def stop_all(self) -> None:
        """Stop all currently playing sounds."""
        pygame.mixer.stop()

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 - 1.0)."""
        self._volume_master = max(0.0, min(1.0, volume))

    def set_sfx_volume(self, volume: float) -> None:
        """Set SFX volume (0.0 - 1.0)."""
        self._volume_sfx = max(0.0, min(1.0, volume))

    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns new mute state."""
        self._muted = not self._muted
        if self._muted:
            pygame.mixer.pause()
        else:
            pygame.mixer.unpause()
        return self._muted

    def cleanup(self) -> None:
        """Cleanup audio resources."""
        if self._initialized:
            pygame.mixer.quit()
            self._initialized = False
            logger.info("Audio engine cleaned up")


# Global audio engine instance
_audio_engine: Optional[AudioEngine] = None


def get_audio_engine() -> AudioEngine:
    """Get the global audio engine instance."""
    global _audio_engine
    if _audio_engine is None:
        _audio_engine = AudioEngine()
    return _audio_engine
