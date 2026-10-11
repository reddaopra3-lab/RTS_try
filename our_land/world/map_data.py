"""Terrain and resource entities used by the map."""
import pygame

from ..config.settings import COLOR_BRIDGE, COLOR_MOUNTAIN, COLOR_RESOURCE, COLOR_RIVER

class River:
    """简单垂直/水平河流，用矩形表示"""
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def contains(self, px, py):
        return self.rect.collidepoint(px, py)

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_RIVER, self.rect)
        # 简单水波纹
        for i in range(3):
            pygame.draw.line(surface, (70, 140, 220),
                             (self.rect.x, self.rect.y + 10 + i * 12),
                             (self.rect.right, self.rect.y + 10 + i * 12), 1)


class Bridge:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def contains(self, px, py):
        return self.rect.collidepoint(px, py)

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_BRIDGE, self.rect)
        pygame.draw.rect(surface, (100, 70, 40), self.rect, 2)


class Mountain:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)

    def contains(self, px, py):
        return self.rect.collidepoint(px, py)

    def draw(self, surface):
        pygame.draw.rect(surface, COLOR_MOUNTAIN, self.rect)
        # 简单山峰线条
        pygame.draw.polygon(surface, (110, 85, 60), [
            (self.rect.centerx, self.rect.y + 5),
            (self.rect.x + 10, self.rect.bottom - 5),
            (self.rect.right - 10, self.rect.bottom - 5)
        ])


class ResourceNode:
    def __init__(self, x, y, amount=900):
        self.x, self.y = float(x), float(y)
        self.amount = amount
        self.radius = 17

    def draw(self, surface):
        if self.amount <= 0:
            return
        pygame.draw.circle(surface, COLOR_RESOURCE, (int(self.x), int(self.y)), self.radius)
        if self.amount < 250:
            pygame.draw.circle(surface, (160, 90, 20), (int(self.x), int(self.y)), self.radius, 2)
