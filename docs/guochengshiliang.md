import math
import pygame
from typing import List, Tuple
from steel_river.config.settings import COLOR_RESOURCE

def rotate_points(cx: float, cy: float, pts: List[Tuple[float, float]], ang: float) -> List[Tuple[float, float]]:
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]

class ProceduralRenderer:
    """视图管线：负责过程化矢量单位图形绘制"""
    @staticmethod
    def draw_excavator(surface: pygame.Surface, x: float, y: float, ang: float, color: Tuple[int, int, int], carry: bool = False) -> None:
        dark = (max(0, color[0] - 50), max(0, color[1] - 50), max(0, color[2] - 50))
        gold = (196, 163, 90)
        
        pygame.draw.polygon(surface, dark, rotate_points(x, y, [(-11, -8), (11, -8), (11, 8), (-11, 8)], ang))
        pygame.draw.polygon(surface, color, rotate_points(x, y, [(-7, -6), (6, -6), (6, 6), (-7, 6)], ang))
        pygame.draw.polygon(surface, (200, 220, 230), rotate_points(x, y, [(-3, -5), (4, -5), (4, 1), (-3, 1)], ang))
        
        boom = rotate_points(x, y, [(6, 0), (18, -2), (18, 2)], ang)
        pygame.draw.polygon(surface, gold, boom)
        
        bucket = rotate_points(x, y, [(16, -5), (22, -6), (22, 5), (16, 4)], ang)
        pygame.draw.polygon(surface, gold, bucket)
        
        if carry:
            pygame.draw.circle(surface, COLOR_RESOURCE, (int(x), int(y - 10)), 4)

    @staticmethod
    def draw_tank(surface: pygame.Surface, x: float, y: float, body_ang: float, turret_ang: float, color: Tuple[int, int, int]) -> None:
        dark = (max(0, color[0] - 55), max(0, color[1] - 55), max(0, color[2] - 55))
        pygame.draw.polygon(surface, dark, rotate_points(x, y, [(-14, -10), (14, -10), (14, 10), (-14, 10)], body_ang))
        pygame.draw.polygon(surface, color, rotate_points(x, y, [(-10, -7), (11, -7), (11, 7), (-10, 7)], body_ang))
        pygame.draw.circle(surface, dark, (int(x), int(y)), 6)
        
        barrel = rotate_points(x, y, [(4, -2), (20, -2), (20, 2), (4, 2)], turret_ang)
        pygame.draw.polygon(surface, (210, 205, 180), barrel)