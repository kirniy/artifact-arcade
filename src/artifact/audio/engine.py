"""
ARTIFACT Audio Engine - Iconic Chiptune Sound System.

Nostalgic melodies: Nightcall, Черный бумер, Satisfaction, Бригада vibes.
Each mode gets its own distinct musical character.
"""

import pygame
import array
import math
import random
import logging
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100


def square(t: float, freq: float) -> float:
    """Square wave oscillator."""
    return 1 if (t * freq) % 1 < 0.5 else -1


def triangle(t: float, freq: float) -> float:
    """Triangle wave oscillator."""
    p = (t * freq) % 1
    return 4 * abs(p - 0.5) - 1


def sine(t: float, freq: float) -> float:
    """Sine wave oscillator."""
    return math.sin(2 * math.pi * freq * t)


def saw(t: float, freq: float) -> float:
    """Sawtooth wave - fat synth bass."""
    return 2 * ((t * freq) % 1) - 1


def pulse(t: float, freq: float, width: float = 0.25) -> float:
    """Pulse wave with variable width."""
    return 1 if (t * freq) % 1 < width else -1


def noise() -> float:
    """White noise generator."""
    return random.random() * 2 - 1


def lowpass(samples: List[float], cutoff: float = 0.1) -> List[float]:
    """Simple lowpass filter."""
    out = []
    prev = 0
    for s in samples:
        prev = prev + cutoff * (s - prev)
        out.append(prev)
    return out


class AudioEngine:
    """
    Iconic chiptune audio engine for ARTIFACT.

    Features nostalgic melodies inspired by:
    - Nightcall (Kavinsky) - synthwave arpeggios
    - Черный бумер - pumping Russian bass
    - Satisfaction (Benny Benassi) - electro riff
    - Бригада - melancholic drama
    """

    # Nostalgic idle tracks that cycle - each has its own vibe
    IDLE_TRACKS = [
        "music_christmas",      # Christmas/NYE - festive bells (first for NYE!)
        "music_nightcall",      # Synthwave - Kavinsky vibes
        "music_bumer",          # Russian club - Черный бумер
        "music_satisfaction",   # Electro house - Benny Benassi
        "music_brigada",        # Melancholic - Бригада drama
        "music_arcade",         # 8-bit games - classic arcade
        "music_trance",         # Energetic - party vibes
        "music_chill",          # Ambient - chill mode
    ]

    IDLE_TRACK_DURATION = 25000  # 25 seconds per track before cycling (more variety)
    IDLE_PAUSE_TIMEOUT = 120000  # 2 minutes of no motion = pause music

    def __init__(self):
        self._initialized = False
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self._music_playing = False
        self._volume_master = 1.0
        self._volume_sfx = 1.0
        self._volume_music = 0.6
        self._muted = False
        self._current_music: Optional[str] = None
        self._music_channel: Optional[pygame.mixer.Channel] = None
        self._generated = False

        # Idle music cycling state
        self._idle_mode = False
        self._idle_track_index = 0
        self._idle_track_timer = 0.0
        self._idle_paused = False
        self._last_motion_time = 0.0
        self._motion_detected = True  # Start with motion detected

    def init(self, skip_generation: bool = False) -> bool:
        """Initialize the audio system."""
        try:
            pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 4096)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            self._initialized = True
            logger.info("Audio engine initialized")

            if not skip_generation:
                self._generate_all_sounds()
            else:
                logger.info("Skipping sound generation")
                self._generated = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    def _create_sound(self, samples: array.array) -> pygame.mixer.Sound:
        """Create a pygame Sound from mono samples (auto-converted to stereo)."""
        stereo = array.array('h')
        for s in samples:
            stereo.append(s)
            stereo.append(s)
        return pygame.mixer.Sound(buffer=stereo)

    def _generate_all_sounds(self) -> None:
        """Generate all sounds quickly using simple waveforms."""
        if self._generated:
            return

        logger.info("Generating iconic chiptune sounds...")

        # === UI SOUNDS ===
        self._gen_click()
        self._gen_confirm()
        self._gen_move()
        self._gen_back()
        self._gen_error()

        # === GAME SOUNDS ===
        self._gen_countdown_tick()
        self._gen_countdown_go()
        self._gen_success()
        self._gen_failure()
        self._gen_score_up()
        self._gen_wheel_tick()
        self._gen_wheel_stop()
        self._gen_jackpot()

        # === MODE SOUNDS ===
        self._gen_mystical()
        self._gen_stars()
        self._gen_correct()
        self._gen_wrong()
        self._gen_spin()
        self._gen_scan()
        self._gen_shutter()
        self._gen_print()

        # === AMBIENT ===
        self._gen_idle_hum()
        self._gen_startup()
        self._gen_whoosh()

        # === ICONIC MUSIC TRACKS ===
        self._gen_all_music()

        self._generated = True
        logger.info(f"Generated {len(self._sounds)} sounds")

    # ===== UI SOUNDS =====

    def _gen_click(self) -> None:
        """Arcade button click."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.06)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 20)
            val = square(t, 800) * 0.4 + sine(t, 150) * 0.3
            samples.append(int(val * env * 32767 * 0.6))
        self._sounds["button_click"] = self._create_sound(samples)

    def _gen_confirm(self) -> None:
        """Two-tone confirm."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.2)):
            t = i / SAMPLE_RATE
            if t < 0.1:
                freq = 523
                env = max(0, 1 - (t * 10))
            else:
                freq = 659
                env = max(0, 1 - ((t - 0.1) * 10))
            val = square(t, freq) * 0.3
            samples.append(int(val * env * 32767))
        self._sounds["button_confirm"] = self._create_sound(samples)

    def _gen_move(self) -> None:
        """Menu navigation blip."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.05)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 25)
            val = triangle(t, 440) * 0.25
            samples.append(int(val * env * 32767))
        self._sounds["menu_move"] = self._create_sound(samples)

    def _gen_back(self) -> None:
        """Back/cancel descending tone."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.15)):
            t = i / SAMPLE_RATE
            freq = 400 - t * 2000
            env = max(0, 1 - t * 7)
            val = square(t, max(100, freq)) * 0.25
            samples.append(int(val * env * 32767))
        self._sounds["back"] = self._create_sound(samples)

    def _gen_error(self) -> None:
        """Error buzz."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.2)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 5)
            val = square(t, 120) * 0.3
            samples.append(int(val * env * 32767))
        self._sounds["error"] = self._create_sound(samples)

    # ===== GAME SOUNDS =====

    def _gen_countdown_tick(self) -> None:
        """Countdown tick."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.05)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 25)
            val = sine(t, 1000) * 0.2
            samples.append(int(val * env * 32767))
        self._sounds["countdown_tick"] = self._create_sound(samples)

    def _gen_countdown_go(self) -> None:
        """GO! sound with rising sweep."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.4)):
            t = i / SAMPLE_RATE
            freq = 300 + t * 1500
            env = max(0, 1 - t * 2.5)
            val = (square(t, 523) + square(t, 659) + square(t, 784)) * 0.15
            val += sine(t, freq) * 0.1
            samples.append(int(val * env * 32767))
        self._sounds["countdown_go"] = self._create_sound(samples)

    def _gen_success(self) -> None:
        """Triumphant arpeggio."""
        samples = array.array('h')
        notes = [523, 659, 784, 1047]
        for i in range(int(SAMPLE_RATE * 0.5)):
            t = i / SAMPLE_RATE
            note_idx = min(int(t * 10), 3)
            env = max(0, 1 - (t - note_idx * 0.1) * 5)
            val = square(t, notes[note_idx]) * 0.25
            samples.append(int(val * env * 32767))
        self._sounds["success"] = self._create_sound(samples)

    def _gen_failure(self) -> None:
        """Sad descending tone."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.4)):
            t = i / SAMPLE_RATE
            freq = 400 - t * 200
            env = max(0, 1 - t * 2.5)
            val = square(t, freq) * 0.25
            samples.append(int(val * env * 32767))
        self._sounds["failure"] = self._create_sound(samples)

    def _gen_score_up(self) -> None:
        """Quick score increment."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.08)):
            t = i / SAMPLE_RATE
            freq = 800 + t * 4000
            env = max(0, 1 - t * 15)
            val = square(t, freq) * 0.2
            samples.append(int(val * env * 32767))
        self._sounds["score_up"] = self._create_sound(samples)

    def _gen_wheel_tick(self) -> None:
        """Roulette tick."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.02)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 60)
            val = noise() * 0.15
            samples.append(int(val * env * 32767))
        self._sounds["wheel_tick"] = self._create_sound(samples)

    def _gen_wheel_stop(self) -> None:
        """Wheel stop reveal."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.6)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 1.7)
            val = (sine(t, 261) + sine(t, 329) + sine(t, 392)) * 0.15
            val += noise() * 0.1 * max(0, 1 - t * 10)
            samples.append(int(val * env * 32767))
        self._sounds["wheel_stop"] = self._create_sound(samples)

    def _gen_jackpot(self) -> None:
        """Jackpot celebration."""
        samples = array.array('h')
        notes = [523, 659, 784, 1047, 784, 659, 523, 659, 784, 1047, 1319]
        for i in range(int(SAMPLE_RATE * 1.0)):
            t = i / SAMPLE_RATE
            note_idx = min(int(t * 15), len(notes) - 1)
            env = max(0, 1 - (t * 10 % 1) * 2) * 0.5 + 0.5
            val = square(t, notes[note_idx]) * 0.2
            if int(t * 5) % 2 == 0:
                val += sine(t, 65) * 0.2
            samples.append(int(val * max(0, 1 - t) * 32767))
        self._sounds["jackpot"] = self._create_sound(samples)

    # ===== MODE SOUNDS =====

    def _gen_mystical(self) -> None:
        """Fortune mystical ambiance."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 2.0)):
            t = i / SAMPLE_RATE
            env = min(t * 2, 1, 2 - t)
            val = sine(t, 220) * 0.1 + sine(t, 277) * 0.08 + sine(t, 330) * 0.06
            val += triangle(t + 0.2, 2000 + sine(t, 0.5) * 500) * 0.03 * (1 if int(t * 3) % 2 else 0)
            samples.append(int(val * env * 32767))
        self._sounds["fortune_mystical"] = self._create_sound(samples)

    def _gen_stars(self) -> None:
        """Cosmic zodiac atmosphere."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 2.5)):
            t = i / SAMPLE_RATE
            env = min(t, 1, 2.5 - t)
            val = sine(t, 55) * 0.1 + sine(t, 82.5) * 0.05
            for j in range(8):
                sparkle_t = (t + j * 0.3) % 2.5
                if sparkle_t < 0.3:
                    val += sine(t, 1500 + j * 200) * 0.03 * (1 - sparkle_t * 3.3)
            samples.append(int(val * env * 32767))
        self._sounds["zodiac_stars"] = self._create_sound(samples)

    def _gen_correct(self) -> None:
        """Correct answer chime."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.3)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 3.5)
            val = (triangle(t, 880) + triangle(t, 1109)) * 0.2
            samples.append(int(val * env * 32767))
        self._sounds["quiz_correct"] = self._create_sound(samples)

    def _gen_wrong(self) -> None:
        """Wrong answer buzz."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.3)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 3.5)
            val = square(t, 150) * 0.25
            samples.append(int(val * env * 32767))
        self._sounds["quiz_wrong"] = self._create_sound(samples)

    def _gen_spin(self) -> None:
        """Roulette spin accelerating clicks."""
        samples = array.array('h')
        click_t = 0
        click_interval = 0.1
        for i in range(int(SAMPLE_RATE * 1.5)):
            t = i / SAMPLE_RATE
            if t >= click_t:
                click_interval *= 0.92
                click_t += click_interval
            click_phase = t - (click_t - click_interval)
            if click_phase < 0.015:
                val = noise() * 0.2 * (1 - click_phase * 70)
            else:
                val = 0
            samples.append(int(val * 32767))
        self._sounds["roulette_spin"] = self._create_sound(samples)

    def _gen_scan(self) -> None:
        """AI scanning sound."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 1.2)):
            t = i / SAMPLE_RATE
            freq = 300 + 200 * sine(t, 10) + 100 * sine(t, 23)
            env = min(t * 3, 1, (1.2 - t) * 3)
            val = sine(t, freq) * 0.15
            if i % 100 < 10:
                val += 0.05 * (1 if (t * freq) % 1 < 0.5 else -1)
            samples.append(int(val * env * 32767))
        self._sounds["prophet_scan"] = self._create_sound(samples)

    def _gen_shutter(self) -> None:
        """Camera shutter click."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.08)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t * 15)
            val = noise() * 0.3 + square(t, 2000) * 0.15 * (1 if t < 0.02 else 0)
            samples.append(int(val * env * 32767))
        self._sounds["camera_shutter"] = self._create_sound(samples)

    def _gen_print(self) -> None:
        """Thermal printer sound."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 1.5)):
            t = i / SAMPLE_RATE
            env = max(0, 1 - t / 1.5)
            val = noise() * 0.05
            val += sine(t, 200) * 0.1 * sine(t, 50)
            val += 0.05 * (1 if int(t * 30) % 2 else -1)
            samples.append(int(val * env * 32767))
        self._sounds["print_sound"] = self._create_sound(samples)

    # ===== AMBIENT =====

    def _gen_idle_hum(self) -> None:
        """Low ambient hum."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 3.0)):
            t = i / SAMPLE_RATE
            env = min(t * 2, 1, 3 - t)
            val = sine(t, 60) * 0.05 + sine(t, 180) * 0.02
            val += sine(t + sine(t, 0.5) * 0.1, 60) * 0.03
            samples.append(int(val * env * 32767))
        self._sounds["idle_hum"] = self._create_sound(samples)

    def _gen_startup(self) -> None:
        """Startup fanfare."""
        samples = array.array('h')
        bass = [65, 65, 82, 98]
        lead = [262, 330, 392, 523, 659, 784, 1047]
        for i in range(int(SAMPLE_RATE * 2.0)):
            t = i / SAMPLE_RATE
            bass_idx = min(int(t * 2.5), 3)
            lead_idx = min(int((t - 0.3) * 6), 6) if t > 0.3 else -1

            val = 0
            if bass_idx >= 0:
                val += square(t, bass[bass_idx]) * 0.2 * min(1, (2 - t))
            if lead_idx >= 0:
                env = max(0, 1 - ((t - 0.3) * 6 % 1) * 3)
                val += square(t, lead[lead_idx]) * 0.15 * env

            val += (sine(t, 262) + sine(t, 330) + sine(t, 392)) * 0.08 * min(1, t * 2, 2 - t)

            if t > 1.5:
                val += noise() * 0.08 * (1 - (t - 1.5) * 2)

            samples.append(int(val * 32767))
        self._sounds["startup_fanfare"] = self._create_sound(samples)

    def _gen_whoosh(self) -> None:
        """Transition whoosh."""
        samples = array.array('h')
        for i in range(int(SAMPLE_RATE * 0.25)):
            t = i / SAMPLE_RATE
            env = sine(t * math.pi / 0.25, 1) * 0.3
            val = noise() * env
            samples.append(int(val * 32767))
        self._sounds["transition_whoosh"] = self._create_sound(samples)

    # =========================================================================
    # ICONIC MUSIC GENERATION - Each track has its own unique character!
    # =========================================================================

    def _gen_all_music(self) -> None:
        """Generate all iconic music tracks."""

        # CHRISTMAS style - festive bells for NYE celebration
        self._gen_christmas_style()

        # NIGHTCALL style - synthwave for fortune/mystical modes
        self._gen_nightcall_style()

        # ЧЕРНЫЙ БУМЕР style - pumping bass for party modes
        self._gen_bumer_style()

        # SATISFACTION style - electro house riff
        self._gen_satisfaction_style()

        # БРИГАДА style - melancholic drama
        self._gen_brigada_style()

        # ARCADE style - classic 8-bit games
        self._gen_arcade_style()

        # TRANCE style - energetic for action games
        self._gen_trance_style()

        # CHILL style - ambient for creative modes
        self._gen_chill_style()

        # QUIZ style - tension/thinking music
        self._gen_quiz_style()

    def _gen_christmas_style(self) -> None:
        """Festive Christmas/NYE music with bells and chimes. Holiday vibes!"""
        samples = array.array('h')
        bpm = 120
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for full melody

        # Jingle Bells-inspired melody (simplified)
        # C-C-C | C-C-C | C-E-G-C | D-D-D-D | D-C-C-C | C-C-B-B | C-D-E-F | G
        melody_notes = [
            262, 262, 262, 0,   # C C C rest
            262, 262, 262, 0,   # C C C rest
            262, 330, 392, 262, # C E G C
            294, 294, 294, 294, # D D D D
            294, 262, 262, 262, # D C C C
            262, 262, 247, 247, # C C B B
            262, 294, 330, 349, # C D E F
            392, 392, 392, 0,   # G G G rest
        ]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            beat_idx = int(t / (beat / 2)) % len(melody_notes)
            val = 0

            # Melody with bell-like tone
            note = melody_notes[beat_idx]
            if note > 0:
                # Bell sound - sine with harmonic overtones and decay
                env = max(0, 1 - ((t * 4) % 1) * 2)  # Quick decay
                val += sine(t, note) * 0.2 * env
                val += sine(t, note * 2) * 0.08 * env  # Octave
                val += sine(t, note * 3) * 0.04 * env  # Third harmonic
                val += triangle(t, note * 4) * 0.02 * env  # Chime sparkle

            # Sleigh bells - high frequency jingle
            if ((t * 8) % 1) < 0.1:
                jingle_env = max(0, 1 - ((t * 8) % 1) * 10)
                val += (sine(t, 2000) * 0.03 + sine(t, 3000) * 0.02) * jingle_env

            # Warm pad chord (C major)
            pad_env = 0.3
            val += sine(t, 130) * 0.08 * pad_env  # C2 bass
            val += sine(t, 165) * 0.04 * pad_env  # E2
            val += sine(t, 196) * 0.04 * pad_env  # G2

            # Subtle bass pulse on beat
            beat_phase = (t / beat) % 1
            if beat_phase < 0.1:
                kick_freq = 80 * (1 - beat_phase * 8)
                val += sine(t, max(30, kick_freq)) * 0.15 * (1 - beat_phase * 10)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_christmas"] = self._create_sound(samples)

    def _gen_nightcall_style(self) -> None:
        """Kavinsky Nightcall-inspired synthwave. Dark, arpeggiated, 80s vibes."""
        samples = array.array('h')
        bpm = 98
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Am - F - C - G progression (Nightcall-esque)
        chords = [
            (220, 262, 330),  # Am
            (175, 220, 262),  # F
            (262, 330, 392),  # C
            (196, 247, 294),  # G
        ]

        # Arpeggiated pattern (iconic synthwave)
        arp_pattern = [0, 1, 2, 1, 0, 2, 1, 2]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4
            beat_in_bar = (t / beat) % 4

            chord = chords[bar]
            val = 0

            # Deep pumping bass (sidechain style)
            pump = 1 - 0.6 * max(0, 1 - (beat_in_bar % 1) * 4)
            bass_note = chord[0] / 2
            val += saw(t, bass_note) * 0.25 * pump
            val += sine(t, bass_note / 2) * 0.15 * pump

            # Arpeggiated synth lead
            arp_idx = int((t / (beat / 2)) % 8)
            arp_note = chord[arp_pattern[arp_idx] % 3] * 2
            arp_env = max(0, 1 - ((t * 4) % 1) * 3)
            val += pulse(t, arp_note, 0.3) * 0.12 * arp_env

            # Pad (warm synth pad)
            for note in chord:
                val += sine(t, note) * 0.04
                val += triangle(t, note * 2) * 0.02

            # Snare on 2 and 4
            snare_t = beat_in_bar % 2
            if 0.95 < snare_t < 1.05:
                snare_phase = (snare_t - 0.95) * 10
                val += noise() * 0.15 * max(0, 1 - snare_phase * 5)

            # Kick on every beat
            kick_t = beat_in_bar % 1
            if kick_t < 0.1:
                kick_freq = 80 * (1 - kick_t * 8)
                val += sine(t, max(30, kick_freq)) * 0.3 * (1 - kick_t * 10)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_nightcall"] = self._create_sound(samples)
        self._sounds["music_fortune"] = self._sounds["music_nightcall"]
        self._sounds["music_ai_prophet"] = self._sounds["music_nightcall"]
        self._sounds["music_zodiac"] = self._sounds["music_nightcall"]

    def _gen_bumer_style(self) -> None:
        """Черный бумер-inspired pumping bass. Russian club classic."""
        samples = array.array('h')
        bpm = 130
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Em - Am progression (Russian club vibes)
        bass_notes = [82, 82, 110, 110]  # E, E, A, A

        # Iconic "бумер" bass pattern
        bass_pattern = [1, 0, 0.5, 1, 0, 1, 0.5, 0]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4
            beat_in_bar = (t / beat) % 4
            eighth = int((t / (beat / 2)) % 8)

            bass = bass_notes[bar]
            val = 0

            # PUMPING BASS - the iconic sound
            bass_vol = bass_pattern[eighth] * 0.4
            if bass_vol > 0:
                bass_env = max(0, 1 - ((t * 4) % 1) * 2)
                val += saw(t, bass) * bass_vol * bass_env
                val += sine(t, bass / 2) * bass_vol * 0.5 * bass_env

            # Synth stab on off-beats
            if eighth in [2, 6]:
                stab_env = max(0, 1 - ((t * 4) % 1) * 8)
                val += square(t, bass * 2) * 0.1 * stab_env
                val += square(t, bass * 3) * 0.05 * stab_env

            # Kick drum (4 on the floor)
            kick_t = beat_in_bar % 1
            if kick_t < 0.08:
                kick_freq = 100 * (1 - kick_t * 10)
                val += sine(t, max(30, kick_freq)) * 0.35 * (1 - kick_t * 12)

            # Open hi-hat on off-beats
            if 0.45 < (beat_in_bar % 1) < 0.55:
                val += noise() * 0.08 * max(0, 1 - ((beat_in_bar % 1) - 0.45) * 20)

            # Clap on 2 and 4
            if 0.98 < (beat_in_bar % 2) < 1.02 or 1.98 < beat_in_bar < 2.02:
                clap_t = (beat_in_bar % 2) - 0.98 if beat_in_bar < 2 else beat_in_bar - 1.98
                val += noise() * 0.18 * max(0, 1 - clap_t * 30)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_bumer"] = self._create_sound(samples)
        self._sounds["music_roast"] = self._sounds["music_bumer"]
        self._sounds["music_roulette"] = self._sounds["music_bumer"]

    def _gen_satisfaction_style(self) -> None:
        """Benny Benassi Satisfaction-inspired electro riff."""
        samples = array.array('h')
        bpm = 130
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # The iconic riff pattern (simplified)
        # D - D - D - D - F - D - D - rest
        riff = [147, 147, 147, 147, 175, 147, 147, 0,
                147, 147, 147, 147, 175, 196, 175, 147]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            beat_in_bar = (t / beat) % 4
            sixteenth = int((t / (beat / 4)) % 16)

            val = 0

            # The riff - distorted saw bass
            note = riff[sixteenth]
            if note > 0:
                riff_env = max(0, 1 - ((t * 8) % 1) * 4)
                # Distorted saw
                raw = saw(t, note) + saw(t, note * 1.01) * 0.5
                distorted = max(-0.8, min(0.8, raw * 2))  # Soft clip
                val += distorted * 0.3 * riff_env

            # Kick (4 on floor)
            kick_t = beat_in_bar % 1
            if kick_t < 0.07:
                val += sine(t, 60 * (1 - kick_t * 10)) * 0.35 * (1 - kick_t * 14)

            # Hi-hat pattern
            if sixteenth % 2 == 0:
                hat_env = max(0, 1 - ((t * 8) % 1) * 15)
                val += noise() * 0.06 * hat_env

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_satisfaction"] = self._create_sound(samples)
        self._sounds["music_autopsy"] = self._sounds["music_satisfaction"]

    def _gen_brigada_style(self) -> None:
        """Бригада TV series-inspired melancholic theme."""
        samples = array.array('h')
        bpm = 85
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Am - Dm - E - Am (Russian melancholic progression)
        chords = [
            (220, 262, 330),  # Am
            (147, 175, 220),  # Dm
            (165, 208, 247),  # E
            (220, 262, 330),  # Am
        ]

        # Melancholic melody
        melody = [659, 587, 523, 587, 659, 784, 659, 587,
                  523, 494, 440, 392, 440, 523, 587, 523]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4
            beat_in_bar = (t / beat) % 4
            melody_idx = int(t / beat) % 16

            chord = chords[bar]
            val = 0

            # Slow bass
            bass_env = min(1, (t % (beat * 2)) * 2)
            val += triangle(t, chord[0] / 2) * 0.15 * bass_env

            # Pad chords (strings-like)
            for note in chord:
                val += sine(t, note) * 0.05
                val += sine(t, note + sine(t, 5) * 3) * 0.03  # Vibrato

            # Melody (piano-like)
            mel_note = melody[melody_idx]
            mel_env = max(0, 1 - ((t / beat) % 1) * 2)
            val += triangle(t, mel_note) * 0.12 * mel_env
            val += sine(t, mel_note) * 0.08 * mel_env

            # Soft snare
            if 0.95 < (beat_in_bar % 2) < 1.05 and bar < 3:
                val += noise() * 0.08 * max(0, 1 - ((beat_in_bar % 2) - 0.95) * 20)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_brigada"] = self._create_sound(samples)
        self._sounds["music_guess_me"] = self._sounds["music_brigada"]

    def _gen_arcade_style(self) -> None:
        """Classic 8-bit arcade game music. Upbeat and catchy."""
        samples = array.array('h')
        bpm = 155
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Major key, happy arcade vibes
        melody = [523, 587, 659, 784, 880, 784, 659, 587,
                  523, 659, 784, 880, 988, 880, 784, 659]
        bass = [131, 165, 196, 165]  # C G Am G

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            beat_in_bar = (t / beat) % 4
            bar = int(t / (beat * 4)) % 4
            melody_idx = int(t / (beat / 2)) % 16

            val = 0

            # Square wave melody (classic NES sound)
            mel_note = melody[melody_idx]
            mel_env = max(0.3, 1 - ((t * 4) % 1) * 2)
            val += square(t, mel_note) * 0.15 * mel_env

            # Square bass
            bass_note = bass[bar]
            val += square(t, bass_note) * 0.12

            # Arpeggio decoration
            arp = [1, 1.25, 1.5, 2][int(t * 12) % 4]
            val += pulse(t, melody[melody_idx] * arp / 2, 0.25) * 0.06

            # Noise drums
            if beat_in_bar % 1 < 0.05:
                val += noise() * 0.12 * (1 - (beat_in_bar % 1) * 20)
            if 0.5 < (beat_in_bar % 1) < 0.55:
                val += noise() * 0.08 * (1 - ((beat_in_bar % 1) - 0.5) * 20)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.65))

        self._sounds["music_arcade"] = self._create_sound(samples)
        self._sounds["music_tower_stack"] = self._sounds["music_arcade"]
        self._sounds["music_brick_breaker"] = self._sounds["music_arcade"]
        self._sounds["music_snake_classic"] = self._sounds["music_arcade"]
        self._sounds["music_pong"] = self._sounds["music_arcade"]

    def _gen_trance_style(self) -> None:
        """Energetic trance for action games. Building energy."""
        samples = array.array('h')
        bpm = 140
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Trance chord progression
        chords = [
            (330, 415, 494),  # Em
            (294, 370, 440),  # D
            (262, 330, 392),  # C
            (294, 370, 440),  # D
        ]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            beat_in_bar = (t / beat) % 4
            bar = int(t / (beat * 4)) % 4

            chord = chords[bar]
            val = 0

            # Pumping supersaw pad
            pump = 1 - 0.7 * max(0, 1 - (beat_in_bar % 1) * 5)
            for note in chord:
                for detune in [-0.02, 0, 0.02]:
                    val += saw(t, note * (1 + detune)) * 0.04 * pump

            # Bass
            bass = chord[0] / 2
            val += saw(t, bass) * 0.2 * pump
            val += sine(t, bass / 2) * 0.15 * pump

            # Lead melody (filter sweep feel)
            lead_freq = chord[2] * 2 + sine(t * 0.5, 1) * 200
            val += saw(t, lead_freq) * 0.08 * pump

            # Kick
            if (beat_in_bar % 1) < 0.06:
                val += sine(t, 70 * (1 - (beat_in_bar % 1) * 15)) * 0.35

            # Off-beat hi-hat
            if 0.45 < (beat_in_bar % 1) < 0.55:
                val += noise() * 0.1 * max(0, 1 - abs((beat_in_bar % 1) - 0.5) * 20)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.65))

        self._sounds["music_trance"] = self._create_sound(samples)
        self._sounds["music_bar_runner"] = self._sounds["music_trance"]
        self._sounds["music_squid_game"] = self._sounds["music_trance"]
        self._sounds["music_flappy"] = self._sounds["music_trance"]

    def _gen_chill_style(self) -> None:
        """Ambient chill for creative modes. Relaxed and spacey."""
        samples = array.array('h')
        bpm = 80
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Dreamy chords
        chords = [
            (262, 330, 392, 494),  # Cmaj7
            (220, 277, 330, 415),  # Am7
            (196, 247, 294, 370),  # Gmaj7
            (175, 220, 262, 330),  # Fmaj7
        ]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4

            chord = chords[bar]
            val = 0

            # Soft pad with slow attack
            pad_env = min(1, (t % (beat * 4)) / 2)
            for note in chord:
                val += sine(t, note) * 0.04 * pad_env
                val += sine(t, note + sine(t, 0.5) * 5) * 0.02 * pad_env  # Chorus

            # Sparse bass
            if (t % (beat * 2)) < beat:
                bass_env = max(0, 1 - (t % (beat * 2)) / beat)
                val += triangle(t, chord[0] / 2) * 0.1 * bass_env

            # Ambient sparkles
            if random.random() < 0.002:
                sparkle_freq = random.choice([880, 1047, 1319, 1568])
            else:
                sparkle_freq = 0
            if sparkle_freq > 0:
                val += sine(t, sparkle_freq) * 0.03

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        self._sounds["music_chill"] = self._create_sound(samples)
        self._sounds["music_flow_field"] = self._sounds["music_chill"]
        self._sounds["music_particle_sculptor"] = self._sounds["music_chill"]
        self._sounds["music_dither_art"] = self._sounds["music_chill"]
        self._sounds["music_glitch_mirror"] = self._sounds["music_chill"]
        self._sounds["music_ascii"] = self._sounds["music_chill"]
        self._sounds["music_lunar_lander"] = self._sounds["music_chill"]

    def _gen_quiz_style(self) -> None:
        """Quiz show tension music. Building suspense."""
        samples = array.array('h')
        bpm = 110
        beat = 60.0 / bpm
        duration = beat * 32  # 8 bars for more variety

        # Tense diminished/sus chords
        chords = [
            (196, 247, 294),  # Gsus
            (185, 233, 277),  # F#dim
            (196, 247, 294),  # Gsus
            (208, 262, 311),  # G#sus
        ]

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            bar = int(t / (beat * 4)) % 4
            beat_in_bar = (t / beat) % 4

            chord = chords[bar]
            val = 0

            # Tense pad
            tension = 1 + 0.3 * sine(t * 0.5, 1)  # Slow LFO
            for note in chord:
                val += sine(t, note * tension) * 0.05

            # Ticking clock bass
            tick_phase = (t * 2) % 1
            if tick_phase < 0.1:
                val += sine(t, 100) * 0.15 * (1 - tick_phase * 10)

            # High tension string
            val += sine(t, 988 + sine(t, 8) * 30) * 0.04

            # Heartbeat kick on weak beats
            if 0.45 < (beat_in_bar % 2) < 0.55:
                hb_t = (beat_in_bar % 2) - 0.45
                val += sine(t, 50) * 0.2 * max(0, 1 - hb_t * 20)

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.6))

        self._sounds["music_quiz"] = self._create_sound(samples)
        self._sounds["music_game_2048"] = self._sounds["music_quiz"]

    # ===== IDLE/MENU MUSIC =====

    def _gen_idle_music(self) -> None:
        """Generate idle screen music."""
        # Use nightcall style for idle - it's chill but interesting
        if "music_idle" not in self._sounds:
            self._sounds["music_idle"] = self._sounds.get("music_nightcall")
        if "music_menu" not in self._sounds:
            self._sounds["music_menu"] = self._sounds.get("music_nightcall")

    # ===== PLAYBACK API =====

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
        self.play("button_click")

    def play_ui_confirm(self) -> None:
        self.play("button_confirm")

    def play_ui_move(self) -> None:
        self.play("menu_move")

    def play_ui_back(self) -> None:
        self.play("back")

    def play_ui_error(self) -> None:
        self.play("error")

    def play_countdown_tick(self) -> None:
        self.play("countdown_tick")

    def play_countdown_go(self) -> None:
        self.play("countdown_go")

    def play_success(self) -> None:
        self.play("success")

    def play_failure(self) -> None:
        self.play("failure")

    def play_score_up(self) -> None:
        self.play("score_up")

    def play_jackpot(self) -> None:
        self.play("jackpot")

    def play_wheel_tick(self) -> None:
        self.play("wheel_tick", volume=0.5)

    def play_wheel_stop(self) -> None:
        self.play("wheel_stop")

    def play_startup(self) -> None:
        self.play("startup_fanfare")

    def play_transition(self) -> None:
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
            return self.play(sound_name, loops=-1)
        return None

    def play_camera_shutter(self) -> None:
        self.play("camera_shutter")

    def play_print(self) -> None:
        self.play("print_sound")

    def play_reward(self) -> None:
        self.play("jackpot")

    def play_quiz_correct(self) -> None:
        self.play("quiz_correct")

    def play_quiz_wrong(self) -> None:
        self.play("quiz_wrong")

    def play_roulette_spin(self) -> None:
        self.play("roulette_spin")

    def start_idle_ambient(self) -> pygame.mixer.Channel:
        """Start idle ambient loop."""
        return self.play("idle_hum", loops=-1, volume=0.3)

    # ===== MUSIC PLAYBACK API =====

    MUSIC_TRACKS = {
        # Main states
        "idle": "music_nightcall",
        "menu": "music_nightcall",

        # Fortune/mystical modes - Nightcall synthwave
        "fortune": "music_nightcall",
        "zodiac": "music_nightcall",
        "ai_prophet": "music_nightcall",

        # Party/roast modes - Черный бумер bass
        "roast": "music_bumer",
        "roulette": "music_bumer",

        # Action modes - Satisfaction electro
        "autopsy": "music_satisfaction",
        "guess_me": "music_brigada",

        # Quiz - tension music
        "quiz": "music_quiz",
        "game_2048": "music_quiz",

        # Arcade games - classic 8-bit
        "tower_stack": "music_arcade",
        "brick_breaker": "music_arcade",
        "snake_classic": "music_arcade",
        "snake_tiny": "music_arcade",
        "pong": "music_arcade",
        "hand_snake": "music_arcade",

        # Action games - trance
        "bar_runner": "music_trance",
        "squid_game": "music_trance",
        "flappy": "music_trance",
        "rocketpy": "music_trance",
        "skii": "music_trance",
        "ninja_fruit": "music_trance",
        "gesture_game": "music_trance",

        # Creative modes - chill ambient
        "flow_field": "music_chill",
        "dither_art": "music_chill",
        "glitch_mirror": "music_chill",
        "particle_sculptor": "music_chill",
        "ascii_art": "music_chill",
        "lunar_lander": "music_chill",

        # Photo modes
        "photobooth": "music_nightcall",
        "rap_god": "music_bumer",
    }

    def play_music(self, track_name: str, fade_in_ms: int = 500) -> Optional[pygame.mixer.Channel]:
        """Play a music track with looping."""
        if not self._initialized or self._muted:
            logger.warning(f"play_music({track_name}) skipped: initialized={self._initialized}, muted={self._muted}")
            return None

        sound_name = self.MUSIC_TRACKS.get(track_name, f"music_{track_name}")

        # Don't restart if already playing
        if self._current_music == sound_name and self._music_channel:
            if self._music_channel.get_busy():
                return self._music_channel

        self.stop_music(fade_out_ms=200)

        sound = self._sounds.get(sound_name)
        if not sound:
            # Fallback to nightcall
            sound = self._sounds.get("music_nightcall")
            if not sound:
                logger.warning(f"Music track not found: {sound_name}")
                return None
            sound_name = "music_nightcall"

        volume = self._volume_music * self._volume_master
        sound.set_volume(volume)

        try:
            self._music_channel = pygame.mixer.Channel(0)
            self._music_channel.set_volume(volume)
            self._music_channel.play(sound, loops=-1, fade_ms=fade_in_ms)
            self._current_music = sound_name
            self._music_playing = True
            logger.info(f"Playing music: {sound_name}")
            return self._music_channel
        except Exception as e:
            logger.error(f"Failed to play music: {e}")
            return None

    def stop_music(self, fade_out_ms: int = 300) -> None:
        """Stop currently playing music."""
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
        """Stop all sounds."""
        self.stop_music(fade_out_ms=0)
        pygame.mixer.stop()

    def set_master_volume(self, volume: float) -> None:
        """Set master volume (0.0 - 1.0)."""
        self._volume_master = max(0.0, min(1.0, volume))

    def set_sfx_volume(self, volume: float) -> None:
        """Set SFX volume (0.0 - 1.0)."""
        self._volume_sfx = max(0.0, min(1.0, volume))

    def set_volume(self, volume: float) -> None:
        """Set master volume (alias for set_master_volume)."""
        self.set_master_volume(volume)

    def get_volume(self) -> float:
        """Get current master volume (0.0 - 1.0)."""
        return self._volume_master

    def is_muted(self) -> bool:
        """Check if audio is muted."""
        return self._muted

    def mute(self) -> None:
        """Mute audio."""
        if not self._muted:
            self._muted = True
            pygame.mixer.pause()
            logger.info("Audio muted")

    def unmute(self) -> None:
        """Unmute audio."""
        if self._muted:
            self._muted = False
            pygame.mixer.unpause()
            logger.info("Audio unmuted")

    def toggle_mute(self) -> bool:
        """Toggle mute state."""
        self._muted = not self._muted
        if self._muted:
            pygame.mixer.pause()
        else:
            pygame.mixer.unpause()
        return self._muted

    # ===== CYCLING IDLE MUSIC =====

    def start_idle_music(self) -> None:
        """Start cycling idle music mode."""
        self._idle_mode = True
        self._idle_paused = False
        self._idle_track_timer = 0.0
        self._motion_detected = True
        self._last_motion_time = 0.0
        # Start with a random track for variety
        self._idle_track_index = random.randint(0, len(self.IDLE_TRACKS) - 1)
        self._play_idle_track()
        logger.info(f"Idle music started with track: {self.IDLE_TRACKS[self._idle_track_index]}")

    def stop_idle_music(self) -> None:
        """Stop idle music cycling."""
        self._idle_mode = False
        self.stop_music(fade_out_ms=500)
        logger.info("Idle music stopped")

    def _play_idle_track(self) -> None:
        """Play the current idle track."""
        if not self._idle_mode or self._idle_paused:
            return

        track_name = self.IDLE_TRACKS[self._idle_track_index]
        sound = self._sounds.get(track_name)
        if sound:
            self.stop_music(fade_out_ms=300)
            volume = self._volume_music * self._volume_master
            sound.set_volume(volume)
            try:
                self._music_channel = pygame.mixer.Channel(0)
                self._music_channel.set_volume(volume)
                self._music_channel.play(sound, loops=-1, fade_ms=500)
                self._current_music = track_name
                self._music_playing = True
            except Exception as e:
                logger.error(f"Failed to play idle track: {e}")

    def update_idle_music(self, delta_ms: float, motion_detected: bool = True) -> None:
        """Update idle music cycling and motion detection.

        Call this every frame during idle state.
        Args:
            delta_ms: Time since last update in milliseconds
            motion_detected: True if camera detected motion
        """
        if not self._idle_mode:
            return

        # Track motion state
        if motion_detected:
            self._motion_detected = True
            self._last_motion_time = 0.0

            # Resume if was paused
            if self._idle_paused:
                self._idle_paused = False
                self._play_idle_track()
                logger.info("Idle music resumed - motion detected")
        else:
            self._last_motion_time += delta_ms

            # Pause after timeout with no motion
            if not self._idle_paused and self._last_motion_time > self.IDLE_PAUSE_TIMEOUT:
                self._idle_paused = True
                self.stop_music(fade_out_ms=2000)  # Slow fade out
                logger.info("Idle music paused - no motion detected")

        # Cycle to next track after duration
        if not self._idle_paused:
            self._idle_track_timer += delta_ms
            if self._idle_track_timer >= self.IDLE_TRACK_DURATION:
                self._idle_track_timer = 0.0
                self._idle_track_index = (self._idle_track_index + 1) % len(self.IDLE_TRACKS)
                self._play_idle_track()
                logger.info(f"Idle music cycling to: {self.IDLE_TRACKS[self._idle_track_index]}")

    def is_idle_music_active(self) -> bool:
        """Check if idle music mode is active."""
        return self._idle_mode

    def is_idle_music_paused(self) -> bool:
        """Check if idle music is paused due to no motion."""
        return self._idle_mode and self._idle_paused

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
