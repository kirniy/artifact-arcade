#!/usr/bin/env python3
"""
VNVNC LED Panel Demo - Ultimate Edition
Showcasing 128x128 LED matrix capabilities with rotating 3D logo and stunning effects.
"""

import os
import math
import time
import random
import array
import subprocess

os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
os.environ['SDL_AUDIODRIVER'] = 'alsa'
os.environ['AUDIODEV'] = 'hw:0,0'  # HDMI audio

import pygame

try:
    import cv2
    HAS_CV2 = True
except:
    HAS_CV2 = False

HDMI_W, HDMI_H = 720, 480
LED_SIZE = 128
SAMPLE_RATE = 22050


def hsv_to_rgb(h, s, v):
    h = h % 360
    s = max(0, min(1, s))
    v = max(0, min(1, v))
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60: r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else: r, g, b = c, 0, x
    return (
        max(0, min(255, int((r + m) * 255))),
        max(0, min(255, int((g + m) * 255))),
        max(0, min(255, int((b + m) * 255)))
    )


# ============== SOUND ==============

class SoundManager:
    def __init__(self):
        self.sounds = {}
        self.current = None
        self.channel = None
        self.enabled = False

    def init(self):
        try:
            # Load bcm2835 module for 3.5mm jack
            subprocess.run(['sudo', 'modprobe', 'snd-bcm2835'], capture_output=True)

            # Use 3.5mm headphone jack (card 2)
            os.environ['AUDIODEV'] = 'hw:2,0'
            pygame.mixer.quit()
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=4096)
            self.channel = pygame.mixer.Channel(0)
            print("Audio: 3.5mm jack (hw:2,0)")

            # Generate switch sound (arcade blip)
            switch_samples = array.array('h')
            for i in range(int(SAMPLE_RATE * 0.1)):
                t = i / SAMPLE_RATE
                env = max(0, 1 - t * 12)
                freq = 1200 - t * 4000  # Descending pitch
                val = (1 if math.sin(2 * math.pi * freq * t) > 0 else -1) * 0.5  # Square wave
                switch_samples.append(int(0.3 * 32767 * val * env))
            self.sounds['switch'] = pygame.mixer.Sound(buffer=switch_samples)

            # Chiptune music generator - Balatro style!
            def square(t, freq):
                return 1 if (t * freq) % 1 < 0.5 else -1

            def triangle(t, freq):
                p = (t * freq) % 1
                return 4 * abs(p - 0.5) - 1

            def noise(t):
                return random.random() * 2 - 1

            # Different melodies for each mode
            chiptunes = {
                'cosmic': {'bpm': 90, 'notes': [261, 329, 392, 523, 392, 329, 261, 196], 'bass': [65, 82, 98, 65]},
                'deep': {'bpm': 70, 'notes': [130, 164, 196, 261, 196, 164, 130, 98], 'bass': [32, 41, 49, 32]},
                'mid': {'bpm': 120, 'notes': [440, 523, 659, 784, 659, 523, 440, 349], 'bass': [110, 130, 146, 110]},
                'high': {'bpm': 140, 'notes': [523, 659, 784, 1046, 784, 659, 523, 440], 'bass': [130, 164, 196, 130]},
                'electric': {'bpm': 130, 'notes': [329, 440, 523, 659, 523, 440, 329, 261], 'bass': [82, 110, 130, 82]},
                'nature': {'bpm': 100, 'notes': [392, 440, 523, 587, 523, 440, 392, 329], 'bass': [98, 110, 130, 98]},
                'digital': {'bpm': 150, 'notes': [587, 659, 784, 880, 784, 659, 587, 523], 'bass': [146, 164, 196, 146]},
                'xmas': {'bpm': 110, 'notes': [392, 392, 440, 392, 523, 493, 392, 392], 'bass': [196, 164, 130, 196]},  # Jingle bells vibe
            }

            for name, cfg in chiptunes.items():
                samples = array.array('h')
                bpm = cfg['bpm']
                beat_len = 60 / bpm
                notes = cfg['notes']
                bass = cfg['bass']
                duration = beat_len * len(notes) * 2  # 2 loops worth

                for i in range(int(SAMPLE_RATE * duration)):
                    t = i / SAMPLE_RATE
                    beat = int(t / (beat_len / 2)) % len(notes)
                    bass_beat = int(t / beat_len) % len(bass)

                    # Melody (square wave with envelope)
                    note_t = (t % (beat_len / 2))
                    env = max(0, 1 - note_t * 4) * 0.8 + 0.2
                    melody = square(t, notes[beat]) * env * 0.25

                    # Bass (triangle wave)
                    bass_note = triangle(t, bass[bass_beat]) * 0.2

                    # Drums (noise on beats)
                    drum = 0
                    drum_t = t % beat_len
                    if drum_t < 0.05:
                        drum = noise(t) * 0.15 * (1 - drum_t * 20)
                    elif 0.25 < drum_t < 0.3:
                        drum = noise(t) * 0.08 * (1 - (drum_t - 0.25) * 20)

                    # Arpeggio overlay
                    arp_idx = int(t * 8) % 4
                    arp_freqs = [notes[beat], notes[beat] * 1.25, notes[beat] * 1.5, notes[beat] * 1.25]
                    arp = square(t, arp_freqs[arp_idx]) * 0.1

                    val = melody + bass_note + drum + arp
                    samples.append(int(max(-1, min(1, val)) * 32767 * 0.7))

                self.sounds[name] = pygame.mixer.Sound(buffer=samples)

            self.enabled = True
            return True
        except Exception as e:
            print(f"Audio failed: {e}")
            self.enabled = False
            return False

    def play(self, name):
        if not self.enabled:
            return
        if name != self.current and name in self.sounds:
            self.current = name
            if self.channel:
                self.channel.stop()
                self.channel.play(self.sounds[name], loops=-1)

    def play_once(self, name):
        """Play sound once (for switch effects)"""
        if not self.enabled:
            return
        if name in self.sounds:
            self.sounds[name].play()

    def stop(self):
        if self.enabled:
            pygame.mixer.stop()


# ============== 3D ROTATING VNVNC ==============

# 3D letter definitions (vertices for each letter)
LETTERS_3D = {
    'V': [(-1, -1, 0), (0, 1, 0), (1, -1, 0)],
    'N': [(-1, 1, 0), (-1, -1, 0), (1, 1, 0), (1, -1, 0)],
    'C': [(1, -1, 0), (-0.5, -1, 0), (-1, -0.5, 0), (-1, 0.5, 0), (-0.5, 1, 0), (1, 1, 0)],
}


class VNVNC3DRotating:
    """True 3D rotating VNVNC logo"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def project(self, x, y, z, rx, ry, rz, scale, ox, oy):
        # Rotate around Y axis
        x1 = x * math.cos(ry) - z * math.sin(ry)
        z1 = x * math.sin(ry) + z * math.cos(ry)
        # Rotate around X axis
        y1 = y * math.cos(rx) - z1 * math.sin(rx)
        z2 = y * math.sin(rx) + z1 * math.cos(rx)
        # Rotate around Z axis
        x2 = x1 * math.cos(rz) - y1 * math.sin(rz)
        y2 = x1 * math.sin(rz) + y1 * math.cos(rz)
        # Perspective
        perspective = 3 / (3 + z2)
        return int(ox + x2 * scale * perspective), int(oy + y2 * scale * perspective), z2

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            self.started = True

        surface.fill((0, 0, 20))

        # Background particles
        for i in range(50):
            px = (i * 73 + int(self.time * 20)) % self.size
            py = (i * 41 + int(self.time * 15)) % self.size
            brightness = 50 + int(30 * math.sin(i + self.time))
            surface.set_at((px, py), (brightness, brightness, brightness + 30))

        cx, cy = self.size // 2, self.size // 2
        rx = math.sin(self.time * 0.5) * 0.3
        ry = self.time * 0.8
        rz = math.sin(self.time * 0.3) * 0.2

        # Draw "VNVNC" with 3D effect
        letters = "VNVNC"
        letter_width = 22
        start_x = cx - (len(letters) * letter_width) // 2

        for idx, letter in enumerate(letters):
            lx = start_x + idx * letter_width
            hue = (idx * 60 + self.time * 40) % 360

            # Draw letter with multiple depth layers for 3D effect
            for depth in range(8):
                z_offset = depth * 0.3
                brightness = 1.0 - depth * 0.1
                color = hsv_to_rgb(hue, 0.8, brightness)

                if letter == 'V':
                    pts = [
                        self.project(-8, -10, z_offset, rx, ry, rz, 1, lx, cy),
                        self.project(0, 10, z_offset, rx, ry, rz, 1, lx, cy),
                        self.project(8, -10, z_offset, rx, ry, rz, 1, lx, cy),
                    ]
                    if len(pts) >= 3:
                        pygame.draw.lines(surface, color, False, [(p[0], p[1]) for p in pts], 2)

                elif letter == 'N':
                    pts = [
                        self.project(-6, 10, z_offset, rx, ry, rz, 1, lx, cy),
                        self.project(-6, -10, z_offset, rx, ry, rz, 1, lx, cy),
                        self.project(6, 10, z_offset, rx, ry, rz, 1, lx, cy),
                        self.project(6, -10, z_offset, rx, ry, rz, 1, lx, cy),
                    ]
                    if len(pts) >= 4:
                        pygame.draw.lines(surface, color, False, [(p[0], p[1]) for p in pts], 2)

                elif letter == 'C':
                    pts = []
                    for angle in range(45, 316, 15):
                        rad = math.radians(angle)
                        px = math.cos(rad) * 8
                        py = math.sin(rad) * 10
                        pts.append(self.project(px, py, z_offset, rx, ry, rz, 1, lx, cy))
                    if len(pts) >= 2:
                        pygame.draw.lines(surface, color, False, [(p[0], p[1]) for p in pts], 2)

        # Glow effect
        glow_size = int(30 + 10 * math.sin(self.time * 2))
        for r in range(glow_size, 0, -3):
            alpha = int(20 * (1 - r / glow_size))
            pygame.draw.circle(surface, (alpha, 0, alpha * 2), (cx, cy), r + 20)

        self.time += 0.03

    def reset(self):
        self.started = False


class VNVNCWave3D:
    """VNVNC with wave distortion"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('mid')
            self.started = True

        surface.fill((5, 0, 15))
        cx, cy = self.size // 2, self.size // 2

        text = "VNVNC"
        char_spacing = 20
        start_x = cx - (len(text) * char_spacing) // 2

        for layer in range(10, 0, -1):
            for i, char in enumerate(text):
                wave = math.sin(self.time * 3 + i * 0.5) * 8
                x = start_x + i * char_spacing
                y = cy + wave + layer * 2
                z = layer * 0.5

                brightness = 255 - layer * 20
                hue = (i * 50 + self.time * 30 + layer * 10) % 360
                color = hsv_to_rgb(hue, 0.9, brightness / 255)

                # Simple block letters
                if char == 'V':
                    pygame.draw.line(surface, color, (x - 6, int(y - 8)), (x, int(y + 8)), 3)
                    pygame.draw.line(surface, color, (x, int(y + 8)), (x + 6, int(y - 8)), 3)
                elif char == 'N':
                    pygame.draw.line(surface, color, (x - 5, int(y + 8)), (x - 5, int(y - 8)), 3)
                    pygame.draw.line(surface, color, (x - 5, int(y - 8)), (x + 5, int(y + 8)), 3)
                    pygame.draw.line(surface, color, (x + 5, int(y + 8)), (x + 5, int(y - 8)), 3)
                elif char == 'C':
                    pygame.draw.arc(surface, color, (x - 8, int(y - 8), 16, 16), 0.5, 5.8, 3)

        self.time += 0.05

    def reset(self):
        self.started = False


# ============== EPIC EFFECTS ==============

class PlasmaVortex:
    """Intense plasma vortex"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True

        cx, cy = self.size // 2, self.size // 2
        for y in range(self.size):
            for x in range(self.size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                angle = math.atan2(dy, dx)

                # Vortex twist
                twist = angle + dist / 15 + self.time * 2
                v = math.sin(twist * 5) * 0.5 + 0.5

                # Radial pulse
                pulse = math.sin(dist / 10 - self.time * 3) * 0.3 + 0.7

                hue = (angle * 60 + dist * 2 + self.time * 50) % 360
                brightness = v * pulse * min(1, (self.size / 2 - dist + 20) / 20)

                if brightness > 0:
                    surface.set_at((x, y), hsv_to_rgb(hue, 0.9, max(0, brightness)))

        self.time += 0.04

    def reset(self):
        self.started = False


class NeonGrid:
    """Retro neon grid"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('high')
            self.started = True

        surface.fill((10, 0, 20))
        horizon = self.size // 2 + 10

        # Sun
        sun_y = horizon - 30
        for r in range(25, 0, -1):
            brightness = (25 - r) * 10
            pygame.draw.circle(surface, (brightness, brightness // 3, brightness // 2),
                             (self.size // 2, sun_y), r)

        # Horizontal lines with perspective
        for i in range(1, 15):
            progress = i / 15
            y = horizon + int(progress * progress * (self.size - horizon))
            intensity = int(200 * (1 - progress * 0.5))
            hue = (self.time * 30 + i * 20) % 360
            color = hsv_to_rgb(hue, 0.8, intensity / 255)
            pygame.draw.line(surface, color, (0, y), (self.size, y), 1)

        # Vertical lines with perspective
        for i in range(-10, 11, 2):
            x1 = self.size // 2 + i * 3
            x2 = self.size // 2 + i * 20
            y1 = horizon
            y2 = self.size
            hue = (self.time * 30 + abs(i) * 15) % 360
            color = hsv_to_rgb(hue, 0.7, 0.6)
            pygame.draw.line(surface, color, (x1, y1), (x2, y2), 1)

        # Scrolling effect
        scroll = (self.time * 50) % 20
        for i in range(5):
            y = horizon + 10 + i * 20 + int(scroll)
            if y < self.size:
                pygame.draw.line(surface, (100, 0, 100), (0, y), (self.size, y), 1)

        self.time += 0.03

    def reset(self):
        self.started = False


class ElectricStorm:
    """Electric storm with lightning"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.lightning = []
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True

        # Dark stormy background
        for y in range(self.size):
            darkness = 10 + y // 10
            surface.fill((darkness // 3, darkness // 3, darkness), (0, y, self.size, 1))

        # Generate lightning
        if random.random() < 0.05:
            x = random.randint(20, self.size - 20)
            self.lightning = [(x, 0)]
            y = 0
            while y < self.size:
                y += random.randint(5, 15)
                x += random.randint(-10, 10)
                x = max(5, min(self.size - 5, x))
                self.lightning.append((x, y))

        # Draw lightning
        if self.lightning and random.random() > 0.3:
            for i in range(len(self.lightning) - 1):
                pygame.draw.line(surface, (255, 255, 255),
                               self.lightning[i], self.lightning[i + 1], 3)
                pygame.draw.line(surface, (200, 200, 255),
                               self.lightning[i], self.lightning[i + 1], 1)

            # Branches
            for point in self.lightning[::3]:
                if random.random() < 0.5:
                    ex = point[0] + random.randint(-20, 20)
                    ey = point[1] + random.randint(10, 30)
                    pygame.draw.line(surface, (150, 150, 255), point, (ex, ey), 1)

        # Rain
        for _ in range(30):
            rx = random.randint(0, self.size)
            ry = random.randint(0, self.size)
            pygame.draw.line(surface, (100, 100, 150), (rx, ry), (rx + 2, ry + 8), 1)

        self.time += 0.05

    def reset(self):
        self.started = False
        self.lightning = []


class QuantumField:
    """Quantum particle field"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.particles = [
            {'x': random.random(), 'y': random.random(), 'vx': 0, 'vy': 0}
            for _ in range(60)
        ]
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            self.started = True

        surface.fill((0, 5, 15))

        # Update particles with wave function behavior
        for p in self.particles:
            # Quantum tunneling / wave behavior
            p['vx'] += (random.random() - 0.5) * 0.02 + math.sin(self.time + p['y'] * 10) * 0.01
            p['vy'] += (random.random() - 0.5) * 0.02 + math.cos(self.time + p['x'] * 10) * 0.01
            p['x'] += p['vx']
            p['y'] += p['vy']

            # Wrap around
            if p['x'] < 0: p['x'] = 1
            if p['x'] > 1: p['x'] = 0
            if p['y'] < 0: p['y'] = 1
            if p['y'] > 1: p['y'] = 0

            # Damping
            p['vx'] *= 0.98
            p['vy'] *= 0.98

        # Draw connections
        for i, p1 in enumerate(self.particles):
            px1 = int(p1['x'] * self.size)
            py1 = int(p1['y'] * self.size)

            for p2 in self.particles[i+1:]:
                px2 = int(p2['x'] * self.size)
                py2 = int(p2['y'] * self.size)
                dist = math.sqrt((px1 - px2)**2 + (py1 - py2)**2)

                if dist < 40:
                    alpha = int(255 * (1 - dist / 40))
                    hue = (self.time * 30 + i * 5) % 360
                    color = hsv_to_rgb(hue, 0.7, alpha / 255)
                    pygame.draw.line(surface, color, (px1, py1), (px2, py2), 1)

            # Draw particle
            hue = (p1['x'] * 180 + self.time * 50) % 360
            pygame.draw.circle(surface, hsv_to_rgb(hue, 0.9, 0.9), (px1, py1), 3)

        self.time += 0.04

    def reset(self):
        self.started = False


class HypercubeProjection:
    """4D hypercube projection"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

        # 4D hypercube vertices (tesseract)
        self.vertices = []
        for w in [-1, 1]:
            for z in [-1, 1]:
                for y in [-1, 1]:
                    for x in [-1, 1]:
                        self.vertices.append([x, y, z, w])

        # Edges connecting vertices
        self.edges = []
        for i in range(16):
            for j in range(i + 1, 16):
                diff = sum(abs(self.vertices[i][k] - self.vertices[j][k]) for k in range(4))
                if diff == 2:  # Adjacent vertices
                    self.edges.append((i, j))

    def rotate4d(self, vertex, angles):
        x, y, z, w = vertex
        # XY rotation
        a = angles[0]
        x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        # XZ rotation
        a = angles[1]
        x, z = x * math.cos(a) - z * math.sin(a), x * math.sin(a) + z * math.cos(a)
        # XW rotation
        a = angles[2]
        x, w = x * math.cos(a) - w * math.sin(a), x * math.sin(a) + w * math.cos(a)
        # YZ rotation
        a = angles[3]
        y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
        return [x, y, z, w]

    def project4dto2d(self, vertex):
        x, y, z, w = vertex
        # 4D to 3D projection
        distance = 3
        factor3d = distance / (distance - w)
        x3d, y3d, z3d = x * factor3d, y * factor3d, z * factor3d
        # 3D to 2D projection
        factor2d = distance / (distance - z3d)
        return x3d * factor2d, y3d * factor2d

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            self.started = True

        surface.fill((0, 0, 10))
        cx, cy = self.size // 2, self.size // 2

        angles = [self.time * 0.5, self.time * 0.3, self.time * 0.4, self.time * 0.6]

        projected = []
        for v in self.vertices:
            rotated = self.rotate4d(v, angles)
            px, py = self.project4dto2d(rotated)
            projected.append((int(cx + px * 30), int(cy + py * 30), rotated[3]))

        # Draw edges
        for i, j in self.edges:
            hue = (self.time * 30 + (projected[i][2] + projected[j][2]) * 50) % 360
            depth = (projected[i][2] + projected[j][2] + 2) / 4
            color = hsv_to_rgb(hue, 0.8, 0.3 + depth * 0.7)
            pygame.draw.line(surface, color, (projected[i][0], projected[i][1]),
                           (projected[j][0], projected[j][1]), 2)

        # Draw vertices
        for px, py, w in projected:
            brightness = 0.5 + (w + 1) / 4
            pygame.draw.circle(surface, hsv_to_rgb((self.time * 50) % 360, 0.9, brightness), (px, py), 4)

        self.time += 0.02

    def reset(self):
        self.started = False


class DNAHelix:
    """DNA double helix animation"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('mid')
            self.started = True

        surface.fill((0, 10, 20))
        cx = self.size // 2

        for y in range(self.size):
            phase = y / 20 + self.time * 2

            # Double helix strands
            x1 = cx + int(math.sin(phase) * 25)
            x2 = cx + int(math.sin(phase + math.pi) * 25)

            depth1 = math.cos(phase)
            depth2 = math.cos(phase + math.pi)

            # Colors based on depth
            if depth1 > 0:
                pygame.draw.circle(surface, (200, 50, 50), (x1, y), 4)
            if depth2 > 0:
                pygame.draw.circle(surface, (50, 50, 200), (x2, y), 4)

            # Base pairs (rungs)
            if y % 8 == 0:
                hue = (y * 3 + self.time * 30) % 360
                color = hsv_to_rgb(hue, 0.7, 0.8)
                pygame.draw.line(surface, color, (x1, y), (x2, y), 2)

            # Draw back strand after front
            if depth1 <= 0:
                pygame.draw.circle(surface, (100, 25, 25), (x1, y), 3)
            if depth2 <= 0:
                pygame.draw.circle(surface, (25, 25, 100), (x2, y), 3)

        self.time += 0.05

    def reset(self):
        self.started = False


class FractalTree:
    """Magical fractal tree with seasons, fireflies, and cherry blossoms"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.season = 0  # 0=spring, 1=summer, 2=autumn, 3=winter
        self.season_time = 0
        self.particles = []  # fireflies/leaves/blossoms
        self.branch_cache = []

    def draw_branch(self, surface, x, y, angle, length, depth, max_depth):
        if depth > max_depth or length < 2:
            # Leaf/blossom at end
            if depth >= max_depth - 1:
                self.branch_cache.append((x, y, depth))
            return

        # Calculate end point with wind sway
        wind = math.sin(self.time * 2 + depth * 0.5 + x * 0.01) * (depth * 0.02)
        end_x = x + math.cos(angle + wind) * length
        end_y = y - math.sin(angle + wind) * length

        # Branch color - brown bark transitioning to seasonal colors
        if depth < max_depth - 2:
            # Main branches - dark brown
            brown = (60 + depth * 5, 40 + depth * 3, 20)
            color = brown
        else:
            # Tips - seasonal color
            if self.season == 0:  # Spring - pink blossoms
                color = (255, 150 + depth * 10, 180)
            elif self.season == 1:  # Summer - green leaves
                color = (50, 180 - depth * 10, 50)
            elif self.season == 2:  # Autumn - orange/red
                hue = 30 - depth * 5 + random.randint(-10, 10)
                color = hsv_to_rgb(max(0, hue), 0.9, 0.9)
            else:  # Winter - bare/frost
                color = (150, 150, 160)

        thickness = max(1, (max_depth - depth) // 2 + 1)
        pygame.draw.line(surface, color, (int(x), int(y)), (int(end_x), int(end_y)), thickness)

        # Asymmetric branching for natural look
        angle_var = 0.4 + 0.1 * math.sin(self.time + depth)
        len_var = 0.65 + 0.1 * math.sin(self.time * 0.5 + x * 0.1)

        self.draw_branch(surface, end_x, end_y, angle + angle_var, length * len_var, depth + 1, max_depth)
        self.draw_branch(surface, end_x, end_y, angle - angle_var * 0.9, length * (len_var + 0.05), depth + 1, max_depth)
        # Extra small branch sometimes
        if depth > 2 and random.random() < 0.3:
            self.draw_branch(surface, end_x, end_y, angle + 0.1, length * 0.5, depth + 2, max_depth)

    def render(self, surface):
        if not self.started:
            self.sound.play('nature')
            self.started = True

        # Sky gradient based on season
        for y in range(self.size - 15):
            t = y / (self.size - 15)
            if self.season == 0:  # Spring dawn
                r, g, b = int(255 * t + 100), int(150 + 50 * t), int(180 + 60 * t)
            elif self.season == 1:  # Summer day
                r, g, b = int(100 + 100 * t), int(150 + 100 * t), int(255)
            elif self.season == 2:  # Autumn sunset
                r, g, b = int(255), int(100 + 80 * t), int(50 + 100 * t)
            else:  # Winter night
                r, g, b = int(20 + 30 * t), int(25 + 35 * t), int(50 + 50 * t)
            pygame.draw.line(surface, (min(255, r), min(255, g), min(255, b)), (0, y), (self.size, y))

        # Ground
        if self.season == 3:
            pygame.draw.rect(surface, (220, 220, 240), (0, self.size - 15, self.size, 15))  # Snow
        elif self.season == 2:
            pygame.draw.rect(surface, (80, 50, 30), (0, self.size - 15, self.size, 15))  # Dead grass
        else:
            pygame.draw.rect(surface, (40, 100, 40), (0, self.size - 15, self.size, 15))  # Grass

        # Clear branch cache
        self.branch_cache = []

        # Draw tree
        max_depth = 8
        self.draw_branch(surface, self.size // 2, self.size - 15, math.pi / 2, 30, 0, max_depth)

        # Draw leaves/blossoms at branch ends
        for bx, by, depth in self.branch_cache:
            if self.season == 0:  # Cherry blossoms
                for _ in range(2):
                    px = int(bx + random.randint(-3, 3))
                    py = int(by + random.randint(-3, 3))
                    if 0 <= px < self.size and 0 <= py < self.size:
                        pygame.draw.circle(surface, (255, 180, 200), (px, py), 2)
            elif self.season == 1:  # Green leaves
                for _ in range(2):
                    px = int(bx + random.randint(-2, 2))
                    py = int(by + random.randint(-2, 2))
                    if 0 <= px < self.size and 0 <= py < self.size:
                        green = random.randint(120, 200)
                        pygame.draw.circle(surface, (50, green, 50), (px, py), 2)

        # Seasonal particles
        if self.season == 0:  # Falling petals
            if random.random() < 0.1:
                self.particles.append({'x': random.randint(0, self.size), 'y': -5, 'type': 'petal'})
        elif self.season == 2:  # Falling leaves
            if random.random() < 0.08:
                self.particles.append({'x': random.randint(0, self.size), 'y': -5, 'type': 'leaf',
                                      'hue': random.randint(15, 45)})
        elif self.season == 3:  # Snow
            if random.random() < 0.15:
                self.particles.append({'x': random.randint(0, self.size), 'y': -5, 'type': 'snow'})
        else:  # Summer - fireflies at night edges
            if random.random() < 0.02:
                self.particles.append({'x': random.randint(0, self.size), 'y': random.randint(20, 100),
                                      'type': 'firefly', 'life': 60})

        # Update and draw particles
        new_particles = []
        for p in self.particles:
            if p['type'] == 'petal':
                p['x'] += math.sin(self.time * 3 + p['y'] * 0.1) * 0.5
                p['y'] += 0.8
                if p['y'] < self.size:
                    pygame.draw.circle(surface, (255, 200, 210), (int(p['x']), int(p['y'])), 2)
                    new_particles.append(p)
            elif p['type'] == 'leaf':
                p['x'] += math.sin(self.time * 2 + p['y'] * 0.05) * 1.5
                p['y'] += 1.2
                if p['y'] < self.size:
                    color = hsv_to_rgb(p['hue'], 0.9, 0.8)
                    pygame.draw.circle(surface, color, (int(p['x']), int(p['y'])), 2)
                    new_particles.append(p)
            elif p['type'] == 'snow':
                p['x'] += math.sin(self.time * 2 + p['y'] * 0.1) * 0.3
                p['y'] += 0.6
                if p['y'] < self.size - 10:
                    pygame.draw.circle(surface, (255, 255, 255), (int(p['x']), int(p['y'])), 1)
                    new_particles.append(p)
            elif p['type'] == 'firefly':
                p['x'] += math.sin(self.time * 4 + p['y']) * 0.5
                p['y'] += math.cos(self.time * 3 + p['x'] * 0.1) * 0.3
                p['life'] -= 1
                if p['life'] > 0:
                    glow = int(200 * abs(math.sin(self.time * 8 + p['x'])))
                    pygame.draw.circle(surface, (glow, glow, 50), (int(p['x']), int(p['y'])), 2)
                    new_particles.append(p)

        self.particles = new_particles[-100:]  # Limit particles

        # Season transition
        self.season_time += 0.002
        if self.season_time > 1:
            self.season_time = 0
            self.season = (self.season + 1) % 4
            self.particles = []

        self.time += 0.03

    def reset(self):
        self.started = False
        self.particles = []
        self.season = 0
        self.season_time = 0


class BlackHole:
    """Black hole with accretion disk"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.particles = [{'r': random.uniform(20, 60), 'a': random.uniform(0, 6.28),
                          'speed': random.uniform(0.02, 0.05)} for _ in range(100)]
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True

        surface.fill((0, 0, 0))
        cx, cy = self.size // 2, self.size // 2

        # Accretion disk particles
        for p in self.particles:
            p['a'] += p['speed'] * (50 / p['r'])  # Faster closer to center
            p['r'] -= 0.05  # Spiral inward

            if p['r'] < 8:  # Reset when consumed
                p['r'] = random.uniform(50, 70)
                p['a'] = random.uniform(0, 6.28)

            x = cx + int(p['r'] * math.cos(p['a']))
            y = cy + int(p['r'] * 0.3 * math.sin(p['a']))  # Squashed for disk effect

            # Color based on temperature (closer = hotter)
            temp = (60 - p['r']) / 60
            if temp > 0.7:
                color = (255, 255, 200)
            elif temp > 0.4:
                color = (255, 150, 50)
            else:
                color = (200, 50, 50)

            pygame.draw.circle(surface, color, (x, y), 2)

        # Event horizon (black circle with gradient edge)
        for r in range(15, 5, -1):
            alpha = (15 - r) * 15
            pygame.draw.circle(surface, (alpha, 0, alpha // 2), (cx, cy), r)
        pygame.draw.circle(surface, (0, 0, 0), (cx, cy), 6)

        # Gravitational lensing effect (ring)
        pygame.draw.circle(surface, (50, 50, 100), (cx, cy), 20, 1)

        self.time += 0.03

    def reset(self):
        self.started = False


# ============== CHRISTMAS ==============

class Snowfall:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.flakes = [{'x': random.randint(0, size), 'y': random.randint(-size, 0),
                       'speed': random.uniform(0.5, 2), 'size': random.randint(1, 3)}
                      for _ in range(150)]

    def render(self, surface):
        if not self.started:
            self.sound.play('mid')
            self.started = True

        for y in range(self.size):
            blue = int(20 + y * 0.2)
            pygame.draw.line(surface, (5, 5, blue), (0, y), (self.size, y))

        for y in range(self.size - 15, self.size):
            pygame.draw.line(surface, (240, 240, 255), (0, y), (self.size, y))

        for f in self.flakes:
            x = int(f['x'] + math.sin(self.time + f['y'] * 0.1) * 2)
            y = int(f['y'])
            if 0 <= x < self.size and 0 <= y < self.size:
                brightness = 200 + f['size'] * 18
                pygame.draw.circle(surface, (brightness, brightness, 255), (x, y), f['size'])
            f['y'] += f['speed']
            if f['y'] > self.size:
                f['y'] = random.randint(-20, -5)
                f['x'] = random.randint(0, self.size)
        self.time += 0.05

    def reset(self):
        self.started = False


class Fireplace:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.flames = [[0] * 70 for _ in range(62)]
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True

        surface.fill((20, 10, 5))
        pygame.draw.rect(surface, (60, 30, 20), (20, 50, 88, 78))
        pygame.draw.rect(surface, (10, 5, 0), (30, 60, 68, 60))
        pygame.draw.rect(surface, (80, 40, 25), (15, 45, 98, 8))

        for x in range(68):
            self.flames[59][x] = random.randint(200, 255)
            self.flames[58][x] = random.randint(150, 255)

        for y in range(57, 0, -1):
            for x in range(1, 67):
                avg = (self.flames[y + 1][x - 1] + self.flames[y + 1][x] +
                       self.flames[y + 1][x + 1] + self.flames[y][x]) / 4.08
                self.flames[y][x] = max(0, avg - random.random() * 3)

        for y in range(60):
            for x in range(68):
                h = int(self.flames[y][x])
                if h > 180:
                    color = (255, 200 + min(55, (h - 180) * 2), min(100, h - 180))
                elif h > 120:
                    color = (255, min(200, (h - 60) * 2), 0)
                elif h > 50:
                    color = (min(255, h * 3), min(100, h), 0)
                else:
                    color = (h * 2, 0, 0)
                if h > 30:
                    surface.set_at((30 + x, 60 + y), color)

        for i, c in enumerate([(200, 0, 0), (0, 150, 0), (200, 0, 0)]):
            pygame.draw.rect(surface, c, (25 + i * 35, 30, 12, 18))
            pygame.draw.rect(surface, (255, 255, 255), (25 + i * 35, 30, 12, 4))

    def reset(self):
        self.started = False


# ============== MORE CLASSICS ==============

class PlasmaClassic:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('mid')
            self.started = True
        for y in range(self.size):
            for x in range(self.size):
                v = (math.sin(x/16 + self.time) + math.sin(y/8 + self.time*0.5) +
                     math.sin((x+y)/16 + self.time*0.7) + math.sin(math.sqrt(x*x+y*y)/8 + self.time*0.3)) / 4
                surface.set_at((x, y), hsv_to_rgb((v+1)*180 + self.time*30, 1.0, 0.9))
        self.time += 0.05

    def reset(self):
        self.started = False


class MatrixRain:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.started = False
        self.columns = [{'y': random.randint(-size, 0), 'speed': random.uniform(0.5, 2),
                        'length': random.randint(5, 15)} for _ in range(size)]

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True
        surface.fill((0, 0, 0))
        for x, col in enumerate(self.columns):
            y = int(col['y'])
            for i in range(col['length']):
                py = y - i
                if 0 <= py < self.size:
                    brightness = 255 if i == 0 else int(255 * (1 - i / col['length']))
                    surface.set_at((x, py), (0, brightness, 0) if i else (200, 255, 200))
            col['y'] += col['speed']
            if col['y'] - col['length'] > self.size:
                col['y'] = random.randint(-20, -5)
                col['speed'] = random.uniform(0.5, 2)

    def reset(self):
        self.started = False


class Starfield:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.started = False
        self.stars = [{'x': random.uniform(-1, 1), 'y': random.uniform(-1, 1), 'z': random.uniform(0.1, 1)}
                     for _ in range(100)]

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            self.started = True
        surface.fill((0, 0, 10))
        cx, cy = self.size // 2, self.size // 2
        for s in self.stars:
            s['z'] -= 0.02
            if s['z'] <= 0.01:
                s['x'], s['y'], s['z'] = random.uniform(-1, 1), random.uniform(-1, 1), 1.0
            sx = int(cx + s['x'] / s['z'] * 50)
            sy = int(cy + s['y'] / s['z'] * 50)
            if 0 <= sx < self.size and 0 <= sy < self.size:
                brightness = int(255 * (1 - s['z']))
                sz = max(1, int(3 * (1 - s['z'])))
                pygame.draw.circle(surface, (brightness, brightness, brightness), (sx, sy), sz)

    def reset(self):
        self.started = False


class Tunnel:
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True
        cx, cy = self.size // 2, self.size // 2
        for y in range(self.size):
            for x in range(self.size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy) + 0.1
                angle = math.atan2(dy, dx)
                v = 1.0 / dist * 20 + self.time * 2
                checker = ((int(angle / math.pi * 8) + int(v)) % 2)
                brightness = (0.3 + 0.7 * checker) * min(1, 30 / dist)
                surface.set_at((x, y), hsv_to_rgb((v * 30 + self.time * 50) % 360, 0.8, brightness))
        self.time += 0.05

    def reset(self):
        self.started = False


class WavePattern:
    """Mesmerizing wave interference pattern"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('high')
            self.started = True

        for y in range(self.size):
            for x in range(self.size):
                # Multiple wave sources
                d1 = math.sqrt((x - 30)**2 + (y - 30)**2)
                d2 = math.sqrt((x - 100)**2 + (y - 30)**2)
                d3 = math.sqrt((x - 64)**2 + (y - 100)**2)

                v = (math.sin(d1/8 - self.time*3) +
                     math.sin(d2/10 - self.time*2.5) +
                     math.sin(d3/12 - self.time*2)) / 3

                hue = (v * 60 + self.time * 20 + x + y) % 360
                brightness = (v + 1) / 2
                surface.set_at((x, y), hsv_to_rgb(hue, 0.9, brightness))

        self.time += 0.05

    def reset(self):
        self.started = False


# ============== NEW EFFECTS ==============

class AuroraBorealis:
    """Northern lights with flowing curtains of light"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.curtains = [{'x': random.randint(0, size), 'phase': random.uniform(0, 6.28)}
                        for _ in range(8)]

    def render(self, surface):
        if not self.started:
            self.sound.play('nature')
            self.started = True

        # Dark night sky gradient
        for y in range(self.size):
            darkness = 5 + int(y / self.size * 15)
            pygame.draw.line(surface, (0, darkness // 4, darkness), (0, y), (self.size, y))

        # Stars
        for i in range(30):
            sx = (i * 73 + int(self.time * 3)) % self.size
            sy = (i * 41) % (self.size // 2)
            twinkle = 150 + int(50 * math.sin(self.time * 3 + i))
            surface.set_at((sx, sy), (twinkle, twinkle, twinkle))

        # Aurora curtains
        for curtain in self.curtains:
            for y in range(20, 80):
                # Wave motion
                wave = math.sin(y / 15 + self.time * 2 + curtain['phase']) * 15
                wave += math.sin(y / 8 + self.time * 3) * 5
                x = int(curtain['x'] + wave)

                # Vertical fade
                intensity = 1.0 - abs(y - 50) / 40
                intensity *= 0.5 + 0.5 * math.sin(self.time + curtain['phase'])

                if intensity > 0 and 0 <= x < self.size:
                    # Green to blue gradient
                    hue = 120 + (y - 20) * 1.5 + math.sin(self.time) * 30
                    color = hsv_to_rgb(hue, 0.8, intensity * 0.8)

                    # Glow spread
                    for gx in range(-2, 3):
                        px = x + gx
                        if 0 <= px < self.size:
                            glow = max(0, 1 - abs(gx) / 3)
                            old = surface.get_at((px, y))
                            new = tuple(min(255, int(old[i] + color[i] * glow)) for i in range(3))
                            surface.set_at((px, y), new)

            curtain['x'] += math.sin(self.time * 0.5 + curtain['phase']) * 0.3

        self.time += 0.03

    def reset(self):
        self.started = False


class Kaleidoscope:
    """Rotating kaleidoscope patterns"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def render(self, surface):
        if not self.started:
            self.sound.play('high')
            self.started = True

        cx, cy = self.size // 2, self.size // 2

        for y in range(self.size):
            for x in range(self.size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                angle = math.atan2(dy, dx)

                # Mirror into segments (6-fold symmetry)
                segments = 6
                angle = abs((angle + math.pi) % (2 * math.pi / segments) - math.pi / segments)

                # Rotating pattern
                rot_angle = angle + self.time * 0.5
                pattern = math.sin(dist / 10 + rot_angle * 3 + self.time)
                pattern += math.sin(dist / 5 - self.time * 2)
                pattern /= 2

                # Color based on position and time
                hue = (dist * 3 + self.time * 50 + angle * 60) % 360
                brightness = 0.3 + 0.7 * (pattern + 1) / 2

                surface.set_at((x, y), hsv_to_rgb(hue, 0.9, max(0, brightness)))

        self.time += 0.04

    def reset(self):
        self.started = False


class Fireworks:
    """Exploding fireworks display"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.explosions = []
        self.rockets = []

    def render(self, surface):
        if not self.started:
            self.sound.play('xmas')
            self.started = True

        # Dark sky
        surface.fill((5, 5, 20))

        # Launch new rockets occasionally
        if random.random() < 0.03 and len(self.rockets) < 3:
            self.rockets.append({
                'x': random.randint(20, self.size - 20),
                'y': self.size,
                'target_y': random.randint(20, 60),
                'speed': random.uniform(2, 4),
                'hue': random.randint(0, 360)
            })

        # Update rockets
        new_rockets = []
        for r in self.rockets:
            r['y'] -= r['speed']
            # Draw rocket trail
            pygame.draw.circle(surface, (255, 255, 200), (int(r['x']), int(r['y'])), 2)
            for i in range(5):
                ty = int(r['y'] + i * 3)
                if ty < self.size:
                    brightness = 200 - i * 40
                    surface.set_at((int(r['x']), ty), (brightness, brightness // 2, 0))

            if r['y'] <= r['target_y']:
                # Explode!
                particles = []
                for _ in range(50):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(1, 4)
                    particles.append({
                        'x': r['x'], 'y': r['y'],
                        'vx': math.cos(angle) * speed,
                        'vy': math.sin(angle) * speed,
                        'life': random.uniform(30, 60),
                        'hue': r['hue'] + random.randint(-20, 20)
                    })
                self.explosions.append({'particles': particles, 'age': 0})
            else:
                new_rockets.append(r)
        self.rockets = new_rockets

        # Update explosions
        new_explosions = []
        for exp in self.explosions:
            exp['age'] += 1
            for p in exp['particles']:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['vy'] += 0.08  # Gravity
                p['life'] -= 1

                if p['life'] > 0:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < self.size and 0 <= py < self.size:
                        brightness = p['life'] / 60
                        color = hsv_to_rgb(p['hue'] % 360, 0.9, brightness)
                        surface.set_at((px, py), color)
                        # Glow
                        for gx, gy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            gpx, gpy = px + gx, py + gy
                            if 0 <= gpx < self.size and 0 <= gpy < self.size:
                                gcolor = hsv_to_rgb(p['hue'] % 360, 0.9, brightness * 0.3)
                                old = surface.get_at((gpx, gpy))
                                new = tuple(min(255, old[i] + gcolor[i]) for i in range(3))
                                surface.set_at((gpx, gpy), new)

            if exp['age'] < 80:
                new_explosions.append(exp)
        self.explosions = new_explosions

        self.time += 0.03

    def reset(self):
        self.started = False
        self.explosions = []
        self.rockets = []


class LavaLamp:
    """Groovy lava lamp with floating blobs"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.blobs = [{'x': random.uniform(0.2, 0.8), 'y': random.uniform(0.2, 0.8),
                       'r': random.uniform(0.08, 0.15), 'vx': 0, 'vy': 0,
                       'hue': random.randint(0, 60)} for _ in range(6)]

    def render(self, surface):
        if not self.started:
            self.sound.play('deep')
            self.started = True

        # Background gradient
        for y in range(self.size):
            t = y / self.size
            r = int(40 + t * 20)
            g = int(10 + t * 15)
            b = int(60 + t * 30)
            pygame.draw.line(surface, (r, g, b), (0, y), (self.size, y))

        # Update blobs
        for blob in self.blobs:
            # Slow random movement
            blob['vx'] += (random.random() - 0.5) * 0.002
            blob['vy'] += (random.random() - 0.5) * 0.002 - 0.0003  # Slight upward bias

            # Heat from bottom pushes up
            if blob['y'] > 0.7:
                blob['vy'] -= 0.001
            if blob['y'] < 0.3:
                blob['vy'] += 0.001

            blob['vx'] *= 0.98
            blob['vy'] *= 0.98

            blob['x'] += blob['vx']
            blob['y'] += blob['vy']

            # Bounce off edges
            if blob['x'] < 0.1: blob['x'] = 0.1; blob['vx'] *= -0.5
            if blob['x'] > 0.9: blob['x'] = 0.9; blob['vx'] *= -0.5
            if blob['y'] < 0.1: blob['y'] = 0.1; blob['vy'] *= -0.5
            if blob['y'] > 0.9: blob['y'] = 0.9; blob['vy'] *= -0.5

        # Draw blobs with metaball-like rendering
        for y in range(self.size):
            for x in range(self.size):
                total = 0
                avg_hue = 0
                for blob in self.blobs:
                    bx = blob['x'] * self.size
                    by = blob['y'] * self.size
                    r = blob['r'] * self.size
                    dist = math.sqrt((x - bx)**2 + (y - by)**2)
                    if dist < r * 3:
                        influence = (r * r) / (dist * dist + 0.1)
                        total += influence
                        avg_hue += blob['hue'] * influence

                if total > 0.5:
                    avg_hue /= total
                    brightness = min(1.0, (total - 0.5) * 2)
                    color = hsv_to_rgb((avg_hue + self.time * 10) % 360, 0.9, 0.5 + brightness * 0.5)
                    surface.set_at((x, y), color)

        self.time += 0.02

    def reset(self):
        self.started = False


class GameOfLife:
    """Conway's Game of Life with colorful cells"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.grid = [[0] * size for _ in range(size)]
        self.colors = [[0] * size for _ in range(size)]
        self.generation = 0
        self._randomize()

    def _randomize(self):
        for y in range(self.size):
            for x in range(self.size):
                self.grid[y][x] = 1 if random.random() < 0.3 else 0
                self.colors[y][x] = random.randint(0, 360)

    def render(self, surface):
        if not self.started:
            self.sound.play('digital')
            self.started = True

        surface.fill((10, 10, 20))

        # Update every few frames
        if int(self.time * 10) % 3 == 0:
            new_grid = [[0] * self.size for _ in range(self.size)]
            for y in range(self.size):
                for x in range(self.size):
                    neighbors = 0
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            ny, nx = (y + dy) % self.size, (x + dx) % self.size
                            neighbors += self.grid[ny][nx]

                    if self.grid[y][x]:
                        new_grid[y][x] = 1 if neighbors in (2, 3) else 0
                    else:
                        if neighbors == 3:
                            new_grid[y][x] = 1
                            self.colors[y][x] = (self.colors[y][x] + 30) % 360

            self.grid = new_grid
            self.generation += 1

            # Reset if stagnant
            if self.generation % 200 == 0:
                self._randomize()

        # Draw cells
        for y in range(self.size):
            for x in range(self.size):
                if self.grid[y][x]:
                    color = hsv_to_rgb(self.colors[y][x], 0.8, 0.9)
                    surface.set_at((x, y), color)

        self.time += 0.05

    def reset(self):
        self.started = False
        self._randomize()
        self.generation = 0


class RadarSweep:
    """Radar/sonar scanning effect"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.blips = []

    def render(self, surface):
        if not self.started:
            self.sound.play('digital')
            self.started = True

        # Dark background with green tint
        surface.fill((0, 15, 5))
        cx, cy = self.size // 2, self.size // 2

        # Concentric rings
        for r in range(10, 65, 12):
            pygame.draw.circle(surface, (0, 50, 20), (cx, cy), r, 1)

        # Crosshairs
        pygame.draw.line(surface, (0, 60, 30), (cx, 0), (cx, self.size), 1)
        pygame.draw.line(surface, (0, 60, 30), (0, cy), (self.size, cy), 1)

        # Sweep angle
        sweep_angle = self.time * 2

        # Draw sweep with fade trail
        for i in range(40):
            angle = sweep_angle - i * 0.03
            intensity = 1.0 - i / 40
            for r in range(5, 64):
                x = int(cx + r * math.cos(angle))
                y = int(cy + r * math.sin(angle))
                if 0 <= x < self.size and 0 <= y < self.size:
                    brightness = int(100 * intensity * (1 - r / 64))
                    color = (0, min(255, brightness + 50), brightness // 2)
                    surface.set_at((x, y), color)

        # Bright sweep edge
        for r in range(5, 64):
            x = int(cx + r * math.cos(sweep_angle))
            y = int(cy + r * math.sin(sweep_angle))
            if 0 <= x < self.size and 0 <= y < self.size:
                surface.set_at((x, y), (100, 255, 100))

        # Add random blips
        if random.random() < 0.02:
            dist = random.uniform(15, 55)
            angle = random.uniform(0, 2 * math.pi)
            self.blips.append({
                'x': cx + dist * math.cos(angle),
                'y': cy + dist * math.sin(angle),
                'life': 60
            })

        # Draw blips
        new_blips = []
        for blip in self.blips:
            blip['life'] -= 1
            if blip['life'] > 0:
                brightness = blip['life'] / 60
                px, py = int(blip['x']), int(blip['y'])
                if 0 <= px < self.size and 0 <= py < self.size:
                    color = (0, int(255 * brightness), int(100 * brightness))
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            npx, npy = px + dx, py + dy
                            if 0 <= npx < self.size and 0 <= npy < self.size:
                                surface.set_at((npx, npy), color)
                new_blips.append(blip)
        self.blips = new_blips

        self.time += 0.03

    def reset(self):
        self.started = False
        self.blips = []


class SpiralGalaxy:
    """Spinning spiral galaxy with stars"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        # Pre-generate star positions
        self.stars = []
        for _ in range(300):
            arm = random.randint(0, 2)  # 3 spiral arms
            dist = random.uniform(5, 60)
            spread = random.uniform(-0.3, 0.3)
            base_angle = arm * 2 * math.pi / 3
            self.stars.append({
                'dist': dist,
                'arm_offset': base_angle,
                'spread': spread,
                'brightness': random.uniform(0.3, 1.0),
                'hue': random.randint(180, 280)  # Blue to purple
            })

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            self.started = True

        surface.fill((0, 0, 10))
        cx, cy = self.size // 2, self.size // 2

        # Draw stars in spiral pattern
        for star in self.stars:
            # Spiral formula: angle increases with distance
            angle = star['arm_offset'] + star['dist'] / 15 + self.time * (1 - star['dist'] / 80)
            angle += star['spread']

            x = int(cx + star['dist'] * math.cos(angle))
            y = int(cy + star['dist'] * math.sin(angle))

            if 0 <= x < self.size and 0 <= y < self.size:
                # Twinkle
                twinkle = 0.7 + 0.3 * math.sin(self.time * 5 + star['dist'])
                brightness = star['brightness'] * twinkle

                # Color gradient from center (white/yellow) to edge (blue)
                if star['dist'] < 15:
                    hue = 40  # Yellow core
                    sat = 0.5
                else:
                    hue = star['hue']
                    sat = 0.8

                color = hsv_to_rgb(hue, sat, brightness)
                surface.set_at((x, y), color)

                # Glow for bright stars
                if brightness > 0.7:
                    for gx, gy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        gpx, gpy = x + gx, y + gy
                        if 0 <= gpx < self.size and 0 <= gpy < self.size:
                            glow = hsv_to_rgb(hue, sat * 0.5, brightness * 0.3)
                            old = surface.get_at((gpx, gpy))
                            new = tuple(min(255, old[i] + glow[i]) for i in range(3))
                            surface.set_at((gpx, gpy), new)

        # Bright galactic core
        for r in range(12, 0, -1):
            brightness = (12 - r) / 12
            color = hsv_to_rgb(40, 0.3, brightness)
            pygame.draw.circle(surface, color, (cx, cy), r)

        self.time += 0.02

    def reset(self):
        self.started = False


# ============== ICONIC/RECOGNIZABLE ANIMATIONS ==============

class SpongeBobChristmas:
    """SpongeBob SquarePants Christmas scene - pixel art style"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.bubbles = []

    def draw_spongebob(self, surface, x, y, bob=0):
        """Draw pixel art SpongeBob (simplified)"""
        # Body (yellow sponge) - 16x20 pixels
        body_y = y + int(bob)
        pygame.draw.rect(surface, (255, 255, 0), (x, body_y, 16, 20))

        # Holes in sponge
        for hx, hy in [(2, 3), (8, 5), (4, 12), (11, 9), (6, 17)]:
            pygame.draw.circle(surface, (200, 200, 0), (x + hx, body_y + hy), 2)

        # Face
        # Eyes (big white with blue)
        pygame.draw.circle(surface, (255, 255, 255), (x + 4, body_y + 6), 4)
        pygame.draw.circle(surface, (255, 255, 255), (x + 12, body_y + 6), 4)
        pygame.draw.circle(surface, (100, 180, 255), (x + 4, body_y + 6), 2)
        pygame.draw.circle(surface, (100, 180, 255), (x + 12, body_y + 6), 2)
        pygame.draw.circle(surface, (0, 0, 0), (x + 4, body_y + 6), 1)
        pygame.draw.circle(surface, (0, 0, 0), (x + 12, body_y + 6), 1)

        # Nose
        pygame.draw.circle(surface, (255, 220, 0), (x + 8, body_y + 10), 2)

        # Mouth (big smile with teeth)
        pygame.draw.arc(surface, (0, 0, 0), (x + 2, body_y + 10, 12, 8), 3.14, 6.28, 2)
        pygame.draw.rect(surface, (255, 255, 255), (x + 4, body_y + 13, 8, 3))  # Teeth

        # Pants (brown)
        pygame.draw.rect(surface, (139, 90, 43), (x, body_y + 20, 16, 6))

        # Legs (yellow)
        pygame.draw.rect(surface, (255, 255, 0), (x + 2, body_y + 26, 4, 8))
        pygame.draw.rect(surface, (255, 255, 0), (x + 10, body_y + 26, 4, 8))

        # Shoes (black)
        pygame.draw.rect(surface, (20, 20, 20), (x + 1, body_y + 34, 6, 4))
        pygame.draw.rect(surface, (20, 20, 20), (x + 9, body_y + 34, 6, 4))

        # Christmas hat!
        pygame.draw.polygon(surface, (200, 0, 0), [(x + 8, body_y - 15), (x, body_y), (x + 16, body_y)])
        pygame.draw.rect(surface, (255, 255, 255), (x - 1, body_y - 2, 18, 4))
        pygame.draw.circle(surface, (255, 255, 255), (x + 8, body_y - 15), 3)

    def draw_patrick(self, surface, x, y, bob=0):
        """Draw pixel art Patrick Star (simplified)"""
        body_y = y + int(bob)
        # Body (pink star shape - simplified as triangle)
        pygame.draw.polygon(surface, (255, 150, 180),
                          [(x + 10, body_y), (x, body_y + 30), (x + 20, body_y + 30)])

        # Eyes
        pygame.draw.circle(surface, (255, 255, 255), (x + 6, body_y + 12), 3)
        pygame.draw.circle(surface, (255, 255, 255), (x + 14, body_y + 12), 3)
        pygame.draw.circle(surface, (0, 0, 0), (x + 6, body_y + 12), 1)
        pygame.draw.circle(surface, (0, 0, 0), (x + 14, body_y + 12), 1)

        # Eyebrows (thick)
        pygame.draw.line(surface, (0, 0, 0), (x + 3, body_y + 8), (x + 9, body_y + 9), 2)
        pygame.draw.line(surface, (0, 0, 0), (x + 11, body_y + 9), (x + 17, body_y + 8), 2)

        # Mouth
        pygame.draw.arc(surface, (100, 50, 80), (x + 5, body_y + 16, 10, 8), 3.14, 6.28, 2)

        # Pants (green with flowers)
        pygame.draw.rect(surface, (100, 200, 100), (x + 3, body_y + 25, 14, 8))
        pygame.draw.circle(surface, (200, 100, 200), (x + 6, body_y + 28), 2)
        pygame.draw.circle(surface, (200, 100, 200), (x + 14, body_y + 28), 2)

        # Christmas hat
        pygame.draw.polygon(surface, (0, 180, 0), [(x + 10, body_y - 12), (x + 2, body_y + 2), (x + 18, body_y + 2)])
        pygame.draw.rect(surface, (255, 255, 255), (x + 1, body_y, 18, 3))
        pygame.draw.circle(surface, (255, 255, 255), (x + 10, body_y - 12), 2)

    def draw_christmas_tree(self, surface, x, y):
        """Draw pixel art Christmas tree"""
        # Tree layers (green triangles)
        for i, (w, h) in enumerate([(30, 15), (24, 12), (18, 10), (12, 8)]):
            ty = y + i * 10
            pygame.draw.polygon(surface, (0, 100 + i * 20, 0),
                              [(x, ty), (x - w // 2, ty + h), (x + w // 2, ty + h)])

        # Trunk
        pygame.draw.rect(surface, (100, 60, 30), (x - 4, y + 48, 8, 12))

        # Ornaments
        ornament_colors = [(255, 0, 0), (255, 255, 0), (0, 100, 255), (255, 0, 255)]
        positions = [(x - 8, y + 12), (x + 6, y + 15), (x - 4, y + 25), (x + 8, y + 28),
                    (x, y + 35), (x - 6, y + 40), (x + 5, y + 42)]
        for i, (ox, oy) in enumerate(positions):
            color = ornament_colors[i % len(ornament_colors)]
            pygame.draw.circle(surface, color, (ox, oy), 3)
            # Shine
            pygame.draw.circle(surface, (255, 255, 255), (ox - 1, oy - 1), 1)

        # Star on top
        star_y = y - 5
        pygame.draw.polygon(surface, (255, 255, 0), [
            (x, star_y - 6), (x + 2, star_y - 2), (x + 6, star_y - 2), (x + 3, star_y + 1),
            (x + 5, star_y + 5), (x, star_y + 3), (x - 5, star_y + 5), (x - 3, star_y + 1),
            (x - 6, star_y - 2), (x - 2, star_y - 2)
        ])
        # Star glow
        glow = int(150 + 100 * math.sin(self.time * 5))
        pygame.draw.circle(surface, (glow, glow, 50), (x, star_y), 8)

    def render(self, surface):
        if not self.started:
            self.sound.play('xmas')
            self.started = True

        # Underwater gradient (dark blue to lighter)
        for y in range(self.size):
            t = y / self.size
            r = int(0 + t * 20)
            g = int(50 + t * 50)
            b = int(100 + t * 80)
            pygame.draw.line(surface, (r, g, b), (0, y), (self.size, y))

        # Sandy floor
        pygame.draw.rect(surface, (194, 178, 128), (0, self.size - 20, self.size, 20))
        # Floor details
        for i in range(8):
            pygame.draw.circle(surface, (180, 160, 110), (i * 18 + 5, self.size - 10), 3)

        # Christmas tree in center
        self.draw_christmas_tree(surface, self.size // 2, 20)

        # SpongeBob (left side, bobbing)
        bob1 = math.sin(self.time * 3) * 3
        self.draw_spongebob(surface, 15, 55, bob1)

        # Patrick (right side, bobbing offset)
        bob2 = math.sin(self.time * 3 + 1) * 3
        self.draw_patrick(surface, 93, 58, bob2)

        # Bubbles
        if random.random() < 0.1:
            self.bubbles.append({'x': random.randint(10, self.size - 10), 'y': self.size - 25,
                                'size': random.randint(2, 5), 'speed': random.uniform(0.5, 1.5)})

        new_bubbles = []
        for b in self.bubbles:
            b['y'] -= b['speed']
            b['x'] += math.sin(self.time * 4 + b['y'] * 0.1) * 0.5
            if b['y'] > 0:
                pygame.draw.circle(surface, (150, 200, 255), (int(b['x']), int(b['y'])), b['size'], 1)
                pygame.draw.circle(surface, (200, 230, 255), (int(b['x'] - 1), int(b['y'] - 1)), 1)
                new_bubbles.append(b)
        self.bubbles = new_bubbles[-50:]

        # Snow falling through water (because it's Christmas!)
        for i in range(20):
            sx = (i * 37 + int(self.time * 30)) % self.size
            sy = (i * 23 + int(self.time * 40)) % self.size
            pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 1)

        # "Merry Christmas!" text flashing
        if int(self.time * 2) % 2:
            # Simple pixel text - just draw colored rectangles
            text_y = 5
            colors = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]
            for i in range(4):
                pygame.draw.rect(surface, colors[i], (20 + i * 22, text_y, 18, 3))

        self.time += 0.05

    def reset(self):
        self.started = False
        self.bubbles = []


class MarioRunner:
    """Infinite Mario runner - NES style pixel art"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.mario_y = 90
        self.mario_vy = 0
        self.jumping = False
        self.ground_y = 100
        self.obstacles = []
        self.coins = []
        self.clouds = [{'x': random.randint(0, size), 'y': random.randint(10, 40)} for _ in range(5)]
        self.score = 0
        self.scroll = 0
        self.run_frame = 0

    def draw_mario(self, surface, x, y, frame):
        """Draw NES-style pixel Mario"""
        # Colors
        RED = (255, 0, 0)
        SKIN = (255, 200, 150)
        BROWN = (139, 90, 43)
        BLUE = (0, 0, 255)

        # Head/hat (red cap)
        pygame.draw.rect(surface, RED, (x + 2, y, 10, 3))
        pygame.draw.rect(surface, RED, (x + 1, y + 3, 12, 3))

        # Face
        pygame.draw.rect(surface, SKIN, (x + 1, y + 6, 12, 4))
        pygame.draw.rect(surface, BROWN, (x + 1, y + 6, 3, 3))  # Hair
        pygame.draw.rect(surface, SKIN, (x + 4, y + 6, 4, 5))  # Face
        pygame.draw.circle(surface, (0, 0, 0), (x + 6, y + 7), 1)  # Eye
        pygame.draw.rect(surface, SKIN, (x + 9, y + 8, 3, 3))  # Nose area
        pygame.draw.rect(surface, BROWN, (x + 2, y + 10, 8, 2))  # Mustache

        # Body (red shirt)
        pygame.draw.rect(surface, RED, (x + 1, y + 12, 12, 6))
        # Overalls (blue)
        pygame.draw.rect(surface, BLUE, (x + 3, y + 14, 8, 4))
        pygame.draw.rect(surface, (255, 255, 0), (x + 4, y + 15, 2, 2))  # Button
        pygame.draw.rect(surface, (255, 255, 0), (x + 8, y + 15, 2, 2))  # Button

        # Arms animation
        if frame % 2 == 0:
            pygame.draw.rect(surface, SKIN, (x - 1, y + 12, 3, 4))
            pygame.draw.rect(surface, SKIN, (x + 12, y + 14, 3, 4))
        else:
            pygame.draw.rect(surface, SKIN, (x - 1, y + 14, 3, 4))
            pygame.draw.rect(surface, SKIN, (x + 12, y + 12, 3, 4))

        # Legs animation
        if self.jumping:
            # Both legs forward when jumping
            pygame.draw.rect(surface, BLUE, (x + 2, y + 18, 4, 6))
            pygame.draw.rect(surface, BLUE, (x + 8, y + 18, 4, 6))
            pygame.draw.rect(surface, BROWN, (x + 1, y + 23, 5, 3))
            pygame.draw.rect(surface, BROWN, (x + 8, y + 23, 5, 3))
        else:
            # Running animation
            if frame % 4 < 2:
                pygame.draw.rect(surface, BLUE, (x + 2, y + 18, 4, 5))
                pygame.draw.rect(surface, BLUE, (x + 9, y + 18, 4, 6))
                pygame.draw.rect(surface, BROWN, (x + 1, y + 23, 5, 3))
                pygame.draw.rect(surface, BROWN, (x + 9, y + 23, 5, 3))
            else:
                pygame.draw.rect(surface, BLUE, (x + 2, y + 18, 4, 6))
                pygame.draw.rect(surface, BLUE, (x + 8, y + 18, 4, 5))
                pygame.draw.rect(surface, BROWN, (x + 1, y + 23, 5, 3))
                pygame.draw.rect(surface, BROWN, (x + 8, y + 23, 5, 3))

    def draw_goomba(self, surface, x, y, frame):
        """Draw NES-style Goomba"""
        BROWN = (139, 90, 43)
        TAN = (200, 150, 100)

        # Body
        pygame.draw.ellipse(surface, BROWN, (x, y, 14, 12))
        # Feet
        if frame % 8 < 4:
            pygame.draw.rect(surface, TAN, (x, y + 10, 5, 4))
            pygame.draw.rect(surface, TAN, (x + 9, y + 10, 5, 4))
        else:
            pygame.draw.rect(surface, TAN, (x + 1, y + 10, 5, 4))
            pygame.draw.rect(surface, TAN, (x + 8, y + 10, 5, 4))
        # Eyes (angry)
        pygame.draw.ellipse(surface, (255, 255, 255), (x + 2, y + 2, 4, 5))
        pygame.draw.ellipse(surface, (255, 255, 255), (x + 8, y + 2, 4, 5))
        pygame.draw.circle(surface, (0, 0, 0), (x + 3, y + 4), 1)
        pygame.draw.circle(surface, (0, 0, 0), (x + 10, y + 4), 1)
        # Eyebrows
        pygame.draw.line(surface, (0, 0, 0), (x + 1, y + 1), (x + 5, y + 3), 2)
        pygame.draw.line(surface, (0, 0, 0), (x + 13, y + 1), (x + 9, y + 3), 2)

    def draw_pipe(self, surface, x, y):
        """Draw green pipe"""
        GREEN = (0, 180, 0)
        DARK_GREEN = (0, 120, 0)

        # Pipe top
        pygame.draw.rect(surface, GREEN, (x - 2, y, 20, 8))
        pygame.draw.rect(surface, DARK_GREEN, (x - 2, y, 3, 8))
        # Pipe body
        pygame.draw.rect(surface, GREEN, (x, y + 8, 16, 30))
        pygame.draw.rect(surface, DARK_GREEN, (x, y + 8, 3, 30))
        # Highlight
        pygame.draw.rect(surface, (100, 255, 100), (x + 12, y, 4, 38))

    def draw_coin(self, surface, x, y, frame):
        """Draw spinning coin"""
        # Coin width changes with animation (3D spin effect)
        widths = [8, 6, 2, 6]
        w = widths[frame % 4]
        cx = x + (8 - w) // 2
        pygame.draw.ellipse(surface, (255, 200, 0), (cx, y, w, 12))
        if w > 4:
            pygame.draw.ellipse(surface, (255, 255, 100), (cx + 1, y + 2, w - 2, 8))

    def render(self, surface):
        if not self.started:
            self.sound.play('high')
            self.started = True

        # Sky gradient (NES style blue)
        surface.fill((92, 148, 252))

        # Clouds
        for cloud in self.clouds:
            cx = (int(cloud['x'] - self.scroll * 0.2)) % (self.size + 40) - 20
            cy = cloud['y']
            pygame.draw.ellipse(surface, (255, 255, 255), (cx, cy, 24, 12))
            pygame.draw.ellipse(surface, (255, 255, 255), (cx + 10, cy - 5, 20, 14))
            pygame.draw.ellipse(surface, (255, 255, 255), (cx + 20, cy, 18, 10))

        # Ground blocks (brown brick pattern)
        for bx in range(0, self.size + 16, 16):
            scroll_x = (bx - int(self.scroll) % 16)
            if -16 <= scroll_x < self.size:
                # Brown block
                pygame.draw.rect(surface, (180, 100, 50), (scroll_x, self.ground_y, 16, 28))
                pygame.draw.rect(surface, (100, 60, 30), (scroll_x, self.ground_y, 16, 2))
                pygame.draw.rect(surface, (100, 60, 30), (scroll_x + 7, self.ground_y, 2, 16))

        # Spawn obstacles
        if random.random() < 0.015:
            obs_type = 'pipe' if random.random() < 0.4 else 'goomba'
            self.obstacles.append({'x': self.size + 20, 'type': obs_type})

        # Spawn coins
        if random.random() < 0.02:
            self.coins.append({'x': self.size + 20, 'y': random.randint(50, 80)})

        # Draw and update obstacles
        new_obstacles = []
        for obs in self.obstacles:
            obs['x'] -= 2
            if obs['x'] > -20:
                if obs['type'] == 'pipe':
                    self.draw_pipe(surface, int(obs['x']), self.ground_y - 30)
                else:
                    self.draw_goomba(surface, int(obs['x']), self.ground_y - 14, int(self.time * 10))
                new_obstacles.append(obs)

                # Collision detection
                mario_x = 20
                if obs['type'] == 'goomba':
                    if abs(obs['x'] - mario_x) < 12 and self.mario_y > 70:
                        # Mario jumps on goomba
                        if self.mario_vy > 0:
                            obs['x'] = -100  # Remove goomba
                            self.score += 100
                            self.mario_vy = -6  # Bounce

        self.obstacles = new_obstacles

        # Draw and update coins
        new_coins = []
        for coin in self.coins:
            coin['x'] -= 2
            if coin['x'] > -10:
                self.draw_coin(surface, int(coin['x']), int(coin['y']), int(self.time * 8))
                new_coins.append(coin)

                # Collect coin
                mario_x = 20
                if abs(coin['x'] - mario_x) < 12 and abs(coin['y'] - self.mario_y) < 15:
                    coin['x'] = -100
                    self.score += 10
        self.coins = new_coins

        # Mario physics
        # Auto-jump over obstacles
        for obs in self.obstacles:
            if 30 < obs['x'] < 50 and not self.jumping:
                self.mario_vy = -8
                self.jumping = True

        self.mario_vy += 0.5  # Gravity
        self.mario_y += self.mario_vy

        if self.mario_y >= self.ground_y - 26:
            self.mario_y = self.ground_y - 26
            self.mario_vy = 0
            self.jumping = False

        # Draw Mario
        self.draw_mario(surface, 20, int(self.mario_y), int(self.time * 10))

        # Score display (simple rectangles as numbers would be complex)
        pygame.draw.rect(surface, (255, 255, 255), (5, 5, 40, 8))
        pygame.draw.rect(surface, (0, 0, 0), (6, 6, min(38, self.score // 10), 6))

        # Question blocks floating
        for i in range(3):
            qx = ((i * 50 + 30) - int(self.scroll * 0.5)) % (self.size + 50) - 25
            qy = 60 + int(math.sin(self.time * 3 + i) * 3)
            pygame.draw.rect(surface, (200, 150, 50), (qx, qy, 16, 16))
            pygame.draw.rect(surface, (255, 200, 100), (qx + 2, qy + 2, 12, 12))
            # Question mark
            pygame.draw.rect(surface, (180, 100, 50), (qx + 6, qy + 4, 4, 6))
            pygame.draw.rect(surface, (180, 100, 50), (qx + 6, qy + 11, 4, 2))

        self.scroll += 2
        self.time += 0.05
        self.run_frame += 1

    def reset(self):
        self.started = False
        self.obstacles = []
        self.coins = []
        self.score = 0
        self.scroll = 0
        self.mario_y = 90


class StPetersburgSnow:
    """St. Isaac's Cathedral silhouette with beautiful snowfall"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.snowflakes = [{'x': random.randint(0, size), 'y': random.randint(-size, 0),
                           'size': random.choice([1, 1, 1, 2, 2, 3]),
                           'speed': random.uniform(0.3, 1.0),
                           'drift': random.uniform(-0.3, 0.3)} for _ in range(200)]
        self.lights = [{'x': random.randint(10, size - 10), 'y': random.randint(70, 100),
                       'color': random.choice([(255, 200, 100), (255, 150, 50)])} for _ in range(15)]

    def draw_cathedral(self, surface):
        """Draw St. Isaac's Cathedral silhouette"""
        # Main dome (the famous golden dome)
        cx = self.size // 2
        dome_y = 25

        # Sky glow behind dome
        for r in range(40, 0, -2):
            alpha = int(30 * (40 - r) / 40)
            pygame.draw.circle(surface, (alpha, alpha, alpha + 20), (cx, dome_y + 20), r)

        # Main dome (large)
        pygame.draw.ellipse(surface, (40, 35, 50), (cx - 25, dome_y, 50, 35))
        # Dome lantern on top
        pygame.draw.rect(surface, (40, 35, 50), (cx - 8, dome_y - 10, 16, 15))
        # Cross on very top
        pygame.draw.rect(surface, (60, 55, 70), (cx - 1, dome_y - 20, 2, 12))
        pygame.draw.rect(surface, (60, 55, 70), (cx - 4, dome_y - 17, 8, 2))

        # Colonnade drum under dome
        pygame.draw.rect(surface, (35, 30, 45), (cx - 30, dome_y + 30, 60, 20))
        # Columns on drum (simplified)
        for i in range(8):
            col_x = cx - 28 + i * 8
            pygame.draw.rect(surface, (50, 45, 60), (col_x, dome_y + 30, 3, 20))

        # Main building body
        pygame.draw.rect(surface, (30, 25, 40), (cx - 45, dome_y + 50, 90, 40))

        # Front colonnade (iconic columns)
        for i in range(12):
            col_x = cx - 42 + i * 7
            pygame.draw.rect(surface, (45, 40, 55), (col_x, dome_y + 50, 4, 35))

        # Pediment (triangular top)
        pygame.draw.polygon(surface, (35, 30, 45),
                          [(cx - 45, dome_y + 50), (cx, dome_y + 38), (cx + 45, dome_y + 50)])

        # Side domes (smaller)
        for dx in [-38, 38]:
            pygame.draw.ellipse(surface, (40, 35, 50), (cx + dx - 10, dome_y + 15, 20, 18))
            pygame.draw.rect(surface, (60, 55, 70), (cx + dx - 1, dome_y + 5, 2, 12))
            pygame.draw.rect(surface, (60, 55, 70), (cx + dx - 3, dome_y + 8, 6, 2))

        # Base/steps
        pygame.draw.rect(surface, (25, 22, 35), (cx - 50, dome_y + 90, 100, 10))
        pygame.draw.rect(surface, (22, 20, 32), (cx - 55, dome_y + 100, 110, 6))

        # Windows (golden glow from inside)
        glow = int(150 + 50 * math.sin(self.time * 2))
        for wx in [-30, -15, 0, 15, 30]:
            pygame.draw.rect(surface, (glow, glow - 50, 30), (cx + wx - 3, dome_y + 60, 6, 15))

    def render(self, surface):
        if not self.started:
            self.sound.play('xmas')
            self.started = True

        # Night sky gradient (deep blue to purple)
        for y in range(self.size):
            t = y / self.size
            r = int(10 + t * 15)
            g = int(15 + t * 20)
            b = int(40 + t * 30)
            pygame.draw.line(surface, (r, g, b), (0, y), (self.size, y))

        # Stars
        random.seed(42)  # Fixed stars
        for i in range(40):
            sx = random.randint(0, self.size)
            sy = random.randint(0, 70)
            twinkle = 0.5 + 0.5 * math.sin(self.time * 3 + i * 0.5)
            brightness = int(100 + 100 * twinkle)
            if sy < 60:  # Don't put stars where cathedral will be
                surface.set_at((sx, sy), (brightness, brightness, brightness))
        random.seed()

        # Ground (snow-covered)
        pygame.draw.rect(surface, (220, 225, 235), (0, 115, self.size, 13))

        # Street lamps
        for lamp in self.lights:
            # Lamp post
            pygame.draw.rect(surface, (40, 40, 50), (lamp['x'], lamp['y'], 2, 20))
            # Lamp glow
            glow_r = int(8 + 3 * math.sin(self.time * 4 + lamp['x']))
            for r in range(glow_r, 0, -1):
                alpha = int(lamp['color'][0] * (glow_r - r) / glow_r)
                pygame.draw.circle(surface, (alpha, alpha // 2, alpha // 4),
                                 (lamp['x'] + 1, lamp['y']), r)

        # Cathedral silhouette
        self.draw_cathedral(surface)

        # Snowfall
        for flake in self.snowflakes:
            # Gentle drift
            flake['x'] += math.sin(self.time * 2 + flake['y'] * 0.05) * 0.3 + flake['drift']
            flake['y'] += flake['speed']

            # Reset when off screen
            if flake['y'] > self.size or flake['x'] < -10 or flake['x'] > self.size + 10:
                flake['y'] = random.randint(-20, -5)
                flake['x'] = random.randint(0, self.size)

            # Draw snowflake
            fx, fy = int(flake['x']), int(flake['y'])
            if 0 <= fx < self.size and 0 <= fy < self.size:
                if flake['size'] == 1:
                    surface.set_at((fx, fy), (255, 255, 255))
                elif flake['size'] == 2:
                    pygame.draw.circle(surface, (240, 245, 255), (fx, fy), 1)
                else:
                    pygame.draw.circle(surface, (255, 255, 255), (fx, fy), 2)
                    # Sparkle on big flakes
                    if random.random() < 0.1:
                        pygame.draw.circle(surface, (255, 255, 200), (fx, fy), 1)

        # Fog/mist at ground level
        for i in range(5):
            fog_y = 110 + i
            alpha = 30 - i * 5
            pygame.draw.line(surface, (200 + alpha, 205 + alpha, 215 + alpha),
                           (0, fog_y), (self.size, fog_y))

        self.time += 0.02

    def reset(self):
        self.started = False


class PacManChase:
    """Classic Pac-Man ghost chase animation"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.pacman_x = -20
        self.ghost_colors = [(255, 0, 0), (255, 184, 255), (0, 255, 255), (255, 184, 82)]  # Blinky, Pinky, Inky, Clyde
        self.pellets = [{'x': i * 12 + 6, 'eaten': False} for i in range(12)]
        self.power_mode = False
        self.power_timer = 0

    def draw_pacman(self, surface, x, y, mouth_open):
        """Draw Pac-Man"""
        YELLOW = (255, 255, 0)
        if mouth_open:
            # Open mouth (pie slice)
            pygame.draw.circle(surface, YELLOW, (int(x), int(y)), 10)
            # Cut out mouth
            mouth_angle = int(self.time * 20) % 45
            pygame.draw.polygon(surface, (0, 0, 20), [
                (int(x), int(y)),
                (int(x + 15), int(y - 8)),
                (int(x + 15), int(y + 8))
            ])
        else:
            pygame.draw.circle(surface, YELLOW, (int(x), int(y)), 10)

        # Eye
        pygame.draw.circle(surface, (0, 0, 0), (int(x - 2), int(y - 4)), 2)

    def draw_ghost(self, surface, x, y, color, scared=False):
        """Draw a ghost"""
        if scared:
            color = (0, 0, 200)

        # Ghost body (rounded top)
        pygame.draw.ellipse(surface, color, (int(x) - 10, int(y) - 10, 20, 18))
        pygame.draw.rect(surface, color, (int(x) - 10, int(y), 20, 10))

        # Wavy bottom
        wave_offset = int(self.time * 10) % 2
        for i in range(4):
            wave_y = y + 8 + (wave_offset if i % 2 == 0 else -wave_offset)
            pygame.draw.circle(surface, color, (int(x) - 8 + i * 5, int(wave_y)), 3)

        # Eyes
        if scared:
            # Scared face
            pygame.draw.circle(surface, (255, 255, 255), (int(x) - 4, int(y) - 3), 3)
            pygame.draw.circle(surface, (255, 255, 255), (int(x) + 4, int(y) - 3), 3)
            pygame.draw.arc(surface, (255, 255, 255), (int(x) - 5, int(y) + 2, 10, 5), 0, 3.14, 2)
        else:
            # Normal eyes
            pygame.draw.circle(surface, (255, 255, 255), (int(x) - 4, int(y) - 3), 4)
            pygame.draw.circle(surface, (255, 255, 255), (int(x) + 4, int(y) - 3), 4)
            pygame.draw.circle(surface, (0, 0, 200), (int(x) - 3, int(y) - 3), 2)
            pygame.draw.circle(surface, (0, 0, 200), (int(x) + 5, int(y) - 3), 2)

    def render(self, surface):
        if not self.started:
            self.sound.play('digital')
            self.started = True

        # Maze-like background
        surface.fill((0, 0, 20))

        # Maze walls (simplified)
        WALL_COLOR = (33, 33, 255)
        # Top and bottom walls
        pygame.draw.rect(surface, WALL_COLOR, (0, 20, self.size, 4))
        pygame.draw.rect(surface, WALL_COLOR, (0, self.size - 24, self.size, 4))
        # Side walls
        pygame.draw.rect(surface, WALL_COLOR, (0, 20, 4, self.size - 40))
        pygame.draw.rect(surface, WALL_COLOR, (self.size - 4, 20, 4, self.size - 40))
        # Middle obstacles
        pygame.draw.rect(surface, WALL_COLOR, (30, 45, 25, 20))
        pygame.draw.rect(surface, WALL_COLOR, (73, 45, 25, 20))
        pygame.draw.rect(surface, WALL_COLOR, (30, 85, 25, 20))
        pygame.draw.rect(surface, WALL_COLOR, (73, 85, 25, 20))

        # Pellets
        pellet_y = 64
        for pellet in self.pellets:
            if not pellet['eaten']:
                # Big pellet every 4th
                if pellet['x'] % 48 < 12:
                    pygame.draw.circle(surface, (255, 184, 174), (pellet['x'], pellet_y), 4)
                else:
                    pygame.draw.circle(surface, (255, 184, 174), (pellet['x'], pellet_y), 2)

        # Move Pac-Man
        self.pacman_x += 1.5
        if self.pacman_x > self.size + 30:
            self.pacman_x = -30
            # Reset pellets
            for pellet in self.pellets:
                pellet['eaten'] = False

        # Check pellet eating
        for pellet in self.pellets:
            if not pellet['eaten'] and abs(pellet['x'] - self.pacman_x) < 8:
                pellet['eaten'] = True
                if pellet['x'] % 48 < 12:  # Power pellet
                    self.power_mode = True
                    self.power_timer = 60

        # Power mode timer
        if self.power_mode:
            self.power_timer -= 1
            if self.power_timer <= 0:
                self.power_mode = False

        # Draw Pac-Man
        mouth_frame = int(self.time * 15) % 2
        self.draw_pacman(surface, self.pacman_x, 64, mouth_frame)

        # Draw ghosts chasing (or fleeing if power mode)
        for i, color in enumerate(self.ghost_colors):
            ghost_x = self.pacman_x - 30 - i * 20
            if self.power_mode:
                # Ghosts flee (move left)
                ghost_x = self.pacman_x + 30 + i * 20
            if -20 < ghost_x < self.size + 20:
                self.draw_ghost(surface, ghost_x, 64, color, self.power_mode)

        # Score display
        pygame.draw.rect(surface, (255, 255, 255), (10, 5, 30, 8))

        # "1UP" text area
        pygame.draw.rect(surface, (255, 0, 0), (self.size - 35, 5, 25, 8))

        self.time += 0.05

    def reset(self):
        self.started = False
        self.pacman_x = -20
        self.power_mode = False
        for pellet in self.pellets:
            pellet['eaten'] = False


class NyanCat:
    """Nyan Cat with rainbow trail"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.rainbow_trail = []
        self.stars = [{'x': random.randint(0, size), 'y': random.randint(0, size),
                      'speed': random.uniform(2, 5)} for _ in range(30)]

    def draw_nyan_cat(self, surface, x, y, frame):
        """Draw Nyan Cat (Pop-Tart cat)"""
        # Pop-tart body (pink frosted)
        pygame.draw.rect(surface, (255, 150, 180), (x, y, 24, 18))
        # Sprinkles
        sprinkle_colors = [(255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 200, 255), (255, 0, 255)]
        for i in range(8):
            sx = x + 3 + (i * 3) % 20
            sy = y + 3 + (i * 7) % 14
            pygame.draw.rect(surface, sprinkle_colors[i % 5], (sx, sy, 2, 2))

        # Cat head (gray)
        head_x = x + 20
        pygame.draw.rect(surface, (150, 150, 150), (head_x, y + 2, 12, 12))
        # Ears
        pygame.draw.polygon(surface, (150, 150, 150), [(head_x, y + 2), (head_x + 3, y - 3), (head_x + 5, y + 2)])
        pygame.draw.polygon(surface, (150, 150, 150), [(head_x + 7, y + 2), (head_x + 9, y - 3), (head_x + 12, y + 2)])
        # Pink inner ears
        pygame.draw.polygon(surface, (255, 150, 180), [(head_x + 1, y + 2), (head_x + 3, y - 1), (head_x + 4, y + 2)])
        pygame.draw.polygon(surface, (255, 150, 180), [(head_x + 8, y + 2), (head_x + 9, y - 1), (head_x + 11, y + 2)])
        # Eyes
        pygame.draw.rect(surface, (0, 0, 0), (head_x + 2, y + 5, 3, 3))
        pygame.draw.rect(surface, (0, 0, 0), (head_x + 7, y + 5, 3, 3))
        # Mouth
        pygame.draw.rect(surface, (255, 150, 180), (head_x + 4, y + 9, 4, 2))

        # Legs (animated)
        leg_offset = 2 if frame % 2 == 0 else 0
        pygame.draw.rect(surface, (150, 150, 150), (x + 3, y + 18, 3, 4 + leg_offset))
        pygame.draw.rect(surface, (150, 150, 150), (x + 10, y + 18, 3, 4 - leg_offset + 2))
        pygame.draw.rect(surface, (150, 150, 150), (x + 17, y + 18, 3, 4 + leg_offset))
        # Tail (wavy)
        tail_wave = 2 if frame % 4 < 2 else -2
        pygame.draw.rect(surface, (150, 150, 150), (x - 6, y + 8 + tail_wave, 8, 3))

    def render(self, surface):
        if not self.started:
            self.sound.play('high')
            self.started = True

        # Space background (dark blue)
        surface.fill((10, 15, 40))

        # Moving stars
        for star in self.stars:
            star['x'] -= star['speed']
            if star['x'] < 0:
                star['x'] = self.size
                star['y'] = random.randint(0, self.size)
            pygame.draw.circle(surface, (255, 255, 255), (int(star['x']), int(star['y'])), 1)

        # Cat position (bouncing)
        cat_x = 40
        cat_y = 55 + int(math.sin(self.time * 10) * 5)

        # Add rainbow segment
        self.rainbow_trail.append({'x': cat_x - 4, 'y': cat_y + 9})
        if len(self.rainbow_trail) > 50:
            self.rainbow_trail.pop(0)

        # Draw rainbow trail
        rainbow_colors = [
            (255, 0, 0),      # Red
            (255, 154, 0),    # Orange
            (255, 255, 0),    # Yellow
            (0, 255, 0),      # Green
            (0, 0, 255),      # Blue
            (130, 0, 255)     # Purple
        ]

        for i, segment in enumerate(self.rainbow_trail):
            alpha = i / len(self.rainbow_trail)
            for j, color in enumerate(rainbow_colors):
                ry = segment['y'] - 9 + j * 3
                rx = segment['x'] - (len(self.rainbow_trail) - i) * 2
                if 0 <= rx < self.size and 0 <= ry < self.size:
                    pygame.draw.rect(surface, color, (rx, ry, 3, 3))

        # Draw Nyan Cat
        self.draw_nyan_cat(surface, cat_x, cat_y, int(self.time * 8))

        # Sparkles around cat
        for i in range(3):
            sx = cat_x + random.randint(-10, 40)
            sy = cat_y + random.randint(-10, 30)
            if random.random() < 0.3:
                pygame.draw.circle(surface, (255, 255, 255), (sx, sy), 1)

        self.time += 0.05

    def reset(self):
        self.started = False
        self.rainbow_trail = []


class TetrisFalling:
    """Tetris blocks falling animation"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False
        self.grid = [[None] * 13 for _ in range(16)]  # 13 columns, 16 rows
        self.current_piece = None
        self.piece_x = 0
        self.piece_y = 0
        self.fall_timer = 0

        # Tetris piece definitions (shape, color)
        self.pieces = [
            ([[1, 1, 1, 1]], (0, 255, 255)),         # I - cyan
            ([[1, 1], [1, 1]], (255, 255, 0)),       # O - yellow
            ([[0, 1, 0], [1, 1, 1]], (128, 0, 128)), # T - purple
            ([[1, 0, 0], [1, 1, 1]], (255, 165, 0)), # L - orange
            ([[0, 0, 1], [1, 1, 1]], (0, 0, 255)),   # J - blue
            ([[0, 1, 1], [1, 1, 0]], (0, 255, 0)),   # S - green
            ([[1, 1, 0], [0, 1, 1]], (255, 0, 0)),   # Z - red
        ]

    def spawn_piece(self):
        shape, color = random.choice(self.pieces)
        self.current_piece = {'shape': shape, 'color': color}
        self.piece_x = random.randint(0, 13 - len(shape[0]))
        self.piece_y = 0

    def can_move(self, dx, dy):
        if not self.current_piece:
            return False
        shape = self.current_piece['shape']
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    new_x = self.piece_x + x + dx
                    new_y = self.piece_y + y + dy
                    if new_x < 0 or new_x >= 13 or new_y >= 16:
                        return False
                    if new_y >= 0 and self.grid[new_y][new_x]:
                        return False
        return True

    def lock_piece(self):
        if not self.current_piece:
            return
        shape = self.current_piece['shape']
        color = self.current_piece['color']
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    grid_y = self.piece_y + y
                    grid_x = self.piece_x + x
                    if 0 <= grid_y < 16 and 0 <= grid_x < 13:
                        self.grid[grid_y][grid_x] = color

        # Clear full lines
        new_grid = [row for row in self.grid if any(cell is None for cell in row)]
        lines_cleared = 16 - len(new_grid)
        self.grid = [[None] * 13 for _ in range(lines_cleared)] + new_grid

        self.current_piece = None

    def render(self, surface):
        if not self.started:
            self.sound.play('digital')
            self.started = True

        surface.fill((0, 0, 0))

        cell_size = 8
        offset_x = (self.size - 13 * cell_size) // 2
        offset_y = (self.size - 16 * cell_size) // 2

        # Draw border
        pygame.draw.rect(surface, (100, 100, 100),
                        (offset_x - 2, offset_y - 2, 13 * cell_size + 4, 16 * cell_size + 4), 2)

        # Draw grid
        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                px = offset_x + x * cell_size
                py = offset_y + y * cell_size
                if cell:
                    pygame.draw.rect(surface, cell, (px, py, cell_size - 1, cell_size - 1))
                    # Highlight
                    pygame.draw.line(surface, (255, 255, 255), (px, py), (px + cell_size - 2, py), 1)
                    pygame.draw.line(surface, (255, 255, 255), (px, py), (px, py + cell_size - 2), 1)

        # Spawn new piece if needed
        if not self.current_piece:
            self.spawn_piece()

        # Move piece down
        self.fall_timer += 1
        if self.fall_timer > 8:
            self.fall_timer = 0
            if self.can_move(0, 1):
                self.piece_y += 1
            else:
                self.lock_piece()

        # Draw current piece
        if self.current_piece:
            shape = self.current_piece['shape']
            color = self.current_piece['color']
            for y, row in enumerate(shape):
                for x, cell in enumerate(row):
                    if cell:
                        px = offset_x + (self.piece_x + x) * cell_size
                        py = offset_y + (self.piece_y + y) * cell_size
                        pygame.draw.rect(surface, color, (px, py, cell_size - 1, cell_size - 1))
                        # Highlight
                        pygame.draw.line(surface, (255, 255, 255), (px, py), (px + cell_size - 2, py), 1)
                        pygame.draw.line(surface, (255, 255, 255), (px, py), (px, py + cell_size - 2), 1)

        # Reset if grid is too full
        if any(self.grid[0]):
            self.grid = [[None] * 13 for _ in range(16)]

        self.time += 0.05

    def reset(self):
        self.started = False
        self.grid = [[None] * 13 for _ in range(16)]
        self.current_piece = None


# ============== VIDEO & IMAGE ==============

class VideoPlayer:
    """Play video file using OpenCV with audio via ffmpeg"""
    def __init__(self, size, sound, video_path):
        self.size = size
        self.sound = sound
        self.video_path = video_path
        self.cap = None
        self.audio_process = None
        self.started = False
        self.frame_surface = None
        self.fps = 30
        self.last_frame_time = 0

    def render(self, surface):
        if not self.started:
            if os.path.exists(self.video_path):
                # Start video
                if HAS_CV2:
                    self.cap = cv2.VideoCapture(self.video_path)
                    self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30

                # Start audio playback with ffmpeg
                try:
                    self.audio_process = subprocess.Popen(
                        ['ffplay', '-nodisp', '-autoexit', '-loop', '0',
                         '-af', 'volume=1.5', self.video_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                except:
                    pass
            self.started = True
            self.last_frame_time = time.time()

        if self.cap and self.cap.isOpened():
            # Sync to video FPS
            now = time.time()
            if now - self.last_frame_time >= 1.0 / self.fps:
                ret, frame = self.cap.read()
                if not ret:
                    # Loop video
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()

                if ret:
                    frame = cv2.resize(frame, (self.size, self.size))
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
                self.last_frame_time = now

            if self.frame_surface:
                surface.blit(self.frame_surface, (0, 0))
        else:
            # Fallback if no video
            surface.fill((20, 0, 40))
            cx, cy = self.size // 2, self.size // 2
            pygame.draw.circle(surface, (100, 0, 100), (cx, cy), 30, 3)
            pygame.draw.line(surface, (100, 0, 100), (cx - 10, cy - 15), (cx + 15, cy), 3)
            pygame.draw.line(surface, (100, 0, 100), (cx + 15, cy), (cx - 10, cy + 15), 3)

    def reset(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.audio_process:
            self.audio_process.terminate()
            self.audio_process = None
        self.started = False


class ImageDisplay:
    """Display static image with effects"""
    def __init__(self, size, sound, image_path):
        self.size = size
        self.sound = sound
        self.image_path = image_path
        self.image = None
        self.started = False
        self.time = 0

    def render(self, surface):
        if not self.started:
            self.sound.play('cosmic')
            if os.path.exists(self.image_path):
                try:
                    img = pygame.image.load(self.image_path)
                    self.image = pygame.transform.scale(img, (self.size, self.size))
                except Exception as e:
                    print(f"Image load error: {e}")
            self.started = True

        if self.image:
            # Subtle pulsing effect
            pulse = 0.9 + 0.1 * math.sin(self.time * 2)
            scaled_size = int(self.size * pulse)
            offset = (self.size - scaled_size) // 2

            scaled = pygame.transform.scale(self.image, (scaled_size, scaled_size))
            surface.fill((0, 0, 0))
            surface.blit(scaled, (offset, offset))

            # Sparkle overlay
            for _ in range(5):
                sx = random.randint(0, self.size - 1)
                sy = random.randint(0, self.size - 1)
                brightness = random.randint(150, 255)
                surface.set_at((sx, sy), (brightness, brightness, brightness))
        else:
            # Fallback pattern
            surface.fill((0, 20, 40))
            for i in range(10):
                x = int(64 + 40 * math.cos(self.time + i * 0.6))
                y = int(64 + 40 * math.sin(self.time + i * 0.6))
                pygame.draw.circle(surface, hsv_to_rgb(i * 36, 0.8, 0.8), (x, y), 5)

        self.time += 0.05

    def reset(self):
        self.started = False


def main():
    print("=" * 60)
    print("  VNVNC LED PANEL DEMO - ULTIMATE EDITION")
    print("=" * 60)

    pygame.init()
    pygame.mouse.set_visible(False)

    sound = SoundManager()
    sound.init()

    print(f"Video: {pygame.display.get_driver()}")

    screen = pygame.display.set_mode((HDMI_W, HDMI_H), pygame.FULLSCREEN)
    led = pygame.Surface((LED_SIZE, LED_SIZE))

    effects = [
        # === ICONIC/RECOGNIZABLE ===
        ("🧽 SpongeBob Xmas", SpongeBobChristmas(LED_SIZE, sound)),
        ("🍄 Mario Runner", MarioRunner(LED_SIZE, sound)),
        ("🏛️  St. Petersburg", StPetersburgSnow(LED_SIZE, sound)),
        ("👻 Pac-Man Chase", PacManChase(LED_SIZE, sound)),
        ("🌈 Nyan Cat", NyanCat(LED_SIZE, sound)),
        ("🧱 Tetris", TetrisFalling(LED_SIZE, sound)),
        # === VIDEO & IMAGE ===
        ("🎬 Winter Saga", VideoPlayer(LED_SIZE, sound, "/tmp/saga.mp4")),
        ("🎄 Polar Express", ImageDisplay(LED_SIZE, sound, "/tmp/polarexpress.png")),
        # === VNVNC BRANDING ===
        ("🎮 VNVNC 3D Rotating", VNVNC3DRotating(LED_SIZE, sound)),
        ("🌊 VNVNC Wave", VNVNCWave3D(LED_SIZE, sound)),
        # === STUNNING VISUAL EFFECTS ===
        ("🌀 Plasma Vortex", PlasmaVortex(LED_SIZE, sound)),
        ("📡 Neon Grid", NeonGrid(LED_SIZE, sound)),
        ("⚡ Electric Storm", ElectricStorm(LED_SIZE, sound)),
        ("⚛️  Quantum Field", QuantumField(LED_SIZE, sound)),
        ("🔮 Hypercube 4D", HypercubeProjection(LED_SIZE, sound)),
        ("🧬 DNA Helix", DNAHelix(LED_SIZE, sound)),
        ("🌳 Four Seasons Tree", FractalTree(LED_SIZE, sound)),
        ("🕳️  Black Hole", BlackHole(LED_SIZE, sound)),
        ("🌌 Wave Pattern", WavePattern(LED_SIZE, sound)),
        # === MORE EFFECTS ===
        ("🌌 Aurora Borealis", AuroraBorealis(LED_SIZE, sound)),
        ("🔮 Kaleidoscope", Kaleidoscope(LED_SIZE, sound)),
        ("🎆 Fireworks", Fireworks(LED_SIZE, sound)),
        ("🫧 Lava Lamp", LavaLamp(LED_SIZE, sound)),
        ("🧬 Game of Life", GameOfLife(LED_SIZE, sound)),
        ("📡 Radar Sweep", RadarSweep(LED_SIZE, sound)),
        ("🌀 Spiral Galaxy", SpiralGalaxy(LED_SIZE, sound)),
        # === CHRISTMAS & CLASSIC ===
        ("❄️  Snowfall", Snowfall(LED_SIZE, sound)),
        ("🔥 Fireplace", Fireplace(LED_SIZE, sound)),
        ("💜 Plasma", PlasmaClassic(LED_SIZE, sound)),
        ("💚 Matrix", MatrixRain(LED_SIZE, sound)),
        ("✨ Starfield", Starfield(LED_SIZE, sound)),
        ("🕳️  Tunnel", Tunnel(LED_SIZE, sound)),
    ]

    current = 0
    clock = pygame.time.Clock()
    running = True

    # Long-press tracking for mode switch
    enter_pressed_time = None
    LONG_PRESS_DURATION = 3.0  # seconds to hold for mode switch
    show_hold_indicator = False

    print(f"\n{len(effects)} effects. Press ENTER to switch. HOLD 3s for ARTIFACT mode. ESC to exit.\n")
    print(f"→ {effects[current][0]}")

    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_RIGHT):
                        # Play switch sound and go to next effect
                        sound.play_once('switch')
                        effects[current][1].reset()
                        current = (current + 1) % len(effects)
                        print(f"→ {effects[current][0]}")
                    elif event.key == pygame.K_LEFT:
                        # Play switch sound and go to previous effect
                        sound.play_once('switch')
                        effects[current][1].reset()
                        current = (current - 1) % len(effects)
                        print(f"→ {effects[current][0]}")

            # Each effect loops forever until ENTER pressed
            effects[current][1].render(led)
            screen.fill((0, 0, 0))
            screen.blit(led, (0, 0))
            pygame.display.flip()
            clock.tick(30)

    except KeyboardInterrupt:
        print("\nStopped")

    sound.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
