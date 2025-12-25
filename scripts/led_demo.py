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
    """Growing fractal tree"""
    def __init__(self, size, sound):
        self.size = size
        self.sound = sound
        self.time = 0
        self.started = False

    def draw_branch(self, surface, x, y, angle, length, depth, max_depth):
        if depth > max_depth or length < 2:
            return

        # Calculate end point
        end_x = x + math.cos(angle) * length
        end_y = y - math.sin(angle) * length

        # Color based on depth
        hue = (depth * 30 + self.time * 20) % 360
        thickness = max(1, (max_depth - depth) // 2)
        color = hsv_to_rgb(hue, 0.7, 0.9 - depth * 0.05)

        pygame.draw.line(surface, color, (int(x), int(y)), (int(end_x), int(end_y)), thickness)

        # Branch angle variation
        sway = math.sin(self.time * 2 + depth) * 0.1

        # Draw sub-branches
        self.draw_branch(surface, end_x, end_y, angle + 0.5 + sway, length * 0.7, depth + 1, max_depth)
        self.draw_branch(surface, end_x, end_y, angle - 0.4 + sway, length * 0.7, depth + 1, max_depth)

    def render(self, surface):
        if not self.started:
            self.sound.play('mid')
            self.started = True

        surface.fill((5, 10, 15))

        # Ground
        pygame.draw.rect(surface, (30, 20, 10), (0, self.size - 10, self.size, 10))

        # Draw tree from bottom center
        depth = 6 + int(math.sin(self.time * 0.5) * 2)
        self.draw_branch(surface, self.size // 2, self.size - 10, math.pi / 2, 25, 0, depth)

        self.time += 0.03

    def reset(self):
        self.started = False


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
        ("🎬 Winter Saga", VideoPlayer(LED_SIZE, sound, "/tmp/saga.mp4")),
        ("🎄 Polar Express", ImageDisplay(LED_SIZE, sound, "/tmp/polarexpress.png")),
        ("🎮 VNVNC 3D Rotating", VNVNC3DRotating(LED_SIZE, sound)),
        ("🌊 VNVNC Wave", VNVNCWave3D(LED_SIZE, sound)),
        ("🌀 Plasma Vortex", PlasmaVortex(LED_SIZE, sound)),
        ("📡 Neon Grid", NeonGrid(LED_SIZE, sound)),
        ("⚡ Electric Storm", ElectricStorm(LED_SIZE, sound)),
        ("⚛️  Quantum Field", QuantumField(LED_SIZE, sound)),
        ("🔮 Hypercube 4D", HypercubeProjection(LED_SIZE, sound)),
        ("🧬 DNA Helix", DNAHelix(LED_SIZE, sound)),
        ("🌳 Fractal Tree", FractalTree(LED_SIZE, sound)),
        ("🕳️  Black Hole", BlackHole(LED_SIZE, sound)),
        ("🌌 Wave Pattern", WavePattern(LED_SIZE, sound)),
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

    print(f"\n{len(effects)} effects. Press ENTER to switch. ESC to exit.\n")
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
