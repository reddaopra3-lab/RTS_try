"""
钢河前线  —  本地 RTS（pygame）

安装（你是 Python 3.14，不要装 pygame，装社区版）：
    pip install pygame-ce

运行（在本文件所在目录）：
    python Attack.py


操作：
    左键框选    右键移动 / 采矿 / 续建
    左键选中建筑 → 打开生产界面；生产队列支持 ×1 / ×5 / ×10
    选中挖掘机后左键友方建筑 → 维修建筑
    选中基地 W  加入挖掘机生产队列（50）
    选中装甲工厂 S  加入坦克生产队列（80）
    B 建基地（兼拖拉机厂，出挖掘机+交矿）
    A 建装甲工厂
    T 建防御塔（不能移动，比坦克更耐打、伤害更高、更便宜）
    ESC 取消建造    R 结束后重开
"""
import math
import random
import sys
import array
import heapq
import pygame

# ==================== 配置 ====================
WIDTH, HEIGHT = 1200, 780
FPS = 60
MINIMAP_SIZE = 180
MINIMAP_MARGIN = 15

COLOR_BG = (28, 32, 40)
COLOR_RESOURCE = (240, 195, 70)
COLOR_PLAYER = (65, 145, 245)
COLOR_ENEMY = (230, 75, 75)
COLOR_SELECTION = (255, 255, 255)
COLOR_TEXT = (230, 230, 230)
COLOR_HP_BG = (70, 20, 20)
COLOR_HP = (50, 220, 90)
COLOR_BUILD = (100, 180, 255)
COLOR_PROGRESS = (80, 200, 255)
COLOR_MSG = (255, 220, 100)
COLOR_ARMOR = (90, 160, 220)
COLOR_TOWER = (210, 170, 70)
COLOR_RIVER = (40, 100, 180)
COLOR_BRIDGE = (140, 100, 60)
COLOR_MOUNTAIN = (90, 70, 50)

COST_WORKER = 50
COST_TANK = 80
COST_BASE = 150
COST_ARMOR = 140
COST_TOWER = 70

BUILD_SIZE = {"base": 54, "armor": 50, "tower": 38}
BUILD_HP = {"base": 700, "armor": 520, "tower": 380}

# 单位生产时间（秒）：单位采用“生产”，建筑仍采用“建造”
UNIT_BUILD_TIME = {"worker": 2.5, "soldier": 4.0}
MAX_PRODUCTION_QUEUE = 12
REPAIR_RATE = 1.2  # 每帧修复生命值


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


# ==================== 地形 ====================
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


# ==================== 实体 ====================
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
            if math.hypot(self.target_x - self.x, self.target_y - self.y) <= 5:
                if self.state == "gather" and self.gather_target and self.gather_target.amount > 0:
                    take = min(0.3, self.gather_target.amount, self.carry_max - self.carry)
                    self.gather_target.amount -= take
                    self.carry += take
                    if self.carry >= self.carry_max or self.gather_target.amount <= 0:
                        self._go_return(game)
                elif self.state == "return" and self.return_base:
                    game.resources[self.team] += self.carry
                    self.carry = 0
                    if self.gather_target and self.gather_target.amount > 0:
                        self.set_gather(self.gather_target, game)
                    else:
                        self.state = "idle"
                elif self.state == "build" and self.build_target and not self.build_target.finished:
                    # 进度累加，可多人同时建，可中断后继续
                    self.build_target.build_progress += 0.55
                    if self.build_target.build_progress >= 100:
                        self.build_target.finish_build()
                        game.play_sound("build")
                        self.state = "idle"
                        self.build_target = None
                elif (
                    self.state == "repair"
                    and self.repair_target
                    and self.repair_target in game.buildings
                    and self.repair_target.finished
                    and self.repair_target.hp > 0
                ):
                    if self.repair_target.hp < self.repair_target.max_hp:
                        old_hp = self.repair_target.hp
                        self.repair_target.hp = min(
                            self.repair_target.max_hp,
                            self.repair_target.hp + REPAIR_RATE,
                        )
                        if old_hp < self.repair_target.max_hp <= self.repair_target.hp:
                            game.show_msg("维修完成", 45)
                    else:
                        self.state = "idle"
                        self.repair_target = None
                elif self.state == "move":
                    self.state = "idle"

        # 攻击
        if self.unit_type == "soldier" or self.state == "idle":
            targets = [u for u in game.units if u.team != self.team and u.hp > 0]
            targets += [b for b in game.buildings if b.team != self.team and b.hp > 0]
            if targets:
                nearest = min(targets, key=lambda t: math.hypot(t.x - self.x, t.y - self.y))
                edist = math.hypot(nearest.x - self.x, nearest.y - self.y)
                if edist <= self.attack_range:
                    self.turret = math.atan2(nearest.y - self.y, nearest.x - self.x)
                    dmg = (self.attack_power / FPS) * getattr(nearest, "defense_bonus", 1.0)
                    nearest.hp -= dmg
                    if random.random() < 0.08:
                        game.play_sound("hit")
                else:
                    self.turret = self.facing
            else:
                self.turret = self.facing


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

    def draw(self, surface):
        color = COLOR_PLAYER if self.team == "player" else COLOR_ENEMY
        if self.unit_type == "worker":
            draw_excavator(surface, self.x, self.y, self.facing, color, self.carry > 0)
        else:
            draw_tank(surface, self.x, self.y, self.facing, self.turret, color)

        if self.selected:
            pygame.draw.circle(surface, COLOR_SELECTION, (int(self.x), int(self.y)), self.radius + 6, 2)

        if self.hp < self.max_hp:
            bar_w = 24
            pygame.draw.rect(surface, COLOR_HP_BG, (self.x - bar_w / 2, self.y - self.radius - 11, bar_w, 4))
            pygame.draw.rect(surface, COLOR_HP, (self.x - bar_w / 2, self.y - self.radius - 11, bar_w * max(0, self.hp) / self.max_hp, 4))


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
        if not self.can_produce(unit_type):
            return 0
        cost = COST_WORKER if unit_type == "worker" else COST_TANK
        added = 0
        count = min(max(0, int(count)), MAX_PRODUCTION_QUEUE - self.queued_count())
        while added < count and game.resources[self.team] >= cost:
            game.resources[self.team] -= cost
            self.production_queue.append(unit_type)
            added += 1
        if added:
            game.play_sound("click")
        return added

    def update_production(self, game):
        if not self.finished or self.hp <= 0 or self.b_type == "tower":
            return
        if self.production_current is None and self.production_queue:
            self.production_current = self.production_queue.pop(0)
            self.production_progress = 0.0
            game.play_sound("train")

        if self.production_current is None:
            return

        total_frames = max(1, int(UNIT_BUILD_TIME[self.production_current] * FPS))
        self.production_progress += 1.0
        if self.production_progress >= total_frames:
            if game.spawn_produced_unit(self) is not None:
                self.production_current = None
                self.production_progress = 0.0

    def finish_build(self):
        self.finished = True
        self.hp = self.max_hp
        self.build_progress = 100

    def fire(self, game):
        if self.b_type != "tower" or not self.finished or self.hp <= 0:
            return
        targets = [u for u in game.units if u.team != self.team and u.hp > 0]
        targets += [b for b in game.buildings if b.team != self.team and b.hp > 0]
        if not targets:
            return
        nearest = min(targets, key=lambda t: math.hypot(t.x - self.x, t.y - self.y))
        dist = math.hypot(nearest.x - self.x, nearest.y - self.y)
        if dist <= self.attack_range:
            self.aim = math.atan2(nearest.y - self.y, nearest.x - self.x)
            nearest.hp -= (self.attack_power / FPS) * getattr(nearest, "defense_bonus", 1.0)
            if random.random() < 0.05:
                game.play_sound("hit")

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


# ==================== 主游戏 ====================
class RTSGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("钢河前线 - 基地/装甲工厂/防御塔")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("microsoftyahei,simhei,arial", 17)
        self.big_font = pygame.font.SysFont("microsoftyahei,simhei,arial", 32)

        self.resources = {"player": 400, "enemy": 350}
        self.units = []
        self.buildings = []
        self.resource_nodes = []
        self.rivers = []
        self.bridges = []
        self.mountains = []
        self.drag_start = None
        self.build_mode = None
        self.game_over = False
        self.winner = None
        self.enemy_timer = 0
        self.msg = ""
        self.msg_timer = 0

        self.sfx = {
            "click": make_sound(600, 0.04, 0.2),
            "train": make_sound(300, 0.12, 0.25, "sine"),
            "build": make_sound(180, 0.2, 0.3, "sine"),
            "hit": make_sound(120, 0.06, 0.15),
            "error": make_sound(100, 0.1, 0.2),
        }

        self.setup_map()

    def play_sound(self, name):
        if name in self.sfx:
            self.sfx[name].play()

    def setup_map(self):
        # ===== 地形 =====
        # 中间一条垂直河流
        self.rivers.append(River(580, 0, 50, HEIGHT))
        # 两座桥
        self.bridges.append(Bridge(560, 220, 90, 40))
        self.bridges.append(Bridge(560, 520, 90, 40))

        # 几块山地
        self.mountains.append(Mountain(80, 80, 160, 120))
        self.mountains.append(Mountain(950, 80, 180, 130))
        self.mountains.append(Mountain(300, 600, 200, 110))
        self.mountains.append(Mountain(750, 600, 180, 100))

        # 双方主基地
        self.buildings.append(Building(140, 380, "player", "base", finished=True))
        self.buildings.append(Building(1060, 380, "enemy", "base", finished=True))

        # 初始农民
        for i in range(3):
            self.units.append(Unit(210, 320 + i * 40, "player", "worker"))
        for i in range(3):
            self.units.append(Unit(990, 340 + i * 40, "enemy", "worker"))


        # ===== 矿点：保证基地附近有矿 =====
        # 玩家附近固定 2 个
        self.resource_nodes.append(ResourceNode(280, 300, 1000))
        self.resource_nodes.append(ResourceNode(260, 480, 1000))
        # 敌方附近固定 2 个
        self.resource_nodes.append(ResourceNode(920, 300, 1000))
        self.resource_nodes.append(ResourceNode(940, 480, 1000))
        # 其余随机（避开河流和山地）
        for _ in range(5):
            for attempt in range(30):
                x = random.randint(350, 850)
                y = random.randint(120, 660)
                if not self.is_blocked(x, y, 20) and not any(math.hypot(x - n.x, y - n.y) < 60 for n in self.resource_nodes):
                    self.resource_nodes.append(ResourceNode(x, y, random.randint(700, 1100)))
                    break

    def show_msg(self, text, time=80):
        self.msg = text
        self.msg_timer = time

    def is_on_bridge(self, x, y):
        return any(b.contains(x, y) for b in self.bridges)

    @staticmethod
    def _circle_intersects_rect(x, y, radius, rect):
        nearest_x = min(max(x, rect.left), rect.right)
        nearest_y = min(max(y, rect.top), rect.bottom)
        return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 < radius ** 2

    def is_blocked(self, x, y, radius):
        if x - radius < 0 or y - radius < 0 or x + radius > WIDTH or y + radius > HEIGHT:
            return True

        # 建筑碰撞
        for b in self.buildings:
            half = b.size / 2 + radius + 2
            if abs(b.x - x) < half and abs(b.y - y) < half:
                return True

        # A unit can cross a river only while fully aligned with a bridge lane.
        for r in self.rivers:
            if not self._circle_intersects_rect(x, y, radius, r.rect):
                continue
            if r.rect.w <= r.rect.h:
                on_bridge = any(
                    bridge.rect.left <= r.rect.left - radius
                    and bridge.rect.right >= r.rect.right + radius
                    and bridge.rect.top + radius <= y <= bridge.rect.bottom - radius
                    for bridge in self.bridges
                )
            else:
                on_bridge = any(
                    bridge.rect.top <= r.rect.top - radius
                    and bridge.rect.bottom >= r.rect.bottom + radius
                    and bridge.rect.left + radius <= x <= bridge.rect.right - radius
                    for bridge in self.bridges
                )
            if not on_bridge:
                return True
        return False

    def can_place_building(self, x, y, b_type):
        size = BUILD_SIZE.get(b_type, 48)
        if self.is_blocked(x, y, 30):
            return False


        return not any(
            abs(unit.x - x) < size / 2 + unit.radius + 2
            and abs(unit.y - y) < size / 2 + unit.radius + 2
            for unit in self.units
        )

    def _segment_is_clear(self, x1, y1, x2, y2, radius):
        distance = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, math.ceil(distance / 5))
        return all(
            not self.is_blocked(
                x1 + (x2 - x1) * i / steps,
                y1 + (y2 - y1) * i / steps,
                radius,
            )
            for i in range(1, steps + 1)
        )

    def find_path(self, x1, y1, x2, y2, radius):
        cell_size = 10
        columns = math.ceil(WIDTH / cell_size)
        rows = math.ceil(HEIGHT / cell_size)
        walkable = {}

        def point(cell):
            return ((cell[0] + 0.5) * cell_size, (cell[1] + 0.5) * cell_size)

        def is_walkable(cell):
            if cell not in walkable:
                px, py = point(cell)
                walkable[cell] = (
                    0 <= cell[0] < columns
                    and 0 <= cell[1] < rows
                    and not self.is_blocked(px, py, radius)
                )
            return walkable[cell]

        def nearby_cells(x, y, max_distance):
            center = (
                min(columns - 1, max(0, int(x / cell_size))),
                min(rows - 1, max(0, int(y / cell_size))),
            )
            cell_radius = math.ceil(max_distance / cell_size)
            candidates = []
            for cx in range(max(0, center[0] - cell_radius), min(columns, center[0] + cell_radius + 1)):
                for cy in range(max(0, center[1] - cell_radius), min(rows, center[1] + cell_radius + 1)):
                    cell = (cx, cy)
                    px, py = point(cell)
                    distance = math.hypot(px - x, py - y)
                    if distance <= max_distance and is_walkable(cell):
                        candidates.append((distance, cell))
            candidates.sort()
            return candidates

        starts = [
            cell for _, cell in nearby_cells(x1, y1, 30)
            if self._segment_is_clear(x1, y1, *point(cell), radius)
        ]
        if not starts:
            return []

        nearest_goal_cell = (
            min(columns - 1, max(0, int(x2 / cell_size))),
            min(rows - 1, max(0, int(y2 / cell_size))),
        )
        if is_walkable(nearest_goal_cell):
            goals = {nearest_goal_cell}
        else:
            goals = {
                cell for _, cell in nearby_cells(x2, y2, 50)
            }
        if not goals:
            return []

        start = starts[0]
        directions = (
            (-1, 0, 10), (1, 0, 10), (0, -1, 10), (0, 1, 10),
            (-1, -1, 14.142), (1, -1, 14.142),
            (-1, 1, 14.142), (1, 1, 14.142),
        )
        distances = {start: 0}
        previous = {}
        queue = [(math.hypot(point(start)[0] - x2, point(start)[1] - y2), 0, start)]
        visited = set()
        goal = None

        while queue:
            _, cost, current = heapq.heappop(queue)
            if current in visited:
                continue
            visited.add(current)
            if current in goals:
                goal = current
                break

            for dx, dy, step_cost in directions:
                neighbor = (current[0] + dx, current[1] + dy)
                if not is_walkable(neighbor):
                    continue
                if dx and dy and (
                    not is_walkable((current[0] + dx, current[1]))
                    or not is_walkable((current[0], current[1] + dy))
                ):
                    continue
                next_cost = cost + step_cost
                if next_cost >= distances.get(neighbor, float("inf")):
                    continue
                distances[neighbor] = next_cost
                previous[neighbor] = current
                px, py = point(neighbor)
                estimate = math.hypot(px - x2, py - y2)
                heapq.heappush(queue, (next_cost + estimate, next_cost, neighbor))

        if goal is None:
            return []

        cells = []
        while goal != start:
            cells.append(goal)
            goal = previous[goal]
        cells.reverse()
        path = [point(cell) for cell in cells]
        if path and not self.is_blocked(x2, y2, radius):
            if self._segment_is_clear(*path[-1], x2, y2, radius):
                path.append((x2, y2))
        elif not path and not self.is_blocked(x2, y2, radius):
            if self._segment_is_clear(x1, y1, x2, y2, radius):
                path.append((x2, y2))
        return path

    def find_path_to_building(self, x, y, building, radius):
        distance = building.size / 2 + radius + 5
        diagonal = distance * math.sqrt(2)
        approaches = (
            (building.x - distance, building.y),
            (building.x + distance, building.y),
            (building.x, building.y - distance),
            (building.x, building.y + distance),
            (building.x - diagonal, building.y - diagonal),
            (building.x + diagonal, building.y - diagonal),
            (building.x - diagonal, building.y + diagonal),
            (building.x + diagonal, building.y + diagonal),
        )
        paths = [
            path for tx, ty in approaches
            if not self.is_blocked(tx, ty, radius)
            and (path := self.find_path(x, y, tx, ty, radius))
        ]
        return min(
            paths,
            key=lambda path: sum(
                math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
                for i in range(1, len(path))
            ) + math.hypot(path[0][0] - x, path[0][1] - y),
            default=[],
        )

    def selected_building(self):
        return next((b for b in self.buildings if b.selected and b.team == "player"), None)

    def spawn_produced_unit(self, building):
        if building.b_type == "base":
            unit_type = "worker"
            side = 1 if building.team == "player" else -1
            base_x = building.x + side * 58
        elif building.b_type == "armor":
            unit_type = "soldier"
            side = 1 if building.team == "player" else -1
            base_x = building.x + side * 56
        else:
            return None

        for offset_y in (-24, 0, 24, 48, -48):
            x = base_x + random.randint(-8, 8)
            y = building.y + offset_y
            unit = Unit(x, y, building.team, unit_type)
            if not self.is_blocked(x, y, unit.radius):
                self.units.append(unit)
                self.show_msg(
                    "挖掘机生产完成" if unit_type == "worker" else "坦克生产完成",
                    35,
                )
                return unit

        # 出厂口被堵时，放在建筑旁最近的安全位置。
        for distance in (70, 85, 100):
            for ang in range(0, 360, 45):
                rad = math.radians(ang)
                x = building.x + math.cos(rad) * distance
                y = building.y + math.sin(rad) * distance
                unit = Unit(x, y, building.team, unit_type)
                if not self.is_blocked(x, y, unit.radius):
                    self.units.append(unit)
                    return unit
        return None

    def handle_production_click(self, mx, my):
        building = self.selected_building()
        if not building:
            return False

        panel_x, panel_y, panel_w, panel_h = self.production_panel_rect()
        if not pygame.Rect(panel_x, panel_y, panel_w, panel_h).collidepoint(mx, my):
            return False

        if not building.can_produce("worker") and not building.can_produce("soldier"):
            return True

        buttons = self.production_button_rects(building)
        unit_type = "worker" if building.b_type == "base" else "soldier"
        for amount, rect in buttons:
            if rect.collidepoint(mx, my):
                added = building.queue_unit(unit_type, self, amount)
                if added < amount:
                    self.show_msg("资源不足或生产队列已满", 60)
                    self.play_sound("error")
                else:
                    name = "挖掘机" if unit_type == "worker" else "坦克"
                    self.show_msg(f"已加入{name}生产队列 ×{added}", 55)
                return True
        return True

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            if self.game_over:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.__init__()
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_w:
                    selected_base = next((b for b in self.buildings if b.selected and b.team == "player" and b.finished and b.b_type == "base"), None)
                    if not selected_base:
                        self.show_msg("请先选中基地（基地=拖拉机厂）")
                        self.play_sound("error")
                    else:
                        added = selected_base.queue_unit("worker", self, 1)
                        if added:
                            self.show_msg("挖掘机已加入生产队列")
                        else:
                            self.show_msg("钢铁不足或生产队列已满")
                            self.play_sound("error")

                if event.key == pygame.K_s:
                    selected_rax = next((b for b in self.buildings if b.selected and b.team == "player" and b.finished and b.b_type == "armor"), None)
                    if not selected_rax:
                        self.show_msg("请先选中装甲工厂")
                        self.play_sound("error")
                    else:
                        added = selected_rax.queue_unit("soldier", self, 1)
                        if added:
                            self.show_msg("坦克已加入生产队列")
                        else:
                            self.show_msg("钢铁不足或生产队列已满")
                            self.play_sound("error")

                if event.key == pygame.K_b:
                    workers = [u for u in self.units if u.selected and u.unit_type == "worker"]
                    if not workers:
                        self.show_msg("请先选中挖掘机")
                        self.play_sound("error")
                    elif self.resources["player"] < COST_BASE:
                        self.show_msg(f"钢铁不足（基地{COST_BASE}）")
                        self.play_sound("error")
                    else:
                        self.build_mode = "base" if self.build_mode != "base" else None
                        if self.build_mode:
                            self.show_msg("建造基地/拖拉机厂：左键放置")

                if event.key == pygame.K_a:
                    workers = [u for u in self.units if u.selected and u.unit_type == "worker"]
                    if not workers:
                        self.show_msg("请先选中挖掘机")
                        self.play_sound("error")
                    elif self.resources["player"] < COST_ARMOR:
                        self.show_msg(f"钢铁不足（装甲工厂{COST_ARMOR}）")
                        self.play_sound("error")
                    else:
                        self.build_mode = "armor" if self.build_mode != "armor" else None
                        if self.build_mode:
                            self.show_msg("建造装甲工厂：左键放置")

                if event.key == pygame.K_t:
                    workers = [u for u in self.units if u.selected and u.unit_type == "worker"]
                    if not workers:
                        self.show_msg("请先选中挖掘机")
                        self.play_sound("error")
                    elif self.resources["player"] < COST_TOWER:
                        self.show_msg(f"钢铁不足（防御塔{COST_TOWER}）")
                        self.play_sound("error")
                    else:
                        self.build_mode = "tower" if self.build_mode != "tower" else None
                        if self.build_mode:
                            self.show_msg("建造防御塔：左键放置（不能移动，性价比高于坦克）")

                if event.key == pygame.K_ESCAPE:
                    self.build_mode = None

            # 左键
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # 小地图点击
                mm_x = WIDTH - MINIMAP_SIZE - MINIMAP_MARGIN
                mm_y = HEIGHT - MINIMAP_SIZE - MINIMAP_MARGIN
                if mm_x <= mx <= mm_x + MINIMAP_SIZE and mm_y <= my <= mm_y + MINIMAP_SIZE:
                    ratio_x = (mx - mm_x) / MINIMAP_SIZE
                    ratio_y = (my - mm_y) / MINIMAP_SIZE
                    tx = ratio_x * WIDTH
                    ty = ratio_y * HEIGHT
                    for u in self.units:
                        if u.selected:
                            u.set_move(tx, ty, self)
                    return True

                if self.handle_production_click(mx, my):
                    continue

                if self.build_mode:
                    cost = {"base": COST_BASE, "armor": COST_ARMOR, "tower": COST_TOWER}[self.build_mode]
                    if (
                        60 < mx < WIDTH - 60
                        and 60 < my < HEIGHT - 60
                        and self.can_place_building(mx, my, self.build_mode)
                    ):

                        new_b = Building(mx, my, "player", self.build_mode, finished=False)
                        self.buildings.append(new_b)
                        self.resources["player"] -= cost
                        for u in self.units:
                            if u.selected and u.unit_type == "worker":
                                u.set_build(new_b, self)
                        self.build_mode = None
                        self.show_msg("开始建造")
                        self.play_sound("click")
                    elif 60 < mx < WIDTH - 60 and 60 < my < HEIGHT - 60:
                        self.show_msg("建筑位置被占用，请避开单位、建筑和河流")
                        self.play_sound("error")
                else:
                    # 选中挖掘机后左键友方建筑 = 维修；否则点击建筑打开生产界面。
                    selected_workers = [u for u in self.units if u.selected and u.team == "player" and u.unit_type == "worker"]
                    clicked_building = next(
                        (b for b in self.buildings
                         if b.team == "player" and b.finished
                         and abs(b.x - mx) < b.size / 2 + 8
                         and abs(b.y - my) < b.size / 2 + 8),
                        None,
                    )
                    if selected_workers and clicked_building:
                        for u in selected_workers:
                            u.set_repair(clicked_building, self)
                        if clicked_building.hp >= clicked_building.max_hp:
                            self.show_msg("建筑生命值已满")
                        else:
                            self.show_msg(f"{len(selected_workers)} 台挖掘机前往维修")
                        return True

                    self.drag_start = event.pos
                    for u in self.units:
                        if u.team == "player":
                            u.selected = False
                    for b in self.buildings:
                        if b.team == "player":
                            b.selected = False

                    if clicked_building:
                        clicked_building.selected = True
                        self.play_sound("click")
                        self.drag_start = None

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.drag_start and not self.build_mode:
                x1, y1 = self.drag_start
                x2, y2 = event.pos
                select_rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
                for u in self.units:
                    if u.team == "player":
                        if select_rect.width < 8 and select_rect.height < 8:
                            if math.hypot(u.x - x1, u.y - y1) < 18:
                                u.selected = True
                        else:
                            if select_rect.collidepoint(u.x, u.y):
                                u.selected = True
                self.drag_start = None

            # 右键
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                mx, my = event.pos
                selected = [u for u in self.units if u.selected]

                # 优先：右键未完成建筑 → 继续建造
                clicked_build = None
                for b in self.buildings:
                    if b.team == "player" and not b.finished:
                        if abs(b.x - mx) < b.size / 2 + 10 and abs(b.y - my) < b.size / 2 + 10:
                            clicked_build = b
                            break

                if clicked_build:
                    for u in selected:
                        if u.unit_type == "worker":
                            u.set_build(clicked_build, self)
                    self.show_msg("继续建造中...")
                    continue

                # 其次：右键矿点
                clicked_node = None
                for node in self.resource_nodes:
                    if node.amount > 0 and math.hypot(node.x - mx, node.y - my) < 26:
                        clicked_node = node
                        break

                if clicked_node:
                    for u in selected:
                        if u.unit_type == "worker":
                            u.set_gather(clicked_node, self)
                else:
                    for i, u in enumerate(selected):
                        ox = (i % 5) * 18 - 36
                        oy = (i // 5) * 18 - 18
                        u.set_move(mx + ox, my + oy, self)

        return True

    def update(self):
        if self.game_over:
            return

        if self.msg_timer > 0:
            self.msg_timer -= 1

        for u in self.units:
            u.update(self)
        for b in self.buildings:
            b.update_production(self)
            b.fire(self)


        self.units = [u for u in self.units if u.hp > 0]
        self.buildings = [b for b in self.buildings if b.hp > 0]
        self.resource_nodes = [n for n in self.resource_nodes if n.amount > 0]

        player_alive = any(b.team == "player" and b.finished and b.b_type == "base" for b in self.buildings)
        enemy_alive = any(b.team == "enemy" and b.finished and b.b_type == "base" for b in self.buildings)
        if not player_alive:
            self.game_over = True
            self.winner = "enemy"
        elif not enemy_alive:
            self.game_over = True
            self.winner = "player"

        # 敌方 AI：采矿、用挖机建造、出坦克
        self.enemy_timer += 1
        if self.enemy_timer >= 40:
            self.enemy_timer = 0
            self.enemy_ai()

    def _enemy_workers(self):
        return [u for u in self.units if u.team == "enemy" and u.unit_type == "worker" and u.hp > 0]

    def _nearest_node(self, x, y):
        live = [n for n in self.resource_nodes if n.amount > 0]
        if not live:
            return None
        return min(live, key=lambda n: math.hypot(n.x - x, n.y - y))

    def _enemy_build_spot(self, kind):
        base = next((b for b in self.buildings if b.team == "enemy" and b.finished and b.b_type == "base"), None)
        if not base:
            return None
        if kind == "armor":
            candidates = [
                (base.x - 110, base.y + 70),
                (base.x - 110, base.y - 70),
                (base.x - 70, base.y + 110),
                (base.x - 40, base.y + 90),
            ]
        else:
            candidates = [
                (base.x - 90, base.y - 100),
                (base.x - 40, base.y - 120),
                (base.x - 90, base.y + 110),
                (720, 380),
                (700, 250),
                (700, 520),
            ]
        for x, y in candidates:
            if self.can_place_building(x, y, kind):
                return x, y
        for _ in range(25):
            x = random.randint(700, 1100)
            y = random.randint(80, 700)
            if self.can_place_building(x, y, kind):
                return x, y
        return None

    def _send_workers_build(self, building, count=2):
        workers = self._enemy_workers()
        idle = [u for u in workers if u.state in ("idle", "gather")]
        chosen = idle[:count] or workers[:count]
        for u in chosen:
            u.set_build(building, self)

    def enemy_ai(self):
        bases = [b for b in self.buildings if b.team == "enemy" and b.finished and b.b_type == "base"]
        if not bases:
            return
        base = bases[0]
        workers = self._enemy_workers()
        armor = [b for b in self.buildings if b.team == "enemy" and b.b_type == "armor"]
        towers = [b for b in self.buildings if b.team == "enemy" and b.b_type == "tower"]
        unfinished = [b for b in self.buildings if b.team == "enemy" and not b.finished]
        tanks = [u for u in self.units if u.team == "enemy" and u.unit_type == "soldier" and u.hp > 0]
        money = self.resources["enemy"]

        # 未完成建筑：挖机去续建
        if unfinished:
            for b in unfinished:
                building = b
                on_it = sum(1 for u in workers if u.build_target is building)
                if on_it < 2:
                    self._send_workers_build(building, 2)
        else:
            # 先造装甲工厂，再造 1～2 座防御塔
            need = None
            if not armor and money >= COST_ARMOR:
                need = "armor"
            elif armor and any(b.finished for b in armor) and len(towers) < 2 and money >= COST_TOWER:
                need = "tower"
            if need:
                spot = self._enemy_build_spot(need)
                if spot:
                    cost = COST_ARMOR if need == "armor" else COST_TOWER
                    self.resources["enemy"] -= cost
                    new_b = Building(spot[0], spot[1], "enemy", need, finished=False)
                    self.buildings.append(new_b)
                    self._send_workers_build(new_b, 2)

        # 挖机太少就从基地加入生产队列。
        if len(workers) + sum(b.queued_count() for b in bases) < 5 and money >= COST_WORKER and any(b.finished for b in bases):
            base.queue_unit("worker", self, 1)

        # 空闲挖机去采矿
        for u in workers:
            if u.state == "idle":
                node = self._nearest_node(u.x, u.y)
                if node:
                    u.set_gather(node, self)

        # 装甲厂出坦克：同样走生产队列，等待生产时间。
        ready_armor = [b for b in armor if b.finished]
        if ready_armor and money >= COST_TANK and len(tanks) < 10:
            rax = ready_armor[0]
            if rax.queued_count() < 4:
                rax.queue_unit("soldier", self, 1)

        player_hq = next((b for b in self.buildings if b.team == "player" and b.finished and b.b_type == "base"), None)
        player_stuff = [u for u in self.units if u.team == "player" and u.hp > 0]
        player_stuff += [b for b in self.buildings if b.team == "player" and b.hp > 0]
        for tank in tanks:
            if tank.state != "idle":
                continue
            if len(tanks) >= 3 and player_hq:
                tank.set_move(
                    player_hq.x + random.randint(-50, 50),
                    player_hq.y + random.randint(-50, 50),
                    self,
                )
            elif player_stuff:
                tgt = min(player_stuff, key=lambda t: math.hypot(t.x - tank.x, t.y - tank.y))
                tank.set_move(tgt.x + random.randint(-20, 20), tgt.y + random.randint(-20, 20), self)



    def production_panel_rect(self):
        return 880, 12, 305, 196

    def production_button_rects(self, building):
        x, y, w, h = self.production_panel_rect()
        top = y + 108
        gap = 7
        bw = (w - 24 - gap * 2) // 3
        return [
            (1, pygame.Rect(x + 12, top, bw, 42)),
            (5, pygame.Rect(x + 12 + bw + gap, top, bw, 42)),
            (10, pygame.Rect(x + 12 + (bw + gap) * 2, top, bw, 42)),
        ]

    def draw_production_panel(self):
        building = self.selected_building()
        if not building:
            return

        x, y, w, h = self.production_panel_rect()
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((15, 18, 24, 225))
        pygame.draw.rect(panel, (150, 160, 175), (0, 0, w, h), 2)
        self.screen.blit(panel, (x, y))

        names = {"base": "基地 / 拖拉机厂", "armor": "装甲工厂", "tower": "防御塔"}
        title = self.font.render(names.get(building.b_type, building.b_type), True, COLOR_TEXT)
        self.screen.blit(title, (x + 12, y + 10))

        if building.b_type == "tower":
            text = self.font.render("该建筑没有生产项目", True, (190, 190, 190))
            self.screen.blit(text, (x + 12, y + 46))
            return

        unit_type = "worker" if building.b_type == "base" else "soldier"
        unit_name = "挖掘机" if unit_type == "worker" else "坦克"
        cost = COST_WORKER if unit_type == "worker" else COST_TANK
        time_sec = UNIT_BUILD_TIME[unit_type]
        queued = building.queued_count()

        # 当前生产状态
        if building.production_current:
            current_name = "挖掘机" if building.production_current == "worker" else "坦克"
            total = max(1, UNIT_BUILD_TIME[building.production_current] * FPS)
            remain = max(0.0, (total - building.production_progress) / FPS)
            status = f"正在生产：{current_name}  {remain:.1f}s"
            status_color = COLOR_PROGRESS
        elif building.production_queue:
            status = "等待生产..."
            status_color = COLOR_PROGRESS
        else:
            status = "生产队列空闲"
            status_color = (180, 180, 180)
        self.screen.blit(self.font.render(status, True, status_color), (x + 12, y + 38))

        info = self.font.render(
            f"{unit_name}  |  钢铁 {cost}  |  生产时间 {time_sec:g}s  |  队列 {queued}/{MAX_PRODUCTION_QUEUE}",
            True, (210, 215, 220),
        )
        self.screen.blit(info, (x + 12, y + 64))

        for amount, rect in self.production_button_rects(building):
            can_afford = self.resources[building.team] >= cost and building.queued_count() < MAX_PRODUCTION_QUEUE
            fill = (55, 70, 90) if can_afford else (45, 45, 48)
            border = COLOR_BUILD if can_afford else (90, 90, 90)
            pygame.draw.rect(self.screen, fill, rect, border_radius=4)
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=4)
            label = self.font.render(f"生产 ×{amount}", True, COLOR_TEXT if can_afford else (130, 130, 130))
            self.screen.blit(label, label.get_rect(center=rect.center))

        hint = self.font.render(
            "快捷键：W 生产挖掘机 / S 生产坦克（点击建筑自动打开）",
            True, (155, 165, 180),
        )
        self.screen.blit(hint, (x + 12, y + 159))

    def draw_minimap(self):
        mm_x = WIDTH - MINIMAP_SIZE - MINIMAP_MARGIN
        mm_y = HEIGHT - MINIMAP_SIZE - MINIMAP_MARGIN
        pygame.draw.rect(self.screen, (20, 24, 30), (mm_x, mm_y, MINIMAP_SIZE, MINIMAP_SIZE))
        pygame.draw.rect(self.screen, (80, 90, 100), (mm_x, mm_y, MINIMAP_SIZE, MINIMAP_SIZE), 2)

        scale_x = MINIMAP_SIZE / WIDTH
        scale_y = MINIMAP_SIZE / HEIGHT

        # 河流
        for r in self.rivers:
            pygame.draw.rect(self.screen, COLOR_RIVER,
                             (mm_x + int(r.rect.x * scale_x), mm_y + int(r.rect.y * scale_y),
                              max(2, int(r.rect.w * scale_x)), max(2, int(r.rect.h * scale_y))))

        for node in self.resource_nodes:
            px = mm_x + int(node.x * scale_x)
            py = mm_y + int(node.y * scale_y)
            pygame.draw.circle(self.screen, COLOR_RESOURCE, (px, py), 2)

        for b in self.buildings:
            px = mm_x + int(b.x * scale_x)
            py = mm_y + int(b.y * scale_y)
            color = COLOR_PLAYER if b.team == "player" else COLOR_ENEMY
            size = 5 if b.b_type == "base" else 4
            pygame.draw.rect(self.screen, color, (px - size // 2, py - size // 2, size, size))

        for u in self.units:
            px = mm_x + int(u.x * scale_x)
            py = mm_y + int(u.y * scale_y)
            color = COLOR_PLAYER if u.team == "player" else COLOR_ENEMY
            pygame.draw.circle(self.screen, color, (px, py), 2)

    def draw(self):
        self.screen.fill(COLOR_BG)

        # 先画地形
        for m in self.mountains:
            m.draw(self.screen)
        for r in self.rivers:
            r.draw(self.screen)
        for b in self.bridges:
            b.draw(self.screen)

        for node in self.resource_nodes:
            node.draw(self.screen)
        for b in self.buildings:
            b.draw(self.screen)
        for u in self.units:
            u.draw(self.screen)

        if self.drag_start and not self.build_mode:
            mx, my = pygame.mouse.get_pos()
            x1, y1 = self.drag_start
            rect = pygame.Rect(min(x1, mx), min(y1, my), abs(mx - x1), abs(my - y1))
            pygame.draw.rect(self.screen, COLOR_SELECTION, rect, 1)

        if self.build_mode:
            mx, my = pygame.mouse.get_pos()
            size = BUILD_SIZE[self.build_mode]
            names = {"base": "基地/拖拉机厂", "armor": "装甲工厂", "tower": "防御塔"}
            colors = {"base": COLOR_BUILD, "armor": COLOR_ARMOR, "tower": COLOR_TOWER}
            color = colors[self.build_mode]
            pygame.draw.rect(self.screen, color, (mx - size / 2, my - size / 2, size, size), 2)
            tip = self.font.render(f"放置{names[self.build_mode]}（ESC取消）", True, color)
            self.screen.blit(tip, (mx - 80, my - 45))

        info = self.font.render(
            f"钢铁: {int(self.resources['player'])}  |  左键选建筑=生产界面  |  挖掘机点建筑=维修  |  右键移动/采矿/续建",
            True, COLOR_TEXT
        )
        self.screen.blit(info, (12, 10))

        selected_units = sum(1 for u in self.units if u.selected)
        selected_b = next((b for b in self.buildings if b.selected), None)
        if selected_units > 0:
            self.screen.blit(self.font.render(f"已选单位: {selected_units}", True, (180, 220, 255)), (12, 34))
        if selected_b:
            names = {"base": "基地/拖拉机厂", "armor": "装甲工厂", "tower": "防御塔"}
            self.screen.blit(self.font.render(f"已选建筑: {names.get(selected_b.b_type, selected_b.b_type)}", True, (180, 255, 180)), (12, 56))

        if self.msg_timer > 0 and self.msg:
            msg_surf = self.font.render(self.msg, True, COLOR_MSG)
            self.screen.blit(msg_surf, (WIDTH // 2 - msg_surf.get_width() // 2, 80))

        self.draw_minimap()
        self.draw_production_panel()

        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            self.screen.blit(overlay, (0, 0))
            msg = "胜利！按 R 重开" if self.winner == "player" else "失败... 按 R 重开"
            color = (80, 255, 120) if self.winner == "player" else (255, 100, 100)
            text = self.big_font.render(msg, True, color)
            self.screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = RTSGame()
    game.run()