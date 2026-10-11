"""Procedurally generated game sound effects."""
import array
import math

import pygame

def make_sound(freq=440, duration=0.08, volume=0.3, wave="square"):
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    buf = array.array("h")
    for i in range(n_samples):
        t = i / sample_rate
        if wave == "square":
            val = 32767 if (int(t * freq) % 2 == 0) else -32767
        else:
            val = int(32767 * math.sin(2 * math.pi * freq * t))
        env = 1.0 - (i / n_samples)
        buf.append(int(val * volume * env))
    return pygame.mixer.Sound(buffer=buf)
