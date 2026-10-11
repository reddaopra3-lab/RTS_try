"""Polygon terrain and resource entities used by the map."""
import math

import pygame

from ..config.settings import COLOR_BRIDGE, COLOR_MOUNTAIN, COLOR_RESOURCE, COLOR_RIVER


def rectangle_points(x, y, width, height):
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def point_in_polygon(x, y, points):
    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = current
        x2, y2 = previous
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def distance_to_segment(x, y, start, end):
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if not length_squared:
        return math.hypot(x - start[0], y - start[1])
    fraction = max(0.0, min(1.0, ((x - start[0]) * dx + (y - start[1]) * dy) / length_squared))
    nearest_x = start[0] + fraction * dx
    nearest_y = start[1] + fraction * dy
    return math.hypot(x - nearest_x, y - nearest_y)


class PolygonTerrain:
    """Arbitrary polygon with rectangle-compatible loading for older maps."""
    color = (255, 255, 255)

    def __init__(self, x=0, y=0, w=None, h=None, points=None):
        if points is None:
            if w is None or h is None:
                raise ValueError("地形必须提供多边形顶点或矩形尺寸")
            points = rectangle_points(x, y, w, h)
        if len(points) < 3:
            raise ValueError("地形多边形至少需要三个顶点")
        self.points = [(float(px), float(py)) for px, py in points]
        self.rect = pygame.Rect(
            min(point[0] for point in self.points),
            min(point[1] for point in self.points),
            max(point[0] for point in self.points) - min(point[0] for point in self.points),
            max(point[1] for point in self.points) - min(point[1] for point in self.points),
        )

    def contains(self, px, py):
        return point_in_polygon(px, py, self.points)

    def intersects_circle(self, px, py, radius):
        if self.contains(px, py):
            return True
        return any(
            distance_to_segment(px, py, self.points[index - 1], point) < radius
            for index, point in enumerate(self.points)
        )

    def contains_circle(self, px, py, radius):
        return self.contains(px, py) and all(
            distance_to_segment(px, py, self.points[index - 1], point) >= radius
            for index, point in enumerate(self.points)
        )

    def draw(self, surface, offset=(0, 0)):
        points = [(round(x - offset[0]), round(y - offset[1])) for x, y in self.points]
        pygame.draw.polygon(surface, self.color, points)


class River(PolygonTerrain):
    """Impassable freeform water polygon."""
    color = COLOR_RIVER

    def draw(self, surface, offset=(0, 0)):
        super().draw(surface, offset)
        points = [(round(x - offset[0]), round(y - offset[1])) for x, y in self.points]
        old_clip = surface.get_clip()
        bounds = pygame.Rect(
            round(self.rect.left - offset[0]),
            round(self.rect.top - offset[1]),
            round(self.rect.width),
            round(self.rect.height),
        )
        surface.set_clip(bounds.clip(old_clip))
        for y in range(bounds.top + 10, bounds.bottom, 24):
            pygame.draw.line(surface, (70, 140, 220), (bounds.left, y), (bounds.right, y), 1)
        surface.set_clip(old_clip)
        pygame.draw.polygon(surface, (65, 135, 210), points, 2)


class Bridge(PolygonTerrain):
    """Walkable freeform bridge polygon."""

    def draw(self, surface, offset=(0, 0)):
        points = [(round(x - offset[0]), round(y - offset[1])) for x, y in self.points]
        pygame.draw.polygon(surface, COLOR_BRIDGE, points)
        pygame.draw.polygon(surface, (100, 70, 40), points, 3)


class Mountain(PolygonTerrain):
    """Terrain slowdown area, drawn and edited as a freeform polygon."""
    color = COLOR_MOUNTAIN

    def draw(self, surface, offset=(0, 0)):
        points = [(round(x - offset[0]), round(y - offset[1])) for x, y in self.points]
        pygame.draw.polygon(surface, self.color, points)
        center_x = sum(x for x, _ in points) // len(points)
        center_y = sum(y for _, y in points) // len(points)
        peak = (center_x, center_y - max(6, self.rect.height // 4))
        pygame.draw.polygon(surface, (110, 85, 60), [
            peak,
            (self.rect.left - offset[0] + 8, self.rect.bottom - offset[1] - 6),
            (self.rect.right - offset[0] - 8, self.rect.bottom - offset[1] - 6),
        ])


class ResourceNode:
    def __init__(self, x, y, amount=900):
        self.x, self.y = float(x), float(y)
        self.amount = amount
        self.radius = 17

    def draw(self, surface, offset=(0, 0)):
        if self.amount <= 0:
            return
        position = (round(self.x - offset[0]), round(self.y - offset[1]))
        pygame.draw.circle(surface, COLOR_RESOURCE, position, self.radius)
        if self.amount < 250:
            pygame.draw.circle(surface, (160, 90, 20), position, self.radius, 2)
