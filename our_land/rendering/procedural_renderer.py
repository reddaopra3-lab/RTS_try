"""Pygame drawing helpers for units and buildings."""
import math

import pygame

from ..config.settings import (
    COLOR_ARMOR, COLOR_ENEMY, COLOR_HP, COLOR_HP_BG, COLOR_PLAYER,
    COLOR_PROGRESS, COLOR_RESOURCE, COLOR_SELECTION, COLOR_TOWER,
)

def _rot(cx, cy, pts, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def draw_excavator(surface, x, y, ang, color, carry=False):
    dark = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
    gold = (196, 163, 90)
    pygame.draw.polygon(surface, dark, _rot(x, y, [(-11, -8), (11, -8), (11, 8), (-11, 8)], ang))
    pygame.draw.polygon(surface, color, _rot(x, y, [(-7, -6), (6, -6), (6, 6), (-7, 6)], ang))
    pygame.draw.polygon(surface, (200, 220, 230), _rot(x, y, [(-3, -5), (4, -5), (4, 1), (-3, 1)], ang))
    boom = _rot(x, y, [(6, 0), (18, -2), (18, 2)], ang)
    pygame.draw.polygon(surface, gold, boom)
    bucket = _rot(x, y, [(16, -5), (22, -6), (22, 5), (16, 4)], ang)
    pygame.draw.polygon(surface, gold, bucket)
    if carry:
        pygame.draw.circle(surface, COLOR_RESOURCE, (int(x), int(y - 10)), 4)


def draw_tank(surface, x, y, body_ang, turret_ang, color):
    dark = (max(0, color[0] - 55), max(0, color[1] - 55), max(0, color[2] - 55))
    pygame.draw.polygon(surface, dark, _rot(x, y, [(-14, -10), (14, -10), (14, 10), (-14, 10)], body_ang))
    pygame.draw.polygon(surface, color, _rot(x, y, [(-10, -7), (11, -7), (11, 7), (-10, 7)], body_ang))
    pygame.draw.circle(surface, dark, (int(x), int(y)), 6)
    barrel = _rot(x, y, [(4, -2), (20, -2), (20, 2), (4, 2)], turret_ang)
    pygame.draw.polygon(surface, (210, 205, 180), barrel)


def draw_hq(surface, x, y, size, color, finished):
    s = size / 2
    rect = pygame.Rect(x - s, y - s, size, size)
    pygame.draw.rect(surface, color, rect)
    pygame.draw.rect(surface, (40, 50, 40), rect.inflate(-10, -18))
    pygame.draw.rect(surface, (180, 200, 210), (x - 8, y - 10, 16, 10))
    pygame.draw.rect(surface, (200, 200, 200), rect, 3)
    pygame.draw.polygon(surface, color, [(x + s - 6, y - s), (x + s + 4, y - s - 14), (x + s + 4, y - s)])
    pygame.draw.rect(surface, color, (x + s + 2, y - s - 18, 10, 7))
    if not finished:
        pygame.draw.rect(surface, (80, 80, 80), rect, 0)


def draw_armor_factory(surface, x, y, size, color, finished):
    s = size / 2
    rect = pygame.Rect(x - s, y - s, size, size)
    pygame.draw.rect(surface, color, rect)
    pygame.draw.rect(surface, (30, 30, 28), (x - 10, y - 4, 20, 18))
    pygame.draw.rect(surface, (196, 163, 90), (x - s, y - s - 6, size, 8))
    pygame.draw.rect(surface, (196, 163, 90), (x - 2, y - s - 16, 4, 16))
    pygame.draw.rect(surface, (200, 200, 200), rect, 3)
    draw_tank(surface, x, y + 6, 0, 0, (180, 180, 170))
    if not finished:
        pygame.draw.rect(surface, (60, 60, 60), rect)


def draw_tower(surface, x, y, size, color, aim, finished):
    s = size / 2
    pygame.draw.polygon(surface, (70, 70, 65), [
        (x - s, y + s * 0.3), (x - s * 0.5, y - s), (x + s * 0.5, y - s), (x + s, y + s * 0.3),
        (x + s * 0.6, y + s), (x - s * 0.6, y + s),
    ])
    pygame.draw.circle(surface, color, (int(x), int(y)), int(s * 0.55))
    pygame.draw.circle(surface, (30, 30, 28), (int(x), int(y)), int(s * 0.28))
    barrel = _rot(x, y, [(4, -3), (s + 8, -3), (s + 8, 3), (4, 3)], aim)
    pygame.draw.polygon(surface, (220, 210, 160), barrel)
    pygame.draw.circle(surface, COLOR_TOWER, (int(x), int(y)), 4)
    if not finished:
        pygame.draw.circle(surface, (80, 80, 80), (int(x), int(y)), int(s), 2)
