#!/usr/bin/env python3
"""
Pre-generate all audio sounds and save them as WAV files.

Run this once to create assets/sounds/*.wav files that can be loaded instantly.
"""

import os
import sys
import wave
import array
import pygame

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from artifact.audio.engine import AudioEngine

def save_sound_to_wav(sound: pygame.mixer.Sound, filepath: str) -> None:
    """Save a pygame Sound to WAV file using wave module."""
    # Get raw sound buffer
    sound_array = pygame.sndarray.array(sound)

    # Convert to bytes
    if sound_array.ndim == 1:
        # Mono - convert to stereo
        stereo = array.array('h')
        for sample in sound_array:
            stereo.append(sample)
            stereo.append(sample)
        sound_bytes = stereo.tobytes()
        channels = 2
    else:
        # Already stereo
        sound_bytes = sound_array.tobytes()
        channels = 2

    # Write WAV file
    with wave.open(filepath, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(44100)
        wav_file.writeframes(sound_bytes)

def main():
    """Generate all sounds and save to WAV files."""
    # Create output directory
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sounds', 'generated')
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating sounds to: {output_dir}")

    # Initialize pygame mixer
    pygame.mixer.pre_init(44100, -16, 2, 4096)
    pygame.mixer.init()

    # Create audio engine and generate sounds
    print("Initializing audio engine...")
    engine = AudioEngine()
    engine._initialized = True

    print("Generating all sounds (this takes ~60 seconds)...")
    engine._generate_all_sounds()

    print(f"Generated {len(engine._sounds)} sounds")

    # Save each sound to WAV file
    saved_count = 0
    for sound_name, sound in engine._sounds.items():
        try:
            output_path = os.path.join(output_dir, f"{sound_name}.wav")
            save_sound_to_wav(sound, output_path)
            print(f"  ✓ {sound_name}.wav")
            saved_count += 1
        except Exception as e:
            print(f"  ✗ {sound_name}: {e}")

    print(f"\n✓ Saved {saved_count}/{len(engine._sounds)} sounds to {output_dir}")
    print("\nNext steps:")
    print("1. Commit the generated WAV files to git")
    print("2. Audio engine will auto-detect and load them at startup")

if __name__ == "__main__":
    main()
