"""
ARTIFACT Audio Engine - Fast Chiptune Sound System.

Balatro-style chiptune music and sound effects.
Generates all sounds in <1 second using simple waveforms.
"""

import pygame
import array
import math
import random
import logging
from typing import Dict, Optional

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


def noise() -> float:
    """White noise generator."""
    return random.random() * 2 - 1


class AudioEngine:
    """
    Fast chiptune audio engine for ARTIFACT.

    Generates all sounds procedurally using simple waveforms.
    Generation takes <1 second (vs 80+ with old engine).
    """

    def __init__(self):
        self._initialized = False
        self._sounds: Dict[str, pygame.mixer.Sound] = {}
        self._music_playing = False
        self._volume_master = 1.0
        self._volume_sfx = 1.0
        self._volume_music = 1.0
        self._muted = False
        self._current_music: Optional[str] = None
        self._music_channel: Optional[pygame.mixer.Channel] = None
        self._generated = False

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

        logger.info("Generating chiptune sounds...")

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

        # === CHIPTUNE MUSIC ===
        self._gen_chiptune_music()

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

    # ===== CHIPTUNE MUSIC =====

    def _gen_chiptune_music(self) -> None:
        """Generate Balatro-style chiptune loops for all modes."""

        # Music configurations: {name: (bpm, melody_notes, bass_notes, duration_beats)}
        configs = {
            # Main states
            'idle': (128, [523, 659, 784, 1047, 988, 784, 659, 523], [130, 146, 164, 146], 16),
            'menu': (120, [440, 523, 659, 523, 440, 659, 784, 659], [55, 73, 82, 73], 8),

            # Fortune modes
            'fortune': (90, [294, 349, 440, 523, 440, 349, 294, 262], [73, 87, 110, 87], 16),

            # Action modes
            'quiz': (130, [440, 523, 587, 659, 587, 523, 440, 392], [110, 130, 146, 130], 8),
            'roulette': (125, [523, 659, 784, 880, 784, 659, 523, 440], [130, 164, 196, 164], 8),
            'roast': (135, [392, 466, 523, 622, 523, 466, 392, 349], [98, 116, 130, 116], 8),

            # Creative modes
            'flow_field': (105, [261, 311, 392, 466, 392, 311, 261, 233], [65, 78, 98, 78], 16),
            'glitch_mirror': (115, [392, 466, 523, 659, 523, 466, 392, 349], [98, 116, 130, 116], 8),
            'particle_sculptor': (118, [196, 233, 311, 392, 311, 233, 196, 174], [49, 58, 78, 58], 12),
            'ascii': (140, [523, 659, 784, 880, 784, 659, 523, 440], [130, 164, 196, 164], 8),

            # Arcade games
            'tower_stack': (150, [659, 587, 523, 587, 659, 784, 659, 587], [164, 146, 130, 146], 8),
            'bar_runner': (160, [784, 880, 988, 880, 784, 659, 587, 659], [196, 220, 246, 220], 8),
            'brick_breaker': (124, [523, 659, 587, 523, 659, 784, 698, 659], [130, 164, 146, 164], 8),
            'squid_game': (138, [392, 440, 392, 349, 330, 349, 392, 262], [98, 110, 98, 87], 8),
        }

        for name, (bpm, melody, bass, duration_beats) in configs.items():
            samples = self._gen_chiptune_loop(bpm, melody, bass, duration_beats)
            self._sounds[f"music_{name}"] = self._create_sound(samples)

    def _gen_chiptune_loop(
        self,
        bpm: int,
        melody: list,
        bass: list,
        duration_beats: int
    ) -> array.array:
        """Generate a single chiptune loop."""
        samples = array.array('h')
        beat_len = 60.0 / bpm
        duration = beat_len * duration_beats

        for i in range(int(SAMPLE_RATE * duration)):
            t = i / SAMPLE_RATE
            beat = int(t / (beat_len / 2)) % len(melody)
            bass_beat = int(t / beat_len) % len(bass)

            # Melody (square wave with envelope)
            note_t = t % (beat_len / 2)
            env = max(0, 1 - note_t * 4) * 0.8 + 0.2
            val = square(t, melody[beat]) * env * 0.2

            # Bass (triangle wave)
            val += triangle(t, bass[bass_beat]) * 0.15

            # Drums (noise on beats)
            drum_t = t % beat_len
            if drum_t < 0.05:
                val += noise() * 0.12 * (1 - drum_t * 20)
            elif 0.25 < drum_t < 0.3:
                val += noise() * 0.06 * (1 - (drum_t - 0.25) * 20)

            # Arpeggio overlay
            arp_idx = int(t * 8) % 4
            arp_mult = [1, 1.25, 1.5, 1.25][arp_idx]
            val += square(t, melody[beat] * arp_mult) * 0.08

            samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

        return samples

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
        "snake_classic": "music_ascii",
        "snake_tiny": "music_ascii",
        "pong": "music_bar_runner",
        "flappy": "music_bar_runner",
        "game_2048": "music_tower_stack",
        "lunar_lander": "music_flow_field",
        "hand_snake": "music_ascii",
        "rocketpy": "music_bar_runner",
        "skii": "music_flow_field",
        "ninja_fruit": "music_brick_breaker",
        "photobooth": "music_idle",
        "rap_god": "music_roast",
        "gesture_game": "music_quiz",
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
            sound = self._sounds.get("music_idle")
            if not sound:
                logger.warning(f"Music track not found: {sound_name}")
                return None
            sound_name = "music_idle"

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

    def toggle_mute(self) -> bool:
        """Toggle mute state."""
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
