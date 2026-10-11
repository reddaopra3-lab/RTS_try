"""Game state, input handling, AI, and rendering loop."""
import math
import random
import sys

import pygame

from .audio.synthesizer import make_sound
from .config.balance import (
    BUILD_SIZE, COST_ARMOR, COST_BASE, COST_TANK, COST_TOWER, COST_WORKER,
    MAX_PRODUCTION_QUEUE, UNIT_BUILD_TIME,
)
from .config.settings import (
    COLOR_ARMOR, COLOR_BG, COLOR_BUILD, COLOR_ENEMY, COLOR_MSG, COLOR_PLAYER,
    COLOR_RESOURCE, COLOR_RIVER, COLOR_SELECTION, COLOR_TEXT, COLOR_TOWER,
    FPS, HEIGHT, MINIMAP_MARGIN, MINIMAP_SIZE, WIDTH,
)
from .models.building import Building
from .models.unit import Unit
from .systems.pathfinding import find_path, find_path_to_building, segment_is_clear
from .world.map_data import Bridge, Mountain, ResourceNode, River
from .world.map_loader import DEFAULT_MAP_PATH, list_maps, setup_map
from .ui.panels import render_minimap, render_production_panel

class RTSGame:
    def __init__(self, map_path=None):
        pygame.init()
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("钢河前线 - 基地/装甲工厂/防御塔")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("microsoftyahei,simhei,arial", 17)
        self.big_font = pygame.font.SysFont("microsoftyahei,simhei,arial", 32)

        self.resources = {"player": 400, "enemy": 350}
        self.map_width = WIDTH
        self.map_height = HEIGHT
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.camera_drag = None
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
        self.map_paths = list_maps()
        self.selected_map_index = next(
            (index for index, path in enumerate(self.map_paths) if path == DEFAULT_MAP_PATH),
            0,
        )
        self.menu_active = map_path is None
        self.menu_error = ""
        self.current_map_path = None

        self.sfx = {
            "click": make_sound(600, 0.04, 0.2),
            "train": make_sound(300, 0.12, 0.25, "sine"),
            "build": make_sound(180, 0.2, 0.3, "sine"),
            "hit": make_sound(120, 0.06, 0.15),
            "error": make_sound(100, 0.1, 0.2),
        }

        if map_path is not None:
            self.setup_map(map_path)
            self.menu_active = False

    def play_sound(self, name):
        if name in self.sfx:
            self.sfx[name].play()

    def setup_map(self, map_path=None):
        path = DEFAULT_MAP_PATH if map_path is None else map_path
        setup_map(self, path)
        self.current_map_path = path
        player_base = next(
            (b for b in self.buildings if b.team == "player" and b.b_type == "base"),
            None,
        )
        if player_base:
            self.center_camera(player_base.x, player_base.y)

    def clamp_camera(self):
        self.camera_x = max(0, min(self.camera_x, self.map_width - WIDTH))
        self.camera_y = max(0, min(self.camera_y, self.map_height - HEIGHT))

    def center_camera(self, world_x, world_y):
        self.camera_x = world_x - WIDTH / 2
        self.camera_y = world_y - HEIGHT / 2
        self.clamp_camera()

    def screen_to_world(self, screen_x, screen_y):
        return screen_x + self.camera_x, screen_y + self.camera_y

    def start_selected_map(self):
        if not self.map_paths:
            self.menu_error = "maps 文件夹中没有地图，请先用地图编辑器创建地图。"
            return
        try:
            self.setup_map(self.map_paths[self.selected_map_index])
        except (OSError, ValueError) as error:
            self.menu_error = f"地图无法加载: {error}"
            return
        self.menu_error = ""
        self.game_over = False
        self.winner = None
        self.enemy_timer = 0
        self.menu_active = False

    @staticmethod
    def menu_map_rect(index):
        return pygame.Rect(WIDTH // 2 - 200, 230 + index * 48, 400, 40)

    @staticmethod
    def menu_start_rect():
        return pygame.Rect(WIDTH // 2 - 110, HEIGHT - 130, 220, 54)

    def menu_visible_start(self):
        visible_count = 7
        return max(
            0,
            min(self.selected_map_index - visible_count // 2, len(self.map_paths) - visible_count),
        )

    def handle_menu_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP and self.map_paths:
                self.selected_map_index = (self.selected_map_index - 1) % len(self.map_paths)
            elif event.key == pygame.K_DOWN and self.map_paths:
                self.selected_map_index = (self.selected_map_index + 1) % len(self.map_paths)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_selected_map()
            elif event.key == pygame.K_ESCAPE:
                return False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            first_index = self.menu_visible_start()
            for offset, _ in enumerate(self.map_paths[first_index:first_index + 7]):
                if self.menu_map_rect(offset).collidepoint(event.pos):
                    self.selected_map_index = first_index + offset
                    return True
            if self.menu_start_rect().collidepoint(event.pos):
                self.start_selected_map()
        return True

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
        if (
            x - radius < 0 or y - radius < 0
            or x + radius > self.map_width or y + radius > self.map_height
        ):
            return True

        # 建筑碰撞
        for b in self.buildings:
            half = b.size / 2 + radius + 2
            if abs(b.x - x) < half and abs(b.y - y) < half:
                return True

        for r in self.rivers:
            if not r.intersects_circle(x, y, radius):
                continue
            on_bridge = any(bridge.contains_circle(x, y, radius) for bridge in self.bridges)
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
        return segment_is_clear(self, x1, y1, x2, y2, radius)

    def find_path(self, x1, y1, x2, y2, radius):
        return find_path(self, x1, y1, x2, y2, radius)

    def find_path_to_building(self, x, y, building, radius):
        return find_path_to_building(self, x, y, building, radius)

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

            if self.menu_active:
                if not self.handle_menu_event(event):
                    return False
                continue

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

                if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    step = 48
                    if event.key == pygame.K_LEFT:
                        self.camera_x -= step
                    elif event.key == pygame.K_RIGHT:
                        self.camera_x += step
                    elif event.key == pygame.K_UP:
                        self.camera_y -= step
                    else:
                        self.camera_y += step
                    self.clamp_camera()

                if event.key == pygame.K_ESCAPE:
                    self.build_mode = None

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
                self.camera_drag = (event.pos, self.camera_x, self.camera_y)
                continue

            if event.type == pygame.MOUSEMOTION and self.camera_drag:
                start_pos, start_x, start_y = self.camera_drag
                self.camera_x = start_x - (event.pos[0] - start_pos[0])
                self.camera_y = start_y - (event.pos[1] - start_pos[1])
                self.clamp_camera()
                continue

            if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                self.camera_drag = None
                continue

            # 左键
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos

                # 小地图点击
                mm_x = WIDTH - MINIMAP_SIZE - MINIMAP_MARGIN
                mm_y = HEIGHT - MINIMAP_SIZE - MINIMAP_MARGIN
                if mm_x <= mx <= mm_x + MINIMAP_SIZE and mm_y <= my <= mm_y + MINIMAP_SIZE:
                    ratio_x = (mx - mm_x) / MINIMAP_SIZE
                    ratio_y = (my - mm_y) / MINIMAP_SIZE
                    self.center_camera(ratio_x * self.map_width, ratio_y * self.map_height)
                    return True

                if self.handle_production_click(mx, my):
                    continue

                mx, my = self.screen_to_world(mx, my)
                if self.build_mode:
                    cost = {"base": COST_BASE, "armor": COST_ARMOR, "tower": COST_TOWER}[self.build_mode]
                    if (
                        60 < mx < self.map_width - 60
                        and 60 < my < self.map_height - 60
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
                    elif 60 < mx < self.map_width - 60 and 60 < my < self.map_height - 60:
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

                    self.drag_start = (mx, my)
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
                x2, y2 = self.screen_to_world(*event.pos)
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
                mx, my = self.screen_to_world(*event.pos)
                mm_x = WIDTH - MINIMAP_SIZE - MINIMAP_MARGIN
                mm_y = HEIGHT - MINIMAP_SIZE - MINIMAP_MARGIN
                if mm_x <= event.pos[0] <= mm_x + MINIMAP_SIZE and mm_y <= event.pos[1] <= mm_y + MINIMAP_SIZE:
                    self.center_camera(
                        (event.pos[0] - mm_x) / MINIMAP_SIZE * self.map_width,
                        (event.pos[1] - mm_y) / MINIMAP_SIZE * self.map_height,
                    )
                    continue
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
                (self.map_width * 0.62, self.map_height * 0.49),
                (self.map_width * 0.58, self.map_height * 0.32),
                (self.map_width * 0.58, self.map_height * 0.68),
            ]
        for x, y in candidates:
            if self.can_place_building(x, y, kind):
                return x, y
        for _ in range(25):
            x = random.randint(max(80, int(self.map_width * 0.55)), max(81, self.map_width - 80))
            y = random.randint(80, max(81, self.map_height - 80))
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
        render_production_panel(self)

    def draw_minimap(self):
        render_minimap(self)

    def draw_menu(self):
        self.screen.fill(COLOR_BG)
        title = self.big_font.render("钢河前线", True, COLOR_TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 90)))
        subtitle = self.font.render("选择战场", True, (175, 190, 210))
        self.screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, 160)))

        first_index = self.menu_visible_start()
        visible_count = 7
        visible_paths = self.map_paths[first_index:first_index + visible_count]
        for offset, path in enumerate(visible_paths):
            index = first_index + offset
            rect = self.menu_map_rect(offset)
            selected = index == self.selected_map_index
            color = (55, 85, 120) if selected else (38, 45, 56)
            pygame.draw.rect(self.screen, color, rect, border_radius=6)
            if selected:
                pygame.draw.rect(self.screen, (120, 190, 255), rect, 2, border_radius=6)
            label = self.font.render(path.stem, True, COLOR_TEXT)
            self.screen.blit(label, (rect.x + 16, rect.y + 10))

        if not self.map_paths:
            empty = self.font.render("maps 文件夹中没有地图，请先创建地图。", True, COLOR_MSG)
            self.screen.blit(empty, empty.get_rect(center=(WIDTH // 2, 300)))

        button = self.menu_start_rect()
        pygame.draw.rect(self.screen, (45, 125, 85), button, border_radius=8)
        pygame.draw.rect(self.screen, (120, 220, 160), button, 2, border_radius=8)
        label = self.font.render("开始游戏  (Enter)", True, COLOR_TEXT)
        self.screen.blit(label, label.get_rect(center=button.center))

        hint = self.font.render("↑ / ↓ 或鼠标选择地图    Esc 退出", True, (175, 185, 200))
        self.screen.blit(hint, hint.get_rect(center=(WIDTH // 2, HEIGHT - 48)))
        if self.menu_error:
            error = self.font.render(self.menu_error, True, COLOR_MSG)
            self.screen.blit(error, error.get_rect(center=(WIDTH // 2, HEIGHT - 175)))
        pygame.display.flip()

    def draw(self):
        if self.menu_active:
            self.draw_menu()
            return

        self.screen.fill(COLOR_BG)

        camera = (self.camera_x, self.camera_y)

        # 先画地形
        for m in self.mountains:
            m.draw(self.screen, camera)
        for r in self.rivers:
            r.draw(self.screen, camera)
        for b in self.bridges:
            b.draw(self.screen, camera)

        for node in self.resource_nodes:
            node.draw(self.screen, camera)
        for b in self.buildings:
            b.draw(self.screen, camera)
        for u in self.units:
            u.draw(self.screen, camera)

        if self.drag_start and not self.build_mode:
            mx, my = pygame.mouse.get_pos()
            x1 = self.drag_start[0] - self.camera_x
            y1 = self.drag_start[1] - self.camera_y
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
            if not self.menu_active:
                self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()
