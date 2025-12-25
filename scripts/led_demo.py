#!/usr/bin/env python3
"""
ARTIFACT LED Panel Demo - Psychedelic Animation
Full screen test with plasma, spirals, and color effects.
Runs on 128x128 LED matrix via NovaStar T50/DH418.
"""

import os
import math
import time
import random

# Must set before pygame import
os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame

# Display dimensions
HDMI_W, HDMI_H = 720, 480
LED_SIZE = 128

def hsv_to_rgb(h, s, v):
    """Convert HSV to RGB (h: 0-360, s: 0-1, v: 0-1)"""
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


class PlasmaEffect:
    """Flowing plasma effect"""
    def __init__(self, size):
        self.size = size
        self.time = 0

    def render(self, surface):
        for y in range(self.size):
            for x in range(self.size):
                # Multiple sine waves create plasma pattern
                v1 = math.sin(x / 16 + self.time)
                v2 = math.sin(y / 8 + self.time * 0.5)
                v3 = math.sin((x + y) / 16 + self.time * 0.7)
                v4 = math.sin(math.sqrt(x*x + y*y) / 8 + self.time * 0.3)

                v = (v1 + v2 + v3 + v4) / 4
                hue = (v + 1) * 180 + self.time * 30

                color = hsv_to_rgb(hue, 1.0, 0.9)
                surface.set_at((x, y), color)

        self.time += 0.05


class SpiralEffect:
    """Rotating spiral pattern"""
    def __init__(self, size):
        self.size = size
        self.angle = 0
        self.cx = size // 2
        self.cy = size // 2

    def render(self, surface):
        surface.fill((0, 0, 0))

        for y in range(self.size):
            for x in range(self.size):
                dx = x - self.cx
                dy = y - self.cy
                dist = math.sqrt(dx*dx + dy*dy)
                angle = math.atan2(dy, dx)

                # Spiral pattern
                spiral = (angle + dist / 10 + self.angle) * 3
                v = (math.sin(spiral) + 1) / 2

                hue = (dist * 3 + self.angle * 50) % 360
                brightness = v * 0.9 + 0.1

                color = hsv_to_rgb(hue, 1.0, brightness)
                surface.set_at((x, y), color)

        self.angle += 0.03


class FireEffect:
    """Fire/heat effect"""
    def __init__(self, size):
        self.size = size
        self.heat = [[0] * size for _ in range(size)]

    def render(self, surface):
        # Add heat at bottom
        for x in range(self.size):
            self.heat[self.size - 1][x] = random.randint(200, 255)
            self.heat[self.size - 2][x] = random.randint(150, 255)

        # Propagate heat upward
        for y in range(self.size - 2, 0, -1):
            for x in range(1, self.size - 1):
                avg = (
                    self.heat[y + 1][x - 1] +
                    self.heat[y + 1][x] +
                    self.heat[y + 1][x + 1] +
                    self.heat[y][x]
                ) / 4.05
                self.heat[y][x] = max(0, avg - random.random() * 2)

        # Render
        for y in range(self.size):
            for x in range(self.size):
                h = int(self.heat[y][x])
                if h > 200:
                    color = (255, 255, min(255, (h - 200) * 4))
                elif h > 150:
                    color = (255, min(255, (h - 100) * 2), 0)
                elif h > 50:
                    color = (min(255, h * 2), 0, 0)
                else:
                    color = (h // 2, 0, 0)
                surface.set_at((x, y), color)


class MatrixRain:
    """Matrix-style falling characters"""
    def __init__(self, size):
        self.size = size
        self.columns = [
            {'y': random.randint(-size, 0), 'speed': random.uniform(0.5, 2), 'length': random.randint(5, 15)}
            for _ in range(size)
        ]

    def render(self, surface):
        surface.fill((0, 0, 0))

        for x, col in enumerate(self.columns):
            y = int(col['y'])
            length = col['length']

            for i in range(length):
                py = y - i
                if 0 <= py < self.size:
                    if i == 0:
                        color = (200, 255, 200)
                    else:
                        brightness = int(255 * (1 - i / length))
                        color = (0, brightness, 0)
                    surface.set_at((x, py), color)

            col['y'] += col['speed']
            if col['y'] - length > self.size:
                col['y'] = random.randint(-20, -5)
                col['speed'] = random.uniform(0.5, 2)
                col['length'] = random.randint(5, 15)


class RainbowWave:
    """Smooth rainbow wave"""
    def __init__(self, size):
        self.size = size
        self.offset = 0

    def render(self, surface):
        for y in range(self.size):
            for x in range(self.size):
                hue = (x * 3 + y * 3 + self.offset) % 360
                color = hsv_to_rgb(hue, 1.0, 1.0)
                surface.set_at((x, y), color)

        self.offset += 2


class PulsatingCircles:
    """Concentric pulsating circles"""
    def __init__(self, size):
        self.size = size
        self.time = 0
        self.cx = size // 2
        self.cy = size // 2

    def render(self, surface):
        surface.fill((0, 0, 0))

        for y in range(self.size):
            for x in range(self.size):
                dx = x - self.cx
                dy = y - self.cy
                dist = math.sqrt(dx*dx + dy*dy)

                wave = math.sin(dist / 5 - self.time * 2) * 0.5 + 0.5
                hue = (dist * 5 + self.time * 50) % 360

                color = hsv_to_rgb(hue, 1.0, wave)
                surface.set_at((x, y), color)

        self.time += 0.1


class Starfield:
    """3D starfield"""
    def __init__(self, size):
        self.size = size
        self.stars = [
            {'x': random.uniform(-1, 1), 'y': random.uniform(-1, 1), 'z': random.uniform(0.1, 1)}
            for _ in range(100)
        ]

    def render(self, surface):
        surface.fill((0, 0, 10))
        cx = self.size // 2
        cy = self.size // 2

        for star in self.stars:
            star['z'] -= 0.02
            if star['z'] <= 0.01:
                star['x'] = random.uniform(-1, 1)
                star['y'] = random.uniform(-1, 1)
                star['z'] = 1.0

            sx = int(cx + star['x'] / star['z'] * 50)
            sy = int(cy + star['y'] / star['z'] * 50)

            if 0 <= sx < self.size and 0 <= sy < self.size:
                brightness = int(255 * (1 - star['z']))
                size = max(1, int(3 * (1 - star['z'])))
                pygame.draw.circle(surface, (brightness, brightness, brightness), (sx, sy), size)


def main():
    print("=" * 50)
    print("ARTIFACT LED Panel Demo")
    print("=" * 50)

    pygame.init()
    print(f"Video driver: {pygame.display.get_driver()}")

    # Create fullscreen display
    screen = pygame.display.set_mode((HDMI_W, HDMI_H), pygame.FULLSCREEN)
    pygame.display.set_caption("ARTIFACT LED Demo")

    # Create LED surface (128x128 in top-left corner)
    led_surface = pygame.Surface((LED_SIZE, LED_SIZE))

    # Initialize effects
    effects = [
        ("🌈 Rainbow Wave", RainbowWave(LED_SIZE)),
        ("🔮 Plasma", PlasmaEffect(LED_SIZE)),
        ("🌀 Spiral", SpiralEffect(LED_SIZE)),
        ("🔥 Fire", FireEffect(LED_SIZE)),
        ("💚 Matrix Rain", MatrixRain(LED_SIZE)),
        ("⭕ Pulsating Circles", PulsatingCircles(LED_SIZE)),
        ("✨ Starfield", Starfield(LED_SIZE)),
    ]

    current_effect = 0
    effect_start_time = time.time()
    effect_duration = 8  # seconds per effect

    clock = pygame.time.Clock()
    running = True
    frame = 0

    print("\nEffects cycle every 8 seconds. Press Ctrl+C to exit.\n")

    try:
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        current_effect = (current_effect + 1) % len(effects)
                        effect_start_time = time.time()
                        print(f"Switched to: {effects[current_effect][0]}")

            # Auto-switch effects
            if time.time() - effect_start_time > effect_duration:
                current_effect = (current_effect + 1) % len(effects)
                effect_start_time = time.time()
                print(f"Now playing: {effects[current_effect][0]}")

            # Render current effect
            name, effect = effects[current_effect]
            effect.render(led_surface)

            # Clear screen and blit LED surface to top-left
            screen.fill((0, 0, 0))
            screen.blit(led_surface, (0, 0))

            pygame.display.flip()

            frame += 1
            clock.tick(30)  # 30 FPS

    except KeyboardInterrupt:
        print("\nStopped by user")

    pygame.quit()
    print("Demo ended.")


if __name__ == "__main__":
    main()
