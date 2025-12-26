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
        self._volume_master = 1.0  # MAX VOLUME BABY!
        self._volume_sfx = 1.0  # FULL BLAST!
        self._volume_music = 1.0  # 100% LOUD music!
        self._muted = False

        # Music playback state
        self._current_music: Optional[str] = None
        self._music_channel: Optional[pygame.mixer.Channel] = None

        # Sound generation cache
        self._generated = False

    def init(self, skip_generation: bool = False) -> bool:
        """Initialize the audio system.

        Args:
            skip_generation: If True, skip procedural sound generation for faster startup
        """
        try:
            pygame.mixer.pre_init(self.SAMPLE_RATE, -16, self.CHANNELS, 2048)  # Larger buffer
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self._initialized = True
            logger.info("Audio engine initialized")

            # Skip sound generation for faster startup (sounds can be generated later)
            if not skip_generation:
                self._generate_all_sounds()
            else:
                logger.info("Skipping sound generation for faster startup")
                self._generated = True  # Pretend we generated them
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

        # === BANGER SYNTHWAVE MUSIC LOOPS ===
        self._generate_idle_music()
        self._generate_menu_music()
        self._generate_fortune_music()
        self._generate_quiz_music()
        self._generate_roulette_music()
        self._generate_roast_music()
        self._generate_flow_field_music()
        self._generate_glitch_mirror_music()
        self._generate_particle_sculptor_music()
        self._generate_ascii_music()
        self._generate_tower_stack_music()
        self._generate_bar_runner_music()
        self._generate_brick_breaker_music()
        self._generate_squid_game_music()

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
    # BANGER SYNTHWAVE MUSIC - Stranger Things inspired loops
    # ═══════════════════════════════════════════════════════════════

    def _generate_idle_music(self) -> None:
        """FUN arcade attract music - catchy, upbeat, makes you wanna play!"""
        voices = []
        duration = 8.0  # 8 second loop
        bpm = 128  # Dance tempo!
        beat = 60.0 / bpm

        # FUNKY BASS LINE - octave jumps, syncopated groove
        bass_pattern = [
            (130.8, 0), (130.8, 0.5), (261.6, 0.75),  # C3, C3, C4
            (146.8, 1), (146.8, 1.5), (293.7, 1.75),  # D3, D3, D4
            (164.8, 2), (164.8, 2.5), (329.6, 2.75),  # E3, E3, E4
            (146.8, 3), (196.0, 3.5), (146.8, 3.75),  # D3, G3, D3
            (130.8, 4), (130.8, 4.5), (261.6, 4.75),  # repeat
            (146.8, 5), (146.8, 5.5), (293.7, 5.75),
            (174.6, 6), (220.0, 6.5), (174.6, 6.75),  # F3, A3, F3
            (196.0, 7), (261.6, 7.25), (196.0, 7.5),  # G3, C4, G3
        ]
        for freq, time in bass_pattern:
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.35,  # THICC bass
                envelope=ADSR(attack=0.01, decay=0.1, sustain=0.4, release=0.08),
                detune=5
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * time * beat))
            delay.extend(s)
            voices.append(delay)

        # CATCHY ARPEGGIO LEAD - classic 80s arcade melody
        arp_notes = [
            (523, 0), (659, 0.25), (784, 0.5), (1047, 0.75),  # C-E-G-C up
            (988, 1), (784, 1.25), (659, 1.5), (523, 1.75),    # B-G-E-C down
            (587, 2), (698, 2.25), (880, 2.5), (1175, 2.75),  # D-F-A-D up
            (1047, 3), (880, 3.25), (698, 3.5), (587, 3.75),  # C-A-F-D down
            (523, 4), (659, 4.25), (784, 4.5), (1047, 4.75),  # repeat first half
            (988, 5), (784, 5.25), (659, 5.5), (523, 5.75),
            (698, 6), (880, 6.25), (1047, 6.5), (1319, 6.75), # F-A-C-E up (big!)
            (1175, 7), (1047, 7.25), (880, 7.5), (784, 7.75), # resolve down
        ]
        for freq, time in arp_notes:
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.2,  # BRIGHT lead!
                envelope=ADSR(attack=0.01, decay=0.08, sustain=0.2, release=0.1),
                pulse_width=0.4
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.22)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * time * beat))
            delay.extend(s)
            voices.append(delay)

        # BRIGHT CHORD STABS - fun major chords
        chord_times = [0, 1, 2, 3, 4, 5, 6, 7]
        chord_freqs = [
            [262, 330, 392],  # C major
            [294, 370, 440],  # D major
            [330, 415, 494],  # E major
            [294, 370, 440],  # D major
            [262, 330, 392],  # C major
            [294, 370, 440],  # D major
            [349, 440, 523],  # F major
            [392, 494, 587],  # G major
        ]
        for i, t in enumerate(chord_times):
            for freq in chord_freqs[i]:
                chord = SynthVoice(
                    wave_type=WaveType.SAWTOOTH,
                    frequency=freq,
                    amplitude=0.12,  # PUNCHY chords
                    envelope=ADSR(attack=0.02, decay=0.15, sustain=0.15, release=0.15),
                    detune=8
                )
                s = chord.generate_samples(self.SAMPLE_RATE, beat * 0.3)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * (t * beat + beat * 0.5)))
                delay.extend(s)
                voices.append(delay)

        # PUNCHY DRUMS - four on the floor with energy!
        for i in range(16):  # 16 beats
            t = i * beat * 0.5

            # KICK on every beat - BOOM!
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=50,
                    amplitude=0.45,  # HEAVY kick
                    envelope=ADSR(attack=0.005, decay=0.15, sustain=0.0, release=0.05)
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.18)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            # SNARE on 2 and 4 - CRACK!
            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=200,
                    amplitude=0.25,  # PUNCHY snare
                    envelope=ADSR(attack=0.005, decay=0.12, sustain=0.0, release=0.05)
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.14)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            # HI-HAT on every 8th note - TSS TSS TSS
            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=8000,
                amplitude=0.1 if i % 2 == 0 else 0.07,  # accent on beats
                envelope=ADSR(attack=0.001, decay=0.04, sustain=0.0, release=0.01)
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.04)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=80, decay=0.2)
        self._sounds["music_idle"] = self._create_sound(mixed)

    def _generate_menu_music(self) -> None:
        """Upbeat menu music - 80s arcade synthwave."""
        voices = []
        duration = 4.0
        bpm = 120
        beat = 60.0 / bpm

        # Punchy bass sequence (classic synthwave pattern)
        bass_pattern = [55, 55, 82, 55, 73, 55, 82, 98]  # A1-E2-D2-E2-G2
        for i, freq in enumerate(bass_pattern):
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.01, decay=0.1, sustain=0.3, release=0.1),
                detune=5
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Synth lead arpeggio
        arp_notes = [440, 523, 659, 523, 440, 659, 784, 659]  # A4-C5-E5 pattern
        for i, freq in enumerate(arp_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.12,
                envelope=ADSR(attack=0.01, decay=0.1, sustain=0.2, release=0.1),
                pulse_width=0.3
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.3)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Drums - kick and snare
        for i in range(8):
            # Kick on beats 0, 2, 4, 6
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=60,
                    amplitude=0.3,
                    envelope=ADSR(attack=0.01, decay=0.1, sustain=0.0, release=0.05)
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.15)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
                delay.extend(s)
                voices.append(delay)

            # Snare on beats 1, 3, 5, 7
            if i % 2 == 1:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=200,
                    amplitude=0.15,
                    envelope=ADSR(attack=0.005, decay=0.1, sustain=0.0, release=0.05)
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.12)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
                delay.extend(s)
                voices.append(delay)

        # Hi-hat pattern
        for i in range(16):
            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=8000,
                amplitude=0.06,
                envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.01)
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.04)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.25))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=80, decay=0.2)
        self._sounds["music_menu"] = self._create_sound(mixed)

    def _generate_fortune_music(self) -> None:
        """Mystical fortune music - ethereal and mysterious."""
        voices = []
        duration = 6.0

        # Deep drone in Dm
        drone = SynthVoice(
            wave_type=WaveType.SAWTOOTH,
            frequency=73.4,  # D2
            amplitude=0.15,
            envelope=ADSR(attack=2.0, decay=1.0, sustain=0.6, release=2.0),
            detune=5
        )
        voices.append(drone.generate_samples(self.SAMPLE_RATE, duration))

        # Mystical pad (Dm7 chord)
        for freq in [147, 175, 220, 262]:  # D3, F3, A3, C4
            pad = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=freq,
                amplitude=0.08,
                envelope=ADSR(attack=1.5, decay=1.0, sustain=0.5, release=1.5),
                vibrato_rate=0.5,
                vibrato_depth=8
            )
            voices.append(pad.generate_samples(self.SAMPLE_RATE, duration))

        # Sparkle arpeggios
        sparkle_notes = [587, 698, 880, 1047, 880, 698, 587, 523]
        for i, freq in enumerate(sparkle_notes):
            sparkle = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.05,
                envelope=ADSR(attack=0.01, decay=0.3, sustain=0.0, release=0.4)
            )
            s = sparkle.generate_samples(self.SAMPLE_RATE, 0.5)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.7))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=300, decay=0.5)
        mixed = apply_filter(mixed, cutoff=0.35, resonance=0.15)
        self._sounds["music_fortune"] = self._create_sound(mixed)

    def _generate_quiz_music(self) -> None:
        """Intense quiz music - tension building synthwave."""
        voices = []
        duration = 4.0
        bpm = 130
        beat = 60.0 / bpm

        # Driving bass
        bass_pattern = [110, 110, 147, 110, 131, 110, 165, 147]
        for i, freq in enumerate(bass_pattern):
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.22,
                envelope=ADSR(attack=0.01, decay=0.08, sustain=0.2, release=0.05),
                detune=3
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Tension chord stabs
        chord_times = [0, beat * 1.5, beat * 3]
        for t in chord_times:
            for freq in [220, 262, 330]:  # Am chord
                stab = SynthVoice(
                    wave_type=WaveType.SQUARE,
                    frequency=freq,
                    amplitude=0.1,
                    envelope=ADSR(attack=0.01, decay=0.2, sustain=0.1, release=0.2),
                    pulse_width=0.4
                )
                s = stab.generate_samples(self.SAMPLE_RATE, 0.3)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

        # Fast hi-hats for urgency
        for i in range(16):
            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=6000,
                amplitude=0.08,
                envelope=ADSR(attack=0.001, decay=0.02, sustain=0.0, release=0.01)
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.03)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.25))
            delay.extend(s)
            voices.append(delay)

        # Kick drum
        for i in range(4):
            kick = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=55,
                amplitude=0.3,
                envelope=ADSR(attack=0.01, decay=0.1, sustain=0.0, release=0.05)
            )
            s = kick.generate_samples(self.SAMPLE_RATE, 0.15)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=60, decay=0.15)
        self._sounds["music_quiz"] = self._create_sound(mixed)

    def _generate_roulette_music(self) -> None:
        """Exciting roulette music - casino synthwave."""
        voices = []
        duration = 4.0
        bpm = 125
        beat = 60.0 / bpm

        # Groovy bass line
        bass_notes = [65, 65, 82, 98, 73, 65, 82, 65]  # C2-E2-G2-D2 pattern
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.01, decay=0.12, sustain=0.25, release=0.08),
                detune=4
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.45)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Funky synth chords
        for i in range(4):
            for freq in [262, 330, 392]:  # C major
                chord = SynthVoice(
                    wave_type=WaveType.SQUARE,
                    frequency=freq,
                    amplitude=0.08,
                    envelope=ADSR(attack=0.01, decay=0.15, sustain=0.2, release=0.1),
                    pulse_width=0.35
                )
                s = chord.generate_samples(self.SAMPLE_RATE, 0.2)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat))
                delay.extend(s)
                voices.append(delay)

        # Funky drums
        for i in range(8):
            # Kick
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=55,
                    amplitude=0.28,
                    envelope=ADSR(attack=0.01, decay=0.12, sustain=0.0, release=0.05)
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.15)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
                delay.extend(s)
                voices.append(delay)

            # Snare
            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=180,
                    amplitude=0.18,
                    envelope=ADSR(attack=0.005, decay=0.12, sustain=0.0, release=0.05)
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.14)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
                delay.extend(s)
                voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=70, decay=0.2)
        self._sounds["music_roulette"] = self._create_sound(mixed)

    def _generate_roast_music(self) -> None:
        """Aggressive roast music - hard-hitting synthwave."""
        voices = []
        duration = 4.0
        bpm = 135
        beat = 60.0 / bpm

        # Heavy distorted bass
        bass_notes = [55, 55, 73, 55, 65, 55, 82, 73]  # Aggressive pattern
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.25,
                envelope=ADSR(attack=0.005, decay=0.1, sustain=0.3, release=0.05),
                pulse_width=0.2
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Aggressive synth stabs
        for i in range(4):
            for freq in [220, 277, 330]:  # A minor
                stab = SynthVoice(
                    wave_type=WaveType.SAWTOOTH,
                    frequency=freq,
                    amplitude=0.12,
                    envelope=ADSR(attack=0.01, decay=0.08, sustain=0.1, release=0.05),
                    detune=10
                )
                s = stab.generate_samples(self.SAMPLE_RATE, 0.15)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * (i * beat + beat * 0.75)))
                delay.extend(s)
                voices.append(delay)

        # Hard-hitting drums
        for i in range(8):
            # Heavy kick
            kick = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=50,
                amplitude=0.35,
                envelope=ADSR(attack=0.005, decay=0.15, sustain=0.0, release=0.05)
            )
            s = kick.generate_samples(self.SAMPLE_RATE, 0.18)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

            # Clap/snare
            if i % 2 == 1:
                clap = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=250,
                    amplitude=0.2,
                    envelope=ADSR(attack=0.001, decay=0.08, sustain=0.0, release=0.05)
                )
                s = clap.generate_samples(self.SAMPLE_RATE, 0.1)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
                delay.extend(s)
                voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=50, decay=0.15)
        self._sounds["music_roast"] = self._create_sound(mixed)

    def _generate_flow_field_music(self) -> None:
        """Dreamy flow-field music - airy pads + drifting arps."""
        voices = []
        duration = 8.0
        bpm = 105
        beat = 60.0 / bpm

        # Soft noise pad with filter sweep
        pad = SynthVoice(
            wave_type=WaveType.NOISE,
            frequency=400,
            amplitude=0.06,
            envelope=ADSR(attack=1.5, decay=1.0, sustain=0.4, release=1.5),
            vibrato_rate=0.2,
            vibrato_depth=6,
        )
        pad_samples = pad.generate_samples(self.SAMPLE_RATE, duration)
        pad_samples = apply_filter(pad_samples, cutoff=0.25, resonance=0.4)
        voices.append(pad_samples)

        # Glassy pluck arps (minor 7th flavor)
        arp_notes = [261, 311, 392, 466, 392, 311, 261, 233]  # Cm7-ish
        for i, freq in enumerate(arp_notes):
            pluck = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.1,
                envelope=ADSR(attack=0.005, decay=0.25, sustain=0.05, release=0.15),
                vibrato_rate=1.2,
                vibrato_depth=5,
            )
            s = pluck.generate_samples(self.SAMPLE_RATE, beat * 0.45)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.75))
            delay.extend(s)
            voices.append(delay)

        # Swirling chorus pad (two detuned sines)
        for detune in (-3, 3):
            swirl = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=98 + detune,  # G2 base
                amplitude=0.08,
                envelope=ADSR(attack=1.0, decay=0.8, sustain=0.6, release=1.2),
                vibrato_rate=0.35,
                vibrato_depth=12,
            )
            voices.append(swirl.generate_samples(self.SAMPLE_RATE, duration))

        # Gentle pulse kick every 2 beats to anchor
        for i in range(int(duration / (beat * 2))):
            t = i * beat * 2
            kick = SynthVoice(
                wave_type=WaveType.SINE,
                frequency=45,
                amplitude=0.2,
                envelope=ADSR(attack=0.005, decay=0.18, sustain=0.0, release=0.12),
            )
            s = kick.generate_samples(self.SAMPLE_RATE, 0.18)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=180, decay=0.35)
        mixed = apply_filter(mixed, cutoff=0.45, resonance=0.2)
        self._sounds["music_flow_field"] = self._create_sound(mixed)

    def _generate_glitch_mirror_music(self) -> None:
        """Glitch mirror music - crunchy bitcrush + detuned drones."""
        voices = []
        duration = 6.0

        # Detuned dual drone with slow phasing
        for detune in (-6, 6):
            drone = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=130 + detune,
                amplitude=0.12,
                envelope=ADSR(attack=1.0, decay=0.6, sustain=0.5, release=1.0),
                vibrato_rate=0.4,
                vibrato_depth=9,
            )
            samples = drone.generate_samples(self.SAMPLE_RATE, duration)
            samples = apply_filter(samples, cutoff=0.3, resonance=0.25)
            voices.append(samples)

        # Bitcrushed arp
        arp_notes = [392, 466, 523, 659, 523, 466, 392, 349]
        for i, freq in enumerate(arp_notes):
            arp = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.09,
                envelope=ADSR(attack=0.005, decay=0.15, sustain=0.05, release=0.1),
                pulse_width=0.25,
            )
            s = arp.generate_samples(self.SAMPLE_RATE, 0.35)
            # crude bitcrush by downsampling every 3rd sample
            crushed = array.array('h', [s[j] for j in range(0, len(s), 3)])
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * 0.45))
            delay.extend(crushed)
            voices.append(delay)

        # Glitch percussion ticks
        for i in range(16):
            tick = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=6000,
                amplitude=0.08,
                envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.01),
            )
            s = tick.generate_samples(self.SAMPLE_RATE, 0.03)
            # jitter the start time slightly
            jitter = (i * 0.35) + (0.02 if i % 3 == 0 else 0)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * jitter))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=90, decay=0.25)
        self._sounds["music_glitch_mirror"] = self._create_sound(mixed)

    def _generate_particle_sculptor_music(self) -> None:
        """Particle Sculptor music - rhythmic hammering with epic pad."""
        voices = []
        duration = 6.0
        bpm = 118
        beat = 60.0 / bpm

        # Heavy anvils (pitched noise)
        for i in range(12):
            anv = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=400 + i * 5,
                amplitude=0.18,
                envelope=ADSR(attack=0.002, decay=0.15, sustain=0.0, release=0.08),
            )
            s = anv.generate_samples(self.SAMPLE_RATE, 0.12)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Epic minor-pad swell
        for freq in [196, 233, 311, 392]:  # Gm chord tones
            pad = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.1,
                envelope=ADSR(attack=0.8, decay=0.6, sustain=0.4, release=0.8),
                detune=7,
            )
            samples = pad.generate_samples(self.SAMPLE_RATE, duration)
            samples = apply_filter(samples, cutoff=0.4, resonance=0.2)
            voices.append(samples)

        # Metallic arp sparkle
        spark_notes = [622, 740, 932, 740]
        for i, freq in enumerate(spark_notes):
            spark = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.07,
                envelope=ADSR(attack=0.002, decay=0.18, sustain=0.0, release=0.12),
            )
            s = spark.generate_samples(self.SAMPLE_RATE, 0.28)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=110, decay=0.3)
        self._sounds["music_particle_sculptor"] = self._create_sound(mixed)

    def _generate_ascii_music(self) -> None:
        """ASCII Art music - chiptune blips with cheerful chords."""
        voices = []
        duration = 4.0
        bpm = 140
        beat = 60.0 / bpm

        # Chiptune bass
        bass_notes = [98, 123, 147, 123, 110, 98, 82, 98]
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.14,
                envelope=ADSR(attack=0.005, decay=0.1, sustain=0.2, release=0.08),
                pulse_width=0.35,
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.35)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        # Cheerful triad stabs (C major)
        chord_freqs = [262, 330, 392]
        for i in range(4):
            for freq in chord_freqs:
                chord = SynthVoice(
                    wave_type=WaveType.SAWTOOTH,
                    frequency=freq,
                    amplitude=0.08,
                    envelope=ADSR(attack=0.01, decay=0.12, sustain=0.12, release=0.1),
                    detune=4,
                )
                s = chord.generate_samples(self.SAMPLE_RATE, 0.2)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat))
                delay.extend(s)
                voices.append(delay)

        # Pixel bleeps
        bleep_notes = [784, 988, 1175, 1319]
        for i, freq in enumerate(bleep_notes):
            bleep = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.06,
                envelope=ADSR(attack=0.001, decay=0.08, sustain=0.0, release=0.05),
                pulse_width=0.2,
            )
            s = bleep.generate_samples(self.SAMPLE_RATE, 0.1)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * (i * beat * 0.5 + 0.1)))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=60, decay=0.18)
        self._sounds["music_ascii"] = self._create_sound(mixed)

    def _generate_tower_stack_music(self) -> None:
        """Tower Stack music - fast, bouncy chiptune with tight rhythm."""
        voices = []
        bpm = 150
        beat = 60.0 / bpm

        lead_notes = [659, 587, 523, 587, 659, 784, 659, 587]  # E5 D5 C5
        for i, freq in enumerate(lead_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.01, decay=0.08, sustain=0.2, release=0.06),
                pulse_width=0.35,
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.32)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        bass_notes = [110, 110, 131, 147, 110, 98, 110, 131]  # A2 A2 C3 D3
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.18,
                envelope=ADSR(attack=0.01, decay=0.12, sustain=0.3, release=0.08),
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.45)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        for i in range(16):
            t = i * beat * 0.5
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=55,
                    amplitude=0.35,
                    envelope=ADSR(attack=0.005, decay=0.12, sustain=0.0, release=0.05),
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.12)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=200,
                    amplitude=0.18,
                    envelope=ADSR(attack=0.003, decay=0.09, sustain=0.0, release=0.04),
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.1)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=9000,
                amplitude=0.06 if i % 2 == 0 else 0.04,
                envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.01),
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.04)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=50, decay=0.18)
        self._sounds["music_tower_stack"] = self._create_sound(mixed)

    def _generate_bar_runner_music(self) -> None:
        """Bar Runner music - fast, driving chiptune sprint."""
        voices = []
        bpm = 160
        beat = 60.0 / bpm

        lead_notes = [784, 880, 988, 880, 784, 659, 587, 659]  # G5 A5 B5
        for i, freq in enumerate(lead_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.18,
                envelope=ADSR(attack=0.01, decay=0.06, sustain=0.2, release=0.05),
                pulse_width=0.3,
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.28)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        bass_notes = [82, 98, 110, 130, 98, 110, 123, 147]  # E2 G2 A2
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.SAWTOOTH,
                frequency=freq,
                amplitude=0.22,
                envelope=ADSR(attack=0.01, decay=0.12, sustain=0.35, release=0.08),
                detune=4,
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.4)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        for i in range(16):
            t = i * beat * 0.5
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=58,
                    amplitude=0.4,
                    envelope=ADSR(attack=0.005, decay=0.1, sustain=0.0, release=0.04),
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.12)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=220,
                    amplitude=0.2,
                    envelope=ADSR(attack=0.003, decay=0.08, sustain=0.0, release=0.04),
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.09)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=10000,
                amplitude=0.07 if i % 2 == 0 else 0.05,
                envelope=ADSR(attack=0.001, decay=0.025, sustain=0.0, release=0.01),
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.035)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=45, decay=0.15)
        self._sounds["music_bar_runner"] = self._create_sound(mixed)

    def _generate_brick_breaker_music(self) -> None:
        """Brick Breaker music - mid-tempo chiptune bounce."""
        voices = []
        bpm = 124
        beat = 60.0 / bpm

        lead_notes = [523, 659, 587, 523, 659, 784, 698, 659]  # C5 E5 D5
        for i, freq in enumerate(lead_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.16,
                envelope=ADSR(attack=0.01, decay=0.1, sustain=0.2, release=0.08),
                pulse_width=0.4,
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.35)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        bass_notes = [98, 123, 110, 98, 147, 123, 110, 98]  # G2 B2 A2
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.01, decay=0.12, sustain=0.3, release=0.08),
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.5)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        for i in range(16):
            t = i * beat * 0.5
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=60,
                    amplitude=0.3,
                    envelope=ADSR(attack=0.006, decay=0.12, sustain=0.0, release=0.05),
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.13)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=180,
                    amplitude=0.16,
                    envelope=ADSR(attack=0.004, decay=0.09, sustain=0.0, release=0.04),
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.1)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=8500,
                amplitude=0.05 if i % 2 == 0 else 0.035,
                envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.01),
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.04)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=55, decay=0.2)
        self._sounds["music_brick_breaker"] = self._create_sound(mixed)

    def _generate_squid_game_music(self) -> None:
        """Squid Game music - tense chiptune pulse with urgency."""
        voices = []
        bpm = 138
        beat = 60.0 / bpm

        lead_notes = [392, 440, 392, 349, 330, 349, 392, 262]  # G4 A4 G4 F4 E4 F4 G4 C4
        for i, freq in enumerate(lead_notes):
            lead = SynthVoice(
                wave_type=WaveType.SQUARE,
                frequency=freq,
                amplitude=0.17,
                envelope=ADSR(attack=0.008, decay=0.08, sustain=0.15, release=0.06),
                pulse_width=0.35,
            )
            s = lead.generate_samples(self.SAMPLE_RATE, beat * 0.32)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        bass_notes = [65, 73, 82, 73, 65, 98, 82, 73]  # C2 D2 E2 D2 C2 G2 E2 D2
        for i, freq in enumerate(bass_notes):
            bass = SynthVoice(
                wave_type=WaveType.TRIANGLE,
                frequency=freq,
                amplitude=0.2,
                envelope=ADSR(attack=0.01, decay=0.14, sustain=0.25, release=0.08),
            )
            s = bass.generate_samples(self.SAMPLE_RATE, beat * 0.5)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * i * beat * 0.5))
            delay.extend(s)
            voices.append(delay)

        for i in range(16):
            t = i * beat * 0.5
            if i % 2 == 0:
                kick = SynthVoice(
                    wave_type=WaveType.SINE,
                    frequency=56,
                    amplitude=0.32,
                    envelope=ADSR(attack=0.006, decay=0.11, sustain=0.0, release=0.05),
                )
                s = kick.generate_samples(self.SAMPLE_RATE, 0.12)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            if i % 4 == 2:
                snare = SynthVoice(
                    wave_type=WaveType.NOISE,
                    frequency=210,
                    amplitude=0.18,
                    envelope=ADSR(attack=0.004, decay=0.08, sustain=0.0, release=0.04),
                )
                s = snare.generate_samples(self.SAMPLE_RATE, 0.09)
                delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
                delay.extend(s)
                voices.append(delay)

            hh = SynthVoice(
                wave_type=WaveType.NOISE,
                frequency=9000,
                amplitude=0.05 if i % 2 == 0 else 0.035,
                envelope=ADSR(attack=0.001, decay=0.03, sustain=0.0, release=0.01),
            )
            s = hh.generate_samples(self.SAMPLE_RATE, 0.035)
            delay = array.array('h', [0] * int(self.SAMPLE_RATE * t))
            delay.extend(s)
            voices.append(delay)

        mixed = mix_voices(voices)
        mixed = apply_reverb(mixed, delay_ms=55, decay=0.18)
        self._sounds["music_squid_game"] = self._create_sound(mixed)

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
            "flow_field": "idle_hum",
            "dither_art": "idle_hum",
            "glitch_mirror": "transition_whoosh",
            "particle_sculptor": "fortune_mystical",
            "tower_stack": "fortune_mystical",
            "bar_runner": "idle_hum",
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

    def play_reward(self) -> None:
        """Play reward/prize sound."""
        self.play("jackpot")

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

    # ═══════════════════════════════════════════════════════════════
    # MUSIC PLAYBACK API - Looping music tracks
    # ═══════════════════════════════════════════════════════════════

    # Music track mapping for modes and states
    MUSIC_TRACKS = {
        "idle": "music_idle",
        "menu": "music_menu",
        "fortune": "music_fortune",
        "zodiac": "music_fortune",
        "quiz": "music_quiz",
        "roulette": "music_roulette",
        "roast": "music_roast",
        "autopsy": "music_roast",
        "guess_me": "music_quiz",
        "squid_game": "music_squid_game",
        "ai_prophet": "music_fortune",
        "flow_field": "music_flow_field",
        "dither_art": "music_flow_field",
        "glitch_mirror": "music_glitch_mirror",
        "particle_sculptor": "music_particle_sculptor",
        "ascii_art": "music_ascii",
        "tower_stack": "music_tower_stack",
        "bar_runner": "music_bar_runner",
        "brick_breaker": "music_brick_breaker",
    }

    def play_music(self, track_name: str, fade_in_ms: int = 500) -> Optional[pygame.mixer.Channel]:
        """Play a music track with looping.

        Args:
            track_name: Name of the track (e.g., "idle", "menu", "fortune")
            fade_in_ms: Fade-in duration in milliseconds

        Returns:
            The channel playing the music, or None if failed
        """
        if not self._initialized or self._muted:
            return None

        # Get the actual sound name
        sound_name = self.MUSIC_TRACKS.get(track_name, track_name)

        # Don't restart if already playing this track
        if self._current_music == sound_name and self._music_channel:
            if self._music_channel.get_busy():
                return self._music_channel

        # Stop current music first
        self.stop_music(fade_out_ms=200)

        sound = self._sounds.get(sound_name)
        if not sound:
            fallback = self._sounds.get("music_idle")
            logger.warning(f"Music track not found: {sound_name}, falling back to music_idle" if fallback else f"Music track not found: {sound_name}")
            if not fallback:
                return None
            sound = fallback
            sound_name = "music_idle"

        # Set volume and play with loop
        volume = self._volume_music * self._volume_master
        sound.set_volume(volume)

        # Use a dedicated channel for music (channel 0)
        try:
            self._music_channel = pygame.mixer.Channel(0)
            self._music_channel.set_volume(volume)
            self._music_channel.play(sound, loops=-1, fade_ms=fade_in_ms)
            self._current_music = sound_name
            self._music_playing = True
            logger.debug(f"Playing music: {sound_name}")
            return self._music_channel
        except Exception as e:
            logger.error(f"Failed to play music: {e}")
            return None

    def stop_music(self, fade_out_ms: int = 300) -> None:
        """Stop currently playing music.

        Args:
            fade_out_ms: Fade-out duration in milliseconds
        """
        if self._music_channel:
            try:
                if fade_out_ms > 0:
                    self._music_channel.fadeout(fade_out_ms)
                else:
                    self._music_channel.stop()
            except Exception:
                pass
        self._current_music = None
        self._music_playing = False

    def set_music_volume(self, volume: float) -> None:
        """Set music volume (0.0 - 1.0)."""
        self._volume_music = max(0.0, min(1.0, volume))
        if self._music_channel and self._music_playing:
            try:
                self._music_channel.set_volume(self._volume_music * self._volume_master)
            except Exception:
                pass

    def is_music_playing(self) -> bool:
        """Check if music is currently playing."""
        if self._music_channel:
            try:
                return self._music_channel.get_busy()
            except Exception:
                return False
        return False

    def get_current_music(self) -> Optional[str]:
        """Get the name of the currently playing music track."""
        return self._current_music

    def stop_all(self) -> None:
        """Stop all currently playing sounds."""
        self.stop_music(fade_out_ms=0)
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
