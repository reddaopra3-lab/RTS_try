"""Unit state, movement orders, and update logic."""
import math

import pygame

from ..config.settings import COLOR_ENEMY, COLOR_HP, COLOR_HP_BG, COLOR_PLAYER, COLOR_SELECTION
from ..rendering.procedural_renderer import draw_excavator, draw_tank
from ..systems.combat import attack_nearest
from ..systems.economy import update_worker_task

class Unit:
    def __init__(self, x, y, team="player", unit_type="worker"):
        self.x, self.y = float(x), float(y)
        self.target_x, self.target_y = self.x, self.y
        self.team = team
        self.unit_type = unit_type
        self.base_speed = 2.6 if unit_type == "worker" else 2.0
        self.speed = self.base_speed
        self.hp = 50 if unit_type == "worker" else 100
        self.max_hp = self.hp
        self.attack_power = 2.0 if unit_type == "worker" else 8.5
        self.attack_range = 160 if unit_type == "soldier" else 28
        self.selected = False
        self.radius = 11 if unit_type == "worker" else 13
        self.defense_bonus = 1.0          # 山地会降低受到的伤害
        self.facing = 0.0
        self.turret = 0.0


        self.state = "idle"
        self.carry = 0
        self.carry_max = 12
        self.gather_target = None
        self.return_base = None
        self.build_target = None
        self.repair_target = None
        self.path = []

    def set_move(self, x, y, game):
        self.state = "move"
        self.gather_target = None
        self.build_target = None
        self.repair_target = None
        self.path = game.find_path(self.x, self.y, x, y, self.radius)
        if self.path:
            self.target_x, self.target_y = self.path[-1]
        else:
            self.target_x, self.target_y = self.x, self.y
            self.state = "idle"

    def set_gather(self, node, game):
        if self.unit_type != "worker":
            return
        self.gather_target = node
        self.state = "gather"
        self.build_target = None
        self.repair_target = None
        self.path = game.find_path(self.x, self.y, node.x, node.y, self.radius)
        if self.path:
            self.target_x, self.target_y = self.path[-1]
        else:
            self.target_x, self.target_y = self.x, self.y
            self.state = "idle"
            self.gather_target = None

    def set_build(self, building, game):
        if self.unit_type != "worker":
            return
        self.build_target = building
        self.repair_target = None
        self.state = "build"
        self.gather_target = None
        self.path = game.find_path_to_building(self.x, self.y, building, self.radius)
        if self.path:
            self.target_x, self.target_y = self.path[-1]
        else:
            self.target_x, self.target_y = self.x, self.y
            self.state = "idle"
            self.build_target = None

    def set_repair(self, building, game):
        if self.unit_type != "worker" or building.team != self.team or not building.finished:
            return
        self.repair_target = building
        self.build_target = None
        self.gather_target = None
        self.return_base = None
        self.state = "repair"
        self.path = game.find_path_to_building(self.x, self.y, building, self.radius)
        if self.path:
            self.target_x, self.target_y = self.path[-1]
        else:
            self.target_x, self.target_y = self.x, self.y
            self.state = "idle"
            self.repair_target = None

    def update_terrain(self, game):
        """根据当前地形调整速度和防御"""
        on_mountain = any(m.contains(self.x, self.y) for m in game.mountains)
        if on_mountain:
            self.speed = self.base_speed * 0.55
            self.defense_bonus = 0.65          # 受到伤害减少
        else:
            self.speed = self.base_speed
            self.defense_bonus = 1.0

    def update(self, game):
        self.update_terrain(game)

        # 沿路径移动
        if self.path:
            next_pt = self.path[0]
            dx = next_pt[0] - self.x
            dy = next_pt[1] - self.y
            dist = math.hypot(dx, dy)
            if dist <= self.speed:
                if game.is_blocked(next_pt[0], next_pt[1], self.radius):
                    self.path = game.find_path(
                        self.x, self.y, self.target_x, self.target_y, self.radius
                    )
                    if self.path:
                        self.target_x, self.target_y = self.path[-1]
                    else:
                        self.state = "idle"
                        self.gather_target = None
                        self.build_target = None
                        self.repair_target = None
                        self.return_base = None
                else:
                    self.x, self.y = next_pt
                    self.path.pop(0)
            elif dist > 0:
                self.facing = math.atan2(dy, dx)
                next_x = self.x + (dx / dist) * self.speed

                next_y = self.y + (dy / dist) * self.speed
                if game.is_blocked(next_x, next_y, self.radius):
                    self.path = game.find_path(
                        self.x, self.y, self.target_x, self.target_y, self.radius
                    )
                    if self.path:
                        self.target_x, self.target_y = self.path[-1]
                    else:
                        self.state = "idle"
                        self.gather_target = None
                        self.build_target = None
                        self.repair_target = None
                        self.return_base = None
                else:
                    self.x, self.y = next_x, next_y
        else:
            update_worker_task(self, game)

        # 攻击
        if self.unit_type == "soldier" or self.state == "idle":
            attack_nearest(self, game)


    def _go_return(self, game):
        bases = [b for b in game.buildings if b.team == self.team and b.finished and b.b_type == "base"]
        if bases:
            self.return_base = min(bases, key=lambda b: math.hypot(b.x - self.x, b.y - self.y))
            self.target_x = self.return_base.x
            self.state = "return"
            self.path = game.find_path_to_building(
                self.x, self.y, self.return_base, self.radius
            )
            if self.path:
                self.target_x, self.target_y = self.path[-1]
            else:
                self.target_x, self.target_y = self.x, self.y
                self.state = "idle"
                self.return_base = None
        else:
            self.state = "idle"

    def draw(self, surface, offset=(0, 0)):
        color = COLOR_PLAYER if self.team == "player" else COLOR_ENEMY
        screen_x = self.x - offset[0]
        screen_y = self.y - offset[1]
        if self.unit_type == "worker":
            draw_excavator(surface, screen_x, screen_y, self.facing, color, self.carry > 0)
        else:
            draw_tank(surface, screen_x, screen_y, self.facing, self.turret, color)

        if self.selected:
            pygame.draw.circle(surface, COLOR_SELECTION, (int(screen_x), int(screen_y)), self.radius + 6, 2)

        if self.hp < self.max_hp:
            bar_w = 24
            pygame.draw.rect(surface, COLOR_HP_BG, (screen_x - bar_w / 2, screen_y - self.radius - 11, bar_w, 4))
            pygame.draw.rect(surface, COLOR_HP, (screen_x - bar_w / 2, screen_y - self.radius - 11, bar_w * max(0, self.hp) / self.max_hp, 4))
