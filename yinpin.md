import array
import math
import pygame
from typing import Dict

class AudioSynthesizer:
    """波形合成与音频播放服务类"""
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.sounds: Dict[str, pygame.mixer.Sound] = {}

    def generate_sound(self, freq: float = 440.0, duration: float = 0.08, volume: float = 0.3, wave: str = "square") -> pygame.mixer.Sound:
        n_samples = int(self.sample_rate * duration)
        buf = array.array("h")
        for i in range(n_samples):
            t = i / self.sample_rate
            if wave == "square":
                val = 32767 if (int(t * freq) % 2 == 0) else -32767
            else:
                val = int(32767 * math.sin(2 * math.pi * freq * t))
            env = 1.0 - (i / n_samples)
            buf.append(int(val * volume * env))
        return pygame.mixer.Sound(buffer=buf)

    def init_preset_sfx(self) -> None:
        self.sounds["click"] = self.generate_sound(600, 0.04, 0.2)
        self.sounds["train"] = self.generate_sound(300, 0.12, 0.25, "sine")
        self.sounds["build"] = self.generate_sound(180, 0.2, 0.3, "sine")
        self.sounds["hit"] = self.generate_sound(120, 0.06, 0.15)
        self.sounds["error"] = self.generate_sound(100, 0.1, 0.2)

    def play(self, name: str) -> None:
        if name in self.sounds:
            self.sounds[name].play()