"""Base, armor factory, and defense tower models."""
import pygame

from ..config.balance import BUILD_HP, BUILD_SIZE
from ..config.settings import (
    COLOR_ARMOR, COLOR_BUILD, COLOR_ENEMY, COLOR_HP, COLOR_HP_BG, COLOR_PLAYER,
    COLOR_PROGRESS, COLOR_SELECTION, COLOR_TOWER,
)
from ..rendering.procedural_renderer import draw_armor_factory, draw_hq, draw_tower
from ..systems.combat import fire_tower
from ..systems.economy import queue_unit, update_production

class Building:
    def __init__(self, x, y, team="player", b_type="base", finished=True):
        self.x, self.y = float(x), float(y)
        self.team = team
        self.b_type = b_type
        self.size = BUILD_SIZE.get(b_type, 48)
        self.max_hp = BUILD_HP.get(b_type, 500)
        self.hp = self.max_hp if finished else 1
        self.selected = False
        self.finished = finished
        self.build_progress = 0 if not finished else 100
        self.defense_bonus = 1.0
        self.aim = 0.0
        self.attack_power = 20.0 if b_type == "tower" else 0.0
        self.attack_range = 220 if b_type == "tower" else 0
        self.production_queue = []
        self.production_progress = 0.0
        self.production_current = None

    def queued_count(self):
        return len(self.production_queue) + (1 if self.production_current else 0)

    def can_produce(self, unit_type):
        return self.finished and self.hp > 0 and (
            (self.b_type == "base" and unit_type == "worker")
            or (self.b_type == "armor" and unit_type == "soldier")
        )

    def queue_unit(self, unit_type, game, count=1):
        return queue_unit(self, unit_type, game, count)

    def update_production(self, game):
        update_production(self, game)

    def finish_build(self):
        self.finished = True
        self.hp = self.max_hp
        self.build_progress = 100

    def fire(self, game):
        fire_tower(self, game)

    def draw(self, surface):
        if self.b_type == "base":
            color = COLOR_PLAYER if self.team == "player" else COLOR_ENEMY
        elif self.b_type == "tower":
            color = COLOR_TOWER if self.team == "player" else (180, 90, 50)
        else:
            color = COLOR_ARMOR if self.team == "player" else (180, 80, 80)
        if not self.finished:
            color = (color[0] // 2, color[1] // 2, color[2] // 2)

        if self.b_type == "base":
            draw_hq(surface, self.x, self.y, self.size, color, self.finished)
        elif self.b_type == "armor":
            draw_armor_factory(surface, self.x, self.y, self.size, color, self.finished)
        else:
            draw_tower(surface, self.x, self.y, self.size, color, self.aim, self.finished)

        rect = pygame.Rect(self.x - self.size / 2, self.y - self.size / 2, self.size, self.size)
        if self.selected:
            pygame.draw.rect(surface, COLOR_SELECTION, rect.inflate(14, 14), 2)

        if not self.finished:
            bar_w = self.size
            pygame.draw.rect(surface, (40, 40, 40), (self.x - bar_w / 2, self.y + self.size / 2 + 6, bar_w, 6))
            pygame.draw.rect(surface, COLOR_PROGRESS, (self.x - bar_w / 2, self.y + self.size / 2 + 6, bar_w * self.build_progress / 100, 6))

        if self.finished and self.hp < self.max_hp:
            bar_w = self.size
            pygame.draw.rect(surface, COLOR_HP_BG, (self.x - bar_w / 2, self.y - self.size / 2 - 10, bar_w, 5))
            pygame.draw.rect(surface, COLOR_HP, (self.x - bar_w / 2, self.y - self.size / 2 - 10, bar_w * max(0, self.hp) / self.max_hp, 5))
